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
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')

    # Reparo de colunas (Evita o DatabaseError se o arquivo .db for antigo)
    c.execute("PRAGMA table_info(nutricao)")
    existentes = [col[1] for col in c.fetchall()]
    if 'user_email' not in existentes:
        c.execute("ALTER TABLE nutricao ADD COLUMN user_email TEXT")
    if 'c' not in existentes:
        c.execute("ALTER TABLE nutricao ADD COLUMN c REAL DEFAULT 0")
    
    conn.commit()
    conn.close()

init_db()

# ================= FUNÇÕES DE SEGURANÇA =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    msg = MIMEText(f"<h3>Saúde Kids</h3><p>Sua nova senha é: <b>{senha_nova}</b></p>", 'html')
    msg['Subject'] = 'Acesso Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except: return False

# ================= SISTEMA DE LOGIN (RESTURADO) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Login")
    aba1, aba2, aba3, aba4 = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with aba1:
        u_log = st.text_input("E-mail", key="log_email")
        s_log = st.text_input("Senha", type="password", key="log_pass")
        if st.button("Acessar"):
            conn = get_connection()
            res = conn.execute("SELECT email FROM users WHERE email=? AND senha=?", (u_log, s_log)).fetchone()
            conn.close()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else: st.error("Dados incorretos.")

    with aba2:
        n_cad = st.text_input("Nome", key="c_n")
        e_cad = st.text_input("E-mail Novo", key="c_e")
        s_cad = st.text_input("Senha Nova", type="password", key="c_s")
        if st.button("Cadastrar"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit()
                conn.close()
                st.success("Cadastrado! Faça login.")
            except: st.error("E-mail já existe.")

    with aba3:
        e_res = st.text_input("E-mail cadastrado para recuperar", key="res_e")
        if st.button("Recuperar Senha"):
            nova = gerar_senha_temporaria()
            if enviar_senha_nova(e_res, nova):
                conn = get_connection()
                conn.execute("UPDATE users SET senha=? WHERE email=?", (nova, e_res))
                conn.commit()
                conn.close()
                st.success("Nova senha enviada para seu e-mail!")
            else: st.error("Erro ao enviar e-mail.")

    with aba4:
        u_alt = st.text_input("Confirme seu E-mail", key="alt_e")
        s_ant = st.text_input("Senha Atual", type="password", key="alt_s_ant")
        s_nov = st.text_input("Nova Senha", type="password", key="alt_s_nov")
        if st.button("Trocar Senha"):
            conn = get_connection()
            check = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u_alt, s_ant)).fetchone()
            if check:
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nov, u_alt))
                conn.commit()
                st.success("Senha atualizada!")
            else: st.error("Dados atuais incorretos.")
            conn.close()
    st.stop()

# ================= ÁREA LOGADA =================
st.sidebar.info(f"Usuário: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0], "Maçã": [15, 0, 0]}

def calcular_insulina(valor, momento):
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT * FROM receita WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    if df_r.empty: return "Configurar Receita", "⚠️"
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if valor < 70: return "0 UI", "Hipoglicemia"
    elif valor <= 200: dose = r[f'{prefixo}_f1']
    elif valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo}"

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    conn = get_connection()
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    v_in = st.number_input("Glicemia:", 0, 600, 100)
    m_in = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
    ds, rt = calcular_
