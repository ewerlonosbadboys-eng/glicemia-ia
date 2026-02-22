import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz, shutil
import matplotlib.pyplot as plt
from io import BytesIO

# Configuração e Fuso
fuso = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v34 PRO", layout="wide")
ARQ = "glic_v34.csv"
if not os.path.exists("backup"): os.makedirs("backup")

# Estilo
st.markdown("<style>.card{padding:20px;border-radius:15px;text-align:center;font-size:25px;font-weight:bold;}.verde{background:#C8F7C5;}.amarelo{background:#FFF3B0;}.vermelho{background:#F8C8C8;}</style>", unsafe_allow_html=True)

def carregar(): return pd.read_csv(ARQ) if os.path.exists(ARQ) else pd.DataFrame(columns=["Data","Hora","Valor","Momento"])
def backup(): 
    if os.path.exists(ARQ): shutil.copy(ARQ, f"backup/bkp_{datetime.now(fuso).strftime('%Y%m%d_%H%M%S')}.csv")

st.title("📱 Saúde Kids v34 PRO")
t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🩸 Registro", "📈 Gráfico", "📥 Relatório"])

with t1:
    df = carregar()
    if not df.empty:
        df['dt'] = pd.to_datetime(df['Data'] + " " + df['Hora'], dayfirst=True)
        hj = datetime.now(fuso).strftime("%d/%m/%Y")
        dfh = df[df['Data'] == hj]
        if not dfh.empty:
            c1, c2, c3 = st.columns(3)
            med = round(dfh['Valor'].mean(), 1)
            c1.metric("Média Hoje", f"{med} mg/dL")
            c2.metric("Máxima", dfh['Valor'].max())
            c3.metric("Mínima", dfh['Valor'].min())
            ult = dfh.iloc[-1]['Valor']
            cor = "verde" if 70 <= ult <= 140 else "amarelo" if 140 < ult <= 180 else "vermelho"
            st.markdown(f"<div class='card {cor}'>Última: {ult} mg/dL</div>", unsafe_allow_html=True)
            if ult < 70 or ult > 180: st.warning("⚠️ Atenção: Glicemia fora da meta!")

with t2:
    v = st.number_input("Valor:", min_value=0)
    m = st.selectbox("Momento:", ["Antes Cafe", "Apos Cafe", "Antes Almoco", "Apos Almoco", "Antes Janta", "Apos Janta", "Madrugada"])
    if st.button("Salvar Registro"):
        ag = datetime.now(fuso)
        nv = pd.DataFrame([[ag.strftime("%d/%m/%Y"), ag.strftime("%H:%M"), v, m]], columns=["Data","Hora","Valor","Momento"])
        pd.concat([carregar(), nv], ignore_index=True).to_csv(ARQ, index=False)
        backup(); st.success("Registrado!"); st.rerun()
    st.dataframe(carregar().tail(10), use_container_width=True)

with t3:
    df = carregar()
    if not df.empty:
        fig, ax = plt.subplots()
        ax.plot(df.index, df['Valor'], marker='o', color='blue')
        ax.axhline(70, color='red', linestyle='--')
        ax.axhline(180, color='red', linestyle='--')
        ax.set_title("Evolução Glicêmica")
        st.pyplot(fig)

with t4:
    if st.button("Gerar Excel"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as wr: carregar().to_excel(wr, index=False)
        st.download_button("Download Relatório", out.getvalue(), "Saude_Kids.xlsx")
