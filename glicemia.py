import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl import Workbook
from openpyxl.styles import PatternFill

# 1. Configurações
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids v21", page_icon="🩸", layout="wide")

ARQ_G = "dados_glicemia_v21.csv"
ARQ_N = "dados_nutricao_v21.csv"

# Banco de Alimentos: [Carbo, Prot, Gord, CALORIAS]
ALIMENTOS = {
    "Pão Francês": [28, 4, 1, 135], "Leite (200ml)": [10, 6, 6, 120],
    "Arroz (colher)": [5, 1, 0, 25], "Feijão (colher)": [5, 2, 0, 30],
    "Frango (filé)": [0, 23, 5, 160], "Ovo": [1, 6, 5, 80],
    "Banana": [22, 1, 0, 90], "Maçã": [15, 0, 0, 60],
    "Iogurte": [15, 5, 3, 110], "Bolacha (un)": [8, 1, 2, 50]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF00; color: black'
        elif n > 180: return 'background-color: #FF0000; color: white'
        elif n > 140: return 'background-color: #FFFF00; color: black'
        else: return 'background-color: #00FF00; color: black'
    except: return ""

st.title("🩸 Sistema Saúde Kids v21")

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação por Horário", "📸 Câmera"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Valor Glicemia:", min_value=0)
        m = st.selectbox("Momento Glicemia:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    
    dfg = carregar(ARQ_G)
    if not dfg.empty:
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(pivot.style.applymap(cor_glicemia), use_container_width=True)

with t2:
    st.subheader("🍽️ Registro de Refeições")
    ca1, ca2 = st.columns(2)
    with ca1:
        # NOVA ABA DE HORÁRIOS SOLICITADA
        horario_ref = st.selectbox("Selecione a Refeição:", 
            ["Café da Manhã", "Lanche da Manhã", "Almoço", "Merenda/Lanche", "Janta", "Lanche da Noite/Ceia"])
        
        escolha = st.multiselect("Alimentos consumidos:", list(ALIMENTOS.keys()))
        t_cal = sum([ALIMENTOS[i][3] for i in escolha])
        
        st.metric("🔥 TOTAL DE CALORIAS", f"{t_cal} kcal")
        
        if st.button("💾 Salvar Refeição"):
            agora = datetime.now(fuso_br)
            itens_txt = ", ".join(escolha)
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), horario_ref, itens_txt, t_cal]], 
                                 columns=["Data", "Refeicao", "Itens", "Kcal"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success(f"{horario_ref} salvo!")
            st.rerun()

    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.write("📋 Resumo do Dia (Calorias):")
            # Tabela organizada por tipo de refeição
            resumo_n = dfn.pivot_table(index='Data', columns='Refeicao', values='Kcal', aggfunc='sum').fillna(0)
            st.dataframe(resumo_n, use_container_width=True)

with t3:
    st.camera_input("📸 Foto do Prato")

def gerar_excel(dg, dn):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not dg.empty:
            dg['Exibe'] = dg['Valor'].astype(str) + " (" + dg['Hora'] + ")"
            p = dg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            p.to_excel(writer, sheet_name='Glicemia')
        if not dn.empty:
            # Excel agora também terá a separação por refeição
            p_n = dn.pivot_table(index='Data', columns='Refeicao', values='Kcal', aggfunc='sum').fillna(0)
            p_n.to_excel(writer, sheet_name='Alimentacao_Calorias')
            dn.to_excel(writer, index=False, sheet_name='Detalhes_Alimentos')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO COMPLETO"):
    d_g = carregar(ARQ_G); d_n = carregar(ARQ_N)
    if not d_g.empty:
        st.download_button("Baixar Excel", gerar_excel(d_g, d_n), file_name="Relatorio_Saude_v21.xlsx")
