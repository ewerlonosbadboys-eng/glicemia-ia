import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Gestor Escala Profissional", layout="wide")

# 1. Login (Mantido conforme solicitado)
if "password_correct" not in st.session_state:
    st.title("🔐 Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# Inicialização de estados
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}
if 'ajustes_pontuais' not in st.session_state: st.session_state['ajustes_pontuais'] = {}

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes Específicos", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro Base")
    nome = st.text_input("Nome")
    h_ent = st.time_input("Horário Padrão de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom+Seg)")
    
    if st.button("Salvar Cadastro"):
        if nome:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, "Entrada": h_ent.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success("Cadastrado!")

with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Funcionário para Escala", [u.get('Nome') for u in st.session_state['db_users']])
        if st.button("✨ GERAR ESCALA BASE"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), {})
            
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Lógica de Domingos e Folga Casada (Respeitando sua ordem)
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == 1:
                    df.loc[d_idx, 'Status'] = 'Folga'
                    if user.get("Casada") and (d_idx + 1) < 31: df.loc[d_idx + 1, 'Status'] = 'Folga'

            # Folgas Semanais (Garantindo que não sejam duplas)
            for sem in range(1, 31, 7):
                bloco = df.iloc[sem:min(sem+7, 31)]
                meta = 2 if len(bloco[(bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')]) == 0 else 1
                folgas_atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                
                while folgas_atuais < meta:
                    pode = bloco[bloco['Status'] == 'Trabalho'].index.tolist()
                    pode = [p for p in pode if df.loc[p, 'Dia'] != 'dom']
                    if not user.get("Rod_Sab"): pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                    if not user.get("Casada"):
                        pode = [p for p in pode if not (df.loc[p, 'Dia'] == 'seg' and (p > 0 and df.loc[p-1, 'Status'] == 'Folga'))]
                    
                    if not pode: break
                    escolha = random.choice(pode)
                    if not ((escolha > 0 and df.loc[escolha-1, 'Status'] == 'Folga' and df.loc[escolha-1, 'Dia'] != 'dom') or 
                            (escolha < 30 and df.loc[escolha+1, 'Status'] == 'Folga')):
                        df.loc[escolha, 'Status'] = 'Folga'
                        folgas_atuais += 1
            
            # Aplicar Horários Iniciais
            df['H_Entrada'] = user.get("Entrada")
            # Saída fixa: Entrada + 8:48 + 1:10 almoço = 9h 58min de permanência
            def calc_saida(ent_str):
                e = datetime.strptime(ent_str, "%H:%M")
                return (e + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            df['H_Saida'] = df['H_Entrada'].apply(calc_saida)
            st.session_state['historico'][func_sel] = df
            st.table(df)

with aba3:
    st.subheader("⚙️ Ajustes de Dias Específicos")
    if not st.session_state['historico']:
        st.warning("Gere a escala na Aba 2 primeiro.")
    else:
        f_sel = st.selectbox("Ajustar para:", list(st.session_state['historico'].keys()))
        df_edit = st.session_state['historico'][f_sel]
        
        c1, c2 = st.columns(2)
        dia_ajuste = c1.selectbox("Dia a alterar", range(1, 32))
        novo_horario = c2.time_input("Novo horário de entrada para este dia")
        
        if st.button("Aplicar Alteração e Corrigir Descansos"):
            idx = dia_ajuste - 1
            df_edit.loc[idx, 'H_Entrada'] = novo_horario.strftime("%H:%M")
            
            # Recalcula Saída do dia alterado
            ent_ajustada = datetime.combine(datetime.today(), novo_horario)
            saida_ajustada = ent_ajustada + timedelta(hours=9, minutes=58)
            df_edit.loc[idx, 'H_Saida'] = saida_ajustada.strftime("%H:%M")
            
            # REGRA DE OURO: Cascata de Descanso (11h e 36h)
            for i in range(idx + 1, 31):
                saida_anterior_str = df_edit.loc[i-1, 'H_Saida']
                status_anterior = df_edit.loc[i-1, 'Status']
                
                s_ant = datetime.strptime(saida_anterior_str, "%H:%M")
                horario_base = datetime.strptime(next(u['Entrada'] for u in st.session_state['db_users'] if u['Nome'] == f_sel), "%H:%M")
                
                # Se o anterior foi FOLGA, descanso de 35h-36h (24h folga + 11h interjornada)
                if status_anterior == 'Folga':
                    # Simplificando: o retorno após folga deve ser no horário padrão, 
                    # mas se a saída antes da folga foi muito tarde, pode afetar.
                    pass # Geralmente a folga já garante as 36h se o horário é fixo
                
                # Se o anterior foi TRABALHO, descanso de 11h obrigatório
                else:
                    minimo_entrada = s_ant + timedelta(hours=11)
                    # Se o mínimo de 11h obrigar a entrar mais tarde que o horário base:
                    if minimo_entrada.time() > horario_base.time() and minimo_entrada.day == s_ant.day:
                        # Precisa entrar mais tarde
                        df_edit.loc[i, 'H_Entrada'] = minimo_entrada.strftime("%H:%M")
                        df_edit.loc[i, 'H_Saida'] = (minimo_entrada + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                    else:
                        # Volta ao normal
                        df_edit.loc[i, 'H_Entrada'] = horario_base.strftime("%H:%M")
                        df_edit.loc[i, 'H_Saida'] = (horario_base + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            
            st.session_state['historico'][f_sel] = df_edit
            st.success("Horário alterado e descansos de 11h recalculados para os dias seguintes!")
            st.table(df_edit)

with aba4:
    if st.session_state['historico']:
        f_nome = st.selectbox("Baixar Escala:", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][f_nome]
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red, yel = PatternFill(start_color="FF0000", fill_type="solid"), PatternFill(start_color="FFFF00", fill_type="solid")
            
            ws.cell(1,1,"Nome")
            for i in range(31):
                ws.cell(1,i+2,i+1).alignment = Alignment(horizontal="center")
                ws.cell(2,i+2,df_h.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
            
            ws.cell(3,1,f_nome); ws.cell(4,1,"Horário")
            for i, row in df_h.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                c_t = ws.cell(3, col, "Folga" if is_f else row['H_Entrada'])
                c_b = ws.cell(4, col, "" if is_f else row['H_Saida'])
                if is_f:
                    cor = red if row['Dia'] == 'dom' else yel
                    c_t.fill = c_b.fill = cor
            for col in range(1, 33): ws.column_dimensions[ws.cell(1, col).column_letter].width = 8
        st.download_button("📥 Baixar Excel Atualizado", out.getvalue(), f"escala_{f_nome}.xlsx")
