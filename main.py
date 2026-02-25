import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random

# Configuração da página
st.set_page_config(page_title="Gestor de Escala 5x2 - Horários", layout="wide")

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
    st.subheader("Cadastro de Equipe e Horário")
    nome = st.text_input("Nome")
    setor = st.selectbox("Setor", st.session_state['db_cats'])
    
    st.write("### Horário de Trabalho (Carga 08:48)")
    h_entrada = st.time_input("Horário de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    
    # Cálculo da Saída: Entrada + 8h 48min
    delta = timedelta(hours=8, minutes=48)
    temp_datetime = datetime.combine(datetime.today(), h_entrada) + delta
    h_saida = temp_datetime.time()
    
    st.info(f"Cálculo Automático: Entrada {h_entrada.strftime('%H:%M')} -> Saída {h_saida.strftime('%H:%M')}")

    st.write("### Regras")
    c1, c2 = st.columns(2)
    f_sabado = c1.checkbox("Rodízio de Sábado")
    f_casada = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar Funcionário"):
        if nome:
            st.session_state['db_users'].append({
                "Nome": nome, "Setor": setor, "Entrada": h_entrada.strftime('%H:%M'),
                "Saida": h_saida.strftime('%H:%M'), "Rodizio_Sab": f_sabado, "Casada": f_casada
            })
            st.success("Salvo!")
    st.table(pd.DataFrame(st.session_state['db_users']))

with aba3:
    st.subheader("Gerador de Escala")
    if st.session_state['db_users']:
        func_nome = st.selectbox("Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA COM HORÁRIOS"):
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
            
            # --- REGRA DOMINGOS 1x1 ---
            dom_idx = df[df['Dia'] == 'Domingo'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if user["Casada"] and (idx + 1) < len(df):
                        df.loc[idx + 1, 'Status'] = 'Folga'

            # --- REGRA DA FOLGA ALEATÓRIA (RESPEITANDO SÁBADO) ---
            for i in range(0, len(df), 7):
                sem = df.iloc[i:i+7]
                if len(sem[sem['Status'] == 'Folga']) < 2:
                    condicao = (sem['Status'] == 'Trabalho')
                    if not user["Rodizio_Sab"]:
                        condicao &= (sem['Dia'] != 'Sábado')
                    
                    pode_folga = sem[condicao].index.tolist()
                    if pode_folga:
                        df.loc[random.choice(pode_folga), 'Status'] = 'Folga'

            # --- TRAVA 5 DIAS (NÃO PODE PASSAR DE 5) ---
            cont = 0
            for i in range(len(df)):
                cont = cont + 1 if df.loc[i, 'Status'] == 'Trabalho' else 0
                if cont > 5:
                    df.loc[i, 'Status'] = 'Folga'
                    cont = 0

            # Limpar horários onde é Folga
            df.loc[df['Status'] == 'Folga', ['Entrada', 'Saída']] = "-"
            
            st.session_state['historico'][f"{func_nome} - Março"] = df
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
                d, s = ws.cell(r, 2).value, ws.cell(r, 5).value # Status na coluna 5 agora
                if d == 'Domingo' and s == 'Folga':
                    for c in range(1, 6):
                        ws.cell(r, c).fill = ve
                        ws.cell(r, c).font = Font(color="FFFFFF", bold=True)
                elif s == 'Folga':
                    for c in range(1, 6): ws.cell(r, c).fill = am
        st.download_button("📥 Baixar Excel com Horários", out.getvalue(), "escala_horarios.xlsx")
