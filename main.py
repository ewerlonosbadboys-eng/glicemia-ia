import streamlit as st
import pandas as pd
from datetime import datetime
import io
import random

# Configuração da página
st.set_page_config(page_title="Gestor de Escala 5x2 - Obediência às Regras", layout="wide")

# 1. Login
if "password_correct" not in st.session_state:
    st.title("🔐 Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorreto.")
    st.stop()

# 2. Memória
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
if 'historico' not in st.session_state: st.session_state['historico'] = {}

# 3. Abas
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Setores", "📅 Gerar Escala", "📜 Histórico"])

with aba1:
    st.subheader("Cadastro")
    nome = st.text_input("Nome")
    setor = st.selectbox("Setor", st.session_state['db_cats'])
    c1, c2 = st.columns(2)
    f_sabado = c1.checkbox("Rodízio de Sábado")
    f_casada = c2.checkbox("Folga Casada (Dom + Seg)")
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'].append({"Nome": nome, "Setor": setor, "Rodizio_Sab": f_sabado, "Casada": f_casada})
            st.success("Salvo!")
    st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerador de Escala")
    if st.session_state['db_users']:
        func = st.selectbox("Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'Segunda','Tuesday':'Terça','Wednesday':'Quarta','Thursday':'Quinta','Friday':'Sexta','Saturday':'Sábado','Sunday':'Domingo'}
            df = pd.DataFrame({'Data': datas.strftime('%d/%m/%Y'), 'Dia': [d_pt[d] for d in datas.day_name()], 'Status': 'Trabalho'})
            
            user = next(i for i in st.session_state['db_users'] if i["Nome"] == func)
            
            # --- REGRA DOMINGOS 1x1 ---
            dom_idx = df[df['Dia'] == 'Domingo'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if user["Casada"] and (idx + 1) < len(df):
                        df.loc[idx + 1, 'Status'] = 'Folga'

            # --- REGRA DA FOLGA ALEATÓRIA (RESPEITANDO O SÁBADO) ---
            for i in range(0, len(df), 7):
                sem = df.iloc[i:i+7]
                if len(sem[sem['Status'] == 'Folga']) < 2:
                    # Se NÃO marcou caixinha de sábado, o Sábado é PROIBIDO de ter folga aleatória
                    if not user["Rodizio_Sab"]:
                        pode_folga = sem[(sem['Status'] == 'Trabalho') & (sem['Dia'] != 'Sábado')].index.tolist()
                    else:
                        pode_folga = sem[sem['Status'] == 'Trabalho'].index.tolist()
                    
                    if pode_folga:
                        df.loc[random.choice(pode_folga), 'Status'] = 'Folga'

            # --- TRAVA 5 DIAS (Última palavra) ---
            cont = 0
            for i in range(len(df)):
                cont = cont + 1 if df.loc[i, 'Status'] == 'Trabalho' else 0
                if cont > 5:
                    df.loc[i, 'Status'] = 'Folga'
                    cont = 0
            
            st.session_state['historico'][f"{func} - Março"] = df
            st.table(df)

with aba4:
    st.subheader("📜 Histórico")
    if st.session_state['historico']:
        sel = st.selectbox("Escala", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][sel]
        st.table(df_h)
        from openpyxl.styles import PatternFill, Font
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Escala')
            ws = writer.sheets['Escala']
            am, ve = PatternFill(start_color="FFFF00", fill_type="solid"), PatternFill(start_color="FF0000", fill_type="solid")
            for r in range(2, len(df_h) + 2):
                d, s = ws.cell(r, 2).value, ws.cell(r, 3).value
                if d == 'Domingo' and s == 'Folga':
                    for c in range(1, 4):
                        ws.cell(r, c).fill = ve
                        ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                elif s == 'Folga':
                    for c in range(1, 4): ws.cell(r, c).fill = am
        st.download_button("📥 Excel", out.getvalue(), "escala.xlsx")
