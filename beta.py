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
import urllib.parse
import random
import string

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# Nomes dos arquivos originais para migração/apoio
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR SQL (ISOLAMENTO POR USUÁRIO) =================

def get_connection():
    return sqlite3.connect('saude_kids_master.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL, p REAL, g REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')
    conn.commit()
    conn.close()

init_db()

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE APOIO =================
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina_automatica(valor, momento):
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT * FROM receita WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    if df_r.empty: return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia!"
    elif 70 <= valor <= 200: dose = r[f'{prefixo}_f1']
    elif 201 <= valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= FUNÇÕES DE SEGURANÇA =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    msg = MIMEText(f"<h3>Saúde Kids</h3><p>Sua nova senha é: <b>{senha_nova}</b></p>", 'html')
    msg['Subject'] = 'Nova Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except: return False

# ================= SISTEMA DE LOGIN =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Login")
    aba_l, aba_c, aba_r = st.tabs(["🔐 Entrar", "📝 Criar Conta", "🔄 Resetar Senha"])
    
    with aba_l:
        u = st.text_input("E-mail")
        s = st.text_input("Senha", type="password")
        if st.button("Acessar"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE email=? AND senha=?", (u, s))
            res = c.fetchone()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else: st.error("Dados incorretos.")
            conn.close()

    with aba_c:
        n_c = st.text_input("Nome")
        e_c = st.text_input("E-mail de Cadastro")
        s_c = st.text_input("Crie uma Senha", type="password")
        if st.button("Cadastrar"):
            try:
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_c, e_c, s_c))
                conn.commit()
                st.success("Conta criada!")
                conn.close()
            except: st.error("E-mail já existe.")

    with aba_r:
        e_reset = st.text_input("E-mail para recuperar")
        if st.button("Enviar Nova Senha"):
            nova = gerar_senha_temporaria()
            if enviar_senha_nova(e_reset, nova):
                conn = get_connection()
                c = conn.cursor()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, e_reset))
                conn.commit()
                st.success("Senha enviada para seu e-mail!")
                conn.close()
            else: st.error("Erro ao enviar e-mail.")
    st.stop()

# ================= CORES COM PRIORIDADE =================
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFFE0; color: black'
        elif n > 180: return 'background-color: #FFB6C1; color: black'
        elif n > 140: return 'background-color: #FFFFE0; color: black'
        else: return 'background-color: #90EE90; color: black'
    except: return ""

# ================= DEFINIÇÃO DAS ABAS (CÂMERA REMOVIDA) =================
st.sidebar.write(f"Usuário: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    conn = get_connection()
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()

    with c1:
        st.subheader("📝 Novo Registro")
        v = st.number_input("Valor:", min_value=0, value=100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        ds, rt = calcular_insulina_automatica(v, m)
        st.markdown(f'<div class="dose-alerta"><h1>{ds}</h1><small>{rt}</small></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO glicemia (user_email, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                     (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), datetime.now(fuso_br).strftime("%H:%M"), v, m, ds))
            conn.commit()
            conn.close()
            st.rerun()

    with c2:
        if not dfg.empty:
            fig = px.line(dfg.tail(10), x='Data', y='Valor', markers=True, title="Evolução Recente")
            st.plotly_chart(fig, use_container_width=True)
    
    if not dfg.empty:
        st.subheader("📋 Histórico")
        st.dataframe(dfg.tail(10).style.applymap(cor_glicemia, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO =================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic.to_excel(writer, sheet_name='Glicemia', index=False)
            ws = writer.sheets['Glicemia']
            # Lógica de preenchimento de cores do PatternFill original aqui...
        if not df_nutri.empty:
            df_nutri.to_excel(writer, sheet_name='Alimentacao', index=False)
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO EXCEL"):
    conn = get_connection()
    dfg_f = pd.read_sql_query("SELECT * FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    dfn_f = pd.read_sql_query("SELECT * FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    excel_data = gerar_excel_colorido(dfg_f, dfn_f)
    st.download_button("Baixar Arquivo", excel_data, f"Relatorio_{st.session_state.user_email}.xlsx")
