import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Função de Login
def check_password():
    def password_guessed():
        if st.session_state["username"] == "admin" and st.session_state["password"] == "123":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Limpa senha da memória
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Acesso Restrito")
        st.text_input("Usuário", on_change=None, key="username")
        st.text_input("Senha", type="password", on_change=None, key="password")
        if st.button("Entrar"):
            password_guessed()
            if not st.session_state["password_correct"]:
                st.error("😕 Usuário ou senha incorretos.")
                return False
            else:
                st.rerun()
        return False
    return True

# Só carrega o app se o login estiver correto
if check_password():
    # Inicialização da memória
    if 'db_users' not in st.session_state:
        st.session_state['db_users'] = []
    if 'db_cats' not in st.session_state:
        st.session_state['db_cats'] = ["Geral"]

    st.title("🚀 Gerenciador de Escala Inteligente")
    
    # Logout lateral
    st.sidebar.button("Sair / Bloquear", on_click=lambda: st.session_state.clear())

    # Abas
    aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala"])

    with aba2:
        st.subheader("Gerenciar Setores")
        nova_cat = st.text_input("Nome do novo setor")
        if st.button("Salvar Categoria"):
            if nova_cat and nova_cat not in st.session_state['db_cats']:
                st.session_state['db_cats'].append(nova_cat)
                st.success("Categoria adicionada!")

    with aba1:
        st.subheader("Cadastro de Funcionário")
        nome = st.text_input("Nome Completo")
        setor = st.selectbox("Categoria/Setor", st.session_state['db_cats'])
        
        col1, col2 = st.columns(2)
        r_sabado = col1.checkbox("Participar do rodízio de sábado")
        r_dom_seg = col2.checkbox("Se folgar Domingo, folga Segunda também")
        
        if st.button("Salvar Usuário"):
            if nome:
                st.session_state['db_users'].append({
                    "Nome": nome, "Setor": setor, 
                    "Rodízio Sáb": r_sabado, "Folga Casada": r_dom_seg
                })
