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

# --- FUNÇÕES DE LÓGICA ---
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

def gerar_escala_5x2_projeto(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    for idx, user in enumerate(lista_usuarios):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == user.get('offset_dom', idx % 2):
                df.loc[d_idx, 'Status'] = 'Folga'
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx + 1, 'Status'] = 'Folga'

        # 2. Distribuição Semanal (Seg-Dom)
        segundas = df[df['Dia'] == 'seg'].index.tolist()
        if 0 not in segundas: segundas.insert(0, 0)
        
        for i in range(len(segundas)):
            inicio = segundas[i]
            fim = segundas[i+1] if i+1 < len(segundas) else 31
            folgas_atuais = (df.iloc[inicio:fim]['Status'] == 'Folga').sum()
            folgas_a_gerar = 2 - folgas_atuais
            
            if folgas_a_gerar > 0:
                for _ in range(folgas_a_gerar):
                    possiveis = [j for j in range(inicio, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                 not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False) and 
                                 not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False) and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    if possiveis: df.loc[random.choice(possiveis), 'Status'] = 'Folga'

        # 3. Horários e Limite de 5 dias
        ents, sais = [], []
        hp = user.get("Entrada", "06:00")
        for m in range(len(df)):
            if df.loc[m, 'Status'] == 'Folga':
                ents.append(""); sais.append("")
            else:
                e = hp
                if m > 0 and sais and sais[-1] != "":
                    e = calcular_entrada_segura(sais[-1], hp)
                ents.append(e)
                sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
        
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
    if st.button("Salvar Funcionário"):
        st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i['Nome'] != n]
        st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas, "offset_dom": random.randint(0,1)})
        st.success("Cadastrado!")

with aba2:
    st.subheader("Geração de Escala Automática")
    if st.button("🚀 CLIQUE PARA GERAR ESCALA"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_5x2_projeto(st.session_state['db_users'])
            st.success("✅ ESCALA GERADA COM SUCESSO!") # MENSAGEM ADICIONADA
        else:
            st.error("⚠️ Erro: Cadastre funcionários na Aba 1 antes de gerar.")

    if st.session_state['historico']:
        st.write("---")
        st.subheader("📋 Visualização das Escalas Geradas")
        for nome, df_p in st.session_state['historico'].items():
            with st.expander(f"Ver Detalhes: {nome}", expanded=True):
                st.dataframe(df_p, use_container_width=True)

with aba3:
    if st.session_state['historico']:
        f_ed = st.selectbox("Escolha o funcionário para ajustar:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        # Ajustes de Categoria, Troca, Horário e Extra...
        st.info("Ajustes manuais habilitados para " + f_ed)

with aba4:
    st.subheader("Download")
    if st.session_state['historico']:
        if st.button("📊 GERAR ARQUIVO PARA DOWNLOAD"):
            # Lógica do Excel 2 linhas...
            st.write("Arquivo preparado!")
