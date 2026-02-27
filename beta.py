import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from io import BytesIO
import pytz
import sqlite3

# =========================================================
# COOKIE OPCIONAL (NÃO QUEBRA SE NÃO TIVER PACOTE)
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

# ================= CONFIG =================
fuso_br = pytz.timezone("America/Sao_Paulo")
st.set_page_config(page_title="Saúde Kids", page_icon="🧪", layout="wide")

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

# Auto login cookie
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

# ================= RECEITA =================
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
        return "0 UI"

    periodo = "manha" if momento in ["Antes Café","Antes Almoço"] else "noite"

    try:
        min_v = rec[f"{periodo}_min"]
        max_v = rec[f"{periodo}_max"]
        dose = rec[f"{periodo}_dose"]

        if min_v <= valor <= max_v:
            return f"{int(dose)} UI"
        return "0 UI"
    except:
        return "0 UI"

def calc_longa(momento):
    rec = carregar_receita()
    if rec is None:
        return "0 UI"

    if momento == "Antes Café":
        return f"{int(rec.get('longa_cafe',0))} UI"
    if momento == "Antes Janta":
        return f"{int(rec.get('longa_janta',0))} UI"
    return "—"

# ================= TABS =================
tab1, tab2, tab3 = st.tabs(["📊 Glicemia","⚙️ Receita","📥 Relatórios"])

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
        st.metric("⚡ Rápida", calc_rapida(valor,momento))

    if momento in MOMENTOS_LONGA:
        st.metric("🩸 Longa", calc_longa(momento))

# ================= RECEITA =================
with tab2:

    st.subheader("⚡ Receita Rápida")

    manha_min = st.number_input("Manhã Min",value=70)
    manha_max = st.number_input("Manhã Max",value=150)
    manha_dose = st.number_input("Manhã Dose",value=3)

    noite_min = st.number_input("Noite Min",value=70)
    noite_max = st.number_input("Noite Max",value=150)
    noite_dose = st.number_input("Noite Dose",value=3)

    st.subheader("🩸 Longa")

    longa_cafe = st.number_input("Longa Antes Café",value=10)
    longa_janta = st.number_input("Longa Antes Janta",value=10)

    if st.button("Salvar Receita"):

        nova = pd.DataFrame([{
            "Usuario":st.session_state.user_email,
            "manha_min":manha_min,
            "manha_max":manha_max,
            "manha_dose":manha_dose,
            "noite_min":noite_min,
            "noite_max":noite_max,
            "noite_dose":noite_dose,
            "longa_cafe":longa_cafe,
            "longa_janta":longa_janta
        }])

        base = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        base = base[base["Usuario"] != st.session_state.user_email] if not base.empty else base
        pd.concat([base,nova]).to_csv(ARQ_R,index=False)

        st.success("Receita salva!")

# ================= RELATÓRIOS =================
with tab3:

    if st.button("📥 Gerar Excel"):
        df = pd.DataFrame({
            "Usuário":[st.session_state.user_email],
            "Data":[agora().strftime("%d/%m/%Y")]
        })

        buffer = BytesIO()
        with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
            df.to_excel(writer,index=False)

        st.download_button("Baixar Excel",buffer.getvalue(),"relatorio.xlsx")

# ================= LOGOUT =================
if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.session_state.user_email = ""
    if HAS_COOKIE:
        cookie_manager.delete(COOKIE_KEY)
    st.rerun()
