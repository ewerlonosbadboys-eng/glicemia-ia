import streamlit as st
import pandas as pd
from datetime import datetime
import io
import random

# Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 1. Sistema de Login
if "password_correct" not in st.session_state:
    st.title("🔐 Acesso Administrativo")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
    st.stop()

# 2. Inicialização de Memória
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.sidebar.button("Sair", on_click=lambda: st.session_state.clear())

# 3. Abas
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Setores", "📅 Gerar Escala", "📜 Histórico"])

with aba2:
    st.subheader("Configurar Setores")
    nova_cat = st.text_input("Nome do Setor")
    if st.button("Salvar Setor"):
        if nova_cat:
            st.session_state['db_cats'].append(nova_cat)
            st.success("Setor salvo!")

with aba1:
    st.subheader("Cadastro de Equipe")
    nome = st.text_input("Nome do Funcionário")
    setor = st.selectbox("Setor", st.session_state['db_cats'])
    st.write("### Configurações de Rodízio e Folga")
    col1, col2 = st.columns(2)
    f_sabado = col1.checkbox("Participar de Rodízio no Sábado")
    f_casada = col2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar Cadastro"):
        if nome:
            st.session_state['db_users'].append({
                "Nome": nome, "Setor": setor, 
                "Rodizio_Sab": f_sabado, "Casada": f_casada
            })
            st.success(f"{nome} cadastrado!")
    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerador de Escala 5x2")
    if st.session_state['db_users']:
        func_sel = st.selectbox("Escolha o Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            dias_pt = {'Monday':'Segunda','Tuesday':'Terça','Wednesday':'Quarta','Thursday':'Quinta','Friday':'Sexta','Saturday':'Sábado','Sunday':'Domingo'}
            df = pd.DataFrame({'Data': datas.strftime('%d/%m/%Y'), 'Dia': [dias_pt[d] for d in datas.day_name()], 'Status': 'Trabalho'})
            
            user_data = next(item for item in st.session_state['db_users'] if item["Nome"] == func_sel)
            
            # Regra Domingo 1x1
            domingos = df[df['Dia'] == 'Domingo'].index.tolist()
            for i, idx in enumerate(domingos):
                if i % 2 == 1:
                    df.loc[idx, 'Status'] = 'Folga'
                    if user_data["Casada"] and (idx + 1) < len(df):
                        df.loc[idx + 1, 'Status'] = 'Folga'

            # Ajuste para Escala 5x2 (Garantir 2 folgas por semana e não passar de 5 dias úteis)
            for i in range(0, len(df), 7):
                semana = df.iloc[i:i+7]
                if len(semana[semana['Status'] == 'Folga']) < 2:
                    possiveis = semana[semana['Status'] == 'Trabalho'].index.tolist()
                    if possiveis:
                        folga_extra = random.choice(possiveis)
                        df.loc[folga_extra, 'Status'] = 'Folga'
            
            st.session_state['historico'][f"{func_sel} - Março"] = df
            st.table(df)

with aba4:
    st.subheader("📜 Histórico")
    if st.session_state['historico']:
        sel = st.selectbox("Selecionar Escala", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][sel]
        st.table(df_h)
        
        from openpyxl.styles import PatternFill, Font
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Escala')
            ws = writer.sheets['Escala']
            amarelo = PatternFill(start_color="FFFF00", fill_type="solid")
            vermelho = PatternFill(start_color="FF0000", fill_type="solid")
            for r in range(2, len(df_h) + 2):
                dia, stt = ws.cell(r, 2).value, ws.cell(r, 3).value
                if dia == 'Domingo' and stt == 'Folga':
                    for c in range(1, 4):
                        ws.cell(r, c).fill = vermelho
                        ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                elif stt == 'Folga':
                    for c in range(1, 4): ws.cell(r, c).fill = amarelo
        st.download_button("📥 Baixar Excel Colorido", out.getvalue(), "escala.xlsx")
