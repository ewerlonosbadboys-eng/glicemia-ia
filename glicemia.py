import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz

# 1. Configuração de Fuso Horário e Página
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids - Monitoramento Completo", page_icon="🩸", layout="wide")

# Usando caderno V6 para garantir que as cores funcionem sem erros de dados antigos
ARQUIVO_GLIC = "dados_glicemia_v6.csv"
ARQUIVO_NUTRI = "dados_nutricao_v6.csv"

# Banco de Alimentos
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz (3 colheres)": [15, 1.5, 0],
    "Feijão (1 concha)": [14, 5, 0.5],
    "Frango Grelhado": [0, 23, 5],
    "Ovo Cozido": [1, 6, 5],
    "Banana (1 un)": [22, 1, 0]
}

def carregar_dados(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# --- REGRAS DE CORES PARA A TABELA ---
def aplicar_cores(val):
    if val == "-" or pd.isna(val): return ""
    try:
        # Pega o primeiro número antes do parêntese
        num = int(str(val).split(" ")[0])
        if num <= 140: return 'background-color: #90EE90; color: black' # Verde
        elif num <= 180: return 'background-color: #FFFFE0; color: black' # Amarelo
        else: return 'background-color: #FFB6C1; color: black' # Vermelho (Alerta)
    except:
        return ""

st.title("🩸 Monitoramento com Alertas de Cores")

tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

# --- ABA 1: GLICEMIA ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        v_glic = st.number_input("Valor da Glicemia (mg/dL):", min_value=0)
