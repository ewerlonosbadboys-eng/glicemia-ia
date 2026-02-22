import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import pytz

# 1. Configuracoes Iniciais
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v33", layout="wide")

ARQ_G = "dados_glicemia_v33.csv"
ARQ_N = "dados_nutricao_v33.csv"

# Banco de Alimentos Original: [Carbo, Prot, Gord, Kcal]
ALIMENTOS = {
    "Pao Frances": [28, 4, 1, 135], 
    "Leite (200ml)": [10, 6, 6, 120], 
    "Arroz (colher)": [5, 1, 0, 25], 
    "Feijao (colher)": [5, 2, 0, 30], 
    "Frango (file)": [0, 23, 5, 160], 
    "Ovo": [1, 6, 5, 80],
    "Banana": [22, 1, 0, 90], 
    "Maca": [15, 0, 0, 60], 
    "Iogurte": [15, 5, 3, 110], 
    "Bolacha (un)": [8, 1, 2, 50]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF00; color: black' # Amarelo para 10 ou baixos
        if n > 180: return 'background-color: #FF0000; color: white'
        if n > 140: return 'background-color: #FFFF00; color: black'
        return 'background-color: #00FF00; color: black'
    except: return ""

st.title("🩸 Sistema Saude Kids v33")

# Voltei com as Abas Originais
aba1, aba2 = st.tabs(["📊 Glicemia", "🍽️ Alimentacao"])

with aba1:
    c1, c2 = st.columns([1, 2])
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
        # Grafico de Picos que voce tinha
        st.line_chart(dfg.set_index('Hora')['Valor'])
        
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.write("### Relatorio Medico Diario")
        st.dataframe(pivot.style.applymap(cor_glicemia), use_container_width=True)

with aba2:
    st.header("Registro de Refeicoes")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        ref = st.selectbox("Selecione a Refeicao:", ["Cafe da Manha", "Lanche Manha", "Almoco", "Merenda", "Janta", "Lanche Noite"])
        escolha = st.multiselect("Alimentos consumidos:", list(ALIMENTOS.keys()))
        
        c_t = sum([ALIMENTOS[i][0] for i in escolha])
        p_t = sum([ALIMENTOS[i][1] for i in escolha])
        g_t = sum([ALIMENTOS[i][2] for i in escolha])
        cal_t = sum([ALIMENTOS[i][3] for i in escolha])
        
        st.metric("Total de Calorias", f"{cal_t} kcal")
        
        if st.button("Salvar Refeicao"):
            if escolha:
                agora = datetime.now(fuso_br)
                itens_txt = ", ".join(escolha)
                novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), ref, itens_txt, c_t, p_t, g_t, cal_t]], 
                                     columns=["Data", "Refeicao", "Itens", "Carbo", "Prot", "Gord", "Kcal"])
                pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
                st.rerun()

    with col_b:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.write("### Resumo Detalhado")
            df_v = dfn.copy()
            # AQUI ESTA O QUE VOCE PEDIU: Nome em cima, Macros embaixo
            df_v["Conteudo"] = (
                df_v["Itens"] + "\n" +
                "Carbo: " + df_v["Carbo"].astype(str) + "g | " +
                "Prot: " + df_v["Prot"].astype(str) + "g | " +
                "Gord: " + df_v["Gord"].astype(str) + "g"
            )
            res_tab = df_v.pivot_table(index='Data', columns='Refeicao', values='Conteudo', aggfunc='last').fillna("-")
            st.write(res_tab) # O st.write mantem as linhas embaixo uma da outra

if st.button("BAIXAR RELATORIO COMPLETO (EXCEL)"):
    dg = carregar(ARQ_G); dn = carregar(ARQ_N)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not dg.empty: dg.to_excel(writer, sheet_name='Glicemia', index=False)
        if not dn.empty: dn.to_excel(writer, sheet_name='Nutricao', index=False)
    st.download_button("Clique para Baixar", output.getvalue(), file_name="Saude_Kids_Relatorio.xlsx")
