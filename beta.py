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
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ================= BANCO DE DADOS =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (nome TEXT, email TEXT PRIMARY KEY, senha TEXT, categoria TEXT, pergunta_secreta TEXT)''')
    if not cursor.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        cursor.execute("INSERT INTO users VALUES (?,?,?,?,?)", ("Administrador", "admin", "542820", "Admin", "0000"))
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
        p_c = st.text_input("Palavra-Chave (para recuperar senha)", key="c_p")
        cat_c = st.selectbox("Categoria", ["Pai/Mãe", "Médico(a)", "Nutri"], key="c_cat")
        if st.button("Cadastrar", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (n_c, e_c, s_c, cat_c, p_c))
                conn.commit(); conn.close(); st.success("Conta criada!")
            except: st.error("E-mail já cadastrado.")

    with aba3:
        st.subheader("Recuperação de Acesso")
        e_esq = st.text_input("Digite seu E-mail", key="e_esq")
        p_esq = st.text_input("Sua Palavra-Chave", type="password", key="p_esq")
        if st.button("Verificar Identidade", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            res = conn.execute("SELECT senha FROM users WHERE email=? AND pergunta_secreta=?", (e_esq, p_esq)).fetchone()
            if res: st.success(f"Sua senha é: {res[0]}")
            else: st.error("Dados não conferem.")
            conn.close()

    with aba4:
        st.subheader("Mudar Senha Atual")
        e_alt = st.text_input("E-mail", key="alt_e")
        s_at = st.text_input("Senha Atual", type="password", key="alt_sa")
        s_nv = st.text_input("Nova Senha", type="password", key="alt_sn")
        if st.button("Atualizar", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            if conn.execute("SELECT 1 FROM users WHERE email=? AND senha=?", (e_alt, s_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nv, e_alt))
                conn.commit(); st.success("Senha alterada!")
            else: st.error("Dados atuais incorretos.")
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
        v = st.number_input("Valor", 0, 600, 100)
        m = st.selectbox("Momento", ["Jejum", "Pré-Refeição", "Pós-Refeição", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m]], columns=["Usuario","Data","Hora","Valor","Momento"])
            pd.concat([pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame(), novo], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
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
        alims = {"Pão Francês": 28, "Arroz": 10, "Feijão": 14}
        sel = st.multiselect("Alimentos", list(alims.keys()))
        soma = sum([alims[x] for x in sel])
        st.metric("Total Carboidratos", f"{soma}g")
        if st.button("💾 Salvar Nutrição"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), ", ".join(sel), soma]], columns=["Usuario","Data","Itens","Carbs"])
            pd.concat([pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame(), novo_n], ignore_index=True).to_csv(ARQ_N, index=False); st.success("Salvo!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_r:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Configurar Dose Padrão")
        df_r = carregar(ARQ_R)
        v_i = df_r.iloc[0]['Dose'] if not df_r.empty else 0
        dose = st.number_input("Dose de Insulina", value=int(v_i))
        if st.button("💾 Salvar Dose"):
            nova_r = pd.DataFrame([{'Usuario': st.session_state.user_email, 'Dose': dose}])
            base_r = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
            pd.concat([base_r[base_r['Usuario'] != st.session_state.user_email], nova_r], ignore_index=True).to_csv(ARQ_R, index=False); st.success("Salvo!")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.sidebar.button("📥 Baixar Excel Colorido"):
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
