import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# Configuração inicial
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

if 'db_users' not in st.session_state:
    st.session_state['db_users'] = []
if 'db_cats' not in st.session_state:
    st.session_state['db_cats'] = ["Geral"]

st.title("🚀 Gerenciador de Escala Inteligente")

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
            st.success(f"{nome} cadastrado!")
        else:
            st.error("Digite o nome!")

    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerador de Escala")
    if not st.session_state['db_users']:
        st.info("Cadastre funcionários primeiro.")
    else:
        setor_sel = st.selectbox("Escolha o Setor", st.session_state['db_cats'])
        if st.button("GERAR ESCALA DA CATEGORIA"):
            # Lógica de datas para Março/2026
            datas = pd.date_range(start='2026-03-01', end='2026-03-31')
            df_escala = pd.DataFrame({
                'Data': datas.strftime('%d/%m/%Y'),
                'Dia': datas.day_name(),
                'Status': ['Trabalho'] * len(datas)
            })
            
            # Marca folgas nos domingos para o exemplo
            df_escala.loc[df_escala['Dia'] == 'Sunday', 'Status'] = 'Folga'
            
            st.write(f"### Escala:
