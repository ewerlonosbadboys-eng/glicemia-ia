import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz

# 1. Configuração Inicial
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids - Sistema Completo", page_icon="🩸", layout="wide")

# Usando caderno V8 para evitar conflitos das fotos anteriores
ARQUIVO_GLIC = "dados_glicemia_v8.csv"
ARQUIVO_NUTRI = "dados_nutricao_v8.csv"

# Banco de Alimentos
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz (3 colheres)": [15, 1.5, 0],
    "Feijão (1 concha)": [14, 5, 0.5],
    "Frango Grelhado": [0, 23, 5],
    "Ovo Cozido": [1, 6, 5],
    "Banana (1 un)": [22, 1, 0],
    "Maçã (1 un)": [15, 0, 0]
}

def carregar_dados(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def aplicar_cores(val):
    if val == "-" or pd.isna(val): return ""
    try:
        num = int(str(val).split(" ")[0])
        if num <= 140: return 'background-color: #90EE90; color: black' # Verde
        elif num <= 180: return 'background-color: #FFFFE0; color: black' # Amarelo
        else: return 'background-color: #FFB6C1; color: black' # Vermelho
    except:
        return ""

st.title("🩸 Monitoramento Integrado (Glicemia + Nutrição)")

# --- CRIAÇÃO DAS ABAS ---
tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

# --- ABA 1: GLICEMIA ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        v_glic = st.number_input("Valor da Glicemia:", min_value=0)
        momento = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_glic, momento]], columns=["Data", "Hora", "Valor", "Categoria"])
            pd.concat([carregar_dados(ARQUIVO_GLIC), novo], ignore_index=True).to_csv(ARQUIVO_GLIC, index=False)
            st.success("Salvo!")
            st.rerun()
    with
