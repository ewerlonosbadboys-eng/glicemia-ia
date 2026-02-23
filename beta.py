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

# ARQUIVOS DE DADOS (CSV)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÕES DE SEGURANÇA =================

def gerar_senha_temporaria(tamanho=6):
    """Gera senha aleatória"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    """Envia e-mail direto"""
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    corpo = f"<h3>Saúde Kids</h3><p>Sua nova senha de acesso é: <b>{senha_nova}</b></p>"
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Sua Nova Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ================= SISTEMA DE LOGIN =================

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])

    with abas_login[0]:
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
                st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        st.subheader("Cadastro")
        nome = st.text_input("Nome")
        email_cad = st.text_input("E-mail")
        senha_cad = st.text_input("Senha", type="password")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (nome, email_cad, senha_cad))
                conn.commit()
                conn.close()
                st.success("Conta criada!")
            except:
                st.error("Erro ao cadastrar.")

    with abas_login[2]:
        st.subheader("Recuperar Acesso")
        email_alvo = st.text_input("Digite seu e-mail cadastrado", key="rec_em_direto")
        
        if st.button("Gerar e Enviar Nova Senha"):
            if email_alvo:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("SELECT email FROM users WHERE email=?", (email_alvo,))
                if c.fetchone():
                    # Correção da identação aqui:
                    senha_gerada = gerar_senha_temporaria()
                    c.execute("UPDATE users SET senha=? WHERE email=?", (senha_gerada, email_alvo))
                    conn.commit()
                    conn.close()
                    
                    if enviar_senha_nova(email_alvo, senha_gerada):
                        st.success(f"✅ Nova senha enviada para {email_alvo}!")
                    else:
                        st.error("Erro ao enviar e-mail.")
                else:
                    st.error("E-mail não encontrado.")
                    conn.close()
            else:
                st.warning("Informe o e-mail.")
    st.stop()

# ================= ÁREA DO APLICATIVO =================

# Funções de Carregamento
def carregar_dados(arq, colunas):
    if os.path.exists(arq):
        return pd.read_csv(arq)
    return pd.DataFrame(columns=colunas)

def salvar_dados(df, arq):
    df.to_csv(arq, index=False)

# Dashboards e Abas do App...
st.sidebar.title(f"Bem-vindo!")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3, t4 = st.tabs(["📊 Glicemia", "🍲 Alimentação", "💉 Insulina/Receita", "📈 Relatórios"])

# Aba 1: Glicemia
with t1:
    st.header("Controle de Glicemia")
    df_g = carregar_dados(ARQ_G, ['Data', 'Hora', 'Valor', 'Momento'])
    
    with st.expander("Novo Registro"):
        col1, col2, col3, col4 = st.columns(4)
        data = col1.date_input("Data", datetime.now(fuso_br))
        hora = col2.time_input("Hora", datetime.now(fuso_br))
        valor = col3.number_input("Valor (mg/dL)", min_value=20, max_value=600, value=100)
        momento = col4.selectbox("Momento", ["Jejum", "Pré-Almoço", "Pós-Almoço", "Pré-Jantar", "Pós-Jantar", "Madrugada", "Outro"])
        
        if st.button("Salvar Glicemia"):
            novo_d = pd.DataFrame([[data.strftime('%d/%m/%Y'), hora.strftime('%H:%M'), valor, momento]], 
                                columns=['Data', 'Hora', 'Valor', 'Momento'])
            df_g = pd.concat([df_g, novo_d], ignore_index=True)
            salvar_dados(df_g, ARQ_G)
            st.success("Salvo!")
            st.rerun()

    if not df_g.empty:
        fig = px.line(df_g, x='Data', y='Valor', color='Momento', title="Evolução Glicêmica", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_g.sort_index(ascending=False), use_container_width=True)

# Aba 2: Alimentação
with t2:
    st.header("Diário Alimentar")
    df_n = carregar_dados(ARQ_N, ['Data', 'Refeição', 'Descrição', 'Carbo(g)'])
    
    with st.expander("Registrar Refeição"):
        c1, c2, c3 = st.columns([1,2,1])
        refeicao = c1.selectbox("Refeição", ["Café", "Lanche M", "Almoço", "Lanche T", "Jantar", "Ceia"])
        desc = c2.text_input("O que comeu?")
        carb = c3.number_input("Carbos (g)", min_value=0)
        
        if st.button("Salvar Refeição"):
            novo_n = pd.DataFrame([[datetime.now(fuso_br).strftime('%d/%m/%Y'), refeicao, desc, carb]], 
                                 columns=['Data', 'Refeição', 'Descrição', 'Carbo(g)'])
            df_n = pd.concat([df_n, novo_n], ignore_index=True)
            salvar_dados(df_n, ARQ_N)
            st.rerun()
    
    st.dataframe(df_n, use_container_width=True)

# Aba 3: Receita/Cálculo
with t3:
    st.header("Configuração de Insulina")
    df_r = carregar_dados(ARQ_R, ['Relacao', 'Sensibilidade', 'Meta'])
    
    if df_r.empty:
        st.warning("Configure seus fatores primeiro.")
        rel = st.number_input("Relação Carbo (1U para X gramas)", value=15)
        sens = st.number_input("Fator de Sensibilidade", value=50)
        meta = st.number_input("Meta Glicêmica", value=100)
        if st.button("Salvar Configuração"):
            df_r = pd.DataFrame([[rel, sens, meta]], columns=['Relacao', 'Sensibilidade', 'Meta'])
            salvar_dados(df_r, ARQ_R)
            st.rerun()
    else:
        st.info(f"Fatores: 1U/{df_r['Relacao'][0]}g | Sensibilidade: {df_r['Sensibilidade'][0]} | Meta: {
