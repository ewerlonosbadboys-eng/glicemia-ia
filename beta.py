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
        # Insere ou atualiza o admin padrão
        conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?)", ("Administrador", "admin", "542820"))
        conn.commit()
    except: pass
    conn.close()

init_db()

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    # Admin vê tudo, usuário comum vê apenas o seu
    if st.session_state.get('user_email') == "admin":
        return df
    return df[df['Usuario'] == st.session_state.get('user_email', '')].copy()

# ================= SISTEMA DE ENTRADA (LOGIN) =================
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids BETA - Acesso")
    abas_login = st.tabs(["Acessar", "Criar Conta", "Esqueci a Senha"])
    
    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Entrar"):
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
        n_nome = st.text_input("Nome Completo")
        n_email = st.text_input("E-mail")
        n_pass = st.text_input("Escolha uma Senha", type="password")
        if st.button("Cadastrar"):
            if n_nome and n_email and n_pass:
                conn = sqlite3.connect('usuarios.db')
                try:
                    conn.execute("INSERT INTO users VALUES (?,?,?)", (n_nome, n_email, n_pass))
                    conn.commit()
                    st.success("Conta criada! Vá em 'Acessar'.")
                except:
                    st.error("Este e-mail já existe.")
                finally:
                    conn.close()
            else:
                st.warning("Preencha tudo.")

    with abas_login[2]:
        st.subheader("Recuperação de Acesso")
        email_rec = st.text_input("E-mail cadastrado")
        if st.button("Mostrar minha Senha"):
            conn = sqlite3.connect('usuarios.db')
            res = conn.execute("SELECT senha FROM users WHERE email=?", (email_rec,)).fetchone()
            conn.close()
            if res:
                st.info(f"Sua senha é: {res[0]}")
            else:
                st.error("Usuário não encontrado.")
    st.stop()

# ================= ÁREA LOGADA =================
st.title("🧪 Painel de Controle")

# Definição das Abas (Admin ganha a 4ª aba)
titulos = ["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"]
if st.session_state.user_email == "admin":
    titulos.append("📩 Mensagens (Admin)")

tabs = st.tabs(titulos)

# --- ABA GLICEMIA ---
with tabs[0]:
    st.subheader("Novo Registro Glicêmico")
    with st.form("glic"):
        c1, c2, c3 = st.columns(3)
        d_g = c1.date_input("Data", datetime.now(fuso_br))
        m_g = c2.selectbox("Momento", MOMENTOS_ORDEM)
        v_g = c3.number_input("Valor", 20, 600, 100)
        if st.form_submit_button("Salvar"):
            novo = pd.DataFrame([[st.session_state.user_email, d_g.strftime('%d/%m/%Y'), m_g, v_g]], 
                                columns=['Usuario', 'Data', 'Momento', 'Valor'])
            df_g = carregar_dados_seguro(ARQ_G)
            pd.concat([df_g, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Registrado!")
            st.rerun()

    df_p = carregar_dados_seguro(ARQ_G)
    if not df_p.empty:
        st.plotly_chart(px.line(df_p, x='Data', y='Valor', markers=True, title="Histórico"), use_container_width=True)

# --- ABA NUTRIÇÃO ---
with tabs[1]:
    st.subheader("Diário Nutricional")
    with st.form("nutri"):
        ali = st.text_input("Alimento")
        carb = st.number_input("Carbos (g)", 0, 500)
        if st.form_submit_button("Registrar"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y %H:%M'), ali, carb]], 
                                  columns=['Usuario', 'Data', 'Alimento', 'Carbos'])
            df_n = carregar_dados_seguro(ARQ_N)
            pd.concat([df_n, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Salvo!")

# --- ABA RECEITA ---
with tabs[2]:
    st.subheader("Configurações de Receita")
    st.info("As configurações de doses e proporções ficam armazenadas aqui.")

# --- ABA ADMIN (MENSAGENS) ---
if st.session_state.user_email == "admin":
    with tabs[3]:
        st.subheader("📩 Sugestões Recebidas")
        if os.path.exists(ARQ_F):
            df_feed = pd.read_csv(ARQ_F)
            st.dataframe(df_feed, use_container_width=True)
            if st.button("Limpar Tudo"):
                os.remove(ARQ_F)
                st.rerun()
        else:
            st.info("Nenhuma mensagem.")

# ================= SIDEBAR (EXCEL E FEEDBACK) =================
st.sidebar.title(f"Olá, {st.session_state.user_email}")

# Lógica Excel
df_ex_g = carregar_dados_seguro(ARQ_G)
df_ex_n = carregar_dados_seguro(ARQ_N)
out = BytesIO()
with pd.ExcelWriter(out, engine='openpyxl') as w:
    if not df_ex_g.empty: df_ex_g.to_excel(w, sheet_name='Glicemia', index=False)
    if not df_ex_n.empty: df_ex_n.to_excel(w, sheet_name='Nutricao', index=False)

st.sidebar.download_button("📥 Exportar para Excel", out.getvalue(), "Saude_Kids.xlsx")

st.sidebar.markdown("---")
with st.sidebar.expander("🚀 Enviar Sugestão"):
    f_msg = st.text_area("O que podemos melhorar?")
    if st.button("Enviar"):
        if f_msg:
            n_f = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y'), f_msg]], 
                               columns=['Usuario', 'Data', 'Sugestão'])
            base_f = pd.read_csv(ARQ_F) if os.path.exists(ARQ_F) else pd.DataFrame()
            pd.concat([base_f, n_f], ignore_index=True).to_csv(ARQ_F, index=False)
            st.success("Obrigado!")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
