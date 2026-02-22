import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz
from io import BytesIO

# 1. Configurações Iniciais e Fuso Horário
fuso = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v48 PRO", layout="wide")

# Nome do arquivo e Categorias do Relatório (Ordem das Colunas no Excel)
ARQ = "glicemia_v48.csv"
COL_MOMENTOS = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

def carregar():
    if os.path.exists(ARQ): 
        return pd.read_csv(ARQ)
    return pd.DataFrame(columns=["Data", "Hora", "Valor", "Momento"])

def cor_estilo(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF99; color: black' # Amarelo (Hipo)
        if n > 180: return 'background-color: #FFCCCC; color: black' # Vermelho (Hiper)
        return 'background-color: #CCFFCC; color: black' # Verde (Normal)
    except: return ""

st.title("🩸 Monitoramento Saude Kids v48 PRO")

t1, t2 = st.tabs(["📝 Novo Registro", "📥 Relatório Médico (Excel)"])

# ABA 1: REGISTRO DE DADOS
with t1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Registrar Glicemia")
        v = st.number_input("Valor (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", COL_MOMENTOS)
        if st.button("💾 Salvar Registro"):
            ag = datetime.now(fuso)
            nv = pd.DataFrame([[ag.strftime("%d/%m/%Y"), ag.strftime("%H:%M"), v, m]], 
                                columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(), nv], ignore
