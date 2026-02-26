# ============================================
# SISTEMA PROFISSIONAL DE ESCALA 5x2 - PRO
# Banco SQLite + Login + Dashboard + Rodízio Anual
# ============================================

import streamlit as st
import pandas as pd
import sqlite3
import random
from datetime import datetime, timedelta
import calendar
import plotly.express as px

st.set_page_config(layout="wide", page_title="Sistema Escala PRO")

# ============================================
# CONFIGURAÇÕES
# ============================================

AS_SISTEMA = {
    "ESCALA": "5x2",
    "INTERSTICIO": "11h10",
    "DOMINGOS": "1x1 alternado",
    "FOLGA_CASADA": "Domingo + Segunda (Subgrupo)",
    "RODIZIO_SABADO": "1 pessoa por sábado no grupo",
    "BALANCEAMENTO": "Máx 50% setor folgando",
    "LIMITE_CONSECUTIVO": "5 dias"
}

# ============================================
# BANCO SQLITE
# ============================================

conn = sqlite3.connect("escala_pro.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    setor TEXT,
    categoria TEXT,
    subgrupo TEXT,
    entrada TEXT,
    rod_sab INTEGER,
    folga_dom_seg INTEGER,
    ferias_inicio TEXT,
    ferias_fim TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS escalas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    data TEXT,
    status TEXT,
    entrada TEXT,
    saida TEXT
)
""")

conn.commit()

# ============================================
# LOGIN POR SETOR
# ============================================

if "setor_logado" not in st.session_state:
    st.session_state.setor_logado = None

st.sidebar.title("🔐 Login por Setor")

setor_login = st.sidebar.text_input("Digite seu setor")

if st.sidebar.button("Entrar"):
    if setor_login:
        st.session_state.setor_logado = setor_login

if not st.session_state.setor_logado:
    st.stop()

st.sidebar.success(f"Setor: {st.session_state.setor_logado}")

# ============================================
# FUNÇÕES
# ============================================

def descanso_ok(saida_anterior, entrada):
    if not saida_anterior:
        return entrada
    s = datetime.strptime(saida_anterior,"%H:%M")
    e = datetime.strptime(entrada,"%H:%M")
    if (e - s).total_seconds() < 40200:
        return (s + timedelta(hours=11,minutes=10)).strftime("%H:%M")
    return entrada


def gerar_ano(usuario_id, entrada_padrao, subgrupo, rod_sab, folga_dom_seg):

    ano = datetime.now().year
    entrada_padrao = entrada_padrao or "06:00"

    for mes in range(1,13):

        dias_mes = calendar.monthrange(ano, mes)[1]

        for dia in range(1,dias_mes+1):

            data = datetime(ano,mes,dia)
            dia_semana = data.weekday()

            status = "Trabalho"

            # DOMINGO
            if dia_semana == 6:

                if subgrupo and folga_dom_seg:
                    status = "Folga"
                else:
                    if random.choice([True,False]):
                        status = "Folga"

            # SE TRABALHOU DOMINGO -> folga segunda a sexta aleatória
            if dia_semana == 6 and status == "Trabalho":
                dia_extra = data + timedelta(days=random.randint(1,5))
                c.execute("""
                INSERT INTO escalas(usuario_id,data,status,entrada,saida)
                VALUES(?,?,?,?,?)
                """,(usuario_id,dia_extra.strftime("%Y-%m-%d"),"Folga","",""))

            # SÁBADO ROTATIVO 1 PESSOA
            if dia_semana == 5 and subgrupo and rod_sab:
                # apenas 1 pessoa por sábado
                c.execute("""
                SELECT COUNT(*) FROM escalas 
                WHERE data=? AND status='Folga'
                """,(data.strftime("%Y-%m-%d"),))
                total = c.fetchone()[0]
                if total == 0:
                    status = "Folga"

            # horário
            if status == "Trabalho":
                entrada = entrada_padrao
                saida = (datetime.strptime(entrada,"%H:%M")+timedelta(hours=9,minutes=58)).strftime("%H:%M")
            else:
                entrada = ""
                saida = ""

            c.execute("""
            INSERT INTO escalas(usuario_id,data,status,entrada,saida)
            VALUES(?,?,?,?,?)
            """,(usuario_id,data.strftime("%Y-%m-%d"),status,entrada,saida))

    conn.commit()


# ============================================
# TABS
# ============================================

aba1,aba2,aba3,aba4,aba5 = st.tabs([
    "Cadastro",
    "Gerar Escala Ano",
    "Ajustes",
    "Dashboard",
    "Férias"
])

# ============================================
# CADASTRO
# ============================================

with aba1:

    nome = st.text_input("Nome")
    categoria = st.text_input("Categoria")
    subgrupo = st.text_input("Subgrupo (opcional)")
    entrada = st.time_input("Entrada padrão")
    rod_sab = st.checkbox("Subgrupo folga sábado rotativo")
    folga_dom_seg = st.checkbox("Subgrupo folga Domingo + Segunda")

    if st.button("Salvar"):
        c.execute("""
        INSERT INTO usuarios(nome,setor,categoria,subgrupo,entrada,rod_sab,folga_dom_seg)
        VALUES(?,?,?,?,?,?,?)
        """,(nome,
             st.session_state.setor_logado,
             categoria,
             subgrupo,
             entrada.strftime("%H:%M"),
             int(rod_sab),
             int(folga_dom_seg)))
        conn.commit()
        st.success("Salvo")


# ============================================
# GERAR ESCALA 1 ANO
# ============================================

with aba2:

    usuarios = c.execute("""
    SELECT * FROM usuarios WHERE setor=?
    """,(st.session_state.setor_logado,)).fetchall()

    if st.button("Gerar Escala 12 Meses"):

        for u in usuarios:
            gerar_ano(u[0],u[5],u[4],u[6],u[7])

        st.success("Escala anual gerada!")


# ============================================
# AJUSTES
# ============================================

with aba3:

    usuarios = c.execute("""
    SELECT id,nome FROM usuarios WHERE setor=?
    """,(st.session_state.setor_logado,)).fetchall()

    user_sel = st.selectbox("Usuário",[u[1] for u in usuarios])

    user_id = [u[0] for u in usuarios if u[1]==user_sel][0]

    st.markdown("### Trocar Folga")

    data_sel = st.date_input("Data")
    novo_status = st.selectbox("Status",["Trabalho","Folga"])

    if st.button("Atualizar Status"):
        c.execute("""
        UPDATE escalas SET status=? WHERE usuario_id=? AND data=?
        """,(novo_status,user_id,data_sel.strftime("%Y-%m-%d")))
        conn.commit()
        st.success("Atualizado")

    st.markdown("### Alterar Categoria")

    nova_cat = st.text_input("Nova Categoria")
    if st.button("Salvar Categoria"):
        c.execute("""
        UPDATE usuarios SET categoria=? WHERE id=?
        """,(nova_cat,user_id))
        conn.commit()
        st.success("Categoria alterada")


# ============================================
# DASHBOARD
# ============================================

with aba4:

    df = pd.read_sql_query("""
    SELECT status,data FROM escalas
    """,conn)

    df["data"] = pd.to_datetime(df["data"])

    resumo = df.groupby("status").count().reset_index()

    fig = px.pie(resumo,names="status",values="data",title="Distribuição Trabalho x Folga")

    st.plotly_chart(fig,use_container_width=True)


# ============================================
# FÉRIAS
# ============================================

with aba5:

    usuarios = c.execute("""
    SELECT id,nome FROM usuarios WHERE setor=?
    """,(st.session_state.setor_logado,)).fetchall()

    user_sel = st.selectbox("Usuário Férias",[u[1] for u in usuarios])
    user_id = [u[0] for u in usuarios if u[1]==user_sel][0]

    inicio = st.date_input("Início férias")
    fim = st.date_input("Fim férias")

    if st.button("Aplicar Férias"):

        c.execute("""
        UPDATE escalas SET status='Férias', entrada='', saida=''
        WHERE usuario_id=? AND data BETWEEN ? AND ?
        """,(user_id,inicio.strftime("%Y-%m-%d"),fim.strftime("%Y-%m-%d")))

        conn.commit()
        st.success("Férias aplicadas")
