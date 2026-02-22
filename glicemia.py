import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz
from io import BytesIO

f = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v42", layout="wide")

# Bancos e Alimentos
G, N = "g42.csv", "n42.csv"
D = {
    "Pao Frances": [28,4,1], "Leite (200ml)": [10,6,6], "Arroz (colher)": [5,1,0],
    "Feijao (colher)": [5,2,0], "Frango (file)": [0,23,5], "Ovo": [1,6,5],
    "Banana": [22,1,0], "Maca": [15,0,0], "Iogurte": [15,5,3], "Bolacha (un)": [8,1,2]
}

def ld(a): return pd.read_csv(a) if os.path.exists(a) else pd.DataFrame()

def cl(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: yellow; color: black'
        if n > 180: return 'background-color: red; color: white'
        return 'background-color: green; color: white'
    except: return ""

st.title("Saude Kids v42")
t1, t2 = st.tabs(["Glicemia", "Alimentacao"])

with t1:
    vg = st.number_input("Valor:", min_value=0)
    mg = st.selectbox("Momento:", ["Antes Cafe","Apos Cafe","Antes Almoco","Apos Almoco","Antes Merenda","Antes Janta","Apos Janta","Madrugada"])
    if st.button("Salvar Glic"):
        h = datetime.now(f)
        df = pd.concat([ld(G), pd.DataFrame([[h.strftime("%d/%m"), h.strftime("%H:%M"), vg, mg]], columns=["D","H","V","M"])])
        df.to_csv(G, index=False)
        st.rerun()
    dg = ld(G)
