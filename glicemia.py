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

# ================= DESIGN (CSS) =================
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #eef2f7, #f8fafc); }
    .card { background: white; padding: 25px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .metric-box { background: #f8fafc; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #e2e8f0; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #16a34a; }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E LOGIN (ORIGINAL PRESERVADO) =================
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

if not st.session_state.logado:
    _, col_central, _ = st.columns([1, 2, 1])
    with col_central:
        st.title("🧪 Saúde Kids - Acesso")
        u = st.text_input("E-mail")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            conn = sqlite3.connect('usuarios.db')
            res = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("Dados incorretos.")
            conn.close()
    st.stop()

# ================= FUNÇÕES DE DADOS =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

# TABELA NUTRICIONAL [Carbo, Proteína, Gordura]
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], 
    "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0]
}

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

# ================= INTERFACE =================
tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    c1, c2 = st.columns([1, 2])
    with c1:
        v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
        m_gl = st.selectbox("Momento Glicemia", MOMENTOS_ORDEM)
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl]], columns=["Usuario","Data","Hora","Valor","Momento"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty: st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor'), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfn = carregar_dados_seguro(ARQ_N)
    m_nutri = st.selectbox("Momento Refeição", MOMENTOS_ORDEM, key="nut_mom")
    sel = st.multiselect("Selecione os Alimentos", list(ALIMENTOS.keys()))
    
    # --- CÁLCULOS TOTAIS APARECENDO ABAIXO DOS ITENS ---
    c_tot = sum([ALIMENTOS[x][0] for x in sel])
    p_tot = sum([ALIMENTOS[x][1] for x in sel])
    g_tot = sum([ALIMENTOS[x][2] for x in sel])
    
    col_c, col_p, col_g = st.columns(3)
    col_c.markdown(f"**C (Carbo total):** {c_tot}g")
    col_p.markdown(f"**P (Proteína total):** {p_tot}g")
    col_g.markdown(f"**G (Gordura total):** {g_tot}g")

    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], 
                             columns=["Usuario","Data","Momento","Alimentos","C","P","G"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.write("### Histórico Nutrição")
    st.dataframe(dfn.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COM AS DUAS ABAS (CORRIGIDO) =================
st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel com Glicemia + Nutrição"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    
    if not df_e_g.empty or not df_e_n.empty:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Aba 1: Glicemia
            if not df_e_g.empty:
                pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Valor', aggfunc='last')
                pivot.to_excel(writer, sheet_name='Glicemia')
            
            # Aba 2: Nutrição (ESSA É A QUE ESTAVA FALTANDO)
            if not df_e_n.empty:
                df_e_n.to_excel(writer, sheet_name='Nutricao', index=False)
        
        st.sidebar.download_button("Clique para Baixar Excel", output.getvalue(), file_name="Relatorio_Saude_Kids.xlsx")
    else:
        st.sidebar.error("Sem dados para exportar.")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
