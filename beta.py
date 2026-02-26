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
    .alerta-zap { background-color: #25D366; color: white !important; font-weight: bold; border-radius: 10px; padding: 10px; text-align: center; display: block; text-decoration: none; margin: 10px 0; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE SISTEMA (BACKUP E DADOS) =================
def realizar_backup():
    if not os.path.exists(PASTA_BACKUP): os.makedirs(PASTA_BACKUP)
    hoje = datetime.now(fuso_br).strftime("%Y-%m-%d")
    for arq in [ARQ_G, ARQ_N, ARQ_R, ARQ_M, "usuarios.db"]:
        if os.path.exists(arq): shutil.copy(arq, os.path.join(PASTA_BACKUP, f"{hoje}_{arq}"))

if 'ultimo_backup' not in st.session_state:
    if datetime.now(fuso_br).hour >= 3:
        realizar_backup()
        st.session_state.ultimo_backup = True

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    try:
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()
    except: return pd.DataFrame()

# ================= BANCO DE DADOS E LOGIN =================
def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)')
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
    conn.commit(); conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    # ... (Código de login permanece o mesmo do seu Beta anterior)
    u = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        conn = sqlite3.connect('usuarios.db')
        if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
            st.session_state.logado = True
            st.session_state.user_email = u
            st.rerun()
    st.stop()

# ================= DICIONÁRIO DE ALIMENTOS AMPLIADO =================
ALIMENTOS = {
    "Pão Francês (1un)": [28, 4, 1], "Pão de Forma (2 fat)": [24, 4, 2], "Tapioca (50g)": [27, 0, 0],
    "Arroz Branco (escum)": [25, 2, 0], "Feijão (concha)": [14, 5, 1], "Macarrão (pegador)": [30, 5, 1],
    "Frango Grelhado (100g)": [0, 31, 4], "Carne Moída (100g)": [0, 25, 15], "Ovo Cozido (1un)": [1, 6, 5],
    "Banana (1un)": [22, 1, 0], "Maçã (1un)": [15, 0, 0], "Leite Integral (200ml)": [10, 6, 6],
    "Iogurte Natural": [9, 7, 6], "Bolacha Salgada (3un)": [15, 2, 4], "Cuscuz (1 pires)": [25, 2, 1]
}

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

# ================= INTERFACE PRINCIPAL =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel Administrativo")
    t1, t2, t3 = st.tabs(["👥 Usuários", "📈 Sugestões", "💾 Backups"])
    with t2:
        if os.path.exists(ARQ_M): 
            st.dataframe(pd.read_csv(ARQ_M), use_container_width=True)
        else: st.info("Nenhuma sugestão enviada.")
    # ... (código admin restante)

else:
    tabs = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita", "📩 Sugerir"])

    with tabs[0]: # GLICEMIA
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfg = carregar_dados
