import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook

# ==========================================
# CONFIGURAÇÃO
# ==========================================
st.set_page_config(page_title="Sistema RH Escala", layout="wide")

# ==========================================
# FUNÇÃO HASH
# ==========================================
def gerar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# ==========================================
# USUÁRIOS
# ==========================================
USUARIOS = {
    "admin": {
        "senha": gerar_hash("123"),
        "categoria": "admin"
    },
    "profissional": {
        "senha": gerar_hash("123"),
        "categoria": "profissional"
    }
}

# ==========================================
# SESSION STATE
# ==========================================
if "logado" not in st.session_state:
    st.session_state.logado = False
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "categoria" not in st.session_state:
    st.session_state.categoria = None

# ==========================================
# FUNÇÃO LOGIN
# ==========================================
def login(usuario, senha):
    if usuario in USUARIOS:
        if USUARIOS[usuario]["senha"] == gerar_hash(senha):
            st.session_state.logado = True
            st.session_state.usuario = usuario
            st.session_state.categoria = USUARIOS[usuario]["categoria"]
            return True
    return False

# ==========================================
# TELA LOGIN
# ==========================================
if not st.session_state.logado:
    st.title("🔐 Login Sistema RH")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if login(usuario, senha):
            st.success("Login realizado!")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")

# ==========================================
# SISTEMA
# ==========================================
else:
    st.sidebar.title("Menu")
    menu = st.sidebar.radio("Navegação", ["Escala", "Ajustes", "Banco de Horas"])

    st.sidebar.write(f"Usuário: {st.session_state.usuario}")
    st.sidebar.write(f"Categoria: {st.session_state.categoria}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    # ======================================
    # BASE ESCALA SIMULADA
    # ======================================
    nomes = [
        "Viviane", "Maria Eduarda", "Tatiane",
        "Fabiana", "Elizangela", "Disnei",
        "Marivaldo", "Joao Victor", "Deybson"
    ]

    dias = list(range(1, 32))
    dados = []

    for nome in nomes:
        linha = {"Nome": nome}
        for dia in dias:
            linha[str(dia)] = "06:00 - 15:58"
        dados.append(linha)

    df = pd.DataFrame(dados)

    # ======================================
    # ABA ESCALA
    # ======================================
    if menu == "Escala":
        st.title("📅 Calendário de Escala")

        st.dataframe(df, use_container_width=True)

        st.download_button(
            label="⬇ Baixar Escala Excel",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="escala.csv",
            mime="text/csv"
        )

    # ======================================
    # ABA AJUSTES (ADMIN)
    # ======================================
    if menu == "Ajustes":

        if st.session_state.categoria != "admin":
            st.warning("Somente ADMIN pode fazer ajustes.")
        else:
            st.title("⚙ Ajustes de Escala")

            funcionario = st.selectbox("Selecionar Funcionário", nomes)
            dia = st.selectbox("Selecionar Dia", dias)

            nova_acao = st.radio("Tipo de Ajuste", [
                "Trocar Horário",
                "Dar Folga",
                "Trocar Categoria Usuário"
            ])

            if nova_acao == "Trocar Horário":
                novo_horario = st.text_input("Novo Horário (ex: 08:00 - 17:48)")
                if st.button("Salvar Horário"):
                    df.loc[df["Nome"] == funcionario, str(dia)] = novo_horario
                    st.success("Horário atualizado!")

            if nova_acao == "Dar Folga":
                if st.button("Confirmar Folga"):
                    df.loc[df["Nome"] == funcionario, str(dia)] = "FOLGA"
                    st.success("Folga aplicada!")

            if nova_acao == "Trocar Categoria Usuário":
                usuario_alvo = st.selectbox("Usuário", list(USUARIOS.keys()))
                nova_categoria = st.selectbox("Nova Categoria", ["admin", "profissional"])
                if st.button("Alterar Categoria"):
                    USUARIOS[usuario_alvo]["categoria"] = nova_categoria
                    st.success("Categoria alterada!")

    # ======================================
    # BANCO DE HORAS
    # ======================================
    if menu == "Banco de Horas":
        st.title("📊 Indicador Banco de Horas")

        col1, col2, col3 = st.columns(3)

        col1.metric("Horas Trabalhadas", "176h")
        col2.metric("Horas Contratuais", "160h")
        col3.metric("Saldo", "+16h")

        st.progress(0.65)

    # ======================================
    # MODELO EXCEL
    # ======================================
    st.sidebar.markdown("---")
    if st.sidebar.button("Baixar Modelo Excel RH"):

        wb = Workbook()
        ws = wb.active
        ws.title = "Modelo Escala"

        ws.append(["Nome"] + dias)

        for nome in nomes:
            ws.append([nome] + ["06:00 - 15:58"] * 31)

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        st.download_button(
            label="Download Modelo",
            data=buffer,
            file_name="modelo_escala_rh.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
