import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment

# 1. Configuração Inicial Única
st.set_page_config(page_title="Escala 5x2 Oficial", layout="wide")

# Inicialização de Memória sem Loops
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'escala_final' not in st.session_state: st.session_state['escala_final'] = None

# Login Direto
if "password_correct" not in st.session_state:
    st.title("🔐 Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📅 Escala e Ajustes", "📥 Baixar"])

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Novo Funcionário")
    nome = st.text_input("Nome")
    h_ent_padrao = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("Salvar Cadastro"):
        if nome:
            st.session_state['db_users'] = [u for u in st.session_state['db_users'] if u['Nome'] != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_ent_padrao.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success(f"{nome} salvo!")

# --- ABA 2: GERAR E AJUSTAR ---
with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Selecione", [u['Nome'] for u in st.session_state['db_users']])
        
        if st.button("✨ GERAR ESCALA"):
            user = next(u for u in st.session_state['db_users'] if u['Nome'] == func_sel)
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Domingos 1x1
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if user['Casada'] and (idx + 1) < 31: df.loc[idx+1, 'Status'] = 'Folga'

            # Folgas Semanais com Trava de Segunda
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not user['Rod_Sab']: pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    if not user['Casada']: # TRAVA CRÍTICA
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    if not (escolha > 0 and df.loc[escolha-1, 'Status'] == 'Folga' and df.loc[escolha-1, 'Dia'] != 'dom'):
                        df.loc[escolha, 'Status'] = 'Folga'
                        atuais += 1

            df['Entrada'] = user['Entrada']
            df['Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['Entrada']]
            st.session_state['escala_final'] = df

    if st.session_state['escala_final'] is not None:
        st.divider()
        st.subheader("Alterar Dia Específico")
        c1, c2, c3 = st.columns([1,1,1])
        dia_mudar = c1.number_input("Dia", 1, 31, step=1)
        hora_nova = c2.time_input("Nova Entrada")
        
        if c3.button("🔄 Aplicar Mudança"):
            idx = dia_mudar - 1
            df_at = st.session_state['escala_final']
            df_at.loc[idx, 'Entrada'] = hora_nova.strftime("%H:%M")
            df_at.loc[idx, 'Saida'] = (datetime.combine(datetime.today(), hora_nova) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            # Regra de 11h: Se sair tarde hoje, empurra amanhã
            if idx < 30 and df_at.loc[idx, 'Status'] == 'Trabalho':
                s_hj = datetime.strptime(df_at.loc[idx, 'Saida'], "%H:%M")
                min_amanha = (s_hj + timedelta(hours=11)).time()
                h_padrao = datetime.strptime(next(u['Entrada'] for u in st.session_state['db_users'] if u['Nome'] == func_sel), "%H:%M").time()
                
                if min_amanha > h_padrao and s_hj.hour > 18:
                    df_at.loc[idx+1, 'Entrada'] = min_amanha.strftime("%H:%M")
                    df_at.loc[idx+1, 'Saida'] = (datetime.combine(datetime.today(), min_amanha) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            st.session_state['escala_final'] = df_at
            st.rerun()

        st.dataframe(st.session_state['escala_final'], use_container_width=True)

# --- ABA 3: DOWNLOAD ---
with aba3:
    if st.session_state['escala_final'] is not None:
        df_exp = st.session_state['escala_final']
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            
            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                ws.cell(2, i+2, df_exp.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
            ws.cell(3, 1, func_sel); ws.cell(4, 1, "Horário")
            for i, row in df_exp.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                c_e = ws.cell(3, col, "Folga" if is_f else row['Entrada'])
                c_s = ws.cell(4, col, "" if is_f else row['Saida'])
                if is_f:
                    c_e.fill = c_s.fill = red if row['Dia'] == 'dom' else yel
            for c in range(1, 33): ws.column_dimensions[ws.cell(1, c).column_letter].width = 9
        st.download_button("📥 Baixar Planilha Excel", output.getvalue(), "escala_corrigida.xlsx")
