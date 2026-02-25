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

st.title("📅 Gestão de Escala com Balanceamento")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE GERAÇÃO BALANCEADA (NOVA) ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    # Ordenar por categoria para balancear dentro do grupo
    lista_ordenada = sorted(lista_usuarios, key=lambda x: x.get('Categoria', 'Geral'))
    
    for idx, user in enumerate(lista_ordenada):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Regra de Domingos (1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        offset_dom = user.get('offset_dom', idx % 2) # Alterna baseado na posição
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Balanceamento Semanal (Escalonamento como na imagem)
        # Define um dia da semana fixo para folga extra baseado no índice do funcionário
        # Pula domingo (0) e sábados se não permitido
        dias_uteis_escala = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"): dias_uteis_escala.append('sáb')
        
        dia_fixo_semana = dias_uteis_escala[idx % len(dias_uteis_escala)]
        
        for sem_inicio in range(0, 31, 7):
            fim_sem = min(sem_inicio + 7, 31)
            bloco = df.iloc[sem_inicio:fim_sem]
            
            # Se a semana já não tem folga (domingo trabalhado), adiciona no dia da escala
            if not (bloco['Status'] == 'Folga').any():
                indices_dia_fixo = bloco[bloco['Dia'] == dia_fixo_semana].index.tolist()
                for f_idx in indices_dia_fixo:
                    df.loc[f_idx, 'Status'] = 'Folga'

        # Ajuste de horários
        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") if e else "" for e in df['H_Entrada']]
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
    st.subheader("👥 Histórico de Cadastros")
    if st.session_state['db_users']:
        df_cadastrados = pd.DataFrame(st.session_state['db_users'])
        st.table(df_cadastrados[['Nome', 'Categoria', 'Entrada', 'Rod_Sab', 'Casada']]) 
        if st.button("🚀 GERAR ESCALA BALANCEADA"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escala gerada com balanceamento por categoria!")
    else:
        st.info("Cadastre funcionários primeiro.")

# --- ABA 3: AJUSTES ---
with aba3:
    if st.session_state['db_users'] and st.session_state['historico']:
        f_ed = st.selectbox("Escolha quem editar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        u_info = next(u for u in st.session_state['db_users'] if u['Nome'] == f_ed)

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.subheader("🔄 Mover Folga")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            dia_v = st.selectbox("De:", [d+1 for d in folgas_atuais])
            dia_n = st.number_input("Para:", 1, 31, value=1)
            if st.button("Trocar"):
                idx_v, idx_n = dia_v - 1, dia_n - 1
                # Lógica de propagação se for domingo
                if df_e.loc[idx_n, 'Dia'] == 'dom' or df_e.loc[idx_v, 'Dia'] == 'dom':
                    dom_indices = df_e[df_e['Dia'] == 'dom'].index.tolist()
                    for d_idx in dom_indices:
                        is_f = (d_idx == idx_n) or (abs(d_idx - idx_n) % 14 == 0)
                        df_e.loc[d_idx, 'Status'] = 'Folga' if is_f else 'Trabalho'
                else:
                    df_e.loc[idx_v, 'Status'], df_e.loc[idx_n, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

        with col_f2:
            st.subheader("➕ Incluir Folga")
            dia_inc = st.number_input("Dia da Folga Extra:", 1, 31, value=1)
            if st.button("Incluir"):
                df_e.loc[dia_inc-1, 'Status'] = 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.success("Adicionado!")

# --- ABA 4: DOWNLOAD ---
with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala")
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                
                row = 3
                for nome, df_f in st.session_state['historico'].items():
                    ws.cell(row, 1, nome)
                    for i, r in df_f.iterrows():
                        cell = ws.cell(row, i+2, "FOLGA" if r['Status'] == 'Folga' else r['H_Entrada'])
                        if r['Status'] == 'Folga':
                            cell.fill = red if r['Dia'] == 'dom' else yel
                    row += 2
            st.download_button("Clique para baixar", out.getvalue(), "escala.xlsx")
