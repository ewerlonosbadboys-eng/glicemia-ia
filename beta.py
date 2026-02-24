import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill
import sqlite3

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_F = "feedbacks_BETA.csv"
DB_NAME = "usuarios_v_beta_final.db" 

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    .check-item { color: #4ade80; font-weight: bold; font-size: 18px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# ================= SISTEMA DE BANCO DE DADOS =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (nome TEXT, email TEXT PRIMARY KEY, senha TEXT, categoria TEXT)''')
    # Admin padrão
    admin_exists = cursor.execute("SELECT 1 FROM users WHERE email='admin'").fetchone()
    if not admin_exists:
        cursor.execute("INSERT INTO users VALUES (?,?,?,?)", ("Administrador", "admin", "542820", "Admin"))
    conn.commit()
    conn.close()

init_db()

if 'logado' not in st.session_state: st.session_state.logado = False

# ================= TELA DE ENTRADA COM CHECKLIST COMPLETO =================
if not st.session_state.logado:
    col_info, col_form = st.columns([1.2, 1])
    
    with col_info:
        st.title("🧪 Saúde Kids - BETA")
        st.markdown("### 📋 Status das Funcionalidades:")
        st.markdown("""
        <div class="check-item">✅ Usuário Admin (Visão Categorizada)</div>
        <div class="check-item">✅ Categorias: Pai/Mãe, Médico, Nutri</div>
        <div class="check-item">✅ Histórico de Glicemia com Cores</div>
        <div class="check-item">✅ Gráficos de Tendência Inteligentes</div>
        <div class="check-item">✅ Calculadora de Carboidratos</div>
        <div class="check-item">✅ Exportação Excel com Cores Automáticas</div>
        <div class="check-item">✅ Recuperação e Alteração de Senha</div>
        """, unsafe_allow_html=True)
        st.info("Sistema pronto para uso. Acesse ou crie sua conta ao lado.")

    with col_form:
        abas_acesso = st.tabs(["🔐 Login", "📝 Cadastro", "🔄 Senha"])
        
        with abas_acesso[0]:
            u = st.text_input("E-mail", key="l_u")
            s = st.text_input("Senha", type="password", key="l_s")
            if st.button("Entrar", use_container_width=True, key="btn_l"):
                conn = sqlite3.connect(DB_NAME)
                user = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
                if user:
                    st.session_state.logado = True
                    st.session_state.user_email = u
                    st.rerun()
                else: st.error("Acesso negado.")
                conn.close()

        with abas_acesso[1]:
            n_cad = st.text_input("Nome", key="c_n")
            e_cad = st.text_input("E-mail", key="c_e")
            s_cad = st.text_input("Senha", type="password", key="c_s")
            cat_cad = st.selectbox("Categoria", ["Pai/Mãe", "Médico(a)", "Nutricionista", "Outro"], key="c_c")
            if st.button("Cadastrar", use_container_width=True, key="btn_c"):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("INSERT INTO users VALUES (?,?,?,?)", (n_cad, e_cad, s_cad, cat_cad))
                    conn.commit(); conn.close(); st.success("Cadastrado com sucesso!")
                except: st.error("E-mail já registrado.")

        with abas_acesso[2]:
            st.subheader("Alterar Senha")
            em_alt = st.text_input("E-mail Cadastrado", key="alt_e")
            s_at = st.text_input("Senha Atual", type="password", key="alt_sa")
            s_nv = st.text_input("Nova Senha", type="password", key="alt_sn")
            if st.button("Atualizar Senha", use_container_width=True):
                conn = sqlite3.connect(DB_NAME)
                check = conn.execute("SELECT 1 FROM users WHERE email=? AND senha=?", (em_alt, s_at)).fetchone()
                if check:
                    conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nv, em_alt))
                    conn.commit(); st.success("Senha alterada!")
                else: st.error("Dados atuais incorretos.")
                conn.close()
    st.stop()

# ================= ÁREA PRIVADA: ADMIN =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Admin Master")
    t1, t2 = st.tabs(["👥 Gestão de Pessoas", "📬 Mensagens"])
    
    with t1:
        conn = sqlite3.connect(DB_NAME)
        df_u = pd.read_sql_query("SELECT nome, email, categoria FROM users", conn)
        conn.close()
        st.dataframe(df_u, use_container_width=True)
        
    with t2:
        if os.path.exists(ARQ_F):
            st.dataframe(pd.read_csv(ARQ_F), use_container_width=True)
            if st.button("Limpar"): os.remove(ARQ_F); st.rerun()
        else: st.info("Sem mensagens.")

# ================= ÁREA PRIVADA: USUÁRIO =================
else:
    def carregar(arq):
        if not os.path.exists(arq): return pd.DataFrame()
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()

    MOMENTOS = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Janta", "Após Janta", "Madrugada"]
    ALIMENTOS = {"Pão": 28, "Arroz": 10, "Feijão": 14, "Banana": 22}

    tab_gl, tab_nu, tab_re = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Configurações"])

    with tab_gl:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        df_g = carregar(ARQ_G)
        c1, c2 = st.columns([1, 2])
        with c1:
            v = st.number_input("Glicemia", 0, 600, 100, key="v_g_f")
            m = st.selectbox("Momento", MOMENTOS, key="m_g_f")
            if st.button("💾 Salvar"):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Usuario","Data","Hora","Valor","Momento"])
                base =
