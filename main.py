import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

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

# --- LÓGICA DE GERAÇÃO 1x1 ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    cats = {}
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        cats.setdefault(c, []).append(u)
    
    for cat_nome, membros in cats.items():
        mapa_folgas_dia = {i: 0 for i in range(31)}
        
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({
                'Data': datas, 
                'Dia': [d_pt[d.day_name()] for d in datas], 
                'Status': 'Trabalho',
                'Sem_Ano': [d.isocalendar()[1] for d in datas]
            })
            
            for i, row in df.iterrows():
                if row['Dia'] == 'dom':
                    if row['Sem_Ano'] % 2 == user.get('offset_dom', 0):
                        df.loc[i, 'Status'] = 'Folga'
                        mapa_folgas_dia[i] += 1
                        if user.get("Casada") and (i + 1) < 31:
                            df.loc[i+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[i+1] += 1

            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                folgas_na_sem = len(df.iloc[sem:fim][df['Status'] == 'Folga'])
                while folgas_na_sem < 2:
                    possiveis = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if not possiveis: break
                    possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                    df.loc[possiveis[0], 'Status'] = 'Folga'
                    mapa_folgas_dia[possiveis[0]] += 1
                    folgas_na_sem += 1

            hp = user.get("Entrada", "06:00")
            ents, sais = [], []
            for i in range(len(df)):
                if df.loc[i, 'Status'] == 'Folga':
                    ents.append(""); sais.append("")
                else:
                    e = hp
                    if i > 0 and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], hp)
                    ents.append(e)
                    sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_historico[nome] = df
            
    return novo_historico

# --- INTERFACE ---
st.title("📅 Gestão de Escala 1x1 - 2026")
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📅 Gerar", "⚙️ Ajustes", "📥 Excel"])

with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n_in = c1.text_input("Nome")
    cat_in = c2.text_input("Setor")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    s_in = col1.checkbox("Trabalha Sábado?")
    c_in = col2.checkbox("Folga Casada?")
    if st.button("Salvar"):
        if n_in and cat_in:
            membros = [u for u in st.session_state['db_users'] if u['Categoria'] == cat_in]
            off = len(membros) % 2 
            st.session_state['db_users'].append({"Nome": n_in, "Categoria": cat_in, "Entrada": h_in.strftime('%H:%M'), "Rod_Sab": s_in, "Casada": c_in, "offset_dom": off})
            st.success(f"{n_in} Salvo!")

with aba2:
    if st.button("🚀 Gerar Escala Final"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Gerado!")
        else: st.warning("Cadastre alguém!")
    
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Escala: {nome}"):
                st.dataframe(df[['Data', 'Dia', 'Status', 'H_Entrada', 'H_Saida']])

with aba3:
    st.subheader("Ajustes Manuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Selecione o Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        u_info = next(u for u in st.session_state['db_users'] if u['Nome'] == f_ed)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🔄 Mover Folga")
            folgas_index = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_tira = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas_index])
            d_poe = st.number_input("Mover folga para o dia:", 1, 31)
            if st.button("Confirmar Troca"):
                df_e.loc[d_tira-1, 'Status'] = 'Trabalho'
                df_e.loc[d_tira-1, 'H_Entrada'] = u_info['Entrada']
                df_e.loc[d_tira-1, 'H_Saida'] = (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                
                df_e.loc[d_poe-1, 'Status'] = 'Folga'
                df_e.loc[d_poe-1, 'H_Entrada'] = ""
                df_e.loc[d_poe-1, 'H_Saida'] = ""
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga movida!"); st.rerun()

        with col_b:
            st.markdown("#### 🕒 Alterar Horário")
            dia_h = st.number_input("Dia do Mês:", 1, 31)
            nova_h = st.time_input("Nova Entrada:")
            if st.button("Salvar Horário"):
                df_e.loc[dia_h-1, 'H_Entrada'] = nova_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), nova_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário alterado!"); st.rerun()

with aba4:
    if st.session_state['historico']:
        if st.button("📊 Gerar Planilha"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala", index=0)
                f_red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                f_yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                center = Alignment(horizontal="center", vertical="center")
                
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    ws.cell(row_idx, 1, nome).alignment = center
                    for i, row in df_f.iterrows():
                        is_f = (row['Status'] == 'Folga')
                        cell = ws.cell(row_idx, i+2, "FOLGA" if is_f else row['H_Entrada'])
                        cell.alignment = center
                        if is_f: cell.fill = f_red if row['Dia'] == 'dom' else f_yel
                    row_idx += 1
            st.download_button("📥 Baixar Excel", out.getvalue(), "escala_2026.xlsx")
