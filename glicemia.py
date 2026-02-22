import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from openpyxl.styles import PatternFill
import plotly.express as px
import pytz

# Fuso Horário Brasil
fuso_br = pytz.timezone('America/Sao_Paulo')

# IA Config
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia & Nutrição", page_icon="🩸", layout="wide")

ARQUIVO_GLIC = "historico_glicemia.csv"
ARQUIVO_NUTRI = "historico_nutricao.csv"

# --- BANCO DE DADOS DE ALIMENTOS ---
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Pão de Forma (1 fatia)": [12, 2, 1],
    "Café com Açúcar": [10, 0, 0],
    "Café com Adoçante": [0, 0, 0],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz (3 colheres)": [15, 1.5, 0],
    "Feijão (1 concha)": [14, 5, 0.5],
    "Frango Grelhado": [0, 23, 5],
    "Ovo Cozido": [1, 6, 5],
    "Maçã (1 un)": [15, 0, 0],
    "Banana (1 un)": [22, 1, 0]
}

def carregar_dados(arq):
    if os.path.isfile(arq):
        df = pd.read_csv(arq)
        return df
    return pd.DataFrame()

# --- INTERFACE PRINCIPAL ---
st.title("🩸 Painel de Controle de Saúde")
tab1, tab2 = st.tabs(["📊 Relatório Glicemia", "🍽️ Diário Alimentar"])

# --- ABA 1: GLICEMIA ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        v_man = st.number_input("Valor Glicemia:", min_value=0, max_value=600)
        cat_g = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 SALVAR GLICEMIA"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_man, cat_g]], columns=["Data", "Hora", "Valor", "Categoria"])
            df_atual = carregar_dados(ARQUIVO_GLIC)
            pd.concat([df_atual, novo], ignore_index=True).to_csv(ARQUIVO_GLIC, index=False)
            st.success("Glicemia salva!")
            st.rerun()
    with col2:
        df_g = carregar_dados(ARQUIVO_GLIC)
        if not df_g.empty:
            hoje = datetime.now(fuso_br).strftime("%d/%m/%Y")
            df_h = df_g[df_g['Data'] == hoje].sort_values('Hora')
            if not df_h.empty:
                fig_picos = px.line(df_h, x='Hora', y='Valor', title="Picos de Glicemia Hoje", markers=True)
                st.plotly_chart(fig_picos, use_container_width=True)

# --- ABA 2: ALIMENTAÇÃO ---
with tab2:
    st.subheader("O que ela comeu?")
    col_n1, col_n2 = st.columns([1, 1])
    
    with col_n1:
        refeicao = st.selectbox("Refeição:", ["Café Manhã", "Lanche Manhã", "Almoço", "Merenda", "Jantar", "Ceia"])
        itens = st.multiselect("Selecione os alimentos:", list(ALIMENTOS.keys()))
        
        total_c = sum([ALIMENTOS[i][0] for i in itens])
        total_p = sum([ALIMENTOS[i][1] for i in itens])
        total_g = sum([ALIMENTOS[i][2] for i in itens])
        
        st.info(f"🍞 Carbo: {total_c}g | 🥩 Prot: {total_p}g | 🥑 Gord: {total_g}g")
        
        if st.button("💾 REGISTRAR ALIMENTAÇÃO"):
            agora = datetime.now(fuso_br)
            detalhe = f"{', '.join(itens)} [C:{total_c}g P:{total_p}g G:{total_g}g]"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), refeicao, detalhe, total_c, total_p, total_g]], 
                                 columns=["Data", "Categoria", "Conteudo", "Carbo", "Prot", "Gord"])
            df_n_atual = carregar_dados(ARQUIVO_NUTRI)
            pd.concat([df_n_atual, novo_n], ignore_index=True).to_csv(ARQUIVO_NUTRI, index=False)
            st.success("Refeição registrada!")
            st.rerun()

    with col_n2:
        df_n = carregar_dados(ARQUIVO_NUTRI)
        if not df_n.empty:
            sum_c = df_n['Carbo'].sum()
            sum_p = df_n['Prot'].sum()
            sum_g = df_n['Gord'].sum()
            fig_pie = px.pie(values=[sum_c, sum_p, sum_g], names=['Carboidratos', 'Proteínas', 'Gorduras'], 
                            title="Total Nutricional Acumulado", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

# --- EXCEL 2 ABAS ---
st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO MÉDICO (EXCEL)"):
    df_g = carregar_dados(ARQUIVO_GLIC)
    df_n = carregar_dados(ARQUIVO_NUTRI)
    
    if not df_g.empty:
        # Tabela Glicemia
        df_g['Exibe'] = df_g['Valor'].astype(str) + " (" + df_g['Hora'] + ")"
        rel_g = df_g.pivot_table(index='Data', columns='Categoria', values='Exibe', aggfunc='last').reset_index()
        
        # Tabela Alimentação
        rel_n = pd.DataFrame()
        if not df_n.empty:
            rel_n = df_n.pivot_table(index='Data', columns='Categoria', values='Conteudo', aggfunc='last').reset_index()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            rel_g.to_excel(writer, index=False, sheet_name='Glicemia')
            if not rel_n.empty:
                rel_n.to_excel(writer, index=False, sheet_name='Alimentacao')
        
        st.download_button("Clique aqui para baixar o arquivo", output.getvalue(), file_name="Relatorio_Medico_Completo.xlsx")

if st.sidebar.button("🗑️ Reset Geral (Limpar Erros)"):
    if os.path.exists(ARQUIVO_GLIC): os.remove(ARQUIVO_GLIC)
    if os.path.exists(ARQUIVO_NUTRI): os.remove(ARQUIVO_NUTRI)
    st.rerun()
