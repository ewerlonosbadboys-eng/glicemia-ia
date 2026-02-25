import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

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

st.title("📅 Gestão de Escala Profissional")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- FUNÇÃO DE GERAÇÃO ---
def gerar_escala_func(user_dict):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
    dom_idx = df[df['Dia'] == 'dom'].index.tolist()
    for i, d_idx in enumerate(dom_idx):
        if i % 2 == 1:
            df.loc[d_idx, 'Status'] = 'Folga'
            if user_dict.get("Casada") and (d_idx + 1) < 31: df.loc[d_idx + 1, 'Status'] = 'Folga'
    for sem in range(0, 31, 7):
        bloco = df.iloc[sem:min(sem+7, 31)]
        meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
        atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
        while atuais < meta:
            pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
            if not user_dict.get("Rod_Sab"): pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
            p_real = [p for p in pode if not ((p > 0 and df.loc[p-1, 'Status'] == 'Folga') or (p < 30 and df.loc[p+1, 'Status'] == 'Folga'))]
            if not p_real: break
            df.loc[random.choice(p_real), 'Status'] = 'Folga'
            atuais += 1
    df['H_Entrada'] = user_dict.get("Entrada", "06:00")
    df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
    return df

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
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({"Nome": nome, "Categoria": categoria if categoria else "Geral", "Entrada": h_ent_padrao.strftime('%H:%M'), "Rod_Sab": f_sab, "Casada": f_cas})
            st.success(f"✅ {nome} salvo!")

# --- ABA 2: GERAR ---
with aba2:
    if st.session_state['db_users']:
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            st.subheader("Individual")
            f_sel = st.selectbox("Selecione", [u.get('Nome') for u in st.session_state['db_users']])
            if st.button("✨ GERAR APENAS ESTE"):
                u_d = next(u for u in st.session_state['db_users'] if u['Nome'] == f_sel)
                st.session_state['historico'][f_sel] = gerar_escala_func(u_d)
                st.table(st.session_state['historico'][f_sel])
        with c_g2:
            st.subheader("Grupo")
            if st.button("🚀 GERAR ESCALA DE TODOS"):
                for u in st.session_state['db_users']: st.session_state['historico'][u['Nome']] = gerar_escala_func(u)
                st.success("Escalas do grupo geradas!")

# --- ABA 3: AJUSTES ---
with aba3:
    if st.session_state['db_users']:
        f_ed = st.selectbox("Editar:", [u.get('Nome') for u in st.session_state['db_users']])
        u_ix = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        n_cat = st.text_input("Nova Categoria:", value=st.session_state['db_users'][u_ix].get('Categoria', ''))
        if st.button("💾 Salvar Categoria"):
            st.session_state['db_users'][u_ix]['Categoria'] = n_cat
            st.rerun()
        if f_ed in st.session_state['historico']:
            st.divider()
            df_e = st.session_state['historico'][f_ed]
            dia = st.number_input("Dia", 1, 31)
            n_h = st.time_input("Entrada")
            if st.button("💾 Aplicar"):
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

# --- ABA 4: DOWNLOAD (INDIVIDUAL E GRUPO) ---
with aba4:
    if st.session_state['historico']:
        c_d1, c_d2 = st.columns(2)
        
        with c_d1:
            st.subheader("Download Individual")
            f_n = st.selectbox("Escolha o funcionário:", list(st.session_state['historico'].keys()))
            if st.button("📥 Baixar Individual"):
                out = io.BytesIO()
                u_cat = next((u.get('Categoria', 'Geral') for u in st.session_state['db_users'] if u['Nome'] == f_n), "Geral")
                with pd.ExcelWriter(out, engine='openpyxl') as writer:
                    df_f = st.session_state['historico'][f_n]
                    ws = writer.book.create_sheet(f_n[:30], index=0)
                    red, yel = PatternFill("FF0000", "solid"), PatternFill("FFFF00", "solid")
                    ws.cell(1, 1, "Categoria"); ws.cell(1, 2, u_cat)
                    ws.cell(2, 1, "Nome"); ws.cell(2, 2, f_n)
                    for i in range(31):
                        ws.cell(3, i+2, i+1).alignment = Alignment(horizontal="center")
                        ws.cell(4, i+2, df_f.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                        is_f = (df_f.iloc[i]['Status'] == 'Folga')
                        c_e = ws.cell(5, i+2, "Folga" if is_f else df_f.iloc[i]['H_Entrada'])
                        c_s = ws.cell(6, i+2, "" if is_f else df_f.iloc[i]['H_Saida'])
                        if is_f: c_e.fill = c_s.fill = red if df_f.iloc[i]['Dia'] == 'dom' else yel
                st.download_button("Clique para Baixar", out.getvalue(), f"escala_{f_n}.xlsx")

        with c_d2:
            st.subheader("Download de Todo o Grupo")
            if st.button("📥 BAIXAR GRUPO COMPLETO"):
                out_g = io.BytesIO()
                with pd.ExcelWriter(out_g, engine='openpyxl') as writer:
                    for nome_f, df_f in st.session_state['historico'].items():
                        u_cat = next((u.get('Categoria', 'Geral') for u in st.session_state['db_users'] if u['Nome'] == nome_f), "Geral")
                        ws = writer.book.create_sheet(nome_f[:30])
                        red, yel = PatternFill("FF0000", "solid"), PatternFill("FFFF00", "solid")
                        ws.cell(1, 1, "Categoria"); ws.cell(1, 2, u_cat)
                        ws.cell(2, 1, "Nome"); ws.cell(2, 2, nome_f)
                        for i in range(31):
                            ws.cell(3, i+2, i+1).alignment = Alignment(horizontal="center")
                            ws.cell(4, i+2, df_f.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                            is_f = (df_f.iloc[i]['Status'] == 'Folga')
                            c_e = ws.cell(5, i+2, "Folga" if is_f else df_f.iloc[i]['H_Entrada'])
                            c_s = ws.cell(6, i+2, "" if is_f else df_f.iloc[i]['H_Saida'])
                            if is_f: c_e.fill = c_s.fill = red if df_f.iloc[i]['Dia'] == 'dom' else yel
                st.download_button("Clique para Baixar Grupo", out_g.getvalue(), "escala_grupo_completo.xlsx")
