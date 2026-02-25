import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

# Configuração da página
st.set_page_config(page_title="Gerenciador de Escala Inteligente", layout="wide")

# Inicialização do estado do sistema
if 'db_users' not in st.session_state:
    st.session_state['db_users'] = []
if 'db_cats' not in st.session_state:
    st.session_state['db_cats'] = ["Geral"]

st.title("🚀 Gerenciador de Escala Inteligente")

# Criando as abas de navegação
aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala"])

# --- ABA 2: CATEGORIAS ---
with aba2:
    st.subheader("Gerenciar Setores")
    nova_cat = st.text_input("Nome do novo setor")
    if st.button("Salvar Categoria"):
        if nova_cat and nova_cat not in st.session_state['db_cats']:
            st.session_state['db_cats'].append(nova_cat)
            st.success("Categoria adicionada!")

# --- ABA 1: CADASTRO DE FUNCIONÁRIOS ---
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
            st.success(f"{nome} cadastrado com sucesso!")
        else:
            st.error("Por favor, digite o nome do funcionário.")

    if st.session_state['db_users']:
        st.write("### Equipe Cadastrada")
        st.table(pd.DataFrame(st.session_state['db_users']))

# --- ABA 3: GERADOR DE ESCALA ---
with aba3:
    st.subheader("Gerador de Escala")
    
    if not st.session_state['db_users']:
        st.info("Cadastre funcionários primeiro para gerar a escala.")
    else:
        setor_sel = st.selectbox("Escolha o Setor para Escala", st.session_state['db_cats'])
        mes_sel = st.selectbox("Mês", ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                                      "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"])
        
        # Lógica simplificada de geração para exemplo (5x2)
        if st.button("GERAR ESCALA DA CATEGORIA"):
            datas = pd.date_range(start='2026-03-01', periods=31) # Exemplo para Março
            df_escala = pd.DataFrame({
                'Data': datas.strftime('%d/%m/%Y'),
                'Dia': datas.day_name(),
                'Status': ['Trabalho'] * 31
            })
            
            # Exemplo de Folga simples para visualização
            df_escala.loc[df_escala['Dia'] == 'Sunday', 'Status'] = 'Folga'
            
            st.write(f"### Escala: {setor_sel}")
            st.table(df_escala)

            # --- EXPORTAÇÃO EXCEL CONFIGURADA (CORES E PORTUGUÊS) ---
            try:
                from openpyxl.styles import PatternFill, Font
                
                # Tradução dos dias
                dias_pt = {
                    'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 
                    'Wednesday': 'Quarta-feira', 'Thursday': 'Quinta-feira', 
                    'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
                }

                df_export = df_escala.copy()
                df_export['Dia'] = df_export['Dia'].map(dias_pt)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Escala')
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Escala']
                    
                    # Cores solicitadas
                    color_folga = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid") # Amarelo
                    color_domingo = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid") # Vermelho
                    font_branca = Font(color="FFFFFF", bold=True)

                    for row_idx, row_data in enumerate(df_export.values
