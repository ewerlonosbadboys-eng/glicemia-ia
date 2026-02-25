import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Gestor Escala Profissional 2026", layout="wide")

# --- 1. LOGIN ---
if "password_correct" not in st.session_state:
    st.title("🔐 Login do Sistema")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# --- 2. MEMÓRIA DO GRUPO ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.title("📅 Gestão de Escala 5x2")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes Específicos", "📥 4. Baixar Excel"])

# --- ABA 1: CADASTRO (Adiciona ao Grupo) ---
with aba1:
    st.subheader("Cadastrar no Grupo")
    nome = st.text_input("Nome do Funcionário")
    h_ent_padrao = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar no Grupo"):
        if nome:
            # Remove se já existir e adiciona o novo (evita duplicados no grupo)
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_ent_padrao.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success(f"✅ {nome} adicionado ao grupo!")

# --- ABA 2: GERAR ESCALA ---
with aba2:
    if st.session_state['db_users']:
        # Seleciona qualquer um do grupo
        func_sel = st.selectbox("Selecione o Funcionário do Grupo", [u.get('Nome') for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), {})
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == 1:
                    df.loc[d_idx, 'Status'] = 'Folga'
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'

            for sem in range(0, 31, 7):
                bloco = df.iloc[sem:min(sem+7, 31)]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist()
