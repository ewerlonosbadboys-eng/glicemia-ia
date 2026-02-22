import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import pytz

# 1. Config
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v36", layout="wide")

ARQ_G = "dados_glicemia_v36.csv"
ARQ_N = "dados_nutricao_v36.csv"

# Banco de Dados Nutricional
ALIMENTOS = {
    "Pao Frances": [28, 4, 1], 
    "Leite (200ml)": [10, 6, 6], 
    "Arroz (colher)": [5, 1, 0], 
    "Feijao (colher)": [5, 2, 0], 
    "Frango (file)": [0, 23, 5], 
    "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], 
    "Maca": [15, 0, 0], 
    "Iogurte": [15, 5, 3], 
    "Bolacha (un)": [8, 1, 2]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glic(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: yellow; color: black'
        if n > 180: return 'background-color: red; color: white'
        return 'background-color: green; color: white'
    except: return ""

st.title("Sistema Saude Kids v36")

aba1, aba2 = st.tabs(["Glicemia", "Alimentacao"])

with aba1:
    col1, col2 = st.columns([1, 2])
    with col1:
        v_g = st.number_input("Valor:", min_value
