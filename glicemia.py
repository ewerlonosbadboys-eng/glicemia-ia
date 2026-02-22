import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz
from io import BytesIO

# Configurações e Categorias do seu Relatório
fuso = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v49 PRO", layout="wide")
ARQ = "glic_v49.csv"
CATS = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

def carregar():
    return pd.read_csv(ARQ) if os.path.exists(ARQ) else pd.DataFrame(columns=["Data","Hora","Valor","Momento"])

def estilo(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70: return 'background-color: #FFFF99' # Amarelo
        if n > 180: return 'background-color: #FFCCCC' # Vermelho
        return 'background-color: #CCFFCC' # Verde
    except: return ""

st.title("🩸 Monitoramento Saude Kids v49")
t1, t2 = st.tabs(["📝 Registro", "📥 Relatório Excel"])

with t1:
    c1, c2 = st.columns([1, 2])
    with c1:
        v = st.number_input("Valor:", min_value=0, value=100)
        m = st.selectbox("Momento:", CATS)
        if st.button("Salvar"):
            ag = datetime.now(fuso)
            nv = pd.DataFrame([[ag.strftime("%d/%m/%Y"), ag.strftime("%H:%M"), v, m]], columns=["Data","Hora","Valor","Momento"])
            pd.concat([carregar(), nv], ignore_index=True).to_csv(ARQ, index=False)
            st.rerun()
    with c2:
        df = carregar()
        if not df.empty: st.dataframe(df.tail(8), use_container_width=True)

with t2:
    df = carregar()
    if not df.empty:
        # Organiza os dados: Data na esquerda e Momentos no topo
        df['X'] = df['Valor'].astype(str) + " (" + df['Hora'] + ")"
        rel = df.pivot_table(index='Data', columns='Momento', values='X', aggfunc='last')
        
        # Garante a ordem correta das colunas conforme seu modelo
        cols = [c for c in CATS if c in rel.columns]
        rel_f = rel.reindex(columns=cols).fillna("-")
