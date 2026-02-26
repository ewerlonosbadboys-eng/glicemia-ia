import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Alignment, Font
from io import BytesIO
import hashlib

st.set_page_config(layout="wide")

# =====================================================
# ESTILO VISUAL RH
# =====================================================
st.markdown("""
<style>
thead tr th {
    background-color: #1f4e78 !important;
    color: white !important;
    text-align: center !important;
}
tbody tr:nth-child(even) {
    background-color: #e9f1f7 !important;
}
tbody tr:nth-child(odd) {
    background-color: #dbeaf5 !important;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# BANCO
# =====================================================
conn = sqlite3.connect("escala.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT,
    senha TEXT,
    categoria TEXT
)
""")

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
    saida TEXT
)
""")

conn.commit()

# =====================================================
# CRIAR ADMIN PADRÃO SE NÃO EXISTIR
# =====================================================
def gerar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

cursor.execute("SELECT * FROM usuarios WHERE usuario='admin'")
if not cursor.fetchone():
    cursor.execute(
        "INSERT INTO usuarios (usuario, senha, categoria) VALUES (?,?,?)",
        ("admin", gerar_hash("123"), "admin")
    )
    conn.commit()

# =====================================================
# LOGIN
# =====================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🔐 Login Sistema RH")

    user = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        cursor.execute("SELECT * FROM usuarios WHERE usuario=?", (user,))
        dados = cursor.fetchone()

        if dados and dados[2] == gerar_hash(senha):
            st.session_state.logado = True
            st.session_state.usuario = dados[1]
            st.session_state.categoria = dados[3]
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")
    st.stop()

# =====================================================
# MENU POR CATEGORIA
# =====================================================
st.sidebar.title("Menu")

menus = ["Visualizar Escala"]

if st.session_state.categoria in ["admin", "rh"]:
    menus.append("Gerar Escala")
    menus.append("Cadastrar Funcionário")
    menus.append("Cadastrar Usuário")

menu = st.sidebar.radio("Navegação", menus)

st.sidebar.write("Usuário:", st.session_state.usuario)
st.sidebar.write("Categoria:", st.session_state.categoria)

# =====================================================
# FUNÇÃO GERAR ESCALA 5x2 + DOMINGO 1x1
# =====================================================
def gerar_escala(mes, ano):
    cursor.execute("DELETE FROM escala")
    conn.commit()

    funcionarios = pd.read_sql_query("SELECT * FROM funcionarios", conn)

    datas = pd.date_range(f"{ano}-{mes:02d}-01", periods=31)

    alternador_domingo = 0

    for _, f in funcionarios.iterrows():
        dias_trabalhados = 0

        for data in datas:
            if data.month != mes:
                continue

            weekday = data.weekday()
            folga = False

            # 5x2
            if dias_trabalhados == 5:
                folga = True
                dias_trabalhados = 0

            # Domingo 1x1
            if weekday == 6:
                if alternador_domingo % 2 == 0:
                    folga = True
                alternador_domingo += 1

            if folga:
                cursor.execute(
                    "INSERT INTO escala VALUES (?,?,?,?)",
                    (f["id"], data.strftime("%Y-%m-%d"), "FOLGA", "FOLGA")
                )
            else:
                cursor.execute(
                    "INSERT INTO escala VALUES (?,?,?,?)",
                    (f["id"], data.strftime("%Y-%m-%d"), "06:00", "15:58")
                )
                dias_trabalhados += 1

    conn.commit()

# =====================================================
# VISUALIZAR ESCALA (FORMATO IGUAL IMAGEM)
# =====================================================
if menu == "Visualizar Escala":

    df_func = pd.read_sql_query("SELECT * FROM funcionarios", conn)
    df_escala = pd.read_sql_query("SELECT * FROM escala", conn)

    if df_escala.empty:
        st.warning("Gere a escala primeiro.")
        st.stop()

    dias = sorted(df_escala["data"].unique())

    colunas = ["Nome"]
    dias_formatados = []

    for d in dias:
        data_obj = datetime.strptime(d, "%Y-%m-%d")
        colunas.append(f"{data_obj.day}\n{data_obj.strftime('%a')}")

    tabela = []

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

        tabela.append(linha_entrada)
        tabela.append(linha_saida)

    df_visual = pd.DataFrame(tabela, columns=colunas)

    st.dataframe(df_visual, use_container_width=True)

# =====================================================
# GERAR ESCALA
# =====================================================
if menu == "Gerar Escala":
    mes = st.selectbox("Mês", range(1,13))
    ano = st.number_input("Ano", value=2026)

    if st.button("Gerar Automático"):
        gerar_escala(mes, ano)
        st.success("Escala gerada com regras automáticas!")

# =====================================================
# CADASTRAR FUNCIONÁRIO
# =====================================================
if menu == "Cadastrar Funcionário":
    nome = st.text_input("Nome")
    if st.button("Salvar"):
        cursor.execute("INSERT INTO funcionarios (nome) VALUES (?)", (nome,))
        conn.commit()
        st.success("Salvo")

# =====================================================
# CADASTRAR USUÁRIO (CATEGORIAS)
# =====================================================
if menu == "Cadastrar Usuário":

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    categoria = st.selectbox("Categoria", ["admin", "rh", "gerente", "profissional"])

    if st.button("Criar Usuário"):
        cursor.execute(
            "INSERT INTO usuarios (usuario, senha, categoria) VALUES (?,?,?)",
            (usuario, gerar_hash(senha), categoria)
        )
        conn.commit()
        st.success("Usuário criado com categoria!")
