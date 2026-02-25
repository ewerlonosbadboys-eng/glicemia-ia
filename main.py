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

st.title("📅 Gestão de Escala Profissional")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE GERAÇÃO BALANCEADA ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    folgas_por_dia = {i: 0 for i in range(31)}

    for user in lista_usuarios:
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        offset_dom = user.get('offset_dom', random.randint(0,1))
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                folgas_por_dia[d_idx] += 1
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'
                    folgas_por_dia[d_idx + 1] += 1

        for sem in range(0, 31, 7):
            bloco = df.iloc[sem:min(sem+7, 31)]
            meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
            atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
            while atuais < meta:
                pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                if not user.get("Rod_Sab"): pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                p_real = [p for p in pode if not ((p > 0 and df.loc[p-1, 'Status'] == 'Folga') or (p < 30 and df.loc[p+1, 'Status'] == 'Folga'))]
                if not p_real: break
                dia_escolhido = min(p_real, key=lambda x: folgas_por_dia[x])
                df.loc[dia_escolhido, 'Status'] = 'Folga'
                folgas_por_dia[dia_escolhido] += 1
                atuais += 1
        
        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
        novo_historico[nome] = df
    return novo_historico

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Cadastrar Novo Funcionário")
    c_cad1, c_cad2 = st.columns(2)
    nome_input = c_cad1.text_input("Nome do Funcionário")
    cat_input = c_cad2.text_input("Categoria / Alocação")
    h_ent_padrao = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    if st.button("Salvar no Grupo"):
        if nome_input:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome_input]
            st.session_state['db_users'].append({
                "Nome": nome_input, 
                "Categoria": cat_input if cat_input else "Geral", 
                "Entrada": h_ent_padrao.strftime('%H:%M'), 
                "Rod_Sab": f_sab, 
                "Casada": f_cas, 
                "offset_dom": random.randint(0,1)
            })
            st.success(f"✅ {nome_input} salvo!")

# --- ABA 2: GERAR ---
with aba2:
    if st.session_state['db_users']:
        if st.button("🚀 GERAR ESCALA BALANCEADA PARA TODOS"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escalas geradas!")

# --- ABA 3: AJUSTES ---
with aba3:
    if st.session_state['db_users'] and st.session_state['historico']:
        f_ed = st.selectbox("Selecione o funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        u_info = next((u for u in st.session_state['db_users'] if u['Nome'] == f_ed), None)

        if u_info:
            st.subheader("🔄 Mover Dia de Folga")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            dia_v = st.selectbox("Remover folga do dia:", [d+1 for d in folgas_atuais])
            dia_n = st.number_input("Colocar folga no dia:", 1, 31, value=1)
            
            if st.button("Confirmar Troca"):
                temp_df = df_e.copy()
                temp_df.loc[dia_v-1, 'Status'] = 'Trabalho'
                temp_df.loc[dia_n-1, 'Status'] = 'Folga'
                cont, max_d = 0, 0
                for s in temp_df['Status']:
                    cont = cont + 1 if s == 'Trabalho' else 0
                    max_d = max(max_d, cont)
                
                if max_d > 5:
                    st.error(f"⚠️ Proibido: Bloco de {max_d} dias seguidos detectado.")
                else:
                    df_e.loc[dia_v-1, 'Status'] = 'Trabalho'
                    df_e.loc[dia_v-1, 'H_Entrada'] = u_info['Entrada']
                    df_e.loc[dia_v-1, 'H_Saida'] = (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                    df_e.loc[dia_n-1, 'Status'] = 'Folga'
                    df_e.loc[dia_n-1, 'H_Entrada'] = ""
                    df_e.loc[dia_n-1, 'H_Saida'] = ""
                    st.session_state['historico'][f_ed] = df_e
                    st.success("Folga alterada!")
                    st.rerun()

# --- ABA 4: DOWNLOAD (CORRIGIDO) ---
with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL CONSOLIDADO"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Geral")
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                
                ws.cell(1, 1, "FUNCIONÁRIO").font = Font(bold=True)
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    # BUSCA SEGURA PARA EVITAR KEYERROR
                    u_inf = next((u for u in st.session_state['db_users'] if u['Nome'] == nome), {"Categoria": "Geral"})
                    categoria = u_inf.get("Categoria", "Geral")
                    
                    cell_nome = ws.cell(row_idx, 1, f"{nome}\n({categoria})")
                    cell_nome.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, d_row in df_f.iterrows():
                        col = i + 2
                        is_f = (d_row['Status'] == 'Folga')
                        c_ent = ws.cell(row_idx, col, "FOLGA" if is_f else d_row['H_Entrada'])
                        c_sai = ws.cell(row_idx+1, col, "" if is_f else d_row['H_Saida'])
                        if is_f: c_ent.fill = c_sai.fill = red if d_row['Dia'] == 'dom' else yel
                        c_ent.border = c_sai.border = border
                    row_idx += 2
                ws.column_dimensions['A'].width = 25
            st.download_button("Clique aqui para baixar", out.getvalue(), "escala_corrigida.xlsx")
