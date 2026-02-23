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

# Inicialização das variáveis de sessão para evitar erros de atributo
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ARQUIVOS DE DADOS
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÕES DE SEGURANÇA E BANCO =================

def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
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
    except: return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

# Funções para filtrar dados por perfil de usuário
def carregar_dados_perfil(arq, colunas):
    if os.path.exists(arq):
        df = pd.read_csv(arq)
        if 'user_email' in df.columns:
            return df[df['user_email'] == st.session_state.user_email]
    return pd.DataFrame(columns=colunas + ['user_email'])

def salvar_dados_perfil(df_novo, arq):
    if os.path.exists(arq):
        df_geral = pd.read_csv(arq)
        # Mantém dados de outros usuários e atualiza apenas o do atual
        df_outros = df_geral[df_geral['user_email'] != st.session_state.user_email]
        df_final = pd.concat([df_outros, df_novo], ignore_index=True)
    else:
        df_final = df_novo
    df_final.to_csv(arq, index=False)

init_db()

# ================= SISTEMA DE LOGIN (TELA INICIAL) =================

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])

    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        st.subheader("Cadastro")
        nome_c = st.text_input("Nome")
        email_c = st.text_input("E-mail", key="c_email")
        senha_c = st.text_input("Senha", type="password", key="c_senha")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (nome_c, email_c, senha_c))
                conn.commit()
                conn.close()
                st.success("Conta criada! Vá em 'Entrar'.")
            except: st.error("Erro ou e-mail já existe.")

    with abas_login[2]:
        st.subheader("Recuperar Senha")
        e_rec = st.text_input("E-mail", key="r_email")
        if st.button("Enviar Nova Senha"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT email FROM users WHERE email=?", (e_rec,))
            if c.fetchone():
                pw = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (pw, e_rec))
                conn.commit()
                if enviar_senha_nova(e_rec, pw): st.success("Senha enviada!")
                else: st.error("Erro ao enviar e-mail.")
            else: st.error("E-mail não cadastrado.")
            conn.close()

    with abas_login[3]:
        st.subheader("Trocar Senha")
        ae = st.text_input("E-mail", key="a_email")
        aa = st.text_input("Senha Antiga", type="password")
        an = st.text_input("Nova Senha", type="password")
        if st.button("Confirmar Troca"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("UPDATE users SET senha=? WHERE email=? AND senha=?", (an, ae, aa))
            if conn.total_changes > 0:
                conn.commit()
                st.success("Senha alterada!")
            else: st.error("Dados incorretos.")
            conn.close()
    st.stop()

# ================= ÁREA DO APLICATIVO (LOGADO) =================

st.sidebar.title(f"Saúde Kids")
st.sidebar.write(f"Perfil: **{st.session_state.user_email}**")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.session_state.user_email = ""
    st.rerun()

# Voltei com as suas abas originais (t1 a t4)
t1, t2, t3, t4 = st.tabs(["📊 Glicemia", "🍲 Alimentação", "💉 Insulina/Receita", "📈 Relatórios"])

# ABA 1: GLICEMIA (Filtrada por Perfil)
with t1:
    st.header("Controle de Glicemia")
    df_g = carregar_dados_perfil(ARQ_G, ['Data', 'Hora', 'Valor', 'Momento'])
    
    with st.expander("Novo Registro"):
        col1, col2, col3, col4 = st.columns(4)
        data = col1.date_input("Data", datetime.now(fuso_br))
        hora = col2.time_input("Hora", datetime.now(fuso_br))
        valor = col3.number_input("Valor (mg/dL)", 20, 600, 100)
        momento = col4.selectbox("Momento", ["Jejum", "Pré-Almoço", "Pós-Almoço", "Pré-Jantar", "Pós-Jantar", "Madrugada", "Outro"])
        
        if st.button("Salvar Glicemia"):
            novo_d = pd.DataFrame([[data.strftime('%d/%m/%Y'), hora.strftime('%H:%M'), valor, momento, st.session_state.user_email]], 
                                columns=['Data', 'Hora', 'Valor', 'Momento', 'user_email'])
            df_g = pd.concat([df_g, novo_d], ignore_index=True)
            salvar_dados_perfil(df_g, ARQ_G)
            st.success("Salvo!")
            st.rerun()

    if not df_g.empty:
        fig = px.line(df_g, x='Data', y='Valor', color='Momento', title="Minha Evolução Glicêmica", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_g.drop(columns=['user_email']), use_container_width=True)

# ABA 2: ALIMENTAÇÃO (Filtrada por Perfil)
with t2:
    st.header("Diário Alimentar")
    df_n = carregar_dados_perfil(ARQ_N, ['Data', 'Refeição', 'Descrição', 'Carbo(g)'])
    
    with st.expander("Registrar Refeição"):
        c1, c2, c3 = st.columns([1,2,1])
        refeicao = c1.selectbox("Refeição", ["Café", "Lanche M", "Almoço", "Lanche T", "Jantar", "Ceia"])
        desc = c2.text_input("O que comeu?")
        carb = c3.number_input("Carbos (g)", min_value=0)
        
        if st.button("Salvar Refeição"):
            novo_n = pd.DataFrame([[datetime.now(fuso_br).strftime('%d/%m/%Y'), refeicao, desc, carb, st.session_state.user_email]], 
                                 columns=['Data', 'Refeição', 'Descrição', 'Carbo(g)', 'user_email'])
            df_n = pd.concat([df_n, novo_n], ignore_index=True)
            salvar_dados_perfil(df_n, ARQ_N)
            st.rerun()
    st.dataframe(df_n.drop(columns=['user_email']), use_container_width=True)

# ABA 3: INSULINA (Configuração do Perfil)
with t3:
    st.header("Configuração de Insulina")
    df_r = carregar_dados_perfil(ARQ_R, ['Relacao', 'Sensibilidade', 'Meta'])
    
    if df_r.empty:
        st.warning("Configure seus fatores.")
        rel = st.number_input("Relação Carbo", value=15)
        sens = st.number_input("Fator Sensibilidade", value=50)
        meta = st.number_input("Meta Glicêmica", value=100)
        if st.button("Salvar Configuração"):
            df_r = pd.DataFrame([[rel, sens, meta, st.session_state.user_email]], columns=['Relacao', 'Sensibilidade', 'Meta', 'user_email'])
            salvar_dados_perfil(df_r, ARQ_R)
            st.rerun()
    else:
        st.info(f"Seus Fatores: 1U/{df_r['Relacao'].iloc[0]}g | Sensibilidade: {df_r['Sensibilidade'].iloc[0]} | Meta: {df_r['Meta'].iloc[0]}")
        if st.button("Resetar Fatores"):
            # Apenas remove os fatores deste usuário
            df_r = pd.DataFrame(columns=['Relacao', 'Sensibilidade', 'Meta', 'user_email'])
            salvar_dados_perfil(df_r, ARQ_R)
            st.rerun()

# ABA 4: RELATÓRIOS (Gera Excel apenas com os dados do usuário logado)
with t4:
    st.header("Relatório Individual")
    
    def gerar_excel_perfil():
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_g.drop(columns=['user_email']).to_excel(writer, index=False, sheet_name='Glicemia')
            df_n.drop(columns=['user_email']).to_excel(writer, index=False, sheet_name='Alimentação')
        return output.getvalue()

    if st.button("📥 BAIXAR MEU RELATÓRIO EXCEL"):
        dados_ex = gerar_excel_perfil()
        st.download_button("Clique aqui para baixar", dados_ex, f"relatorio_{st.session_state.user_email}.xlsx")
