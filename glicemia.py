import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl import Workbook
from openpyxl.styles import PatternFill

# 1. Configurações Iniciais
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids v25", page_icon="🩸", layout="wide")

ARQ_G = "dados_glicemia_v25.csv"
ARQ_N = "dados_nutricao_v25.csv"

# Banco de Alimentos Simplificado
ALIMENTOS = {
    "Pão Francês": 135, "Leite (200ml)": 120, "Arroz (colher)": 25, 
    "Feijão (colher)": 30, "Frango (filé)": 160, "Ovo": 80,
    "Banana": 90, "Maçã": 60, "Iogurte": 110, "Bolacha (un)": 50
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF00; color: black'   # Amarelo para baixo (10, 20...)
        if n > 180: return 'background-color: #FF0000; color: white'  # Vermelho para alto
        if n > 140: return 'background-color: #FFFF00; color: black'  # Amarelo para atenção
        return 'background-color: #00FF00; color: black'             # Verde para normal
    except: return ""

st.title("🩸 Monitoramento Saúde Kids v25")

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação Detalhada", "📸 Câmera"])

# --- ABA GLICEMIA ---
with t1:
    c1, c2 = st.columns(2)
    with c1:
        v_g = st.number_input("Valor da Glicemia:", min_value=0, key="g_val")
        m_g = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_g, m_g]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    
    dfg = carregar(ARQ_G)
    if not dfg.empty:
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(pivot.style.applymap(cor_glicemia), use_container_width=True)

# --- ABA ALIMENTAÇÃO (O QUE VOCÊ PEDIU) ---
with t2:
    st.subheader("🍽️ Registro de Refeições")
    ca1, ca2 = st.columns([1, 2])
    with ca1:
        ref = st.selectbox("Refeição:", ["Café da Manhã", "Lanche Manhã", "Almoço", "Merenda", "Janta", "Lanche Noite"])
        escolha = st.multiselect("Itens consumidos:", list(ALIMENTOS.keys()))
        soma = sum([ALIMENTOS[i] for i in escolha])
        st.metric("Total de Calorias", f"{soma} kcal")
        
        if st.button("💾 Salvar Alimentos"):
            if escolha:
                agora = datetime.now(fuso_br)
                itens_txt = ", ".join(escolha)
                novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), ref, itens_txt, soma]], columns=["Data", "Refeicao", "Itens", "Kcal"])
                pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
                st.rerun()

    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.write("📋 **Resumo da Di
