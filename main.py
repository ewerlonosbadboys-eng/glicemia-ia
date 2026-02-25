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

# --- LÓGICA DE GERAÇÃO COM BALANCEAMENTO E REGRA 5 DIAS ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    # Ordenamos para garantir que o escalonamento (escada) siga a ordem dos nomes
    usuarios_ordenados = sorted(lista_usuarios, key=lambda x: x.get('Categoria', 'Geral'))

    for idx, user in enumerate(usuarios_ordenados):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Regra de Domingos (1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        offset_dom = user.get('offset_dom', idx % 2) 
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Lógica de Escada (Balanceamento Semanal)
        dias_disponiveis = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"): dias_disponiveis.append('sáb')
        dia_folga_escala = dias_disponiveis[idx % len(dias_disponiveis)]

        for sem in range(0, 31, 7):
            bloco = df.iloc[sem:min(sem+7, 31)]
            if not (bloco['Status'] == 'Folga').any():
                idx_folga = bloco[bloco['Dia'] == dia_folga_escala].index.tolist()
                if idx_folga:
                    df.loc[idx_folga[0], 'Status'] = 'Folga'
            
            # Garante folga na semana se necessário
            atuais = len(df.iloc[sem:min(sem+7, 31)][df['Status'] == 'Folga'])
            if atuais == 0:
                pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                if pode: df.loc[pode[0], 'Status'] = 'Folga'

        # 3. TRAVA DE SEGURANÇA: MÁXIMO 5 DIAS SEGUIDOS
        contador = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                contador += 1
            else:
                contador = 0
            
            if contador > 5:
                df.loc[i, 'Status'] = 'Folga'
                contador = 0

        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") if df.loc[i, 'Status'] == 'Trabalho' else "" for i, e in enumerate(df['H_Entrada'])]
        novo_historico[nome] = df
        
    return novo_historico

# --- ABA 1: CADASTRO ---
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

# --- ABA 2: GERAR ---
with aba2:
    st.subheader("👥 Funcionários Cadastrados")
    if st.session_state['db_users']:
        df_cadastrados = pd.DataFrame(st.session_state['db_users'])
        df_view = df_cadastrados[['Nome', 'Categoria', 'Entrada', 'Rod_Sab', 'Casada']].copy()
        df_view.columns = ['Nome', 'Categoria', 'H. Entrada', 'Rodízio Sábado', 'Folga Casada']
        st.table(df_view) 
        if st.button("🚀 GERAR ESCALA BALANCEADA PARA TODOS"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escalas geradas com sucesso!")

# --- ABA 3: AJUSTES ---
with aba3:
    if st.session_state['db_users'] and st.session_state['historico']:
        f_ed = st.selectbox("Escolha quem editar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_user = next((i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed), None)
        u_info = st.session_state['db_users'][idx_user]

        st.subheader("🏷️ Alterar Categoria")
        cats_existentes = sorted(list(set([u.get('Categoria', 'Geral') for u in st.session_state['db_users']])))
        cat_atual = u_info.get('Categoria', 'Geral')
        nova_cat = st.selectbox("Selecione uma Categoria:", cats_existentes, index=cats_existentes.index(cat_atual) if cat_atual in cats_existentes else 0)
        if st.button("Atualizar Categoria"):
            st.session_state['db_users'][idx_user]['Categoria'] = nova_cat
            st.success("Categoria atualizada!"); st.rerun()

        st.divider()
        st.subheader("📅 Gestão de Folgas")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            st.markdown("**🔄 Mover Folga Existente**")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            dia_v = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas_atuais], key="mv_v")
            dia_n = st.number_input("Colocar folga no dia:", 1, 31, value=1, key="mv_n")
            if st.button("Confirmar Troca de Folga"):
                idx_v, idx_n = dia_v - 1, dia_n - 1
                if df_e.loc[idx_n, 'Dia'] == 'dom' or df_e.loc[idx_v, 'Dia'] == 'dom':
                    dom_indices = df_e[df_e['Dia'] == 'dom'].index.tolist()
                    for d_idx in dom_indices:
                        is_folga = (d_idx == idx_n) or (abs(d_idx - idx_n) % 14 == 0)
                        df_e.loc[d_idx, 'Status'] = 'Folga' if is_folga else 'Trabalho'
                        df_e.loc[d_idx, 'H_Entrada'] = "" if is_folga else u_info['Entrada']
                        df_e.loc[d_idx, 'H_Saida'] = "" if is_folga else (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                else:
                    df_e.loc[idx_v, 'Status'] = 'Trabalho'
                    df_e.loc[idx_v, 'H_Entrada'] = u_info['Entrada']
                    df_e.loc[idx_v, 'H_Saida'] = (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                    df_e.loc[idx_n, 'Status'], df_e.loc[idx_n, 'H_Entrada'], df_e.loc[idx_n, 'H_Saida'] = 'Folga', "", ""
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga movida!"); st.rerun()

        with col_f2:
            st.markdown("**➕ Incluir Folga Extra**")
            dia_extra = st.number_input("Dia para adicionar folga:", 1, 31, value=1, key="inc_f")
            if st.button("Adicionar Folga Extra"):
                idx_e = dia_extra - 1
                if df_e.loc[idx_e, 'Dia'] == 'dom':
                    dom_indices = df_e[df_e['Dia'] == 'dom'].index.tolist()
                    for d_idx in dom_indices:
                        is_folga = (d_idx == idx_e) or (abs(d_idx - idx_e) % 14 == 0)
                        df_e.loc[d_idx, 'Status'] = 'Folga' if is_folga else 'Trabalho'
                        df_e.loc[d_idx, 'H_Entrada'] = "" if is_folga else u_info['Entrada']
                        df_e.loc[d_idx, 'H_Saida'] = "" if is_folga else (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                else:
                    df_e.loc[idx_e, 'Status'] = 'Folga'
                    df_e.loc[idx_e, 'H_Entrada'] = ""
                    df_e.loc[idx_e, 'H_Saida'] = ""
                st.session_state['historico'][f_ed] = df_e
                st.success(f"Folga adicionada!"); st.rerun()

        st.divider()
        st.subheader("🕒 Ajustar Horário Individual")
        dia_h = st.number_input("Dia para mudar", 1, 31)
        n_h = st.time_input("Novo Horário")
        if st.button("Aplicar Horário"):
            idx = int(dia_h - 1)
            if df_e.loc[idx, 'Status'] != 'Folga':
                df_e.loc[idx, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[idx, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário ajustado!")

# --- ABA 4: DOWNLOAD ---
with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL CONSOLIDADO"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Final")
                red, yel = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid"), PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                ws.cell(1, 1, "FUNCIONÁRIO").font = Font(bold=True)
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next((u for u in st.session_state['db_users'] if u['Nome'] == nome), {"Categoria": "Geral"})
                    ws.cell(row_idx, 1, f"{nome}\n({u_inf.get('Categoria', 'Geral')})").alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    for i, day_row in df_f.iterrows():
                        col = i + 2
                        is_f = (day_row['Status'] == 'Folga')
                        c_ent = ws.cell(row_idx, col, "FOLGA" if is_f else day_row['H_Entrada'])
                        c_sai = ws.cell(row_idx+1, col, "" if is_f else day_row['H_Saida'])
                        if is_f: c_ent.fill = c_sai.fill = red if day_row['Dia'] == 'dom' else yel
                        c_ent.border = c_sai.border = border
                    row_idx += 2
            st.download_button("Salvar Arquivo", out.getvalue(), "escala_corrigida.xlsx")
