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

# 3. Inicialização de Memória
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.sidebar.button("Sair", on_click=lambda: st.session_state.clear())

# 4. Abas do Aplicativo
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
            st.success("Cadastrado com sucesso!")
    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerar Escala Mensal")
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
            
            # Pega as regras do funcionário selecionado
            dados_f = next(item for item in st.session_state['db_users'] if item["Nome"] == func_sel)
            
            # Regra: Domingo sempre folga
            df.loc[df['Dia'] == 'Domingo', 'Status'] = 'Folga'
            
            # Regra: Segunda-feira só folga se "Casada" estiver marcado
            if dados_f["Casada"]:
                for i in range(len(df)-1):
                    if df.loc[i, 'Dia'] == 'Domingo':
                        df.loc[i+1, 'Status'] = 'Folga'
            
            st.session_state['historico'][f"{func_sel} - Março"] = df
            st.success(f"Escala de {func_sel} gerada!")
            st.table(df)

with aba4:
    st.subheader("📜 Histórico")
    if st.session_state['historico']:
        sel = st.selectbox("Ver Escala Salva", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][sel]
        st.table(df_h)
        
        # --- EXPORTAÇÃO EXCEL COLORIDA ---
        from openpyxl.styles import PatternFill, Font
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Escala')
            ws = writer.sheets['Escala']
            
            cor_amarelo = PatternFill(start_color="FFFF00", fill_type="solid")
            cor_vermelho = PatternFill(start_color="FF0000", fill_type="solid")
            fonte_branca = Font(color="FFFFFF", bold=True)

            for r in range(2, len(df_h) + 2):
                dia_nome = ws.cell(r, 2).value
                status_val = ws.cell(r, 3).value
                
                # Se for Domingo -> Vermelho
                if dia_nome == 'Domingo':
                    for c in range(1, 4):
                        ws.cell(r, c).fill = cor_vermelho
                        ws.cell(r, c).font = fonte_branca
                # Se for Folga (nos outros dias) -> Amarelo
                elif status_val == 'Folga':
                    for c in range(1, 4):
                        ws.cell(r, c).fill = cor_amarelo
        
        st.download_button("📥 Baixar Excel Colorido", out.getvalue(), f"escala_{sel}.xlsx")
