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

# --- FUNÇÃO ÚNICA DE E-MAIL ---
def enviar_link_recuperacao(email_destino):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" # Sua senha de 16 letras
    
    link_app = "https://glicemia-ia.streamlit.app" 
    email_codificado = urllib.parse.quote(email_destino)
    link_final = f"{link_app}/?reset=true&email={email_codificado}"
    
    corpo = f"<h3>Recuperação de Senha</h3><p>Clique no link para definir sua nova senha: <a href='{link_final}'>Redefinir Senha</a></p>"
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Redefinição de Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

# --- SENSOR DE LINK (REDEFINIÇÃO) ---
query_params = st.query_params
if "reset" in query_params and "email" in query_params:
    st.session_state.reset_mode = True
    st.session_state.email_reset = query_params["email"]

if st.session_state.get("reset_mode"):
    st.title("🔐 Criar Nova Senha")
    st.info(f"Redefinindo para: {st.session_state.email_reset}")
    nova_s = st.text_input("Nova Senha", type="password")
    if st.button("Confirmar Alteração"):
        conn = sqlite3.connect('usuarios.db')
        c = conn.cursor()
        c.execute("UPDATE users SET senha=? WHERE email=?", (nova_s, st.session_state.email_reset))
        conn.commit()
        conn.close()
        st.success("Senha atualizada! Agora faça o login.")
        st.session_state.reset_mode = False
        st.query_params.clear()
        st.rerun()
    st.stop()

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'conta_criada' not in st.session_state:
    st.session_state.conta_criada = False

if not st.session_state.logado:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    # Gerenciamento dinâmico de abas
    titulos_abas = ["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"]
    if st.session_state.conta_criada:
        titulos_abas = ["🔐 Entrar", "❓ Esqueci Senha"]
        st.success("Conta criada! Entre agora.")

    abas = st.tabs(titulos_abas)

    # Aba Login
    with abas[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
            conn.close()

    # Aba Criar Conta ou Esqueci Senha
    if not st.session_state.conta_criada:
        with abas[1]:
            n = st.text_input("Nome")
            em = st.text_input("E-mail para cadastro")
            se = st.text_input("Crie uma Senha", type="password")
            if st.button("Cadastrar"):
                try:
                    conn = sqlite3.connect('usuarios.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n, em, se))
                    conn.commit()
                    conn.close()
                    st.session_state.conta_criada = True
                    st.rerun()
                except:
                    st.error("E-mail já cadastrado.")
        
        with abas[2]: # Aba Esqueci Senha
            email_rec = st.text_input("E-mail cadastrado", key="rec_1")
            if st.button("Enviar Link de Recuperação", key="btn_rec_1"):
                if enviar_link_recuperacao(email_rec):
                    st.success("E-mail enviado!")
                else:
                    st.error("Erro ao enviar.")
    else:
        with abas[1]: # Esqueci Senha quando conta_criada é True
            email_rec = st.text_input("E-mail cadastrado", key="rec_2")
            if st.button("Enviar Link de Recuperação", key="btn_rec_2"):
                if enviar_link_recuperacao(email_rec):
                    st.success("E-mail enviado!")
                else:
                    st.error("Erro ao enviar.")
    st.stop()

# ================= SEÇÃO LOGADA (O RESTO DO SEU APP) =================
# ... (Aqui continua o seu código de Glicemia, Alimentação e Receita que você já tinha)
st.title("🧪 Painel Saúde Kids")
# (Coloque aqui o restante das suas abas t1, t2, t3 e funções de Excel)
