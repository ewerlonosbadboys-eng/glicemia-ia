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
    return pd.read_csv(arq) if os.path.isfile(arq) else pd.DataFrame()

# --- INTERFACE PRINCIPAL ---
st.title("🩸 Pain
