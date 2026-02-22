import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz
from io import BytesIO

# 1. Setup e Fuso
fuso = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v40", layout="wide")

# Arquivos e Alimentos (Carbo, Prot, Gord)
AG, AN = "glic_v40.csv", "nutri_v40.csv"
ALIM = {
    "Pao Frances": [28,4,1], "Leite (200ml)": [10,6,6], "Arroz (colher)": [5,1,0],
    "Feijao (colher)": [5,2,0], "Frango (file)": [0,23,5], "Ovo": [1,6,5],
    "Banana": [22,1,0], "Maca": [15,0,0], "Iogurte": [15,5,3], "Bolacha (un)": [8,1,2]
}

def load(f): return pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()

def cor_g(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: yellow; color: black'
        if n > 180: return 'background-color: red; color: white'
        return 'background-color: green; color: white'
    except: return ""

st.title("Monitoramento Saude Kids v40")
t1, t2 = st.tabs(["Glicemia", "Alimentacao"])

with t1:
    v_g = st.number_input("Valor:", min_value=0)
    m_g = st.selectbox("Momento:", ["Antes Cafe", "Apos Cafe", "Antes Almoco", "Apos Almoco", "Antes Merenda", "Antes Janta", "Apos Janta", "Madrugada"])
    if st.button("Salvar Glicemia"):
        now = datetime.now(fuso)
        df = pd.concat([load(AG), pd.DataFrame([[now.strftime("%d/%m"), now.strftime("%
