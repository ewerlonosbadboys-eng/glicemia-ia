import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Gestor Escala 2026 - Versão 1x1", layout="wide")

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

# --- LÓGICA DE GERAÇÃO 1x1 REAL ---
def gerar_escalas_balanceadas(lista_usuarios):
    # Definindo o período de Março de 2026
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_historico = {}
    
    # Agrupar por categoria para balanceamento
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
                'Semana_Ano': [d.isocalendar()[1] for d in datas] # Pega o número da semana no ano
            })
            
            # 1. PROCESSAR DOMINGOS (REGRA 1x1)
            for i, row in df.iterrows():
                if row['Dia'] == 'dom':
                    # Se a semana do ano for Par e o user for offset 0 OU Semana Ímpar e user offset 1 -> FOLGA
                    if row['Semana_Ano'] % 2 == user.get('offset_dom', 0):
                        df.loc[i, 'Status'] = 'Folga'
                        mapa_folgas_dia[i] += 1
                        
                        # Aplica Folga Casada (Segunda)
                        if user.get("Casada") and (i + 1) < 31:
                            df.loc[i+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[i+1] += 1

            # 2. COMPLETAR 5x2 (Garantir 2 folgas por semana de 7 dias)
            for sem_inicio in range(0, 31, 7):
                sem_fim = min(sem_inicio + 7, 31)
                folgas_na_semana = len(df.iloc[sem_inicio:sem_fim][df['Status'] == 'Folga'])
                
                while folgas_na_semana < 2:
                    # Busca dias de trabalho que não sejam sábados proibidos
                    possiveis = [j for j in range(sem_inicio, sem_fim) 
                                if df.loc[j, 'Status'] == 'Trabalho' and
                                not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    
                    if not possiveis: break
                    # Escolhe o dia que tem menos gente folgando no setor
                    possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                    escolhido = possiveis[0]
                    df.loc[escolhido, 'Status'] = 'Folga'
                    mapa_folgas_dia[escolhido] += 1
                    folgas_na_semana += 1

            # 3. HORÁRIOS E INTERSTÍCIO
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

# --- INTERFACE Streamlit ---
st.title("📅 Gestor de Escala Profissional - Regra 1x1")
aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "📅 Gerar Escala", "⚙️ Ajustes", "📥 Exportar"])

with aba1:
    st.subheader("Cadastro de Funcionários")
    col1, col2 = st.columns(2)
    n_in = col1.text_input("Nome completo")
    cat_in = col2.text_input("Setor/Categoria")
    h_in = st.time_input("Horário de Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    
    c_folga, c_sab = st.columns(2)
    s_in = c_sab.checkbox("Trabalha aos Sábados?")
    c_in = c_folga.checkbox("Folga Casada (Dom + Seg)?")
    
    if st.button("Adicionar Funcionário"):
        if n_in and cat_in:
            # Alterna automaticamente o grupo do domingo (0 ou 1)
            membros_mesmo_setor = [u for u in st.session_state['db_users'] if u['Categoria'] == cat_in]
            grupo_domingo = len(membros_mesmo_setor) % 2
            
            st.session_state['db_users'].append({
                "Nome": n_in, "Categoria": cat_in, "Entrada": h_in.strftime('%H:%M'), 
                "Rod_Sab": s_in, "Casada": c_in, "offset_dom": grupo_domingo
            })
            st.success(f"✅ {n_in} cadastrado no Grupo {'A' if grupo_domingo==0 else 'B'} de domingos.")

with aba2:
    if st.button("🚀 GERAR ESCALA DE MARÇO/2026"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escalas_balanceadas(st.session_state['db_users'])
            st.balloons()
        else: st.error("Erro: Cadastre os funcionários primeiro.")
    
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Folha de Escala: {nome}"):
                st.table(df[['Data', 'Dia', 'Status', 'H_Entrada', 'H_Saida']])

with aba4:
    if st.session_state['historico']:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala Geral", index=0)
            
            # Estilos
            f_dom = PatternFill(start_color="FFCCCC", end_color="FFCCCC", patternType="solid") # Vermelho claro
            f_folga = PatternFill(start_color="FFFFCC", end_color="FFFFCC", patternType="solid") # Amarelo claro
            center = Alignment(horizontal="center", vertical="center")
            
            # Cabeçalho de Dias
            df_ref = list(st.session_state['historico'].values())[0]
            for i, row in df_ref.iterrows():
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, row['Dia']).alignment = center
            
            # Dados dos funcionários
            row_idx = 3
            for nome, df_f in st.session_state['histor
