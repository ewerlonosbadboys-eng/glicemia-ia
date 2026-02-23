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

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR SQL (TODAS AS TABELAS) =================
def get_connection():
    return sqlite3.connect('saude_kids_master.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Criar tabelas com a estrutura correta
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL, p REAL, g REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')
    
    # --- AUTO-CORREÇÃO DE COLUNAS (Evita o DatabaseError) ---
    for tabela in ['glicemia', 'nutricao']:
        c.execute(f"PRAGMA table_info({tabela})")
        colunas = [col[1] for col in c.fetchall()]
        if 'user_email' not in colunas:
            c.execute(f"ALTER TABLE {tabela} ADD COLUMN user_email TEXT DEFAULT ''")
    
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
    msg['Subject'] = 'Acesso Saúde Kids'
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
    aba1, aba2, aba3, aba4 = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with aba1:
        u = st.text_input("E-mail", key="l_u")
        s = st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE email=? AND senha=?", (u, s))
            res = c.fetchone()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")
            conn.close()

    with aba2:
        n_c = st.text_input("Nome")
        e_c = st.text_input("E-mail Novo")
        s_c = st.text_input("Senha Nova", type="password")
        if st.button("Cadastrar"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_c, e_c, s_c))
                conn.commit()
                st.success("Cadastro realizado!")
                conn.close()
            except: st.error("Erro no cadastro.")

    with aba3:
        e_res = st.text_input("E-mail para recuperação")
        if st.button("Enviar E-mail"):
            nova = gerar_senha_temporaria()
            if enviar_senha_nova(e_res, nova):
                conn = get_connection()
                conn.execute("UPDATE users SET senha=? WHERE email=?", (nova, e_res))
                conn.commit()
                st.success("Verifique seu e-mail!")
                conn.close()

    with aba4:
        # Espaço para lógica de alteração de senha
        st.info("Funcionalidade em manutenção")
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

# ================= DEFINIÇÃO DAS ABAS =================
st.sidebar.write(f"Usuário: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    # Lógica de Glicemia com SQL
    conn = get_connection()
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    st.subheader("Registros de Glicemia")
    st.dataframe(dfg.tail(10).style.applymap(cor_glicemia, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🍽️ Alimentação")
    escolha = st.multiselect("Selecione os alimentos:", list(ALIMENTOS.keys()))
    if st.button("Salvar Alimentação"):
        agora = datetime.now(fuso_br).strftime("%d/%m/%Y")
        resumo = ", ".join(escolha)
        conn = get_connection()
        conn.execute("INSERT INTO nutricao (user_email, data, info, c, p, g) VALUES (?,?,?,?,?,?)", (st.session_state.user_email, agora, resumo, 0, 0, 0))
        conn.commit()
        conn.close()
        st.rerun()
    
    conn = get_connection()
    dfn = pd.read_sql_query("SELECT data as Data, info as Info FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    st.dataframe(dfn, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Receita")
    # Lógica de salvamento de receita aqui
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO =================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic.to_excel(writer, sheet_name='Glicemia', index=False)
            ws = writer.sheets['Glicemia']
            # Aplicar PatternFill aqui...
        if not df_nutri.empty:
            df_nutri.to_excel(writer, sheet_name='Alimentacao', index=False)
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR EXCEL"):
    conn = get_connection()
    dfg_f = pd.read_sql_query("SELECT * FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    dfn_f = pd.read_sql_query("SELECT * FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    st.download_button("Download", gerar_excel_colorido(dfg_f, dfn_f), "Relatorio.xlsx")
