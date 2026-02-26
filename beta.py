import streamlit as st
import pandas as pd
from datetime import datetime, time
import os
import shutil
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
import sqlite3
import smtplib
from email.mime.text import MIMEText
import random
import string
import urllib.parse

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_M = "mensagens_admin_BETA.csv"
PASTA_BACKUP = "backups_saude_kids"

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    .alerta-zap { background-color: #25D366; color: white !important; font-weight: bold; border-radius: 10px; padding: 10px; text-align: center; display: block; text-decoration: none; margin-top: 10px; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ================= SISTEMA DE BACKUP AUTOMÁTICO (3H) =================
def realizar_backup():
    if not os.path.exists(PASTA_BACKUP): os.makedirs(PASTA_BACKUP)
    hoje = datetime.now(fuso_br).strftime("%Y-%m-%d")
    for arq in [ARQ_G, ARQ_N, ARQ_R, ARQ_M, "usuarios.db"]:
        if os.path.exists(arq):
            shutil.copy(arq, os.path.join(PASTA_BACKUP, f"{hoje}_{arq}"))

if 'ultimo_backup' not in st.session_state:
    if datetime.now(fuso_br).hour >= 3:
        realizar_backup()
        st.session_state.ultimo_backup = True

# ================= FUNÇÕES DE APOIO E DADOS =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    try:
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()
    except: return pd.DataFrame()

def init_db():
