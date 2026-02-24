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

# ================= BANCO DE DADOS (LIMPO) =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Criando tabela sem a coluna de pergunta secreta
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (nome TEXT, email TEXT PRIMARY KEY, senha TEXT, categoria TEXT)''')
    if not cursor.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        cursor.execute("INSERT INTO users VALUES (?,?,?,?)", ("Administrador", "admin", "542820", "Admin"))
    conn.commit()
    conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

# ================= TELA DE ENTRADA (AS 4 ABAS SOLICITADAS) =================
if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    aba1, aba2, aba3, aba4 = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with aba1:
        u_l = st.text_input("E-mail", key="l_e")
        s_l = st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar Aplicativo", use_container_width=True):
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
        if st.button("Criar Conta Agora", use_container_width=True):
            try:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO users VALUES (?,?,?,?)", (n_c, e_c, s_c, cat_c))
                conn.commit(); conn.close(); st.success("Conta criada com sucesso!")
            except: st.error("Erro: E-mail já existe ou banco ocupado.")

    with aba3:
        st.subheader("Recuperação de Senha")
        e_esq = st.text_input("E-mail cadastrado", key="e_esq")
        if st.button("Mostrar minha senha", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            res = conn.execute("SELECT senha FROM users WHERE email=?", (e_esq,)).fetchone()
            if res: st.success(f"Sua senha cadastrada é: {res[0]}")
            else: st.error("E-mail não encontrado no sistema.")
            conn.close()

    with aba4:
        st.subheader("Trocar Senha")
        e_alt = st.text_input("E-mail da conta", key="alt_e")
        s_at = st.text_input("Senha Atual", type="password", key="alt_sa")
        s_nv = st.text_input("Nova Senha", type="password", key="alt_sn")
        if st.button("Salvar Nova Senha", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            if conn.execute("SELECT 1 FROM users WHERE email=? AND senha=?", (e_alt, s_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (s_nv, e_alt))
                conn.commit(); st.success("Senha alterada com sucesso!")
            else: st.error("Senha atual não confere.")
            conn.close()
    st.stop()

# ================= ÁREA PRIVADA (ADMIN / USUÁRIO) =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel de Controle Admin")
    t1, t2 = st.tabs(["👥 Lista de Usuários", "📬 Suporte/Feedbacks"])
    with t1:
        conn = sqlite3.connect(DB_NAME)
        st.dataframe(pd.read_sql_query("SELECT nome, email, categoria FROM users", conn), use_container_width=True)
        conn.close()
    with t2:
        if os.path.exists(ARQ_F):
            st.dataframe(pd.read_csv(ARQ_F), use_container_width=True)
        else: st.info("Nenhuma mensagem recebida ainda.")
else:
    def carregar(arq):
        if not os.path.exists(arq): return pd.DataFrame()
        df = pd.read_csv(arq)
        if 'Usuario' in df.columns:
            return df[df['Usuario'] == st.session_state.user_email].copy()
        return pd.DataFrame()

    st.sidebar.title(f"Bem-vindo(a)!")
    
    # ABAS PRINCIPAIS DO USUÁRIO
    tab_g, tab_n, tab_r = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

    with tab_g:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Registrar Glicemia")
        df_g = carregar(ARQ_G)
        c1, c2 = st.columns([1, 2])
        with c1:
            valor_g = st.number_input("Valor (mg/dL)", 0, 600, 100)
            momento_g = st.selectbox("Momento", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Janta", "Após Janta", "Madrugada"])
            if st.button("💾 Salvar Registro"):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), valor_g, momento_g]], columns=["Usuario","Data","Hora","Valor","Momento"])
                base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
                pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
        with c2:
            if not df_g.empty:
                st.plotly_chart(px.line(df_g.tail(10), x='Hora', y='Valor', markers=True, title="Últimas Medições"), use_container_width=True)
        
        if not df_g.empty:
            st.write("### Histórico Recente")
            def aplicar_cores(val):
                if val < 70: return 'background-color: #8B8000; color: white;' # Amarelo escuro/Ouro
                if val > 180: return 'background-color: #8B0000; color: white;' # Vermelho
                return 'background-color: #006400; color: white;' # Verde
            st.dataframe(df_g.tail(15).style.applymap(aplicar_cores, subset=['Valor']), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_n:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Calculadora de Carboidratos")
        alims = {"Pão Francês": 28, "Arroz (colher)": 10, "Feijão (concha)": 14, "Banana": 22, "Maçã": 15, "Suco Laranja": 20}
        sel = st.multiselect("O que você comeu?", list(alims.keys()))
        soma_carbs = sum([alims[x] for x in sel])
        st.metric("Total de Carboidratos", f"{soma_carbs}g")
        if st.button("💾 Salvar Refeição"):
            novo_n = pd.DataFrame([[st.session_state.user_email, datetime.now(fuso_br).strftime("%d/%m/%Y"), ", ".join(sel), soma_carbs]], columns=["Usuario","Data","Itens","Carbs"])
            base_n = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
            pd.concat([base_n, novo_n], ignore_index=True).to_csv(ARQ_N, index=False); st.success("Refeição salva!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_r:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Minha Receita Padrão")
        df_r = carregar(ARQ_R)
        v_atual = df_r.iloc[0]['Dose'] if not df_r.empty else 0
        dose_padrao = st.number_input("Dose de Insulina Base (UI)", value=int(v_atual))
        if st.button("💾 Salvar Configuração"):
            nova_r = pd.DataFrame([{'Usuario': st.session_state.user_email, 'Dose': dose_padrao}])
            base_r = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
            # Remove a dose antiga antes de salvar a nova
            base_limpa = base_r[base_r['Usuario'] != st.session_state.user_email] if not base_r.empty else pd.DataFrame()
            pd.concat([base_limpa, nova_r], ignore_index=True).to_csv(ARQ_R, index=False); st.success("Dose padrão atualizada!")
        st.markdown('</div>', unsafe_allow_html=True)

    # SIDEBAR COM EXCEL E SAIR
    st.sidebar.markdown("---")
    if st.sidebar.button("📥 Gerar Excel Colorido"):
        df_ex = carregar(ARQ_G)
        if not df_ex.empty:
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
            st.sidebar.download_button("Baixar Relatório.xlsx", output.getvalue(), "SaudeKids_Relatorio.xlsx")
        else: st.sidebar.warning("Sem dados para exportar.")

if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
