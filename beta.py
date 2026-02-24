Entendido. Modifiquei **exclusivamente** a aba "Pessoas Cadastradas" dentro do painel do Administrador. Agora, além de listar os usuários, você tem um campo para selecionar um e-mail da lista e definir uma nova senha para esse usuário diretamente.

### 📋 Checklist de Alterações

1. **✅ Função de Alteração para Admin:** Adicionado bloco de código que permite ao admin escolher um usuário e sobrescrever a senha no banco de dados.
2. **✅ Preservação Total:** Nenhuma outra funcionalidade (Glicemia, Nutrição, Receita, Gráficos ou Login) foi alterada, conforme solicitado.

---

### 💻 Código Atualizado (Foco no Poder do Admin)

```python
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
ARQ_M = "mensagens_admin_BETA.csv" 

# DESIGN DARK MODE
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; padding: 25px; border-radius: 20px; border: 1px solid #30363d; margin-bottom: 25px; }
    .metric-box { background: #262730; border: 1px solid #4a4a4a; padding: 15px; border-radius: 12px; text-align: center; }
    .dose-destaque { font-size: 38px; font-weight: 700; color: #4ade80; }
    label, p, span, h1, h2, h3, .stMarkdown { color: white !important; }
    .stTextInput>div>div>input, .stNumberInput>div>div>input { background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; }
</style>
""", unsafe_allow_html=True)

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
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    try:
        if v < 70: return "0 UI", "Hipoglicemia!"
        elif v <= 200: d = rec[f'{periodo}_f1']
        elif v <= 400: d = rec[f'{periodo}_f2']
        else: d = rec[f'{periodo}_f3']
        return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"
    except: return "0 UI", "Erro na Receita"

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

ALIMENTOS = {
    "Pão Francês (1un)": [28, 4, 1], "Pão de Forma (2 fatias)": [24, 4, 2], "Pão Integral (2 fatias)": [22, 5, 2],
    "Tapioca (50g)": [27, 0, 0], "Arroz Branco (servir)": [10, 2, 0], "Arroz Integral (servir)": [8, 2, 1],
    "Feijão (concha)": [14, 5, 1], "Carne Boi (100g)": [0, 26, 12], "Frango (100g)": [0, 31, 4],
    "Peixe (100g)": [0, 20, 5], "Ovo Cozido (1un)": [1, 6, 5], "Macarrão (pegador)": [30, 5, 1],
    "Batata Doce (100g)": [20, 2, 0], "Banana (1un)": [22, 1, 0], "Maçã (1un)": [15, 0, 0]
}

# ================= INTERFACE PRINCIPAL =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel Admin - Gestão Estratégica")
    
    t_usuarios, t_metricas, t_sugestoes = st.tabs(["👥 Pessoas Cadastradas", "📈 Crescimento e App", "📩 Sugestões"])
    
    conn = sqlite3.connect('usuarios.db')
    df_users = pd.read_sql_query("SELECT nome, email FROM users", conn)
    conn.close()

    with t_usuarios:
        st.subheader("Lista de Usuários")
        st.dataframe(df_users, use_container_width=True)
        st.metric("Total de Cadastros", len(df_users))
        
        st.markdown("---")
        st.subheader("🔑 Alterar Senha de Usuário (Poder Admin)")
        user_selecionado = st.selectbox("Selecione o E-mail do Usuário", df_users['email'].tolist())
        nova_senha_admin = st.text_input("Digite a Nova Senha para este usuário", type="password")
        
        if st.button("Confirmar Alteração de Senha", use_container_width=True):
            if nova_senha_admin:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("UPDATE users SET senha=? WHERE email=?", (nova_senha_admin, user_selecionado))
                conn.commit()
                conn.close()
                st.success(f"Senha de {user_selecionado} alterada com sucesso!")
            else:
                st.warning("Digite uma senha antes de confirmar.")

    with t_metricas:
        c1, c2 = st.columns(2)
        with c1:
            st.write("### Distribuição de Acessos (Pizza)")
            if os.path.exists(ARQ_G):
                df_uso = pd.read_csv(ARQ_G)
                uso_por_user = df_uso['Usuario'].value_counts().reset_index()
                uso_por_user.columns = ['Usuario', 'Registros']
                fig_pizza = px.pie(uso_por_user, values='Registros', names='Usuario', hole=.3, color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.info("Aguardando dados de uso.")
        
        with c2:
            st.write("### Crescimento de Cadastros")
            dados_crescimento = pd.DataFrame({
                'Mês': ['Jan', 'Fev', 'Mar'],
                'Usuários': [len(df_users)//2, len(df_users)//1.2, len(df_users)]
            })
            fig_line = px.line(dados_crescimento, x='Mês', y='Usuários', markers=True, title="Novos Cadastros")
            st.plotly_chart(fig_line, use_container_width=True)

    with t_sugestoes:
        if os.path.exists(ARQ_M):
            df_msg = pd.read_csv(ARQ_M)
            st.dataframe(df_msg, use_container_width=True)
        else:
            st.info("Nenhuma mensagem recebida.")

else:
    # --- INTERFACE DO USUÁRIO (MANTIDA) ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita", "📩 Sugerir Melhoria"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfg = carregar_dados_seguro(ARQ_G)
        c1, c2 = st.columns([1, 2])
        with c1:
            v_gl = st.number_input("Valor Glicemia", 0, 600, 100)
            m_gl = st.selectbox("Momento", MOMENTOS_ORDEM)
            dose, msg_d = calc_insulina(v_gl, m_gl)
            st.markdown(f'<div class="metric-box"><small>{msg_d}</small><br><span class="dose-destaque">{dose}</span></div>', unsafe_allow_html=True)
            if st.button("💾 Salvar Glicemia", use_container_width=True):
                agora = datetime.now(fuso_br)
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]], columns=["Usuario","Data","Hora","Valor","Momento","Dose"])
                base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
                pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)
                st.rerun()
        with c2:
            if not dfg.empty:
                fig = px.line(dfg.tail(10), x='Hora', y='Valor', markers=True, title="Tendência")
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
                st.plotly_chart(fig, use_container_width=True)
                
        if not dfg.empty:
            def cor_gl(v):
                try:
                    n = int(v)
                    if n < 70: return 'background-color: #8B8000' 
                    elif n > 180: return 'background-color: #8B0000' 
                    else: return 'background-color: #006400' 
                except: return ''
            st.dataframe(dfg.tail(15).style.applymap(cor_gl, subset=['Valor']), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfn = carregar_dados_seguro(ARQ_N)
        m_nutri = st.selectbox("Refeição", MOMENTOS_ORDEM, key="n_m")
        sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))
        c_tot, p_tot, g_tot = sum([ALIMENTOS[x][0] for x in sel]), sum([ALIMENTOS[x][1] for x in sel]), sum([ALIMENTOS[x][2] for x in sel])
        c1, c2, c3 = st.columns(3)
        c1.metric("Carbs", f"{c_tot}g"); c2.metric("Prot", f"{p_tot}g"); c3.metric("Gord", f"{g_tot}g")
        if st.button("💾 Salvar Refeição", use_container_width=True):
            agora = datetime.now(fuso_br)
            novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]], columns=["Usuario","Data","Momento","Info","C","P","G"])
            base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
            pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()
        st.dataframe(dfn.tail(10), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("⚙️ Configuração de Receita")
        df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        v = r_u.iloc[0] if not r_u.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
        cm, cn = st.columns(2)
        with cm:
            m1 = st.number_input("Manhã 70-200", value=int(v.get('manha_f1',0)), key="m1")
            m2 = st.number_input("Manhã 201-400", value=int(v.get('manha_f2',0)), key="m2")
            m3 = st.number_input("Manhã > 400", value=int(v.get('manha_f3',0)), key="m3")
        with cn:
            n1 = st.number_input("Noite 70-200", value=int(v.get('noite_f1',0)), key="n1")
            n2 = st.number_input("Noite 201-400", value=int(v.get('noite_f2',0)), key="n2")
            n3 = st.number_input("Noite > 400", value=int(v.get('noite_f3',0)), key="n3")
        if st.button("💾 Salvar Receita", use_container_width=True):
            nova_rec = pd.DataFrame([{'Usuario': st.session_state.user_email, 'manha_f1':m1, 'manha_f2':m2, 'manha_f3':m3, 'noite_f1':n1, 'noite_f2':n2, 'noite_f3':n3}])
            df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
            pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
            st.success("Receita Salva!")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📩 Enviar Sugestão de Melhoria")
        txt_melhoria = st.text_area("Descreva aqui o que podemos melhorar:")
        if st.button("Enviar para Admin", use_container_width=True):
            if txt_melhoria:
                agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M")
                nova_msg = pd.DataFrame([[st.session_state.user_email, agora, txt_melhoria]], columns=["Usuario", "Data", "Sugestão"])
                base_msg = pd.read_csv(ARQ_M) if os.path.exists(ARQ_M) else pd.DataFrame()
                pd.concat([base_msg, nova_msg], ignore_index=True).to_csv(ARQ_M, index=False)
                st.success("Sua sugestão foi enviada!")
            else:
                st.warning("Escreva algo antes de enviar.")
        st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL =================
st.sidebar.markdown("---")
if st.sidebar.button("📥 Gerar Excel Colorido"):
    df_e_g = carregar_dados_seguro(ARQ_G)
    df_e_n = carregar_dados_seguro(ARQ_N)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_e_g.empty:
            pivot = df_e_g.pivot_table(index='Data', columns='Momento', values='Valor', aggfunc='last')
            cols = [c for c in MOMENTOS_ORDEM if c in pivot.columns]
            pivot[cols].to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            f_v, f_r, f_a = PatternFill("solid", fgColor="C8E6C9"), PatternFill("solid", fgColor="FFB6C1"), PatternFill("solid", fgColor="FFFFE0")
            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value:
                        try:
                            val = int(cell.value); cell.alignment = Alignment(horizontal='center')
                            if val < 70: cell.fill = f_a
                            elif val > 180: cell.fill = f_r
                            else: cell.fill = f_v
                        except: pass
        if not df_e_n.empty: df_e_n.to_excel(writer, sheet_name='Alimentos', index=False)
    st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name="SaudeKids_Relatorio.xlsx")

if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()

```
