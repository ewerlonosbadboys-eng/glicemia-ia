import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl import Workbook
from openpyxl.styles import PatternFill

# 1. Configurações de Fuso Horário e Página
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Monitoramento Kids - Completo", page_icon="🩸", layout="wide")

# Arquivos de dados (Versão 11 para resetar erros anteriores)
ARQ_G = "dados_glicemia_v11.csv"
ARQ_N = "dados_nutricao_v11.csv"

# Banco de Alimentos
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# Função de Cores para a Tabela do App
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n <= 140: return 'background-color: #90EE90; color: black' # Verde
        if n <= 180: return 'background-color: #FFFFE0; color: black' # Amarelo
        return 'background-color: #FFB6C1; color: black' # Vermelho
    except: return ""

st.title("🩸 Sistema Completo: Glicemia, Alimentação e Câmera")

# Criando as Abas
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

# --- ABA 1: GLICEMIA ---
with t1:
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Glicemia salva!")
            st.rerun()
    with c2:
        dfg = carregar(ARQ_G)
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor', title="Gráfico de Picos", markers=True))

    st.subheader("📋 Relatório Médico Diário (Com Cores)")
    if not dfg.empty:
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        tab_pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(tab_pivot.style.applymap(cor_glicemia), use_container_width=True)

# --- ABA 2: ALIMENTAÇÃO ---
with t2:
    st.subheader("Diário Nutricional")
    ca1, ca2 = st.columns(2)
    with ca1:
        escolha = st.multiselect("Alimentos consumidos:", list(ALIMENTOS.keys()))
        carb = sum([ALIMENTOS[i][0] for i in escolha]); prot = sum([ALIMENTOS[i][1] for i in escolha]); gord = sum([ALIMENTOS[i][2] for i in escolha])
        st.info(f"Totais da refeição: Carbo: {carb}g | Prot: {prot}g | Gord: {gord}g")
        if st.button("💾 Salvar Refeição"):
            agora = datetime.now(fuso_br)
            txt = f"{', '.join(escolha)} (C:{carb} P:{prot} G:{gord})"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), txt, carb, prot, gord]], columns=["Data", "Info", "C", "P", "G"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Alimentação salva!")
            st.rerun()
    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.plotly_chart(px.pie(values=[dfn['C'].sum(), dfn['P'].sum(), dfn['G'].sum()], names=['Carboidratos', 'Proteínas', 'Gorduras'], title="Equilíbrio Nutricional Total"))

# --- ABA 3: CÂMERA ---
with t3:
    st.subheader("📸 Registro por Foto")
    st.camera_input("Tirar Foto")

# --- FUNÇÃO DO EXCEL COLORIDO ---
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            # Definição das cores para o Excel
            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid") # Verde
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid") # Amarelo
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid") # Vermelho
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            val = int(str(cell.value).split(" ")[0])
                            if val <= 140: cell.fill = v_fill
                            elif val <= 180: cell.fill = a_fill
                            else: cell.fill = r_fill
                        except: pass
        if not df_nutri.empty:
            df_nutri.to_excel(writer, index=False, sheet_name='Alimentacao')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO MÉDICO COLORIDO (Excel)"):
    dfg = carregar(ARQ_G); dfn = carregar(ARQ_N)
    if not dfg.empty:
        excel_data = gerar_excel_colorido(dfg, dfn)
        st.download_button("Clique aqui para baixar", excel_data, file_name="Relatorio_Saude.xlsx")
