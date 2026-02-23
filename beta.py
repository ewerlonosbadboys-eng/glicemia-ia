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
import urllib.parse
import random
import string

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# Inicialização de Variáveis de Sessão
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

# ================= MOTOR DE BANCO DE DADOS SQL =================

def get_connection():
    return sqlite3.connect('saude_kids_master.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Tabela de Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nome TEXT, email TEXT UNIQUE, senha TEXT)''')
    
    # Tabela de Glicemia (Vinculada ao Usuário)
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_email TEXT, data TEXT, hora TEXT, valor INTEGER, momento TEXT,
                  FOREIGN KEY(user_email) REFERENCES users(email))''')
    
    # Tabela de Nutrição (Vinculada ao Usuário)
    c.execute('''CREATE TABLE IF NOT EXISTS nutricao 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_email TEXT, data TEXT, refeicao TEXT, descricao TEXT, carbo REAL,
                  FOREIGN KEY(user_email) REFERENCES users(email))''')
    
    # Tabela de Configurações de Insulina
    c.execute('''CREATE TABLE IF NOT EXISTS config_insulina 
                 (user_email TEXT PRIMARY KEY, relacao REAL, sensibilidade REAL, meta REAL)''')
    
    conn.commit()
    conn.close()

init_db()

# ARQUIVOS DE DADOS (CSV)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÕES DE SEGURANÇA =================

def gerar_senha_temporaria(tamanho=6):
    """Gera uma senha aleatória de letras e números"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    """Envia a senha gerada diretamente para o e-mail"""
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    
    corpo = f"""
    <h3>Saúde Kids - Nova Senha Gerada</h3>
    <p>Sua senha antiga foi resetada por segurança.</p>
    <p>Sua nova senha de acesso é: <b style='font-size: 20px; color: blue;'>{senha_nova}</b></p>
    <p>Use esta senha para entrar no aplicativo agora.</p>
    """
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Sua Nova Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ================= SISTEMA DE LOGIN =================

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    # ADICIONADA A QUARTA ABA: ALTERAR SENHA
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])

    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        st.subheader("Cadastro")
        n = st.text_input("Nome completo")
        em = st.text_input("Seu melhor e-mail")
        se = st.text_input("Crie uma senha", type="password")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (n, em, se))
                conn.commit()
                conn.close()
                st.success("Conta criada! Use a aba 'Entrar'.")
            except:
                st.error("Este e-mail já existe.")

    with abas_login[2]:
        st.subheader("Recuperar Acesso")
        email_alvo = st.text_input("Digite o e-mail da conta", key="rec_em_direto")
        
        if st.button("Enviar Nova Senha"):
            if email_alvo:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("SELECT email FROM users WHERE email=?", (email_alvo,))
                if c.fetchone():
                    senha_gerada = gerar_senha_temporaria()
                    c.execute("UPDATE users SET senha=? WHERE email=?", (senha_gerada, email_alvo))
                    conn.commit()
                    conn.close()
                    if enviar_senha_nova(email_alvo, senha_gerada):
                        st.success(f"✅ Senha enviada para {email_alvo}!")
                    else:
                        st.error("Erro ao enviar e-mail.")
                else:
                    st.error("E-mail não cadastrado.")
                    conn.close()
            else:
                st.warning("Informe o e-mail.")

    with abas_login[3]:
        st.subheader("Alterar Minha Senha")
        alt_email = st.text_input("Confirme seu e-mail", key="alt_em")
        alt_antiga = st.text_input("Senha Atual", type="password", key="alt_ant")
        alt_nova1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        alt_nova2 = st.text_input("Repita a Nova Senha", type="password", key="alt_n2")
        
        if st.button("Confirmar Alteração"):
            if alt_nova1 != alt_nova2:
                st.error("As novas senhas não coincidem!")
            elif not alt_email or not alt_antiga or not alt_nova1:
                st.warning("Preencha todos os campos.")
            else:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_email, alt_antiga))
                if c.fetchone():
                    c.execute("UPDATE users SET senha=? WHERE email=?", (alt_nova1, alt_email))
                    conn.commit()
                    st.success("✅ Senha alterada com sucesso! Volte na aba 'Entrar'.")
                else:
                    st.error("E-mail ou senha atual incorretos.")
                conn.close()
    st.stop()

# ================= ÁREA LOGADA (SQL DINÂMICO) =================

st.sidebar.title("Saúde Kids PRO")
st.sidebar.write(f"Conectado como: \n**{st.session_state.user_email}**")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3, t4 = st.tabs(["📊 Glicemia", "🍲 Alimentação", "💉 Configurações", "📈 Exportar"])

# --- ABA 1: GLICEMIA (SQL) ---
with t1:
    st.header("Seu Histórico Glicêmico")
    conn = get_connection()
    
    with st.expander("➕ Novo Registro"):
        col1, col2, col3 = st.columns(3)
        v_gli = col1.number_input("Valor", 20, 600, 100)
        m_gli = col2.selectbox("Momento", ["Jejum", "Pré-Almoço", "Pós-Almoço", "Pré-Jantar", "Pós-Jantar", "Madrugada"])
        if st.button("Salvar Registro"):
            c = conn.cursor()
            c.execute("INSERT INTO glicemia (user_email, data, hora, valor, momento) VALUES (?,?,?,?,?)",
                     (st.session_state.user_email, datetime.now(fuso_br).strftime('%d/%m/%Y'), 
                      datetime.now(fuso_br).strftime('%H:%M'), v_gli, m_gli))
            conn.commit()
            st.success("Salvo no banco de dados!")
            st.rerun()
    
    df_g = pd.read_sql_query("SELECT data, hora, valor, momento FROM glicemia WHERE user_email=?", conn, 
                             params=(st.session_state.user_email,))
    if not df_g.empty:
        st.plotly_chart(px.line(df_g, x='data', y='valor', title="Sua Curva"), use_container_width=True)
        st.dataframe(df_g, use_container_width=True)
    conn.close()

# --- ABA 3: CONFIGURAÇÕES (SQL) ---
with t3:
    st.header("Seus Fatores")
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT relacao, sensibilidade, meta FROM config_insulina WHERE user_email=?", (st.session_state.user_email,))
    config = c.fetchone()
    
    if not config:
        st.warning("Configure seus dados pela primeira vez:")
        r = st.number_input("Relação Carbo", value=15.0)
        s = st.number_input("Sensibilidade", value=50.0)
        m = st.number_input("Meta", value=100.0)
        if st.button("Salvar"):
            c.execute("INSERT INTO config_insulina VALUES (?,?,?,?)", (st.session_state.user_email, r, s, m))
            conn.commit()
            st.rerun()
    else:
        st.info(f"Relação: 1:{config[0]} | Sensibilidade: {config[1]} | Meta: {config[2]}")
        if st.button("Resetar Fatores"):
            c.execute("DELETE FROM config_insulina WHERE user_email=?", (st.session_state.user_email,))
            conn.commit()
            st.rerun()
    conn.close()
    
# ================= ESTILO VISUAL =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= CORES COM PRIORIDADE =================
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70:
            return 'background-color: #FFFFE0; color: black'
        elif n > 180:
            return 'background-color: #FFB6C1; color: black'
        elif n > 140:
            return 'background-color: #FFFFE0; color: black'
        else:
            return 'background-color: #90EE90; color: black'
    except:
        return ""

# ================= FUNÇÕES DE APOIO =================
def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina_automatica(valor, momento):
    df_r = carregar(ARQ_R)
    if df_r.empty:
        return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia! Tratar agora."
    elif 70 <= valor <= 200: dose = r[f'{prefixo}_f1']
    elif 201 <= valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= DEFINIÇÃO DAS ABAS (CÂMERA REMOVIDA) =================
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

# --- ABA 1: GLICEMIA ---
with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    dfg = carregar(ARQ_G)

    with c1:
        st.subheader("📝 Novo Registro")
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        
        dose_sug, ref_tab = calcular_insulina_automatica(v, m)
        st.markdown(f"""<div class="dose-alerta">
            <p style="margin:0; color:#166534;">Dose Sugerida:</p>
            <h1 style="margin:0; color:#15803d;">{dose_sug}</h1>
            <small>{ref_tab}</small>
        </div>""", unsafe_allow_html=True)

        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose_sug]],
                                columns=["Data", "Hora", "Valor", "Momento", "Dose"])
            pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo com sucesso!")
            st.rerun()

    with c2:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            fig = px.line(dfg.tail(10), x='DataHora', y='Valor', markers=True, title="Evolução Recente")
            st.plotly_chart(fig, use_container_width=True)

    if not dfg.empty:
        st.subheader("📋 Histórico")
        st.dataframe(dfg.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 2: ALIMENTAÇÃO ---
with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🍽️ Controle de Nutrientes")
    ca1, ca2 = st.columns(2)

    with ca1:
        escolha = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
        carb = sum([ALIMENTOS[i][0] for i in escolha])
        prot = sum([ALIMENTOS[i][1] for i in escolha])
        gord = sum([ALIMENTOS[i][2] for i in escolha])

        st.info(f"Totais: Carboidratos: {carb}g | Proteínas: {prot}g | Gorduras: {gord}g")

        if st.button("💾 Salvar Alimentação"):
            agora = datetime.now(fuso_br)
            txt = f"{', '.join(escolha)} (C:{carb} P:{prot} G:{gord})"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), txt, carb, prot, gord]],
                                 columns=["Data", "Info", "C", "P", "G"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()

    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            fig2 = px.pie(values=[dfn['C'].sum(), dfn['P'].sum(), dfn['G'].sum()],
                         names=['Carbo', 'Prot', 'Gord'], title="Distribuição Nutricional Total")
            st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 3: RECEITA (Antiga Configuração) ---
with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Configurar Doses do Médico (Receita)")
    
    df_r = carregar(ARQ_R)
    v_at = df_r.iloc[0] if not df_r.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    
    col_m, col_n = st.columns(2)
    with col_m:
        st.info("**☀️ Café / Almoço / Merenda**")
        mf1 = st.number_input("Dose 70-200:", value=int(v_at['manha_f1']), key="mf1")
        mf2 = st.number_input("Dose 201-400:", value=int(v_at['manha_f2']), key="mf2")
        mf3 = st.number_input("Dose > 400:", value=int(v_at['manha_f3']), key="mf3")
    with col_n:
        st.info("**🌙 Jantar / Madrugada**")
        nf1 = st.number_input("Dose 70-200:", value=int(v_at['noite_f1']), key="nf1")
        nf2 = st.number_input("Dose 201-400:", value=int(v_at['noite_f2']), key="nf2")
        nf3 = st.number_input("Dose > 400:", value=int(v_at['noite_f3']), key="nf3")
        
    if st.button("💾 Salvar Receita"):
        pd.DataFrame([{'manha_f1':mf1, 'manha_f2':mf2, 'manha_f3':mf3, 'noite_f1':nf1, 'noite_f2':nf2, 'noite_f3':nf3}]).to_csv(ARQ_R, index=False)
        st.success("Receita atualizada!")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO =================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic = df_glic.copy()
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']

            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")

            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            val = int(str(cell.value).split(" ")[0])
                            if val < 70: cell.fill = a_fill
                            elif val > 180: cell.fill = r_fill
                            elif val > 140: cell.fill = a_fill
                            else: cell.fill = v_fill
                        except: pass

        if not df_nutri.empty:
            df_nutri.to_excel(writer, index=False, sheet_name='Alimentacao')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO EXCEL"):
    dfg = carregar(ARQ_G)
    dfn = carregar(ARQ_N)
    if not dfg.empty:
        excel_data = gerar_excel_colorido(dfg, dfn)
        st.download_button("Clique para Baixar", excel_data, file_name="Relatorio_Medico.xlsx")
