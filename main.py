import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

st.set_page_config(page_title="Gestor Escala 2026", layout="wide")

# --- 1. LOGIN ---
if "password_correct" not in st.session_state:
    st.title("🔐 Login do Sistema")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# --- 2. MEMÓRIA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.title("📅 Gestão de Escala com Troca de Folgas")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE GERAÇÃO REVISADA CONFORME IMAGENS ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-02', periods=31) # Começando em uma Segunda para lógica de semana
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    usuarios_ordenados = sorted(lista_usuarios, key=lambda x: x.get('Categoria', 'Geral'))

    for idx, user in enumerate(usuarios_ordenados):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Definição dos Domingos (1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        offset_dom = user.get('offset_dom', idx % 2) 
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                # Folga Casada (Opcional)
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Lógica de Folgas Semanais (Segunda a Domingo)
        # Se trabalhou Domingo, precisa de folga na semana. 
        # Se folgou Domingo, a folga da semana já foi batida.
        
        dias_possiveis_folga = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"):
            dias_possiveis_folga.append('sáb')

        # Rodízio da Escada (Apenas entre os dias permitidos)
        dia_fixo_semanal = dias_possiveis_folga[idx % len(dias_possiveis_folga)]

        for i in range(0, len(df), 7): # Analisa bloco de 7 dias (Semana)
            semana = df.iloc[i:i+7]
            folgas_na_semana = (semana['Status'] == 'Folga').sum()
            
            # Se a pessoa TRABALHA no domingo dessa semana e não tem folga ainda:
            if folgas_na_semana == 0:
                idx_folga = semana[semana['Dia'] == dia_fixo_semanal].index.tolist()
                if idx_folga:
                    df.loc[idx_folga[0], 'Status'] = 'Folga'

        # 3. Trava de Segurança (5x1)
        contador = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                contador += 1
            else:
                contador = 0
            if contador > 5:
                # Força folga se não for domingo ou sábado fixo
                if df.loc[i, 'Dia'] not in ['dom', 'sáb'] or (df.loc[i, 'Dia'] == 'sáb' and user.get("Rod_Sab")):
                    df.loc[i, 'Status'] = 'Folga'
                    contador = 0

        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") if df.loc[i, 'Status'] == 'Trabalho' else "" for i, e in enumerate(df['H_Entrada'])]
        novo_historico[nome] = df
        
    return novo_historico

# --- ABAS DE INTERFACE (Cadastro, Gerar e Ajustes mantidos conforme solicitado) ---
with aba1:
    st.subheader("Cadastrar Novo Funcionário")
    c_cad1, c_cad2 = st.columns(2)
    nome_in = c_cad1.text_input("Nome do Funcionário")
    cat_in = c_cad2.text_input("Categoria / Alocação")
    h_ent_padrao = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    if st.button("Salvar no Grupo"):
        if nome_in:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome_in]
            st.session_state['db_users'].append({"Nome": nome_in, "Categoria": cat_in if cat_in else "Geral", "Entrada": h_ent_padrao.strftime('%H:%M'), "Rod_Sab": f_sab, "Casada": f_cas, "offset_dom": random.randint(0,1)})
            st.success(f"✅ {nome_in} salvo!")

with aba2:
    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users'])[['Nome', 'Categoria', 'Rod_Sab', 'Casada']]) 
        if st.button("🚀 GERAR ESCALA"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escala gerada!")

with aba3:
    if st.session_state['db_users'] and st.session_state['historico']:
        f_ed = st.selectbox("Escolha quem editar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_user = next((i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed), None)
        u_info = st.session_state['db_users'][idx_user]

        st.subheader("🏷️ Alterar Categoria")
        cats_existentes = sorted(list(set([u.get('Categoria', 'Geral') for u in st.session_state['db_users']])))
        nova_cat = st.selectbox("Nova Categoria:", cats_existentes)
        if st.button("Atualizar Categoria"):
            st.session_state['db_users'][idx_user]['Categoria'] = nova_cat
            st.success("Categoria atualizada!"); st.rerun()

        st.divider()
        st.subheader("📅 Gestão de Folgas")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            dia_v = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas_atuais])
            dia_n = st.number_input("Colocar folga no dia:", 1, 31, value=1)
            if st.button("Trocar Folga"):
                df_e.loc[dia_v-1, 'Status'], df_e.loc[dia_n-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()
        
        st.divider()
        st.subheader("🕒 Ajustar Horário")
        dia_h = st.number_input("Dia", 1, 31)
        n_h = st.time_input("Novo Horário")
        if st.button("Aplicar"):
            idx = int(dia_h - 1)
            df_e.loc[idx, 'H_Entrada'] = n_h.strftime("%H:%M")
            df_e.loc[idx, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
            st.session_state['historico'][f_ed] = df_e
            st.success("Ajustado!")

with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala")
                red, yel = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid"), PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                for i in range(31):
                    ws.cell(1, i+2, i+1)
                    ws.cell(2, i+2, list(st.session_state['historico'].values())[0].iloc[i]['Dia'])
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    ws.cell(row_idx, 1, nome)
                    for i, row in df_f.iterrows():
                        cel = ws.cell(row_idx, i+2, "FOLGA" if row['Status'] == 'Folga' else row['H_Entrada'])
                        cel.border = border
                        if row['Status'] == 'Folga': cel.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("Salvar Excel", out.getvalue(), "escala_corrigida.xlsx")
