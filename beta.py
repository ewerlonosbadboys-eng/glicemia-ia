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

# DESIGN MODO ESCURO (DARK MODE) - TUDO PRETO/AZUL ESCURO
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 20px; border-radius: 15px; border: 1px solid #30363d; margin-bottom: 20px; color: white; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; color: white; }
    .dose-destaque { font-size: 32px; font-weight: bold; color: #4ade80; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE SEGURANÇA (SUAS ORIGINAIS) =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

if 'logado' not in st.session_state: st.session_state.logado = False

# LOGIN COM FUNDO ESCURO
if not st.session_state.logado:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.title("🧪 Saúde Kids - Login")
        u = st.text_input("E-mail")
        s = st.text_input("Senha", type="password")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("Erro no login.")
            conn.close()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ================= CONTROLE DE DADOS =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

# TABELA NUTRICIONAL QUE VOCÊ PEDIU
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], 
    "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0]
}

# ================= INTERFACE PRINCIPAL =================
tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    v_gl = st.number_input("Valor", 0, 600, 100)
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
    m_nutri = st.selectbox("Momento Refeição", MOMENTOS_ORDEM, key="n_m")
    sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
    
    # CÁLCULOS TOTAIS C, P, G QUE VOCÊ RECLAMOU QUE SUMIU
    c_tot = sum([ALIMENTOS[x][0] for x in sel])
    p_tot = sum([ALIMENTOS[x][1] for x in sel])
    g_tot = sum([ALIMENTOS[x][2] for x in sel])
    
    # EXIBIÇÃO EM 3 COLUNAS (MODO ESCURO)
    col_c, col_p, col_g = st.columns(3)
    col_c.metric("C (Carbo)", f"{c_tot}g")
    col_p.metric("P (Proteína)", f"{p_tot}g")
    col_g.metric("G (Gordura)", f"{g_tot}g")

    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        # SALVANDO TUDO: INFO, C, P e G
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], 
                             columns=["Usuario","Data","Momento","Info","C","P","G"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    
    st.write("### Histórico Alimentos")
    st.dataframe(dfn.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write("### ⚙️ Configurações e Receita")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COM DUAS ABAS (GLICEMIA + ALIMENTOS) =================
st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Completo"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_e_g.empty:
            pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Valor', aggfunc='last')
            pivot.to_excel(writer, sheet_name='Glicemia')
        if not df_e_n.empty:
            df_e_n.to_excel(writer, sheet_name='Alimentos', index=False)
            
    st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name="Relatorio_Completo.xlsx")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
