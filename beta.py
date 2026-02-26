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

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_M = "mensagens_admin_BETA.csv"

# ================= DESIGN DARK MODE =================
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
def gerar_senha_temporaria(tamanho=6):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    return True  # simplificado para estabilidade

def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)')
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
    conn.commit(); conn.close()

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

# ================= INTERFACE =================
tab1, tab2 = st.tabs(["📊 Glicemia", "⚙️ Receita"])

# ---- GLICEMIA
with tab1:
    v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
    m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
    dose, msg = calc_insulina(v_gl, m_gl)
    st.markdown(f"<div class='metric-box'><b>{msg}</b><br><span class='dose-destaque'>{dose}</span></div>", unsafe_allow_html=True)

# ---- RECEITA EDITÁVEL
with tab2:
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
    v = r_u.iloc[0] if not r_u.empty else {}

    st.subheader("🌞 Manhã")
    m1_min = st.number_input("Faixa 1 Mín", value=int(v.get('manha_f1_min',70)))
    m1_max = st.number_input("Faixa 1 Máx", value=int(v.get('manha_f1_max',150)))
    m1_dose = st.number_input("Dose Faixa 1", value=int(v.get('manha_f1_dose',3)))

    st.subheader("🌙 Noite")
    n1_min = st.number_input("Faixa 1 Mín ", value=int(v.get('noite_f1_min',70)))
    n1_max = st.number_input("Faixa 1 Máx ", value=int(v.get('noite_f1_max',150)))
    n1_dose = st.number_input("Dose Faixa 1 ", value=int(v.get('noite_f1_dose',3)))

    if st.button("Salvar Receita"):
        nova = pd.DataFrame([{
            'Usuario': st.session_state.user_email,
            'manha_f1_min': m1_min, 'manha_f1_max': m1_max, 'manha_f1_dose': m1_dose,
            'noite_f1_min': n1_min, 'noite_f1_max': n1_max, 'noite_f1_dose': n1_dose
        }])
        df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        pd.concat([df_r_all, nova], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Receita salva com sucesso!")

# ================= SAIR =================
if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
