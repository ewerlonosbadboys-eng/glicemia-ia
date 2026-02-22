import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz

# 1. Configurações Iniciais
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Monitoramento Kids", page_icon="🩸", layout="wide")

# Novo arquivo para limpar erros das fotos
ARQ_G = "dados_g_v9.csv"
ARQ_N = "dados_n_v9.csv"

# Alimentos cadastrados
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n <= 140: return 'background-color: #90EE90' # Verde
        if n <= 180: return 'background-color: #FFFFE0' # Amarelo
        return 'background-color: #FFB6C1' # Vermelho
    except: return ""

st.title("🩸 Sistema Tudo-em-Um: Saúde & Nutrição")

# --- ABAS ---
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Glicemia (mg/dL):", min_value=0)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Janta", "Madrugada"])
        if st.button("💾 Salvar"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo!")
            st.rerun()
    with c2:
        dfg = carregar(ARQ_G)
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor', title="Últimas Medidas", markers=True))

    st.subheader("📋 Tabela Médica Colorida")
    if not dfg.empty:
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        tab = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(tab.style.applymap(cor_glicemia), use_container_width=True)

with t2:
    st.subheader("Resumo Nutricional")
    ca1, ca2 = st.columns(2)
    with ca1:
        escolha = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
        carb = sum([ALIMENTOS[i][0] for i in escolha])
        prot = sum([ALIMENTOS[i][1] for i in escolha])
        gord = sum([ALIMENTOS[i][2] for i in escolha])
        st.info(f"Totais: C:{carb}g | P:{prot}g | G:{gord}g")
        if st.button("💾 Salvar Refeição"):
            agora = datetime.now(fuso_br)
            txt = f"{', '.join(escolha)} (C:{carb} P:{prot} G:{gord})"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), txt, carb, prot, gord]], columns=["Data", "Info", "C", "P", "G"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()
    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.plotly_chart(px.pie(values=[dfn['C'].sum(), dfn['P'].sum(), dfn['G'].sum()], names=['Carbo', 'Prot', 'Gord'], title="Equilíbrio Nutricional"))

with t3:
    st.camera_input("📸 Tirar Foto")

st.markdown("---")
if st.button("📥 BAIXAR EXCEL PARA O MÉDICO"):
    dfg = carregar(ARQ_G); dfn = carregar(ARQ_N)
    if not dfg.empty:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            dfg.to_excel(writer, index=False, sheet_name='Glicemia')
            if not dfn.empty: dfn.to_excel(writer, index=False, sheet_name='Alimentacao')
        st.download_button("Clique aqui para baixar", output.getvalue(), file_name="Relatorio.xlsx")
