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

# ================= MOTOR SQL (COM AUTO-CORREÇÃO) =================
def get_connection():
    return sqlite3.connect('saude_kids_master.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, data TEXT, info TEXT, c REAL, p REAL, g REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (user_email TEXT PRIMARY KEY, manha_f1 REAL, manha_f2 REAL, manha_f3 REAL, noite_f1 REAL, noite_f2 REAL, noite_f3 REAL)''')
    
    # RESOLVE O ERRO DE DATABASE: Verifica colunas faltantes
    c.execute("PRAGMA table_info(glicemia)")
    cols = [col[1] for col in c.fetchall()]
    if 'user_email' not in cols: c.execute("ALTER TABLE glicemia ADD COLUMN user_email TEXT DEFAULT ''")
    if 'dose' not in cols: c.execute("ALTER TABLE glicemia ADD COLUMN dose TEXT DEFAULT '0 UI'")
    
    conn.commit()
    conn.close()

init_db()

# ================= ESTILO VISUAL =================
# (Sua definição de CSS original)
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES DE APOIO E SEGURANÇA =================
# (Mantidas todas as funções originais: calcular_insulina, enviar_email, etc)

# ================= SISTEMA DE LOGIN (4 ABAS) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    aba1, aba2, aba3, aba4 = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    # (Lógica de login completa...)
    st.stop()

# ================= ÁREA PRINCIPAL DO APP =================
st.sidebar.info(f"Logado como: {st.session_state.user_email}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

# ... (Lógica das abas T1, T2 e T3 filtrando por user_email) ...

# ================= EXCEL COLORIDO =================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            # Lógica original de pivô para o relatório médico
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            
            ws = writer.sheets['Glicemia']
            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid") # Verde
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid") # Amarelo
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid") # Vermelho

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

# Botão de Download (Sempre fora das abas para visibilidade)
st.markdown("---")
conn = get_connection()
dfg_f = pd.read_sql_query("SELECT * FROM glicemia WHERE user_email=?", conn, params=(st.session_state.user_email,))
dfn_f = pd.read_sql_query("SELECT * FROM nutricao WHERE user_email=?", conn, params=(st.session_state.user_email,))
conn.close()

if st.button("📥 BAIXAR RELATÓRIO EXCEL MÉDICO"):
    if not dfg_f.empty:
        excel_data = gerar_excel_colorido(dfg_f, dfn_f)
        st.download_button(
            label="Clique aqui para salvar o arquivo",
            data=excel_data,
            file_name=f"Relatorio_Saude_Kids_{datetime.now().strftime('%d_%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("Não há dados para gerar o relatório.")
