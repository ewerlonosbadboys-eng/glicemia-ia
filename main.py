
import streamlit as st
import pandas as pd
from datetime import date

# Configuração da página (DEVE ser a primeira linha de código)
st.set_page_config(page_title="Gestor Pro Escala", layout="wide")

# Inicialização segura da memória (impede a tela preta)
if 'db_users' not in st.session_state:
    st.session_state['db_users'] = []
if 'db_cats' not in st.session_state:
    st.session_state['db_cats'] = ["Geral"]

st.title("🚀 Gerenciador de Escala Inteligente")

# Criando as abas
aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala"])

with aba2:
    st.subheader("Gerenciar Setores")
    nova_cat = st.text_input("Nome do novo setor")
    if st.button("Salvar Categoria"):
        if nova_cat not in st.session_state['db_cats']:
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
            st.success(f"{nome} cadastrado!")
        else:
            st.error("Digite um nome!")

    st.write("### Usuários Cadastrados")
    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users']))
    else:
        st.info("Nenhum funcionário cadastrado ainda.")

with aba3:
    st.subheader("Gerador de Escala")
    st.write("Selecione o setor e o mês para gerar a tabela.")
    # Aqui viria a lógica de geração que já temos...
