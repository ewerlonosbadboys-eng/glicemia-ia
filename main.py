import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment

# 1. Configuração de Página
st.set_page_config(page_title="Sistema de Escala 2026", layout="wide")

# Inicialização de Memória Estática
if 'lista_func' not in st.session_state: st.session_state['lista_func'] = []
if 'escala_ativa' not in st.session_state: st.session_state['escala_ativa'] = None

# Interface Simplificada
st.title("🚀 Gerador de Escala 5x2")
st.write("Versão de Alta Performance (Anti-Travamento)")

# Menu Lateral Simples
aba = st.sidebar.radio("Navegação", ["1. Cadastro", "2. Gerar Escala", "3. Baixar Excel"])

# --- ABA 1: CADASTRO ---
if aba == "1. Cadastro":
    st.subheader("👤 Cadastrar Funcionário")
    nome = st.text_input("Nome")
    ent = st.time_input("Horário de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    
    col1, col2 = st.columns(2)
    sab = col1.checkbox("Trabalha Sábado (Rodízio)")
    cas = col2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("Salvar Dados"):
        if nome:
            st.session_state['lista_func'] = [f for f in st.session_state['lista_func'] if f['Nome'] != nome]
            st.session_state['lista_func'].append({
                "Nome": nome, "Entrada": ent.strftime('%H:%M'),
                "Sab": sab, "Casada": cas
            })
            st.success(f"✅ {nome} cadastrado com sucesso!")

# --- ABA 2: GERAR ESCALA ---
elif aba == "2. Gerar Escala":
    if not st.session_state['lista_func']:
        st.warning("⚠️ Cadastre um funcionário primeiro!")
    else:
        func = st.selectbox("Selecione o Funcionário", [f['Nome'] for f in st.session_state['lista_func']])
        
        if st.button("✨ GERAR ESCALA COMPLETA"):
            user = next(f for f in st.session_state['lista_func'] if f['Nome'] == func)
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Lógica de Domingos (1x1)
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(dom_idx):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if user['Casada'] and (idx + 1) < 31: df.loc[idx+1, 'Status'] = 'Folga'

            # Lógica de Folgas Semanais
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not user['Sab']: pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    
                    # TRAVA DE SEGUNDA-FEIRA: Não folga se domingo foi folga (e não for casada)
                    if not user['Casada']:
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    df.loc[escolha, 'Status'] = 'Folga'
                    atuais += 1

            df['Entrada'] = user['Entrada']
            df['Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['Entrada']]
            st.session_state['escala_ativa'] = df
            st.session_state['func_nome'] = func
            st.table(df)

# --- ABA 3: BAIXAR EXCEL ---
elif aba == "3. Baixar Excel":
    if st.session_state['escala_ativa'] is None:
        st.info("Gere a escala na aba anterior primeiro.")
    else:
        df_f = st.session_state['escala_ativa']
        nome_f = st.session_state['func_nome']
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            center = Alignment(horizontal="center")

            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, df_f.iloc[i]['Dia']).alignment = center
            
            ws.cell(3, 1, nome_f); ws.cell(4, 1, "Horário")
            for i, row in df_f.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                c_e = ws.cell(3, col, "Folga" if is_f else row['Entrada'])
                c_s = ws.cell(4, col, "" if is_f else row['Saida'])
                if is_f:
                    c_e.fill = c_s.fill = red if row['Dia'] == 'dom' else yel
            
            for c in range(1, 33): ws.column_dimensions[ws.cell(1, c).column_letter].width = 9
            
        st.download_button("📥 Baixar Arquivo Excel", output.getvalue(), f"escala_{nome_f}.xlsx")
