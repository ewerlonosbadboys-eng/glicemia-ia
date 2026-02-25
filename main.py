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

# --- LÓGICA DE GERAÇÃO COM FOCO NA ESCADA E REGRA DE 5 DIAS ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    # Ordenação por categoria para manter a estética de escada nas tabelas
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
        # Se NÃO marcou a caixa, o sábado vira opção de folga para balancear a escala
        dias_possiveis_folga = ['seg', 'ter', 'qua', 'qui', 'sex']
        if not user.get("Rod_Sab"):
            dias_possiveis_folga.append('sáb')
        
        # Define o dia da folga fixa semanal baseado na posição (Escada)
        dia_fixo_semana = dias_possiveis_folga[idx % len(dias_possiveis_folga)]

        for sem in range(0, 31, 7):
            bloco = df.iloc[sem:min(sem+7, 31)]
            # Se não houver folga de domingo nesse bloco de 7 dias, aplica a folga da escada
            if not (bloco['Status'] == 'Folga').any():
                idx_f = bloco[bloco['Dia'] == dia_fixo_semana].index.tolist()
                if idx_f:
                    df.loc[idx_f[0], 'Status'] = 'Folga'
            
            # Garantia de folga semanal
            if len(df.iloc[sem:min(sem+7, 31)][df['Status'] == 'Folga']) == 0:
                pode = [p for p in bloco.index.tolist() if df.loc[p, 'Dia'] != 'dom']
                if pode: df.loc[pode[0], 'Status'] = 'Folga'

        # 3. TRAVA DE SEGURANÇA FINAL: MÁXIMO 5 DIAS DE TRABALHO
        cont = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                cont += 1
            else:
                cont = 0
            
            if cont > 5:
                df.loc[i, 'Status'] = 'Folga'
                cont = 0

        # Preenchimento dos Horários
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
    if st.session_state['db_users']:
        df_view = pd.DataFrame(st.session_state['db_users'])[['Nome', 'Categoria', 'Entrada', 'Rod_Sab', 'Casada']]
        st.table(df_view) 
        if st.button("🚀 GERAR ESCALA BALANCEADA (REGRAS 2026)"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escala gerada com balanceamento semanal e trava de 5 dias!")

# --- ABA 3: AJUSTES (Mantido Integralmente) ---
with aba3:
    if st.session_state['db_users'] and st.session_state['historico']:
        f_ed = st.selectbox("Escolha quem editar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_user = next((i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed), None)
        u_info = st.session_state['db_users'][idx_user]

        st.subheader("📅 Gestão de Folgas")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            dia_v = st.selectbox("Mover folga do dia:", [d+1 for d in folgas_atuais], key="mv_v")
            dia_n = st.number_input("Para o dia:", 1, 31, value=1, key="mv_n")
            if st.button("Trocar Folga"):
                idx_v, idx_n = dia_v - 1, dia_n - 1
                if df_e.loc[idx_n, 'Dia'] == 'dom' or df_e.loc[idx_v, 'Dia'] == 'dom':
                    doms = df_e[df_e['Dia'] == 'dom'].index.tolist()
                    for d in doms:
                        is_f = (d == idx_n) or (abs(d - idx_n) % 14 == 0)
                        df_e.loc[d, 'Status'] = 'Folga' if is_f else 'Trabalho'
                else:
                    df_e.loc[idx_v, 'Status'], df_e.loc[idx_n, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

        with col_f2:
            dia_extra = st.number_input("Adicionar folga extra no dia:", 1, 31, value=1, key="inc_f")
            if st.button("Adicionar Folga"):
                df_e.loc[dia_extra-1, 'Status'] = 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

# --- ABA 4: DOWNLOAD (Excel com Cores Mantido) ---
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
                        ws.cell(row_idx, col, "FOLGA" if is_f else day_row['H_Entrada']).border = border
                        ws.cell(row_idx+1, col, "" if is_f else day_row['H_Saida']).border = border
                        if is_f:
                            ws.cell(row_idx, col).fill = ws.cell(row_idx+1, col).fill = red if day_row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("Salvar Arquivo", out.getvalue(), "escala_gerada.xlsx")
