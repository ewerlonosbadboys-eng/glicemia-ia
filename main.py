import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Login
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Login Administrativo")
        user = st.text_input("Usuário", key="username")
        pw = st.text_input("Senha", type="password", key="password")
        if st.button("Entrar"):
            if user == "admin" and pw == "123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return False
    return True

if check_password():
    # Inicialização da memória e histórico
    if 'db_users' not in st.session_state: st.session_state['db_users'] = []
    if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
    if 'historico_escalas' not in st.session_state: st.session_state['historico_escalas'] = {}

    st.sidebar.button("Sair", on_click=lambda: st.session_state.clear())
    st.title("🚀 Gerenciador de Escala com Histórico")

    aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala", "📜 Histórico"])

    with aba2:
        st.subheader("Gerenciar Setores")
        nova_cat = st.text_input("Novo setor")
        if st.button("Salvar Categoria"):
            if nova_cat and nova_cat not in st.session_state['db_cats']:
                st.session_state['db_cats'].append(nova_cat)
                st.success("Categoria salva!")

    with aba1:
        st.subheader("Cadastro de Equipe")
        nome = st.text_input("Nome")
        setor = st.selectbox("Setor", st.session_state['db_cats'])
        c1, c2 = st.columns(2)
        r_sab = c1.checkbox("Rodízio de Sábado")
        r_dc = c2.checkbox("Folga Casada (Dom+Seg)")
        if st.button("Cadastrar"):
            if nome:
                st.session_state['db_users'].append({"Nome": nome, "Setor": setor, "Sáb": r_sab, "Casada": r_dc})
                st.success("OK!")
        if st.session_state['db_users']: st.table(pd.DataFrame(st.session_state['db_users']))

    with aba3:
        st.subheader("Gerar Nova Escala")
        if not st.session_state['db_users
