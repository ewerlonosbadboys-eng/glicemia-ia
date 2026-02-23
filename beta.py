import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill
import sqlite3
import smtplib
from email.mime.text import MIMEText
import random
import string

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR SQL ÚNICO E REPARADOR =================
def get_connection():
    return sqlite3.connect('saude_kids_final.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Tabelas Base
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')

    # 2. Migração de Emergência (Garante que as colunas existam)
    def fix_table(tabela, colunas_necessarias):
        c.execute(f"PRAGMA table_info({tabela})")
        existentes = [col[1] for col in c.fetchall()]
        for col, tipo in colunas_necessarias.items():
            if col not in existentes:
                c.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")

    fix_table('nutricao', {'user_email': 'TEXT', 'info': 'TEXT', 'c': 'REAL'})
    fix_table('glicemia', {'user_email': 'TEXT', 'dose': 'TEXT'})
    
    conn.commit()
    conn.close()

init_db()

# ================= ESTILO E APOIO =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; }
</style>
""", unsafe_allow_html=True)

ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina(valor, momento):
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT * FROM receita WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    if df_r.empty: return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia!"
    elif valor <= 200: dose = r[f'{prefixo}_f1']
    elif valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= LOGIN =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci", "🔄 Alterar"])
    
    with abas[0]:
        u = st.text_input("E-mail", key="l_em")
        s = st.text_input("Senha", type="password", key="l_ps")
        if st.button("Acessar"):
            conn = get_connection()
            res = conn.execute("SELECT email FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            conn.close()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else: st.error("Dados incorretos.")
    
    with abas[1]:
        n = st.text_input("Nome")
        e = st.text_input("E-mail Novo")
        p = st.text_input("Senha Nova", type="password")
        if st.button("Cadastrar"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n, e, p))
                conn.commit()
                conn.close()
                st.success("Conta criada!")
            except: st.error("E-mail já existe.")
    st.stop()

# ================= APP PRINCIPAL =================
st.sidebar.info(f"Usuário: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    conn = get_connection()
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Glicemia:", 0, 600, 100)
        m =
