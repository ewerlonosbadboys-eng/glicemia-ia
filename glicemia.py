import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz

# Fuso Horário Brasil
fuso_br = pytz.timezone('America/Sao_Paulo')

st.set_page_config(page_title="Saúde Kids - Glicemia e Nutrição", page_icon="🩸", layout="wide")

# Nomes dos arquivos de dados
ARQUIVO_GLIC = "dados_glicemia_v3.csv"
ARQUIVO_NUTRI = "dados_nutricao_v3.csv"

# Banco de Dados de Alimentos
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz (3 colheres)": [15, 1.5, 0],
    "Feijão (1 concha)": [14, 5, 0.5],
    "Frango Grelhado": [0, 23, 5],
    "Banana (1 un)": [22, 1, 0]
}

def carregar_dados(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

st.title("🩸 Monitoramento Integrado para Médico")

tab1, tab2 = st.tabs(["📊 Glicemia", "🍽️ Alimentação"])

# --- ABA 1: GLICEMIA ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        v_glic = st.number_input("Valor da Glicemia:", min_value=0)
        momento = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_glic, momento]], columns=["Data", "Hora", "Valor", "Categoria"])
            pd.concat([carregar_dados(ARQUIVO_GLIC), novo], ignore_index=True).to_csv(ARQUIVO_GLIC, index=False)
            st.success("Salvo com sucesso!")
            st.rerun()
    with col2:
        df_g = carregar_dados(ARQUIVO_GLIC)
        if not df_g.empty:
            hoje = datetime.now(fuso_br).strftime("%d/%m/%Y")
            df_h = df_g[df_g['Data'] == hoje].sort_values('Hora')
            if not df_h.empty:
                st.plotly_chart(px.line(df_h, x='Hora', y='Valor', title="Picos de Glicemia Hoje", markers=True))

# --- ABA 2: ALIMENTAÇÃO ---
with tab2:
    st.subheader("Diário e Gráfico Nutricional")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        ref = st.selectbox("Refeição:", ["Café", "Lanche", "Almoço", "Merenda", "Jantar", "Ceia"])
        itens = st.multiselect("O que ela comeu?", list(ALIMENTOS.keys()))
        c = sum([ALIMENTOS[i][0] for i in itens])
        p = sum([ALIMENTOS[i][1] for i in itens])
        g = sum([ALIMENTOS[i][2] for i in itens])
        st.info(f"Totais desta refeição: Carbo {c}g | Prot {p}g | Gord {g}g")
        if st.button("💾 Salvar Alimentação"):
            agora = datetime.now(fuso_br)
            detalhes = f"{', '.join(itens)} [C:{c} P:{p} G:{g}]"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), ref, detalhes, c, p, g]], columns=["Data", "Ref", "Conteudo", "C", "P", "G"])
            pd.concat([carregar_dados(ARQUIVO_NUTRI), novo_n], ignore_index=True).to_csv(ARQUIVO_NUTRI, index=False)
            st.success("Refeição registrada!")
            st.rerun()
    with col_a2:
        df_n = carregar_dados(ARQUIVO_NUTRI)
        if not df_n.empty:
            fig_pie = px.pie(values=[df_n['C'].sum(), df_n['P'].sum(), df_n['G'].sum()], 
                             names=['Carboidratos', 'Proteínas', 'Gorduras'], 
                             title="O que ela mais consumiu (Total Acumulado)")
            st.plotly_chart(fig_pie, use_container_width=True)

# --- DOWNLOAD EXCEL MÉDICO ---
st.markdown("---")
if st.button("📥 Gerar Relatório Médico (Excel com 2 Abas)"):
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
