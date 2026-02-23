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

def get_connection():
    return sqlite3.connect('saude_kids_final.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receita (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')
    
    # Reparo automático de colunas para evitar o DatabaseError
    c.execute("PRAGMA table_info(nutricao)")
    existentes = [col[1] for col in c.fetchall()]
    if 'user_email' not in existentes: c.execute("ALTER TABLE nutricao ADD COLUMN user_email TEXT")
    if 'c' not in existentes: c.execute("ALTER TABLE nutricao ADD COLUMN c REAL DEFAULT 0")
    conn.commit()
    conn.close()

init_db()

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2563eb; color: white; }
    .card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .metric-box { text-align: center; padding: 15px; border-radius: 10px; background: #eff6ff; border: 1px solid #dbeafe; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE APOIO =================
ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0], "Maçã": [15, 0, 0]}

def calcular_insulina_automatica(valor, momento):
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
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= FUNÇÕES DE SEGURANÇA =================
def gerar_senha_temporaria(tamanho=6):
    return ''.join(random.choice(string.ascii_letters + string.digits) for i in range(tamanho))

def enviar_email_recuperacao(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    msg = MIMEText(f"Sua nova senha Saúde Kids: {senha_nova}")
    msg['Subject'] = 'Recuperação de Senha'
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
    aba1, aba2, aba3, aba4 = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci", "🔄 Alterar"])
    with aba1:
        u = st.text_input("E-mail", key="l_e")
        s = st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar"):
            conn = get_connection()
            res = conn.execute("SELECT email FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            conn.close()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else: st.error("Erro no login")
    with aba2:
        n_c = st.text_input("Nome", key="c_n")
        e_c = st.text_input("E-mail Novo", key="c_e")
        s_c = st.text_input("Senha Nova", type="password", key="c_s")
        if st.button("Cadastrar"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_c, e_c, s_c))
                conn.commit()
                conn.close()
                st.success("Conta criada!")
            except: st.error("E-mail em uso.")
    with aba3:
        e_r = st.text_input("E-mail para recuperar", key="r_e")
        if st.button("Recuperar"):
            nova = gerar_senha_temporaria()
            if enviar_email_recuperacao(e_r, nova):
                conn = get_connection()
                conn.execute("UPDATE users SET senha=? WHERE email=?", (nova, e_r))
                conn.commit()
                conn.close()
                st.success("Senha enviada!")
    with aba4:
        u_a = st.text_input("E-mail atual", key="a_e")
        s_a = st.text_input("Senha antiga", type="password", key="a_s")
        s_n = st.text_input("Senha nova", type="password", key="a_n")
        if st.button("Trocar"):
            conn = get_connection()
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u_a, s_a)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_n, u_a))
                conn.commit()
                st.success("Senha alterada!")
            conn.close()
    st.stop()

# ================= CORES COM PRIORIDADE =================
def cor_glicemia(valor):
    if valor < 70: return 'background-color: #fee2e2' # Vermelho (Hipo)
    if 70 <= valor <= 180: return 'background-color: #f0fdf4' # Verde (Alvo)
    return 'background-color: #fefce8' # Amarelo (Hiper)

# ================= DEFINIÇÃO DAS ABAS =================
st.sidebar.info(f"Usuário: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    conn = get_connection()
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    v = st.number_input("Valor:", 0, 600, 100)
    m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
    ds, rt = calcular_insulina_automatica(v, m)
    st.metric("Sugestão de Dose", ds, rt)
    if st.button("💾 Salvar Registro"):
        conn = get_connection()
        conn.execute("INSERT INTO glicemia (user_email, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)", (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), datetime.now(fuso_br).strftime("%H:%M"), v, m, ds))
        conn.commit()
        conn.close()
        st.rerun()
    if not dfg.empty:
        st.dataframe(dfg.style.applymap(lambda x: cor_glicemia(x) if isinstance(x, int) else '', subset=['Valor']), use_container_width=True)

with t2:
    sel = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
    carb = sum([ALIMENTOS[i][0] for i in sel])
    if st.button("💾 Salvar Refeição"):
        conn = get_connection()
        conn.execute("INSERT INTO nutricao (user_email, data, info, c) VALUES (?,?,?,?)", (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), ", ".join(sel), carb))
        conn.commit()
        conn.close()
        st.rerun()
    conn = get_connection()
    dfn = pd.read_sql_query("SELECT data as Data, info as Alimentos, c as Carbo FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    st.dataframe(dfn, use_container_width=True)

with t3:
    conn = get_connection()
    r = conn.execute("SELECT * FROM receita WHERE user_email=?", (st.session_state.user_email,)).fetchone()
    conn.close()
    if not r: r = [st.session_state.user_email, 1, 2, 3, 1, 2, 3]
    col1, col2 = st.columns(2)
    with col1:
        st.write("MANHÃ")
        m1 = st.number_input("Até 200", value=float(r[1]), key="m1")
        m2 = st.number_input("201-400", value=float(r[2]), key="m2")
        m3 = st.number_input("Acima 400", value=float(r[3]), key="m3")
    with col2:
        st.write("NOITE")
        n1 = st.number_input("Até 200 ", value=float(r[4]), key="n1")
        n2 = st.number_input("201-400 ", value=float(r[5]), key="n2")
        n3 = st.number_input("Acima 400 ", value=float(r[6]), key="n3")
    if st.button("💾 Salvar Tabela"):
        conn = get_connection()
        conn.execute("INSERT OR REPLACE INTO receita VALUES (?,?,?,?,?,?,?)", (st.session_state.user_email, m1, m2, m3, n1, n2, n3))
        conn.commit()
        conn.close()

# ================= EXCEL COLORIDO =================
def exportar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Glicemia')
    return output.getvalue()

if st.button("📥 Baixar Relatório"):
    st.download_button("Clique para baixar", exportar_excel(dfg), "Relatorio.xlsx")
