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

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# ARQUIVOS DE DADOS (CSV)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÃO DE ENVIO DE E-MAIL =================
def enviar_link_recuperacao(email_destino):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" # Senha de App do Google
    
    link_app = "https://glicemia-ia.streamlit.app" 
    email_codificado = urllib.parse.quote(email_destino)
    link_final = f"{link_app}/?reset=true&email={email_codificado}"
    
    corpo = f"""
    <h3>Recuperação de Senha - Saúde Kids</h3>
    <p>Clique no link abaixo para cadastrar uma nova senha:</p>
    <a href='{link_final}'>Redefinir minha senha agora</a>
    """
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Link de Redefinição - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

# ================= SENSOR DE LINK DE RECUPERAÇÃO =================
query_params = st.query_params
if "reset" in query_params and "email" in query_params:
    st.session_state.reset_mode = True
    st.session_state.email_reset = query_params["email"]

if st.session_state.get("reset_mode"):
    st.title("🔐 Nova Senha")
    st.info(f"Redefinindo para: {st.session_state.email_reset}")
    nova_s = st.text_input("Digite a nova senha", type="password")
    confirmar_s = st.text_input("Confirme a nova senha", type="password")
    
    if st.button("Salvar Nova Senha"):
        if nova_s == confirmar_s and len(nova_s) >= 4:
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("UPDATE users SET senha=? WHERE email=?", (nova_s, st.session_state.email_reset))
            conn.commit()
            conn.close()
            st.success("Pronto! Senha alterada. Faça login normalmente.")
            st.session_state.reset_mode = False
            st.query_params.clear()
            st.rerun()
        else:
            st.error("As senhas não coincidem ou são muito curtas.")
    st.stop()

# ================= BANCO DE DADOS DE USUÁRIOS =================
def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ================= SISTEMA DE LOGIN E ABAS =================
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'conta_criada' not in st.session_state:
    st.session_state.conta_criada = False

if not st.session_state.logado:
    st.markdown("""<style>.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }</style>""", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    titulos = ["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"]
    if st.session_state.conta_criada:
        titulos = ["🔐 Entrar", "❓ Esqueci Senha"]

    abas_login = st.tabs(titulos)

    with abas_login[0]: # LOGIN
        u = st.text_input("E-mail", key="l_user")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Sistema"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
            conn.close()

    if not st.session_state.conta_criada:
        with abas_login[1]: # CADASTRO
            nome = st.text_input("Nome")
            email_cad = st.text_input("E-mail")
            senha_cad = st.text_input("Senha", type="password")
            if st.button("Finalizar Cadastro"):
                try:
                    conn = sqlite3.connect('usuarios.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (nome, email_cad, senha_cad))
                    conn.commit()
                    conn.close()
                    st.session_state.conta_criada = True
                    st.success("Conta criada! Vá para a aba Entrar.")
                    st.rerun()
                except:
                    st.error("Este e-mail já está cadastrado.")
        
        with abas_login[2]: # ESQUECI SENHA
            email_rec = st.text_input("E-mail cadastrado", key="rec_em")
            if st.button("Enviar Link"):
                if enviar_link_recuperacao(email_rec):
                    st.success("Link enviado! Verifique seu e-mail.")
                else:
                    st.error("Erro ao enviar e-mail.")
    else:
        with abas_login[1]: # ESQUECI SENHA (QUANDO LOGADO)
            email_rec = st.text_input("E-mail cadastrado", key="rec_em_2")
            if st.button("Enviar Link de Recuperação"):
                if enviar_link_recuperacao(email_rec):
                    st.success("Link enviado!")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ================= ÁREA DO APLICATIVO (LOGADO) =================
st.title("🧪 Saúde Kids - Painel de Controle")

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# Suas abas de Glicemia, Alimentação e Receita entram aqui
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.subheader("Controle de Glicemia")
    # ... (seu código de registros de glicemia aqui) ...

with t2:
    st.subheader("Controle de Alimentação")
    # ... (seu código de nutrientes aqui) ...

with t3:
    st.subheader("Doses e Receitas")
    # ... (seu código de configuração de doses aqui) ...

# Botão de Logout no final
if st.sidebar.button("Sair / Logoff"):
    st.session_state.logado = False
    st.rerun()
