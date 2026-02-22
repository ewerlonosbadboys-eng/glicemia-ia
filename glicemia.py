import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from openpyxl.styles import PatternFill

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸", layout="wide")
st.title("🩸 Diário de Glicemia com Alertas Coloridos")

# --- FUNÇÃO PARA SALVAR ---
def salvar_leitura(valor, categoria):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    mes_ano = agora.strftime("%m/%Y")
    nova_linha = pd.DataFrame([[data, valor, categoria, mes_ano]], 
                             columns=["Data", "Valor", "Categoria", "Mes_Ano"])
    arquivo = "historico_glicemia.csv"
    if not os.path.isfile(arquivo):
        nova_linha.to_csv(arquivo, index=False)
    else:
        nova_linha.to_csv(arquivo, mode='a', header=False, index=False)
    st.success(f"✅ Salvo: {valor} mg/dL")

# --- INTERFACE ---
categorias_ordem = [
    "Medida antes do café", "Medida após o café",
    "Medida antes do almoço", "Medida após o almoço",
    "Medida antes da merenda", "Medida antes da janta",
    "Medida após a janta", "Medida madrugada", "Medida Extra"
]

col1, col2 = st.columns(2)
with col1:
    valor_manual = st.number_input("Valor:", min_value=0, max_value=600, step=1)
    cat_sel = st.selectbox("Momento:", categorias_ordem)

with col2:
