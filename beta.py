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

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 20px; border-radius: 15px; border: 1px solid #30363d; margin-bottom: 20px; }
    .dose-info { font-size: 22px; color: #4ade80; font-weight: bold; padding: 10px; background: #262730; border-radius: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ================= BANCO DE DADOS =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT, categoria TEXT)''')
    if not cursor.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        cursor.execute("INSERT INTO users VALUES (?,?,?,?)", ("Administrador", "admin", "542820", "Admin"))
    conn.commit()
    conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

# ================= TELA DE ENTRADA (AS 4 ABAS) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    aba1, aba2, aba3, aba4 = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with aba1:
        u_l = st.text_input("E-mail", key="l_e")
        s_l = st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            user = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u_l, s_l)).fetchone()
            if user:
                st.session_state.logado, st.session_state.user_email = True, u_l
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")
            conn.close()

    with aba2:
        n_c = st.text_input("Nome Completo", key="c_n")
        e_c = st.text_input("E-mail", key="c_e")
        s_c = st.text_input("Senha", type="password", key="c_s")
        cat_c = st.selectbox("Categoria", ["Pai/Mãe", "Médico(a)", "Nutri"], key="c_cat")
        if st.button("Cadastrar", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO users VALUES (?,?,?,?)", (n_c, e_c, s_c, cat_c))
                conn.commit(); conn.close(); st.success("Conta criada!")
            except: st.error("Erro: E-mail já existe.")

    with aba3:
        e_esq = st.text_input("E-mail cadastrado", key="e_esq")
        if st.button("Ver Senha", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            res = conn.execute("SELECT senha FROM users WHERE email=?", (e_esq,)).fetchone()
            if res: st.success(f"Sua senha cadastrada é: {res[0]}")
            else: st.error("E-mail não encontrado.")
            conn.close()

    with aba4:
        e_alt = st.text_input("E-mail", key="alt_e")
        s_at = st.text_input("Senha Atual", type="password", key="alt_sa")
        s_nv = st.text_input("Nova Senha", type="password", key="alt_sn")
        if st.button("Confirmar Troca", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            if conn.execute("SELECT 1 FROM users WHERE email=? AND senha=?", (e_alt, s_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nv, e_alt))
                conn.commit(); st.success("Senha alterada com sucesso!")
            else: st.error("Dados atuais incorretos.")
            conn.close()
    st.stop()

# ================= ÁREA DO USUÁRIO =================
def carregar(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

if st.session_state.user_email == "admin":
    st.title("🛡️ Admin Master")
    conn = sqlite3.connect(DB_NAME)
    st.dataframe(pd.read_sql_query("SELECT nome, email, categoria FROM users", conn), use_container_width=True)
    conn.close()
else:
    tab_g, tab_n, tab_r = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

    # --- ABA RECEITA (CONFIGURAÇÃO) ---
    with tab_r:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Configuração de Receita (Doses de Insulina UI)")
        df_r = carregar(ARQ_R)
        
        c1, c2, c3 = st.columns(3)
        with c1: d_cafe = st.number_input("Dose Café", 0, 100, int(df_r['Cafe'].iloc[0]) if not df_r.empty else 0)
        with c2: d_alm = st.number_input("Dose Almoço", 0, 100, int(df_r['Almoco'].iloc[0]) if not df_r.empty else 0)
        with c3: d_jan = st.number_input("Dose Janta", 0, 100, int(df_r['Janta'].iloc[0]) if not df_r.empty else 0)
        
        if st.button("💾 Salvar Configuração de Receita"):
            nova_r = pd.DataFrame([{'Usuario': st.session_state.user_email, 'Cafe': d_cafe, 'Almoco': d_alm, 'Jantar': d_jan}])
            base_r = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
            pd.concat([base_r[base_r['Usuario'] != st.session_state.user_email], nova_r], ignore_index=True).to_csv(ARQ_R, index=False)
            st.success("Receita Salva!")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- ABA GLICEMIA ---
    with tab_g:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        df_g = carregar(ARQ_G)
        df_r = carregar(ARQ_R)
        
        col_f, col_v = st.columns([1, 2])
        with col_f:
            v_gli = st.number_input("Valor Glicemia", 0, 600, 100)
            m_gli = st.selectbox("Momento", ["Café", "Almoço", "Janta", "Madrugada", "Lanche"])
            
            # MOSTRAR DOSE CONFORME RECEITA
            if not df_r.empty and m_gli in ["Café", "Almoço", "Janta"]:
                dose = df_r[m_gli.replace('ã','a').replace('é','e')].iloc[0]
                st.markdown(f'<div class="dose-info">Dose p/ {m_gli}: {dose} UI</div>', unsafe_allow_html=True)

            if st.button("💾 Salvar Medição"):
                agora = datetime.now(fuso_br)
                novo_g = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gli, m_gli]], columns=["Usuario","Data","Hora","Valor","Momento"])
                pd.concat([pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame(), novo_g], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
        
        with col_v:
            if not df_g.empty:
                st.plotly_chart(px.line(df_g.tail(10), x='Hora', y='Valor', markers=True, title="Tendência"), use_container_width=True)

        if not df_g.empty:
            def cor(v):
                if v < 70: return 'background-color: #8B8000'
                if v > 180: return 'background-color: #8B0000'
                return 'background-color: #006400'
            st.dataframe(df_g.tail(15).style.applymap(cor, subset=['Valor']), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- ABA NUTRIÇÃO ---
    with tab_n:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Nova Refeição (Macros)")
        cn1, cn2, cn3 = st.columns(3)
        with cn1: carb = st.number_input("Carboidratos (g)", 0, 300, 0)
        with cn2: prot = st.number_input("Proteínas (g)", 0, 300, 0)
        with cn3: gord = st.number_input("Gorduras (g)", 0, 300, 0)
        desc_al = st.text_input("Descrição (O que comeu?)")
        
        if st.button("💾 Salvar Refeição"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M"), desc_al, carb, prot, gord]], 
                                 columns=["Usuario","Data","Descricao","Carb","Prot","Gord"])
            pd.concat([pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame(), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Refeição Salva!")
            st.rerun()
        
        st.markdown("---")
        st.subheader("Histórico de Nutrição")
        df_nu = carregar(ARQ_N)
        if not df_nu.empty:
            st.dataframe(df_nu.tail(10), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- EXCEL ---
    st.sidebar.markdown("---")
    if st.sidebar.button("📥 Baixar Relatório Full"):
        df_g_ex = carregar(ARQ_G)
        df_n_ex = carregar(ARQ_N)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_g_ex.to_excel(writer, sheet_name='Glicemia', index=False)
            df_n_ex.to_excel(writer, sheet_name='Nutricao', index=False)
            ws = writer.sheets['Glicemia']
            for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
                for cell in row:
                    v = int(cell.value)
                    if v < 70: cell.fill = PatternFill("solid", fgColor="FFFFE0")
                    elif v > 180: cell.fill = PatternFill("solid", fgColor="FFB6C1")
                    else: cell.fill = PatternFill("solid", fgColor="C8E6C9")
        st.sidebar.download_button("Clique p/ Download", output.getvalue(), "SaudeKids_Full.xlsx")

if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
