import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.title("🔐 Login do Sistema")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# --- MEMÓRIA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

# --- FUNÇÕES ---
def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0: diff += 24
        if diff < 11:
            return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except: pass
    return ent_padrao

def gerar_escala_balanceada(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    categorias = {}
    for u in lista_usuarios:
        cat = u.get('Categoria', 'Geral')
        if cat not in categorias: categorias[cat] = []
        categorias[cat].append(u)

    for cat_nome, membros in categorias.items():
        folgas_no_dia = {i: 0 for i in range(31)}
        for idx, user in enumerate(membros):
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Domingos e Casada
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == user.get('offset_dom', random.randint(0,1)):
                    df.loc[d_idx, 'Status'] = 'Folga'
                    folgas_no_dia[d_idx] += 1
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'
                        folgas_no_dia[d_idx + 1] += 1

            # Balanceamento Seg-Sex
            segundas = df[df['Dia'] == 'seg'].index.tolist()
            if 0 not in segundas: segundas.insert(0, 0)
            for i in range(len(segundas)):
                inicio, fim = segundas[i], (segundas[i+1] if i+1 < len(segundas) else 31)
                f_faltam = 2 - (df.iloc[inicio:fim]['Status'] == 'Folga').sum()
                if f_faltam > 0:
                    for _ in range(f_faltam):
                        possiveis = [j for j in range(inicio, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                     not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False) and 
                                     not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False) and
                                     not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                        if possiveis:
                            possiveis.sort(key=lambda x: folgas_no_dia[x])
                            escolha = possiveis[0]
                            df.loc[escolha, 'Status'] = 'Folga'
                            folgas_no_dia[escolha] += 1

            # Horários
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
st.title("📅 Gestão de Escala - Projeto 5x2")
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n, cat = c1.text_input("Nome"), c2.text_input("Categoria")
    h = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    sab, cas = col1.checkbox("Rodízio Sábado"), col2.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar Registro"):
        st.session_state['db_users'] = [u for u in st.session_state['db_users'] if u['Nome'] != n]
        st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas})
        st.success("Salvo!")

with aba2:
    if st.button("🚀 GERAR ESCALA"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_balanceada(st.session_state['db_users'])
            st.success("✅ Escala gerada com balanceamento!")
        else: st.error("Cadastre alguém primeiro.")
    if st.session_state['historico']:
        for nome, df_p in st.session_state['historico'].items():
            with st.expander(f"Ver: {nome}"): st.dataframe(df_p)

with aba3: # ABA AJUSTES - RESTAURADA E COMPLETA
    st.subheader("⚙️ Painel de Ajustes Manuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Selecione o Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_u = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        u_info = st.session_state['db_users'][idx_u]

        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown("### 🏷️ Categoria e Setor")
            n_cat = st.text_input("Nova Categoria:", value=u_info['Categoria'])
            if st.button("Salvar Categoria"):
                st.session_state['db_users'][idx_u]['Categoria'] = n_cat
                st.success("Categoria atualizada!"); st.rerun()

            st.markdown("### 🔄 Mover Folga")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_antigo = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas_atuais])
            d_novo = st.number_input("Mover para o dia:", 1, 31, value=1)
            if st.button("Confirmar Troca de Dia"):
                df_e.loc[d_antigo-1, 'Status'], df_e.loc[d_novo-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga movida!"); st.rerun()

        with c_b:
            st.markdown("### 🕒 Horário Individual")
            dia_h = st.number_input("Escolha o Dia:", 1, 31, key="dia_h_edit")
            n_h = st.time_input("Novo Horário de Entrada:", key="time_h_edit")
            if st.button("Aplicar Novo Horário"):
                df_e.loc[dia_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário alterado!"); st.rerun()

            st.markdown("### ➕ Folga Extra")
            dia_ex = st.number_input("Dia da Folga Adicional:", 1, 31, key="dia_extra")
            if st.button("Dar Folga Extra"):
                df_e.loc[dia_ex-1, 'Status'] = 'Folga'
                df_e.loc[dia_ex-1, 'H_Entrada'], df_e.loc[dia_ex-1, 'H_Saida'] = "", ""
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga extra inserida!"); st.rerun()
    else:
        st.warning("Gere a escala na Aba 2 para habilitar os ajustes.")

with aba4:
    if st.session_state['historico']:
        if st.button("📊 GERAR EXCEL FINAL"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb, ws = writer.book, writer.book.create_sheet("Escala 5x2")
                red, yel = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid"), PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})").alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    for i, row in df_f.iterrows():
                        is_f = (row['Status'] == 'Folga')
                        c1, c2 = ws.cell(row_idx, i+2, "FOLGA" if is_f else row['H_Entrada']), ws.cell(row_idx+1, i+2, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border
                        c1.alignment = c2.alignment = Alignment(horizontal="center")
                        if is_f: c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            st.download_button("📥 BAIXAR AGORA", out.getvalue(), "escala_projeto.xlsx")
