import streamlit as st
import pandas as pd
from datetime import datetime, tiimport streamlit as st
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
medelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# --- MEMÓRIA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0: diff += 24
        if diff < 11: return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except: pass
    return ent_padrao

def gerar_escala_inteligente(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    # Agrupamento por Categoria para balanceamento setorial
    cats = {}
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        cats.setdefault(c, []).append(u)
    
    for cat_nome, membros in cats.items():
        mapa_folgas_dia = {i: 0 for i in range(31)} 
        random.shuffle(membros)
        
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Divide o mês em semanas reais (7 dias) para garantir 2 folgas em cada ciclo
            for sem in range(0, 31, 7):
                fim_semana = min(sem + 7, 31)
                folgas_alocadas = 0
                
                # 1. REGRA DO DOMINGO (Alternado conforme Offset)
                domingos_na_semana = [j for j in range(sem, fim_semana) if df.loc[j, 'Dia'] == 'dom']
                for d_idx in domingos_na_semana:
                    semana_id = d_idx // 7
                    if semana_id % 2 == user.get('offset_dom', 0):
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_alocadas += 1
                        
                        # Se for FOLGA CASADA, tenta obrigatoriamente a Segunda-feira
                        if user.get("Casada") and (d_idx + 1) < 31:
                            df.loc[d_idx + 1, 'Status'] = 'Folga'
                            mapa_folgas_dia[d_idx + 1] += 1
                            folgas_alocadas += 1

                # 2. ALOCAÇÃO DAS FOLGAS RESTANTES (Garante que não sobrem dias)
                while folgas_alocadas < 2:
                    possiveis = []
                    for j in range(sem, fim_semana):
                        if df.loc[j, 'Status'] == 'Trabalho':
                            # Se não for casada, evita colar em outra folga
                            colado = (j > 0 and df.loc[j-1, 'Status'] == 'Folga') or (j < 30 and df.loc[j+1, 'Status'] == 'Folga')
                            sab_bloqueado = (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))
                            
                            if not sab_bloqueado:
                                if user.get("Casada") or not colado:
                                    possiveis.append(j)
                    
                    if not possiveis: # Se a trava de "não colar" impedir a folga, liberamos a trava para não faltar folga
                        possiveis = [j for j in range(sem, fim_semana) if df.loc[j, 'Status'] == 'Trabalho' and not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    
                    if possiveis:
                        # Escolhe o dia que tem MENOS folgas na mesma categoria (Balanceamento Setorial)
                        possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                        escolhido = possiveis[0]
                        df.loc[escolhido, 'Status'] = 'Folga'
                        mapa_folgas_dia[escolhido] += 1
                        folgas_alocadas += 1
                    else:
                        break # Evita loop infinito se a semana acabar

            # Cálculo de Horários com 11h de descanso
            ents, sais = [], []
            h_padrao = user.get("Entrada", "06:00")
            for i in range(len(df)):
                if df.loc[i, 'Status'] == 'Folga':
                    ents.append(""); sais.append("")
                else:
                    ent_atual = h_padrao
                    if i > 0 and sais[-1] != "":
                        ent_atual = calcular_entrada_segura(sais[-1], h_padrao)
                    ents.append(ent_atual)
                    sais.append((datetime.strptime(ent_atual, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df
            
    return novo_hist

# --- INTERFACE ---
tab1, tab2, tab3, tab4 = st.tabs(["👤 Cadastro", "📅 Escala", "🔧 Ajustes", "📥 Exportar"])

with tab1:
    st.subheader("Cadastro de Equipe")
    c1, c2 = st.columns(2)
    with c1:
        nome_in = st.text_input("Nome do Colaborador")
        cat_in = st.text_input("Setor/Categoria")
    with c2:
        ent_in = st.time_input("Horário Base", value=datetime.strptime("06:00", "%H:%M").time())
        sab_in = st.checkbox("Trabalha aos Sábados?")
        cas_in = st.checkbox("Deseja Folga Casada (Seguidas)?")

    if st.button("Adicionar"):
        if nome_in and cat_in:
            off = len([u for u in st.session_state['db_users'] if u['Categoria'] == cat_in]) % 2
            st.session_state['db_users'].append({
                "Nome": nome_in, "Categoria": cat_in, "Entrada": ent_in.strftime('%H:%M'),
                "Rod_Sab": sab_in, "Casada": cas_in, "offset_dom": off
            })
            st.success(f"{nome_in} salvo!")

with tab2:
    if st.button("🔄 GERAR ESCALA 5x2"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
            st.balloons()
        else: st.warning("Cadastre alguém primeiro.")
    
    if st.session_state['historico']:
        for n, d in st.session_state['historico'].items():
            with st.expander(f"Escala de {n}"):
                st.table(d)

with tab3:
    st.subheader("Ajustes Pontuais")
    if st.session_state['historico']:
        func = st.selectbox("Selecione:", list(st.session_state['historico'].keys()))
        df_temp = st.session_state['historico'][func]
        dia = st.number_input("Dia do Mês:", 1, 31)
        novo_status = st.radio("Status:", ["Trabalho", "Folga"], horizontal=True)
        if st.button("Atualizar"):
            df_temp.loc[dia-1, 'Status'] = novo_status
            st.session_state['historico'][func] = df_temp
            st.rerun()

with tab4:
    if st.session_state['historico']:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala Geral", index=0)
            f_dom = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
            f_fol = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
            border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Cabeçalhos
            ref = list(st.session_state['historico'].values())[0]
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, ref.iloc[i]['Dia']).alignment = center
            
            row_idx = 3
            for nome, df_f in st.session_state['historico'].items():
                cat = next(u['Categoria'] for u in st.session_state['db_users'] if u['Nome'] == nome)
                ws.cell(row_idx, 1, f"{nome}\n({cat})").alignment = center
                ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                for i, row in df_f.iterrows():
                    is_folga = (row['Status'] == 'Folga')
                    c1 = ws.cell(row_idx, i+2, "FOLGA" if is_folga else row['H_Entrada'])
                    c2 = ws.cell(row_idx+1, i+2, "" if is_folga else row['H_Saida'])
                    c1.border = c2.border = border
                    c1.alignment = c2.alignment = center
                    if is_folga:
                        c1.fill = c2.fill = f_dom if row['Dia'] == 'dom' else f_fol
                row_idx += 2
        
        st.download_button("📥 Baixar Excel", output.getvalue(), "escala_5x2_final.xlsx")
