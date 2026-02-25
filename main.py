import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Sistema de Login
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

# 3. Inicialização
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
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio Sábado")
    f_cas = c2.checkbox("Folga Casada (Domingo + Segunda)")
    
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'].append({
                "Nome": nome, "Setor": setor, "Sábado": f_sab, "Casada": f_cas
            })
            st.success("Cadastrado!")
    st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerar Escala")
    if st.session_state['db_users']:
        funcionario = st.selectbox("Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            # Tradução manual para evitar inglês
            dias_map = {'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 
                        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
            
            df = pd.DataFrame({
                'Data': datas.strftime('%d/%m/%Y'),
                'Dia': [dias_map[d] for d in datas.day_name()],
                'Status': 'Trabalho'
            })
            
            # Busca dados do funcionário
            dados_f = next(item for item in st.session_state['db_users'] if item["Nome"] == funcionario)
            
            # Regras de Folga
            df.loc[df['Dia'] == 'Domingo', 'Status'] = 'Folga'
            
            # SÓ APLICA FOLGA CONSECUTIVA SE ESTIVER MARCADO NO CADASTRO
            if dados_f["Casada"]:
                for i in range(len(df)-1):
                    if df.loc[i, 'Dia'] == 'Domingo':
                        df.loc[i+1, 'Status'] = 'Folga'
            
            st.session_state['historico'][f"{funcionario} - Março"] = df
            st.table(df)

with aba4:
    st.subheader("📜 Histórico")
    if st.session_state['historico']:
        sel = st.selectbox("Ver Escala", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][sel]
        st.table(df_h)
        
        # Exportação Excel Colorida
        from openpyxl.styles import PatternFill, Font
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Escala')
            ws = writer.sheets['Escala']
            cf = PatternFill(start_color="FFFF00", fill_type="solid") # Amarelo
            cd = PatternFill(start_color="FF0000", fill_type="solid") # Vermelho
            for r in range(2, len(df_h) + 2):
                dia = ws.cell(r, 2).value
                stt = ws.cell(r, 3).value
                if dia == 'Domingo':
                    for c in range(1, 4):
                        ws.cell(r, c).fill = cd
                        ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                elif stt == 'Folga':
                    for c in range(1, 4): ws.cell(r, c).fill = cf
        st.download_button("📥 Baixar Excel", out.getvalue(), "escala.xlsx")
