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
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# DESIGN MODO ESCURO (CORRIGIDO PARA NÃO SUMIR O LOGIN)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; color: white; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; color: white; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; }
    .stDataFrame { background-color: #1a1c24; }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E LOGIN (VOLTEI O SEU ORIGINAL COMPLETO) =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    corpo = f"<h3>Saúde Kids</h3><p>Sua nova senha de acesso é: <b>{senha_nova}</b></p>"
    msg = MIMEText(corpo, 'html'); msg['Subject'] = 'Sua Nova Senha - Saúde Kids'; msg['From'] = meu_email; msg['To'] = email_destino
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
    conn.commit(); conn.close()

init_db()

if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    # VOLTEI AS SUAS ABAS DE LOGIN QUE TINHAM SUMIDO
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])

    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("Incorreto.")
            conn.close()

    with abas_login[1]:
        n_cad = st.text_input("Nome completo")
        e_cad = st.text_input("E-mail para cadastro")
        s_cad = st.text_input("Senha para cadastro", type="password")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit(); conn.close()
                st.success("Conta criada!")
            except: st.error("E-mail já existe.")
    
    with abas_login[2]:
        email_alvo = st.text_input("E-mail da conta")
        if st.button("Recuperar Senha"):
            conn = sqlite3.connect('usuarios.db'); c = conn.cursor()
            if c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone():
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                if enviar_senha_nova(email_alvo, nova): st.success("Senha enviada!")
            conn.close()

    with abas_login[3]:
        alt_em = st.text_input("Confirme E-mail")
        alt_at = st.text_input("Senha Atual", type="password")
        alt_n1 = st.text_input("Nova Senha", type="password")
        if st.button("Alterar"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit(); st.success("Alterada!")
            conn.close()
    st.stop()

# ================= FUNÇÕES DE DADOS =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], 
    "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0]
}

# ================= INTERFACE PRINCIPAL =================
tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
    m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
    if st.button("💾 Salvar Glicemia"):
        agora = datetime.now(fuso_br)
        novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl]], columns=["Usuario","Data","Hora","Valor","Momento"])
        base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
        pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
        st.rerun()
    st.dataframe(dfg.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfn = carregar_dados_seguro(ARQ_N)
    m_nutri = st.selectbox("Momento da Refeição", MOMENTOS_ORDEM, key="n_m")
    sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
    
    # CÁLCULOS TOTAIS C, P, G
    c_tot = sum([ALIMENTOS[x][0] for x in sel])
    p_tot = sum([ALIMENTOS[x][1] for x in sel])
    g_tot = sum([ALIMENTOS[x][2] for x in sel])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("C (Carbo Total)", f"{c_tot}g")
    c2.metric("P (Proteína Total)", f"{p_tot}g")
    c3.metric("G (Gordura Total)", f"{g_tot}g")

    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], 
                             columns=["Usuario","Data","Momento","Info","C","P","G"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.dataframe(dfn.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COM DUAS ABAS =================
st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Glicemia + Alimentos"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_e_g.empty:
            pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Valor', aggfunc='last')
            pivot.to_excel(writer, sheet_name='Glicemia')
        if not df_e_n.empty:
            df_e_n.to_excel(writer, sheet_name='Alimentos', index=False)
    st.sidebar.download_button("Baixar Relatório", output.getvalue(), file_name="Relatorio_Kids.xlsx")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
