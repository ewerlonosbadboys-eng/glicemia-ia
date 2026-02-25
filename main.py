import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
            
            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                folgas_na_semana = 0 
                
                dom_no_bloco = [j for j in range(sem, fim) if df.loc[j, 'Dia'] == 'dom']
                for d_idx in dom_no_bloco:
                    semana_do_mes = d_idx // 7
                    if semana_do_mes % 2 == user.get('offset_dom', 0):
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_na_semana += 1 
                
                while folgas_na_semana < 2:
                    possiveis_vazios = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                       mapa_folgas_dia[j] == 0 and
                                       df.loc[j, 'Dia'] != 'dom' and
                                       not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    
                    if not possiveis_vazios:
                        possiveis_vazios = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                           df.loc[j, 'Dia'] != 'dom' and
                                           not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    
                    if possiveis_vazios:
                        random.shuffle(possiveis_vazios)
                        possiveis_vazios.sort(key=lambda x: mapa_folgas_dia[x])
                        escolhido = possiveis_vazios[0]
                        df.loc[escolhido, 'Status'] = 'Folga'
                        mapa_folgas_dia[escolhido] += 1
                        folgas_na_semana += 1
                    else:
                        break
            
            ents, sais = [], []
            hp = user.get("Entrada", "06:00")
            for m in range(len(df)):
                if df.loc[m, 'Status'] == 'Folga':
                    ents.append(""); sais.append("")
                else:
                    e = hp
                    if m > 0 and len(sais) > 0 and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], hp)
                    ents.append(e)
                    sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df
            
    return novo_hist

# --- INTERFACE (ABAS) ---
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "🚀 Gerar Escala", "⚙️ Ajustes", "📥 Baixar Excel"])

with aba1:
    st.subheader("Cadastro de Funcionários")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome", key="input_nome")
    ct = c2.text_input("Categoria (ex: Recepcionista)", key="input_cat")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time(), key="input_hora")
    col_check1, col_check2 = st.columns(2)
    s_rk = col_check1.checkbox("Trabalha Sábado?", key="check_sab")
    c_rk = col_check2.checkbox("Folga Casada?", key="check_casada")
    
    if st.button("Salvar Funcionário", key="btn_salvar_user"):
        if n and ct:
            existentes = len([u for u in st.session_state['db_users'] if u['Categoria'] == ct])
            st.session_state['db_users'].append({
                "Nome": n, "Categoria": ct, "Entrada": h_in.strftime('%H:%M'), 
                "Rod_Sab": s_rk, "Casada": c_rk, "offset_dom": existentes % 2
            })
            st.success(f"{n} cadastrado!")

with aba2:
    if st.button("🚀 GERAR ESCALA 5x2", key="btn_gerar_escala"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
            st.success("Escala Balanceada Gerada!")
        else: st.warning("Cadastre alguém.")
    
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Ver Escala: {nome}"):
                st.dataframe(df, use_container_width=True)

with aba3:
    st.subheader("Ajustes Manuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Funcionário:", list(st.session_state['historico'].keys()), key="select_user_ajuste")
        df_e = st.session_state['historico'][f_ed]
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Mover Folga")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_tira = st.selectbox("Dia para Trabalhar:", [d+1 for d in folgas_atuais], key="select_dia_tira")
            d_poe = st.number_input("Novo dia de Folga:", 1, 31, value=1, key="input_dia_poe")
            if st.button("Confirmar Mudança de Folga", key="btn_mudar_folga"):
                df_e.loc[d_tira-1, 'Status'], df_e.loc[d_poe-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e; st.rerun()
        with col_b:
            st.markdown("#### Mudar Horário")
            dia_h = st.number_input("Dia:", 1, 31, key="dh_ajuste")
            hora_h = st.time_input("Nova Entrada:", key="hh_ajuste")
            if st.button("Salvar Novo Horário", key="btn_salvar_hora_ajuste"):
                df_e.loc[dia_h-1, 'H_Entrada'] = hora_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), hora_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e; st.success("Horário Atualizado!")

with aba4:
    if st.session_state['historico']:
        if st.button("📊 GERAR EXCEL COLORIDO", key="btn_gerar_excel_final"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                wb = writer.book; ws = wb.create_sheet("Escala", index=0)
                fill_dom = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                fill_folga = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                center = Alignment(horizontal="center", vertical="center")
                
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})").alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    for i, row in df_f.iterrows():
                        is_f = (row['Status'] == 'Folga')
                        c1, c2 = ws.cell(row_idx, i+2, "FOLGA" if is_f else row['H_Entrada']), ws.cell(row_idx+1, i+2, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border; c1.alignment = c2.alignment = center
                        if is_f: c1.fill = c2.fill = fill_dom if row['Dia'] == 'dom' else fill_folga
                    row_idx += 2
            st.download_button("📥 Baixar Agora", output.getvalue(), "escala_final.xlsx", key="btn_download_excel")
