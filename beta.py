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

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .main-card { background-color: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ================= LÓGICA DE NAVEGAÇÃO =================
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.email = ""
    st.session_state.nome = ""

# --- TELA DE LOGIN / CADASTRO (TELA INTEIRA) ---
if not st.session_state.logado:
    st.title("🩺 Saúde Kids - Acesso")
    
    aba_login, aba_cad = st.tabs(["Fazer Login", "Criar Nova Conta"])
    
    with aba_login:
        with st.form("login_form"):
            u_email = st.text_input("E-mail")
            u_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
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
                    st.error("Usuário ou senha incorretos.")

    with aba_cad:
        with st.form("cad_form"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome")
            s = c2.text_input("Sobrenome")
            t = st.text_input("Telefone")
            e = st.text_input("E-mail para login")
            p = st.text_input("Crie uma Senha", type="password")
            if st.form_submit_button("Cadastrar"):
                try:
                    conn = conectar_db()
                    c = conn.cursor()
                    c.execute("INSERT INTO usuarios (nome, sobrenome, telefone, email, senha) VALUES (?,?,?,?,?)", (n,s,t,e,p))
                    conn.commit()
                    conn.close()
                    st.success("Conta criada! Vá para a aba Login.")
                except:
                    st.error("Este e-mail já está em uso.")

else:
    # ================= APLICATIVO APÓS LOGIN =================
    st.sidebar.title(f"Olá, {st.session_state.nome}!")
    if st.sidebar.button("Sair do Sistema"):
        st.session_state.logado = False
        st.rerun()

    # --- Funções Internas ---
    def carregar_glicemia():
        conn = conectar_db()
        df = pd.read_sql(f"SELECT data, hora, valor, momento, dose FROM glicemia WHERE email_user = '{st.session_state.email}'", conn)
        conn.close()
        return df

    def carregar_receita():
        conn = conectar_db()
        c = conn.cursor()
        c.execute("SELECT * FROM receita WHERE email_user = ?", (st.session_state.email,))
        res = c.fetchone()
        conn.close()
        return res

    # --- Interface do App ---
    t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

    with t1:
        st.subheader("📝 Novo Registro de Glicemia")
        v = st.number_input("Valor (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        
        # Cálculo de Dose (Puxando do Banco)
        receita = carregar_receita()
        if receita:
            # Lógica de cálculo simplificada baseada na receita do banco
            prefixo = (1, 2, 3) if "Antes" in m or "Após" in m and "Janta" not in m else (4, 5, 6)
            if v < 70: dose_sug = "0 UI"
            elif v <= 200: dose_sug = f"{receita[prefixo[0]]} UI"
            elif v <= 400: dose_sug = f"{receita[prefixo[1]]} UI"
            else: dose_sug = f"{receita[prefixo[2]]} UI"
        else:
            dose_sug = "Configurar Receita"

        st.markdown(f'<div class="dose-alerta"><h1>{dose_sug}</h1></div>', unsafe_allow_html=True)

        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            conn = conectar_db()
            c = conn.cursor()
            c.execute("INSERT INTO glicemia (email_user, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                      (st.session_state.email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose_sug))
            conn.commit()
            conn.close()
            st.success("Salvo!")
            st.rerun()

    with t3:
        st.subheader("⚙️ Minha Receita Médica")
        r = carregar_receita()
        v_r = r if r else (st.session_state.email, 0, 0, 0, 0, 0, 0)
        
        col_dia, col_noite = st.columns(2)
        with col_dia:
            st.info("☀️ Tabela Dia")
            m1 = st.number_input("70-200:", value=int(v_r[1]), key="m1")
            m2 = st.number_input("201-400:", value=int(v_r[2]), key="m2")
            m3 = st.number_input("> 400:", value=int(v_r[3]), key="m3")
        with col_noite:
            st.info("🌙 Tabela Noite")
            n1 = st.number_input("70-200:", value=int(v_r[4]), key="n1")
            n2 = st.number_input("201-400:", value=int(v_r[5]), key="n2")
            n3 = st.number_input("> 400:", value=int(v_r[6]), key="n3")
            
        if st.button("💾 Atualizar Receita"):
            conn = conectar_db()
            c = conn.cursor()
            c.execute("REPLACE INTO receita VALUES (?,?,?,?,?,?,?)", (st.session_state.email, m1, m2, m3, n1, n2, n3))
            conn.commit()
            conn.close()
            st.success("Receita atualizada!")
            st.rerun()
