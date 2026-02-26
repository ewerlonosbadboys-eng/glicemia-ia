import streamlit as st
import pandas as pd
from datetime import datetime
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
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE BANCO E DADOS =================
def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)')
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
    conn.commit()
    conn.close()

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    try:
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()
    except: return pd.DataFrame()

init_db()

# ================= LISTA DE NUTRIÇÃO AMPLIADA =================
ALIMENTOS = {
    "Pão Francês (1un)": [28, 4, 1], "Pão de Forma (2 fat)": [24, 4, 2], "Tapioca (50g)": [27, 0, 0],
    "Arroz Branco (1 escum)": [25, 2, 0],
