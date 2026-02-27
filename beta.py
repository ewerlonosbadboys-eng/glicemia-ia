import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
import zipfile
import shutil
from pathlib import Path

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_M = "mensagens_admin_BETA.csv"

# ================= BACKUP / RESTORE =================
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_STATE_FILE = BACKUP_DIR / "last_auto_backup.txt"

ARQUIVOS_BACKUP = [
    "usuarios.db",
    ARQ_G,
    ARQ_N,
    ARQ_R,
    ARQ_M,
]

def agora_br():
    return datetime.now(fuso_br)

def criar_backup_zip_em_bytes():
    ts = agora_br().strftime("%Y-%m-%d_%H-%M-%S")
    nome = f"backup_saude_kids_{ts}.zip"
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for arq in ARQUIVOS_BACKUP:
            if os.path.exists(arq):
                z.write(arq)
    out.seek(0)
    return out.getvalue(), nome

def criar_backup_zip_em_disco():
    ts = agora_br().strftime("%Y-%m-%d_%H-%M-%S")
    nome = f"backup_saude_kids_{ts}.zip"
    caminho = BACKUP_DIR / nome
    with zipfile.ZipFile(caminho, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for arq in ARQUIVOS_BACKUP:
            if os.path.exists(arq):
                z.write(arq)
    return caminho

def restaurar_backup_zip_bytes(zip_bytes: bytes):
    tmp_dir = BACKUP_DIR / "_tmp_restore"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as z:
        z.extractall(tmp_dir)

    for arq in ARQUIVOS_BACKUP:
        src = tmp_dir / arq
        if src.exists():
            shutil.copy(src, arq)

    shutil.rmtree(tmp_dir)

def backup_automatico_diario_3h():
    # Streamlit roda quando acessa; regra: após 03:00, se não fez backup hoje => faz 1.
    agora = agora_br()
    hoje = agora.strftime("%Y-%m-%d")
    if agora.hour >= 3:
        ultima = ""
        if BACKUP_STATE_FILE.exists():
            ultima = BACKUP_STATE_FILE.read_text(encoding="utf-8").strip()
        if ultima != hoje:
            criar_backup_zip_em_disco()
            BACKUP_STATE_FILE.write_text(hoje, encoding="utf-8")

def listar_backups():
    backups = []
    for p in sorted(BACKUP_DIR.glob("backup_saude_kids_*.zip")):
        stat = p.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, tz=fuso_br)
        backups.append({
            "arquivo": p.name,
            "caminho": str(p),
            "data_hora": dt,
            "tamanho_mb": round(stat.st_size / (1024 * 1024), 2),
        })
    if not backups:
        return pd.DataFrame(columns=["arquivo", "caminho", "data_hora", "tamanho_mb"])
    df = pd.DataFrame(backups).sort_values("data_hora", ascending=False).reset_index(drop=True)
    return df

def apagar_backups_antigos(dias_manter=7):
    limite = agora_br() - timedelta(days=dias_manter)
    apagados = 0
    for p in BACKUP_DIR.glob("backup_saude_kids_*.zip"):
        dt = datetime.fromtimestamp(p.stat().st_mtime, tz=fuso_br)
        if dt < limite:
            try:
                p.unlink()
                apagados += 1
            except:
                pass
    return apagados

backup_automatico_diario_3h()

# ================= DESIGN DARK MODE =================
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
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com"
    minha_senha = st.secrets.get("GMAIL_APP_PASSWORD", "okiu qihp lglk trcc")

    if not minha_senha:
        return False

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
    except:
        return False

def init_db():
    conn = sqlite3.connect('usuarios.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (nome TEXT, email TEXT PRIMARY KEY, senha TEXT)''')
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
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
        if st.button("Acessar Aplicativo", use_container_width=True):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone():
                st.session_state.logado = True
                st.session_state.user_email = u
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")
            conn.close()

    with abas_login[1]:
        n_cad = st.text_input("Nome Completo")
        e_cad = st.text_input("E-mail para Cadastro")
        s_cad = st.text_input("Senha para Cadastro", type="password")
        if st.button("Realizar Cadastro", use_container_width=True):
            try:
                conn = sqlite3.connect('usuarios.db')
                conn.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                conn.commit()
                conn.close()
                st.success("Conta criada com sucesso!")
            except:
                st.error("Este e-mail já está cadastrado.")

    with abas_login[2]:
        email_alvo = st.text_input("Digite seu e-mail cadastrado")
        if st.button("Recuperar Acesso", use_container_width=True):
            conn = sqlite3.connect('usuarios.db')
            c = conn.cursor()
            user = c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone()
            if user:
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()

                if enviar_senha_nova(email_alvo, nova):
                    st.success("Nova senha enviada para seu e-mail!")
                else:
                    st.warning("E-mail não configurado no app.")
                    st.info("Use a senha temporária abaixo para entrar e depois altere sua senha:")
                    st.code(nova)
            else:
                st.error("E-mail não encontrado.")
            conn.close()

    with abas_login[3]:
        alt_em = st.text_input("Confirme seu E-mail", key="alt_em")
        alt_at = st.text_input("Senha Atual", type="password", key="alt_at")
        alt_n1 = st.text_input("Nova Senha", type="password", key="alt_n1")
        if st.button("Confirmar Alteração", use_container_width=True):
            conn = sqlite3.connect('usuarios.db')
            if conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone():
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit()
                st.success("Senha alterada com sucesso!")
            else:
                st.error("Dados atual incorretos.")
            conn.close()

    st.stop()

# ================= FUNÇÕES DE APOIO =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq):
        return pd.DataFrame()
    df = pd.read_csv(arq)
    if 'Usuario' not in df.columns:
        df['Usuario'] = st.session_state.user_email
    return df[df['Usuario'] == st.session_state.user_email].copy()

def _schema_receita_nova(rec: pd.Series, periodo: str) -> bool:
    need = [
        f"{periodo}_f1_min", f"{periodo}_f1_max", f"{periodo}_f1_dose",
        f"{periodo}_f2_min", f"{periodo}_f2_max", f"{periodo}_f2_dose",
        f"{periodo}_f3_min", f"{periodo}_f3_max", f"{periodo}_f3_dose"
    ]
    return all(k in rec.index for k in need)

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty:
        return "0 UI", "Configurar Receita"

    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"

    try:
        if _schema_receita_nova(rec, periodo):
            f1_min = float(rec[f"{periodo}_f1_min"]); f1_max = float(rec[f"{periodo}_f1_max"]); f1_dose = float(rec[f"{periodo}_f1_dose"])
            f2_min = float(rec[f"{periodo}_f2_min"]); f2_max = float(rec[f"{periodo}_f2_max"]); f2_dose = float(rec[f"{periodo}_f2_dose"])
            f3_min = float(rec[f"{periodo}_f3_min"]); f3_max = float(rec[f"{periodo}_f3_max"]); f3_dose = float(rec[f"{periodo}_f3_dose"])

            if v < 70:
                return "0 UI", "Hipoglicemia!"

            if f1_min <= v <= f1_max:
                return f"{int(f1_dose)} UI", f"Faixa 1 ({int(f1_min)}-{int(f1_max)})"
            elif f2_min <= v <= f2_max:
                return f"{int(f2_dose)} UI", f"Faixa 2 ({int(f2_min)}-{int(f2_max)})"
            elif f3_min <= v <= f3_max:
                return f"{int(f3_dose)} UI", f"Faixa 3 ({int(f3_min)}-{int(f3_max)})"
            else:
                return "0 UI", "Fora das faixas"

        if v < 70:
            return "0 UI", "Hipoglicemia!"
        elif v <= 200:
            d = rec.get(f"{periodo}_f1", 0)
        elif v <= 400:
            d = rec.get(f"{periodo}_f2", 0)
        else:
            d = rec.get(f"{periodo}_f3", 0)

        return f"{int(d)} UI", f"Tabela {periodo.capitalize()}"

    except:
        return "0 UI", "Erro na Receita"

MOMENTOS_ORDEM = ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

ALIMENTOS = {
    "Pão Francês (1un)": [28, 4, 1],
    "Pão de Forma (2 fatias)": [24, 4, 2],
    "Pão Integral (2 fatias)": [22, 5, 2],
    "Tapioca (50g)": [27, 0, 0],
    "Arroz Branco (servir)": [10, 2, 0],
    "Arroz Integral (servir)": [8, 2, 1],
    "Feijão (concha)": [14, 5, 1],
    "Carne Boi (100g)": [0, 26, 12],
    "Frango (100g)": [0, 31, 4],
    "Peixe (100g)": [0, 20, 5],
    "Ovo Cozido (1un)": [1, 6, 5],
    "Macarrão (pegador)": [30, 5, 1],
    "Batata Doce (100g)": [20, 2, 0],
    "Banana (1un)": [22, 1, 0],
    "Maçã (1un)": [15, 0, 0]
}

# ================= INTERFACE PRINCIPAL =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel Admin - Gestão Estratégica")
    t_usuarios, t_metricas, t_sugestoes, t_backup = st.tabs(
        ["👥 Pessoas Cadastradas", "📈 Crescimento e App", "📩 Sugestões", "💾 Backup & Restauração"]
    )

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
            st.write("### Distribuição de Acessos")
            if os.path.exists(ARQ_G):
                df_uso = pd.read_csv(ARQ_G)
                uso_por_user = df_uso['Usuario'].value_counts().reset_index()
                uso_por_user.columns = ['Usuario', 'Registros']
                fig_pizza = px.pie(uso_por_user, values='Registros', names='Usuario', hole=.3)
                st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.info("Sem dados.")
        with c2:
            st.write("### Crescimento")
            dados_c = pd.DataFrame({'Mês': ['Jan', 'Fev', 'Mar'], 'Usuários': [len(df_users)//2, int(len(df_users)/1.1), len(df_users)]})
            st.plotly_chart(px.line(dados_c, x='Mês', y='Usuários', markers=True), use_container_width=True)

    with t_sugestoes:
        if os.path.exists(ARQ_M):
            st.dataframe(pd.read_csv(ARQ_M), use_container_width=True)
        else:
            st.info("Sem sugestões.")

    with t_backup:
        st.subheader("💾 Backup Manual / Automático / Restauração")

        st.write("### 📦 Gerar Backup Manual")
        if st.button("📦 Gerar Backup Agora", use_container_width=True):
            b, nome = criar_backup_zip_em_bytes()
            st.download_button("⬇️ Baixar Backup (.zip)", b, file_name=nome, use_container_width=True)

        st.markdown("---")
        st.write("### ♻️ Restauração Manual")
        up = st.file_uploader("Enviar arquivo .zip de backup", type=["zip"])
        if up is not None:
            if st.button("✅ Restaurar Agora", use_container_width=True):
                restaurar_backup_zip_bytes(up.getvalue())
                st.success("Restauração concluída! Recarregue o app (F5).")

        st.markdown("---")
        st.write("### ⏰ Backup Automático")
        st.info("Config: 1 backup por dia após **03:00** (Brasília).")
        if BACKUP_STATE_FILE.exists():
            st.caption(f"Último dia registrado: {BACKUP_STATE_FILE.read_text(encoding='utf-8').strip()}")

        st.markdown("---")
        st.write("### 🗂️ Backups existentes (pasta backups/)")
        df_bk = listar_backups()
        if df_bk.empty:
            st.warning("Nenhum backup encontrado.")
        else:
            df_show = df_bk.copy()
            df_show["data_hora"] = df_show["data_hora"].dt.strftime("%d/%m/%Y %H:%M:%S")
            st.dataframe(df_show[["arquivo", "data_hora", "tamanho_mb"]], use_container_width=True)

            st.markdown("#### Ações")
            selecionado = st.selectbox("Selecionar backup", df_bk["arquivo"].tolist())
            p_sel = BACKUP_DIR / selecionado

            colx1, colx2, colx3 = st.columns(3)
            with colx1:
                if p_sel.exists():
                    with open(p_sel, "rb") as f:
                        st.download_button("⬇️ Baixar Selecionado", f.read(), file_name=selecionado, use_container_width=True)
            with colx2:
                if st.button("🗑️ Apagar Selecionado", use_container_width=True):
                    if p_sel.exists():
                        p_sel.unlink()
                        st.success("Backup apagado.")
                        st.rerun()
            with colx3:
                if st.button("🧹 Apagar Antigos (7 dias)", use_container_width=True):
                    apagados = apagar_backups_antigos(dias_manter=7)
                    st.success(f"Apagados: {apagados}")
                    st.rerun()

else:
    # --- INTERFACE USUÁRIO ---
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
                agora = agora_br()
                novo = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_gl, m_gl, dose]],
                                    columns=["Usuario", "Data", "Hora", "Valor", "Momento", "Dose"])
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
                    if n < 70:
                        return 'background-color: #8B8000'
                    elif n > 180:
                        return 'background-color: #8B0000'
                    else:
                        return 'background-color: #006400'
                except:
                    return ''
            st.dataframe(dfg.tail(15).style.applymap(cor_gl, subset=['Valor']), use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfn = carregar_dados_seguro(ARQ_N)

        m_nutri = st.selectbox("Refeição", MOMENTOS_ORDEM, key="n_m")
        sel = st.multiselect("Alimentos", list(ALIMENTOS.keys()))

        c_tot = sum([ALIMENTOS[x][0] for x in sel])
        p_tot = sum([ALIMENTOS[x][1] for x in sel])
        g_tot = sum([ALIMENTOS[x][2] for x in sel])

        col1, col2, col3 = st.columns(3)
        col1.metric("Carbos", f"{c_tot}g")
        col2.metric("Proteínas", f"{p_tot}g")
        col3.metric("Gorduras", f"{g_tot}g")

        if st.button("💾 Salvar Refeição", use_container_width=True):
            agora = agora_br()
            novo_n = pd.DataFrame([[st.session_state.user_email, agora.strftime("%d/%m/%Y"), m_nutri, ", ".join(sel), c_tot, p_tot, g_tot]],
                                  columns=["Usuario", "Data", "Momento", "Info", "C", "P", "G"])
            base = pd.read_csv(ARQ_N) if os.path.exists(ARQ_N) else pd.DataFrame()
            pd.concat([base, novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()

        st.dataframe(dfn.tail(10), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        df_r_all = pd.read_csv(ARQ_R) if os.path.exists(ARQ_R) else pd.DataFrame()
        r_u = df_r_all[df_r_all['Usuario'] == st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
        v = r_u.iloc[0] if not r_u.empty else {}

        st.subheader("🌞 Receita Manhã (Editável)")
        cm1, cm2, cm3 = st.columns(3)
        with cm1:
            m1_min = st.number_input("Faixa 1 - Mín", value=int(v.get('manha_f1_min', 70)), key="m1_min_u")
            m1_max = st.number_input("Faixa 1 - Máx", value=int(v.get('manha_f1_max', 150)), key="m1_max_u")
            m1_dose = st.number_input("Dose Faixa 1 (UI)", value=int(v.get('manha_f1_dose', 3)), key="m1_dose_u")
        with cm2:
            m2_min = st.number_input("Faixa 2 - Mín", value=int(v.get('manha_f2_min', 151)), key="m2_min_u")
            m2_max = st.number_input("Faixa 2 - Máx", value=int(v.get('manha_f2_max', 300)), key="m2_max_u")
            m2_dose = st.number_input("Dose Faixa 2 (UI)", value=int(v.get('manha_f2_dose', 5)), key="m2_dose_u")
        with cm3:
            m3_min = st.number_input("Faixa 3 - Mín", value=int(v.get('manha_f3_min', 301)), key="m3_min_u")
            m3_max = st.number_input("Faixa 3 - Máx", value=int(v.get('manha_f3_max', 600)), key="m3_max_u")
            m3_dose = st.number_input("Dose Faixa 3 (UI)", value=int(v.get('manha_f3_dose', 8)), key="m3_dose_u")

        st.markdown("---")
        st.subheader("🌙 Receita Noite (Editável)")
        cn1, cn2, cn3 = st.columns(3)
        with cn1:
            n1_min = st.number_input("Faixa 1 - Mín", value=int(v.get('noite_f1_min', 70)), key="n1_min_u")
            n1_max = st.number_input("Faixa 1 - Máx", value=int(v.get('noite_f1_max', 150)), key="n1_max_u")
            n1_dose = st.number_input("Dose Faixa 1 (UI)", value=int(v.get('noite_f1_dose', 3)), key="n1_dose_u")
        with cn2:
            n2_min = st.number_input("Faixa 2 - Mín", value=int(v.get('noite_f2_min', 151)), key="n2_min_u")
            n2_max = st.number_input("Faixa 2 - Máx", value=int(v.get('noite_f2_max', 300)), key="n2_max_u")
            n2_dose = st.number_input("Dose Faixa 2 (UI)", value=int(v.get('noite_f2_dose', 5)), key="n2_dose_u")
        with cn3:
            n3_min = st.number_input("Faixa 3 - Mín", value=int(v.get('noite_f3_min', 301)), key="n3_min_u")
            n3_max = st.number_input("Faixa 3 - Máx", value=int(v.get('noite_f3_max', 600)), key="n3_max_u")
            n3_dose = st.number_input("Dose Faixa 3 (UI)", value=int(v.get('noite_f3_dose', 8)), key="n3_dose_u")

        if st.button("💾 Salvar Receita", use_container_width=True):
            nova_rec = pd.DataFrame([{
                'Usuario': st.session_state.user_email,
                'manha_f1_min': m1_min, 'manha_f1_max': m1_max, 'manha_f1_dose': m1_dose,
                'manha_f2_min': m2_min, 'manha_f2_max': m2_max, 'manha_f2_dose': m2_dose,
                'manha_f3_min': m3_min, 'manha_f3_max': m3_max, 'manha_f3_dose': m3_dose,
                'noite_f1_min': n1_min, 'noite_f1_max': n1_max, 'noite_f1_dose': n1_dose,
                'noite_f2_min': n2_min, 'noite_f2_max': n2_max, 'noite_f2_dose': n2_dose,
                'noite_f3_min': n3_min, 'noite_f3_max': n3_max, 'noite_f3_dose': n3_dose,
            }])

            df_r_all = df_r_all[df_r_all['Usuario'] != st.session_state.user_email] if not df_r_all.empty else pd.DataFrame()
            pd.concat([df_r_all, nova_rec], ignore_index=True).to_csv(ARQ_R, index=False)
            st.success("Receita salva com sucesso!")

        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        txt = st.text_area("Sugestão de Melhoria:")
        if st.button("Enviar Sugestão"):
            if txt:
                agora = agora_br().strftime("%d/%m/%Y %H:%M")
                novo_m = pd.DataFrame([[st.session_state.user_email, agora, txt]],
                                      columns=["Usuario", "Data", "Sugestão"])
                base_m = pd.read_csv(ARQ_M) if os.path.exists(ARQ_M) else pd.DataFrame()
                pd.concat([base_m, novo_m], ignore_index=True).to_csv(ARQ_M, index=False)
                st.success("Enviado com sucesso!")
        st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COM DUAS ABAS (GLICEMIA E NUTRIÇÃO) =================
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

            f_v = PatternFill("solid", fgColor="C8E6C9")
            f_r = PatternFill("solid", fgColor="FFB6C1")
            f_a = PatternFill("solid", fgColor="FFFFE0")

            for row in ws1.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value is not None and str(cell.value) != "nan":
                        try:
                            val = int(cell.value)
                            cell.alignment = Alignment(horizontal='center')
                            if val < 70:
                                cell.fill = f_a
                            elif val > 180:
                                cell.fill = f_r
                            else:
                                cell.fill = f_v
                        except:
                            pass

        if not df_e_n.empty:
            df_e_n.to_excel(writer, sheet_name='Nutrição', index=False)
            ws2 = writer.sheets['Nutrição']
            for cell in ws2[1]:
                cell.alignment = Alignment(horizontal='center')

    st.sidebar.download_button("Baixar Agora", output.getvalue(), file_name="Relatorio_Saude_Kids.xlsx")

if st.sidebar.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
