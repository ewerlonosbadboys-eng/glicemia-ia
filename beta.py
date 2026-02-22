import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

# ================= CONFIGURAÇÕES =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# ARQUIVOS BETA (Para não misturar com o original)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

MOMENTOS = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# ================= LÓGICA DE INSULINA =================
def calcular_insulina(v_glic):
    df_r = carregar(ARQ_R)
    if df_r.empty:
        return None, "Configure a Receita na aba ao lado."
    alvo = df_r.iloc[0]['alvo']
    sens = df_r.iloc[0]['sensibilidade']
    if v_glic > alvo:
        dose = (v_glic - alvo) / sens
        return round(dose, 1), f"({v_glic} - {alvo}) / {sens}"
    return 0, "Glicemia no alvo."

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-box { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("🧪 Glicemia Coly - BETA")

# ================= ABAS =================
t1, t2, t3, t4 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera", "📜 Receita Médica"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    dfg = carregar(ARQ_G)

    with c1:
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", MOMENTOS)
        
        if v > 0:
            dose, msg = calcular_insulina(v)
            if dose is not None:
                st.markdown(f'<div class="dose-box"><h2 style="color:#166534; margin:0;">💉 {dose} Unidades</h2><small>{msg}</small></div>', unsafe_allow_html=True)
            else:
                st.warning(msg)

        if st.button("💾 Salvar Registro BETA"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], 
                                columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo no Banco de Testes!")
            st.rerun()

    with c2:
        if not dfg.empty:
            dfg['DH'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            fig = px.line(dfg.tail(10), x='DH', y='Valor', markers=True, title="Evolução Beta")
            st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with t4:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Configurar Parâmetros Médicos")
    df_r = carregar(ARQ_R)
    alvo_v = df_r.iloc[0]['alvo'] if not df_r.empty else 100
    sens_v = df_r.iloc[0]['sensibilidade'] if not df_r.empty else 50
    
    col_a, col_s = st.columns(2)
    with col_a:
        novo_alvo = st.number_input("Alvo Glicêmico:", value=int(alvo_v))
    with col_s:
        nova_sens = st.number_input("Fator de Sensibilidade:", value=int(sens_v))
        
    if st.button("💾 Salvar Configuração"):
        pd.DataFrame([[novo_alvo, nova_sens]], columns=['alvo', 'sensibilidade']).to_csv(ARQ_R, index=False)
        st.success("Configuração de Receita salva no BETA!")
    st.markdown('</div>', unsafe_allow_html=True)
