import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

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
        st.download_button("Clique para Baixar", excel_data, file_name="Relatorio_Medico.xlsx")

import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids - v0.1 Original", page_icon="🩺", layout="wide")

# ================= BANCO DE DADOS (SQLITE) =================
def conectar_db():
    return sqlite3.connect('saude_kids.db', check_same_thread=False)

def criar_tabelas():
    conn = conectar_db()
    c = conn.cursor()
    # Tabela de Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, sobrenome TEXT, 
                  telefone TEXT, email TEXT UNIQUE, senha TEXT)''')
    # Tabela de Glicemia
    c.execute('''CREATE TABLE IF NOT EXISTS glicemia 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email_user TEXT, data TEXT, 
                  hora TEXT, valor INTEGER, momento TEXT, dose TEXT)''')
    # Tabela de Receita (Doses)
    c.execute('''CREATE TABLE IF NOT EXISTS receita 
                 (email_user TEXT PRIMARY KEY, manha_f1 INTEGER, manha_f2 INTEGER, manha_f3 INTEGER,
                  noite_f1 INTEGER, noite_f2 INTEGER, noite_f3 INTEGER)''')
    conn.commit()
    conn.close()

criar_tabelas()

# ================= LÓGICA DE ACESSO =================
if 'logado' not in st.session_state:
    st.session_state.logado = False
    st.session_state.email = ""
    st.session_state.nome = ""

if not st.session_state.logado:
    st.sidebar.title("🔐 Área de Acesso")
    opcao = st.sidebar.selectbox("Entrar ou Cadastrar", ["Login", "Criar Conta"])

    if opcao == "Criar Conta":
        st.subheader("📝 Cadastro de Novo Paciente")
        with st.form("cadastro"):
            col1, col2 = st.columns(2)
            n = col1.text_input("Nome")
            s = col2.text_input("Sobrenome")
            t = st.text_input("Telefone")
            e = st.text_input("E-mail")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Finalizar Cadastro"):
                try:
                    conn = conectar_db()
                    c = conn.cursor()
                    c.execute("INSERT INTO usuarios (nome, sobrenome, telefone, email, senha) VALUES (?,?,?,?,?)", (n,s,t,e,p))
                    conn.commit()
                    conn.close()
                    st.success("Cadastro realizado! Mude para Login.")
                except:
                    st.error("E-mail já cadastrado.")
    else:
        st.subheader("🔑 Login")
        e_login = st.text_input("E-mail")
        p_login = st.text_input("Senha", type="password")
        if st.button("Acessar"):
            conn = conectar_db()
            c = conn.cursor()
            c.execute("SELECT nome FROM usuarios WHERE email = ? AND senha = ?", (e_login, p_login))
            user = c.fetchone()
            if user:
                st.session_state.logado = True
                st.session_state.email = e_login
                st.session_state.nome = user[0]
                st.rerun()
            else:
                st.error("Dados incorretos.")
    st.stop()

# ================= ÁREA DO SISTEMA (LOGADO) =================
st.sidebar.write(f"👤 Paciente: **{st.session_state.nome}**")
if st.sidebar.button("Sair do Sistema"):
    st.session_state.logado = False
    st.rerun()

# --- Funções de Carregamento SQL ---
def carregar_glicemia():
    conn = conectar_db()
    df = pd.read_sql(f"SELECT data, hora, valor, momento, dose FROM glicemia WHERE email_user = '{st.session_state.email}'", conn)
    conn.close()
    return df

def carregar_receita():
    conn = conectar_db()
    c = conn.cursor()
    c.execute("SELECT * FROM receita WHERE email_user = ?", (st.session_state.email,))
    r = c.fetchone()
    conn.close()
    return r

# --- Lógica de Cálculo ---
def calcular_insulina_automatica(valor, momento):
    r = carregar_receita()
    if not r: return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    
    # Índices da tupla r: 0:email, 1:m_f1, 2:m_f2, 3:m_f3, 4:n_f1, 5:n_f2, 6:n_f3
    prefixo_indices = (1, 2, 3) if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else (4, 5, 6)
    
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia!"
    elif 70 <= valor <= 200: dose = r[prefixo_indices[0]]
    elif 201 <= valor <= 400: dose = r[prefixo_indices[1]]
    else: dose = r[prefixo_indices[2]]
    
    return f"{int(dose)} UI", "Calculado via SQL"

# ================= ABAS =================
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    dfg = carregar_glicemia()

    with c1:
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        dose_sug, ref_tab = calcular_insulina_automatica(v, m)
        
        st.markdown(f'<div class="dose-alerta"><h3>{dose_sug}</h3><small>{ref_tab}</small></div>', unsafe_allow_html=True)

        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            conn = conectar_db()
            c = conn.cursor()
            c.execute("INSERT INTO glicemia (email_user, data, hora, valor, momento, dose) VALUES (?,?,?,?,?,?)",
                      (st.session_state.email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose_sug))
            conn.commit()
            conn.close()
            st.success("Salvo no Banco de Dados!")
            st.rerun()

    with c2:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['data'] + " " + dfg['hora'], dayfirst=True)
            fig = px.line(dfg.tail(10), x='DataHora', y='valor', markers=True, title="Meu Histórico")
            st.plotly_chart(fig, use_container_width=True)

with t3:
    st.subheader("⚙️ Configuração da Sua Receita")
    r_atual = carregar_receita()
    # Padrão 0 se não houver receita
    v = r_atual if r_atual else (st.session_state.email, 0, 0, 0, 0, 0, 0)
    
    col_m, col_n = st.columns(2)
    with col_m:
        st.info("**☀️ Dia**")
        mf1 = st.number_input("70-200 (Dia):", value=int(v[1]))
        mf2 = st.number_input("201-400 (Dia):", value=int(v[2]))
        mf3 = st.number_input("> 400 (Dia):", value=int(v[3]))
    with col_n:
        st.info("**🌙 Noite**")
        nf1 = st.number_input("70-200 (Noite):", value=int(v[4]))
        nf2 = st.number_input("201-400 (Noite):", value=int(v[5]))
        nf3 = st.number_input("> 400 (Noite):", value=int(v[6]))

    if st.button("💾 Salvar Minha Receita"):
        conn = conectar_db()
        c = conn.cursor()
        c.execute("REPLACE INTO receita VALUES (?,?,?,?,?,?,?)", (st.session_state.email, mf1, mf2, mf3, nf1, nf2, nf3))
        conn.commit()
        conn.close()
        st.success("Receita salva!")
        st.rerun()
