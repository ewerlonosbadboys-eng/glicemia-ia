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
    st.info(f"Saída: {h_saida.strftime('%H:%M')}")
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_entrada.strftime('%H:%M'),
                "Saida": h_saida.strftime('%H:%M'), "Rodizio_Sab": f_sab, "Casada": f_cas
            })
            st.success("Salvo!")

with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Funcionário", [u.get('Nome') for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), None)
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # 1. Domingo 1x1
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for idx, d_idx in enumerate(dom_idx):
                if idx % 2 == 1:
                    df.loc[d_idx, 'Status'] = 'Folga'
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'

            # 2. Folgas Semanais SEM DUPLA
            for i in range(0, 31, 7):
                sem = df.iloc[i:i+7]
                while len(df.iloc[i:i+7][df.iloc[i:i+7]['Status'] == 'Folga']) < 2:
                    cond = (df.iloc[i:i+7]['Status'] == 'Trabalho')
                    if not user.get("Rodizio_Sab"): cond &= (df.iloc[i:i+7]['Dia'] != 'sáb')
                    
                    pode_idx = df.iloc[i:i+7][cond].index.tolist()
                    if not pode_idx: break
                    
                    escolha = random.choice(pode_idx)
                    
                    # TRAVA ANTI-DUPLA: Verifica se o vizinho já é folga (exceto Dom+Seg casado)
                    vizinhos = []
                    if escolha > 0: vizinhos.append(df.loc[escolha-1, 'Status'])
                    if escolha < 30: vizinhos.append(df.loc[escolha+1, 'Status'])
                    
                    if 'Folga' not in vizinhos:
                        df.loc[escolha, 'Status'] = 'Folga'
                    else:
                        # Se caiu perto de outra folga, tenta outro dia pra não ficar grudado
                        pode_idx.remove(escolha)
                        if not pode_idx: break 

            # 3. Trava Final 5 dias
            cont = 0
            for i in range(31):
                cont = cont + 1 if df.loc[i, 'Status'] == 'Trabalho' else 0
                if cont > 5:
                    df.loc[i, 'Status'] = 'Folga'
                    cont = 0

            st.session_state['historico'][func_sel] = df
            st.table(df)

with aba3:
    if st.session_state['historico']:
        f_nome = st.selectbox("Escala para Baixar", list(st.session_state['historico'].keys()))
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
                c_t = ws.cell(3, col, "Folga" if is_f else u_info.get("Entrada"))
                c_b = ws.cell(4, col, "" if is_f else u_info.get("Saida"))
                c_t.alignment = c_b.alignment = center
                if is_f:
                    cor = red if row['Dia'] == 'dom' else yel
                    c_t.fill = c_b.fill = cor
                    if row['Dia'] == 'dom': c_t.font = c_b.font = white
            for col in range(1, 33): ws.column_dimensions[ws.cell(1, col).column_letter].width = 7
        st.download_button("📥 Baixar Excel", out.getvalue(), f"escala_{f_nome}.xlsx")
