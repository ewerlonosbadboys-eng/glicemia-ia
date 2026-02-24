import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill
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
ARQ_F = "feedbacks_BETA.csv"
DB_NAME = "usuarios_v_final.db" 

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E BANCO DE DADOS =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (nome TEXT, email TEXT PRIMARY KEY, senha TEXT, categoria TEXT)''')
    admin_exists = cursor.execute("SELECT 1 FROM users WHERE email='admin'").fetchone()
    if not admin_exists:
        cursor.execute("INSERT INTO users VALUES (?,?,?,?)", ("Administrador", "admin", "542820", "Admin"))
    conn.commit()
    conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

# ================= TELAS DE ACESSO (CORRIGIDO COM KEYS ÚNICAS) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
    
    with abas_login[0]:
        u = st.text_input("E-mail", key="login_email")
        s = st.text_input("Senha", type="password", key="login_senha")
        if st.button("Acessar Aplicativo", key="btn_login"):
            conn = sqlite3.connect(DB_NAME)
            user = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            if user:
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("Dados incorretos.")
            conn.close()

    with abas_login[1]:
        n_cad = st.text_input("Nome Completo", key="cad_nome")
        e_cad = st.text_input("E-mail", key="cad_email")
        s_cad = st.text_input("Senha", type="password", key="cad_senha")
        cat_cad = st.selectbox("Categoria:", ["Pai/Mãe", "Médico(a)", "Nutricionista", "Outro"], key="cad_cat")
        if st.button("Cadastrar Conta", key="btn_cad"):
            try:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO users VALUES (?,?,?,?)", (n_cad, e_cad, s_cad, cat_cad))
                conn.commit(); conn.close(); st.success("Conta criada!")
            except: st.error("E-mail já existe.")
    st.stop()

# ================= ÁREA DO ADMINISTRADOR =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel Admin")
    tab_a1, tab_a2 = st.tabs(["👥 Usuários & Categorias", "📬 Mensagens"])
    
    with tab_a1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        conn = sqlite3.connect(DB_NAME)
        df_users = pd.read_sql_query("SELECT nome, email, categoria FROM users", conn)
        conn.close()
        st.dataframe(df_users, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with tab_a2:
        if os.path.exists(ARQ_F):
            st.dataframe(pd.read_csv(ARQ_F), use_container_width=True)
            if st.button("🗑️ Limpar Mensagens"): os.remove(ARQ_F); st.rerun()
        else: st.info("Sem mensagens.")

# ================= ÁREA DO USUÁRIO COMUM (HISTÓRICO, CORES, EXCEL) =================
else:
    def carregar_dados(arq):
        if not os.path.exists(arq): return pd.DataFrame()
        df = pd.read_csv(arq)
        return df[df['Usuario'] == st.session_state.user_email].copy()

    def calc_insulina(v, m):
        df_r = carregar_dados(ARQ_R)
        if df_r.empty: return "0 UI", "Configurar Receita"
        rec = df_r.iloc[0]
        periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
        try:
            if v < 70: return "0 UI", "Hipoglicemia!"
            elif v <= 200: d = rec[f'{periodo}_f1']
            elif v <= 400: d = rec[f'{periodo}_f2']
            else: d = rec[f'{periodo}_f3']
            return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"
        except: return "0 UI", "Erro"

    MOMENTOS = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]
    ALIMENTOS = {"Pão Francês": [28, 4, 1], "Arroz": [10, 2, 0], "Feijão": [14, 5, 1], "Banana": [22, 1, 0]}

    tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfg = carregar_dados(ARQ_G)
        c1, c2 = st.columns([1, 2])
        with c1:
            v_gl = st.number_input("Valor Glicemia", 0, 600, 100, key="val_gl")
            m_gl = st.selectbox("Momento", MOMENTOS, key="mom_gl")
            dose, msg_d = calc_insulina(v_gl, m_gl)
            st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
            if st.button("💾 Salvar Glicemia", key="btn_save_gl"):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
                base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
                pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
        with c2:
            if not dfg.empty:
                fig = px.line(dfg.tail(10), x='Hora', y='Valor', markers=True, title="Tendência Glicêmica")
                st.plotly_chart(fig, use_container_width=True)
                def cor_gl(v):
                    n = int(v)
                    if n < 70: return 'background-color: #8B8000; color: white;' 
                    elif n > 180: return 'background-color: #8B0000; color: white;' 
                    else: return 'background-color: #006400; color: white;' 
                st.dataframe(dfg.tail(15).style.applymap(cor_gl, subset=['Valor']), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfn = carregar_dados(ARQ_N)
        sel = st.multiselect("Selecione os Alimentos", list(ALIMENTOS.keys()), key="sel_alim")
        carb_total = sum([ALIMENTOS[x][0] for x in sel])
        st.write(f"**Total de Carboidratos:** {carb_total}g")
        if st.button("💾 Salvar Refeição", key="btn_save_nut"):
            agora = datetime.now(fuso_br)
            novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), ", ".join(sel), carb_total]], columns=["Usuario","Data","Alimentos","Carboidratos"])
            base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
            pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False); st.rerun()
        st.dataframe(dfn.tail(10), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        v = r_u.iloc[0] if not r_u.empty else {'manha_f1':0}
        m1 = st.number_input("Manhã (UI)", value=int(v.get('manha_f1', 0)), key="rec_m1")
        if st.button("💾 Salvar Configuração", key="btn_save_rec"):
            nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':m1, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}])
            df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
            pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False); st.success("Salvo!")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- SIDEBAR (EXCEL COLORIDO E MENSAGENS) ---
    st.sidebar.markdown("---")
    if st.sidebar.button("📥 Baixar Excel Colorido", key="btn_excel"):
        df_e_g = carregar_dados(ARQ_G)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if not df_e_g.empty:
                df_e_g.to_excel(writer, sheet_name='Glicemia', index=False)
                ws = writer.sheets['Glicemia']
                for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
                    for cell in row:
                        val = int(cell.value)
                        if val < 70: cell.fill = PatternFill("solid", fgColor="FFFFE0")
                        elif val > 180: cell.fill = PatternFill("solid", fgColor="FFB6C1")
                        else: cell.fill = PatternFill("solid", fgColor="C8E6C9")
        st.sidebar.download_button("Clique para baixar", output.getvalue(), file_name="Relatorio_Saude_Kids.xlsx")

    with st.sidebar.expander("🚀 Mensagem ao Admin"):
        t_m = st.text_area("Sua sugestão:", key="msg_admin")
        if st.button("Enviar", key="btn_msg"):
            n_f = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br), t_m]], columns=["Usuario", "Data", "Sugestão"])
            b_f = pd.read_csv(ARQ_F) if os.path.exists(ARQ_F) else pd.DataFrame()
            pd.concat([b_f, n_f], ignore_index=True).to_csv(ARQ_F, index=False); st.success("Enviado!")

if st.sidebar.button("Sair", key="btn_sair"):
    st.session_state.logado = False
    st.rerun()
