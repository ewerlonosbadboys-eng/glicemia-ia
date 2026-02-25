import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Sistema de Login
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acesso Restrito")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return False
    return True

if check_password():
    # Inicialização de Memória e Histórico
    if 'db_users' not in st.session_state: st.session_state['db_users'] = []
    if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
    if 'historico' not in st.session_state: st.session_state['historico'] = {}

    st.sidebar.button("Sair", on_click=lambda: st.session_state.clear())
    st.title("🚀 Gerenciador de Escala Inteligente")

    # Abas do Aplicativo
    aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala", "📜 Histórico"])

    with aba2:
        st.subheader("Configurar Setores")
        nova_cat = st.text_input("Nome do novo setor")
        if st.button("Adicionar Setor"):
            if nova_cat and nova_cat not in st.session_state['db_cats']:
                st.session_state['db_cats'].append(nova_cat)
                st.success("Setor adicionado!")

    with aba1:
        st.subheader("Cadastro de Funcionários")
        nome = st.text_input("Nome Completo")
        setor = st.selectbox("Setor Responsável", st.session_state['db_cats'])
        c1, c2 = st.columns(2)
        f_sabado = c1.checkbox("Rodízio aos Sábados")
        f_casada = c2.checkbox("Folga Casada (Dom + Seg)")
        
        if st.button("Salvar Funcionário"):
            if nome:
                st.session_state['db_users'].append({
                    "Nome": nome, "Setor": setor, 
                    "Sábado": f_sabado, "Casada": f_casada
                })
                st.success(f"{nome} cadastrado com sucesso!")
        
        if st.session_state['db_users']:
            st.table(pd.DataFrame(st.session_state['db_users']))

    with aba3:
        st.subheader("Gerador de Escala Mensal")
        if not st.session_state['db_users']:
            st.warning("Cadastre a equipe primeiro!")
        else:
            setor_sel = st.selectbox("Gerar escala para:", st.session_state['db_cats'])
            mes_ref = st.selectbox("Mês de Referência", ["Março 2026", "Abril 2026"])
            
            if st.button("✨ GERAR E SALVAR"):
                # Simulação de datas para Março 2026
                datas = pd.date_range(start='2026-03-01', end='2026-03-31')
                df = pd.DataFrame({
                    'Data': datas.strftime('%d/%m/%Y'),
                    'Dia': datas.day_name(),
                    'Status': '
