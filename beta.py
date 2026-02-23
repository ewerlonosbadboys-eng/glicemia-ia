import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
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

st.markdown("""
<style>
    .main { background-color: #f1f5f9; }
    .card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 20px; }
    .metric-box { background: #ffffff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 32px; font-weight: bold; color: #16a34a; }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E LOGIN (ORIGINAL) =================

def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    corpo = f"<h3>Saúde Kids</h3><p>Sua nova senha de acesso é: <b>{senha_nova}</b></p>"
    msg = MIMEText(corpo, 'html')
    msg['Subject'] = 'Sua Nova Senha - Saúde Kids'
    msg['From'] = meu_email
    msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except: return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    conn.commit()
    conn.close()

init_db()

if 'logado' not in st.session_state:
    st.session_state.logado = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
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
                st.session_state.user_email = u
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        n_cad = st.text_input("Nome completo", key="n_cad")
        e_cad = st.text_input("Seu melhor e-mail", key="e_cad")
        s_cad = st.text_input("Crie uma senha", type="password", key="s_cad")
        if st.button("Cadastrar"):
            try:
                conn = sqlite3.connect('usuarios.db')
                c = conn.cursor()
                c.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit()
                conn.close()
                st.success("Conta criada! Vá em 'Entrar'.")
            except: st.error("E-mail já existe.")
    
    with abas_login[2]:
        email_alvo = st.text_input("E-mail da conta", key="rec_em")
        if st.button("Enviar Nova Senha"):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            if c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone():
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                if enviar_senha_nova(email_alvo, nova): st.success("Senha enviada!")
                else: st.error("Erro no envio.")
            else: st.error("E-mail não encontrado.")
            conn.close()

    with abas_login[3]:
        alt_em = st.text_input("Confirme E-mail", key="alt_em")
        alt_at = st.text_input("Senha Atual", type="password", key="alt_at")
        alt_n1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        if st.button("Confirmar Alteração"):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit()
                st.success("Senha alterada!")
            else: st.error("Dados incorretos.")
            conn.close()
    st.stop()

# ================= FUNÇÕES DE DADOS E LAYOUT =================

def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    if 'Usuario' not in df.columns:
        df['Usuario'] = st.session_state.user_email
    return df[df['Usuario'] == st.session_state.user_email].copy()

def cor_glicemia_status(v):
    try:
        n = int(v)
        if n < 70: return 'background-color: #FFFFE0; color: black;'
        elif n > 180: return 'background-color: #FFB6C1; color: black;'
        else: return 'background-color: #C8E6C9; color: black;'
    except: return ''

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

# TABELA COM C, P, G
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], 
    "Leite (200ml)": [10, 6, 6], 
    "Arroz": [15, 1, 0], 
    "Feijão": [14, 5, 0], 
    "Frango": [0, 23, 5], 
    "Ovo": [1, 6, 5], 
    "Banana": [22, 1, 0], 
    "Maçã": [15, 0, 0]
}

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty: return "0 UI", "Configurar Receita"
    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    if v < 70: return "0 UI", "Hipoglicemia!"
    elif v <= 200: d = rec[f'{periodo}_f1']
    elif v <= 400: d = rec[f'{periodo}_f2']
    else: d = rec[f'{periodo}_f3']
    return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"

# ================= INTERFACE PRINCIPAL =================

st.sidebar.info(f"Usuário: {st.session_state.user_email}")

tab1, tab2, tab3 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfg = carregar_dados_seguro(ARQ_G)
    c1, c2 = st.columns([1, 2])
    with c1:
        v_gl = st.number_input("Valor", 0, 600, 100, key="v_gl_in")
        m_gl = st.selectbox("Momento", MOMENTOS_ORDEM, key="m_gl_in")
        dose, msg_d = calc_insulina(v_gl, m_gl)
        st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
            base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
            pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.rerun()
    with c2:
        if not dfg.empty:
            dfg['DT'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            st.plotly_chart(px.line(dfg.tail(10), x='DT', y='Valor', markers=True), use_container_width=True)
    
    st.write("### Histórico de Glicemias (Marcações)")
    if not dfg.empty:
        st.dataframe(dfg.tail(15).style.applymap(cor_glicemia_status, subset=['Valor']), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfn = carregar_dados_seguro(ARQ_N)
    
    st.write("### Registrar Refeição por Momento")
    m_nutri = st.selectbox("Selecione o Momento da Refeição", MOMENTOS_ORDEM, key="m_nutri_sel")
    sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
    
    # CÁLCULOS TOTAIS C, P, G
    c_tot = sum([ALIMENTOS[x][0] for x in sel])
    p_tot = sum([ALIMENTOS[x][1] for x in sel])
    g_tot = sum([ALIMENTOS[x][2] for x in sel])
    
    # EXIBIÇÃO DOS TOTAIS NA TELA
    col_c, col_p, col_g = st.columns(3)
    col_c.metric("C (Carbo)", f"{c_tot}g")
    col_p.metric("P (Proteína)", f"{p_tot}g")
    col_g.metric("G (Gordura)", f"{g_tot}g")
    
    if st.button("💾 Salvar Alimentação"):
        agora = datetime.now(fuso_br)
        novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], 
                             columns=["Usuario","Data","Momento","Info","C","P","G"])
        base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
        pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
        st.rerun()
        
    st.write("### Histórico de Nutrição")
    st.dataframe(dfn.tail(15), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
    r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
    v = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    
    cm, cn = st.columns(2)
    with cm:
        st.info("MANHÃ")
        m1 = st.number_input("Dose 70-200", value=int(v.get('manha_f1',0)), key="m1")
        m2 = st.number_input("Dose 201-400", value=int(v.get('manha_f2',0)), key="m2")
        m3 = st.number_input("Dose > 400", value=int(v.get('manha_f3',0)), key="m3")
    with cn:
        st.info("NOITE")
        n1 = st.number_input("Dose 70-200 ", value=int(v.get('noite_f1',0)), key="n1")
        n2 = st.number_input("Dose 201-400 ", value=int(v.get('noite_f2',0)), key="n2")
        n3 = st.number_input("Dose > 400 ", value=int(v.get('noite_f3',0)), key="n3")
    if st.button("💾 Salvar Receita"):
        nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':m1, 'manha_f2':m2, 'manha_f3':m3, 'noite_f1':n1, 'noite_f2':n2, 'noite_f3':n3}])
        df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
        st.success("Receita Salva!")
    st.markdown('</div>', unsafe_allow_html=True)

# ================= GERAR EXCEL COM DUAS ABAS (CORRIGIDO) =================
st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Colorido"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # ABA 1: GLICEMIA (PIVOT E CORES)
        if not df_e_g.empty:
            df_e_g['Exibe'] = df_e_g['Valor'].astype(str)
            pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last')
            colunas_existentes = [c for c in MOMENTOS_ORDEM if c in pivot.columns]
            pivot = pivot[colunas_existentes]
            pivot.to_excel(writer, sheet_name='Glicemia')
            
            ws = writer.sheets['Glicemia']
            f_v = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
            f_r = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")
            f_a = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")
            
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "None":
                        try:
                            val = int(cell.value)
                            cell.alignment = Alignment(horizontal='center')
                            if val < 70: cell.fill = f_a
                            elif val > 180: cell.fill = f_r
                            else: cell.fill = f_v
                        except: pass
        
        # ABA 2: ALIMENTOS (NUTRIÇÃO COMPLETA)
        if not df_e_n.empty:
            df_e_n.to_excel(writer, sheet_name='Alimentos', index=False)
            
    if not df_e_g.empty or not df_e_n.empty:
        st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name=f"Relatorio_{st.session_state.user_email}.xlsx")
    else: st.sidebar.warning("Sem dados.")

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
