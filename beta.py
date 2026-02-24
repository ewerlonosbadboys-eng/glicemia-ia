import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill
import sqlite3

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_F = "feedbacks_BETA.csv"
DB_NAME = "usuarios_v_final_check.db" 

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
</style>
""", unsafe_allow_html=True)

# ================= BANCO DE DADOS =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (nome TEXT, email TEXT PRIMARY KEY, senha TEXT, categoria TEXT)''')
    if not cursor.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        cursor.execute("INSERT INTO users VALUES (?,?,?,?)", ("Administrador", "admin", "542820", "Admin"))
    conn.commit()
    conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

# ================= TELA DE ENTRADA (LIMPA) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Login")
    
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("Bem-vindo ao sistema de controle.")
        st.image("https://cdn-icons-png.flaticon.com/512/3022/3022251.png", width=150) # Ícone decorativo simples

    with col_r:
        abas = st.tabs(["🔐 Login", "📝 Cadastro", "🔄 Senha"])
        with abas[0]:
            u = st.text_input("E-mail", key="l_e")
            s = st.text_input("Senha", type="password", key="l_s")
            if st.button("Entrar", use_container_width=True):
                conn = sqlite3.connect(DB_NAME)
                user = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
                if user:
                    st.session_state.logado, st.session_state.user_email = True, u
                    st.rerun()
                else: st.error("Acesso Negado.")
                conn.close()
        with abas[1]:
            n_c = st.text_input("Nome", key="c_n")
            e_c = st.text_input("E-mail", key="c_e")
            s_c = st.text_input("Senha", type="password", key="c_s")
            cat_c = st.selectbox("Categoria", ["Pai/Mãe", "Médico(a)", "Nutri"], key="c_cat")
            if st.button("Criar Conta", use_container_width=True):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("INSERT INTO users VALUES (?,?,?,?)", (n_c, e_c, s_c, cat_c))
                    conn.commit(); conn.close(); st.success("Sucesso!")
                except: st.error("E-mail já existe.")
        with abas[2]:
            e_a = st.text_input("E-mail", key="a_e")
            s_at = st.text_input("Senha Atual", type="password", key="a_sat")
            s_nv = st.text_input("Nova Senha", type="password", key="a_snv")
            if st.button("Alterar Senha", use_container_width=True):
                conn = sqlite3.connect(DB_NAME)
                if conn.execute("SELECT 1 FROM users WHERE email=? AND senha=?", (e_a, s_at)).fetchone():
                    conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nv, e_a))
                    conn.commit(); st.success("Alterada!")
                conn.close()
    st.stop()

# ================= ÁREA PRIVADA (ADMIN / USUÁRIO) =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Admin Master")
    t1, t2 = st.tabs(["👥 Usuários", "📬 Mensagens"])
    with t1:
        conn = sqlite3.connect(DB_NAME)
        st.dataframe(pd.read_sql_query("SELECT nome, email, categoria FROM users", conn), use_container_width=True)
        conn.close()
    with t2:
        if os.path.exists(ARQ_F):
            st.dataframe(pd.read_csv(ARQ_F), use_container_width=True)
else:
    def carregar(arq):
        if not os.path.exists(arq): return pd.DataFrame()
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()

    tab_g, tab_n, tab_r = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

    with tab_g:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        df_g = carregar(ARQ_G)
        c1, c2 = st.columns([1, 2])
        with c1:
            v = st.number_input("Valor", 0, 600, 100)
            m = st.selectbox("Momento", ["Jejum", "Pré-Refeição", "Pós-Refeição", "Madrugada"])
            if st.button("Salvar Registro"):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Usuario","Data","Hora","Valor","Momento"])
                base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
                pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
        with c2:
            if not df_g.empty:
                st.plotly_chart(px.line(df_g.tail(10), x='Hora', y='Valor', markers=True), use_container_width=True)
                def cor(val):
                    if val < 70: return 'background-color: #8B8000; color: white;'
                    if val > 180: return 'background-color: #8B0000; color: white;'
                    return 'background-color: #006400; color: white;'
                st.dataframe(df_g.tail(10).style.applymap(cor, subset=['Valor']), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_n:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        alims = {"Pão Francês": 28, "Arroz": 10, "Feijão": 14, "Banana": 22}
        sel = st.multiselect("Alimentos", list(alims.keys()))
        soma = sum([alims[x] for x in sel])
        st.metric("Total Carboidratos", f"{soma}g")
        if st.button("Salvar Nutrição"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), ", ".join(sel), soma]], columns=["Usuario","Data","Itens","Carbs"])
            base_n = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
            pd.concat([base_n, novo_n], ignore_index=True).to_csv(ARQ_N, index=False); st.success("Salvo!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_r:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Configurar Tabela de Insulina")
        df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email]
        v_ini = r_u.iloc[0]['Dose'] if not r_u.empty else 0
        dose_nv = st.number_input("Dose Padrão (UI)", value=int(v_ini))
        if st.button("Salvar Tabela"):
            nova_r = pd.DataFrame([{'Usuario': st.session_state.user_email, 'Dose': dose_nv}])
            df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
            pd.concat([df_r_all, nova_r], ignore_index=True).to_csv(ARQ_R, index=False); st.success("Salvo!")
        st.markdown('</div>', unsafe_allow_html=True)

    # SIDEBAR
    if st.sidebar.button("📥 Baixar Relatório Excel"):
        df_ex = carregar(ARQ_G)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_ex.to_excel(writer, sheet_name='Glicemia', index=False)
            ws = writer.sheets['Glicemia']
            for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
                for cell in row:
                    v_c = int(cell.value)
                    if v_c < 70: cell.fill = PatternFill("solid", fgColor="FFFFE0")
                    elif v_c > 180: cell.fill = PatternFill("solid", fgColor="FFB6C1")
                    else: cell.fill = PatternFill("solid", fgColor="C8E6C9")
        st.sidebar.download_button("Baixar Agora", output.getvalue(), "Relatorio.xlsx")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
