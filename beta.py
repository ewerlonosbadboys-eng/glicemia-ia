import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
import sqlite3
import smtplib
from email.mime.text import MIMEText
import random
import string
import zipfile
import shutil
from pathlib import Path

# ================= CONFIGURAÇÕES =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_M = "mensagens_admin_BETA.csv"

# ================= BACKUP =================
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_STATE_FILE = BACKUP_DIR / "last_auto_backup.txt"

ARQUIVOS_BACKUP = [
    "usuarios.db",
    ARQ_G,
    ARQ_N,
    ARQ_R,
    ARQ_M,
]

def agora_br():
    return datetime.now(fuso_br)

def criar_backup_zip():
    ts = agora_br().strftime("%Y-%m-%d_%H-%M-%S")
    nome = f"backup_saude_kids_{ts}.zip"
    caminho = BACKUP_DIR / nome

    with zipfile.ZipFile(caminho, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for arq in ARQUIVOS_BACKUP:
            if os.path.exists(arq):
                z.write(arq)

    return caminho

def restaurar_backup_zip(zip_file):
    tmp_dir = BACKUP_DIR / "_tmp_restore"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file, "r") as z:
        z.extractall(tmp_dir)

    for arq in ARQUIVOS_BACKUP:
        src = tmp_dir / arq
        if src.exists():
            shutil.copy(src, arq)

    shutil.rmtree(tmp_dir)

def backup_automatico():
    agora = agora_br()
    hoje = agora.strftime("%Y-%m-%d")

    if agora.hour >= 3:
        if BACKUP_STATE_FILE.exists():
            ultima_data = BACKUP_STATE_FILE.read_text().strip()
        else:
            ultima_data = ""

        if ultima_data != hoje:
            criar_backup_zip()
            BACKUP_STATE_FILE.write_text(hoje)

backup_automatico()

# ================= DESIGN =================
st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #ffffff; }
.card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
.metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
.dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
label, p, span, h1, h2, h3 { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ================= LOGIN =================
def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)')
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
    conn.commit()
    conn.close()

init_db()

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    u = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        conn = sqlite3.connect('usuarios.db')
        if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
            st.session_state.logado = True
            st.session_state.user_email = u
            st.rerun()
        else:
            st.error("Login inválido")
        conn.close()
    st.stop()

# ================= FUNÇÕES =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq):
        return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty:
        return "0 UI", "Configurar Receita"

    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"

    try:
        if rec[f'{periodo}_f1_min'] <= v <= rec[f'{periodo}_f1_max']:
            return f"{int(rec[f'{periodo}_f1_dose'])} UI", "Faixa 1"
        elif rec[f'{periodo}_f2_min'] <= v <= rec[f'{periodo}_f2_max']:
            return f"{int(rec[f'{periodo}_f2_dose'])} UI", "Faixa 2"
        elif rec[f'{periodo}_f3_min'] <= v <= rec[f'{periodo}_f3_max']:
            return f"{int(rec[f'{periodo}_f3_dose'])} UI", "Faixa 3"
        else:
            return "0 UI", "Fora da faixa"
    except:
        return "0 UI", "Erro"

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

# ================= ADMIN =================
if st.session_state.user_email == "admin":

    st.title("🛡️ Painel Admin")

    tab_admin1, tab_admin2 = st.tabs(["👥 Gestão", "💾 Backup & Restore"])

    with tab_admin1:
        conn = sqlite3.connect('usuarios.db')
        df_users = pd.read_sql_query("SELECT nome, email FROM users", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True)

    with tab_admin2:
        st.subheader("Backup Manual")
        if st.button("📥 Criar Backup Agora"):
            caminho = criar_backup_zip()
            with open(caminho, "rb") as f:
                st.download_button("Baixar Backup", f.read(), file_name=caminho.name)

        st.markdown("---")
        st.subheader("Restaurar Backup")
        arquivo_zip = st.file_uploader("Enviar arquivo .zip de backup", type=["zip"])
        if arquivo_zip:
            restaurar_backup_zip(arquivo_zip)
            st.success("Backup restaurado com sucesso! Reinicie o app.")

# ================= SAIR =================
if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
