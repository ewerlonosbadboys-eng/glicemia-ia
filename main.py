import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Sistema de Login
if "password_correct" not in st.session_state:
    st.title("🔐 Acesso Restrito")
    u = st.text_input("Usuário", key="login_user")
    p = st.text_input("Senha", type="password", key="login_pass")
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
st.title("🚀 Gerenciador de Escala Inteligente")

# 4. Abas do Aplicativo
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala", "📜 Histórico"])

with aba2:
    st.subheader("Configurar Setores")
    nova_cat = st.text_input("Nome do novo setor")
    if st.button("Adicionar Setor"):
        if nova_cat and nova_cat not in st.session_state['db_cats']:
            st.session_state['db_cats'].append(nova_cat)
            st.success("Setor adicionado!")

with aba1:
    st.subheader("Cadastro de Equipe")
    nome = st.text_input("Nome Completo")
    setor = st.selectbox("Setor", st.session_state['db_cats'])
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio Sábados")
    f_cas = c2.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar Funcionário"):
        if nome:
            st.session_state['db_users'].append({"Nome": nome, "Setor": setor, "Sáb": f_sab, "Casada": f_cas})
            st.success(f"{nome} cadastrado!")
    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerar Escala")
    if not st.session_state['db_users']:
        st.info("Cadastre alguém primeiro.")
    else:
        set_sel = st.selectbox("Setor para Gerar", st.session_state['db_cats'])
        mes_sel = st.selectbox("Mês", ["Março 2026", "Abril 2026"])
        if st.button("✨ GERAR E SALVAR"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            df = pd.DataFrame({'Data': datas.strftime('%d/%m/%Y'), 'Dia': datas.day_name(), 'Status': 'Trabalho'})
            df.loc[df['Dia'] == 'Sunday', 'Status'] = 'Folga'
            # Lógica de Folga Casada
            for i in range(len(df)-1):
                if df.loc[i, 'Dia'] == 'Sunday': df.loc[i+1, 'Status'] = 'Folga'
            st.session_state['historico'][f"{set_sel} - {mes_sel}"] = df
            st.success("Escala salva no histórico!")
            st.table(df)

with aba4:
    st.subheader("📜 Histórico")
    if not st.session_state['historico']:
        st.info("Sem escalas salvas.")
    else:
        sel = st.selectbox("Escolha uma Escala", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][sel]
        st.table(df_h)
        try:
            from openpyxl.styles import PatternFill, Font
            d_pt = {'Monday':'Segunda','Tuesday':'Terça','Wednesday':'Quarta','Thursday':'Quinta','Friday':'Sexta','Saturday':'Sábado','Sunday':'Domingo'}
            df_ex = df_h.copy()
            df_ex['Dia'] = df_ex['Dia'].map(d_pt)
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df_ex.to_excel(writer, index=False, sheet_name='Escala')
                ws = writer.sheets['Escala']
                cf = PatternFill(start_color="FFFF00", fill_type="solid") # Amarelo
                cd = PatternFill(start_color="FF0000", fill_type="solid") # Vermelho
                for r in range(2, len(df_ex) + 2):
                    dia = ws.cell(r, 2).value
                    stt = ws.cell(r, 3).value
                    if dia == 'Domingo':
                        for c in range(1, 4):
                            ws.cell(r, c).fill = cd
                            ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                    elif stt == 'Folga':
                        for c in range(1, 4): ws.cell(r, c).fill = cf
            st.download_button("📥 Baixar Excel Colorido", out.getvalue(), "escala.xlsx")
        except Exception as e:
            st.error(f"Erro: {e}")
