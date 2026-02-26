import streamlit as st
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

# --- LÓGICA DE GERAÇÃO INTELIGENTE 5x2 ---
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
        random.shuffle(membros)
        
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            for sem in range(0, 31, 7):
                fim_sem = min(sem + 7, 31)
                folgas_alocadas = 0
                
# --- REGRA DO DOMINGO 1x1 ---
                # Localiza o domingo dentro da semana atual
                doms = [j for j in range(sem, fim_sem) if df.loc[j, 'Dia'] == 'dom']
                for d_idx in doms:
                    # O cálculo % 2 alterna entre as semanas (0, 1, 2, 3...)
                    semana_idx = d_idx // 7
                    if semana_idx % 2 == user.get('offset_dom', 0):
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_alocadas += 1
                        # Se a folga casada estiver ativa, folga a segunda seguinte
                        if user.get("Casada") and (d_idx + 1) < 31:
                            df.loc[d_idx+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[d_idx+1] += 1
                            folgas_alocadas += 1
                        if user.get("Casada") and (d_idx + 1) < 31:
                            df.loc[d_idx+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[d_idx+1] += 1
                            folgas_alocadas += 1
        # ... define a folga
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_alocadas += 1
                        if user.get("Casada") and (d_idx + 1) < 31:
                            df.loc[d_idx+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[d_idx+1] += 1
                            folgas_alocadas += 1

                while folgas_alocadas < 2:
                    possiveis = [j for j in range(sem, fim_sem) if df.loc[j, 'Status'] == 'Trabalho' and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if not possiveis: break
                    possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                    escolhido = possiveis[0]
                    df.loc[escolhido, 'Status'] = 'Folga'
                    mapa_folgas_dia[escolhido] += 1
                    folgas_alocadas += 1

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
st.title("📅 Gestão de Escala - Sistema Completo")
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro de Funcionários")
    c1, c2 = st.columns(2)
    n_in = c1.text_input("Nome")
    cat_in = c2.text_input("Categoria")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    col1, col2 = st.columns(2)
    s_in = col1.checkbox("Trabalha Sábado?")
    c_in = col2.checkbox("Folga Casada (Seguidas)?")
    if st.button("Salvar Funcionário"):
        if n_in and cat_in:
            off = len([u for u in st.session_state['db_users'] if u['Categoria'] == cat_in]) % 2
            st.session_state['db_users'].append({"Nome": n_in, "Categoria": cat_in, "Entrada": h_in.strftime('%H:%M'), "Rod_Sab": s_in, "Casada": c_in, "offset_dom": off})
            st.success(f"{n_in} salvo!")

with aba2:
    if st.button("🚀 GERAR ESCALA FINAL"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Escala Gerada com Sucesso!")
        else: st.warning("Cadastre funcionários primeiro.")
    
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df, use_container_width=True)

with aba3:
    st.subheader("Ajustes Manuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Selecione o Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        
        # Encontrar info do usuário
        u_idx = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        u_info = st.session_state['db_users'][u_idx]

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🔄 Trocar Folga por Trabalho")
            folgas = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_tira = st.selectbox("Tirar folga do dia:", [d+1 for d in folgas])
            d_poe = st.number_input("Mover folga para o dia:", 1, 31)
            if st.button("Confirmar Alteração de Folga"):
                df_e.loc[d_tira-1, 'Status'] = 'Trabalho'
                df_e.loc[d_tira-1, 'H_Entrada'] = u_info['Entrada']
                df_e.loc[d_tira-1, 'H_Saida'] = (datetime.strptime(u_info['Entrada'], "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                
                df_e.loc[d_poe-1, 'Status'] = 'Folga'
                df_e.loc[d_poe-1, 'H_Entrada'] = ""
                df_e.loc[d_poe-1, 'H_Saida'] = ""
                
                st.session_state['historico'][f_ed] = df_e
                st.success("Folga alterada!"); st.rerun()

        with col_b:
            st.markdown("#### 🕒 Ajustar Horário Específico")
            dia_h = st.number_input("Dia do Mês:", 1, 31, key="dia_h")
            nova_h = st.time_input("Nova Entrada:", key="nova_h")
            if st.button("Salvar Novo Horário"):
                df_e.loc[dia_h-1, 'H_Entrada'] = nova_h.strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), nova_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário atualizado!")
        
        st.divider()
        st.subheader("🏷️ Alterar Categoria")
        nova_cat = st.text_input("Nova Categoria:", value=u_info['Categoria'])
        if st.button("Atualizar Categoria"):
            st.session_state['db_users'][u_idx]['Categoria'] = nova_cat
            st.success("Categoria atualizada! Gere a escala novamente para balancear."); st.rerun()

with aba4:
    if st.session_state['historico']:
        if st.button("📊 GERAR EXCEL COLORIDO"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book; ws = wb.create_sheet("Escala", index=0)
                f_red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                f_yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                center = Alignment(horizontal="center", vertical="center", wrap_text=True)
                
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})").alignment = center
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    for i, row in df_f.iterrows():
                        is_f = (row['Status'] == 'Folga')
                        c1, c2 = ws.cell(row_idx, i+2, "FOLGA" if is_f else row['H_Entrada']), ws.cell(row_idx+1, i+2, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border; c1.alignment = c2.alignment = center
                        if is_f: c1.fill = c2.fill = f_red if row['Dia'] == 'dom' else f_yel
                    row_idx += 2
            st.download_button("📥 Baixar Agora", out.getvalue(), "escala_corrigida.xlsx")
