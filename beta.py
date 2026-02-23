import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill
import sqlite3
import random
import string

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR SQL ÚNICO E REPARADOR =================
def get_connection():
    # Centralizando em um único arquivo de banco de dados
    return sqlite3.connect('saude_kids_final.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Criando tabelas se não existirem
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')

    # Reparo de colunas para evitar o DatabaseError
    c.execute("PRAGMA table_info(nutricao)")
    existentes = [col[1] for col in c.fetchall()]
    if 'user_email' not in existentes:
        c.execute("ALTER TABLE nutricao ADD COLUMN user_email TEXT")
    if 'c' not in existentes:
        c.execute("ALTER TABLE nutricao ADD COLUMN c REAL DEFAULT 0")

    conn.commit()
    conn.close()

init_db()

# ================= FUNÇÕES DE APOIO =================
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina(valor, momento):
    conn = get_connection()
    df_r = pd.read_sql_query("SELECT * FROM receita WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    if df_r.empty: 
        return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    
    if valor < 70: 
        return "0 UI", "⚠️ Hipoglicemia!"
    elif valor <= 200: 
        dose = r[f'{prefixo}_f1']
    elif valor <= 400: 
        dose = r[f'{prefixo}_f2']
    else: 
        dose = r[f'{prefixo}_f3']
        
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= SISTEMA DE LOGIN =================
# LINHA 82 CORRIGIDA:
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Login")
    aba1, aba2 = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
    
    with aba1:
        u_log = st.text_input("E-mail", key="log_email")
        s_log = st.text_input("Senha", type="password", key="log_pass")
        if st.button("Acessar Sistema"):
            conn = get_connection()
            res = conn.execute("SELECT email FROM users WHERE email=? AND senha=?", (u_log, s_log)).fetchone()
            conn.close()
            if res:
                st.session_state.logado = True
                st.session_state.user_email = res[0]
                st.rerun()
            else:
                st.error("Dados de acesso inválidos.")
                
    with aba2:
        n_cad = st.text_input("Nome Completo", key="cad_nome")
        e_cad = st.text_input("Melhor E-mail", key="cad_email")
        s_cad = st.text_input("Senha de Acesso", type="password", key="cad_pass")
        if st.button("Finalizar Cadastro"):
            try:
                conn = get_connection()
                conn.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit()
                conn.close()
                st.success("Conta criada! Já pode fazer login.")
            except:
                st.error("Este e-mail já está em uso.")
    st.stop()

# ================= INTERFACE PRINCIPAL =================
st.sidebar.info(f"Conectado: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

tab_glic, tab_nutri, tab_rec = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

# --- ABA GLICEMIA ---
with tab_glic:
    conn = get_connection()
    df_g = pd.read_sql_query("SELECT data as Data, hora as Hora, valor as Valor, momento as Momento, dose as Dose FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    
    col_l, col_r = st.columns(2)
    with col_l:
        val = st.number_input("Glicemia atual:", 0, 600, 100)
        mom = st.selectbox("Momento do teste:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        dose_res, msg_res = calcular_insulina(val, mom)
        st.info(f"Sugestão: {dose_res} ({msg_res})")
        
        if st.button("💾 Salvar Valor"):
            conn = get_connection()
            conn.execute("INSERT INTO glicemia (user_email, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                         (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), datetime.now(fuso_br).strftime("%H:%M"), val, mom, dose_res))
            conn.commit()
            conn.close()
            st.rerun()
            
    with col_r:
        if not df_g.empty:
            st.plotly_chart(px.line(df_g.tail(10), x='Hora', y='Valor', markers=True, title="Histórico Recente"), use_container_width=True)

    st.dataframe(df_g.tail(10), use_container_width=True)

# --- ABA ALIMENTAÇÃO ---
with tab_nutri:
    st.subheader("🍽️ O que foi consumido?")
    escolhas = st.multiselect("Selecione os alimentos:", list(ALIMENTOS.keys()))
    carb_total = sum([ALIMENTOS[i][0] for i in escolhas])
    
    if st.button("💾 Salvar Refeição"):
        conn = get_connection()
        conn.execute("INSERT INTO nutricao (user_email, data, info, c) VALUES (?,?,?,?)",
                    (st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), ", ".join(escolhas), carb_total))
        conn.commit()
        conn.close()
        st.success("Refeição registrada!")
        st.rerun()
    
    conn = get_connection()
    df_n = pd.read_sql_query("SELECT data as Data, info as Alimentos, c as Carbo FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
    conn.close()
    st.dataframe(df_n, use_container_width=True)

# --- ABA RECEITA ---
with tab_rec:
    st.subheader("⚙️ Configuração das Tabelas de Insulina")
    conn = get_connection()
    rec_data = conn.execute("SELECT * FROM receita WHERE user_email=?", (st.session_state.user_email,)).fetchone()
    conn.close()
    
    if not rec_data: 
        rec_data = [st.session_state.user_email, 1, 2, 3, 1, 2, 3]
    
    col_m, col_n = st.columns(2)
    with col_m:
        st.write("**MANHÃ**")
        v_m1 = st.number_input("Dose (70-200)", value=float(rec_data[1]), key="v_m1")
        v_m2 = st.number_input("Dose (201-400)", value=float(rec_data[2]), key="v_m2")
        v_m3 = st.number_input("Dose (> 400)", value=float(rec_data[3]), key="v_m3")
    with col_n:
        st.write("**NOITE**")
        v_n1 = st.number_input("Dose (70-200) ", value=float(rec_data[4]), key="v_n1")
        v_n2 = st.number_input("Dose (201-400) ", value=float(rec_data[5]), key="v_n2")
        v_n3 = st.number_input("Dose (> 400) ", value=float(rec_data[6]), key="v_n3")
    
    if st.button("💾 Salvar Receita"):
        conn = get_connection()
        conn.execute("INSERT OR REPLACE INTO receita VALUES (?,?,?,?,?,?,?)", 
                     (st.session_state.user_email, v_m1, v_m2, v_m3, v_n1, v_n2, v_n3))
        conn.commit()
        conn.close()
        st.success("Dados da receita atualizados!")
