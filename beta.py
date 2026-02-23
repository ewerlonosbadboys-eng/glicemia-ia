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
# (Mantido exatamente como solicitado)
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR SQL (Ajustado para Isolamento Real) =================

def get_connection():
    return sqlite3.connect('saude_kids_master.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    # Adicionada coluna user_email em todas as tabelas de dados
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
# (Mantido sem alterações)
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE APOIO =================
# (Mantido sem alterações na lógica original)
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina_automatica(valor, momento):
    conn = get_connection()
    # BUSCA SOMENTE A RECEITA DO USUÁRIO LOGADO
    df_r = pd.read_sql_query("SELECT * FROM receita WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    
    if df_r.empty:
        return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia!"
    elif 70 <= valor <= 200: dose = r[f'{prefixo}_f1']
    elif 201 <= valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= FUNÇÕES DE SEGURANÇA =================
# (Mantido sem alterações)
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

# ================= SISTEMA DE LOGIN =================
# (Mantido sem alterações)
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Login")
    aba_l, aba_c = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
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
    st.stop()

# ================= CORES COM PRIORIDADE =================
# (Mantido sem alterações)
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
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    conn = get_connection()
    # FILTRO POR USUÁRIO NA LEITURA
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()

    with c1:
        st.subheader("📝 Novo Registro")
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        dose_sug, ref_tab = calcular_insulina_automatica(v, m)
        st.markdown(f'<div class="dose-alerta"><h1>{dose_sug}</h1><small>{ref_tab}</small></div>', unsafe_allow_html=True)

        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            conn = get_connection()
            c = conn.cursor()
            # SALVAMENTO COM O E-MAIL DO USUÁRIO
            c.execute("INSERT INTO glicemia (user_email, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                     (st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose_sug))
            conn.commit()
            conn.close()
            st.rerun()

    with c2:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            fig = px.line(dfg.tail(10), x='DataHora', y='Valor', markers=True, title="Evolução Recente")
            st.plotly_chart(fig, use_container_width=True)

    if not dfg.empty:
        st.subheader("📋 Histórico")
        st.dataframe(dfg.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    conn = get_connection()
    # FILTRO POR USUÁRIO NA ALIMENTAÇÃO
    dfn = pd.read_sql_query("SELECT data as Data, info as Info, c as C, p as P, g as G FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()

    escolha = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
    carb = sum([ALIMENTOS[i][0] for i in escolha])
    if st.button("💾 Salvar Alimentação"):
        agora = datetime.now(fuso_br)
        txt = f"{', '.join(escolha)} (Carbo: {carb}g)"
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO nutricao (user_email, data, info, c, p, g) VALUES (?,?,?,?,?,?)",
                 (st.session_state.user_email, agora.strftime("%d/%m/%Y"), txt, carb, 0, 0))
        conn.commit()
        conn.close()
        st.rerun()
    st.dataframe(dfn, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM receita WHERE user_email=?", (st.session_state.user_email,))
    v_at = c.fetchone()
    conn.close()
    
    if v_at is None: v_at = [None, 0, 0, 0, 0, 0, 0]
    
    col1, col2 = st.columns(2)
    with col1:
        mf1 = st.number_input("Manhã Dose 1", value=int(v_at[1]))
        mf2 = st.number_input("Manhã Dose 2", value=int(v_at[2]))
        mf3 = st.number_input("Manhã Dose 3", value=int(v_at[3]))
    with col2:
        nf1 = st.number_input("Noite Dose 1", value=int(v_at[4]))
        nf2 = st.number_input("Noite Dose 2", value=int(v_at[5]))
        nf3 = st.number_input("Noite Dose 3", value=int(v_at[6]))

    if st.button("💾 Salvar Receita"):
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO receita VALUES (?,?,?,?,?,?,?)",
                 (st.session_state.user_email, mf1, mf2, mf3, nf1, nf2, nf3))
        conn.commit()
        conn.close()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO (Filtro Aplicado) =================
# (A lógica interna de cores foi mantida conforme o seu código)
