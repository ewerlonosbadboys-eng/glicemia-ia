import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill
import sqlite3
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
    # Centralizando em um único arquivo de banco de dados
    return sqlite3.connect('saude_kids_final.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Criando tabelas se não existirem
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')

    # Reparo de colunas para evitar o DatabaseError
    c.execute("PRAGMA table_info(nutricao)")
    existentes = [col[1] for col in c.fetchall()]
    if 'user_email' not in existentes:
        c.execute("ALTER TABLE nutricao ADD COLUMN user_email TEXT")
    if 'c' not in existentes:
        c.execute("ALTER TABLE nutricao ADD COLUMN c REAL DEFAULT 0")

    conn.commit()
    conn.close()

init_db()

# ================= FUNÇÕES DE APOIO =================
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
    if df_r.empty: 
        return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    
    if valor < 70: 
        return "0 UI", "⚠️ Hipoglicemia!"
    elif valor <= 200: 
        dose = r[f'{prefixo}_f1']
    elif valor <= 400: 
        dose = r[f'{prefixo}_f2']
    else: 
        dose = r[f'{prefixo}_f3']
        
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= SISTEMA DE LOGIN =================
# LINHA 82 CORRIGIDA:
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Login")
    aba1, aba2 = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
    
    with aba1:
        u_log = st.text_input("E-mail", key="log_email")
        s_log = st
