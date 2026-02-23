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
ARQ_F = "feedbacks_BETA.csv"

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E LOGIN =================
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
    conn.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    try:
        conn.execute("INSERT OR IGNORE INTO users VALUES (?,?,?)", ("Administrador", "admin", "542820"))
        conn.commit()
    except: pass
    conn.close()

init_db()

if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            user_valido = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            conn.close()
            if user_valido:
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("E-mail ou Senha incorretos.")

    with abas_login[1]:
        new_nome = st.text_input("Nome Completo")
        new_email = st.text_input("E-mail para Cadastro")
        new_pass = st.text_input("Senha para Cadastro", type="password")
        if st.button("Realizar Cadastro"):
            try:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("INSERT INTO users VALUES (?,?,?)", (new_nome, new_email, new_pass))
                conn.commit(); conn.close()
                st.success("Conta criada!")
            except: st.error("E-mail já cadastrado.")

    with abas_login[2]:
        email_alvo = st.text_input("Digite seu e-mail")
        if st.button("Recuperar Acesso"):
            conn = sqlite3.connect('usuarios.db'); c = conn.cursor()
            if c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone():
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                if enviar_senha_nova(email_alvo, nova): st.success("Senha enviada ao e-mail!")
                else: st.error("Erro no envio.")
            else: st.error("E-mail não encontrado.")
            conn.close()

    with abas_login[3]:
        alt_em = st.text_input("E-mail", key="alt_em")
        alt_at = st.text_input("Senha Atual", type="password", key="alt_at")
        alt_n1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        if st.button("Confirmar Alteração"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit(); st.success("Senha alterada!")
            else: st.error("Dados incorretos.")
            conn.close()
    st.stop()

# ================= FUNÇÕES DE APOIO =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    if st.session_state.user_email == "admin": return df
    return df[df['Usuario'] == st.session_state.user_email].copy()

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty: return "0 UI", "Configurar Receita"
    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    try:
        if v < 70: return "0 UI", "Hipoglicemia!"
        elif v <= 200: d = rec[f'{periodo}_f1']
        elif v <= 400: d = rec[f'{periodo}_f2']
        else: d = rec[f'{periodo}_f3']
        return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"
    except: return "0 UI", "Erro na Receita"

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

ALIMENTOS = {
    "Pão Francês (1un)": [28, 4, 1], "Arroz Branco (colher)": [10, 2, 0], "Feijão (concha)": [14, 5, 1], "Banana": [22, 1, 0]
}

# ================= INTERFACE PRINCIPAL =================
titulos_abas = ["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"]
if st.session_state.user_email == "admin":
    titulos_abas.append("🛡️ Admin")

tabs = st.tabs(titulos_abas)

with tabs[0]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    c1, c2 = st.columns([1, 2])
    with c1:
        v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
        m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
        dose, msg_d = calc_insulina(v_gl, m_gl)
        st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty:
            fig = px.line(dfg.tail(10), x='Hora', y='Valor', markers=True, title="Tendência")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dfg.tail(15), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfn = carregar_dados_seguro(ARQ_N)
    sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), "Refeição", ", ".join(sel), 0, 0, 0]], columns=["Usuario","Data","Momento","Info","C","P","G"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.dataframe(dfn.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Configuração de Receita")
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
    v = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    m1 = st.number_input("Manhã 70-200", value=int(v.get('manha_f1',0)))
    if st.button("💾 Salvar Receita"):
        nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':m1, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}])
        df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Salvo!")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= ABA ADMIN CORRIGIDA =================
if st.session_state.user_email == "admin":
    with tabs[3]:
        st.subheader("👥 Usuários Cadastrados")
        conn = sqlite3.connect('usuarios.db')
        df_users = pd.read_sql_query("SELECT nome, email FROM users", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True)

        st.markdown("---")
        st.subheader("📬 Mensagens dos Usuários")
        if os.path.exists(ARQ_F):
            df_feed = pd.read_csv(ARQ_F)
            st.dataframe(df_feed.sort_index(ascending=False), use_container_width=True)
            if st.button("🗑️ Limpar Mensagens"):
                os.remove(ARQ_F); st.rerun()
        else: st.info("Nenhuma mensagem.")

# ================= SIDEBAR =================
st.sidebar.markdown("---")
with st.sidebar.expander("🚀 Enviar Sugestão ao Admin"):
    txt_feed = st.text_area("Mensagem:")
    if st.button("Enviar"):
        if txt_feed:
            agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M")
            novo_f = pd.DataFrame([[st.session_state.user_email, agora, txt_feed]], columns=["Usuario", "Data", "Sugestão"])
            base_f = pd.read_csv(ARQ_F) if os.path.exists(ARQ_F) else pd.DataFrame()
            pd.concat([base_f, novo_f], ignore_index=True).to_csv(ARQ_F, index=False)
            st.success("Enviado!")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
