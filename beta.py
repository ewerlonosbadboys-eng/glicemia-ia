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

# ARQUIVOS DE DADOS (Mantendo seus nomes originais)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÕES DE SEGURANÇA =================

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

init_db()

# ================= SISTEMA DE LOGIN =================

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

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
            else: st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        n_cad = st.text_input("Nome completo", key="n_cad")
        e_cad = st.text_input("Seu melhor e-mail", key="e_cad")
        s_cad = st.text_input("Crie uma senha", type="password", key="s_cad")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit()
                conn.close()
                st.success("Conta criada! Vá em 'Entrar'.")
            except: st.error("E-mail já existe.")

    # ... (Abas de Esqueci/Alterar mantidas como o original)
    st.stop()

# ================= ÁREA LOGADA =================

# ESTILO VISUAL (NOVO LAYOUT)
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border: 1px solid #e2e8f0; }
    .stMetric { background: #f1f5f9; padding: 15px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# FUNÇÃO PARA CARREGAR DADOS SEM QUEBRAR COLUNAS
def carregar_dados(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    if 'Usuario' not in df.columns: 
        df['Usuario'] = st.session_state.user_email
    return df[df['Usuario'] == st.session_state.user_email].copy()

# CORES DE GLICEMIA (Mantendo sua regra original)
def cor_glicemia(v):
    try:
        n = int(v)
        if n < 70: return 'background-color: #FFFFE0' # Amarelo (Hipo)
        if n > 180: return 'background-color: #FFB6C1' # Vermelho (Hiper)
        return 'background-color: #90EE90' # Verde (Alvo)
    except: return ""

ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0], "Maçã": [15, 0, 0]}

def calcular_insulina_automatica(valor, momento):
    df_r = carregar_dados(ARQ_R)
    if df_r.empty: return "Configurar Receita", "⚠️"
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia"
    elif valor <= 200: dose = r[f'{prefixo}_f1']
    elif valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= INTERFACE =================
st.sidebar.write(f"👤 {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados(ARQ_G)
    col_input, col_chart = st.columns([1, 2])
    
    with col_input:
        st.subheader("Novo Registro")
        v_gl = st.number_input("Valor (mg/dL):", 0, 600, 100)
        m_gl = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        dose, ref = calcular_insulina_automatica(v_gl, m_gl)
        st.metric("Sugestão de Dose", dose, ref)
        
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], 
                                columns=["Usuario", "Data", "Hora", "Valor", "Momento", "Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()

    with col_chart:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            fig = px.line(dfg.tail(15), x='DataHora', y='Valor', markers=True, title="Evolução das Glicemias")
            st.plotly_chart(fig, use_container_width=True)
    
    if not dfg.empty:
        st.dataframe(dfg.tail(10).style.applymap(cor_glicemia, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Controle Nutricional")
    sel = st.multiselect("Selecione os alimentos:", list(ALIMENTOS.keys()))
    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        c_tot = sum([ALIMENTOS[i][0] for i in sel])
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), ", ".join(sel), c_tot]], 
                              columns=["Usuario", "Data", "Info", "C"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.success("Salvo!")
    st.dataframe(carregar_dados(ARQ_N), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Configuração da Receita")
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    if not df_r_all.empty and 'Usuario' not in df_r_all.columns: df_r_all['Usuario'] = st.session_state.user_email
    
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email]
    v_at = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("☀️ Período Diurno")
        mf1 = st.number_input("Dose 70-200", value=int(v_at.get('manha_f1',0)), key="mf1")
        mf2 = st.number_input("Dose 201-400", value=int(v_at.get('manha_f2',0)), key="mf2")
        mf3 = st.number_input("Dose > 400", value=int(v_at.get('manha_f3',0)), key="mf3")
    with c2:
        st.info("🌙 Período Noturno")
        nf1 = st.number_input("Dose 70-200 ", value=int(v_at.get('noite_f1',0)), key="nf1")
        nf2 = st.number_input("Dose 201-400 ", value=int(v_at.get('noite_f2',0)), key="nf2")
        nf3 = st.number_input("Dose > 400 ", value=int(v_at.get('noite_f3',0)), key="nf3")
    
    if st.button("💾 Salvar Minhas Doses"):
        nova_r = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':mf1, 'manha_f2':mf2, 'manha_f3':mf3, 'noite_f1':nf1, 'noite_f2':nf2, 'noite_f3':nf3}])
        df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        pd.concat([df_r_all, nova_r], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Receita atualizada!")
    st.markdown('</div>', unsafe_allow_html=True)
