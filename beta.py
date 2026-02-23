import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
import sqlite3

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_F = "feedbacks_BETA.csv"

MOMENTOS_ORDEM = ["Jejum", "Pré-Almoço", "Pós-Almoço", "Pré-Jantar", "Pós-Jantar", "Madrugada"]

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
</style>
""", unsafe_allow_html=True)

def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    try:
        # Garante que o admin exista
        conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?)", ("Administrador", "admin", "542820"))
        conn.commit()
    except: pass
    conn.close()

init_db()

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    if st.session_state.get('user_email') == "admin":
        return df
    return df[df['Usuario'] == st.session_state.get('user_email', '')].copy()

# ================= SISTEMA DE ENTRADA =================
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids BETA")
    # AQUI ESTÁ A ABA DE ESQUECI A SENHA
    abas_login = st.tabs(["Acessar", "Criar Conta", "Esqueci a Senha"])
    
    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            user_db = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            conn.close()
            if user_db:
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else:
                st.error("Dados incorretos.")

    with abas_login[1]:
        new_nome = st.text_input("Nome Completo")
        new_email = st.text_input("E-mail de Cadastro")
        new_pass = st.text_input("Senha de Cadastro", type="password")
        if st.button("Criar Conta"):
            if new_nome and new_email and new_pass:
                conn = sqlite3.connect('usuarios.db')
                try:
                    conn.execute("INSERT INTO users VALUES (?,?,?)", (new_nome, new_email, new_pass))
                    conn.commit()
                    st.success("Conta criada!")
                except:
                    st.error("E-mail já cadastrado.")
                finally:
                    conn.close()

    with abas_login[2]:
        st.subheader("Recuperação de Senha")
        e_recup = st.text_input("Digite seu e-mail cadastrado")
        if st.button("Verificar Senha"):
            conn = sqlite3.connect('usuarios.db')
            res = conn.execute("SELECT senha FROM users WHERE email=?", (e_recup,)).fetchone()
            conn.close()
            if res:
                st.info(f"Sua senha é: **{res[0]}**")
            else:
                st.error("E-mail não encontrado.")
    st.stop()

# ================= PAINEL PRINCIPAL =================
st.title("🧪 Painel Saúde Kids")

titulos = ["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"]
if st.session_state.user_email == "admin":
    titulos.append("📩 Mensagens (Admin)")

tabs = st.tabs(titulos)

# 1. GLICEMIA
with tabs[0]:
    st.subheader("Registro Glicêmico")
    with st.form("glic"):
        c1, c2, c3 = st.columns(3)
        d = c1.date_input("Data", datetime.now(fuso_br))
        m = c2.selectbox("Momento", MOMENTOS_ORDEM)
        v = c3.number_input("Valor", 20, 600, 100)
        if st.form_submit_button("Salvar"):
            n = pd.DataFrame([[st.session_state.user_email, d.strftime('%d/%m/%Y'), m, v]], columns=['Usuario','Data','Momento','Valor'])
            base = carregar_dados_seguro(ARQ_G)
            pd.concat([base, n], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo!")
            st.rerun()
    
    df_p = carregar_dados_seguro(ARQ_G)
    if not df_p.empty:
        st.plotly_chart(px.line(df_p, x='Data', y='Valor', color='Usuario' if st.session_state.user_email == 'admin' else None, markers=True), use_container_width=True)

# 2. NUTRIÇÃO
with tabs[1]:
    st.subheader("Diário Nutricional")
    with st.form("nutri"):
        ali = st.text_input("Alimento")
        car = st.number_input("Carbos (g)", 0)
        if st.form_submit_button("Registrar"):
            n_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y %H:%M'), ali, car]], columns=['Usuario','Data','Alimento','Carbos'])
            base_n = carregar_dados_seguro(ARQ_N)
            pd.concat([base_n, n_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Registrado!")

# 3. RECEITA
with tabs[2]:
    st.subheader("⚙️ Configurações da Receita")
    st.info("Espaço para doses e proporções.")

# 4. ADMIN
if st.session_state.user_email == "admin":
    with tabs[3]:
        st.subheader("📬 Mensagens")
        if os.path.exists(ARQ_F):
            df_f = pd.read_csv(ARQ_F)
            st.dataframe(df_f, use_container_width=True)
            if st.button("Limpar Mensagens"):
                os.remove(ARQ_F)
                st.rerun()
        else:
            st.info("Sem mensagens.")

# ================= SIDEBAR =================
st.sidebar.title(f"👤 {st.session_state.user_email}")

# Excel
df_ex_g = carregar_dados_seguro(ARQ_G)
df_ex_n = carregar_dados_seguro(ARQ_N)
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    if not df_ex_g.empty: df_ex_g.to_excel(w, sheet_name='Glicemia', index=False)
    if not df_ex_n.empty: df_ex_n.to_excel(w, sheet_name='Nutricao', index=False)
st.sidebar.download_button("📥 Baixar Excel", out.getvalue(), "Relatorio.xlsx")

st.sidebar.markdown("---")
with st.sidebar.expander("🚀 Feedback"):
    f_msg = st.text_area("Sugestão:")
    if st.button("Enviar"):
        if f_msg:
            n_f = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y'), f_msg]], columns=['Usuario','Data','Sugestão'])
            b_f = pd.read_csv(ARQ_F) if os.path.exists(ARQ_F) else pd.DataFrame()
            pd.concat([b_f, n_f], ignore_index=True).to_csv(ARQ_F, index=False)
            st.success("Enviado!")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
