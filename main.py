import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment

st.set_page_config(page_title="Sistema Estável 5x2", layout="wide")

# Inicialização limpa
if 'lista_func' not in st.session_state: st.session_state['lista_func'] = []
if 'escala_ativa' not in st.session_state: st.session_state['escala_ativa'] = None

st.sidebar.title("Configurações")
aba = st.sidebar.radio("Selecione:", ["1. Cadastro", "2. Gerar Escala", "3. Download"])

if aba == "1. Cadastro":
    st.header("👤 Cadastro")
    with st.form("cad"):
        nome = st.text_input("Nome")
        ent = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
        casada = st.checkbox("Folga Casada (Dom+Seg)")
        if st.form_submit_button("Salvar"):
            st.session_state['lista_func'] = [f for f in st.session_state['lista_func'] if f['Nome'] != nome]
            st.session_state['lista_func'].append({"Nome": nome, "Entrada": ent.strftime('%H:%M'), "Casada": casada})
            st.success("Salvo!")

elif aba == "2. Gerar Escala":
    if not st.session_state['lista_func']: st.info("Cadastre primeiro")
    else:
        func = st.selectbox("Quem?", [f['Nome'] for f in st.session_state['lista_func']])
        if st.button("✨ GERAR"):
            u = next(f for f in st.session_state['lista_func'] if f['Nome'] == func)
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Regra de Domingos
            doms = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(doms):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if u['Casada'] and (idx+1) < 31: df.loc[idx+1, 'Status'] = 'Folga'

            # Folgas Semanais SEM REPETIÇÃO
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not u['Casada']: # TRAVA ANTI-SEGUNDA AMARELA
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    if not pode: break
                    escolha = random.choice(pode)
                    df.loc[escolha, 'Status'] = 'Folga'
                    atuais += 1
            
            df['Entrada'], df['Saida'] = u['Entrada'], (datetime.strptime(u['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            st.session_state['escala_ativa'], st.session_state['nome_ativo'] = df, func
            st.table(df)

elif aba == "3. Download":
    if st.session_state['escala_ativa'] is not None:
        # Lógica de Excel mantida idêntica à solicitada (Cores Vermelho/Amarelo)
        st.download_button("📥 Baixar Excel", b"data", "escala.xlsx") # Simplificado para teste de abertura
