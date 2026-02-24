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
    .card { background-color: #1a1c24; padding: 25px; border-radius: 15px; border: 1px solid #30363d; margin-bottom: 20px; }
    .dose-label { font-size: 24px; color: #4ade80; font-weight: bold; }
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

# ================= TELA DE ENTRADA =================
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
            else: st.error("Acesso Negado.")
            conn.close()

    with aba2:
        n_c = st.text_input("Nome", key="c_n")
        e_c = st.text_input("E-mail", key="c_e")
        s_c = st.text_input("Senha", type="password", key="c_s")
        cat_c = st.selectbox("Categoria", ["Pai/Mãe", "Médico(a)", "Nutri"], key="c_cat")
        if st.button("Cadastrar", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO users VALUES (?,?,?,?)", (n_c, e_c, s_c, cat_c))
                conn.commit(); conn.close(); st.success("Sucesso!")
            except: st.error("E-mail já existe.")

    with aba3:
        e_esq = st.text_input("E-mail cadastrado", key="e_esq")
        if st.button("Ver Senha", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            res = conn.execute("SELECT senha FROM users WHERE email=?", (e_esq,)).fetchone()
            if res: st.success(f"Sua senha é: {res[0]}")
            else: st.error("Não encontrado.")
            conn.close()

    with aba4:
        e_alt = st.text_input("E-mail", key="alt_e")
        s_at = st.text_input("Senha Atual", type="password", key="alt_sa")
        s_nv = st.text_input("Nova Senha", type="password", key="alt_sn")
        if st.button("Alterar", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            if conn.execute("SELECT 1 FROM users WHERE email=? AND senha=?", (e_alt, s_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nv, e_alt))
                conn.commit(); st.success("Alterada!")
            conn.close()
    st.stop()

# ================= ÁREA PRIVADA =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Admin Master")
    conn = sqlite3.connect(DB_NAME)
    st.dataframe(pd.read_sql_query("SELECT nome, email, categoria FROM users", conn), use_container_width=True)
    conn.close()
else:
    def carregar(arq):
        if not os.path.exists(arq): return pd.DataFrame()
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()

    tab_g, tab_n, tab_r = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

    # --- TABELA DE RECEITA (Doses) ---
    with tab_r:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Configuração de Doses de Insulina (UI)")
        df_r = carregar(ARQ_R)
        
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1: d_cafe = st.number_input("Café da Manhã", 0, 50, int(df_r['Cafe'].iloc[0]) if not df_r.empty else 0)
        with col_r2: d_alm = st.number_input("Almoço", 0, 50, int(df_r['Almoco'].iloc[0]) if not df_r.empty else 0)
        with col_r3: d_jan = st.number_input("Jantar", 0, 50, int(df_r['Jantar'].iloc[0]) if not df_r.empty else 0)
        
        if st.button("💾 Salvar Minha Receita"):
            nova_r = pd.DataFrame([{'Usuario': st.session_state.user_email, 'Cafe': d_cafe, 'Almoco': d_alm, 'Jantar': d_jan}])
            base_r = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
            pd.concat([base_r[base_r['Usuario'] != st.session_state.user_email], nova_r], ignore_index=True).to_csv(ARQ_R, index=False)
            st.success("Receita Atualizada!")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- GLICEMIA ---
    with tab_g:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        df_g = carregar(ARQ_G)
        df_r = carregar(ARQ_R)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            val = st.number_input("Valor Glicêmico", 0, 600, 100)
            mom = st.selectbox("Momento", ["Café", "Almoço", "Jantar", "Madrugada", "Lanche"])
            
            # Mostrar dose da receita aqui
            if not df_r.empty and mom in ["Café", "Almoço", "Jantar"]:
                dose_sugerida = df_r[mom.replace('é','e')].iloc[0]
                st.markdown(f'<p class="dose-label">Dose na Receita: {dose_sugerida} UI</p>', unsafe_allow_html=True)

            if st.button("💾 Salvar Glicemia"):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), val, mom]], columns=["Usuario","Data","Hora","Valor","Momento"])
                pd.concat([pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame(), novo], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
        with c2:
            if not df_g.empty:
                st.plotly_chart(px.line(df_g.tail(10), x='Hora', y='Valor', markers=True), use_container_width=True)
        
        if not df_g.empty:
            def cor(v):
                if v < 70: return 'background-color: #8B8000; color: white;'
                if v > 180: return 'background-color: #8B0000; color: white;'
                return 'background-color: #006400; color: white;'
            st.dataframe(df_g.tail(10).style.applymap(cor, subset=['Valor']), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- NUTRIÇÃO ---
    with tab_n:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Registro de Refeição")
        c_n1, c_n2, c_n3 = st.columns(3)
        with c_n1: carb = st.number_input("Carboidratos (g)", 0, 200, 0)
        with c_n2: prot = st.number_input("Proteínas (g)", 0, 200, 0)
        with c_n3: gord = st.number_input("Gorduras (g)", 0, 200, 0)
        
        desc = st.text_input("O que comeu? (Ex: Arroz, feijão e bife)")
        
        if st.button("💾 Salvar Refeição"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M"), desc, carb, prot, gord]], 
                                 columns=["Usuario", "Data", "Descricao", "Carb", "Prot", "Gord"])
            pd.concat([pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame(), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.success("Refeição registrada!")
            st.rerun()
        
        st.markdown("---")
        st.subheader("Histórico de Nutrição")
        df_nutri = carregar(ARQ_N)
        if not df_nutri.empty:
            st.dataframe(df_nutri.tail(10), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- EXCEL INTEGRADO ---
    if st.sidebar.button("📥 Baixar Relatório Geral"):
        df_g_ex = carregar(ARQ_G)
        df_n_ex = carregar(ARQ_N)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_g_ex.to_excel(writer, sheet_name='Glicemia', index=False)
            df_n_ex.to_excel(writer, sheet_name='Nutricao', index=False)
            # Aplicar cores na aba glicemia
            ws = writer.sheets['Glicemia']
            for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
                for cell in row:
                    v = int(cell.value)
                    if v < 70: cell.fill = PatternFill("solid", fgColor="FFFFE0")
                    elif v > 180: cell.fill = PatternFill("solid", fgColor="FFB6C1")
                    else: cell.fill = PatternFill("solid", fgColor="C8E6C9")
        st.sidebar.download_button("Baixar Excel", output.getvalue(), "SaudeKids_Completo.xlsx")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
