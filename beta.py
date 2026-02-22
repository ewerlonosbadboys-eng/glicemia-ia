import streamlit as st
import pandas as pd
from datetime import datetime
import os
import plotly.express as px
import pytz

# ================= CONFIGURAÇÕES =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Beta - Receita Fixa", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# ================= LÓGICA DA RECEITA MÉDICA (TABELA) =================
def calcular_insulina_lispro(valor, momento):
    # Regra para CAFÉ DA MANHÃ E ALMOÇO
    if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"]:
        if 70 <= valor <= 200: return "3 UI"
        elif 201 <= valor <= 400: return "4 UI"
        elif valor > 400: return "5 UI"
        return "0 UI (Glicemia baixa)"
    
    # Regra para JANTAR
    elif momento in ["Antes Janta", "Após Janta", "Madrugada"]:
        if 70 <= valor <= 200: return "1 UI"
        elif 201 <= valor <= 400: return "2 UI"
        elif valor > 400: return "3 UI"
        return "0 UI (Glicemia baixa)"
    
    return "Selecione o momento"

# ================= INTERFACE =================
st.markdown("<h1 style='text-align: center;'>🧪 Glicemia Coly - Teste de Receita</h1>", unsafe_allow_html=True)

# Exibição da Receita Atual para conferência
with st.expander("📋 Ver Tabela da Receita Médica Carregada"):
    st.write("**Café da Manhã e Almoço:** 70-200: 3UI | 201-400: 4UI | >401: 5UI")
    st.write("**Jantar:** 70-200: 1UI | 201-400: 2UI | >401: 3UI")

st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("📝 Lançar Medida")
    v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0, value=100)
    m = st.selectbox("Momento da Medida:", [
        "Antes Café", "Após Café", "Antes Almoço", "Após Almoço", 
        "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"
    ])
    
    # Cálculo em tempo real baseado na foto da receita
    dose_sugerida = calcular_insulina_lispro(v, m)
    
    st.markdown(f"""
    <div style="background-color: #e8f5e9; padding: 20px; border-radius: 10px; border-left: 5px solid #2e7d32;">
        <h3 style="margin:0; color: #2e7d32;">💉 Aplicar Insulina LISPRO:</h3>
        <h1 style="margin:0; color: #1b5e20;">{dose_sugerida}</h1>
        <p style="margin:0; font-size: 0.8em;">Baseado na prescrição médica para {m}.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("💾 Salvar no Histórico Beta"):
        agora = datetime.now(fuso_br)
        dfg = carregar(ARQ_G)
        novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose_sugerida]], 
                            columns=["Data", "Hora", "Valor", "Momento", "Dose"])
        pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
        st.success("Dados salvos no ambiente de testes!")

with c2:
    st.subheader("📊 Últimas Medidas (BETA)")
    dfg = carregar(ARQ_G)
    if not dfg.empty:
        st.dataframe(dfg.tail(10), use_container_width=True)
    else:
        st.info("Nenhum dado salvo no Beta ainda.")
