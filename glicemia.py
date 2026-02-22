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

st.set_page_config(page_title="Saúde Integrada", page_icon="🩸", layout="wide")

ARQUIVO_GLIC = "historico_glicemia.csv"
ARQUIVO_NUTRI = "historico_nutricao.csv"

# --- BANCO DE DADOS DE ALIMENTOS ---
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
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

st.title("🩸 Monitoramento Glicêmico e Alimentar")
tab1, tab2 = st.tabs(["📊 Glicemia", "🍽️ Alimentação"])

# --- ABA 1: GLICEMIA ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        v_man = st.number_input("Valor da Glicemia:", min_value=0)
        cat_g = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_man, cat_g]], columns=["Data", "Hora", "Valor", "Categoria"])
            pd.concat([carregar_dados(ARQUIVO_GLIC), novo], ignore_index=True).to_csv(ARQUIVO_GLIC, index=False)
            st.rerun()
    with col2:
        df_g = carregar_dados(ARQUIVO_GLIC)
        if not df_g.empty:
            df_hoje = df_g[df_g['Data'] == datetime.now(fuso_br).strftime("%d/%m/%Y")].sort_values('Hora')
            if not df_hoje.empty:
                st.plotly_chart(px.line(df_hoje, x='Hora', y='Valor', title="Picos de Glicemia Hoje", markers=True))

# --- ABA 2: ALIMENTAÇÃO ---
with tab2:
    st.subheader("Diário e Gráficos de Nutrientes")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        refeicao = st.selectbox("Refeição:", ["Café", "Lanche Manhã", "Almoço", "Merenda", "Janta", "Ceia"])
        escolhidos = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
        tc = sum([ALIMENTOS[i][0] for i in escolhidos])
        tp = sum([ALIMENTOS[i][1] for i in escolhidos])
        tg = sum([ALIMENTOS[i][2] for i in escolhidos])
        st.info(f"Totais - Carbo: {tc}g | Prot: {tp}g | Gord: {tg}g")
        if st.button("💾 Salvar Refeição"):
            agora = datetime.now(fuso_br)
            txt = f"{', '.join(escolhidos)} [C:{tc}g P:{tp}g G:{tg}g]"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), refeicao, txt, tc, tp, tg]], columns=["Data", "Ref", "Conteudo", "C", "P", "G"])
            pd.concat([carregar_dados(ARQUIVO_NUTRI), novo_n], ignore_index=True).to_csv(ARQUIVO_NUTRI, index=False)
            st.rerun()
    with col_a2:
        df_n = carregar_dados(ARQUIVO_NUTRI)
        if not df_n.empty:
            fig_pie = px.pie(values=[df_n['C'].sum(), df_n['P'].sum(), df_n['G'].sum()], names=['Carbos', 'Proteína', 'Gordura'], title="O que ela mais consumiu (Total)")
            st.plotly_chart(fig_pie, use_container_width=True)

# --- BOTÃO DOWNLOAD EXCEL (2 ABAS) ---
st.markdown("---")
if st.button("📥 Gerar Relatório Médico Completo"):
    df_g = carregar_dados(ARQUIVO_GLIC)
    df_n = carregar_dados(ARQUIVO_NUTRI)
    if not df_g.empty:
        df_g['Exibe'] = df_g['Valor'].astype(str) + " (" + df_g['Hora'] + ")"
        rel_g = df_g.pivot_table(index='Data', columns='Categoria', values='Exibe', aggfunc='last').reset_index()
        rel_n = df_n.pivot_table(index='Data', columns='Ref', values='Conteudo', aggfunc='last').reset_index() if not df_n.empty else pd.DataFrame()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            rel_g.to_excel(writer, index=False, sheet_name='Glicemia')
            if not rel_n.empty: rel_n.to_excel(writer, index=False, sheet_name='Alimentacao')
        st.download_button("Clique aqui para baixar", output.getvalue(), file_name="Relatorio_Medico.xlsx")

if st.sidebar.button("🗑️ Resetar Tudo (Limpar Erros)"):
    if os.path.exists(ARQUIVO_GLIC): os.remove(ARQUIVO_GLIC)
    if os.path.exists(ARQUIVO_NUTRI): os.remove(ARQUIVO_NUTRI)
    st.rerun()
