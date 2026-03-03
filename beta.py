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
from urllib.parse import quote
import uuid

# =========================================================
# (OPCIONAL) LOGIN PERSISTENTE POR COOKIE (NÃO BUGA SE NÃO TIVER)
# =========================================================
try:
    import extra_streamlit_components as stx  # type: ignore
    _cookie_manager = stx.CookieManager()
    HAS_COOKIES = True
except Exception:
    _cookie_manager = None
    HAS_COOKIES = False

COOKIE_KEY = "SK_LOGIN_EMAIL"
COOKIE_DIAS = 30

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone("America/Sao_Paulo")
st.set_page_config(page_title="Saúde Kids BETA", page_icon="🧪", layout="wide")

ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"
ARQ_M = "mensagens_admin_BETA.csv"

# ================= NORMALIZAÇÃO =================
def norm_email(x: str) -> str:
    return (x or "").strip().lower()

def norm_senha(x: str) -> str:
    return (x or "").strip()

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
    """
    Regra: após 03:00, se ainda não fez backup HOJE => faz 1.
    """
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
    return pd.DataFrame(backups).sort_values("data_hora", ascending=False).reset_index(drop=True)

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
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        background-color: #262730 !important; color: white !important; border: 1px solid #4a4a4a !important;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; }
</style>
""", unsafe_allow_html=True)

# ================= SEGURANÇA E LOGIN =================
def gerar_senha_temporaria(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return "".join(random.choice(caracteres) for _ in range(tamanho))

def enviar_senha_nova(email_destino, senha_nova):
    meu_email = "ewerlon.osbadboys@gmail.com"
    minha_senha = (st.secrets.get("GMAIL_APP_PASSWORD", "") or "").strip()
    if not minha_senha:
        return False

    corpo = f"<h3>Saúde Kids</h3><p>Sua nova senha de acesso é: <b>{senha_nova}</b></p>"
    msg = MIMEText(corpo, "html")
    msg["Subject"] = "Sua Nova Senha - Saúde Kids"
    msg["From"] = meu_email
    msg["To"] = email_destino

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(meu_email, minha_senha)
            smtp.send_message(msg)
        return True
    except:
        return False

def init_db():
    conn = sqlite3.connect("usuarios.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            nome TEXT,
            email TEXT PRIMARY KEY,
            senha TEXT
        )
    """)
    if not conn.execute("SELECT 1 FROM users WHERE email='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES ('Administrador', 'admin', '542820')")
    conn.commit()
    conn.close()

init_db()

if "logado" not in st.session_state:
    st.session_state.logado = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# ====== AUTO-LOGIN POR COOKIE (SE DISPONÍVEL) ======
def cookie_get_email():
    if not HAS_COOKIES or _cookie_manager is None:
        return ""
    try:
        v = _cookie_manager.get(COOKIE_KEY)
        return norm_email(v)
    except Exception:
        return ""

def cookie_set_email(email: str):
    if not HAS_COOKIES or _cookie_manager is None:
        return
    try:
        _cookie_manager.set(COOKIE_KEY, norm_email(email), expires_at=timedelta(days=COOKIE_DIAS))
    except Exception:
        pass

def cookie_clear():
    if not HAS_COOKIES or _cookie_manager is None:
        return
    try:
        _cookie_manager.delete(COOKIE_KEY)
    except Exception:
        pass

if not st.session_state.logado:
    ck = cookie_get_email()
    if ck:
        st.session_state.logado = True
        st.session_state.user_email = ck

if not st.session_state.logado:
    st.title("🧪 Saúde Kids - Acesso")

    if not HAS_COOKIES:
        st.caption("ℹ️ Login persistente desativado (pacote extra-streamlit-components não instalado).")

    abas_login = st.tabs(["🔐 Entrar", "📝 Criar Conta", "❓ Esqueci Senha", "🔄 Alterar Senha"])

    with abas_login[0]:
        u = norm_email(st.text_input("E-mail", key="l_email"))
        s = norm_senha(st.text_input("Senha", type="password", key="l_pass"))

        if st.button("Acessar Aplicativo", use_container_width=True):
            conn = sqlite3.connect("usuarios.db")
            ok = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (u, s)).fetchone()
            conn.close()
            if ok:
                st.session_state.logado = True
                st.session_state.user_email = u
                cookie_set_email(u)
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos.")

    with abas_login[1]:
        n_cad = (st.text_input("Nome Completo") or "").strip()
        e_cad = norm_email(st.text_input("E-mail para Cadastro"))
        s_cad = norm_senha(st.text_input("Senha para Cadastro", type="password"))

        if st.button("Realizar Cadastro", use_container_width=True):
            if not n_cad or not e_cad or not s_cad:
                st.warning("Preencha nome, e-mail e senha.")
            else:
                try:
                    conn = sqlite3.connect("usuarios.db")
                    conn.execute("INSERT INTO users VALUES (?,?,?)", (n_cad, e_cad, s_cad))
                    conn.commit()
                    conn.close()
                    st.success("Conta criada com sucesso!")
                except:
                    st.error("Este e-mail já está cadastrado.")

    with abas_login[2]:
        email_alvo = norm_email(st.text_input("Digite seu e-mail cadastrado"))
        if st.button("Recuperar Acesso", use_container_width=True):
            conn = sqlite3.connect("usuarios.db")
            c = conn.cursor()
            user = c.execute("SELECT email FROM users WHERE email=?", (email_alvo,)).fetchone()
            if user:
                nova = gerar_senha_temporaria()
                c.execute("UPDATE users SET senha=? WHERE email=?", (nova, email_alvo))
                conn.commit()
                conn.close()
                if enviar_senha_nova(email_alvo, nova):
                    st.success("Nova senha enviada para seu e-mail!")
                else:
                    st.warning("E-mail não configurado no app (sem GMAIL_APP_PASSWORD).")
                    st.info("Use a senha temporária abaixo para entrar e depois altere sua senha:")
                    st.code(nova)
            else:
                conn.close()
                st.error("E-mail não encontrado.")

    with abas_login[3]:
        alt_em = norm_email(st.text_input("Confirme seu E-mail", key="alt_em"))
        alt_at = norm_senha(st.text_input("Senha Atual", type="password", key="alt_at"))
        alt_n1 = norm_senha(st.text_input("Nova Senha", type="password", key="alt_n1"))
        if st.button("Confirmar Alteração", use_container_width=True):
            conn = sqlite3.connect("usuarios.db")
            ok = conn.execute("SELECT * FROM users WHERE email=? AND senha=?", (alt_em, alt_at)).fetchone()
            if ok:
                conn.execute("UPDATE users SET senha=? WHERE email=?", (alt_n1, alt_em))
                conn.commit()
                conn.close()
                st.success("Senha alterada com sucesso!")
            else:
                conn.close()
                st.error("Dados atual incorretos.")
    st.stop()

# ================= FUNÇÕES DE APOIO =================
def carregar_dados_seguro(arq):
    if not os.path.exists(arq):
        return pd.DataFrame()
    df = pd.read_csv(arq)
    if "Usuario" not in df.columns:
        df["Usuario"] = st.session_state.user_email
    return df[df["Usuario"] == st.session_state.user_email].copy()

# ================= IDs e CRUD (editar/excluir) =================
def _ensure_id_column(df: pd.DataFrame, col_name="ID", prefix="GL") -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if col_name not in df.columns:
        df[col_name] = [f"{prefix}-{uuid.uuid4().hex[:12]}" for _ in range(len(df))]
    else:
        mask = df[col_name].isna() | (df[col_name].astype(str).str.strip() == "")
        if mask.any():
            df.loc[mask, col_name] = [f"{prefix}-{uuid.uuid4().hex[:12]}" for _ in range(mask.sum())]
    return df

def carregar_glicemia_com_id() -> pd.DataFrame:
    df_all = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
    if df_all.empty:
        return pd.DataFrame(columns=["ID","Usuario","Data","Hora","Valor","Momento","Dose"])
    if "Usuario" not in df_all.columns:
        df_all["Usuario"] = ""
    df_all = _ensure_id_column(df_all, col_name="ID", prefix="GL")
    try:
        df_all.to_csv(ARQ_G, index=False)
    except:
        pass
    return df_all[df_all["Usuario"] == st.session_state.user_email].copy()

def salvar_registro_glicemia(valor: int, momento: str, dose_para_salvar: str, dt: datetime):
    novo = pd.DataFrame([{
        "ID": f"GL-{uuid.uuid4().hex[:12]}",
        "Usuario": st.session_state.user_email,
        "Data": dt.strftime("%d/%m/%Y"),
        "Hora": dt.strftime("%H:%M"),
        "Valor": int(valor),
        "Momento": str(momento).strip(),
        "Dose": dose_para_salvar or ""
    }])
    base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame(columns=novo.columns)
    if "Usuario" not in base.columns:
        base["Usuario"] = ""
    base = _ensure_id_column(base, col_name="ID", prefix="GL")
    pd.concat([base, novo], ignore_index=True).to_csv(ARQ_G, index=False)

def aplicar_edicoes_e_exclusoes_glicemia(df_editado: pd.DataFrame):
    if df_editado is None or df_editado.empty:
        return
    base = pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()
    if base.empty:
        return
    if "Usuario" not in base.columns:
        base["Usuario"] = ""
    base = _ensure_id_column(base, col_name="ID", prefix="GL")

    df_editado = df_editado.copy()
    if "Excluir" not in df_editado.columns:
        df_editado["Excluir"] = False

    df_editado["Valor"] = pd.to_numeric(df_editado["Valor"], errors="coerce").fillna(0).astype(int)
    df_editado["Momento"] = df_editado["Momento"].astype(str).str.strip()
    df_editado["Dose"] = df_editado.get("Dose", "").astype(str)

    ids_user = set(base.loc[base["Usuario"] == st.session_state.user_email, "ID"].astype(str).tolist())
    ids_excluir = set(df_editado.loc[df_editado["Excluir"] == True, "ID"].astype(str).tolist()).intersection(ids_user)

    df_upd = df_editado.loc[df_editado["Excluir"] != True].copy()
    df_upd["ID"] = df_upd["ID"].astype(str)

    for _, r in df_upd.iterrows():
        rid = str(r["ID"])
        if rid not in ids_user:
            continue
        mask = (base["ID"].astype(str) == rid) & (base["Usuario"] == st.session_state.user_email)
        if mask.any():
            base.loc[mask, "Data"] = str(r.get("Data", "")).strip()
            base.loc[mask, "Hora"] = str(r.get("Hora", "")).strip()
            base.loc[mask, "Valor"] = int(r.get("Valor", 0))
            base.loc[mask, "Momento"] = str(r.get("Momento", "")).strip()
            base.loc[mask, "Dose"] = str(r.get("Dose", "")).strip()

    if ids_excluir:
        base = base[~((base["Usuario"] == st.session_state.user_email) & (base["ID"].astype(str).isin(ids_excluir)))].copy()

    base.to_csv(ARQ_G, index=False)

# ================= RECEITA =================
def _schema_receita_nova(rec: pd.Series, periodo: str) -> bool:
    need = [
        f"{periodo}_f1_min", f"{periodo}_f1_max", f"{periodo}_f1_dose",
        f"{periodo}_f2_min", f"{periodo}_f2_max", f"{periodo}_f2_dose",
        f"{periodo}_f3_min", f"{periodo}_f3_max", f"{periodo}_f3_dose",
    ]
    return all(k in rec.index for k in need)

def calc_insulina(v, m):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty:
        return "0 UI", "Configurar Receita"

    rec = df_r.iloc[0]
    periodo = "manha" if m in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"

    try:
        if not _schema_receita_nova(rec, periodo):
            return "0 UI", "Receita inválida"

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

    except:
        return "0 UI", "Erro na Receita"

def calc_insulina_rapida(v, m):
    return calc_insulina(v, m)

def calc_glargina(momento: str):
    df_r = carregar_dados_seguro(ARQ_R)
    if df_r.empty:
        return "0 UI", "Longa: Configurar"

    rec = df_r.iloc[0]
    try:
        cafe = float(rec.get("glargina_cafe_ui", 0))
        janta = float(rec.get("glargina_janta_ui", 0))

        if momento == "Antes Café":
            return f"{int(cafe)} UI", "Longa (Antes Café)"
        elif momento == "Antes Janta":
            return f"{int(janta)} UI", "Longa (Antes Janta)"
        else:
            return "—", "Longa: não aplicável"
    except:
        return "0 UI", "Longa: erro"

# ================= PRÓXIMA MEDIDA (+2h) e WHATSAPP =================
def proxima_medida_apos(momento: str, dt_base: datetime):
    mapa = {"Antes Café": "Após Café", "Antes Almoço": "Após Almoço", "Antes Janta": "Após Janta"}
    if momento not in mapa:
        return "", ""
    dt_apos = dt_base + timedelta(hours=2)
    return mapa[momento], dt_apos.strftime("%H:%M")


def link_whatsapp_lembrete(momento: str, valor_glicemia: int, dose_rapida: str, dose_longa: str) -> str:
    dt_agora = agora_br()
    momento_apos, hora_apos = proxima_medida_apos(momento, dt_agora)

    linhas = [
        "🧪 Saúde Kids",
        "",
        f"✅ Medida AGORA: {momento}",
        f"📍 Glicemia: {int(valor_glicemia)}"
    ]

    if dose_rapida and dose_rapida != "—":
        linhas.append(f"⚡ Rápida: {dose_rapida}")

    if dose_longa and dose_longa != "—":
        linhas.append(f"🩸 Longa: {dose_longa}")

    if momento_apos and hora_apos:
        linhas.extend([
            "",
            f"⏰ Próxima medida: {momento_apos} às {hora_apos} (2h após)"
        ])

    mensagem = "\n".join(linhas)
    return "https://wa.me/?text=" + quote(mensagem)


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
    "Maçã (1un)": [15, 0, 0],
}

# ================= INTERFACE PRINCIPAL =================
if st.session_state.user_email == "admin":
    st.title("🛡️ Painel Admin - Gestão Estratégica")
    t_usuarios, t_metricas, t_sugestoes, t_backup = st.tabs(["👥 Pessoas Cadastradas", "📈 Crescimento e App", "📩 Sugestões", "💾 Backup & Restauração"])

    conn = sqlite3.connect("usuarios.db")
    df_users = pd.read_sql_query("SELECT nome, email FROM users", conn)
    conn.close()

    with t_usuarios:
        st.subheader("Lista de Usuários")
        st.dataframe(df_users, use_container_width=True)
        st.metric("Total de Cadastros", len(df_users))
        st.markdown("---")
        st.subheader("🔑 Alterar Senha de Usuário (Poder Admin)")
        user_selecionado = st.selectbox("Selecione o E-mail do Usuário", df_users["email"].tolist())
        nova_senha_admin = norm_senha(st.text_input("Digite a Nova Senha para este usuário", type="password"))
        if st.button("Confirmar Alteração de Senha", use_container_width=True):
            if nova_senha_admin:
                conn = sqlite3.connect("usuarios.db")
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
                if "Usuario" in df_uso.columns and not df_uso.empty:
                    uso_por_user = df_uso["Usuario"].value_counts().reset_index()
                    uso_por_user.columns = ["Usuario", "Registros"]
                    st.plotly_chart(px.pie(uso_por_user, values="Registros", names="Usuario", hole=.3), use_container_width=True)
                else:
                    st.info("Sem dados.")
            else:
                st.info("Sem dados.")
        with c2:
            st.write("### Crescimento")
            dados_c = pd.DataFrame({"Mês": ["Jan", "Fev", "Mar"], "Usuários": [max(1, len(df_users)//2), max(1, int(len(df_users)/1.1)), len(df_users)]})
            st.plotly_chart(px.line(dados_c, x="Mês", y="Usuários", markers=True), use_container_width=True)

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
        if up is not None and st.button("✅ Restaurar Agora", use_container_width=True):
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
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Glicemia", "🍽️ Nutrição", "⚙️ Receita", "📩 Sugerir Melhoria"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        dfg = carregar_glicemia_com_id()

        c1, c2 = st.columns([1, 2])
        with c1:
            v_gl = st.number_input("Valor Glicemia", 0, 600, 100)

            MOMENTOS_BASE = 
