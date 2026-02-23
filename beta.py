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

# 1. CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# =========================================================
# LÓGICA DE REDIRECIONAMENTO (O CORAÇÃO DO PROBLEMA)
# =========================================================

# Pegamos os dados do link (ex: ?reset=true&email=...)
params = st.query_params

# Se o link contém "reset", travamos o app na tela de senha
if "reset" in params:
    email_para_reset = params.get("email")
    
    st.title("🔐 Redefinir sua Senha")
    st.markdown(f"Você está alterando a senha de: **{email_para_reset}**")
    
    nova_senha = st.text_input("Nova Senha", type="password", key="new_pwd_reset")
    confirmar_senha = st.text_input("Confirme a Nova Senha", type="password", key="conf_pwd_reset")
    
    if st.button("Gravar Nova Senha"):
        if nova_senha == confirmar_senha and len(nova_senha) >= 4:
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("UPDATE users SET senha=? WHERE email=?", (nova_senha, email_para_reset))
            conn.commit()
            conn.close()
            
            st.success("✅ Senha alterada com sucesso!")
            st.info("Clique no botão abaixo para ir ao login.")
            
            # Botão para limpar o link e voltar ao normal
            if st.button("Ir para o Login"):
                st.query_params.clear()
                st.rerun()
        else:
            st.error("❌ As senhas não conferem ou são muito curtas.")
            
    if st.button("Cancelar e Sair"):
        st.query_params.clear()
        st.rerun()

    # O st.stop() aqui é obrigatório: ele impede que o login apareça embaixo
    st.stop() 

# =========================================================
# FUNÇÕES DE E-MAIL E LOGIN (SÓ CARREGA SE NÃO ESTIVER RESETANDO)
# =========================================================

def enviar_link_recuperacao(email_destino):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    link_app = "https://glicemia-ia.streamlit.app" 
    email_codificado = urllib.parse.quote(email_destino)
    # Criamos o link exatamente como o sensor lá de cima espera
    link_final = f"{link_app}/?reset=true&email={email_codificado}"
    
    corpo = f"""
    <h2>Recuperação de Senha - Saúde Kids</h2>
    <p>Você solicitou a troca de senha. Clique no botão abaixo:</p>
    <a href='{link_final}' style='padding:10px; background-color:blue; color:white; text-decoration:none; border-radius:5px;'>REDEFINIR SENHA</a>
    <p>Se o botão não funcionar, copie o link: {link_final}</p>
    """
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Recuperação de Senha'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

# Daqui para baixo segue seu código normal de Login e as abas t1, t2, t3...

# ================= 6. RESTANTE DO APP (GRÁFICOS, ETC) =================
# O código que você já tinha de glicemia continua daqui para baixo...
# 4. SISTEMA DE LOGIN (SÓ APARECE SE NÃO ESTIVER EM RESET)
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    # USAR LISTA FIXA DE ABAS EVITA O ERRO "INDEX OUT OF RANGE"
    abas = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])
    
    with abas[0]:
        st.subheader("Login")
        u = st.text_input("E-mail", key="login_email")
        s = st.text_input("Senha", type="password", key="login_pass")
        if st.button("Entrar"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("E-mail ou senha inválidos.")
            conn.close()

    with abas[1]:
        st.subheader("Cadastro")
        nome = st.text_input("Seu Nome")
        email_c = st.text_input("Seu E-mail")
        senha_c = st.text_input("Crie uma Senha", type="password")
        if st.button("Cadastrar"):
            # Coloque aqui sua lógica de INSERT no SQLite
            st.success("Cadastro realizado!")

    with abas[2]:
        st.subheader("Recuperar Senha")
        email_alvo = st.text_input("E-mail cadastrado", key="email_reset_input")
        if st.button("Enviar Link de Recuperação"):
            if enviar_link_recuperacao(email_alvo):
                st.success("Link enviado! Verifique seu e-mail.")
            else:
                st.error("Erro ao enviar e-mail.")
    st.stop()

# 5. RESTANTE DO APP (GRÁFICOS, ETC)
# (COLE AQUI O RESTANTE DO SEU CÓDIGO ORIGINAL QUE VOCÊ JÁ TEM)

# Lógica para capturar o link do e-mail ANTES de carregar o login
query_params = st.query_params
if "reset" in query_params and "email" in query_params:
    st.session_state.reset_mode = True
    st.session_state.email_reset = query_params["email"]

# Se detectou o link, mostra APENAS esta tela e trava o resto
if st.session_state.get("reset_mode"):
    st.title("🔐 Defina sua Nova Senha")
    st.warning(f"Redefinindo para: {st.session_state.email_reset}")
    
    nova_s = st.text_input("Nova Senha", type="password", key="pwd_reset_field")
    confirma_s = st.text_input("Confirme a Senha", type="password", key="pwd_reset_confirm")
    
    if st.button("Salvar Nova Senha e Entrar"):
        if nova_s == confirma_s and len(nova_s) >= 4:
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("UPDATE users SET senha=? WHERE email=?", (nova_s, st.session_state.email_reset))
            conn.commit()
            conn.close()
            
            st.success("Senha alterada! Redirecionando para login...")
            st.session_state.reset_mode = False
            # Limpa o link da barra de endereço para não bugar no próximo acesso
            st.query_params.clear() 
            st.rerun()
        else:
            st.error("As senhas precisam ser iguais e ter no mínimo 4 caracteres.")
    
    if st.button("Cancelar"):
        st.session_state.reset_mode = False
        st.query_params.clear()
        st.rerun()
        
    st.stop() # Mata a execução aqui para não carregar a tela de login embaixo

# ================= 2. FUNÇÕES DE APOIO =================

def enviar_link_recuperacao(email_destino):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    
    link_app = "https://glicemia-ia.streamlit.app" 
    email_codificado = urllib.parse.quote(email_destino)
    link_final = f"{link_app}/?reset=true&email={email_codificado}"
    
    corpo = f"<h3>Saúde Kids</h3><p>Clique aqui para mudar sua senha: <a href='{link_final}'>LINK DE ACESSO</a></p>"
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Redefinição de Senha'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

# ================= 3. CONTROLE DE LOGIN (SÓ APARECE SE NÃO ESTIVER EM RESET) =================

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Bem-vindo ao Saúde Kids")
    
    # Criamos as abas de forma fixa para evitar o erro de IndexError
    aba_login, aba_cad, aba_rec = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])
    
    with aba_login:
        u = st.text_input("E-mail", key="main_login_em")
        s = st.text_input("Senha", type="password", key="main_login_pw")
        if st.button("Acessar"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Dados incorretos.")
            conn.close()

    with aba_cad:
        # (Coloque aqui seus campos de Nome, Email, Senha de cadastro que já tinha)
        st.info("Preencha os dados para se cadastrar.")

    with aba_rec:
        st.subheader("Recuperação por E-mail")
        email_alvo = st.text_input("Digite o e-mail cadastrado", key="rec_input_final")
        if st.button("Enviar Link Agora"):
            if enviar_link_recuperacao(email_alvo):
                st.success("E-mail enviado com sucesso!")
            else:
                st.error("Erro ao enviar. Verifique sua conexão ou dados.")
    
    st.stop() # Só passa daqui se estiver logado

# ================= 4. RESTANTE DO SEU APP (GLICEMIA, ETC) =================
# Seu código original de gráficos e tabelas continua aqui...

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

# ARQUIVOS DE DADOS (CSV)
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= FUNÇÃO DE ENVIO DE E-MAIL =================
def enviar_link_recuperacao(email_destino):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" # Senha de App do Google
    
    link_app = "https://glicemia-ia.streamlit.app" 
    email_codificado = urllib.parse.quote(email_destino)
    link_final = f"{link_app}/?reset=true&email={email_codificado}"
    
    corpo = f"""
    <h3>Recuperação de Senha - Saúde Kids</h3>
    <p>Clique no link abaixo para cadastrar uma nova senha:</p>
    <a href='{link_final}'>Redefinir minha senha agora</a>
    """
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Link de Redefinição - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

# ================= SENSOR DE LINK DE RECUPERAÇÃO =================
query_params = st.query_params
if "reset" in query_params and "email" in query_params:
    st.session_state.reset_mode = True
    st.session_state.email_reset = query_params["email"]

if st.session_state.get("reset_mode"):
    st.title("🔐 Nova Senha")
    st.info(f"Redefinindo para: {st.session_state.email_reset}")
    nova_s = st.text_input("Digite a nova senha", type="password")
    confirmar_s = st.text_input("Confirme a nova senha", type="password")
    
    if st.button("Salvar Nova Senha"):
        if nova_s == confirmar_s and len(nova_s) >= 4:
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("UPDATE users SET senha=? WHERE email=?", (nova_s, st.session_state.email_reset))
            conn.commit()
            conn.close()
            st.success("Pronto! Senha alterada. Faça login normalmente.")
            st.session_state.reset_mode = False
            st.query_params.clear()
            st.rerun()
        else:
            st.error("As senhas não coincidem ou são muito curtas.")
    st.stop()

# ================= BANCO DE DADOS DE USUÁRIOS =================
def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ================= SISTEMA DE LOGIN E ABAS =================
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'conta_criada' not in st.session_state:
    st.session_state.conta_criada = False

if not st.session_state.logado:
    st.markdown("""<style>.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }</style>""", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    titulos = ["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"]
    if st.session_state.conta_criada:
        titulos = ["🔐 Entrar", "❓ Esqueci Senha"]

    abas_login = st.tabs(titulos)

    with abas_login[0]: # LOGIN
        u = st.text_input("E-mail", key="l_user")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Sistema"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
            conn.close()

    if not st.session_state.conta_criada:
        with abas_login[1]: # CADASTRO
            nome = st.text_input("Nome")
            email_cad = st.text_input("E-mail")
            senha_cad = st.text_input("Senha", type="password")
            if st.button("Finalizar Cadastro"):
                try:
                    conn = sqlite3.connect('usuarios.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO users (nome, email, senha) VALUES (?,?,?)", (nome, email_cad, senha_cad))
                    conn.commit()
                    conn.close()
                    st.session_state.conta_criada = True
                    st.success("Conta criada! Vá para a aba Entrar.")
                    st.rerun()
                except:
                    st.error("Este e-mail já está cadastrado.")
        
        with abas_login[2]: # ESQUECI SENHA
            email_rec = st.text_input("E-mail cadastrado", key="rec_em")
            if st.button("Enviar Link"):
                if enviar_link_recuperacao(email_rec):
                    st.success("Link enviado! Verifique seu e-mail.")
                else:
                    st.error("Erro ao enviar e-mail.")
    else:
        with abas_login[1]: # ESQUECI SENHA (QUANDO LOGADO)
            email_rec = st.text_input("E-mail cadastrado", key="rec_em_2")
            if st.button("Enviar Link de Recuperação"):
                if enviar_link_recuperacao(email_rec):
                    st.success("Link enviado!")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

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
