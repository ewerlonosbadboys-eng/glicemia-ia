import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import randomimport streamlit as st
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

st.title("📅 Gestão de Escala - Sistema Completo")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE GERAÇÃO COM TRAVA RÍGIDA 5x1 ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    usuarios_ordenados = sorted(lista_usuarios, key=lambda x: x.get('Categoria', 'Geral'))

    for idx, user in enumerate(usuarios_ordenados):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos (1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        offset_dom = user.get('offset_dom', idx % 2) 
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Trava de 5 dias (Não pode trabalhar mais que 5 dias direto)
        contador = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                contador += 1
            else:
                contador = 0
            if contador > 5:
                df.loc[i, 'Status'] = 'Folga'
                contador = 0

        # 3. Escada (Apenas se a semana não tiver folga e trabalhou domingo)
        dias_possiveis = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"): dias_possiveis.append('sáb')
        dia_fixo = dias_possiveis[idx % len(dias_possiveis)]

        for sem in range(0, len(df), 7):
            semana = df.iloc[sem:sem+7]
            if (semana['Status'] == 'Folga').sum() == 0:
                idx_f = semana[semana['Dia'] == dia_fixo].index.tolist()
                if idx_f: df.loc[idx_f[0], 'Status'] = 'Folga'

        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") if df.loc[k, 'Status'] == 'Trabalho' else "" for k, e in enumerate(df['H_Entrada'])]
        novo_historico[nome] = df
        
    return novo_historico

# --- ABAS DE INTERFACE ---
with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n_in = c1.text_input("Nome")
    cat_in = c2.text_input("Categoria")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    s_in = col1.checkbox("Rodízio de Sábado")
    c_in = col2.checkbox("Folga Casada")
    if st.button("Salvar Funcionário"):
        st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != n_in]
        st.session_state['db_users'].append({"Nome": n_in, "Categoria": cat_in, "Entrada": h_in.strftime('%H:%M'), "Rod_Sab": s_in, "Casada": c_in, "offset_dom": random.randint(0,1)})
        st.success("Salvo!")

with aba2:
    if st.session_state['db_users']:
        if st.button("🚀 GERAR ESCALA"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Gerado!")

with aba3: # AJUSTES COMPLETOS RESTAURADOS
    if st.session_state['historico']:
        f_ed = st.selectbox("Selecione para editar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_u = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        u_info = st.session_state['db_users'][idx_u]

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            st.subheader("🏷️ Categoria")
            n_cat = st.text_input("Mudar Categoria:", value=u_info['Categoria'])
            if st.button("Atualizar Categoria"):
                st.session_state['db_users'][idx_u]['Categoria'] = n_cat
                st.rerun()

            st.subheader("🔄 Mover Folga")
            folgas = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_v = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas])
            d_n = st.number_input("Colocar no dia:", 1, 31)
            if st.button("Trocar Folga"):
                df_e.loc[d_v-1, 'Status'], df_e.loc[d_n-1, 'Status'] = 'Trabalho', 'Folga'
                df_e.loc[d_v-1, 'H_Entrada'] = u_info['Entrada']
                df_e.loc[d_v-1, 'H_Saida'] = (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                df_e.loc[d_n-1, 'H_Entrada'], df_e.loc[d_n-1, 'H_Saida'] = "", ""
                st.session_state['historico'][f_ed] = df_e
                st.success("Trocado!"); st.rerun()

        with col_a2:
            st.subheader("🕒 Horário")
            dia_h = st.number_input("Dia:", 1, 31)
            n_h = st.time_input("Novo Horário:")
            if st.button("Ajustar Horário"):
                df_e.loc[dia_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Ajustado!")

            st.subheader("➕ Folga Extra")
            dia_ex = st.number_input("Adicionar folga no dia:", 1, 31, key="ex")
            if st.button("Adicionar"):
                df_e.loc[dia_ex-1, 'Status'] = 'Folga'
                df_e.loc[dia_ex-1, 'H_Entrada'], df_e.loc[dia_ex-1, 'H_Saida'] = "", ""
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala")
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    cell_n = ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})")
                    cell_n.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, row in df_f.iterrows():
                        col = i + 2
                        is_f = (row['Status'] == 'Folga')
                        c1 = ws.cell(row_idx, col, "FOLGA" if is_f else row['H_Entrada'])
                        c2 = ws.cell(row_idx+1, col, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border
                        c1.alignment = c2.alignment = Alignment(horizontal="center")
                        if is_f: c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("Salvar Excel", out.getvalue(), "escala_completa.xlsx")

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

st.title("📅 Gestão de Escala - Regra Sábado Útil")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE GERAÇÃO COM BLOQUEIO DE SÁBADO ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    usuarios_ordenados = sorted(lista_usuarios, key=lambda x: x.get('Categoria', 'Geral'))

    for idx, user in enumerate(usuarios_ordenados):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos (Regra 1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        offset_dom = user.get('offset_dom', idx % 2) 
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Trava de 5 dias + Bloqueio de Sábado
        contador = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                contador += 1
            else:
                contador = 0
            
            if contador > 5:
                # Se cair no Sábado e NÃO tiver rodízio, pula a folga pro próximo dia disponível (Domingo)
                if df.loc[i, 'Dia'] == 'sáb' and not user.get("Rod_Sab"):
                    if (i + 1) < len(df):
                        df.loc[i+1, 'Status'] = 'Folga'
                        contador = 0
                else:
                    df.loc[i, 'Status'] = 'Folga'
                    contador = 0

        # 3. Folga Semanal (Escada) - APENAS SE A SEMANA NÃO TEM FOLGA
        # Dias permitidos para folga automática
        dias_permitidos = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"): dias_permitidos.append('sáb')
        
        dia_fixo = dias_permitidos[idx % len(dias_permitidos)]

        for sem in range(0, len(df), 7):
            semana = df.iloc[sem:sem+7]
            if (semana['Status'] == 'Folga').sum() == 0:
                idx_f = semana[semana['Dia'] == dia_fixo].index.tolist()
                if idx_f: df.loc[idx_f[0], 'Status'] = 'Folga'

        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") if df.loc[k, 'Status'] == 'Trabalho' else "" for k, e in enumerate(df['H_Entrada'])]
        novo_historico[nome] = df
        
    return novo_historico

# --- ABAS DE INTERFACE ---
with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n_in = c1.text_input("Nome")
    cat_in = c2.text_input("Categoria")
    h_in = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    s_in = col1.checkbox("Rodízio de Sábado")
    c_in = col2.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar"):
        st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != n_in]
        st.session_state['db_users'].append({"Nome": n_in, "Categoria": cat_in, "Entrada": h_in.strftime('%H:%M'), "Rod_Sab": s_in, "Casada": c_in, "offset_dom": random.randint(0,1)})
        st.success("Salvo!")

with aba2:
    if st.session_state['db_users']:
        if st.button("🚀 GERAR ESCALA"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Escala Gerada!")

with aba3: # AJUSTES COMPLETOS
    if st.session_state['historico']:
        f_ed = st.selectbox("Editar funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_u = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        u_info = st.session_state['db_users'][idx_u]

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("🏷️ Categoria")
            n_cat = st.text_input("Nova Categoria:", value=u_info['Categoria'])
            if st.button("Mudar Categoria"):
                st.session_state['db_users'][idx_u]['Categoria'] = n_cat
                st.rerun()

            st.subheader("🔄 Mover Folga")
            folgas = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_v = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas])
            d_n = st.number_input("Colocar no dia:", 1, 31)
            if st.button("Confirmar Troca"):
                df_e.loc[d_v-1, 'Status'], df_e.loc[d_n-1, 'Status'] = 'Trabalho', 'Folga'
                df_e.loc[d_v-1, 'H_Entrada'] = u_info['Entrada']
                df_e.loc[d_v-1, 'H_Saida'] = (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                df_e.loc[d_n-1, 'H_Entrada'], df_e.loc[d_n-1, 'H_Saida'] = "", ""
                st.session_state['historico'][f_ed] = df_e
                st.success("Trocado!"); st.rerun()

        with col_b:
            st.subheader("🕒 Horário Individual")
            dia_h = st.number_input("Dia:", 1, 31)
            n_h = st.time_input("Novo Horário:")
            if st.button("Aplicar Horário"):
                df_e.loc[dia_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Ajustado!")

            st.subheader("➕ Folga Extra")
            dia_ex = st.number_input("Dia da folga extra:", 1, 31, key="extra")
            if st.button("Adicionar"):
                df_e.loc[dia_ex-1, 'Status'] = 'Folga'
                df_e.loc[dia_ex-1, 'H_Entrada'], df_e.loc[dia_ex-1, 'H_Saida'] = "", ""
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala")
                red, yel = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid"), PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    cell_n = ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})")
                    cell_n.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, row in df_f.iterrows():
                        col = i + 2
                        is_f = (row['Status'] == 'Folga')
                        c1 = ws.cell(row_idx, col, "FOLGA" if is_f else row['H_Entrada'])
                        c2 = ws.cell(row_idx+1, col, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border
                        c1.alignment = c2.alignment = Alignment(horizontal="center")
                        if is_f: c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("Salvar Arquivo Excel", out.getvalue(), "escala_2026.xlsx")
