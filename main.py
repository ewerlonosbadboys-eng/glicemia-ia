# ============================================================
# SISTEMA ESCALA PRO - VERSÃO CORPORATIVA COMPLETA
# Login + Banco SQLite + Calendário RH + Banco Horas + Excel
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, timedelta
import plotly.express as px
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Alignment, Border, Side
import io

st.set_page_config(layout="wide", page_title="Escala PRO Corporativo")

# ============================================================
# BANCO DE DADOS
# ============================================================

conn = sqlite3.connect("escala_pro.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS setores(
    setor TEXT PRIMARY KEY,
    senha TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS usuarios(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    setor TEXT,
    categoria TEXT,
    carga_diaria REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS escalas(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    data TEXT,
    entrada TEXT,
    saida TEXT,
    status TEXT
)
""")

conn.commit()

# ============================================================
# LOGIN REAL
# ============================================================

if "logado" not in st.session_state:
    st.session_state.logado = False

st.sidebar.title("🔐 Login Setor")

setor = st.sidebar.text_input("Setor")
senha = st.sidebar.text_input("Senha", type="password")

if st.sidebar.button("Entrar"):
    user = c.execute("SELECT * FROM setores WHERE setor=? AND senha=?",
                     (setor, senha)).fetchone()
    if user:
        st.session_state.logado = True
        st.session_state.setor = setor
    else:
        st.sidebar.error("Acesso negado")

if not st.session_state.logado:
    st.stop()

st.sidebar.success(f"Logado: {st.session_state.setor}")

# ============================================================
# TABS
# ============================================================

aba1, aba2, aba3, aba4 = st.tabs([
    "Cadastro",
    "Calendário RH",
    "Dashboard",
    "Exportar Excel"
])

# ============================================================
# CADASTRO
# ============================================================

with aba1:

    nome = st.text_input("Nome Funcionário")
    categoria = st.text_input("Categoria")
    carga = st.number_input("Carga diária padrão (horas)", value=8.0)

    if st.button("Salvar Funcionário"):
        c.execute("""
        INSERT INTO usuarios(nome,setor,categoria,carga_diaria)
        VALUES(?,?,?,?)
        """,(nome, st.session_state.setor, categoria, carga))
        conn.commit()
        st.success("Salvo")

# ============================================================
# CALENDÁRIO ESTILO RH
# ============================================================

with aba2:

    ano = datetime.now().year
    mes = datetime.now().month

    dias_mes = calendar.monthrange(ano, mes)[1]

    usuarios = pd.read_sql_query("""
    SELECT * FROM usuarios WHERE setor=?
    """, conn, params=(st.session_state.setor,))

    if not usuarios.empty:

        tabela = []

        for _, user in usuarios.iterrows():

            linha = {"Nome": user["nome"]}

            for dia in range(1, dias_mes+1):
                data_str = f"{ano}-{mes:02d}-{dia:02d}"

                escala = c.execute("""
                SELECT * FROM escalas
                WHERE usuario_id=? AND data=?
                """,(user["id"], data_str)).fetchone()

                if escala:
                    linha[dia] = escala[3] if escala[5]=="Trabalho" else "F"
                else:
                    linha[dia] = ""

            tabela.append(linha)

        df_cal = pd.DataFrame(tabela)
        st.dataframe(df_cal, use_container_width=True)

# ============================================================
# DASHBOARD + BANCO HORAS
# ============================================================

with aba3:

    df = pd.read_sql_query("""
    SELECT u.nome, e.data, e.entrada, e.saida, u.carga_diaria
    FROM escalas e
    JOIN usuarios u ON u.id=e.usuario_id
    WHERE u.setor=?
    """, conn, params=(st.session_state.setor,))

    if not df.empty:

        df["data"] = pd.to_datetime(df["data"])
        df["horas_trabalhadas"] = (
            pd.to_datetime(df["saida"], format="%H:%M") -
            pd.to_datetime(df["entrada"], format="%H:%M")
        ).dt.total_seconds() / 3600

        df["banco_horas"] = df["horas_trabalhadas"] - df["carga_diaria"]

        resumo = df.groupby("nome")["banco_horas"].sum().reset_index()

        fig = px.bar(resumo, x="nome", y="banco_horas",
                     title="Indicador Banco de Horas")

        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# EXPORTAÇÃO EXCEL MODELO RH
# ============================================================

with aba4:

    if st.button("Baixar Excel Modelo RH"):

        wb = Workbook()
        ws = wb.active
        ws.title = "Escala"

        fill_folga = PatternFill(start_color="FFFF00",
                                 end_color="FFFF00",
                                 fill_type="solid")

        center = Alignment(horizontal="center", vertical="center")
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        usuarios = pd.read_sql_query("""
        SELECT * FROM usuarios WHERE setor=?
        """, conn, params=(st.session_state.setor,))

        dias_mes = calendar.monthrange(ano, mes)[1]

        for col in range(1, dias_mes+1):
            ws.cell(1, col+1, col)

        row = 2

        for _, user in usuarios.iterrows():

            ws.cell(row,1,user["nome"])

            for dia in range(1,dias_mes+1):

                data_str=f"{ano}-{mes:02d}-{dia:02d}"

                escala=c.execute("""
                SELECT * FROM escalas
                WHERE usuario_id=? AND data=?
                """,(user["id"],data_str)).fetchone()

                cell=ws.cell(row,dia+1)

                if escala:
                    if escala[5]=="Folga":
                        cell.value="F"
                        cell.fill=fill_folga
                    else:
                        cell.value=escala[3]

                cell.alignment=center
                cell.border=border

            row+=1

        buffer=io.BytesIO()
        wb.save(buffer)

        st.download_button(
            "Download Excel",
            data=buffer.getvalue(),
            file_name="escala_rh.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
