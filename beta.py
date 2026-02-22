import streamlit as st
import pandas as pd
from datetime import datetime
import os
import pytz

# ================= CONFIGURAÇÕES =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Beta - Glicemia Inteligente", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# ================= LÓGICA DE CÁLCULO DA RECEITA =================
def calcular_dose_automatica(valor, momento):
    df_r = carregar(ARQ_R)
    # Se não houver configuração, usa os valores da foto que você mandou
    if df_r.empty:
        v_r = {'m1': 3, 'm2': 4, 'm3': 5, 'n1': 1, 'n2': 2, 'n3': 3}
    else:
        v_r = df_r.iloc[0].to_dict()

    # Define se usa a tabela MANHÃ/ALMOÇO ou JANTAR
    if momento in ["Antes Janta", "Após Janta", "Madrugada"]:
        faixa1, faixa2, faixa3 = v_r['n1'], v_r['n2'], v_r['n3']
    else:
        faixa1, faixa2, faixa3 = v_r['m1'], v_r['m2'], v_r['m3']

    # Lógica dos intervalos
    if valor < 70: return "0 UI", "⚠️ Glicemia Baixa! Tratar hipo."
    elif 70 <= valor <= 200: return f"{int(faixa1)} UI", "Faixa 70-200"
    elif 201 <= valor <= 400: return f"{int(faixa2)} UI", "Faixa 201-400"
    else: return f"{int(faixa3)} UI", "Faixa acima de 400"

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
    .card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #e2e8f0; }
    .dose-destaque { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ================= ABAS =================
tab1, tab2 = st.tabs(["📊 Medir Glicemia", "⚙️ Configurar Receita"])

# --- ABA 2: CONFIGURAÇÃO DA RECEITA (PARA VOCÊ ALTERAR) ---
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Configuração da Tabela Médica")
    st.write("Altere os valores abaixo sempre que o doutor mudar a receita.")
    
    df_r = carregar(ARQ_R)
    vals = df_r.iloc[0].to_dict() if not df_r.empty else {'m1': 3, 'm2': 4, 'm3': 5, 'n1': 1, 'n2': 2, 'n3': 3}

    col1, col2 = st.columns(2)
    with col1:
        st.info("**☀️ Café, Almoço e Merenda**")
        m1 = st.number_input("Dose 70-200 (Manhã):", value=int(vals['m1']), key="m1")
        m2 = st.number_input("Dose 201-400 (Manhã):", value=int(vals['m2']), key="m2")
        m3 = st.number_input("Dose > 400 (Manhã):", value=int(vals['m3']), key="m3")
    
    with col2:
        st.info("**🌙 Jantar e Madrugada**")
        n1 = st.number_input("Dose 70-200 (Noite):", value=int(vals['n1']), key="n1")
        n2 = st.number_input("Dose 201-400 (Noite):", value=int(vals['n2']), key="n2")
        n3 = st.number_input("Dose > 400 (Noite):", value=int(vals['n3']), key="n3")

    if st.button("💾 Salvar Nova Receita"):
        pd.DataFrame([{'m1': m1, 'm2': m2, 'm3': m3, 'n1': n1, 'n2': n2, 'n3': n3}]).to_csv(ARQ_R, index=False)
        st.success("Receita atualizada! Agora o cálculo seguirá estes novos valores.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 1: MEDIÇÃO E CÁLCULO ---
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.2])
    
    with c1:
        st.subheader("📝 Lançar Medida")
        v_glic = st.number_input("Glicemia atual (mg/dL):", min_value=0, value=100)
        mom = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        
        # CÁLCULO AUTOMÁTICO
        dose, aviso = calcular_dose_automatica(v_glic, mom)
        
        st.markdown(f"""
        <div class="dose-destaque">
            <p style="margin:0; color: #166534; font-weight: bold;">Sugestão de Aplicação:</p>
            <h1 style="margin:0; color: #15803d; font-size: 50px;">{dose}</h1>
            <small style="color: #166534;">{aviso}</small>
        </div>
        """, unsafe_allow_html=True)

        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            dfg = carregar(ARQ_G)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_glic, mom, dose]], 
                                columns=["Data", "Hora", "Valor", "Momento", "Dose"])
            pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo no histórico!")

    with c2:
        st.subheader("📋 Últimos Registros")
        dfg = carregar(ARQ_G)
        if not dfg.empty:
            st.dataframe(dfg.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
