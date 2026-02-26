import streamlit as st
import pandas as pd
from datetime import datetime, time
import os
import shutil
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill, Alignment
import sqlite3
import smtplib
from email.mime.text import MIMEText
import random
import string
import urllib.parse

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_M = "mensagens_admin_BETA.csv"
PASTA_BACKUP = "backups_saude_kids"

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    .alerta-zap { background-color: #25D366; color: white !important; font-weight: bold; border-radius: 10px; padding: 10px; text-align: center; display: block; text-decoration: none; margin-top: 10px; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important; }
</style>
""", unsafe_allow_html=True)

# ================= SISTEMA DE BACKUP =================
def realizar_backup():
    if not os.path.exists(PASTA_BACKUP): os.makedirs(PASTA_BACKUP)
    hoje = datetime.now(fuso_br).strftime("%Y-%m-%d")
    arquivos = [ARQ_G, ARQ_N, ARQ_R, ARQ_M, "usuarios.db"]
    for arq in arquivos:
        if os.path.exists(arq):
            shutil.copy(arq, os.path.join(PASTA_BACKUP, f"{hoje}_{arq}"))

agora_hora = datetime.now(fuso_br).hour
if 'ultimo_backup' not in st.session_state:
    if agora_hora >= 3: 
        realizar_backup()
        st.session_state.ultimo_backup = datetime.now(fuso_br).date()

# ================= SEGURANÇA E LOGIN =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com" 
    minha_senha = "okiu qihp lglk trcc" 
    corpo = f"<h3>Saúde Kids</h3><p>Sua nova senha de acesso é: <b>{senha_nova}</b></p>"
    msg = MIMEText(corpo, 'html'); msg['Subject'] = 'Sua Nova Senha - Saúde Kids'; msg['From'] = meu_email; msg['To'] = email_destino
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except: return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
    conn.commit(); conn.close()

init_db()
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")
    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])
    
    with abas_login[0]:
        u = st.text_input("E-mail", key="l_email")
        s = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Aplicativo", use_container_width=True):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else: st.error("E-mail ou senha incorretos.")
            conn.close()
    # (Abas Criar Conta, Esqueci Senha e Alterar Senha permanecem iguais ao código base...)
    with abas_login[1]:
        n_cad = st.text_input("Nome Completo")
        e_cad = st.text_input("E-mail para Cadastro")
        s_cad = st.text_input("Senha para Cadastro", type="password")
        if st.button("Realizar Cadastro", use_container_width=True):
            try:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit(); conn.close()
                st.success("Conta criada com sucesso!")
            except: st.error("Este e-mail já está cadastrado.")
    with abas_login[2]:
        email_alvo = st.text_input("Digite seu e-mail cadastrado")
        if st.button("Recuperar Acesso", use_container_width=True):
            conn = sqlite3.connect('usuarios.db'); c = conn.cursor()
            user = c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone()
            if user:
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                if enviar_senha_nova(email_alvo, nova): st.success("Nova senha enviada para seu e-mail!")
                else: st.error("Erro ao enviar e-mail.")
            else: st.error("E-mail não encontrado.")
            conn.close()
    with abas_login[3]:
        alt_em = st.text_input("Confirme seu E-mail", key="alt_em")
        alt_at = st.text_input("Senha Atual", type="password", key="alt_at")
        alt_n1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        if st.button("Confirmar Alteração", use_container_width=True):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit(); st.success("Senha alterada com sucesso!")
            else: st.error("Dados atual incorretos.")
            conn.close()
    st.stop()

# ================= FUNÇÕES DE APOIO =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq): return pd.DataFrame()
    df = pd.read_csv(arq)
    return df[df['Usuario'] == st.session_state.user_email].copy()

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty: return "0 UI", "Configurar Receita"
    rec = df_r.iloc[0]
    p = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    
    try:
        # Lógica baseada nas faixas editáveis
        if v < rec[f'{p}_lim1']: return "0 UI", "Hipoglicemia!"
        elif v <= rec[f'{p}_lim2']: d = rec[f'{p}_f1']
        elif v <= rec[f'{p}_lim3']: d = rec[f'{p}_f2']
        else: d = rec[f'{p}_f3']
        return f"{int(d)} UI", f"Tabela {p.capitalize()}"
    except: return "0 UI", "Erro nos limites"

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]
ALIMENTOS = {"Pão Francês (1un)": [28, 4, 1], "Arroz Branco (servir)": [10, 2, 0], "Feijão (concha)": [14, 5, 1], "Banana (1un)": [22, 1, 0]}

# ================= INTERFACE PRINCIPAL =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel Admin")
    # (Painel Admin permanece igual ao código base...)
    t_usuarios, t_metricas, t_sugestoes, t_backup = st.tabs(["👥 Usuários", "📈 Métricas", "📩 Sugestões", "💾 Backups"])
    with t_backup:
        st.subheader("Histórico de Backups (Servidor)")
        if os.path.exists(PASTA_BACKUP):
            arquivos_b = os.listdir(PASTA_BACKUP)
            st.write(arquivos_b)
            if st.button("Forçar Novo Backup Agora"):
                realizar_backup(); st.success("Backup realizado!")
else:
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita", "📩 Sugerir"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfg = carregar_dados_seguro(ARQ_G)
        c1, c2 = st.columns([1, 2])
        with c1:
            v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
            m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
            dose, msg_d = calc_insulina(v_gl, m_gl)
            st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
            
            # Alerta WhatsApp se Crítico
            if v_gl < 70 or v_gl > 200:
                df_r = carregar_dados_seguro(ARQ_R)
                if not df_r.empty and str(df_r.iloc[0].get('whatsapp', '')) != '':
                    num = df_r.iloc[0]['whatsapp']
                    msg_zap = urllib.parse.quote(f"Alerta Saúde Kids: Glicemia de {st.session_state.user_email} está em {v_gl} mg/dL ({m_gl}).")
                    link = f"https://wa.me/55{num}?text={msg_zap}"
                    st.markdown(f'<a href="{link}" target="_blank" class="alerta-zap">⚠️ ENVIAR ALERTA WHATSAPP</a>', unsafe_allow_html=True)

            if st.button("💾 Salvar Glicemia", use_container_width=True):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
                base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
                pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False); st.rerun()
        with c2:
            if not dfg.empty:
                fig = px.line(dfg.tail(10), x='Hora', y='Valor', markers=True, title="Tendência")
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
                st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Configuração de Faixas e Doses")
        df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        v = r_u.iloc[0] if not r_u.empty else {'manha_lim1':70, 'manha_lim2':200, 'manha_lim3':400, 'noite_lim1':70, 'noite_lim2':200, 'noite_lim3':400, 'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0, 'whatsapp': ''}
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🌅 Período Manhã")
            lim_m1 = st.number_input("Mínimo (Abaixo disso é Hipo)", value=int(v.get('manha_lim1', 70)), key="lm1")
            m1_val = st.number_input(f"Dose se {lim_m1} até:", value=int(v.get('manha_lim2', 200)), key="lm2")
            m1_ui = st.number_input("UI (Unidades)", value=int(v.get('manha_f1', 0)), key="mu1")
            m2_val = st.number_input(f"Dose se {m1_val+1} até:", value=int(v.get('manha_lim3', 400)), key="lm3")
            m2_ui = st.number_input("UI (Unidades)", value=int(v.get('manha_f2', 0)), key="mu2")
            st.write(f"Acima de {m2_val}:")
            m3_ui = st.number_input("UI (Unidades)", value=int(v.get('manha_f3', 0)), key="mu3")
            
        with c2:
            st.markdown("### 🌙 Período Noite")
            lim_n1 = st.number_input("Mínimo (Abaixo disso é Hipo)", value=int(v.get('noite_lim1', 70)), key="ln1")
            n1_val = st.number_input(f"Dose se {lim_n1} até:", value=int(v.get('noite_lim2', 200)), key="ln2")
            n1_ui = st.number_input("UI (Unidades)", value=int(v.get('noite_f1', 0)), key="nu1")
            n2_val = st.number_input(f"Dose se {n1_val+1} até:", value=int(v.get('noite_lim3', 400)), key="ln3")
            n2_ui = st.number_input("UI (Unidades)", value=int(v.get('noite_f2', 0)), key="nu2")
            st.write(f"Acima de {n2_val}:")
            n3_ui = st.number_input("UI (Unidades)", value=int(v.get('noite_f3', 0)), key="nu3")
        
        st.markdown("---")
        zap = st.text_input("DDD + WhatsApp para Alertas (Apenas números)", value=v.get('whatsapp', ''))
        
        if st.button("💾 Salvar Configurações Médicas", use_container_width=True):
            nova_rec = pd.DataFrame([{
                'Usuario': st.session_state.user_email, 'whatsapp': zap,
                'manha_lim1': lim_m1, 'manha_lim2': m1_val, 'manha_lim3': m2_val,
                'noite_lim1': lim_n1, 'noite_lim2': n1_val, 'noite_lim3': n2_val,
                'manha_f1': m1_ui, 'manha_f2': m2_ui, 'manha_f3': m3_ui,
                'noite_f1': n1_ui, 'noite_f2': n2_ui, 'noite_f3': n3_ui
            }])
            df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
            pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False); st.success("Receita Atualizada!")
        st.markdown('</div>', unsafe_allow_html=True)

# (Aba Nutrição e Sidebar permanecem conforme o Beta original para preservar as funções de Excel e Sair)
    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfn = carregar_dados_seguro(ARQ_N)
        m_nutri = st.selectbox("Refeição", MOMENTOS_ORDEM, key="n_m")
        sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
        c_tot = sum([ALIMENTOS[x][0] for x in sel]); p_tot = sum([ALIMENTOS[x][1] for x in sel]); g_tot = sum([ALIMENTOS[x][2] for x in sel])
        col1, col2, col3 = st.columns(3)
        col1.metric("Carbos", f"{c_tot}g"); col2.metric("Proteínas", f"{p_tot}g"); col3.metric("Gorduras", f"{g_tot}g")
        if st.button("💾 Salvar Refeição", use_container_width=True):
            agora = datetime.now(fuso_br)
            novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], columns=["Usuario","Data","Momento","Info","C","P","G"])
            base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
            pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False); st.rerun()
        st.dataframe(dfn.tail(10), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Completo"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_e_g.empty:
            pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Valor', aggfunc='last')
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws1 = writer.sheets['Glicemia']
            f_v, f_r, f_a = PatternFill("solid", fgColor="C8E6C9"), PatternFill("solid", fgColor="FFB6C1"), PatternFill("solid", fgColor="FFFFE0")
            for row in ws1.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value:
                        try:
                            val = int(cell.value); cell.alignment = Alignment(horizontal='center')
                            if val < 70: cell.fill = f_a
                            elif val > 180: cell.fill = f_r
                            else: cell.fill = f_v
                        except: pass
        if not df_e_n.empty: df_e_n.to_excel(writer, sheet_name='Nutrição', index=False)
    st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name="Relatorio_Saude_Kids.xlsx")

if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
