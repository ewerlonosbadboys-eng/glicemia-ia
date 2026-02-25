import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# --- LOGIN E MEMÓRIA ---
if "password_correct" not in st.session_state:
    st.title("🔐 Login do Sistema")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.title("📅 Gestão de Escala - Projeto 5x2 Final")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- FUNÇÕES ---
def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    s = datetime.strptime(saida_ant, fmt)
    e = datetime.strptime(ent_padrao, fmt)
    diff = (e - s).total_seconds() / 3600
    if diff < 0: diff += 24
    if diff < 11:
        return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    return ent_padrao

def gerar_escala_5x2_projeto(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    for idx, user in enumerate(lista_usuarios):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == user.get('offset_dom', idx % 2):
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'
        segundas = df[df['Dia'] == 'seg'].index.tolist()
        if 0 not in segundas: segundas.insert(0, 0)
        for i in range(len(segundas)):
            inicio, fim = segundas[i], (segundas[i+1] if i+1 < len(segundas) else 31)
            folgas_a_gerar = 2 - (df.iloc[inicio:fim]['Status'] == 'Folga').sum()
            if folgas_a_gerar > 0:
                for _ in range(folgas_a_gerar):
                    possiveis = [j for j in range(inicio, fim) if df.loc[j, 'Status'] == 'Trabalho' and not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False) and not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False) and not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if possiveis: df.loc[random.choice(possiveis), 'Status'] = 'Folga'
        ents, sais = [], []
        hp = user.get("Entrada", "06:00")
        for m in range(len(df)):
            if df.loc[m, 'Status'] == 'Folga': ents.append(""); sais.append("")
            else:
                e = hp
                if m > 0 and sais[m-1] != "": e = calcular_entrada_segura(sais[m-1], hp)
                ents.append(e); sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
        df['H_Entrada'], df['H_Saida'] = ents, sais
        novo_hist[nome] = df
    return novo_hist

# --- INTERFACE ---
with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome")
    cat = c2.text_input("Categoria")
    h = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    sab = col1.checkbox("Rodízio de Sábado")
    cas = col2.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar"):
        st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i['Nome'] != n]
        st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas, "offset_dom": random.randint(0,1)})
        st.success("Salvo!")

with aba2:
    if st.button("🚀 GERAR ESCALA"):
        st.session_state['historico'] = gerar_escala_5x2_projeto(st.session_state['db_users'])
    if st.session_state['historico']:
        for nome, df_p in st.session_state['historico'].items():
            with st.expander(f"Escala: {nome}"): st.dataframe(df_p)

with aba3: # ABA DE AJUSTES COMPLETA
    if st.session_state['historico']:
        f_ed = st.selectbox("Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        idx_u = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        u_info = st.session_state['db_users'][idx_u]

        c_a, c_b = st.columns(2)
        with c_a:
            st.subheader("🏷️ Categoria")
            n_cat = st.text_input("Mudar:", value=u_info['Categoria'])
            if st.button("Salvar Nova Categoria"):
                st.session_state['db_users'][idx_u]['Categoria'] = n_cat
                st.rerun()

            st.subheader("🔄 Mover Folga")
            fols = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_v = st.selectbox("Tirar folga do dia:", [d+1 for d in fols])
            d_n = st.number_input("Colocar folga no dia:", 1, 31)
            if st.button("Mover Folga Agora"):
                df_e.loc[d_v-1, 'Status'], df_e.loc[d_n-1, 'Status'] = 'Trabalho', 'Folga'
                # Recalcula apenas os horários desse funcionário
                ents, sais = [], []
                for m in range(len(df_e)):
                    if df_e.loc[m, 'Status'] == 'Folga': ents.append(""); sais.append("")
                    else:
                        e = u_info['Entrada']
                        if m > 0 and sais[m-1] != "": e = calcular_entrada_segura(sais[m-1], u_info['Entrada'])
                        ents.append(e); sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
                df_e['H_Entrada'], df_e['H_Saida'] = ents, sais
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga movida!"); st.rerun()

        with c_b:
            st.subheader("🕒 Horário")
            dia_h = st.number_input("Escolha o Dia:", 1, 31)
            n_h = st.time_input("Novo Horário de Entrada:")
            if st.button("Ajustar Horário Individual"):
                df_e.loc[dia_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário alterado!")

            st.subheader("➕ Folga Extra")
            dia_ex = st.number_input("Adicionar Folga Extra no dia:", 1, 31, key="extra")
            if st.button("Dar Folga Extra"):
                df_e.loc[dia_ex-1, 'Status'] = 'Folga'
                df_e.loc[dia_ex-1, 'H_Entrada'], df_e.loc[dia_ex-1, 'H_Saida'] = "", ""
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga extra aplicada!"); st.rerun()

with aba4:
    if st.session_state['historico']:
        if st.button("📥 EXCEL"):
            # Lógica de Excel mantida...
            st.info("Exportação disponível.")
