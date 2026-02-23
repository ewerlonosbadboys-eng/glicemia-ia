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

# --- FUNÇÃO ÚNICA DE E-MAIL ---
def enviar_link_recuperacao(email_destino):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" # Sua senha de 16 letras já está aqui!
    
    link_app = "https://glicemia-ia.streamlit.app" 
    email_codificado = urllib.parse.quote(email_destino)
    link_final = f"{link_app}/?reset=true&email={email_codificado}"
    
    corpo = f"<h3>Recuperação de Senha</h3><p>Clique no link para definir sua nova senha: <a href='{link_final}'>Redefinir Senha</a></p>"
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Redefinição de Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

# --- SENSOR DE LINK (O "OUVINTE") ---
query_params = st.query_params
if "reset" in query_params and "email" in query_params:
    st.session_state.reset_mode = True
    st.session_state.email_reset = query_params["email"]

if st.session_state.get("reset_mode"):
    st.title("🔐 Criar Nova Senha")
    st.info(f"Redefinindo para: {st.session_state.email_reset}")
    nova_s = st.text_input("Nova Senha", type="password")
    if st.button("Confirmar Alteração"):
        conn = sqlite3.connect('usuarios.db')
        c = conn.cursor()
        c.execute("UPDATE users SET senha=? WHERE email=?", (nova_s, st.session_state.email_reset))
        conn.commit()
        conn.close()
        st.success("Senha atualizada! Agora faça o login.")
        st.session_state.reset_mode = False
        st.query_params.clear()
        st.rerun()
    st.stop()
                    
# SENSOR DE LINK (Coloque antes de mostrar as abas)
query_params = st.query_params
if "reset" in query_params and "email" in query_params:
    st.session_state.reset_mode = True
    st.session_state.email_reset = query_params["email"]

if st.session_state.get("reset_mode"):
    st.title("🔐 Nova Senha")
    nova_s = st.text_input("Digite a nova senha", type="password")
    if st.button("Salvar"):
        conn = sqlite3.connect('usuarios.db')
        c = conn.cursor()
        c.execute("UPDATE users SET senha=? WHERE email=?", (nova_s, st.session_state.email_reset))
        conn.commit()
        conn.close()
        st.success("Senha alterada! Volte para a tela inicial.")
        st.session_state.reset_mode = False
        st.query_params.clear()
        st.rerun()
    st.stop() # Importante: Isso trava a tela aqui até ele resetar

# --- BANCO DE DADOS DE USUÁRIOS ---
def gerenciar_usuarios():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    # Esta linha abaixo apaga a tabela antiga que está dando erro de colunas
    c.execute("DROP TABLE IF EXISTS users") 
    # Esta linha cria a tabela nova com os 5 campos certos
    c.execute('''CREATE TABLE users 
                 (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()
    import smtplib
from email.mime.text import MIMEText

def enviar_email_recuperacao(email_destino, nova_senha):
    # Configurações do seu e-mail (Use Gmail como exemplo)
    meu_email = "seu-email@gmail.com"
    minha_senha = "sua-senha-de-app-aqui" # Não é a senha normal, é a senha de app do Google
    
    corpo_email = f"""
    <h3>Recuperação de Senha - App Glicemia</h3>
    <p>Você solicitou a alteração de sua senha.</p>
    <p>Sua nova senha temporária é: <b>{nova_senha}</b></p>
    <p>Acesse o aplicativo aqui: <a href="https://seu-app.streamlit.app">Link do Aplicativo</a></p>
    <p>Recomendamos trocar essa senha após o login.</p>
    """
    
    msg = MIMEText(corpo_email, 'html')
    msg['Subject'] = 'Alteração de Senha - App Glicemia'
    msg['From'] = meu_email
    msg['To'] = email_destino

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"Erro ao enviar: {e}")
        return False
    # Procure a aba[2] ou onde está o "Esqueci Senha" e coloque:
with abas[2]: # ou o índice correspondente
    st.subheader("Recuperar Acesso")
    email_alvo = st.text_input("Seu e-mail cadastrado", key="email_rec")
    if st.button("Enviar E-mail de Recuperação"):
        if enviar_link_recuperacao(email_alvo):
            st.success("Link enviado com sucesso!")
        else:
            st.error("Erro ao enviar. Verifique sua Senha de App.")
    
# Inicializa o estado de 'conta_criada' se não existir
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'conta_criada' not in st.session_state:
    st.session_state.conta_criada = False

# --- TELA DE ACESSO ---
if not st.session_state.logado:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    # Define quais abas aparecem: se criou conta, esconde a aba "Criar Conta"
    if not st.session_state.conta_criada:
        abas = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])
    else:
        abas = st.tabs(["🔐 Entrar", "❓ Esqueci Senha"])
        st.success("Conta criada com sucesso! Agora você pode entrar.")

    # Lógica da Aba LOGIN (Atualizada para salvar senha)
    with abas[0]:
        # O segredo está no 'autocomplete="username"' e 'autocomplete="current-password"'
        u = st.text_input("E-mail", key="login_user", autocomplete="username")
        s = st.text_input("Senha", type="password", key="login_pass", autocomplete="current-password")
        
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Usuário ou senha não encontrados.")
            conn.close()

    # ABA CRIAR CONTA (Lógica que limpa erro de e-mail cadastrado)
    if not st.session_state.conta_criada:
        with abas[1]:
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome", key="reg_nome")
            sn = c2.text_input("Sobrenome", key="reg_sn")
            t = st.text_input("Telefone", key="reg_tel")
            em = st.text_input("E-mail", key="reg_em")
            se = st.text_input("Senha", type="password", key="reg_se")
            
            if st.button("Finalizar Cadastro"):
                try:
                    conn = sqlite3.connect('usuarios.db')
                    c = conn.cursor()
                    
                    # Tenta salvar especificando os nomes das colunas para evitar o erro OperationalError
                    c.execute("""
                        INSERT OR REPLACE INTO users (nome, sobrenome, telefone, email, senha) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (n, sn, t, em, se))
                    
                    conn.commit()
                    conn.close()
                    
                    # Marca que a conta foi criada para a aba sumir
                    st.session_state.conta_criada = True
                    st.success("Cadastro realizado com sucesso!")
                    st.rerun()
                    
                except sqlite3.OperationalError:
                    # Se der erro de coluna faltando, este comando força a criação da coluna Telefone e Sobrenome
                    conn = sqlite3.connect('usuarios.db')
                    c = conn.cursor()
                    st.warning("Ajustando banco de dados... Por favor, clique em Finalizar Cadastro novamente.")
                    # Reinicia a tabela do zero para aceitar os novos campos
                    c.execute("DROP TABLE IF EXISTS users")
                    c.execute("CREATE TABLE users (nome TEXT, sobrenome TEXT, telefone TEXT, email TEXT PRIMARY KEY, senha TEXT)")
                    conn.commit()
                    conn.close()

        # Lógica da Aba Esqueci Senha (é a terceira quando tem criar conta)
        with abas[2]:
            e_email = st.text_input("E-mail cadastrado", key="e_email")
            if st.button("Enviar Link"):
                st.info(f"Link enviado para: {e_email}")
                st.link_button("Redefinir Senha", "https://seusite.com/reset")
    else:
        # Se a conta já foi criada, a aba Esqueci Senha passa a ser a segunda (índice 1)
        with abas[1]:
            e_email = st.text_input("E-mail cadastrado", key="e_email")
            if st.button("Enviar Link"):
                st.info(f"Link enviado para: {e_email}")
                st.link_button("Redefinir Senha", "https://seusite.com/reset")

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- TELA DE ACESSO ---
if not st.session_state.logado:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    aba_login, aba_criar, aba_esqueci = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])
    
    with aba_login:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_senha")
        if st.button("Entrar"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            resultado = c.fetchone()
            conn.close()
            if resultado:
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
                
    with aba_criar:
        n_email = st.text_input("Seu E-mail", key="n_email")
        n_senha = st.text_input("Crie uma Senha", type="password", key="n_senha")
        if st.button("Finalizar Cadastro"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users (email, senha) VALUES (?,?)", (n_email, n_senha))
                conn.commit()
                conn.close()
                st.success("Conta criada! Agora vá em 'Entrar'.")
            except:
                st.error("Este e-mail já está cadastrado.")

    with aba_esqueci:
        e_email = st.text_input("E-mail cadastrado", key="e_email")
        if st.button("Enviar Link de Recuperação"):
            # Simulando o envio de link
            st.info(f"Um link de redefinição foi enviado para: {e_email}")
            st.link_button("Clique aqui para redefinir", "https://seusite.com/reset-password")

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- CONTROLE DE ACESSO ATUALIZADO (SUBSTITUIR NO TOPO) ---
if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'conta_criada' not in st.session_state:
    st.session_state.conta_criada = False

if not st.session_state.logado:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    # Se a conta foi criada, mostra apenas 2 abas. Se não, mostra as 3.
    if not st.session_state.conta_criada:
        abas = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha"])
    else:
        abas = st.tabs(["🔐 Entrar", "❓ Esqueci Senha"])
        st.success("Conta criada com sucesso! Use a aba 'Entrar' agora.")

    # Lógica da Aba LOGIN
    with abas[0]:
        u = st.text_input("E-mail", key="login_user")
        s = st.text_input("Senha", type="password", key="login_pass")
        if st.button("Acessar Aplicativo"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s))
            if c.fetchone():
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Usuário ou senha não encontrados.")
            conn.close()

    # Lógica da Aba CRIAR CONTA (Só aparece se conta_criada for False)
    if not st.session_state.conta_criada:
        with abas[1]:
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome")
            sobrenome = col2.text_input("Sobrenome")
            email_novo = st.text_input("E-mail", key="email_novo")
            senha_nova = st.text_input("Senha", type="password", key="senha_nova")
            
            if st.button("Finalizar Cadastro"):
                try:
                    conn = sqlite3.connect('usuarios.db')
                    c = conn.cursor()
                    c.execute("INSERT INTO users (nome, sobrenome, email, senha) VALUES (?,?,?,?)", 
                             (nome, sobrenome, email_novo, senha_nova))
                    conn.commit()
                    conn.close()
                    # AQUI ESTÁ O SEGREDO: Marcamos que a conta foi criada e reiniciamos
                    st.session_state.conta_criada = True
                    st.rerun()
                except:
                    st.error("Erro: Este e-mail já existe no sistema.")

        # Aba Esqueci Senha (posição 2)
        with abas[2]:
            st.write("Insira seu e-mail para receber o link de recuperação.")
            st.text_input("E-mail cadastrado", key="recupera_email")
            st.button("Enviar Link para E-mail")
    else:
        # Se a conta já foi criada, a aba Esqueci Senha vira a posição 1
        with abas[1]:
            st.write("Insira seu e-mail para receber o link de recuperação.")
            st.text_input("E-mail cadastrado", key="recupera_email_2")
            st.button("Enviar Link para E-mail")

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA - v17", page_icon="🧪", layout="wide")

# ARQUIVOS DE BANCO DE DADOS
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

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

        # =========================================================
# BLOCO NOVO: TELA DE LOGIN COM O MESMO LAYOUT
# (Cole no final do arquivo, sem apagar nada acima)
# =========================================================

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    # Usando o mesmo estilo de 'card' que você já tem no código
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.title("🔐 Acesso ao Saúde Kids")
    
    # Criando colunas para o formulário ficar centralizado
    col_login, _ = st.columns([1, 1])
    
    with col_login:
        user_input = st.text_input("Usuário (E-mail)")
        pass_input = st.text_input("Senha", type="password")
        
        if st.button("Entrar no Sistema"):
            # Aqui você define seu usuário e senha padrão
            if user_input == "admin@saude.com" and pass_input == "12345":
                st.session_state.logado = True
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
                
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Este comando impede que o código antigo (que está acima) 
    # apareça antes da pessoa logar
    st.stop() 

# O seu código antigo que está acima deste bloco passará a ser 
# exibido somente quando st.session_state.logado for True.
    st.download_button("Clique para Baixar", excel_data, file_name="Relatorio_Medico.xlsx")

# =========================================================
# BLOCO TEMPORÁRIO PARA LIMPAR USUÁRIOS (USE APENAS UMA VEZ)
# =========================================================
if st.button("🚨 APAGAR TODOS OS USUÁRIOS E RECOMEÇAR"):
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    st.success("Banco de dados limpo! Tente cadastrar agora.")

# =========================================================
# BLOCO PARA VERIFICAR O BANCO DE DADOS (COLE NO FINAL)
# =========================================================
st.markdown("---")
st.subheader("🔍 Inspetor de Banco de Dados")

if st.checkbox("Mostrar usuários cadastrados"):
    try:
        conn = sqlite3.connect('usuarios.db')
        # O comando abaixo lê a tabela de usuários
        import pandas as pd
        df_usuarios = pd.read_sql_query("SELECT nome, sobrenome, email, telefone FROM users", conn)
        conn.close()
        
        if not df_usuarios.empty:
            st.write("Estes são os dados que estão dentro do arquivo 'usuarios.db':")
            st.dataframe(df_usuarios)
        else:
            st.warning("O arquivo existe, mas a tabela está vazia.")
    except Exception as e:
        st.error(f"Erro ao acessar o banco: {e}")

if st.button("🗑️ Apagar arquivo do Banco para testar do zero"):
    import os
    if os.path.exists("usuarios.db"):
        os.remove("usuarios.db")
        st.success("Arquivo 'usuarios.db' removido! Recarregue a página para criar um novo.")
        st.rerun()
