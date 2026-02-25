import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random

# Configuração da página
st.set_page_config(page_title="Gestor de Escala 5x2 - Carga e Almoço", layout="wide")

# 1. Login
if "password_correct" not in st.session_state:
    st.title("🔐 Login Administrativo")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Dados incorretos.")
    st.stop()

# 2. Inicialização
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'db_cats' not in st.session_state: st.session_state['db_cats'] = ["Geral"]
if 'historico' not in st.session_state: st.session_state['historico'] = {}

# 3. Abas
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📁 Setores", "📅 Gerar Escala", "📜 Histórico"])

with aba1:
    st.subheader("Cadastro de Funcionário")
    nome = st.text_input("Nome Completo")
    setor = st.selectbox("Setor", st.session_state['db_cats'])
    
    st.write("### Definição de Horário")
    h_entrada = st.time_input("Horário de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    
    # Carga: 08:48 + Almoço: 01:10 = 09:58 de permanência total
    permanencia_total = timedelta(hours=9, minutes=58)
    h_saida_dt = datetime.combine(datetime.today(), h_entrada) + permanencia_total
    h_saida = h_saida_dt.time()
    
    st.success(f"Horário Calculado: Entrada {h_entrada.strftime('%H:%M')} | Almoço 01:10 | Saída {h_saida.strftime('%H:%M')}")

    st.write("### Regras de Escala")
    c1, c2 = st.columns(2)
    f_sabado = c1.checkbox("Rodízio de Sábado")
    f_casada = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar no Banco de Dados"):
        if nome:
            st.session_state['db_users'].append({
                "Nome": nome, "Setor": setor, "Entrada": h_entrada.strftime('%H:%M'),
                "Saida": h_saida.strftime('%H:%M'), "Rodizio_Sab": f_sabado, "Casada": f_casada
            })
            st.success("Funcionário salvo com sucesso!")
    st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerador de Escala Inteligente")
    if st.session_state['db_users']:
        func_nome = st.selectbox("Selecione o Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA 5x2"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'Segunda','Tuesday':'Terça','Wednesday':'Quarta','Thursday':'Quinta','Friday':'Sexta','Saturday':'Sábado','Sunday':'Domingo'}
            
            user = next(i for i in st.session_state['db_users'] if i["Nome"] == func_nome)
            
            df = pd.DataFrame({
                'Data': datas.strftime('%d/%m/%Y'),
                'Dia': [d_pt[d] for d in datas.day_name()],
                'Entrada': user["Entrada"],
                'Saída': user["Saida"],
                'Status': 'Trabalho'
            })
            
            # 1. Regra Domingos 1x1
            dom_idx = df[df['Dia'] == 'Domingo'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if user["Casada"] and (idx + 1) < len(df):
                        df.loc[idx + 1, 'Status'] = 'Folga'

            # 2. Folga Aleatória (Respeita Sábado se não marcado)
            for i in range(0, len(df), 7):
                sem = df.iloc[i:i+7]
                if len(sem[sem['Status'] == 'Folga']) < 2:
                    cond = (sem['Status'] == 'Trabalho')
                    if not user["Rodizio_Sab"]: cond &= (sem['Dia'] != 'Sábado')
                    pode = sem[cond].index.tolist()
                    if pode: df.loc[random.choice(pode), 'Status'] = 'Folga'

            # 3. TRAVA CRÍTICA 5 DIAS (Máximo 5 trabalhados)
            cont = 0
            for i in range(len(df)):
                cont = cont + 1 if df.loc[i, 'Status'] == 'Trabalho' else 0
                if cont > 5:
                    df.loc[i, 'Status'] = 'Folga'
                    cont = 0

            df.loc[df['Status'] == 'Folga', ['Entrada', 'Saída']] = "-"
            st.session_state['historico'][f"{func_nome} - Março"] = df
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
            am, ve = PatternFill(start_color="FFFF00", fill_type="solid"), PatternFill(start_color="FF0000", fill_type="solid")
            for r in range(2, len(df_h) + 2):
                d, s = ws.cell(r, 2).value, ws.cell(r, 5).value
                if d == 'Domingo' and s == 'Folga':
                    for c in range(1, 6):
                        ws.cell(r, c).fill = ve
                        ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                elif s == 'Folga':
                    for c in range(1, 6): ws.cell(r, c).fill = am
        st.download_button("📥 Baixar Excel", out.getvalue(), "escala_completa.xlsx")
