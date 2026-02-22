import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import pytz

# Configurações de Fuso e Arquivos
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v32", layout="wide")

ARQ_G = "dados_glicemia_v32.csv"
ARQ_N = "dados_nutricao_v32.csv"

# Banco de Alimentos: [Carbo, Prot, Gord, Kcal]
ALIMENTOS = {
    "Pao Frances": [28, 4, 1, 135], 
    "Leite (200ml)": [10, 6, 6, 120], 
    "Arroz (colher)": [5, 1, 0, 25], 
    "Feijao (colher)": [5, 2, 0, 30], 
    "Frango (file)": [0, 23, 5, 160], 
    "Ovo": [1, 6, 5, 80],
    "Banana": [22, 1, 0, 90], 
    "Maca": [15, 0, 0, 60], 
    "Iogurte": [15, 5, 3, 110], 
    "Bolacha (un)": [8, 1, 2, 50]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF00; color: black'
        if n > 180: return 'background-color: #FF0000; color: white'
        if n > 140: return 'background-color: #FFFF00; color: black'
        return 'background-color: #00FF00; color: black'
    except: return ""

st.title("Monitoramento Saude Kids v32")

# --- SEÇÃO 1: GLICEMIA ---
st.header("1. Registro de Glicemia")
col1, col2 = st.columns(2)
with col1:
    v_g = st.number_input("Valor da Glicemia:", min_value=0, key="glic")
    m_g = st.selectbox("Momento:", ["Antes Cafe", "Apos Cafe", "Antes Almoco", "Apos Almoco", "Antes Merenda", "Antes Janta", "Apos Janta", "Madrugada"], key="mom")
    if st.button("Salvar Glicemia"):
        agora = datetime.now(fuso_br)
        novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_g, m_g]], columns=["Data", "Hora", "Valor", "Momento"])
        pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
        st.rerun()

dfg = carregar(ARQ_G)
if not dfg.empty:
    dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
    pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
    st.dataframe(pivot.style.applymap(cor_glicemia), use_container_width=True)

st.markdown("---")

# --- SEÇÃO 2: ALIMENTAÇÃO ---
st.header("2. O que ela comeu hoje?")
c_a, c_b = st.columns([1, 2])
with c_a:
    ref = st.selectbox("Refeicao:", ["Cafe da Manha", "Lanche Manha", "Almoco", "Merenda", "Janta", "Lanche Noite"], key="ref_box")
    escolha = st.multiselect("Itens:", list(ALIMENTOS.keys()), key="itens_sel")
    
    c_t = sum([ALIMENTOS[i][0] for i in escolha])
    p_t = sum([ALIMENTOS[i][1] for i in escolha])
    g_t = sum([ALIMENTOS[i][2] for i in escolha])
    
    if st.button("Salvar Alimentacao"):
        if escolha:
            agora = datetime.now(fuso_br)
            itens_txt = ", ".join(escolha)
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), ref, itens_txt, c_t, p_t, g_t]], columns=["Data", "Refeicao", "Itens", "Carbo", "Prot", "Gord"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()

dfn = carregar(ARQ_N)
if not dfn.empty:
    st.write("📋 **Resumo: Alimentos e Nutrientes (C, P, G)**")
    df_exibir = dfn.copy()
    # Formatação que você pediu: Alimentos em cima e Macros embaixo
    df_exibir["Detalhes"] = df_exibir["Itens"] + " | Carbo:" + df_exibir["Carbo"].astype(str) + "g Prot:" + df_exibir["Prot"].astype(str) + "g Gord:" + df_exibir["Gord"].astype(str) + "g"
    resumo = df_exibir.pivot_table
