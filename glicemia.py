import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from openpyxl.styles import PatternFill
import plotly.express as px
import pytz

# Fuso Horário Brasil
fuso_br = pytz.timezone('America/Sao_Paulo')

# IA Config
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia & Nutrição", page_icon="🩸", layout="wide")
st.title("🩸 Monitoramento Completo (Glicemia + Alimentos)")

ARQUIVO_GLIC = "historico_glicemia.csv"
ARQUIVO_NUTRI = "historico_nutricao.csv"

# --- TABELA DE ALIMENTOS ---
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Pão de Forma (1 fatia)": [12, 2, 1],
    "Café com Açúcar": [10, 0, 0],
    "Café com Adoçante": [0, 0, 0],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz (3 colheres)": [15, 1.5, 0],
    "Feijão (1 concha)": [14, 5, 0.5],
    "Frango Grelhado": [0, 23, 5],
    "Ovo Cozido": [1, 6, 5],
    "Maçã (1 un)": [15, 0, 0],
    "Banana (1 un)": [22, 1, 0]
}

def carregar_dados(arq):
    if os.path.isfile(arq):
        df = pd.read_csv(arq)
        return df
    return pd.DataFrame()

# --- ABA 1: GLICEMIA ---
tab1, tab2 = st.tabs(["🩸 Glicemia", "🍽️ Alimentação"])

with tab1:
    st.subheader("Registrar Glicemia")
    col1, col2 = st.columns(2)
    with col1:
        valor_man = st.number_input("Valor:", min_value=0, max_value=600)
        cat_sel = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada", "Extra"])
    with col2:
        foto = st.camera_input("Foto Sensor")

    v_final = valor_man
    if foto and valor_man == 0:
        try:
            img = PIL.Image.open(foto)
            res = "".join(re.findall(r'\d+', model.generate_content(["Número?", img]).text))
            if res: v_final = int(res)
        except: st.error("Erro na foto")

    if v_final > 0:
        cor = "yellow" if v_final <= 69 else "green" if v_final <= 200 else "red"
        st.markdown(f"<h1 style='color:{cor}; text-align:center;'>{v_final} mg/dL</h1>", unsafe_allow_html=True)
        if st.button("💾 SALVAR GLICEMIA"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_final, cat_sel]], columns=["Data", "Hora", "Valor", "Categoria"])
            df_g = carregar_dados(ARQUIVO_GLIC)
            pd.concat([df_g, novo]).to_csv(ARQUIVO_GLIC, index=False)
            st.success("Salvo!")
            st.rerun()

# --- ABA 2: ALIMENTAÇÃO ---
with tab2:
    st.subheader("Contagem de Carboidratos")
    refeicao = st.selectbox("Refeição:", ["Café Manhã", "Lanche Manhã", "Almoço", "Merenda", "Jantar", "Ceia"])
    itens = st.multiselect("O que ela comeu?", list(ALIMENTOS.keys()))
    
    # Cálculos
    c = sum([ALIMENTOS[i][0] for i in itens])
    p = sum([ALIMENTOS[i][1] for i in itens])
    g = sum([ALIMENTOS[i][2] for i in itens])
    
    st.info(f"🍞 Carbos: {c}g | 🥩 Prot: {p}g | 🥑 Gord: {g}g")
    
    if st.button("💾 SALVAR REFEIÇÃO"):
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), refeicao, ", ".join(itens), c, p, g]], columns=["Data", "Refeicao", "Itens", "Carbo", "Prot", "Gord"])
        df_n = carregar_dados(ARQUIVO_NUTRI)
        pd.concat([df_n, novo_n]).to_csv(ARQUIVO_NUTRI, index=False)
        st.success("Alimentos Salvos!")

st.markdown("---")

# --- RELATÓRIOS ---
df_g = carregar_dados(ARQUIVO_GLIC)
if not df_g.empty:
    st.subheader("📈 Picos de Hoje")
    hoje = datetime.now(fuso_br).strftime("%d/%m/%Y")
    df_h = df_g[df_g['Data'] == hoje].sort_values('Hora')
    if not df_h.empty:
        st.plotly_chart(px.line(df_h, x='Hora', y='Valor', markers=True))

    st.subheader("📊 Relatório para o Médico")
    df_g['Exibe'] = df_g['Valor'].astype(str) + " (" + df_g['Hora'] + ")"
    rel = df_g.pivot_table(index='Data', columns='Categoria', values='Exibe', aggfunc='last').reset_index()
    st.dataframe(rel)

    # Botão Reset
    if st.sidebar.button("🗑️ Limpar Tudo (Reset)"):
        if os.path.exists(ARQUIVO_GLIC): os.remove(ARQUIVO_GLIC)
        if os.path.exists(ARQUIVO_NUTRI): os.remove(ARQUIVO_NUTRI)
        st.rerun()
