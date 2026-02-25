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

# --- NOVA FUNÇÃO: BALANCEAMENTO DE DOMINGOS ---
def definir_domingo_balanceado():
    if not st.session_state['db_users']:
        return 1  # Começa pelo padrão
    contagem = {0: 0, 1: 0} # Grupo A e Grupo B de domingos
    for u in st.session_state['db_users']:
        offset = u.get('offset_dom', 1)
        contagem[offset] += 1
    return 0 if contagem[0] <= contagem[1] else 1

# --- LÓGICA DE GERAÇÃO COM BALANCEAMENTO ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    folgas_por_dia = {i: 0 for i in range(31)}

    for user in lista_usuarios:
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos (Balanceado pelo offset do cadastro)
        offset_dom = user.get('offset_dom', 1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                folgas_por_dia[d_idx] += 1
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'
                    folgas_por_dia[d_idx + 1] += 1

        # 2. Folgas Semanais Balanceadas
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
    nome = c_cad1.text_input("Nome do Funcionário")
    categoria = c_cad2.text_input("Categoria / Alocação (Livre)")
    h_ent_padrao = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    if st.button("Salvar no Grupo"):
        if nome:
            # Regra de balanceamento na entrada
            offset = definir_domingo_balanceado()
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, 
                "Categoria": categoria if categoria else "Geral", 
                "Entrada": h_ent_padrao.strftime('%H:%M'), 
                "Rod_Sab": f_sab, 
                "Casada": f_cas,
                "offset_dom": offset # Garante a transição correta entre meses
            })
            st.success(f"✅ {nome} salvo e balanceado!")

# --- ABA 2: GERAR ---
with aba2:
    if st.session_state['db_users']:
        st.subheader("Geração de Escala")
        if st.button("🚀 GERAR ESCALA BALANCEADA PARA TODOS"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("✅ Escalas geradas com balanceamento de domingos e folgas!")
            prim = list(st.session_state['historico'].keys())[0]
            st.table(st.session_state['historico'][prim].head(10))

# --- ABA 3: AJUSTES (CÓDIGO ORIGINAL PRESERVADO) ---
with aba3:
    if st.session_state['db_users']:
        f_ed = st.selectbox("Escolha quem editar:", [u.get('Nome') for u in st.session_state['db_users']])
        u_ix = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        n_cat = st.text_input("Mudar Categoria:", value=st.session_state['db_users'][u_ix].get('Categoria', ''))
        if st.button("💾 Salvar Alteração"):
            st.session_state['db_users'][u_ix]['Categoria'] = n_cat
            st.rerun()
        
        if f_ed in st.session_state['historico']:
            st.divider()
            df_e = st.session_state['historico'][f_ed]
            dia = st.number_input("Dia do Mês", 1, 31)
            n_h = st.time_input("Nova Entrada")
            if st.button("💾 Aplicar e Recalcular Descanso"):
                idx = int(dia - 1)
                df_e.loc[idx, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[idx, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                for i in range(idx + 1, 31):
                    if df_e.loc[i-1, 'Status'] == 'Trabalho':
                        s_ant = datetime.strptime(df_e.loc[i-1, 'H_Saida'], "%H:%M")
                        minimo = (s_ant + timedelta(hours=11, minutes=10)).time()
                        b_ent = datetime.strptime(st.session_state['db_users'][u_ix]['Entrada'], "%H:%M").time()
                        if minimo > b_ent:
                            df_e.loc[i, 'H_Entrada'] = minimo.strftime("%H:%M")
                            df_e.loc[i, 'H_Saida'] = (datetime.combine(datetime.today(), minimo) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Ajustado!")

# --- ABA 4: DOWNLOAD (CÓDIGO ORIGINAL PRESERVADO) ---
with aba4:
    if st.session_state['historico']:
        st.subheader("Exportar para Excel")
        if st.button("📥 BAIXAR ESCALA CONSOLIDADA"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Balanceada")
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                blue_head = PatternFill(start_color="DDEBF7", end_color="DDEBF7", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                
                ws.cell(1, 1, "FUNCIONÁRIO").font = Font(bold=True)
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    col = i + 2
                    ws.cell(1, col, i+1).fill = blue_head
                    ws.cell(1, col, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, col, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_info = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    display_name = f"{nome}\n({u_info.get('Categoria')})"
                    c_nome = ws.cell(row_idx, 1, display_name)
                    c_nome.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
                    c_nome.font = Font(size=9)
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    for i, day_row in df_f.iterrows():
                        col = i + 2
                        is_f = (day_row['Status'] == 'Folga')
                        c_ent = ws.cell(row_idx, col, "FOLGA" if is_f else day_row['H_Entrada'])
                        c_sai = ws.cell(row_idx+1, col, "" if is_f else day_row['H_Saida'])
                        c_ent.alignment = Alignment(horizontal="center")
                        c_sai.alignment = Alignment(horizontal="center")
                        if is_f:
                            fill_color = red if day_row['Dia'] == 'dom' else yel
                            c_ent.fill = c_sai.fill = fill_color
                        c_ent.border = border
                        c_sai.border = border
                    row_idx += 2
                ws.column_dimensions['A'].width = 25
                for i in range(31): ws.column_dimensions[ws.cell(1, i+2).column_letter].width = 8
            st.download_button("Clique para salvar", out.getvalue(), "escala_balanceada_2026.xlsx")
