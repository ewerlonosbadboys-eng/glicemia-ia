import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import pytz

# 1. Configuracoes Iniciais
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v29", layout="wide")

ARQ_G = "dados_glicemia_v29.csv"
ARQ_N = "dados_nutricao_v29.csv"

# Banco de Alimentos: [Carbo, Prot, Gord, Calorias]
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

st.title("Monitoramento Saude Kids v29")

aba1, aba2 = st.tabs(["Glicemia", "Alimentacao Detalhada"])

with aba1:
    c1, c2 = st.columns(2)
    with c1:
        v_g = st.number_input("Valor da Glicemia:", min_value=0)
        m_g = st.selectbox("Momento:", ["Antes Cafe", "Apos Cafe", "Antes Almoco", "Apos Almoco", "Antes Merenda", "Antes Janta", "Apos Janta", "Madrugada"])
        if st.button("Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_g, m_g]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    
    dfg = carregar(ARQ_G)
    if not dfg.empty:
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot =
