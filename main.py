import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Gestor Escala Pro", layout="wide")

# 1. Login
if "password_correct" not in st.session_state:
    st.title("🔐 Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

# 2. Cadastro
aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📅 Gerar Escala", "📜 Histórico"])

with aba1:
    st.subheader("Cadastro")
    nome = st.text_input("Nome")
    h_entrada = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    delta = timedelta(hours=9, minutes=58) # 8:48 + 1:10
    h_saida = (datetime.combine(datetime.today(), h_entrada) + delta).time()
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio Sábado")
    f_cas = c2.checkbox("Folga Casada")
    
    if st.button("Salvar"):
        st.session_state['db_users'].append({
            "Nome": nome, "Entrada": h_entrada.strftime('%H:%M'),
            "Saida": h_saida.strftime('%H:%M'), "Rod_Sab": f_sab, "Casada": f_cas
        })
        st.success("Salvo!")

with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            user = next(i for i in st.session_state['db_users'] if i["Nome"] == func_sel)
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Regras de Folga
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1:
                    df.loc[idx, 'Status'] = 'Folga'
                    if user["Casada"] and (idx+1) < 31: df.loc[idx+1, 'Status'] = 'Folga'
            
            # 5x2 e Sábado
            for i in range(0, 31, 7):
                sem = df.iloc[i:i+7]
                if len(sem[sem['Status'] == 'Folga']) < 2:
                    pode = sem[(sem['Status'] == 'Trabalho') & (sem['Dia'] != 'sáb' if not user["Rod_Sab"] else True)].index.tolist()
                    if pode: df.loc[random.choice(pode), 'Status'] = 'Folga'
            
            # Trava 5 dias
            c = 0
            for i in range(31):
                c = c + 1 if df.loc[i, 'Status'] == 'Trabalho' else 0
                if c > 5: df.loc[i, 'Status'] = 'Folga'; c = 0
            
            st.session_state['historico'][func_sel] = df
            st.table(df)

with aba3:
    if st.session_state['historico']:
        f_nome = st.selectbox("Ver Histórico", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][f_nome]
        user_info = next(i for i in st.session_state['db_users'] if i["Nome"] == f_nome)
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            # Criar DataFrame horizontal como solicitado
            headers_dias = [d for d in df_h['Dia']]
            headers_num = [i+1 for i in range(31)]
            
            wb = writer.book
            ws = wb.create_sheet("Escala")
            
            # Estilos
            fill_red = PatternFill(start_color="FF0000", fill_type="solid")
            fill_yel = PatternFill(start_color="FFFF00", fill_type="solid")
            font_white = Font(color="FFFFFF", bold=True)
            center = Alignment(horizontal="center", vertical="center")

            # Escrever Cabeçalhos
            ws.cell(1, 1, "Nome")
            for i, n in enumerate(headers_num): ws.cell(1, i+2, n).alignment = center
            for i, d in enumerate(headers_dias): ws.cell(2, i+2, d).alignment = center
            
            # Escrever Dados do Funcionário
            ws.cell(3, 1, f_nome)
            ws.cell(4, 1, "Horário")
            
            for i, row in df_h.iterrows():
                col = i + 2
                cell_top = ws.cell(3, col, user_info["Entrada"] if row['Status'] == 'Trabalho' else "Folga")
                cell_bot = ws.cell(4, col, user_info["Saida"] if row['Status'] == 'Trabalho' else "")
                
                cell_top.alignment = center
                cell_bot.alignment = center
                
                if row['Dia'] == 'dom' and row['Status'] == 'Folga':
                    cell_top.fill = fill_red
                    cell_top.font = font_white
                    cell_bot.fill = fill_red
                elif row['Status'] == 'Folga':
                    cell_top.fill = fill_yel
                    cell_bot.fill = fill_yel

        st.download_button("📥 Baixar Excel Horizontal Colorido", out.getvalue(), "escala_horizontal.xlsx")
