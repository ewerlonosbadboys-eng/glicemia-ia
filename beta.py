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
        conn.execute("INSERT INTO users VALUES (?,?,?)", ("Administrador", "admin", "542820"))
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

# ================= CONTROLE DE SESSÃO =================
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids BETA")
    abas_login = st.tabs(["Acessar", "Criar Conta"])
    
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
                st.error("E-mail ou Senha incorretos.")

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
    st.stop()

# ================= DASHBOARD (PÓS-LOGIN) =================
st.title("🧪 Painel Saúde Kids")

# Configuração de Abas Dinâmicas
titulos_abas = ["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"]
if st.session_state.user_email == "admin":
    titulos_abas.append("📩 Mensagens (Admin)")

tabs = st.tabs(titulos_abas)

with tabs[0]:
    st.subheader("Registro de Glicemia")
    with st.form("form_glicemia"):
        col1, col2, col3 = st.columns(3)
        with col1: data = st.date_input("Data", datetime.now(fuso_br))
        with col2: momento = st.selectbox("Momento", MOMENTOS_ORDEM)
        with col3: valor = st.number_input("Valor (mg/dL)", min_value=20, max_value=600, value=100)
        if st.form_submit_button("Salvar Registro"):
            novo_d = pd.DataFrame([[st.session_state.user_email, data.strftime('%d/%m/%Y'), momento, valor]], 
                                  columns=['Usuario', 'Data', 'Momento', 'Valor'])
            base = carregar_dados_seguro(ARQ_G)
            pd.concat([base, novo_d], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo!")
            st.rerun()

    df_plot = carregar_dados_seguro(ARQ_G)
    if not df_plot.empty:
        fig = px.line(df_plot, x='Data', y='Valor', color='Usuario' if st.session_state.user_email == 'admin' else None, markers=True, title="Tendência Glicêmica")
        st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Diário Nutricional")
    with st.form("form_nutri"):
        alimento = st.text_input("Alimento/Refeição")
        carbos = st.number_input("Carboidratos (g)", min_value=0)
        if st.form_submit_button("Registrar Alimento"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y %H:%M'), alimento, carbos]], 
                                  columns=['Usuario', 'Data', 'Alimento', 'Carbos'])
            base_n = carregar_dados_seguro(ARQ_N)
            pd.concat([base_n, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Registrado!")

with tabs[2]:
    st.subheader("Configurações da Receita")
    st.info("Espaço reservado para configurações de doses e proporções.")

# CONTEÚDO DA ABA ADMIN
if st.session_state.user_email == "admin":
    with tabs[3]:
        st.subheader("📬 Mensagens dos Usuários")
        if os.path.exists(ARQ_F):
            df_f = pd.read_csv(ARQ_F)
            st.dataframe(df_f, use_container_width=True)
            if st.button("Limpar Mensagens"):
                os.remove(ARQ_F)
                st.rerun()
        else:
            st.info("Nenhuma mensagem.")

# ================= SIDEBAR E EXPORTAÇÃO =================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/822/822118.png", width=100)
st.sidebar.title(f"Olá, {st.session_state.user_email}")

# Lógica do Excel
df_e_g = carregar_dados_seguro(ARQ_G)
df_e_n = carregar_dados_seguro(ARQ_N)
output = BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    if not df_e_g.empty:
        df_e_g.to_excel(writer, sheet_name='Glicemia', index=False)
    if not df_e_n.empty:
        df_e_n.to_excel(writer, sheet_name='Nutrição', index=False)

st.sidebar.download_button("📥 Baixar Relatório Excel", output.getvalue(), file_name="Relatorio_Saude.xlsx")

st.sidebar.markdown("---")
with st.sidebar.expander("🚀 Enviar Sugestão"):
    msg = st.text_area("O que podemos melhorar?")
    if st.button("Enviar"):
        if msg:
            novo_f = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y'), msg]], 
                                  columns=['Usuario', 'Data', 'Sugestão'])
            base_f = pd.read_csv(ARQ_F) if os.path.exists(ARQ_F) else pd.DataFrame()
            pd.concat([base_f, novo_f], ignore_index=True).to_csv(ARQ_F, index=False)
            st.success("Enviado!")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
