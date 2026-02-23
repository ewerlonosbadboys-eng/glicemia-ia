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
import urllib.parse
import random
import string

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# ARQUIVOS DE DADOS (CSV)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÕES DE SEGURANÇA =================

def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    corpo = f"""
    <h3>Saúde Kids - Nova Senha Gerada</h3>
    <p>Sua nova senha de acesso é: <b style='font-size: 20px; color: blue;'>{senha_nova}</b></p>
    """
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Sua Nova Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except: return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ================= SISTEMA DE LOGIN =================

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])

    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        n = st.text_input("Nome completo", key="cad_n")
        em = st.text_input("Seu melhor e-mail", key="cad_e")
        se = st.text_input("Crie uma senha", type="password", key="cad_s")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n, em, se))
                conn.commit()
                conn.close()
                st.success("Conta criada! Vá em 'Entrar'.")
            except: st.error("E-mail já existe.")

    with abas_login[2]:
        email_alvo = st.text_input("E-mail da conta", key="rec_em")
        if st.button("Enviar Nova Senha"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            if c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone():
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                if enviar_senha_nova(email_alvo, nova): st.success("Nova senha enviada!")
                else: st.error("Erro ao enviar e-mail.")
            else: st.error("E-mail não encontrado.")
            conn.close()

    with abas_login[3]:
        alt_em = st.text_input("Confirme E-mail", key="alt_em")
        alt_at = st.text_input("Senha Atual", type="password", key="alt_at")
        alt_n1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        if st.button("Confirmar Alteração"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit()
                st.success("Senha alterada com sucesso!")
            else: st.error("Dados incorretos.")
            conn.close()
    st.stop()

# ================= ÁREA LOGADA =================

st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE CARREGAMENTO FILTRADO ---
def carregar_filtrado(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    if 'Usuario' in df.columns:
        return df[df['Usuario'] == st.session_state.user_email].copy()
    return pd.DataFrame()

# ================= CORES COM PRIORIDADE =================
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFFE0; color: black'
        elif n > 180: return 'background-color: #FFB6C1; color: black'
        elif n > 140: return 'background-color: #FFFFE0; color: black'
        else: return 'background-color: #90EE90; color: black'
    except: return ""

ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0], "Maçã": [15, 0, 0]}

def calcular_insulina_automatica(valor, momento):
    df_r = carregar_filtrado(ARQ_R)
    if df_r.empty: return "Configurar Receita", "⚠️"
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if valor < 70: return "0 UI", "Hipoglicemia!"
    elif valor <= 200: dose = r[f'{prefixo}_f1']
    elif valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= INTERFACE PRINCIPAL =================
st.sidebar.info(f"Logado como: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_filtrado(ARQ_G)
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Valor da Glicemia:", 0, 600, 100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        ds, rt = calcular_insulina_automatica(v, m)
        st.markdown(f'<div class="dose-alerta"><h1>{ds}</h1><small>{rt}</small></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, ds]], 
                                columns=["Usuario", "Data", "Hora", "Valor", "Momento", "Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            st.plotly_chart(px.line(dfg.tail(10), x='DataHora', y='Valor', markers=True), use_container_width=True)
    st.dataframe(dfg.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    sel = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        c = sum([ALIMENTOS[i][0] for i in sel])
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), ", ".join(sel), c]], 
                              columns=["Usuario", "Data", "Info", "C"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.dataframe(carregar_filtrado(ARQ_N), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
    v_at = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    col_m, col_n = st.columns(2)
    with col_m:
        st.write("MANHÃ")
        mf1 = st.number_input("Dose 70-200", value=int(v_at['manha_f1']), key="mf1")
        mf2 = st.number_input("201-400", value=int(v_at['manha_f2']), key="mf2")
        mf3 = st.number_input("Acima 400", value=int(v_at['manha_f3']), key="mf3")
    with col_n:
        st.write("NOITE")
        nf1 = st.number_input("Dose 70-200 ", value=int(v_at['noite_f1']), key="nf1")
        nf2 = st.number_input("201-400 ", value=int(v_at['noite_f2']), key="nf2")
        nf3 = st.number_input("Acima 400 ", value=int(v_at['noite_f3']), key="nf3")
    if st.button("💾 Salvar Minha Receita"):
        nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':mf1, 'manha_f2':mf2, 'manha_f3':mf3, 'noite_f1':nf1, 'noite_f2':nf2, 'noite_f3':nf3}])
        if not df_r_all.empty: df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email]
        pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Receita atualizada!")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO =================
def exportar_excel(df_g, df_n):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_g.empty: df_g.to_excel(writer, index=False, sheet_name='Glicemia')
        if not df_n.empty: df_n.to_excel(writer, index=False, sheet_name='Alimentação')
    return output.getvalue()

if st.button("📥 BAIXAR MEU RELATÓRIO"):
    dat_g = carregar_filtrado(ARQ_G)
    dat_n = carregar_filtrado(ARQ_N)
    st.download_button("Clique aqui para baixar", exportar_excel(dat_g, dat_n), file_name="Meus_Dados_Saude.xlsx")
