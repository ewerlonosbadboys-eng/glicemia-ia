import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz

# 1. Configuracoes e Arquivos
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v26", layout="wide")

ARQ_G = "dados_glicemia_v26.csv"
ARQ_N = "dados_nutricao_v26.csv"

# Banco de Alimentos
ALIMENTOS = {
    "Pao Frances": 135, "Leite (200ml)": 120, "Arroz (colher)": 25, 
    "Feijao (colher)": 30, "Frango (file)": 160, "Ovo": 80,
    "Banana": 90, "Maca": 60, "Iogurte": 110, "Bolacha (un)": 50
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

st.title("Monitoramento Saude Kids v26")

aba1, aba2 =
