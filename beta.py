import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids - v0.1 Original", page_icon="🩺", layout="centered")

# ================= BANCO DE DADOS =================
def conectar_db():
    return sqlite3.connect('saude_kids.db', check_same_thread=False)

def criar_tabelas():
    conn = conectar_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, sobrenome TEXT, 
                  telefone TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email_user TEXT, data TEXT, 
                  hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (email_user TEXT PRIMARY KEY, manha_f1 INTEGER, manha_f2 INTEGER, manha_f3 INTEGER,
                  noite_f1 INTEGER, noite_f2 INTEGER, noite_f3 INTEGER)''')
    conn.commit()
    conn.close()

criar_tabelas()

# ================= ESTILO VISUAL (CORRIGINDO LETRAS INVISÍVEIS) =================
st.markdown("""
<style>
    /* Fundo principal */
    .stApp { background-color: #f8fafc; }
    
    /* Cor de texto para labels de formulários para garantir visibilidade */
    label, p, span, .stMarkdown { color: #1e293b !important; font-weight: 500; }
    
    /* Estilização dos Cards */
    .main-card { background-color: white; padding: 30px; border-radius: 15px; border: 1px solid #e2e8f0; }
    
    /* Alerta de Dose */
    .dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; color: #166534 !important; }
</style>
""", unsafe_allow_html=True)

# ================= LÓGICA DE SESSÃO =================
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.email = ""
    st.session_state.nome = ""

# --- TELA DE ACESSO (INTEIRA) ---
if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center; color: #0f172a;'>🩺 Saúde Kids</h1>", unsafe_allow_html=True)
    
    # Traduzindo as Tabs
    aba_login, aba_cad = st.tabs(["Fazer Login", "Criar Nova Conta"])
    
    with aba_login:
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        with st.form("login_form"):
            u_email = st.text_input("Seu E-mail")
            u_senha = st.text_input("Sua Senha", type="password")
            if st.form_submit_button("Entrar no Sistema"):
                conn = conectar_db()
                c = conn.cursor()
                c.execute("SELECT nome FROM usuarios WHERE email = ? AND senha = ?", (u_email, u_senha))
                user = c.fetchone()
                conn.close()
                if user:
                    st.session_state.logado = True
                    st.session_state.email = u_email
                    st.session_state.nome = user[0]
                    st.rerun()
                else:
                    st.error("Dados incorretos. Verifique seu e-mail e senha.")
        st.markdown('</div>', unsafe_allow_html=True)

    with aba_cad:
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        with st.form("cad_form"):
            col1, col2 = st.columns(2)
            n = col1.text_input("Primeiro Nome")
            s = col2.text_input("Sobrenome")
            t = st.text_input("WhatsApp / Telefone")
            e = st.text_input("E-mail (Será seu Login)")
            p = st.text_input("Crie uma Senha Forte", type="password")
            if st.form_submit_button("Finalizar Cadastro"):
                if n and e and p:
                    try:
                        conn = conectar_db()
                        c = conn.cursor()
                        c.execute("INSERT INTO usuarios (nome, sobrenome, telefone, email, senha) VALUES (?,?,?,?,?)", (n,s,t,e,p))
                        conn.commit()
                        conn.close()
                        st.success("Conta criada com sucesso! Agora clique em 'Fazer Login'.")
                    except:
                        st.error("Este e-mail já está sendo usado por outra pessoa.")
                else:
                    st.warning("Por favor, preencha o Nome, E-mail e Senha.")
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # ================= APLICATIVO LOGADO =================
    st.sidebar.markdown(f"### Bem-vindo, \n**{st.session_state.nome}**")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    # --- Funções de Dados ---
    def carregar_receita():
        conn = conectar_db()
        c = conn.cursor()
        c.execute("SELECT * FROM receita WHERE email_user = ?", (st.session_state.email,))
        res = c.fetchone()
        conn.close()
        return res

    # --- Menu Principal ---
    t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

    with t1:
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.subheader("📝 Registrar Glicemia")
        v = st.number_input("Valor medido (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento da Medição:", ["Antes do Café", "Após o Café", "Antes do Almoço", "Após o Almoço", "Antes do Lanche", "Antes da Janta", "Após a Janta", "Madrugada"])
        
        # Lógica da Receita
        receita = carregar_receita()
        if receita:
            # Índices: 1,2,3 (Dia) / 4,5,6 (Noite)
            dia = ["Antes do Café", "Após o Café", "Antes do Almoço", "Após o Almoço", "Antes do Lanche"]
            indices = (1, 2, 3) if m in dia else (4, 5, 6)
            
            if v < 70: dose = "0 UI"
            elif v <= 200: dose = f"{receita[indices[0]]} UI"
            elif v <= 400: dose = f"{receita[indices[1]]} UI"
            else: dose = f"{receita[indices[2]]} UI"
        else:
            dose = "Configurar Receita"

        st.markdown(f'<div class="dose-alerta"><h2>Dose Sugerida: {dose}</h2></div>', unsafe_allow_html=True)

        if st.button("💾 Salvar no Histórico"):
            agora = datetime.now(fuso_br)
            conn = conectar_db()
            c = conn.cursor()
            c.execute("INSERT INTO glicemia (email_user, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                      (st.session_state.email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose))
            conn.commit()
            conn.close()
            st.success("Glicemia registrada!")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.subheader("📋 Sua Receita Médica")
        r = carregar_receita()
        v_r = r if r else (st.session_state.email, 0, 0, 0, 0, 0, 0)
        
        c_dia, c_noite = st.columns(2)
        with c_dia:
            st.info("☀️ Tabela do Dia")
            m1 = st.number_input("Insulina (70-200):", value=int(v_r[1]), key="m1")
            m2 = st.number_input("Insulina (201-400):", value=int(v_r[2]), key="m2")
            m3 = st.number_input("Insulina (> 400):", value=int(v_r[3]), key="m3")
        with c_noite:
            st.info("🌙 Tabela da Noite")
            n1 = st.number_input("Insulina (70-200):", value=int(v_r[4]), key="n1")
            n2 = st.number_input("Insulina (201-400):", value=int(v_r[5]), key="n2")
            n3 = st.number_input("Insulina (> 400):", value=int(v_r[6]), key="n3")
