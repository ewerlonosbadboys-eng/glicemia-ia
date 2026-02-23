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
        # Inserção do Admin padrão
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

# ================= SISTEMA DE ACESSO =================
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids BETA")
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
                    st.success("Conta criada! Pode fazer login.")
                except:
                    st.error("Este e-mail já está cadastrado.")
                finally:
                    conn.close()
            else:
                st.warning("Preencha todos os campos.")

    with abas_login[2]:
        st.subheader("Recuperar Senha")
        email_recup = st.text_input("Digite seu e-mail cadastrado")
        if st.button("Verificar minha Senha"):
            conn = sqlite3.connect('usuarios.db')
            res = conn.execute("SELECT senha FROM users WHERE email=?", (email_recup,)).fetchone()
            conn.close()
            if res:
                st.info(f"Sua senha cadastrada é: **{res[0]}**")
            else:
                st.error("E-mail não encontrado.")
    st.stop()

# ================= ÁREA DO USUÁRIO =================
st.title("🧪 Painel Saúde Kids")

# Definição Dinâmica de Abas
titulos = ["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"]
if st.session_state.user_email == "admin":
    titulos.append("📩 Mensagens (Admin)")

tabs = st.tabs(titulos)

# 1. ABA GLICEMIA
with tabs[0]:
    st.subheader("Registro de Glicemia")
    with st.form("form_glicemia"):
        col1, col2, col3 = st.columns(3)
        with col1: d_reg = st.date_input("Data", datetime.now(fuso_br))
        with col2: m_reg = st.selectbox("Momento", MOMENTOS_ORDEM)
        with col3: v_reg = st.number_input("Valor (mg/dL)", 20, 600, 100)
        if st.form_submit_button("Salvar Registro"):
            novo_g = pd.DataFrame([[st.session_state.user_email, d_reg.strftime('%d/%m/%Y'), m_reg, v_reg]], 
                                  columns=['Usuario', 'Data', 'Momento', 'Valor'])
            df_g = carregar_dados_seguro(ARQ_G)
            pd.concat([df_g, novo_g], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo!")
            st.rerun()

    df_plot = carregar_dados_seguro(ARQ_G)
    if not df_plot.empty:
        fig = px.line(df_plot, x='Data', y='Valor', color='Usuario' if st.session_state.user_email == 'admin' else None, markers=True, title="Histórico Glicêmico")
        st.plotly_chart(fig, use_container_width=True)

# 2. ABA NUTRIÇÃO
with tabs[1]:
    st.subheader("Diário Nutricional")
    with st.form("form_nutri"):
        ali = st.text_input("Alimento/Refeição")
        carb = st.number_input("Carboidratos (g)", min_value=0)
        if st.form_submit_button("Registrar Alimento"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y %H:%M'), ali, carb]], 
                                  columns=['Usuario', 'Data', 'Alimento', 'Carbos'])
            df_n = carregar_dados_seguro(ARQ_N)
            pd.concat([df_n, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Registrado!")

# 3. ABA RECEITA
with tabs[2]:
    st.subheader("Configurações da Receita")
    st.info("Configurações de doses e proporções preservadas.")

# 4. ABA ADMIN
if st.session_state.user_email == "admin":
    with tabs[3]:
        st.subheader("📬 Mensagens Recebidas")
        if os.path.exists(ARQ_F):
            df_feed = pd.read_csv(ARQ_F)
            st.dataframe(df_feed, use_container_width=True)
            if st.button("Limpar Histórico de Mensagens"):
                os.remove(ARQ_F)
                st.rerun()
        else:
            st.info("Nenhuma mensagem ainda.")

# ================= MENU LATERAL (SIDEBAR) =================
st.sidebar.title(f"👤 {st.session_state.user_email}")

# Lógica de Exportação Excel
df_ex_g = carregar_dados_seguro(ARQ_G)
df_ex_n = carregar_dados_seguro(ARQ_N)
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    if not df_ex_g.empty: df_ex_g.to_excel(w, sheet_name='Glicemia', index=False)
    if not df_ex_n.empty: df_ex_n.to_excel(w, sheet_name='Nutricao', index=False)

st.sidebar.download_button("📥 Exportar Relatório Excel", out.getvalue(), file_name="Relatorio_BETA.xlsx")

st.sidebar.markdown("---")
with st.sidebar.expander("🚀 Enviar Sugestão ao Admin"):
    f_msg = st.text_area("O que podemos melhorar?")
    if st.button("Enviar"):
        if f_msg:
            novo_f = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y'), f_msg]], 
                                  columns=['Usuario', 'Data', 'Sugestão'])
            base_f = pd.read_csv(ARQ_F) if os.path.exists(ARQ_F) else pd.DataFrame()
            pd.concat([base_f, novo_f], ignore_index=True).to_csv(ARQ_F, index=False)
            st.success("Obrigado pelo feedback!")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
