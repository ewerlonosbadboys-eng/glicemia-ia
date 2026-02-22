import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl import Workbook
from openpyxl.styles import PatternFill

# 1. Configurações e Arquivos
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids v20", page_icon="🩸", layout="wide")

ARQ_G = "dados_glicemia_v20.csv"
ARQ_N = "dados_nutricao_v20.csv"

# Banco de Alimentos: [Carbo, Prot, Gord, CALORIAS]
ALIMENTOS = {
    "Pão Francês": [28, 4, 1, 135], 
    "Leite (200ml)": [10, 6, 6, 120],
    "Arroz (colher)": [5, 1, 0, 25], 
    "Feijão (colher)": [5, 2, 0, 30],
    "Frango (filé)": [0, 23, 5, 160], 
    "Ovo": [1, 6, 5, 80],
    "Banana": [22, 1, 0, 90], 
    "Maçã": [15, 0, 0, 60]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        # PRIORIDADE: Valores baixos (Hipoglicemia) sempre AMARELO
        if n < 70: return 'background-color: #FFFF00; color: black'
        elif n > 180: return 'background-color: #FF0000; color: white'
        elif n > 140: return 'background-color: #FFFF00; color: black'
        else: return 'background-color: #00FF00; color: black'
    except: return ""

st.title("🩸 Monitoramento Saúde Kids v20")

t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        v = st.number_input("Valor Glicemia:", min_value=0)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([carregar(ARQ_G), novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    
    dfg = carregar(ARQ_G)
    with c2:
        if not dfg.empty:
            st.plotly_chart(px.line(dfg.tail(10), x='Hora', y='Valor', title="Evolução", markers=True))

    if not dfg.empty:
        st.subheader("📋 Relatório Médico (Cores Corrigidas)")
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(pivot.style.applymap(cor_glicemia), use_container_width=True)

with t2:
    st.subheader("🔥 Contador de Calorias")
    ca1, ca2 = st.columns(2)
    with ca1:
        escolha = st.multiselect("Alimentos selecionados:", list(ALIMENTOS.keys()))
        t_cal = sum([ALIMENTOS[i][3] for i in escolha])
        st.metric("Total de Calorias", f"{t_cal} kcal")
        if st.button("💾 Salvar Refeição"):
            agora = datetime.now(fuso_br)
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), ", ".join(escolha), t_cal]], columns=["Data", "Itens", "Kcal"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()
    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            st.write("Últimos Registros:")
            st.table(dfn.tail(5))

with t3:
    st.camera_input("📸 Foto")

# Função Excel com as mesmas cores do App
def gerar_excel(dg, dn):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not dg.empty:
            dg['Exibe'] = dg['Valor'].astype(str) + " (" + dg['Hora'] + ")"
            p = dg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            p.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            am = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
            vd = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
            vm = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            n = int(str(cell.value).split(" ")[0])
                            if n < 70: cell.fill = am
                            elif n > 180: cell.fill = vm
                            elif n > 140: cell.fill = am
                            else: cell.fill = vd
                        except: pass
        if not dn.empty:
            dn.to_excel(writer, index=False, sheet_name='Alimentacao')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO MÉDICO"):
    d_g = carregar(ARQ_G); d_n = carregar(ARQ_N)
    if not d_g.empty:
        st.download_button("Clique aqui para baixar", gerar_excel(d_g, d_n), file_name="Relatorio_v20.xlsx")
