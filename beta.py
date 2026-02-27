import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
import sqlite3
import smtplib
from email.mime.text import MIMEText
import random
import string
import zipfile
import shutil
from pathlib import Path

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =========================================================
# COOKIE (não quebra se não tiver pacote)
# =========================================================
try:
    import extra_streamlit_components as stx
    cookie_manager = stx.CookieManager()
    HAS_COOKIE = True
except:
    cookie_manager = None
    HAS_COOKIE = False

COOKIE_KEY = "SK_LOGIN"
COOKIE_DIAS = 30

# ================= CONFIGURAÇÕES =================
fuso_br = pytz.timezone("America/Sao_Paulo")
st.set_page_config(page_title="Saúde Kids", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia.csv"
ARQ_N = "dados_nutricao.csv"
ARQ_R = "config_receita.csv"

# ================= UTIL =================
def agora():
    return datetime.now(fuso_br)

def norm_email(x):
    return (x or "").strip().lower()

def norm_senha(x):
    return (x or "").strip()

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("usuarios.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            nome TEXT,
            email TEXT PRIMARY KEY,
            senha TEXT
        )
    """)
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador','admin','542820')")
    conn.commit()
    conn.close()

init_db()

# ================= LOGIN =================
if "logado" not in st.session_state:
    st.session_state.logado = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if not st.session_state.logado and HAS_COOKIE:
    ck = cookie_manager.get(COOKIE_KEY)
    if ck:
        st.session_state.logado = True
        st.session_state.user_email = ck

if not st.session_state.logado:
    st.title("🔐 Login")

    email = norm_email(st.text_input("Email"))
    senha = norm_senha(st.text_input("Senha", type="password"))

    if st.button("Entrar"):
        conn = sqlite3.connect("usuarios.db")
        ok = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (email, senha)).fetchone()
        conn.close()

        if ok:
            st.session_state.logado = True
            st.session_state.user_email = email
            if HAS_COOKIE:
                cookie_manager.set(COOKIE_KEY, email, expires_at=timedelta(days=COOKIE_DIAS))
            st.rerun()
        else:
            st.error("Login inválido")

    st.stop()

# ================= FUNÇÕES RECEITA =================
def carregar_receita():
    if not os.path.exists(ARQ_R):
        return None
    df = pd.read_csv(ARQ_R)
    df = df[df["Usuario"] == st.session_state.user_email]
    if df.empty:
        return None
    return df.iloc[0]

def calc_rapida(valor, momento):
    rec = carregar_receita()
    if rec is None:
        return "0 UI", "Configurar"

    periodo = "manha" if momento in ["Antes Café","Antes Almoço"] else "noite"

    try:
        f1_min = rec[f"{periodo}_f1_min"]
        f1_max = rec[f"{periodo}_f1_max"]
        f1_dose = rec[f"{periodo}_f1_dose"]

        f2_min = rec[f"{periodo}_f2_min"]
        f2_max = rec[f"{periodo}_f2_max"]
        f2_dose = rec[f"{periodo}_f2_dose"]

        if valor < 70:
            return "0 UI","Hipoglicemia"

        if f1_min <= valor <= f1_max:
            return f"{int(f1_dose)} UI","Faixa 1"
        if f2_min <= valor <= f2_max:
            return f"{int(f2_dose)} UI","Faixa 2"

        return "0 UI","Fora faixa"
    except:
        return "0 UI","Erro"

def calc_longa(momento):
    rec = carregar_receita()
    if rec is None:
        return "0 UI","Configurar"

    if momento == "Antes Café":
        return f"{int(rec.get('longa_cafe',0))} UI","Longa (Antes Café)"
    if momento == "Antes Janta":
        return f"{int(rec.get('longa_janta',0))} UI","Longa (Antes Janta)"

    return "—","Não aplicável"

# ================= TABS =================
tab1, tab2, tab3 = st.tabs(["📊 Glicemia","⚙️ Receita","📄 Relatórios"])

# ================= GLICEMIA =================
with tab1:
    valor = st.number_input("Valor Glicemia",0,600,100)
    momento = st.selectbox("Momento",[
        "Antes Café","Após Café","Antes Almoço","Após Almoço",
        "Antes Janta","Após Janta","Madrugada"
    ])

    MOMENTOS_RAPIDA = ["Antes Café","Antes Almoço","Antes Janta"]
    MOMENTOS_LONGA = ["Antes Café","Antes Janta"]

    if momento in MOMENTOS_RAPIDA:
        dose_r,msg = calc_rapida(valor,momento)
        st.metric("⚡ Rápida",dose_r)

    if momento in MOMENTOS_LONGA:
        dose_l,msg2 = calc_longa(momento)
        st.metric("🩸 Longa",dose_l)

# ================= RECEITA =================
with tab2:
    st.subheader("⚡ Rápida")

    m1_min = st.number_input("Manhã Min",value=70)
    m1_max = st.number_input("Manhã Max",value=150)
    m1_dose = st.number_input("Manhã Dose",value=3)

    n1_min = st.number_input("Noite Min",value=70)
    n1_max = st.number_input("Noite Max",value=150)
    n1_dose = st.number_input("Noite Dose",value=3)

    st.subheader("🩸 Longa")

    longa_cafe = st.number_input("Longa Antes Café",value=10)
    longa_janta = st.number_input("Longa Antes Janta",value=10)

    if st.button("Salvar Receita"):
        nova = pd.DataFrame([{
            "Usuario":st.session_state.user_email,
            "manha_f1_min":m1_min,"manha_f1_max":m1_max,"manha_f1_dose":m1_dose,
            "noite_f1_min":n1_min,"noite_f1_max":n1_max,"noite_f1_dose":n1_dose,
            "longa_cafe":longa_cafe,
            "longa_janta":longa_janta
        }])
        base = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        base = base[base["Usuario"] != st.session_state.user_email] if not base.empty else base
        pd.concat([base,nova]).to_csv(ARQ_R,index=False)
        st.success("Salvo!")

# ================= RELATÓRIOS =================
with tab3:

    if st.button("📥 Gerar Excel"):
        df = pd.DataFrame({"Exemplo":[1,2,3]})
        buffer = BytesIO()
        with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
            df.to_excel(writer,index=False)
        st.download_button("Baixar Excel",buffer.getvalue(),"relatorio.xlsx")

    if st.button("📄 Gerar PDF"):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer,pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("Relatório Saúde Kids",styles["Title"]))
        story.append(Spacer(1,12))

        data = [["Exemplo"],["1"],["2"],["3"]]
        tbl = Table(data)
        tbl.setStyle(TableStyle([("GRID",(0,0),(-1,-1),1,colors.grey)]))
        story.append(tbl)

        doc.build(story)
        st.download_button("Baixar PDF",buffer.getvalue(),"relatorio.pdf")

# ================= LOGOUT =================
if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.session_state.user_email = ""
    if HAS_COOKIE:
        cookie_manager.delete(COOKIE_KEY)
    st.rerun()
