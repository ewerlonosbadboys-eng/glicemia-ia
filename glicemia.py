import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl import Workbook
from openpyxl.styles import PatternFill

# 1. Configurações
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids - v17", page_icon="🩸", layout="wide")

ARQ_G = "dados_glicemia_v17.csv"
ARQ_N = "dados_nutricao_v17.csv"

# Banco de Alimentos Atualizado: [Carbo, Prot, Gord, CALORIAS]
ALIMENTOS = {
    "Pão Francês": [28, 4, 1, 135], 
    "Leite (200ml)": [10, 6, 6, 120],
    "Arroz (colher)": [5, 1, 0, 25], 
    "Feijão (colher)": [5, 2, 0, 30],
    "Frango (filé)": [0, 23, 5, 160], 
    "Ovo": [1, 6, 5, 80],
    "Banana": [22, 1, 0, 90], 
    "Maçã": [15, 0, 0, 60],
    "Iogurte": [15, 5, 3, 110]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFFE0; color: black'
        elif n > 180: return 'background-color: #FFB6C1; color: black'
        elif n > 140: return 'background-color: #FFFFE0; color: black'
        else: return 'background-color: #90EE90; color: black'
    except: return ""

st.title("🩸 Sistema v17 - Agora com Total de Calorias")

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo!")
            st.rerun()
    with c2:
        dfg = carregar(ARQ_G)
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor', title="Evolução", markers=True))
    if not dfg.empty:
