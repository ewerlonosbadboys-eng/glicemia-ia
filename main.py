import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment

# Configuração de Página - Deve ser a primeira linha
st.set_page_config(page_title="Gestor Escala 5x2 Pro", layout="wide")

# Inicialização de Estado Segura
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'escala_gerada' not in st.session_state: st.session_state['escala_gerada'] = None

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

aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📅 Gerar e Ajustar", "📥 Baixar Excel"])

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Cadastro de Funcionário")
    with st.form("cadastro_form"):
        nome = st.text_input("Nome")
        h_ent = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
        c1, c2 = st.columns(2)
        f_sab = c1.checkbox("Rodízio de Sábado")
        f_cas = c2.checkbox("Folga Casada (Dom+Seg)")
        enviar = st.form_submit_button("Salvar")
        
        if enviar and nome:
            st.session_state['db_users'] = [u for u in st.session_state['db_users'] if u['Nome'] != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_ent.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success("Cadastrado!")

# --- ABA 2: GERAR E AJUSTAR ---
with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Selecione o Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        
        if st.button("✨ GERAR ESCALA MENSAL"):
            user = next(u for u in st.session_state['db_users'] if u['Nome'] == func_sel)
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Lógica de Domingos
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if user['Casada'] and (idx + 1) < 31: df.loc[idx+1, 'Status'] = 'Folga'

            # Folgas Semanais (Trava de Segunda-feira)
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                tem_folga_dom = any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga'))
                meta = 1 if tem_folga_dom else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not user['Rod_Sab']: pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    if not user['Casada']:
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    # Evita folga grudada
                    if not (escolha > 0 and df.loc[escolha-1, 'Status'] == 'Folga' and df.loc[escolha-1, 'Dia'] != 'dom'):
                        df.loc[escolha, 'Status'] = 'Folga'
                        atuais += 1

            df['Entrada'] = user['Entrada']
            df['Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['Entrada']]
            st.session_state['escala_gerada'] = df

    if st.session_state['escala_gerada'] is not None:
        st.write("### Ajuste de Horário Específico")
        c1, c2, c3 = st.columns(3)
        dia_aj = c1.number_input("Dia do Mês", 1, 31)
        nova_e = c2.time_input("Nova Entrada")
        if c3.button("Confirmar Ajuste"):
            idx = dia_aj - 1
            df_e = st.session_state['escala_gerada']
            df_e.loc[idx, 'Entrada'] = nova_e.strftime("%H:%M")
            df_e.loc[idx, 'Saida'] = (datetime.combine(datetime.today(), nova_e) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            # Recalcula Descanso 11h
            if idx < 30 and df_e.loc[idx, 'Status'] == 'Trabalho':
                s_hj = datetime.strptime(df_e.loc[idx, 'Saida'], "%H:%M")
                min_am = s_hj + timedelta(hours=11)
                if min_am.time() > datetime.strptime(next(u['Entrada'] for u in st.session_state['db_users'] if u['Nome'] == func_sel), "%H:%M").time():
                    df_e.loc[idx+1, 'Entrada'] = min_am.strftime("%H:%M")
                    df_e.loc[idx+1, 'Saida'] = (min_am + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            st.session_state['escala_gerada'] = df_e
        
        st.dataframe(st.session_state['escala_gerada'], height=400)

# --- ABA 3: BAIXAR ---
with aba3:
    if st.session_state['escala_gerada'] is not None:
        df_f = st.session_state['escala_gerada']
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            
            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(
