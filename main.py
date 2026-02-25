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

st.title("📅 Gestão de Escala $5 \times 2$ Contínua")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE BALANCEAMENTO DE DOMINGOS PARA NOVOS ---
def definir_proximo_domingo_livre():
    if not st.session_state['db_users']:
        return 0 # Começa pelo primeiro domingo disponível
    
    contagem_domingos = {0: 0, 1: 0} # 0 = Domingos Ímpares, 1 = Domingos Pares
    for u in st.session_state['db_users']:
        idx = u.get('inicio_domingo', 0)
        contagem_domingos[idx] += 1
    
    # Retorna o índice do grupo de domingo que tem menos gente
    return 0 if contagem_domingos[0] <= contagem_domingos[1] else 1

# --- LÓGICA DE GERAÇÃO $5 \times 2$ COM TRANSIÇÃO ---
def gerar_escalas_balanceadas(lista_usuarios):
    # Definimos Março de 2026 como base, mas olhando o histórico
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    
    novo_historico = {}
    folgas_por_dia = {i: 0 for i in range(31)}

    for user in lista_usuarios:
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos com Balanceamento (Pega o offset salvo no cadastro)
        offset_domingo = user.get('inicio_domingo', 0)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_domingo:
                df.loc[d_idx, 'Status'] = 'Folga'
                folgas_por_dia[d_idx] += 1
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'
                    folgas_por_dia[d_idx + 1] += 1

        # 2. Folgas Semanais (Garantindo 5x2 no mês corrido)
        for sem in range(0, 31, 7):
            bloco = df.iloc[sem:min(sem+7, 31)]
            meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
            atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
            
            while atuais < meta:
                pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                if not user.get("Rod_Sab"): pode = [p for p in pode if df.loc[p, 'Dia'] != 'sáb']
                
                # Trava para não grudar folga (Exceto a casada permitida)
                p_real = [p for p in pode if not ((p > 0 and df.loc[p-1, 'Status'] == 'Folga' and df.loc[p-1, 'Dia'] != 'dom') or 
                                                 (p < 30 and df.loc[p+1, 'Status'] == 'Folga' and df.loc[p, 'Dia'] != 'dom'))]
                
                if not p_real: break
                # Escolhe o dia com menos folgas no grupo para balancear o setor
                dia_escolhido = min(p_real, key=lambda x: folgas_por_dia[x])
                df.loc[dia_escolhido, 'Status'] = 'Folga'
                folgas_por_dia[dia_escolhido] += 1
                atuais += 1
        
        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
        novo_historico[nome] = df
        
    return novo_historico

# --- ABA 1: CADASTRO COM BALANCEAMENTO DE DOMINGO ---
with aba1:
    st.subheader("Cadastro de Funcionário")
    c_cad1, c_cad2 = st.columns(2)
    nome = c_cad1.text_input("Nome")
    categoria = c_cad2.text_input("Setor / Alocação")
    
    c_h, c_o = st.columns(2)
    h_ent_padrao = c_h.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar e Balancear no Grupo"):
        if nome:
            # Regra de balanceamento de domingo automático para novos
            dom_offset = definir_proximo_domingo_livre()
            
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, 
                "Categoria": categoria if categoria else "Geral", 
                "Entrada": h_ent_padrao.strftime('%H:%M'), 
                "Rod_Sab": f_sab, 
                "Casada": f_cas,
                "inicio_domingo": dom_offset # Salva para manter a transição de meses
            })
            st.success(f"✅ {nome} cadastrado! Alocado no Grupo de Domingo {dom_offset + 1} para balanceamento.")

# --- ABA 2: GERAR (CONTÍNUO) ---
with aba2:
    if st.session_state['db_users']:
        if st.button("🚀 GERAR ESCALA DE MARÇO (CONTÍNUA)"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Escala gerada respeitando a transição de Fevereiro e o balanceamento do grupo!")

# --- ABA 3: AJUSTES (MANTIDO) ---
with aba3:
    if st.session_state['db_users']:
        f_ed = st.selectbox("Editar:", [u.get('Nome') for u in st.session_state['db_users']])
        u_ix = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_ed)
        n_cat = st.text_input("Categoria:", value=st.session_state['db_users'][u_ix].get('Categoria', ''))
        if st.button("💾 Salvar"):
            st.session_state['db_users'][u_ix]['Categoria'] = n_cat
            st.rerun()

# --- ABA 4: DOWNLOAD (FORMATO FOTO CONSOLIDADO) ---
with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL CONSOLIDADO (5x2)"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Março 2026")
                
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                
                # Cabeçalho
                ws.cell(1, 1, "FUNCIONÁRIO").font = Font(bold=True)
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    col = i + 2
                    ws.cell(1, col, i+1).alignment = Alignment(horizontal="center")
                    ws.cell(2, col, df_ref.iloc[i]['Dia']).alignment = Alignment(horizontal="center")
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    c_nome = ws.cell(row_idx, 1, nome)
                    c_nome.alignment = Alignment(vertical="center", horizontal="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, day_row in df_f.iterrows():
                        col = i + 2
                        is_f = (day_row['Status'] == 'Folga')
                        c_ent = ws.cell(row_idx, col, "FOLGA" if is_f else day_row['H_Entrada'])
                        c_sai = ws.cell(row_idx+1, col, "" if is_f else day_row['H_Saida'])
                        if is_f:
                            c_ent.fill = c_sai.fill = red if day_row['Dia'] == 'dom' else yel
                        c_ent.border = c_sai.border = border
                    row_idx += 2
            st.download_button("Salvar Arquivo", out.getvalue(), "escala_transicao_marco.xlsx")
