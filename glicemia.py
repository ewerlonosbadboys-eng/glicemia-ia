import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz
from io import BytesIO

# Config
fuso = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v37", layout="wide")

# Bancos de Dados
AG, AN = "glic_v37.csv", "nutri_v37.csv"
ALIM = {
    "Pao": [28,4,1], "Leite": [10,6,6], "Arroz": [5,1,0],
    "Feijao": [5,2,0], "Frango": [0,23,5], "Ovo": [1,6,5],
    "Banana": [22,1,0], "Maca": [15,0,0], "Iogurte": [15,5,3], "Bolacha": [8,1,2]
}

def load(f): return pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()

def cor(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: yellow; color: black'
        if n > 180: return 'background-color: red; color: white'
        return 'background-color: green; color: white'
    except: return ""

st.title("Saude Kids v37")
tab1, tab2 = st.tabs(["Glicemia", "Alimentos"])

with tab1:
    v = st.number_input("Valor:", min_value=0)
    m = st.selectbox("Momento:", ["Jejum","Pos-Cafe","Ant-Alm","Pos-Alm","Merenda","Ant-Jan","Pos-Jan","Noite"])
    if st.button("Salvar Glic"):
        now = datetime.now(fuso)
        df = pd.concat([load(AG), pd.DataFrame([[now.strftime("%d/%m"), now.strftime("%H:%M"), v, m]], columns=["D","H","V","M"])])
        df.to_csv(AG, index=False)
        st.rerun()
    d_g = load(AG)
    if not d_g.empty:
        st.line_chart(d_g.set_index('H')['V'])
        d_g['X'] = d_g['V'].astype(str) + " (" + d_g['H'] + ")"
        st.dataframe(d_g.pivot_table(index='D', columns='M', values='X', aggfunc='last').fillna("-").style.applymap(cor))

with tab2:
    col_a, col_b = st.columns(2)
    with col_a:
        r = st.selectbox("Refeição:", ["Cafe","Lanche M","Almoco","Merenda","Janta","Lanche N"])
        esc = st.multiselect("Itens:", list(ALIM.keys()))
        ct, pt, gt = sum([ALIM[i][0] for i in esc]), sum([ALIM[i][1] for i in esc]), sum([ALIM[i][2] for i in esc])
        st.info(f"C:{ct}g | P:{pt}g | G:{gt}g")
        if st.button("Salvar Nutri"):
            if esc:
                now = datetime.now(fuso)
                dfn = pd.concat([load(AN), pd.DataFrame([[now.strftime("%d/%m"), r, ", ".join(esc), ct, pt, gt]], columns=["D","R","I","C","P","G"])])
                dfn.to_csv(AN, index=False)
                st.rerun()
    with col_b:
        d_n = load(AN)
        if not d_n.empty:
            d_n["Info"] = d_n["I"] + " (C:" + d_n["C"].astype(str) + " P:" + d_n["P"].astype(str) + " G:" + d_n["G"].astype(str) + ")"
            st.dataframe(d_n.pivot_table(index='D', columns='R', values='Info', aggfunc='last').fillna("-"))

if st.button("Excel"):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as wr:
        load(AG).to_excel(wr, sheet_name='G')
        load(AN).to_excel(wr, sheet_name='N')
    st.download_button("Baixar", out.getvalue(), file_name="Dados.xlsx")
