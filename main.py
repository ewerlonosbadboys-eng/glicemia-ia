import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Gestor Escala 5x2 Pro", layout="wide")

# 1. Login Simples
if "password_correct" not in st.session_state:
    st.title("🔐 Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# Inicialização de memória (Corrigido para não travar)
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro de Funcionário")
    nome = st.text_input("Nome")
    h_ent = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'] = [u for u in st.session_state['db_users'] if u['Nome'] != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_ent.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success("Salvo!")

with aba2:
    if st.session_state['db_users']:
        func = st.selectbox("Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            u_info = next(u for u in st.session_state['db_users'] if u['Nome'] == func)
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # 1. Domingos 1x1
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1:
                    df.loc[idx, 'Status'] = 'Folga'
                    if u_info['Casada'] and (idx + 1) < 31:
                        df.loc[idx+1, 'Status'] = 'Folga'

            # 2. Folgas da Semana (Regras Rígidas)
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                tem_dom_folga = any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga'))
                meta = 1 if tem_dom_folga else 2
                
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                while atuais < meta:
                    pode = bloco[bloco['Status'] == 'Trabalho'].index.tolist()
                    pode = [p for p in pode if df.loc[p, 'Dia'] != 'dom']
                    if not u_info['Rod_Sab']: pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    
                    # TRAVA: Segunda proibida se Domingo foi folga (e não é casada)
                    if not u_info['Casada']:
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    # Evita folga grudada na semana
                    if not ((escolha > 0 and df.loc[escolha-1, 'Status'] == 'Folga' and df.loc[escolha-1, 'Dia'] != 'dom')):
                        df.loc[escolha, 'Status'] = 'Folga'
                        atuais += 1
            
            df['H_Entrada'] = u_info['Entrada']
            df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
            st.session_state['historico'][func] = df
            st.table(df)

with aba3:
    if st.session_state['historico']:
        f_edit = st.selectbox("Ajustar dia de:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_edit]
        u_dat = next(u for u in st.session_state['db_users'] if u['Nome'] == f_edit)
        
        c1, c2 = st.columns(2)
        d_aj = c1.number_input("Dia", 1, 31)
        n_h = c2.time_input("Novo Horário")
        
        if st.button("💾 Aplicar"):
            idx = d_aj - 1
            df_e.loc[idx, 'H_Entrada'] = n_h.strftime("%H:%M")
            df_e.loc[idx, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            # Recalcula descansos de 11h para os dias seguintes automaticamente
            for i in range(idx + 1, 31):
                saida_ant = datetime.strptime(df_e.loc[i-1, 'H_Saida'], "%H:%M")
                h_base = datetime.strptime(u_dat['Entrada'], "%H:%M")
                if df_e.loc[i-1, 'Status'] == 'Trabalho':
                    minimo = saida_ant + timedelta(hours=11)
                    if minimo.time() > h_base.time() and minimo.hour < 20:
                        df_e.loc[i, 'H_Entrada'] = minimo.strftime("%H:%M")
                        df_e.loc[i, 'H_Saida'] = (minimo + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            st.session_state['historico'][f_edit] = df_e
            st.rerun()

with aba4:
    if st.session_state['historico']:
        f_nome = st.selectbox("Baixar:", list(st.session_state['historico'].keys()))
        df_final = st.session_state['historico'][f_nome]
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            
            ws.cell(1,1,"Nome")
            for i in range(31):
                ws.cell(1,i+2,i+1).alignment = Alignment(horizontal="center")
                ws.cell(2,i+2,df_final.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
            ws.cell(3,1,f_nome); ws.cell(4,1,"Horário")
            for i, row in df_final.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                ws.cell(3, col, "Folga" if is_f else row['H_Entrada']).alignment = Alignment(horizontal="center")
                ws.cell(4, col, "" if is_f else row['H_Saida']).alignment = Alignment(horizontal="center")
                if is_f:
                    ws.cell(3,col).fill = red if row['Dia'] == 'dom' else yel
                    ws.cell(4,col).fill = red if row['Dia'] == 'dom' else yel
            for col in range(1, 33): ws.column_dimensions[ws.cell(1, col).column_letter].width = 8
        st.download_button("📥 Baixar Planilha", out.getvalue(), f"escala_{f_nome}.xlsx")
