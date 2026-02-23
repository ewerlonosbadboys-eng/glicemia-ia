st.markdown("""
<style>

/* FUNDO GERAL */
.stApp {
    background: linear-gradient(135deg, #eef2f7, #f8fafc);
}

/* REMOVE ESPAÇO PADRÃO */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
}

/* CARDS MODERNOS */
.card {
    background: white;
    padding: 28px;
    border-radius: 20px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.05);
    margin-bottom: 25px;
    transition: 0.3s ease-in-out;
}

.card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 30px rgba(0,0,0,0.08);
}

/* MÉTRICAS */
.metric-box {
    background: linear-gradient(145deg, #ffffff, #f1f5f9);
    border: none;
    padding: 20px;
    border-radius: 18px;
    text-align: center;
    box-shadow: inset 0 2px 6px rgba(0,0,0,0.03);
}

.dose-destaque {
    font-size: 40px;
    font-weight: 700;
    color: #059669;
}

/* BOTÕES MODERNOS */
.stButton > button {
    border-radius: 14px;
    border: none;
    background: linear-gradient(90deg, #2563eb, #3b82f6);
    color: white;
    font-weight: 600;
    padding: 10px 20px;
    transition: 0.3s;
}

.stButton > button:hover {
    background: linear-gradient(90deg, #1d4ed8, #2563eb);
    transform: scale(1.03);
}

/* INPUTS */
.stNumberInput input, 
.stTextInput input, 
.stSelectbox div[data-baseweb="select"] {
    border-radius: 12px !important;
}

/* TABS ESTILO APP */
button[role="tab"] {
    border-radius: 12px !important;
    padding: 10px 18px !important;
    font-weight: 600 !important;
}

button[aria-selected="true"] {
    background-color: #2563eb !important;
    color: white !important;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b, #0f172a);
}

section[data-testid="stSidebar"] * {
    color: white !important;
}

/* DATAFRAME MAIS LIMPO */
[data-testid="stDataFrame"] {
    border-radius: 15px;
    overflow: hidden;
}

/* TITULOS */
h1, h2, h3 {
    font-weight: 700;
    color: #0f172a;
}

/* LOGIN */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

</style>
""", unsafe_allow_html=True)
