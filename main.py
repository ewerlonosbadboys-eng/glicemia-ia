import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

# Configuração Base
st.set_page_config(page_title="Gestor Escala Profissional", layout="wide")

# Inicialização de Memória Segura
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

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

st.title("📅 Sistema de Escala 5x2")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Cadastro de Funcionário")
    nome = st.text_input("Nome")
    h_ent_padrao = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar Funcionário"):
        if nome:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_ent_padrao.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success(f"✅ {nome} salvo!")

# --- ABA 2: GERAR ESCALA ---
with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Selecione para Gerar", [u.get('Nome') for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA BASE"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), {})
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Regra de Domingos 1x1
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == 1:
                    df.loc[d_idx, 'Status'] = 'Folga'
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'

            # Folgas Semanais (Trava Anti-Folga Dupla das suas fotos)
            for sem in range(0, 31, 7):
                bloco = df.iloc[sem:min(sem+7, 31)]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not user.get("Rod_Sab"): pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    if not user.get("Casada"):
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    df.loc[escolha, 'Status'] = 'Folga'
                    atuais += 1
            
            df['H_Entrada'] = user.get("Entrada", "06:00")
            df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
            st.session_state['historico'][func_sel] = df
            st.table(df)

# --- ABA 3: AJUSTES ---
with aba3:
    if st.session_state['historico']:
        f_edit = st.selectbox("Ajustar horários de:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_edit]
        dia = st.number_input("Dia do Mês", 1, 31)
        novo_h = st.time_input("Nova Entrada")
        if st.button("💾 Aplicar Ajuste"):
            idx = dia - 1
            df_e.loc[idx, 'H_Entrada'] = novo_h.strftime("%H:%M")
            df_e.loc[idx, 'H_Saida'] = (datetime.combine(datetime.today(), novo_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            st.session_state['historico'][f_edit] = df_e
            st.success("Ajustado!")

# --- ABA 4: EXPORTAR ---
with aba4:
    if st.session_state['historico']:
        f_nome = st.selectbox("Escolha para baixar", list(st.session_state['historico'].keys()))
        df_final = st.session_state['historico'][f_nome]
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            center = Alignment(horizontal="center", vertical="center")

            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, df_final.iloc[i]['Dia']).alignment = center
            ws.cell(3, 1, f_nome); ws.cell(4, 1, "Horário")
            for i, row in df_final.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                c_e = ws.cell(3, col, "Folga" if is_f else row['H_Entrada'])
                c_s = ws.cell(4, col, "" if is_f else row['H_Saida'])
                if is_f:
                    c_e.fill = c_s.fill = red if row['Dia'] == 'dom' else yel
            for c in range(1, 33): ws.column_dimensions[ws.cell(1, c).column_letter].width = 9

        st.download_button("📥 Baixar Excel Agora", out.getvalue(), f"escala_{f_nome}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
