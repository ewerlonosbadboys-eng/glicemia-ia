import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Diário Glicemia Kids", page_icon="🩸")
st.title("🩸 Diário Glicemia Categorizado")

# --- FUNÇÃO PARA SALVAR DADOS ---
def salvar_leitura(valor, categoria):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")
    mes_ano = agora.strftime("%m/%Y")
    
    nova_linha = pd.DataFrame([[data, hora, valor, categoria, mes_ano]], 
                             columns=["Data", "Hora", "Valor (mg/dL)", "Categoria", "Mês/Ano"])
    
    arquivo = "historico_glicemia.csv"
    if not os.path.isfile(arquivo):
        nova_linha.to_csv(arquivo, index=False)
    else:
        nova_linha.to_csv(arquivo, mode='a', header=False, index=False)
    st.success(f"✅ Salvo: {valor} mg/dL em '{categoria}'")

# --- ENTRADA DE DADOS ---
valor_final = 0
col1, col2 = st.columns([1, 1])

with col1:
    valor_manual = st.number_input("Digite o valor:", min_value=0, max_value=600, step=1)
    if valor_manual > 0:
        valor_final = valor_manual

with col2:
    categorias = [
        "Medida antes do café", "Medida após o café",
        "Medida antes do almoço", "Medida após o almoço",
        "Medida antes da merenda", "Medida antes da janta",
        "Medida após a janta", "Medida madrugada", "Medida Extra"
