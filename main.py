import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment

st.set_page_config(page_title="Gerador de Escala 5x2", layout="wide")

# Inicialização de memória
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.title("📅 Sistema de Escala")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro")
    nome = st.text_input("Nome do Funcionário")
    ent = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    casada = st.checkbox("Folga Casada (Dom + Seg)")
    if st.button("Salvar"):
        if nome:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({"Nome": nome, "Entrada": ent.strftime('%H:%M'), "Casada": casada})
            st.success(f"{nome} salvo!")

with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Gerar para:", [u.get('Nome') for u in st.session_state['db_users']])
        if st.button("✨ GERAR AGORA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            u_data = next(i for i in st.session_state['db_users'] if i['Nome'] == func_sel)
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Regra de Domingos
            doms = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(doms):
                if i % 2 == 1:
                    df.loc[idx, 'Status'] = 'Folga'
                    if u_data['Casada'] and (idx + 1) < 31: df.loc[idx+1, 'Status'] = 'Folga'

            # Regra de Folgas Semanais (Anti-Amarelo Grudado)
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not u_data['Casada']:
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    if not pode: break
                    df.loc[random.choice(pode), 'Status'] = 'Folga'
                    atuais += 1
            
            df['H_Entrada'] = u_data['Entrada']
            df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
            st.session_state['historico'][func_sel] = df
            st.table(df)

with aba3:
    st.info("Ajustes manuais podem ser feitos aqui.")

with aba4:
    if not st.session_state['historico']:
        st.warning("Gere a escala na Aba 2 primeiro!")
    else:
        f_nome = st.selectbox("Baixar escala de:", list(st.session_state['historico'].keys()))
        df_f = st.session_state['historico'][f_nome]
        
        # Gerar Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala")
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            
            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                ws.cell(2, i+2, df_f.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
            
            ws.cell(3, 1, f_nome); ws.cell(4, 1, "Horário")
            for i, row in df_f.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                c1 = ws.cell(3, col, "Folga" if is_f else row['H_Entrada'])
                c2 = ws.cell(4, col, "" if is_f else row['H_Saida'])
                if is_f:
                    c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
            
            for c in range(1, 33): ws.column_dimensions[ws.cell(1, c).column_letter].width = 10
        
        # O BOTÃO QUE ESTAVA FALTANDO:
        st.download_button(
            label="📥 CLIQUE AQUI PARA BAIXAR EXCEL",
            data=output.getvalue(),
            file_name=f"escala_{f_nome}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
