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

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR SQL (COM REPARO DE TABELAS) =================
def get_connection():
    return sqlite3.connect('saude_kids_master.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Criar tabelas base
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL, p REAL, g REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')

    # --- REPARO DE EMERGÊNCIA (Resolve o DatabaseError) ---
     tabelas_para_checar = {
        'glicemia': ['user_email', 'dose'],
        'nutricao': ['user_email', 'c', 'p', 'g']
    }
    
    for tabela, colunas in tabelas_para_checar.items():
        c.execute(f"PRAGMA table_info({tabela})")
        colunas_existentes = [col[1] for col in c.fetchall()]
        for col in colunas:
            if col not in colunas_existentes:
                tipo = "REAL" if col in ['c', 'p', 'g'] else "TEXT"
                c.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo} DEFAULT ''")
    
    conn.commit()
    conn.close()

init_db()

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE APOIO =================
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina_automatica(valor, momento):
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT * FROM receita WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    if df_r.empty: return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia!"
    elif 70 <= valor <= 200: dose = r[f'{prefixo}_f1']
    elif 201 <= valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= FUNÇÕES DE SEGURANÇA =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    msg = MIMEText(f"<h3>Saúde Kids</h3><p>Sua nova senha é: <b>{senha_nova}</b></p>", 'html')
    msg['Subject'] = 'Acesso Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except: return False

# ================= SISTEMA DE LOGIN (4 ABAS) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    aba_login, aba_criar, aba_esqueci, aba_alterar = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with aba_login:
        u = st.text_input("E-mail", key="login_mail")
        s = st.text_input("Senha", type="password", key="login_pass")
        if st.button("Acessar Sistema"):
            conn = get_connection()
            res = conn.execute("SELECT email FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            conn.close()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")

    with aba_criar:
        n_c = st.text_input("Nome Completo")
        e_c = st.text_input("E-mail")
        s_c = st.text_input("Senha", type="password")
        if st.button("Finalizar Cadastro"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_c, e_c, s_c))
                conn.commit()
                conn.close()
                st.success("Cadastro realizado com sucesso!")
            except: st.error("Este e-mail já está em uso.")

    with aba_esqueci:
        e_rec = st.text_input("E-mail cadastrado")
        if st.button("Recuperar Senha"):
            nova = gerar_senha_temporaria()
            if enviar_senha_nova(e_rec, nova):
                conn = get_connection()
                conn.execute("UPDATE users SET senha=? WHERE email=?", (nova, e_rec))
                conn.commit()
                conn.close()
                st.success("Senha enviada para o seu e-mail!")
            else: st.error("Erro ao enviar e-mail.")

    with aba_alterar:
        u_alt = st.text_input("Confirme E-mail")
        s_ant = st.text_input("Senha Atual", type="password")
        s_nov = st.text_input("Nova Senha", type="password")
        if st.button("Alterar Senha"):
            conn = get_connection()
            check = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u_alt, s_ant)).fetchone()
            if check:
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nov, u_alt))
                conn.commit()
                st.success("Senha alterada!")
            else: st.error("Dados incorretos.")
            conn.close()
    st.stop()

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

# ================= ÁREA DO APP =================
st.sidebar.info(f"Usuário: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

# --- Aba Glicemia ---
with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    conn = get_connection()
    dfg = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    
    col1, col2 = st.columns(2)
    with col1:
        v = st.number_input("Valor:", 0, 600, 100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        ds, rt = calcular_insulina_automatica(v, m)
        st.markdown(f'<div class="dose-alerta"><h1>{ds}</h1><small>{rt}</small></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar Glicemia"):
            conn = get_connection()
            conn.execute("INSERT INTO glicemia (user_email, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                         (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), datetime.now(fuso_br).strftime("%H:%M"), v, m, ds))
            conn.commit()
            conn.close()
            st.rerun()
    with col2:
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Data', y='Valor', markers=True), use_container_width=True)
    st.dataframe(dfg.tail(10).style.applymap(cor_glicemia, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- Aba Alimentação ---
with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🍽️ Registro de Refeição")
    itens = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
    carb_total = sum([ALIMENTOS[i][0] for i in itens])
    if st.button("💾 Salvar Refeição"):
        conn = get_connection()
        conn.execute("INSERT INTO nutricao (user_email, data, info, c) VALUES (?,?,?,?)",
                    (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), ", ".join(itens), carb_total))
        conn.commit()
        conn.close()
        st.rerun()
    conn = get_connection()
    dfn = pd.read_sql_query("SELECT data as Data, info as Info, c as Carbos FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    st.dataframe(dfn, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- Aba Receita ---
with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Minha Receita (Doses)")
    conn = get_connection()
    r = conn.execute("SELECT * FROM receita WHERE user_email=?", (st.session_state.user_email,)).fetchone()
    conn.close()
    if not r: r = [st.session_state.user_email, 1, 2, 3, 1, 2, 3]
    
    c_m, c_n = st.columns(2)
    with c_m:
        st.write("**MANHÃ**")
        m1 = st.number_input("Até 200", value=float(r[1]), key="m1")
        m2 = st.number_input("201-400", value=float(r[2]), key="m2")
        m3 = st.number_input("Acima 400", value=float(r[3]), key="m3")
    with c_n:
        st.write("**NOITE**")
        n1 = st.number_input("Até 200 ", value=float(r[4]), key="n1")
        n2 = st.number_input("201-400 ", value=float(r[5]), key="n2")
        n3 = st.number_input("Acima 400 ", value=float(r[6]), key="n3")
    if st.button("💾 Salvar Doses"):
        conn = get_connection()
        conn.execute("INSERT OR REPLACE INTO receita VALUES (?,?,?,?,?,?,?)", (st.session_state.user_email, m1, m2, m3, n1, n2, n3))
        conn.commit()
        conn.close()
        st.success("Receita salva!")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO =================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            val = int(str(cell.value).split(" ")[0])
                            if val < 70: cell.fill = a_fill
                            elif val > 180: cell.fill = r_fill
                            elif val > 140: cell.fill = a_fill
                            else: cell.fill = v_fill
                        except: pass
        if not df_nutri.empty:
            df_nutri.to_excel(writer, index=False, sheet_name='Alimentacao')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO EXCEL MÉDICO"):
    conn = get_connection()
    dg = pd.read_sql_query("SELECT * FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    dn = pd.read_sql_query("SELECT * FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    if not dg.empty:
        st.download_button("Clique aqui para baixar", gerar_excel_colorido(dg, dn), f"Relatorio_SaudeKids_{datetime.now().strftime('%d_%m')}.xlsx")
    else: st.warning("Sem dados para exportar.")
