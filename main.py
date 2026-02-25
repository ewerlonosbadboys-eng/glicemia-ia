import streamlit as st
import pandas as pd
from datetime import datetime
import io
import random

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Login (admin / 123)
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

# 3. Inicialização de Memória
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.sidebar.button("Sair", on_click=lambda: st.session_state.clear())

# 4. Abas
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Setores", "📅 Gerar Escala", "📜 Histórico"])

with aba2:
    st.subheader("Setores")
    nova_cat = st.text_input("Nome do Setor")
    if st.button("Salvar Setor"):
        if nova_cat:
            st.session_state['db_cats'].append(nova_cat)
            st.success("Setor salvo!")

with aba1:
    st.subheader("Cadastro de Equipe")
    nome = st.text_input("Nome do Funcionário")
    setor = st.selectbox("Setor", st.session_state['db_cats'])
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'].append({"Nome": nome, "Setor": setor})
            st.success("Cadastrado!")
    st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerar Escala (Domingo 1x1 + Folga Aleatória)")
    if st.session_state['db_users']:
        func_sel = st.selectbox("Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            dias_pt = {'Monday':'Segunda','Tuesday':'Terça','Wednesday':'Quarta','Thursday':'Quinta','Friday':'Sexta','Saturday':'Sábado','Sunday':'Domingo'}
            
            df = pd.DataFrame({
                'Data': datas.strftime('%d/%m/%Y'),
                'Dia': [dias_pt[d] for d in datas.day_name()],
                'Status': 'Trabalho'
            })
            
            # --- REGRA DE DOMINGOS (1x1) ---
            domingos_indices = df[df['Dia'] == 'Domingo'].index.tolist()
            for idx, dom_idx in enumerate(domingos_indices):
                if idx % 2 == 1: # Folga um domingo sim, outro não
                    df.loc[dom_idx, 'Status'] = 'Folga'
            
            # --- REGRA DE FOLGA ALEATÓRIA (Para manter 5x2) ---
            # Cada semana precisa de 2 folgas. Se o domingo é trabalho, sorteia 2 na semana.
            # Se o domingo é folga, sorteia mais 1 na semana.
            for i in range(0, len(df), 7):
                semana = df.iloc[i:i+7]
                folgas_atuais = len(semana[semana['Status'] == 'Folga'])
                folgas_necessarias = 2 - folgas_atuais
                
                if folgas_necessarias > 0:
                    indices_possiveis = semana[semana['Status'] == 'Trabalho'].index.tolist()
                    if indices_possiveis:
                        sorteados = random.sample(indices_possiveis, min(folgas_necessarias, len(indices_possiveis)))
                        for s in sorteados:
                            df.loc[s, 'Status'] = 'Folga'
            
            st.session_state['historico'][f"{func_sel} - Março"] = df
            st.success(f"Escala de {func_sel} gerada!")
            st.table(df)

with aba4:
    st.subheader("📜 Histórico")
    if st.session_state['historico']:
        sel = st.selectbox("Ver Escala", list(st.session_state['historico'].keys()))
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
                dia = ws.cell(r, 2).value
                stt = ws.cell(r, 3).value
                if dia == 'Domingo' and stt == 'Folga':
                    for c in range(1, 4):
                        ws.cell(r, c).fill = vermelho
                        ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                elif stt == 'Folga':
                    for c in range(1, 4): ws.cell(r, c).fill = amarelo
        st.download_button("📥 Baixar Excel", out.getvalue(), "escala.xlsx")
