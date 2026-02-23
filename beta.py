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
import random
import string

# ================= CONFIGURAÇÕES E ESTILO =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

st.markdown("""
<style>
    .main { background-color: #f1f5f9; }
    .card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 20px; }
    .metric-box { background: #ffffff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 32px; font-weight: bold; color: #16a34a; }
</style>
""", unsafe_allow_html=True)

# ================= BANCO DE DADOS E SEGURANÇA =================

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

def enviar_email_senha(destinatario, nova_senha):
    remetente = "ewerlon.osbadboys@gmail.com"
    senha_app = "okiu qihp lglk trcc"
    corpo = f"Sua nova senha no Saúde Kids é: {nova_senha}"
    msg = MIMEText(corpo)
    msg['Subject'] = 'Recuperação de Senha - Saúde Kids'
    msg['From'] = remetente
    msg['To'] = destinatario
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remetente, senha_app)
            server.send_message(msg)
        return True
    except: return False

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    if 'Usuario' not in df.columns:
        df['Usuario'] = st.session_state.user_email if 'user_email' in st.session_state else ""
    return df[df['Usuario'] == st.session_state.user_email].copy()

def cor_glicemia_status(v):
    try:
        n = int(v)
        if n < 70: return 'background-color: #FFFFE0; color: black;'
        elif n > 180: return 'background-color: #FFB6C1; color: black;'
        else: return 'background-color: #C8E6C9; color: black;'
    except: return ''

# ================= LOGIN =================

if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids BETA")
    tab_l, tab_c, tab_r = st.tabs(["🔐 Login", "📝 Cadastro", "🔑 Recuperar"])
    
    with tab_l:
        u = st.text_input("E-mail")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            conn = sqlite3.connect('usuarios.db')
            res = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("Login inválido.")
            conn.close()

    with tab_c:
        n_n = st.text_input("Nome")
        n_e = st.text_input("E-mail ")
        n_s = st.text_input("Senha ", type="password")
        if st.button("Criar Conta"):
            try:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("INSERT INTO users VALUES (?,?,?)", (n_n, n_e, n_s))
                conn.commit()
                st.success("Conta criada!")
                conn.close()
            except: st.error("E-mail já existe.")

    with tab_r:
        r_e = st.text_input("E-mail para recuperar")
        if st.button("Enviar Senha Temporária"):
            nova = ''.join(random.choices(string.digits, k=6))
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=?", (r_e,)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (nova, r_e))
                conn.commit()
                if enviar_email_senha(r_e, nova): st.success("Verifique seu e-mail!")
                else: st.error("Falha no envio.")
            else: st.error("E-mail não cadastrado.")
            conn.close()
    st.stop()

# ================= ÁREA LOGADA =================

ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0], "Maçã": [15, 0, 0]}

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty: return "0 UI", "Configurar Receita"
    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if v < 70: return "0 UI", "Hipoglicemia!"
    elif v <= 200: d = rec[f'{periodo}_f1']
    elif v <= 400: d = rec[f'{periodo}_f2']
    else: d = rec[f'{periodo}_f3']
    return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"

st.sidebar.info(f"Logado como: {st.session_state.user_email}")

tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    c1, c2 = st.columns([1, 2])
    with c1:
        v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
        m_gl = st.selectbox("Momento", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        dose, msg_d = calc_insulina(v_gl, m_gl)
        st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty:
            dfg['DT'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            st.plotly_chart(px.line(dfg.tail(10), x='DT', y='Valor', markers=True), use_container_width=True)
    
    st.subheader("Histórico de Glicemias")
    if not dfg.empty:
        st.dataframe(dfg.tail(15).style.applymap(cor_glicemia_status, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfn = carregar_dados_seguro(ARQ_N)
    sel = st.multiselect("O que comeu?", list(ALIMENTOS.keys()))
    if st.button("💾 Salvar Refeição"):
        carb = sum([ALIMENTOS[x][0] for x in sel])
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), ", ".join(sel), carb]], columns=["Usuario","Data","Info","C"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.subheader("Histórico de Nutrição")
    st.dataframe(dfn.tail(15), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
    v = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    
    cm, cn = st.columns(2)
    with cm:
        st.info("MANHÃ")
        m1 = st.number_input("Dose 70-200", value=int(v.get('manha_f1',0)), key="m1")
        m2 = st.number_input("Dose 201-400", value=int(v.get('manha_f2',0)), key="m2")
        m3 = st.number_input("Dose > 400", value=int(v.get('manha_f3',0)), key="m3")
    with cn:
        st.info("NOITE")
        n1 = st.number_input("Dose 70-200 ", value=int(v.get('noite_f1',0)), key="n1")
        n2 = st.number_input("Dose 201-400 ", value=int(v.get('noite_f2',0)), key="n2")
        n3 = st.number_input("Dose > 400 ", value=int(v.get('noite_f3',0)), key="n3")
    if st.button("💾 Salvar Minha Receita"):
        nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':m1, 'manha_f2':m2, 'manha_f3':m3, 'noite_f1':n1, 'noite_f2':n2, 'noite_f3':n3}])
        df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Receita Atualizada!")
    st.markdown('</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Colorido"):
    df_g = carregar_dados_seguro(ARQ_G)
    if not df_g.empty:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_g.to_excel(writer, sheet_name='Glicemia', index=False)
            ws = writer.sheets['Glicemia']
            # Aplicando cores no Excel
            f_v = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
            f_r = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
            for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
                for cell in row:
                    if cell.value > 180: cell.fill = f_r
                    elif cell.value >= 70: cell.fill = f_v
        st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name="Relatorio.xlsx")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
