import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# --- MEMÓRIA DO SISTEMA ---
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
        if c not in cats: cats[c] = []
        cats[c].append(u)
    for cat_nome, membros in cats.items():
        mapa_folgas = {i: 0 for i in range(31)}
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == user.get('offset_dom', random.randint(0,1)):
                    df.loc[d_idx, 'Status'] = 'Folga'
                    mapa_folgas[d_idx] += 1
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx+1, 'Status'] = 'Folga'
                        mapa_folgas[d_idx+1] += 1
            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                while (df.iloc[sem:fim]['Status'] == 'Folga').sum() < 2:
                    possiveis = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                 not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False) and 
                                 not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False) and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if possiveis:
                        possiveis.sort(key=lambda x: mapa_folgas[x])
                        esc = possiveis[0]
                        df.loc[esc, 'Status'] = 'Folga'
                        mapa_folgas[esc] += 1
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

# --- INTERFACE FIXA (ABAS 1, 2, 3, 4) ---
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n, cat = c1.text_input("Nome"), c2.text_input("Categoria")
    h = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    sab, cas = st.checkbox("Rodízio Sábado"), st.checkbox("Folga Casada")
    if st.button("Salvar Funcionário"):
        st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas})
        st.success("Salvo!")

with aba2:
    if st.button("🚀 GERAR ESCALA"):
        st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
        st.success("✅ Escala gerada com sucesso!")
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Ver: {nome}"): st.dataframe(df)

with aba3:
    st.subheader("⚙️ Ajustes")
    if st.session_state['historico']:
        f_sel = st.selectbox("Selecione:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_sel]
        c_a, c_b = st.columns(2)
        with c_a:
            nova_cat = st.text_input("Nova Categoria:", key="cat_edit")
            if st.button("Atualizar"): st.success("Atualizado!")
            d_sair = st.number_input("Tirar folga do dia:", 1, 31)
            d_entrar = st.number_input("Mover para dia:", 1, 31)
            if st.button("Trocar"):
                df_e.loc[d_sair-1, 'Status'], df_e.loc[d_entrar-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_sel] = df_e
                st.rerun()
        with c_b:
            dia_h = st.number_input("Dia Horário:", 1, 31)
            n_h = st.time_input("Nova Hora:")
            if st.button("Salvar Hora"):
                df_e.loc[dia_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                st.session_state['historico'][f_sel] = df_e
            if st.button("Folga Extra"):
                df_e.loc[dia_h-1, 'Status'] = 'Folga'
                st.session_state['historico'][f_sel] = df_e
                st.rerun()

with aba4:
    st.subheader("📥 Download Excel")
    if st.session_state['historico']:
        if st.button("📊 GERAR ARQUIVO EXCEL"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Final", index=0)
                # Estilos
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                center = Alignment(horizontal="center", vertical="center")
                
                # Cabeçalho Dias
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    # Nome e Categoria mesclados
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})").alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, row in df_f.iterrows():
                        is_f = (row['Status'] == 'Folga')
                        c1 = ws.cell(row_idx, i+2, "FOLGA" if is_f else row['H_Entrada'])
                        c2 = ws.cell(row_idx+1, i+2, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border
                        c1.alignment = c2.alignment = center
                        if is_f:
                            c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("📥 Clique para Baixar", output.getvalue(), "escala_5x2.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("Gere a escala na Aba 2 primeiro.")
