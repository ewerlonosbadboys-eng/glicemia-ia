import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
from openpyxl.styles import PatternFill, Alignment

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
        if diff < 11.16: # 11h 10min aprox
            return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except: pass
    return ent_padrao

# --- 3. LÓGICA DE GERAÇÃO ---
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
            # Regra 1x1 Domingo
            for i, row in df.iterrows():
                if row['Dia'] == 'dom':
                    if row['Sem_Ano'] % 2 == user.get('offset_dom', 0):
                        df.loc[i, 'Status'] = 'Folga'
                        mapa_folgas_dia[i] += 1
                        if user.get("Casada") and (i + 1) < 31:
                            df.loc[i+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[i+1] += 1
            # Regra 5x2
            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                f_count = len(df.iloc[sem:fim][df['Status'] == 'Folga'])
                while f_count < 2:
                    possiveis = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if not possiveis: break
                    possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                    df.loc[possiveis[0], 'Status'] = 'Folga'
                    mapa_folgas_dia[possiveis[0]] += 1
                    f_count += 1
            # Horários
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

# --- 4. INTERFACE ---
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📅 Gerar Escala", "⚙️ Ajustes", "📥 Exportar"])

with aba1:
    st.header("Cadastro de Equipe")
    c1, c2 = st.columns(2)
    n_in = c1.text_input("Nome do Funcionário")
    cat_in = c2.text_input("Setor/Categoria")
    h_in = st.time_input("Horário de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    col_x, col_y = st.columns(2)
    s_in = col_x.checkbox("Trabalha Sábados?")
    c_in = col_y.checkbox("Folga Casada (Dom+Seg)?")
    if st.button("Salvar Cadastro"):
        if n_in and cat_in:
            membros = [u for u in st.session_state['db_users'] if u['Categoria'] == cat_in]
            off = len(membros) % 2
            st.session_state['db_users'].append({"Nome": n_in, "Categoria": cat_in, "Entrada": h_in.strftime('%H:%M'), "Rod_Sab": s_in, "Casada": c_in, "offset_dom": off})
            st.success(f"{n_in} cadastrado!")

with aba2:
    if st.button("🚀 Gerar Escala de Março/2026"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Escala gerada com sucesso!")
        else: st.error("Cadastre os funcionários primeiro.")
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Escala: {nome}"):
                st.dataframe(df[['Data', 'Dia', 'Status', 'H_Entrada', 'H_Saida']], use_container_width=True)

with aba3:
    st.header("Ajustes do Sistema")
    if st.session_state['db_users']:
        nomes = [u['Nome'] for u in st.session_state['db_users']]
        f_selecionado = st.selectbox("Selecione para editar:", nomes)
        idx = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_selecionado)
        
        c_alt1, c_alt2 = st.columns(2)
        with c_alt1:
            st.subheader("Dados Cadastrais")
            novo_n = st.text_input("Editar Nome", value=st.session_state['db_users'][idx]['Nome'])
            nova_cat = st.text_input("Editar Setor", value=st.session_state['db_users'][idx]['Categoria'])
            if st.button("Salvar Alterações"):
                st.session_state['db_users'][idx]['Nome'] = novo_n
                st.session_state['db_users'][idx]['Categoria'] = nova_cat
                st.rerun()
            if st.button("🗑️ Remover Funcionário", type="primary"):
                st.session_state['db_users'].pop(idx)
                if f_selecionado in st.session_state['historico']: del st.session_state['historico'][f_selecionado]
                st.rerun()

        with c_alt2:
            if f_selecionado in st.session_state['historico']:
                st.subheader("Trocar Folga Manual")
                df_f = st.session_state['historico'][f_selecionado]
                d_sai = st.selectbox("Tirar folga do dia:", df_f[df_f['Status'] == 'Folga'].index + 1)
                d_entra = st.number_input("Passar folga para o dia:", 1, 31)
                if st.button("Trocar Agora"):
                    df_f.loc[d_sai-1, 'Status'] = 'Trabalho'
                    df_f.loc[d_sai-1, 'H_Entrada'] = st.session_state['db_users'][idx]['Entrada']
                    df_f.loc[d_entra-1, 'Status'] = 'Folga'
                    df_f.loc[d_entra-1, 'H_Entrada'] = ""
                    st.session_state['historico'][f_selecionado] = df_f
                    st.success("Troca realizada!")

    if st.button("⚠️ Limpar Tudo"):
        st.session_state['db_users'] = []
        st.session_state['historico'] = {}
        st.rerun()

with aba4:
    if st.session_state['historico']:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            f_red = PatternFill(start_color="FFCCCC", end_color="FFCCCC", patternType="solid")
            f_yel = PatternFill(start_color="FFFFCC", end_color="FFFFCC", patternType="solid")
            center = Alignment(horizontal="center", vertical="center")
            
            ref = list(st.session_state['historico'].values())[0]
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, ref.iloc[i]['Dia']).alignment = center
            
            curr_row = 3
            for nome, df_p in st.session_state['historico'].items():
                ws.cell(curr_row, 1, nome).alignment = center
                for i, row in df_p.iterrows():
                    val = "FOLGA" if row['Status'] == 'Folga' else row['H_Entrada']
                    c = ws.cell(curr_row, i+2, val)
                    c.alignment = center
                    if row['Status'] == 'Folga':
                        c.fill = f_red if row['Dia'] == 'dom' else f_yel
                curr_row += 1
        st.download_button("📥 Baixar Excel Colorido", out.getvalue(), "escala_correta.xlsx")
