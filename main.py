import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

# 1. Configuração e Segurança
st.set_page_config(page_title="Escala 5x2 Estável", layout="wide")

if "password_correct" not in st.session_state:
    st.title("🔐 Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# Inicialização de dados persistentes
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Cadastro")
    nome = st.text_input("Nome do Funcionário")
    h_entrada_base = st.time_input("Horário de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    
    col1, col2 = st.columns(2)
    f_sabado = col1.checkbox("Trabalha Sábado (Rodízio)")
    f_casada = col2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("Salvar Cadastro"):
        if nome:
            # Atualiza ou Adiciona
            st.session_state['db_users'] = [u for u in st.session_state['db_users'] if u['Nome'] != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_entrada_base.strftime('%H:%M'),
                "Rod_Sab": f_sabado, "Casada": f_casada
            })
            st.success("Cadastro realizado!")

# --- ABA 2: GERADOR DE ESCALA ---
with aba2:
    if st.session_state['db_users']:
        func_nome = st.selectbox("Selecione o Funcionário", [u['Nome'] for u in st.session_state['db_users']])
        if st.button("✨ GERAR NOVA ESCALA"):
            user = next(u for u in st.session_state['db_users'] if u['Nome'] == func_nome)
            datas = pd.date_range(start='2026-03-01', periods=31)
            dias_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            df = pd.DataFrame({'Data': datas, 'Dia': [dias_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Marcar Domingos (1x1)
            domingos = df[df['Dia'] == 'dom'].index.tolist()
            for i, idx in enumerate(domingos):
                if i % 2 == 1: # Folga no Domingo
                    df.loc[idx, 'Status'] = 'Folga'
                    if user['Casada'] and (idx + 1) < 31:
                        df.loc[idx+1, 'Status'] = 'Folga'

            # Gerar Folgas Semanais
            for semana in range(0, 31, 7):
                bloco = df.iloc[semana:min(semana+7, 31)]
                folgas_dom = len(bloco[(bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')])
                meta_semanal = 1 if folgas_dom > 0 else 2
                
                folgas_colocadas = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                tentativas = 0
                while folgas_colocadas < meta_semanal and tentativas < 20:
                    tentativas += 1
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    
                    if not user['Rod_Sab']:
                        pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    
                    # REGRA: Proibido Segunda se Domingo foi Folga (e não é casada)
                    if not user['Casada']:
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and p > 0 and df.loc[p-1, 'Status'] == 'Folga')]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    
                    # Evita folga grudada na semana
                    vizinho_folga = (escolha > 0 and df.loc[escolha-1, 'Status'] == 'Folga' and df.loc[escolha-1, 'Dia'] != 'dom')
                    if not vizinho_folga:
                        df.loc[escolha, 'Status'] = 'Folga'
                        folgas_colocadas += 1

            df['Entrada'] = user['Entrada']
            df['Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['Entrada']]
            st.session_state['historico'][func_nome] = df
            st.dataframe(df, use_container_width=True)

# --- ABA 3: AJUSTES MANUAIS ---
with aba3:
    if st.session_state['historico']:
        f_edit = st.selectbox("Editar Escala de:", list(st.session_state['historico'].keys()))
        df_edit = st.session_state['historico'][f_edit]
        u_info = next(u for u in st.session_state['db_users'] if u['Nome'] == f_edit)
        
        c1, c2, c3 = st.columns(3)
        dia_sel = c1.number_input("Dia", 1, 31, step=1)
        nova_ent = c2.time_input("Nova Entrada")
        
        if c3.button("Aplicar Horário"):
            idx = dia_sel - 1
            df_edit.loc[idx, 'Entrada'] = nova_ent.strftime("%H:%M")
            df_edit.loc[idx, 'Saida'] = (datetime.combine(datetime.today(), nova_ent) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            # Recalcula Descanso de 11h para o dia seguinte
            if idx < 30 and df_edit.loc[idx, 'Status'] == 'Trabalho':
                saida_hj = datetime.strptime(df_edit.loc[idx, 'Saida'], "%H:%M")
                minimo_amanha = saida_hj + timedelta(hours=11)
                ent_padrao = datetime.strptime(u_info['Entrada'], "%H:%M")
                
                if minimo_amanha.time() > ent_padrao.time() and minimo_amanha.hour < 21:
                    df_edit.loc[idx+1, 'Entrada'] = minimo_amanha.strftime("%H:%M")
                    df_edit.loc[idx+1, 'Saida'] = (minimo_amanha + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            st.session_state['historico'][f_edit] = df_edit
            st.success("Horário Atualizado!")
            st.dataframe(df_edit)

# --- ABA 4: DOWNLOAD ---
with aba4:
    if st.session_state['historico']:
        f_down = st.selectbox("Baixar Escala:", list(st.session_state['historico'].keys()))
        df_fin = st.session_state['historico'][f_down]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            
            # Cores
            v_red = PatternFill(start_color="FF0000", fill_type="solid")
            v_yel = PatternFill(start_color="FFFF00", fill_type="solid")
            alinhamento = Alignment(horizontal="center")

            # Cabeçalho Horizontal
            ws.cell(1, 1, "Nome")
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = alinhamento
                ws.cell(2, i+2, df_fin.iloc[i]['Dia']).alignment = alinhamento
            
            ws.cell(3, 1, f_down)
            ws.cell(4, 1, "Horário")
            
            for i, row in df_fin.iterrows():
                col = i + 2
                folga = (row['Status'] == 'Folga')
                cell_ent = ws.cell(3, col, "Folga" if folga else row['Entrada'])
                cell_sai = ws.cell(4, col, "" if folga else row['Saida'])
                cell_ent.alignment = cell_sai.alignment = alinhamento
                
                if folga:
                    cor = v_red if row['Dia'] == 'dom' else v_yel
                    cell_ent.fill = cell_sai.fill = cor
            
            for c in range(1, 33): ws.column_dimensions[ws.cell(1, c).column_letter].width = 8
            
        st.download_button("📥 Baixar Planilha Excel", output.getvalue(), f"escala_{f_down}.xlsx")
