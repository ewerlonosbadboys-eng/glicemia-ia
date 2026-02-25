import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment

# 1. Configuração de Página (Obrigatório ser a primeira linha)
st.set_page_config(page_title="Escala 5x2 Fixa", layout="wide")

# Limpeza forçada de estados que causam loop
if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

# Login Simples e Estático
if not st.session_state['password_correct']:
    st.title("🔐 Acesso")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if senha == "123":
            st.session_state['password_correct'] = True
            st.rerun()
    st.stop()

# Inicialização Manual de Dados
if 'lista_func' not in st.session_state: st.session_state['lista_func'] = []
if 'escala_ativa' not in st.session_state: st.session_state['escala_ativa'] = None

# Interface
st.title("📅 Gestor de Escala Profissional")
menu = ["Cadastro", "Gerar Escala", "Ajustar e Baixar"]
escolha = st.sidebar.selectbox("Menu", menu)

# --- CADASTRO ---
if escolha == "Cadastro":
    st.subheader("👥 Cadastro de Funcionário")
    nome = st.text_input("Nome completo")
    h_entrada = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    sab = c1.checkbox("Rodízio de Sábado")
    cas = c2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("💾 Salvar Funcionário"):
        if nome:
            st.session_state['lista_func'] = [f for f in st.session_state['lista_func'] if f['Nome'] != nome]
            st.session_state['lista_func'].append({
                "Nome": nome, "Entrada": h_entrada.strftime('%H:%M'),
                "Sab": sab, "Casada": cas
            })
            st.success(f"Funcionário {nome} cadastrado!")

# --- GERADOR ---
elif escolha == "Gerar Escala":
    if not st.session_state['lista_func']:
        st.warning("Cadastre alguém primeiro!")
    else:
        func = st.selectbox("Escolha o Funcionário", [f['Nome'] for f in st.session_state['lista_func']])
        if st.button("✨ GERAR ESCALA DE MARÇO"):
            f_data = next(f for f in st.session_state['lista_func'] if f['Nome'] == func)
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Regra de Domingos 1x1
            doms = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(doms):
                if i % 2 == 1: 
                    df.loc[idx, 'Status'] = 'Folga'
                    if f_data['Casada'] and (idx + 1) < 31: df.loc[idx+1, 'Status'] = 'Folga'

            # Folgas da Semana (Sem grudar se não for casada)
            for s in range(0, 31, 7):
                bloco = df.iloc[s:s+7]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    if not f_data['Sab']: pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    if not f_data['Casada']:
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha_f = random.choice(pode)
                    if not (escolha_f > 0 and df.loc[escolha_f-1, 'Status'] == 'Folga' and df.loc[escolha_f-1, 'Dia'] != 'dom'):
                        df.loc[escolha_f, 'Status'] = 'Folga'
                        atuais += 1

            df['Entrada'] = f_data['Entrada']
            df['Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['Entrada']]
            st.session_state['escala_ativa'] = df
            st.session_state['nome_ativo'] = func
            st.success("Escala gerada! Vá para a aba 'Ajustar e Baixar'.")

# --- AJUSTES E DOWNLOAD ---
elif escolha == "Ajustar e Baixar":
    if st.session_state['escala_ativa'] is None:
        st.info("Gere a escala na aba anterior.")
    else:
        df = st.session_state['escala_ativa']
        st.write(f"### Escala de {st.session_state['nome_ativo']}")
        
        with st.expander("🛠️ Mudar Horário de um Dia"):
            d_aj = st.number_input("Dia do Mês", 1, 31)
            h_aj = st.time_input("Novo Horário")
            if st.button("Confirmar Alteração"):
                idx = d_aj - 1
                df.loc[idx, 'Entrada'] = h_aj.strftime("%H:%M")
                df.loc[idx, 'Saida'] = (datetime.combine(datetime.today(), h_aj) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                
                # Recalcula 11h para o dia seguinte se for tarde
                if idx < 30 and h_aj.hour >= 12:
                    s_hj = datetime.strptime(df.loc[idx, 'Saida'], "%H:%M")
                    min_am = (s_hj + timedelta(hours=11)).strftime("%H:%M")
                    df.loc[idx+1, 'Entrada'] = min_am
                    df.loc[idx+1, 'Saida'] = (datetime.strptime(min_am, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                
                st.session_state['escala_ativa'] = df
                st.rerun()

        st.dataframe(df, use_container_width=True)

        # Exportação para Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red = PatternFill(start_color="FF0000", fill_type="solid")
            yel = PatternFill(start_color="FFFF00", fill_type="solid")
            
            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                ws.cell(2, i+2, df.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
            ws.cell(3, 1, st.session_state['nome_ativo']); ws.cell(4, 1, "Horário")
            for i, row in df.iterrows():
                col = i + 2
                folga = (row['Status'] == 'Folga')
                c_e = ws.cell(3, col, "Folga" if folga else row['Entrada'])
                c_s = ws.cell(4, col, "" if folga else row['Saida'])
                if folga:
                    c_e.fill = c_s.fill = red if row['Dia'] == 'dom' else yel
            for c in range(1, 33): ws.column_dimensions[ws.cell(1, c).column_letter].width = 9
        
        st.download_button("📥 Baixar Excel", output.getvalue(), "escala.xlsx")
