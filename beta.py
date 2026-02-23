import streamlit as st
import pandas as pd
from datetime import datetime
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

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# DESIGN DARK MODE (PRESERVANDO CORES DE STATUS)
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; }
</style>
""", unsafe_allow_html=True)

def cor_glicemia_status(v):
    try:
        n = int(v)
        if n < 70: return 'background-color: #8B8000; color: white;' 
        elif n > 180: return 'background-color: #8B0000; color: white;' 
        else: return 'background-color: #006400; color: white;' 
    except: return ''

# ================= SEGURANÇA E LOGIN =================
def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit(); conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])
    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("Incorreto.")
            conn.close()
    with abas_login[1]:
        n_cad = st.text_input("Nome")
        e_cad = st.text_input("E-mail Cadastro")
        s_cad = st.text_input("Senha Cadastro", type="password")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit(); conn.close()
                st.success("Conta criada!")
            except: st.error("Erro.")
    st.stop()

# ================= FUNÇÕES DE APOIO =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty: return "0 UI", "Configurar Receita"
    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    try:
        if v < 70: return "0 UI", "Hipoglicemia!"
        elif v <= 200: d = rec[f'{periodo}_f1']
        elif v <= 400: d = rec[f'{periodo}_f2']
        else: d = rec[f'{periodo}_f3']
        return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"
    except: return "0 UI", "Erro na Receita"

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]
ALIMENTOS = {"Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6], "Arroz": [15, 1, 0], "Feijão": [14, 5, 0], "Frango": [0, 23, 5], "Ovo": [1, 6, 5], "Banana": [22, 1, 0]}

# ================= INTERFACE PRINCIPAL =================
tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    c1, c2 = st.columns([1, 2])
    with c1:
        v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
        m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
        dose, msg_d = calc_insulina(v_gl, m_gl)
        st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty:
            fig = px.line(dfg.tail(10), x='Hora', y='Valor', markers=True, title="Tendência")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
            st.plotly_chart(fig, use_container_width=True)
    if not dfg.empty:
        st.dataframe(dfg.tail(15).style.applymap(cor_glicemia_status, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfn = carregar_dados_seguro(ARQ_N)
    m_nutri = st.selectbox("Refeição", MOMENTOS_ORDEM, key="n_m")
    sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
    c_tot, p_tot, g_tot = sum([ALIMENTOS[x][0] for x in sel]), sum([ALIMENTOS[x][1] for x in sel]), sum([ALIMENTOS[x][2] for x in sel])
    c1, c2, c3 = st.columns(3)
    c1.metric("C", f"{c_tot}g"); c2.metric("P", f"{p_tot}g"); c3.metric("G", f"{g_tot}g")
    if st.button("💾 Salvar Refeição"):
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], columns=["Usuario","Data","Momento","Info","C","P","G"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
    st.dataframe(dfn.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Configuração de Receita")
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
    v = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    cm, cn = st.columns(2)
    with cm:
        m1 = st.number_input("Manhã 70-200", value=int(v.get('manha_f1',0)), key="m1")
        m2 = st.number_input("Manhã 201-400", value=int(v.get('manha_f2',0)), key="m2")
        m3 = st.number_input("Manhã > 400", value=int(v.get('manha_f3',0)), key="m3")
    with cn:
        n1 = st.number_input("Noite 70-200", value=int(v.get('noite_f1',0)), key="n1")
        n2 = st.number_input("Noite 201-400", value=int(v.get('noite_f2',0)), key="n2")
        n3 = st.number_input("Noite > 400", value=int(v.get('noite_f3',0)), key="n3")
    if st.button("💾 Salvar Receita"):
        nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':m1, 'manha_f2':m2, 'manha_f3':m3, 'noite_f1':n1, 'noite_f2':n2, 'noite_f3':n3}])
        df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Salva!")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO (RESTAURADO IGUAL AO BETA 15) =================
st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Colorido"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_e_g.empty:
            pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Valor', aggfunc='last')
            # Garante a ordem das colunas
            cols = [c for c in MOMENTOS_ORDEM if c in pivot.columns]
            pivot = pivot[cols]
            pivot.to_excel(writer, sheet_name='Glicemia')
            
            ws = writer.sheets['Glicemia']
            f_v = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid") # Verde
            f_r = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid") # Vermelho
            f_a = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid") # Amarelo
            
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value:
                        try:
                            val = int(cell.value)
                            cell.alignment = Alignment(horizontal='center')
                            if val < 70: cell.fill = f_a
                            elif val > 180: cell.fill = f_r
                            else: cell.fill = f_v
                        except: pass
        
        if not df_e_n.empty:
            df_e_n.to_excel(writer, sheet_name='Alimentos', index=False)

    st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name="Relatorio_Colorido.xlsx")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
