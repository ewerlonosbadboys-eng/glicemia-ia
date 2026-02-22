import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

# ================= CONFIGURAÇÕES BETA =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Glicemia Coly - BETA", page_icon="🧪", layout="wide")

# ARQUIVOS SEPARADOS PARA NÃOESTRAGAR O ORIGINAL
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

COL_MEDICO = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# ================= LÓGICA DE INSULINA =================
def calcular_insulina(valor):
    df_r = carregar(ARQ_R)
    if df_r.empty: return None, "Configure a Receita na aba ao lado."
    alvo = df_r.iloc[0]['alvo']
    sens = df_r.iloc[0]['sensibilidade']
    if valor > alvo:
        dose = (valor - alvo) / sens
        return round(dose, 1), f"({valor} - {alvo}) / {sens}"
    return 0, "Glicemia no alvo."

# ================= ESTILO =================
st.markdown("""
<style>
.card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
.dose-box { background-color: #f0fdf4; padding: 15px; border-radius: 10px; border: 1px solid #16a34a; color: #166534; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

t1, t2, t3, t4 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera", "📜 Receita"])

# ================= ABA GLICEMIA =================
with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    dfg = carregar(ARQ_G)
    
    with c1:
        v = st.number_input("Valor (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", COL_MEDICO)
        
        dose, msg = calcular_insulina(v)
        if v > 0:
            st.markdown(f'<div class="dose-box">Sugestão: {dose} U <br><small>{msg}</small></div>', unsafe_allow_html=True)

        if st.button("💾 Salvar no Beta"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo no Banco de Testes!")
            st.rerun()

    if not dfg.empty:
        st.subheader("📋 Visualização do Relatório (Igual sua foto)")
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        pivot = dfg.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last')
        # Reordena colunas
        cols = [c for c in COL_MEDICO if c in pivot.columns]
        st.dataframe(pivot.reindex(columns=cols).fillna("-"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= ABA RECEITA =================
with t4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Configurar Cálculo")
    df_r = carregar(ARQ_R)
    alvo_atual = df_r.iloc[0]['alvo'] if not df_r.empty else 100
    sens_atual = df_r.iloc[0]['sensibilidade'] if not df_r.empty else 50
    
    na = st.number_input("Alvo:", value=int(alvo_atual))
    ns = st.number_input("Sensibilidade:", value=int(sens_atual))
    if st.button("Salvar Regras"):
        pd.DataFrame([[na, ns]], columns=['alvo', 'sensibilidade']).to_csv(ARQ_R, index=False)
        st.success("Regras Beta Salvas!")
    st.markdown('</div>', unsafe_allow_html=True)
