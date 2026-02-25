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

st.title("📅 Gestão de Escala com Troca de Folgas")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- LÓGICA DE GERAÇÃO COM TRAVA DE 5 DIAS ---
def gerar_escalas_balanceadas(lista_usuarios):
    datas = pd.date_range(start='2026-03-02', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    usuarios_ordenados = sorted(lista_usuarios, key=lambda x: x.get('Categoria', 'Geral'))

    for idx, user in enumerate(usuarios_ordenados):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos (1x1)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        offset_dom = user.get('offset_dom', idx % 2) 
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == offset_dom:
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Folgas Semanais (Compensação de Domingo)
        dias_possiveis = ['seg', 'ter', 'qua', 'qui', 'sex']
        if user.get("Rod_Sab"): dias_possiveis.append('sáb')
        dia_fixo = dias_possiveis[idx % len(dias_possiveis)]

        for i in range(0, len(df), 7):
            semana = df.iloc[i:i+7]
            if (semana['Status'] == 'Folga').sum() == 0:
                idx_f = semana[semana['Dia'] == dia_fixo].index.tolist()
                if idx_f: df.loc[idx_f[0], 'Status'] = 'Folga'

        # 3. TRAVA ABSOLUTA: MÁXIMO 5 DIAS DE TRABALHO
        contador = 0
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Trabalho':
                contador += 1
            else:
                contador = 0
            
            if contador > 5:
                # Se atingiu 6 dias, obriga folga (evita domingos se possível)
                if df.loc[i, 'Dia'] != 'dom':
                    df.loc[i, 'Status'] = 'Folga'
                    contador = 0

        df['H_Entrada'] = user.get("Entrada", "06:00")
        df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") if df.loc[i, 'Status'] == 'Trabalho' else "" for i, e in enumerate(df['H_Entrada'])]
        novo_historico[nome] = df
        
    return novo_historico

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Cadastrar Novo Funcionário")
    c1, c2 = st.columns(2)
    nome_in = c1.text_input("Nome")
    cat_in = c2.text_input("Categoria")
    h_ent = st.time_input("Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    f_sab = st.checkbox("Rodízio de Sábado")
    f_cas = st.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar"):
        st.session_state['db_users'].append({"Nome": nome_in, "Categoria": cat_in, "Entrada": h_ent.strftime('%H:%M'), "Rod_Sab": f_sab, "Casada": f_cas, "offset_dom": random.randint(0,1)})
        st.success("Salvo!")

# --- ABA 2: GERAR ---
with aba2:
    if st.session_state['db_users']:
        if st.button("🚀 GERAR ESCALA"):
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.success("Escala Gerada!")

# --- ABA 3: AJUSTES ---
with aba3:
    if st.session_state['historico']:
        f_ed = st.selectbox("Editar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        # Funções de troca e horário simplificadas para o exemplo, mantendo a lógica anterior
        st.write(df_e)

# --- ABA 4: DOWNLOAD (COM HORÁRIO DE SAÍDA) ---
with aba4:
    if st.session_state['historico']:
        if st.button("📥 BAIXAR EXCEL"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala")
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                
                # Cabeçalho de Dias
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = Alignment(horizontal="center")
                
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    ws.cell(row_idx, 1, nome).alignment = Alignment(vertical="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, row in df_f.iterrows():
                        col = i + 2
                        is_f = (row['Status'] == 'Folga')
                        # Linha de Entrada
                        c_ent = ws.cell(row_idx, col, "FOLGA" if is_f else row['H_Entrada'])
                        # Linha de Saída (Adicionada)
                        c_sai = ws.cell(row_idx+1, col, "" if is_f else row['H_Saida'])
                        
                        c_ent.border = c_sai.border = border
                        c_ent.alignment = c_sai.alignment = Alignment(horizontal="center")
                        
                        if is_f:
                            c_ent.fill = c_sai.fill = red if row['Dia'] == 'dom' else yel
                    
                    row_idx += 2
            st.download_button("Salvar Arquivo", out.getvalue(), "escala_completa.xlsx")
