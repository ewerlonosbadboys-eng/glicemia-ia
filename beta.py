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

# ================= ÁREA LOGADA =================

def carregar_dados(arq, colunas):
    if os.path.exists(arq):
        return pd.read_csv(arq)
    return pd.DataFrame(columns=colunas)

def salvar_dados(df, arq):
    df.to_csv(arq, index=False)

st.sidebar.title("Bem-vindo!")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

t1, t2, t3, t4 = st.tabs(["📊 Glicemia", "🍲 Alimentação", "💉 Insulina/Receita", "📈 Relatórios"])

with t1:
    st.header("Controle de Glicemia")
    df_g = carregar_dados(ARQ_G, ['Data', 'Hora', 'Valor', 'Momento'])
    
    with st.expander("Novo Registro"):
        col1, col2, col3, col4 = st.columns(4)
        data = col1.date_input("Data", datetime.now(fuso_br))
        hora = col2.time_input("Hora", datetime.now(fuso_br))
        valor = col3.number_input("Valor (mg/dL)", min_value=20, max_value=600, value=100)
        momento = col4.selectbox("Momento", ["Jejum", "Pré-Almoço", "Pós-Almoço", "Pré-Jantar", "Pós-Jantar", "Madrugada", "Outro"])
        
        if st.button("Salvar Glicemia"):
            novo_d = pd.DataFrame([[data.strftime('%d/%m/%Y'), hora.strftime('%H:%M'), valor, momento]], 
                                columns=['Data', 'Hora', 'Valor', 'Momento'])
            df_g = pd.concat([df_g, novo_d], ignore_index=True)
            salvar_dados(df_g, ARQ_G)
            st.success("Salvo!")
            st.rerun()

    if not df_g.empty:
        fig = px.line(df_g, x='Data', y='Valor', color='Momento', title="Evolução Glicêmica", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_g.sort_index(ascending=False), use_container_width=True)

with t2:
    st.header("Diário Alimentar")
    df_n = carregar_dados(ARQ_N, ['Data', 'Refeição', 'Descrição', 'Carbo(g)'])
    
    with st.expander("Registrar Refeição"):
        c1, c2, c3 = st.columns([1,2,1])
        refeicao = c1.selectbox("Refeição", ["Café", "Lanche M", "Almoço", "Lanche T", "Jantar", "Ceia"])
        desc = c2.text_input("O que comeu?")
        carb = c3.number_input("Carbos (g)", min_value=0)
        
        if st.button("Salvar Refeição"):
            novo_n = pd.DataFrame([[datetime.now(fuso_br).strftime('%d/%m/%Y'), refeicao, desc, carb]], 
                                 columns=['Data', 'Refeição', 'Descrição', 'Carbo(g)'])
            df_n = pd.concat([df_n, novo_n], ignore_index=True)
            salvar_dados(df_n, ARQ_N)
            st.rerun()
    st.dataframe(df_n, use_container_width=True)

with t3:
    st.header("Configuração de Insulina")
    df_r = carregar_dados(ARQ_R, ['Relacao', 'Sensibilidade', 'Meta'])
    
    if df_r.empty:
        st.warning("Configure seus fatores primeiro.")
        rel = st.number_input("Relação Carbo (1U para X gramas)", value=15)
        sens = st.number_input("Fator de Sensibilidade", value=50)
        meta = st.number_input("Meta Glicêmica", value=100)
        if st.button("Salvar Configuração"):
            df_r = pd.DataFrame([[rel, sens, meta]], columns=['Relacao', 'Sensibilidade', 'Meta'])
            salvar_dados(df_r, ARQ_R)
            st.rerun()
    else:
        st.info(f"Fatores: 1U/{df_r['Relacao'][0]}g | Sensibilidade: {df_r['Sensibilidade'][0]} | Meta: {df_r['Meta'][0]}")
        if st.button("Resetar Fatores"):
            if os.path.exists(ARQ_R): os.remove(ARQ_R)
            st.rerun()

with t4:
    st.header("Gerar Relatório Excel")
    
    def gerar_excel():
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_glic = carregar_dados(ARQ_G, [])
            df_nutri = carregar_dados(ARQ_N, [])
            
            if not df_glic.empty:
                df_temp = df_glic.copy()
                df_temp['Exibe'] = df_temp['Valor'].astype(str) + " (" + df_temp['Hora'] + ")"
                pivot = df_temp.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
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

    if st.button("📥 BAIXAR RELATÓRIO EXCEL"):
        dados_ex = gerar_excel()
        st.download_button("Clique aqui para baixar", dados_ex, "relatorio_saude_kids.xlsx")
