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
        c = u.get('Categoria', 'Geral'); cats.setdefault(c, []).append(u)
    
    for cat_nome, membros in cats.items():
        mapa_folgas = {i: 0 for i in range(31)}
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == user.get('offset_dom', random.randint(0,1)):
                    df.loc[d_idx, 'Status'] = 'Folga'; mapa_folgas[d_idx] += 1
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx+1, 'Status'] = 'Folga'; mapa_folgas[d_idx+1] += 1
            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                while (df.iloc[sem:fim]['Status'] == 'Folga').sum() < 2:
                    possiveis = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                 not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False) and 
                                 not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False) and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if possiveis:
                        possiveis.sort(key=lambda x: mapa_folgas[x])
                        df.loc[possiveis[0], 'Status'] = 'Folga'; mapa_folgas[possiveis[0]] += 1
                    else: break
            ents, sais = [], []
            hp = user.get("Entrada", "06:00")
            for m in range(len(df)):
                if df.loc[m, 'Status'] == 'Folga': ents.append(""); sais.append("")
                else:
                    e = hp
                    if m > 0 and sais and sais[-1] != "": e = calcular_entrada_segura(sais[-1], hp)
                    ents.append(e); sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df
    return novo_hist

# --- INTERFACE ---
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n, ct = c1.text_input("Nome"), c2.text_input("Categoria")
    h_in = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    s_rk, c_rk = st.checkbox("Rodízio Sábado"), st.checkbox("Folga Casada")
    if st.button("Salvar"):
        st.session_state['db_users'].append({"Nome": n, "Categoria": ct, "Entrada": h_in.strftime('%H:%M'), "Rod_Sab": s_rk, "Casada": c_rk})
        st.success("Salvo!")

with aba2:
    if st.button("🚀 GERAR ESCALA"):
        st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Escala: {nome}"): st.dataframe(df)

with aba3: # RESTAURADA
    st.subheader("⚙️ Ajustes Manuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Selecionar Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Mover Folga")
            d_tira = st.selectbox("Dia para trabalhar:", [d+1 for d in df_e[df_e['Status'] == 'Folga'].index])
            d_poe = st.number_input("Novo dia de folga:", 1, 31)
            if st.button("Confirmar Troca"):
                df_e.loc[d_tira-1, 'Status'], df_e.loc[d_poe-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e; st.rerun()
        with col_b:
            st.markdown("#### Horário e Extra")
            d_h = st.number_input("Dia:", 1, 31, key="dh")
            n_h = st.time_input("Nova Entrada:", key="nh")
            if st.button("Ajustar Horário"):
                df_e.loc[d_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e; st.success("Ajustado!")
            if st.button("Inserir Folga Extra"):
                df_e.loc[d_h-1, 'Status'] = 'Folga'
                st.session_state['historico'][f_ed] = df_e; st.rerun()

with aba4: # RESTAURADA
    st.subheader("📥 Exportar Excel")
    if st.session_state['historico']:
        if st.button("📊 GERAR ARQUIVO"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                wb = writer.book; ws = wb.create_sheet("Escala", index=0)
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
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
                        if is_f: c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("📥 Baixar Planilha", output.getvalue(), "escala.xlsx")
