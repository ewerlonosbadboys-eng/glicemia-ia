import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Alignment
from io import BytesIO
import hashlib

st.set_page_config(layout="wide")

# =====================================================
# CONFIGURAÇÃO
# =====================================================
INTERSTICIO_MINUTOS = 670  # 11h10
HORARIO_ENTRADA = "06:00"
HORARIO_SAIDA = "15:58"

# =====================================================
# BANCO DE DADOS
# =====================================================
conn = sqlite3.connect("escala.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS funcionarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS escala (
    funcionario_id INTEGER,
    data TEXT,
    entrada TEXT,
    saida TEXT,
    FOREIGN KEY(funcionario_id) REFERENCES funcionarios(id)
)
""")

conn.commit()

# =====================================================
# FUNÇÃO HASH LOGIN
# =====================================================
def gerar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

USUARIOS = {
    "admin": gerar_hash("123")
}

# =====================================================
# LOGIN
# =====================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("Login Sistema RH")
    user = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if user in USUARIOS and USUARIOS[user] == gerar_hash(senha):
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Login inválido")
    st.stop()

# =====================================================
# FUNÇÃO GERAR ESCALA AUTOMÁTICA
# =====================================================
def gerar_escala(mes, ano):

    cursor.execute("DELETE FROM escala")
    conn.commit()

    cursor.execute("SELECT * FROM funcionarios")
    funcionarios = cursor.fetchall()

    dias_mes = pd.date_range(f"{ano}-{mes:02d}-01", periods=31)

    domingo_toggle = 0

    for f in funcionarios:
        dias_trabalhados = 0
        for data in dias_mes:

            if data.month != mes:
                continue

            weekday = data.weekday()  # 6 domingo

            folga = False

            # Regra 5x2
            if dias_trabalhados == 5:
                folga = True
                dias_trabalhados = 0

            # Regra Domingo 1x1 alternado
            if weekday == 6:
                if domingo_toggle % 2 == 0:
                    folga = True
                domingo_toggle += 1

            # Balanceamento 50% (simples)
            cursor.execute("""
            SELECT COUNT(*) FROM escala
            WHERE data=? AND entrada='FOLGA'
            """, (data.strftime("%Y-%m-%d"),))
            folgas_no_dia = cursor.fetchone()[0]

            if folgas_no_dia >= len(funcionarios)/2:
                folga = False

            if folga:
                cursor.execute("""
                INSERT INTO escala VALUES (?,?,?,?)
                """, (f[0], data.strftime("%Y-%m-%d"), "FOLGA", "FOLGA"))
            else:
                cursor.execute("""
                INSERT INTO escala VALUES (?,?,?,?)
                """, (f[0], data.strftime("%Y-%m-%d"), HORARIO_ENTRADA, HORARIO_SAIDA))
                dias_trabalhados += 1

    conn.commit()

# =====================================================
# MENU
# =====================================================
st.sidebar.title("Menu")
menu = st.sidebar.radio("Navegação", ["Cadastrar Funcionário", "Gerar Escala", "Exportar Excel"])

# =====================================================
# CADASTRO
# =====================================================
if menu == "Cadastrar Funcionário":
    nome = st.text_input("Nome Funcionário")
    if st.button("Salvar"):
        cursor.execute("INSERT INTO funcionarios (nome) VALUES (?)", (nome,))
        conn.commit()
        st.success("Funcionário cadastrado")

    df = pd.read_sql_query("SELECT * FROM funcionarios", conn)
    st.dataframe(df, use_container_width=True)

# =====================================================
# GERAR ESCALA
# =====================================================
if menu == "Gerar Escala":
    mes = st.selectbox("Mês", list(range(1,13)))
    ano = st.number_input("Ano", value=2026)

    if st.button("Gerar Escala Automática"):
        gerar_escala(mes, ano)
        st.success("Escala gerada com regras automáticas!")

# =====================================================
# EXPORTAR FORMATO IGUAL IMAGEM
# =====================================================
if menu == "Exportar Excel":

    df_func = pd.read_sql_query("SELECT * FROM funcionarios", conn)
    df_escala = pd.read_sql_query("SELECT * FROM escala", conn)

    if df_escala.empty:
        st.warning("Gere a escala primeiro.")
        st.stop()

    wb = Workbook()
    ws = wb.active
    ws.title = "Escala Mensal"

    dias = sorted(df_escala["data"].unique())
    cabecalho = [""] + [datetime.strptime(d, "%Y-%m-%d").day for d in dias]
    ws.append(cabecalho)

    for _, func in df_func.iterrows():
        linha_entrada = [func["nome"]]
        linha_saida = [""]

        for d in dias:
            registro = df_escala[
                (df_escala["funcionario_id"] == func["id"]) &
                (df_escala["data"] == d)
            ]

            if not registro.empty:
                linha_entrada.append(registro.iloc[0]["entrada"])
                linha_saida.append(registro.iloc[0]["saida"])
            else:
                linha_entrada.append("")
                linha_saida.append("")

        ws.append(linha_entrada)
        ws.append(linha_saida)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    st.download_button(
        "Baixar Escala Formato RH",
        buffer,
        "escala_mensal_rh.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
