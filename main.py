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
        
        # 1. Definir Domingos (Folga 1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == user.get('offset_dom', idx % 2):
                df.loc[d_idx, 'Status'] = 'Folga'
                # Regra da Caixinha: Folga Casada (Dom + Seg)
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Distribuição das Folgas por Semana (Seg-Dom)
        segundas = df[df['Dia'] == 'seg'].index.tolist()
        if 0 not in segundas: segundas.insert(0, 0)
        
        for i in range(len(segundas)):
            inicio = segundas[i]
            fim = segundas[i+1] if i+1 < len(segundas) else 31
            
            # Conta folgas já existentes no bloco (Dom ou Casada)
            folgas_atuais = (df.iloc[inicio:fim]['Status'] == 'Folga').sum()
            folgas_a_gerar = 2 - folgas_atuais
            
            if folgas_a_gerar > 0:
                for _ in range(folgas_a_gerar):
                    possiveis = []
                    for j in range(inicio, fim):
                        if df.loc[j, 'Status'] == 'Trabalho':
                            # Bloqueio de folgas juntas
                            v_ant = df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False
                            v_prox = df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False
                            
                            if not v_ant and not v_prox:
                                # Regra Crítica: Só folga Sábado se a caixinha estiver marcada
                                if df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"):
                                    continue
                                possiveis.append(j)
                    
                    if possiveis:
                        df.loc[random.choice(possiveis), 'Status'] = 'Folga'

        # 3. Trava de 5 dias corridos
        contador = 0
        for k in range(len(df)):
            if df.loc[k, 'Status'] == 'Trabalho':
                contador += 1
                if contador > 5:
                    # Tenta forçar folga se não for quebrar a regra de folgas juntas
                    df.loc[k, 'Status'] = 'Folga'
                    contador = 0
            else:
                contador = 0

        # 4. Horários e Interjornada
        ents, sais = [], []
        hp = user.get("Entrada", "06:00")
        for m in range(len(df)):
            if df.loc[m, 'Status'] == 'Folga':
                ents.append(""); sais.append("")
            else:
                e = hp
                if m > 0 and sais[m-1] != "":
                    e = calcular_entrada_segura(sais[m-1], hp)
                ents.append(e)
                sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
        
        df['H_Entrada'], df['H_Saida'] = ents, sais
        novo_hist[nome] = df
    return novo_hist

# --- INTERFACE ---
with aba1:
    st.subheader("Cadastro de Funcionários")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome")
    cat = c2.text_input("Categoria")
    h = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    sab = col1.checkbox("Rodízio de Sábado (Permitir Folga no Sáb)")
    cas = col2.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar"):
        st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i['Nome'] != n]
        st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas, "offset_dom": random.randint(0,1)})
        st.success(f"{n} cadastrado com sucesso!")

with aba2:
    if st.button("🚀 GERAR ESCALA PROJETADA"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_5x2_projeto(st.session_state['db_users'])
            st.success("Escala gerada seguindo todas as regras de bloqueio!")
        else: st.warning("Cadastre alguém antes.")
    
    if st.session_state['historico']:
        for nome, df_p in st.session_state['historico'].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df_p)

with aba3:
    if st.session_state['historico']:
        f_ed = st.selectbox("Ajustar funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        u_info = next(u for u in st.session_state['db_users'] if u['Nome'] == f_ed)

        c_a, c_b = st.columns(2)
        with c_a:
            st.subheader("🏷️ Categoria")
            n_cat = st.text_input("Nova Categoria:", value=u_info['Categoria'])
            if st.button("Salvar Categoria"):
                for u in st.session_state['db_users']:
                    if u['Nome'] == f_ed: u['Categoria'] = n_cat
                st.rerun()

            st.subheader("🔄 Mover Folga")
            fols = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_v = st.selectbox("Tirar folga do dia:", [d+1 for d in fols])
            d_n = st.number_input("Colocar folga no dia:", 1, 31)
            if st.button("Trocar Folga"):
                df_e.loc[d_v-1, 'Status'], df_e.loc[d_n-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.success("Troca realizada!"); st.rerun()

        with c_b:
            st.subheader("🕒 Horário")
            dia_h = st.number_input("Dia:", 1, 31, key="dia_h")
            n_h = st.time_input("Novo Horário:", key="time_h")
            if st.button("Alterar"):
                df_e.loc[dia_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.rerun()

with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL"):
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
            st.download_button("Salvar Arquivo", out.getvalue(), "escala_projeto_5x2.xlsx")
