import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import pytz

# 1. Configuracoes Iniciais
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v27", layout="wide")

ARQ_G = "dados_glicemia_v27.csv"
ARQ_N = "dados_nutricao_v27.csv"

# Banco de Alimentos
ALIMENTOS = {
    "Pao Frances": 135, "Leite (200ml)": 120, "Arroz (colher)": 25, 
    "Feijao (colher)": 30, "Frango (file)": 160, "Ovo": 80,
    "Banana": 90, "Maca": 60, "Iogurte": 110, "Bolacha (un)": 50
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        # REGRA DE OURO: Valores baixos (10, 20, 50...) SEMPRE AMARELO
        if n < 70: return 'background-color: #FFFF00; color: black'
        if n > 180: return 'background-color: #FF0000; color: white'
        if n > 140: return 'background-color: #FFFF00; color: black'
        return 'background-color: #00FF00; color: black'
    except: return ""

st.title("Monitoramento Saude Kids v27")

aba1, aba2 = st.tabs(["Glicemia", "Alimentacao Detalhada"])

with aba1:
    c1, c2 = st.columns(2)
    with c1:
        v_g = st.number_input("Valor da Glicemia:", min_value=0)
        m_g = st.selectbox("Momento:", ["Antes Cafe", "Apos Cafe", "Antes Almoco", "Apos Almoco", "Antes Merenda", "Antes Janta", "Apos Janta", "Madrugada"])
        if st.button("Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_g, m_g]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    
    dfg = carregar(ARQ_G)
    if not dfg.empty:
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(pivot.style.applymap(cor_glicemia), use_container_width=True)

with aba2:
    st.subheader("O que ela comeu hoje?")
    col_a, col_b = st.columns([1, 2])
    with col_a:
        ref = st.selectbox("Refeicao:", ["Cafe da Manha", "Lanche Manha", "Almoco", "Merenda", "Janta", "Lanche Noite"])
        escolha = st.multiselect("Itens:", list(ALIMENTOS.keys()))
        soma = sum([ALIMENTOS[i] for i in escolha])
        st.metric("Total", f"{soma} kcal")
        
        if st.button("Salvar Refeicao"):
            if escolha:
                agora = datetime.now(fuso_br)
                itens_txt = ", ".join(escolha)
                novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), ref, itens_txt, soma]], columns=["Data", "Refeicao", "Itens", "Kcal"])
                pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
                st.rerun()

    with col_b:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.write("Resumo (Comidas + Calorias):")
            df_v = dfn.copy()
            # Juntando nomes e calorias para o resumo que voce pediu
            df_v["Conteudo"] = df_v["Itens"] + " [" + df_v["Kcal"].astype(str) + " kcal]"
            res_tab = df_v.pivot_table(index='Data', columns='Refeicao', values='Conteudo', aggfunc='last').fillna("-")
            st.dataframe(res_tab, use_container_width=True)

if st.button("Baixar Excel para o Medico"):
    dg = carregar(ARQ_G); dn = carregar(ARQ_N)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not dg.empty: dg.to_excel(writer, sheet_name='Glicemia', index=False)
        if not dn.empty: dn.to_excel(writer, sheet_name='Alimentacao', index=False)
    st.download_button("Clique para Baixar", output.getvalue(), file_name="Relatorio_Saude.xlsx")
