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
import pytz # Biblioteca para fuso horário

# --- CONFIGURAÇÃO DE FUSO HORÁRIO BRASIL ---
fuso_br = pytz.timezone('America/Sao_Paulo')

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸", layout="wide")
st.title("🩸 Monitoramento (Horário de Brasília)")

ARQUIVO = "historico_glicemia.csv"

# Função para salvar com a hora certa do Brasil
def salvar_leitura(valor, categoria):
    # Pega a hora exata de Brasília
    agora_br = datetime.now(fuso_br) 
    data = agora_br.strftime("%d/%m/%Y")
    hora = agora_br.strftime("%H:%M")
    mes_ano = agora_br.strftime("%m/%Y")
    
    df = carregar_dados()
    nova = pd.DataFrame([[data, hora, valor, categoria, mes_ano]], 
                       columns=["Data", "Hora", "Valor", "Categoria", "Mes_Ano"])
    df = pd.concat([df, nova], ignore_index=True)
    df.to_csv(ARQUIVO, index=False)
    st.success(f"✅ Salvo às {hora}: {valor} mg/dL")

# ... (restante do código de carregamento e interface
