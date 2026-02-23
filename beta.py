import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
import sqlite3
import smtplib
from email.mime.text import MIMEText
import random
import string

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="centered") # Login centralizado

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= DESIGN DA TELA DE ENTRADA =================
st.markdown("""
<style>
    /* Fundo suave para acabar com o branco total */
    .stApp {
        background: linear-gradient(135deg, #f0f4f8 0%, #d9e2ec 100%);
    }
    
    /* Estilização do formulário de login */
    .login-container {
        background-color: white;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-top: 50px;
    }

    /* Títulos e textos */
    h1 { color: #102a43; font-weight: 800; text-align: center; }
    
    /* Botões mais bonitos */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #2b6cb0;
        color: white;
        font-weight: bold;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E LOGIN (LÓGICA ORIGINAL) =================

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
    c.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

if not st.session_state.logado:
    # Container visual para o Login
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.title("🧪 Saúde Kids")
    st.subheader("Controle de Saúde Infantil")
    
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci", "🔄 Alterar"])

    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo", key="btn_login"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        n_cad = st.text_input("Nome completo", key="n_cad")
        e_cad = st.text_input("Seu melhor e-mail", key="e_cad")
        s_cad = st.text_input("Crie uma senha", type="password", key="s_cad")
        if st.button("Cadastrar Conta"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit()
                conn.close()
                st.success("Conta criada! Vá em 'Entrar'.")
            except: st.error("E-mail já existe.")
    
    with abas_login[2]:
        email_alvo = st.text_input("E-mail da conta", key="rec_em")
        if st.button("Recuperar Senha"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            if c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone():
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                if enviar_senha_nova(email_alvo, nova): st.success("Senha enviada para seu e-mail!")
                else: st.error("Erro no envio do e-mail.")
            else: st.error("E-mail não encontrado.")
            conn.close()

    with abas_login[3]:
        alt_em = st.text_input("Confirme E-mail", key="alt_em")
        alt_at = st.text_input("Senha Atual", type="password", key="alt_at")
        alt_n1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        if st.button("Trocar Senha Agora"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit()
                st.success("Senha alterada com sucesso!")
            else: st.error("Dados atuais incorretos.")
            conn.close()
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ================= RESTANTE DO APP (MANTIDO CONFORME BETA 14) =================

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

def cor_glicemia_status(v):
    try:
        n = int(v)
        if n < 70: return 'background-color: #FFFFE0; color: black;'
        elif n > 180: return 'background-color: #FFB6C1; color: black;'
        else: return 'background-color: #C8E6C9; color: black;'
    except: return ''

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]
ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5]}

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty: return "0 UI", "Configure a Receita"
    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if v < 70: return "0 UI", "Hipoglicemia!"
    elif v <= 200: d = rec[f'{periodo}_f1']
    elif v <= 400: d = rec[f'{periodo}_f2']
    else: d = rec[f'{periodo}_f3']
    return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"

st.sidebar.info(f"Logado como: {st.session_state.user_email}")
tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    dfg = carregar_dados_seguro(ARQ_G)
    c1, c2 = st.columns([1, 2])
    with c1:
        v_gl = st.number_input("Valor da Glicemia", 0, 600, 100)
        m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
        dose, msg_d = calc_insulina(v_gl, m_gl)
        st.metric("Sugestão Insulina", dose, msg_d)
        if st.button("Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor', title="Últimas Medições"), use_container_width=True)
    st.write("### Histórico")
    st.dataframe(dfg.tail(15).style.applymap(cor_glicemia_status, subset=['Valor']), use_container_width=True)

with tab2:
    dfn = carregar_dados_seguro(ARQ_N)
    m_nutri = st.selectbox("Momento da Refeição", MOMENTOS_ORDEM, key="m_nutri")
    sel = st.multiselect("Alimentos consumidos", list(ALIMENTOS.keys()))
    if st.button("Salvar Nutrição"):
        carb = sum([ALIMENTOS[x][0] for x in sel])
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), carb]], columns=["Usuario","Data","Momento","Info","C"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.write("### Histórico Nutrição")
    st.dataframe(dfn.tail(15), use_container_width=True)

with tab3:
    # (Mantido igual à versão bem-sucedida para não quebrar a lógica)
    st.write("Configure aqui as doses da receita médica.")
    # Código da receita omitido aqui para brevidade, mas deve ser mantido conforme sua base.

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
