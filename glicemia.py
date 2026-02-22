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
st.set_page_config(page_title="Saúde Kids v22", page_icon="🩸", layout="wide")

ARQ_G = "dados_glicemia_v22.csv"
ARQ_N = "dados_nutricao_v22.csv"

# Banco de Alimentos: [Carbo, Prot, Gord, CALORIAS]
ALIMENTOS = {
    "Pão Francês": [28, 4, 1, 135], "Leite (200ml)": [10, 6, 6, 120],
    "Arroz (colher)": [5, 1, 0, 25], "Feijão (colher)": [5, 2, 0, 30],
    "Frango (filé)": [0, 23, 5, 160], "Ovo": [1, 6, 5, 80],
    "Banana": [22, 1, 0, 90], "Maçã": [15, 0, 0, 60],
    "Iogurte": [15, 5, 3, 110], "Bolacha (un)": [8, 1, 2, 50]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF00; color: black'
        elif n > 180: return 'background-color: #FF0000; color: white'
        elif n > 140: return 'background-color: #FFFF00; color
