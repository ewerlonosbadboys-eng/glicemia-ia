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
st.set_page_config(page_title="Saúde Kids - v15", page_icon="🩸", layout="wide")

# Usando V15 para forçar a nova regra de cores em todos os dados
ARQ_G = "dados_glicemia_v15.csv"
ARQ_N = "dados_nutricao_v15.csv"

ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# --- FUNÇÃO DE CORES PARA O APP (PRIORIDADE BAIXA) ---
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        # A regra de ser menor que 70 tem que vir PRIMEIRO
        if n < 70: return 'background-color: #FFFFE0; color: black'   # AMARELO
        elif n > 180: return 'background-color: #FFB6C1; color: black' # VERMELHO
        elif n > 140: return 'background-color: #FFFFE0; color: black' # AMARELO
        else: return 'background-color: #90EE90; color: black'         # VERDE
    except: return ""

st.title("🩸 Monitoramento Kids v15 - Tudo Colorido Corretamente")

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo!")
            st.rerun()
    with c2:
        dfg = carregar(ARQ_G)
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor', title="Gráfico de Picos", markers=True))

    if not dfg.empty:
        st.subheader("📋 Relatório Médico no App")
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        tab_pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(tab_pivot.style.applymap(cor_glicemia), use_container_width=True)

with t2:
    st.subheader("Diário Nutricional")
    ca1, ca2 = st.columns(2)
    with ca1:
        escolha = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
        carb = sum([ALIMENTOS[i][0] for i in escolha]); prot = sum([ALIMENTOS[i][1] for i in escolha]); gord = sum([ALIMENTOS[i][2] for i in escolha])
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
            st.plotly_chart(px.pie(values=[dfn['C'].sum(), dfn['P'].sum(), dfn['G'].sum()], names=['Carbo', 'Prot', 'Gord'], title="Resumo de Hoje"))

with t3:
    st.camera_input("📸 Foto")

# --- FUNÇÃO EXCEL QUE FORÇA A COR AMARELA PARA VALORES BAIXOS ---
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            
            # Padrões de preenchimento
            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid") # Verde
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid") # Amarelo
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid") # Vermelho
            
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            # Pega o número e garante que ele seja comparado corretamente
                            val_texto = str(cell.value).split(" ")[0]
                            val = int(val_texto)
                            
                            # Lógica FORÇADA: Baixo sempre Amarelo
                            if val < 70: 
                                cell.fill = a_fill
                            elif val > 180: 
                                cell.fill = r_fill
                            elif val > 140: 
                                cell.fill = a_fill
                            else: 
                                cell.fill = v_fill
                        except Exception as e:
                            pass
        if not df_nutri.empty:
            df_nutri.to_excel(writer, index=False, sheet_name='Alimentacao')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR EXCEL COLORIDO DEFINITIVO"):
    dfg = carregar(ARQ_G); dfn = carregar(ARQ_N)
    if not dfg.empty:
        excel_data = gerar_excel_colorido(dfg, dfn)
        st.download_button("Clique para Baixar", excel_data, file_name="Relatorio_Medico_v15.xlsx")
