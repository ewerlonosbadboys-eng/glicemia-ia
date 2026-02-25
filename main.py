import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

st.set_page_config(page_title="Gestor Escala 2026", layout="wide")

# --- 1. LOGIN (Mantido conforme original) ---
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

# --- LÓGICA DE GERAÇÃO CORRIGIDA ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
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
                # 2. Folga Casada (Apenas se a caixinha estiver marcada)
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 3. Lógica de Escada (Segunda a Sexta apenas)
        # Se NÃO marcar Sábado, ele NUNCA recebe folga aqui
        dias_disponiveis = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"): # Só entra sábado se explicitamente marcado
            dias_disponiveis.append('sáb')
        
        dia_folga_escala = dias_disponiveis[idx % len(dias_disponiveis)]

        for sem in range(0, 31, 7):
            bloco = df.iloc[sem:min(sem+7, 31)]
            # Se a semana ainda não tem folga (domingo ou casada)
            if not (bloco['Status'] == 'Folga').any():
                idx_folga = bloco[bloco['Dia'] == dia_folga_escala].index.tolist()
                if idx_folga:
                    df.loc[idx_folga[0], 'Status'] = 'Folga'

        # 4. Trava de Segurança (5x1)
        contador = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                contador += 1
            else:
                contador = 0
            if contador > 5:
                # Se trabalhou 6 dias, força folga (a menos que seja domingo fixo de trabalho)
                if df.loc[i, 'Dia'] != 'dom':
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
    if st.session_state['db_users']:
        st.table(pd.DataFrame(st.session_state['db_users'])[['Nome', 'Categoria', 'Rod_Sab', 'Casada']]) 
        if st.button("🚀 GERAR ESCALA"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escala gerada respeitando a escada de Seg-Sex!")

# --- ABA 3: AJUSTES (CÓDIGO ORIGINAL PRESERVADO) ---
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
            dia_v = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas_atuais], key="mv_v")
            dia_n = st.number_input("Colocar folga no dia:", 1, 31, value=1, key="mv_n")
            if st.button("Confirmar Troca"):
                idx_v, idx_n = dia_v - 1, dia_n - 1
                df_e.loc[idx_v, 'Status'], df_e.loc[idx_n, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()
        with col_f2:
            dia_extra = st.number_input("Adicionar folga extra:", 1, 31, value=1, key="inc_f")
            if st.button("Adicionar"):
                df_e.loc[dia_extra-1, 'Status'] = 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

# --- ABA 4: DOWNLOAD (EXCEL COM CORES PRESERVADO) ---
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
                
                # Cabeçalho
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1)
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia'])
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    ws.cell(row_idx, 1, nome)
                    for i, row in df_f.iterrows():
                        cel = ws.cell(row_idx, i+2, "FOLGA" if row['Status'] == 'Folga' else row['H_Entrada'])
                        cel.border = border
                        if row['Status'] == 'Folga':
                            cel.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("Salvar Arquivo", out.getvalue(), "escala_final.xlsx")
