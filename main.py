import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Gestor Escala 5x2 Pro", layout="wide")

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

aba1, aba2, aba3 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "📥 3. Baixar Excel"])

with aba1:
    st.subheader("Cadastro")
    nome = st.text_input("Nome")
    h_entrada = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    h_saida = (datetime.combine(datetime.today(), h_entrada) + timedelta(hours=9, minutes=58)).time()
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_entrada.strftime('%H:%M'),
                "Saida": h_saida.strftime('%H:%M'), "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success("Salvo!")

with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Funcionário", [u.get('Nome') for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), {"Casada": False, "Rod_Sab": False})
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # 1. Definir Domingos (1x1)
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == 1: # Domingo de Folga
                    df.loc[d_idx, 'Status'] = 'Folga'
                    # SÓ DÁ FOLGA NA SEGUNDA SE A CAIXINHA ESTIVER MARCADA
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'

            # 2. Distribuir demais folgas
            for sem_start in range(1, 31, 7):
                bloco_fim = min(sem_start + 7, 31)
                folgas_no_dom = len(df.iloc[sem_start:bloco_fim][(df['Dia'] == 'dom') & (df['Status'] == 'Folga')])
                meta_semana = 2 if folgas_no_dom == 0 else 1
                
                # Conta folgas na semana (excluindo o domingo)
                folgas_atuais = len(df.iloc[sem_start:bloco_fim][(df['Status'] == 'Folga') & (df['Dia'] != 'dom')])
                
                tentativas = 0
                while folgas_atuais < meta_semana and tentativas < 50:
                    tentativas += 1
                    pode = df.iloc[sem_start:bloco_fim][df['Status'] == 'Trabalho'].index.tolist()
                    pode = [p for p in pode if df.loc[p, 'Dia'] != 'dom']
                    
                    if not user.get("Rod_Sab"):
                        pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    
                    # REGRA DE OURO: Se não é casada, segunda-feira é PROIBIDA após folga no domingo
                    if not user.get("Casada"):
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and (p > 0 and df.loc[p-1, 'Status'] == 'Folga'))]

                    if not pode: break
                    escolha = random.choice(pode)
                    
                    # Trava anti-dupla (vizinhos)
                    viz_f = False
                    if escolha > 0 and df.loc[escolha-1, 'Status'] == 'Folga': viz_f = True
                    if escolha < 30 and df.loc[escolha+1, 'Status'] == 'Folga': viz_f = True
                    
                    if not viz_f:
                        df.loc[escolha, 'Status'] = 'Folga'
                        folgas_atuais += 1

            st.session_state['historico'][func_sel] = df
            st.table(df)

with aba3:
    if st.session_state['historico']:
        f_nome = st.selectbox("Baixar:", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][f_nome]
        u_info = next((i for i in st.session_state['db_users'] if i.get("Nome") == f_nome), None)
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red, yel = PatternFill(start_color="FF0000", fill_type="solid"), PatternFill(start_color="FFFF00", fill_type="solid")
            white, center = Font(color="FFFFFF", bold=True), Alignment(horizontal="center", vertical="center")

            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, df_h.iloc[i]['Dia']).alignment = center
            ws.cell(3, 1, f_nome); ws.cell(4, 1, "Horário")
            
            for i, row in df_h.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                ent = u_info.get("Entrada", "06:00") if u_info else "06:00"
                sai = u_info.get("Saida", "15:58") if u_info else "15:58"
                c_t = ws.cell(3, col, "Folga" if is_f else ent)
                c_b = ws.cell(4, col, "" if is_f else sai)
                c_t.alignment = c_b.alignment = center
                if is_f:
                    cor = red if row['Dia'] == 'dom' else yel
                    c_t.fill = c_b.fill = cor
                    if row['Dia'] == 'dom': c_t.font = c_b.font = white
            for col in range(1, 33): ws.column_dimensions[ws.cell(1, col).column_letter].width = 7
        st.download_button("📥 Baixar Excel", out.getvalue(), f"escala_{f_nome}.xlsx")
