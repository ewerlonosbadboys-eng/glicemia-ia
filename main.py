# app.py
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO (SUBGRUPO = REGRAS)
# + Preferência "Evitar folga" por subgrupo
# + Persistência real (SQLite) de ajustes (overrides)
# + Calendário RH visual + Banco de Horas
# + Admin (somente setor ADMIN e is_admin)
# + Gerar respeitando ajustes (overrides) OU ignorando
#
# ✅ CORREÇÕES ATIVAS:
# 1) DESCANSO GLOBAL 11:10 (INTERSTÍCIO) PARA A ESCALA INTEIRA
# 2) DOMINGO 1x1 (POR COLABORADOR) GLOBAL
# 3) PROIBIR FOLGAS CONSECUTIVAS AUTOMÁTICAS (ex.: DOM+SEG)
#    - Só fica folga consecutiva se estiver TRAVADO por override (manual / "caixinha")
# 4) enforce_global_rest_keep_targets NÃO PODE criar folga consecutiva “por acidente”
# 5) enforce_max_5_consecutive_work conta WORK_STATUSES como trabalho para sequência
#
# ✅ REGRAS GERAIS (ATUALIZAÇÃO):
# 6) FÉRIAS: só entra "Férias" se estiver cadastrada na ABA 🏖️ Férias (tabela ferias).
#    - Override "Férias" sem estar na tabela é ignorado.
#    - Se o banco tiver "Férias" sem estar na tabela, é corrigido para "Trabalho".
# 7) REGRA SEMANAL (SEG→DOM):
#    - Semana inicia SEG e termina DOM.
#    - Domingo 1x1 permanece.
#    - Se o colaborador FOLGA no domingo => 1 folga no período SEG–SÁB (SÁB só se permitir).
#    - Se o colaborador TRABALHA no domingo => 2 folgas no período SEG–SÁB (SÁB só se permitir).
#
# ✅ ALTERAÇÃO PEDIDA ANTES:
# - Removido tudo relacionado a "Balanço Madrugada" e ciclo "saída tarde"
#   (status, horários, funções e ações)
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import io
import random
import calendar
import sqlite3
import hashlib
import secrets
from openpyxl.styles import PatternFill, Alignment, Border, Side, Font
from openpyxl.utils import get_column_letter

st.set_page_config(page_title="Escala 5x2 Oficial", layout="wide")



# =========================================================
# UI THEME (CSS) — só visual
# =========================================================
st.markdown("""
<style>
/* largura e respiro geral */
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

/* títulos mais compactos */
h1, h2, h3 { letter-spacing: -0.2px; }

/* cards */
.kpi-card {
  border: 1px solid rgba(49, 51, 63, 0.12);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(250, 250, 252, 0.6);
}
.kpi-title { font-size: 0.85rem; opacity: 0.75; margin-bottom: 2px; }
.kpi-value { font-size: 1.3rem; font-weight: 800; margin: 0; }

/* caixas e divisórias */
.hr { height:1px; background: rgba(49, 51, 63, 0.12); margin: 14px 0; }

/* sidebar mais limpa */
section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* dataframe: arredondar */
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

DB_PATH = "escala.db"

# ---- Regras fixas
INTERSTICIO_MIN = timedelta(hours=11, minutes=10)   # 11:10
DURACAO_JORNADA = timedelta(hours=9, minutes=58)    # 9:58

PREF_EVITAR_PENALTY = 1000

BALANCO_STATUS = "Balanço"
WORK_STATUSES = {"Trabalho", BALANCO_STATUS}

BALANCO_DIA_ENTRADA = "06:00"
BALANCO_DIA_SAIDA = "11:50"

D_PT = {
    "Monday": "seg",
    "Tuesday": "ter",
    "Wednesday": "qua",
    "Thursday": "qui",
    "Friday": "sex",
    "Saturday": "sáb",
    "Sunday": "dom",
}

# =========================================================
# Helpers de hora (minutos)
# =========================================================
def _to_min(hhmm: str) -> int:
    if not hhmm:
        return 0
    h, m = map(int, str(hhmm).split(":"))
    return h * 60 + m

def _min_to_hhmm(x: int) -> str:
    x %= (24 * 60)
    return f"{x//60:02d}:{x%60:02d}"

def _add_min(hhmm: str, delta: timedelta) -> str:
    return _min_to_hhmm(_to_min(hhmm) + int(delta.total_seconds() // 60))

def _sub_min(hhmm: str, delta: timedelta) -> str:
    return _min_to_hhmm(_to_min(hhmm) - int(delta.total_seconds() // 60))

def _saida_from_entrada(ent: str) -> str:
    return _add_min(ent, DURACAO_JORNADA)

def _is_fixed_day(status: str) -> bool:
    # FIXO: balanço
    return str(status) == BALANCO_STATUS

def is_work_status(status: str) -> bool:
    return str(status) in WORK_STATUSES

def _locked(locked_status: set[int] | None, idx: int) -> bool:
    return bool(locked_status and idx in locked_status)

def _ajustar_para_intersticio(ent_desejada: str, saida_anterior: str) -> str:
    """
    Entrada >= desejada respeitando 11:10 após saída anterior
    (considera dia seguinte quando necessário)
    """
    if not ent_desejada or not saida_anterior:
        return ent_desejada

    s = _to_min(saida_anterior)
    e_des = _to_min(ent_desejada)
    e_min = _to_min(_add_min(saida_anterior, INTERSTICIO_MIN))

    if e_des <= s:
        e_des += 1440
    if e_min <= s:
        e_min += 1440

    e_ok = max(e_des, e_min)
    return _min_to_hhmm(e_ok)

# =========================================================
# ✅ Proibir folga consecutiva AUTOMÁTICA (DOM+SEG etc.)
# Só permite se estiver travado (override/manual/"caixinha")
# =========================================================
def enforce_no_consecutive_folga(df: pd.DataFrame, locked_status: set[int] | None = None):
    for i in range(1, len(df)):
        if df.loc[i - 1, "Status"] == "Folga" and df.loc[i, "Status"] == "Folga":
            prev_locked = _locked(locked_status, i - 1)
            cur_locked = _locked(locked_status, i)

            # ambos travados => foi decisão manual, mantém
            if prev_locked and cur_locked:
                continue

            # prioriza manter o travado e desfazer o outro
            if not cur_locked:
                df.loc[i, "Status"] = "Trabalho"
            elif not prev_locked:
                df.loc[i - 1, "Status"] = "Trabalho"

# =========================================================
# DB
# =========================================================
def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def _safe_exec(cur, sql: str, params=None):
    try:
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
    except Exception:
        pass

def db_init():
    con = db_conn()
    cur = con.cursor()

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS setores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS usuarios_sistema (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        is_lider INTEGER NOT NULL DEFAULT 0,
        criado_em TEXT NOT NULL,
        UNIQUE(setor, chapa)
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS colaboradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        subgrupo TEXT DEFAULT '',
        entrada TEXT DEFAULT '06:00',
        folga_sab INTEGER DEFAULT 0,
        criado_em TEXT NOT NULL,
        UNIQUE(setor, chapa)
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS subgrupos_setor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        nome TEXT NOT NULL,
        UNIQUE(setor, nome)
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS subgrupo_regras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        subgrupo TEXT NOT NULL,
        evitar_seg INTEGER NOT NULL DEFAULT 0,
        evitar_ter INTEGER NOT NULL DEFAULT 0,
        evitar_qua INTEGER NOT NULL DEFAULT 0,
        evitar_qui INTEGER NOT NULL DEFAULT 0,
        evitar_sex INTEGER NOT NULL DEFAULT 0,
        evitar_sab INTEGER NOT NULL DEFAULT 0,
        UNIQUE(setor, subgrupo)
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS ferias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS estado_mes_anterior (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        consec_trab_final INTEGER NOT NULL,
        ultima_saida TEXT NOT NULL,
        ultimo_domingo_status TEXT,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        UNIQUE(setor, chapa, ano, mes)
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS escala_mes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        chapa TEXT NOT NULL,
        dia INTEGER NOT NULL,
        data TEXT NOT NULL,
        dia_sem TEXT NOT NULL,
        status TEXT NOT NULL,
        h_entrada TEXT,
        h_saida TEXT,
        UNIQUE(setor, ano, mes, chapa, dia)
    )
    """)

    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        chapa TEXT NOT NULL,
        dia INTEGER NOT NULL,
        campo TEXT NOT NULL,
        valor TEXT NOT NULL,
        UNIQUE(setor, ano, mes, chapa, dia, campo)
    )
    """)

    con.commit()
    _safe_exec(cur, "INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("GERAL",))
    _safe_exec(cur, "INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("ADMIN",))
    con.commit()

    cur.execute("SELECT 1 FROM usuarios_sistema WHERE setor=? AND chapa=? LIMIT 1", ("ADMIN", "admin"))
    if cur.fetchone() is None:
        salt = secrets.token_hex(16)
        senha_hash = hash_password("123", salt)
        cur.execute("""
            INSERT INTO usuarios_sistema(nome, setor, chapa, senha_hash, salt, is_admin, is_lider, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Administrador", "ADMIN", "admin", senha_hash, salt, 1, 1, datetime.now().isoformat()))
        con.commit()

    con.close()

# =========================================================
# AUTH
# =========================================================
def system_user_exists(setor: str, chapa: str) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT 1 FROM usuarios_sistema WHERE setor=? AND chapa=? LIMIT 1", (setor, chapa))
    ok = cur.fetchone() is not None
    con.close()
    return ok

def create_system_user(nome: str, setor: str, chapa: str, senha: str, is_lider: int = 0, is_admin: int = 0):
    salt = secrets.token_hex(16)
    senha_hash = hash_password(senha, salt)
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", (setor,))
    cur.execute("""
        INSERT INTO usuarios_sistema(nome, setor, chapa, senha_hash, salt, is_admin, is_lider, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (nome, setor, chapa, senha_hash, salt, int(is_admin), int(is_lider), datetime.now().isoformat()))
    con.commit()
    con.close()

def verify_login(setor: str, chapa: str, senha: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT nome, senha_hash, salt, is_admin, is_lider
        FROM usuarios_sistema
        WHERE setor=? AND chapa=?
        LIMIT 1
    """, (setor, chapa))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    nome, senha_hash, salt, is_admin, is_lider = row
    if hash_password(senha, salt) == senha_hash:
        return {"nome": nome, "setor": setor, "chapa": chapa, "is_admin": bool(is_admin), "is_lider": bool(is_lider)}
    return None

def is_lider_chapa(setor: str, chapa_lider: str) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT is_lider FROM usuarios_sistema WHERE setor=? AND chapa=? LIMIT 1", (setor, chapa_lider))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0] == 1)

def update_password(setor: str, chapa: str, nova_senha: str):
    salt = secrets.token_hex(16)
    senha_hash = hash_password(nova_senha, salt)
    con = db_conn()
    cur = con.cursor()
    cur.execute("UPDATE usuarios_sistema SET senha_hash=?, salt=? WHERE setor=? AND chapa=?",
                (senha_hash, salt, setor, chapa))
    con.commit()
    con.close()

# =========================================================
# ADMIN
# =========================================================
@st.cache_data(show_spinner=False)
def admin_list_users():
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT id, nome, setor, chapa, is_admin, is_lider, criado_em
        FROM usuarios_sistema
        ORDER BY setor ASC, nome ASC
    """, con)
    con.close()
    return df

def admin_reset_user_password(user_id: int, nova_senha: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT setor, chapa FROM usuarios_sistema WHERE id=?", (int(user_id),))
    row = cur.fetchone()
    if not row:
        con.close()
        return False
    setor, chapa = row
    con.close()
    update_password(setor, chapa, nova_senha)
    return True

# =========================================================
# COLABORADORES
# =========================================================
def colaborador_exists(setor: str, chapa: str) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT 1 FROM colaboradores WHERE setor=? AND chapa=? LIMIT 1", (setor, chapa))
    ok = cur.fetchone() is not None
    con.close()
    return ok

def create_colaborador(nome: str, setor: str, chapa: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO colaboradores(nome, setor, chapa, criado_em) VALUES (?, ?, ?, ?)",
                (nome, setor, chapa, datetime.now().isoformat()))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

def delete_colaborador_total(setor: str, chapa: str):
    """
    Exclui colaborador e tudo do setor relacionado a ele:
    - colaboradores
    - ferias
    - overrides
    - escala_mes
    - estado_mes_anterior
    """
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM ferias WHERE setor=? AND chapa=?", (setor, chapa))
    cur.execute("DELETE FROM overrides WHERE setor=? AND chapa=?", (setor, chapa))
    cur.execute("DELETE FROM escala_mes WHERE setor=? AND chapa=?", (setor, chapa))
    cur.execute("DELETE FROM estado_mes_anterior WHERE setor=? AND chapa=?", (setor, chapa))
    cur.execute("DELETE FROM colaboradores WHERE setor=? AND chapa=?", (setor, chapa))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

def update_colaborador_perfil(setor: str, chapa: str, subgrupo: str, entrada: str, folga_sab: bool):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        UPDATE colaboradores
        SET subgrupo=?, entrada=?, folga_sab=?
        WHERE setor=? AND chapa=?
    """, (subgrupo or "", entrada, 1 if folga_sab else 0, setor, chapa))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False)
def load_colaboradores_setor(setor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT nome, chapa, subgrupo, entrada, folga_sab
        FROM colaboradores
        WHERE setor=?
        ORDER BY nome ASC
    """, (setor,))
    rows = cur.fetchall()
    con.close()
    return [{
        "Nome": r[0],
        "Chapa": r[1],
        "Subgrupo": (r[2] or "").strip(),
        "Entrada": (r[3] or "06:00").strip(),
        "Folga_Sab": bool(r[4]),
        "Setor": setor,
    } for r in rows]

# =========================================================
# SUBGRUPOS + REGRAS
# =========================================================
@st.cache_data(show_spinner=False)
def list_subgrupos(setor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT nome FROM subgrupos_setor WHERE setor=? ORDER BY nome ASC", (setor,))
    rows = [r[0] for r in cur.fetchall()]
    con.close()
    return rows

def add_subgrupo(setor: str, nome: str):
    nome = (nome or "").strip()
    if not nome:
        return
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO subgrupos_setor(setor, nome) VALUES (?, ?)", (setor, nome))
    cur.execute("""
        INSERT OR IGNORE INTO subgrupo_regras(setor, subgrupo, evitar_seg, evitar_ter, evitar_qua, evitar_qui, evitar_sex, evitar_sab)
        VALUES (?, ?, 0,0,0,0,0,0)
    """, (setor, nome))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

def delete_subgrupo(setor: str, nome: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM subgrupos_setor WHERE setor=? AND nome=?", (setor, nome))
    cur.execute("DELETE FROM subgrupo_regras WHERE setor=? AND subgrupo=?", (setor, nome))
    cur.execute("UPDATE colaboradores SET subgrupo='' WHERE setor=? AND subgrupo=?", (setor, nome))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False)
def get_subgrupo_regras(setor: str, subgrupo: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT evitar_seg, evitar_ter, evitar_qua, evitar_qui, evitar_sex, evitar_sab
        FROM subgrupo_regras
        WHERE setor=? AND subgrupo=?
        LIMIT 1
    """, (setor, subgrupo))
    row = cur.fetchone()
    con.close()
    if not row:
        return {"seg": 0, "ter": 0, "qua": 0, "qui": 0, "sex": 0, "sáb": 0}
    return {"seg": row[0], "ter": row[1], "qua": row[2], "qui": row[3], "sex": row[4], "sáb": row[5]}

def set_subgrupo_regras(setor: str, subgrupo: str, regras: dict):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO subgrupo_regras(setor, subgrupo, evitar_seg, evitar_ter, evitar_qua, evitar_qui, evitar_sex, evitar_sab)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        setor, subgrupo,
        int(regras.get("seg", 0)),
        int(regras.get("ter", 0)),
        int(regras.get("qua", 0)),
        int(regras.get("qui", 0)),
        int(regras.get("sex", 0)),
        int(regras.get("sáb", 0)),
    ))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

# =========================================================
# FÉRIAS
# =========================================================
def add_ferias(setor: str, chapa: str, inicio: date, fim: date):
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT INTO ferias(setor, chapa, inicio, fim) VALUES (?, ?, ?, ?)",
                (setor, chapa, inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

def delete_ferias_row(setor: str, chapa: str, inicio: str, fim: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        DELETE FROM ferias
        WHERE setor=? AND chapa=? AND inicio=? AND fim=?
    """, (setor, chapa, inicio, fim))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False)
def list_ferias(setor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT chapa, inicio, fim FROM ferias WHERE setor=? ORDER BY date(inicio) ASC", (setor,))
    rows = cur.fetchall()
    con.close()
    return rows

def is_de_ferias(setor: str, chapa: str, data_obj: date) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT 1 FROM ferias
        WHERE setor=? AND chapa=?
          AND date(inicio) <= date(?) AND date(fim) >= date(?)
        LIMIT 1
    """, (setor, chapa, data_obj.strftime("%Y-%m-%d"), data_obj.strftime("%Y-%m-%d")))
    ok = cur.fetchone() is not None
    con.close()
    return ok

def is_first_week_after_return(setor: str, chapa: str, data_obj: date) -> bool:
    ontem = data_obj - timedelta(days=1)
    if is_de_ferias(setor, chapa, data_obj):
        return False
    if is_de_ferias(setor, chapa, ontem):
        return True
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT fim FROM ferias
        WHERE setor=? AND chapa=? AND date(fim) < date(?)
        ORDER BY date(fim) DESC
        LIMIT 1
    """, (setor, chapa, data_obj.strftime("%Y-%m-%d")))
    row = cur.fetchone()
    con.close()
    if not row:
        return False
    fim = datetime.strptime(row[0], "%Y-%m-%d").date()
    retorno = fim + timedelta(days=1)
    return retorno <= data_obj <= (retorno + timedelta(days=6))

# =========================================================
# ESTADO
# =========================================================
def save_estado_mes(setor: str, ano: int, mes: int, estado: dict):
    con = db_conn()
    cur = con.cursor()
    for chapa, stt in estado.items():
        cur.execute("""
            INSERT OR REPLACE INTO estado_mes_anterior(setor, chapa, consec_trab_final, ultima_saida, ultimo_domingo_status, ano, mes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            setor, chapa,
            int(stt.get("consec_trab_final", 0)),
            stt.get("ultima_saida", "") or "",
            stt.get("ultimo_domingo_status", None),
            int(ano), int(mes)
        ))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

def load_estado_prev(setor: str, ano: int, mes: int):
    prev_ano, prev_mes = ano, mes - 1
    if prev_mes == 0:
        prev_mes = 12
        prev_ano -= 1
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT chapa, consec_trab_final, ultima_saida, ultimo_domingo_status
        FROM estado_mes_anterior
        WHERE setor=? AND ano=? AND mes=?
    """, (setor, prev_ano, prev_mes))
    rows = cur.fetchall()
    con.close()
    estado = {}
    for chapa, consec, ultima_saida, ultimo_dom in rows:
        estado[chapa] = {"consec_trab_final": int(consec), "ultima_saida": ultima_saida or "", "ultimo_domingo_status": ultimo_dom}
    return estado

# =========================================================
# OVERRIDES
# =========================================================
def set_override(setor: str, ano: int, mes: int, chapa: str, dia: int, campo: str, valor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO overrides(setor, ano, mes, chapa, dia, campo, valor)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (setor, int(ano), int(mes), chapa, int(dia), campo, str(valor)))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

def delete_override(setor: str, ano: int, mes: int, chapa: str, dia: int, campo: str | None = None):
    con = db_conn()
    cur = con.cursor()
    if campo:
        cur.execute("""
            DELETE FROM overrides
            WHERE setor=? AND ano=? AND mes=? AND chapa=? AND dia=? AND campo=?
        """, (setor, int(ano), int(mes), chapa, int(dia), campo))
    else:
        cur.execute("""
            DELETE FROM overrides
            WHERE setor=? AND ano=? AND mes=? AND chapa=? AND dia=?
        """, (setor, int(ano), int(mes), chapa, int(dia)))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False)
def load_overrides(setor: str, ano: int, mes: int):
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT chapa, dia, campo, valor
        FROM overrides
        WHERE setor=? AND ano=? AND mes=?
    """, con, params=(setor, int(ano), int(mes)))
    con.close()
    return df

def _ov_map(setor: str, ano: int, mes: int):
    df = load_overrides(setor, ano, mes)
    ov = {}
    if df is None or df.empty:
        return ov
    for _, r in df.iterrows():
        ch = str(r["chapa"])
        dia = int(r["dia"])
        campo = str(r["campo"])
        valor = str(r["valor"])
        ov.setdefault(ch, {}).setdefault(dia, {})[campo] = valor
    return ov

def _is_status_locked(ovmap: dict, chapa: str, data_ts: pd.Timestamp) -> bool:
    dia = int(pd.to_datetime(data_ts).day)
    return bool(ovmap.get(chapa, {}).get(dia, {}).get("status"))

def _apply_overrides_to_df_inplace(df: pd.DataFrame, setor: str, chapa: str, ovmap: dict):
    """
    Aplica overrides, MAS:
    - status 'Férias' só é aceito se estiver na tabela ferias (aba Férias).
    """
    if chapa not in ovmap:
        return df
    for i in range(len(df)):
        dia_num = int(pd.to_datetime(df.loc[i, "Data"]).day)
        rule = ovmap.get(chapa, {}).get(dia_num, {})
        if not rule:
            continue

        data_obj = pd.to_datetime(df.loc[i, "Data"]).date()

        if "status" in rule:
            stt = str(rule["status"])
            if stt == "Férias" and not is_de_ferias(setor, chapa, data_obj):
                # ignora este override
                pass
            else:
                df.loc[i, "Status"] = stt
                if stt not in WORK_STATUSES:
                    df.loc[i, "H_Entrada"] = ""
                    df.loc[i, "H_Saida"] = ""

        if "h_entrada" in rule:
            df.loc[i, "H_Entrada"] = rule["h_entrada"]

        if "h_saida" in rule:
            df.loc[i, "H_Saida"] = rule["h_saida"]

        if df.loc[i, "Status"] in WORK_STATUSES:
            if (df.loc[i, "H_Entrada"] or "") and not (df.loc[i, "H_Saida"] or ""):
                df.loc[i, "H_Saida"] = _saida_from_entrada(df.loc[i, "H_Entrada"])
    return df

# =========================================================
# ESCALA DB
# =========================================================
def save_escala_mes_db(setor: str, ano: int, mes: int, historico_df_por_chapa: dict[str, pd.DataFrame]):
    con = db_conn()
    cur = con.cursor()
    for chapa, df in historico_df_por_chapa.items():
        for _, row in df.iterrows():
            dia = int(row["Data"].day)
            cur.execute("""
                INSERT OR REPLACE INTO escala_mes(setor, ano, mes, chapa, dia, data, dia_sem, status, h_entrada, h_saida)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                setor, int(ano), int(mes), chapa, dia,
                pd.to_datetime(row["Data"]).strftime("%Y-%m-%d"),
                row["Dia"],
                row["Status"],
                row.get("H_Entrada", "") or "",
                row.get("H_Saida", "") or "",
            ))
    con.commit()
    con.close()
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False)
def load_escala_mes_db(setor: str, ano: int, mes: int):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT chapa, data, dia_sem, status, h_entrada, h_saida
        FROM escala_mes
        WHERE setor=? AND ano=? AND mes=?
        ORDER BY chapa, date(data) ASC
    """, (setor, int(ano), int(mes)))
    rows = cur.fetchall()
    con.close()
    if not rows:
        return {}
    hist = {}
    for chapa, data_s, dia_sem, status, h_ent, h_sai in rows:
        dt = pd.to_datetime(data_s)
        hist.setdefault(chapa, []).append({
            "Data": dt, "Dia": dia_sem, "Status": status,
            "H_Entrada": h_ent or "", "H_Saida": h_sai or ""
        })
    return {ch: pd.DataFrame(items) for ch, items in hist.items()}

def apply_overrides_to_hist(setor: str, ano: int, mes: int, hist_db: dict[str, pd.DataFrame]):
    """
    Aplica overrides no histórico carregado do banco.
    REGRA GERAL:
    - "Férias" só existe se estiver na tabela ferias.
    - Se encontrar "Férias" no banco mas NÃO estiver na tabela, vira "Trabalho".
    """
    ov = load_overrides(setor, ano, mes)
    if (ov is None or ov.empty) and not hist_db:
        return hist_db

    # aplica overrides (se houver)
    if ov is not None and not ov.empty and hist_db:
        for _, r in ov.iterrows():
            ch = str(r["chapa"])
            dia = int(r["dia"])
            campo = str(r["campo"])
            valor = str(r["valor"])
            if ch not in hist_db:
                continue

            df = hist_db[ch].copy()
            idx = dia - 1
            if idx < 0 or idx >= len(df):
                continue

            data_obj = pd.to_datetime(df.loc[idx, "Data"]).date()

            if campo == "status":
                if valor == "Férias" and not is_de_ferias(setor, ch, data_obj):
                    pass
                else:
                    df.loc[idx, "Status"] = valor
                    if valor not in WORK_STATUSES:
                        df.loc[idx, "H_Entrada"] = ""
                        df.loc[idx, "H_Saida"] = ""

            elif campo == "h_entrada":
                df.loc[idx, "H_Entrada"] = valor
                if df.loc[idx, "Status"] in WORK_STATUSES:
                    df.loc[idx, "H_Saida"] = _saida_from_entrada(valor)

            elif campo == "h_saida":
                df.loc[idx, "H_Saida"] = valor

            hist_db[ch] = df

    # ✅ SANITIZA: força férias SOMENTE pela tabela ferias
    if hist_db:
        colaboradores = load_colaboradores_setor(setor)
        colab_by = {c["Chapa"]: c for c in colaboradores}

        for ch, df in list(hist_db.items()):
            ent_pad = colab_by.get(ch, {}).get("Entrada", "06:00")
            df2 = df.copy()
            for i in range(len(df2)):
                data_obj = pd.to_datetime(df2.loc[i, "Data"]).date()
                in_ferias = is_de_ferias(setor, ch, data_obj)

                if in_ferias:
                    df2.loc[i, "Status"] = "Férias"
                    df2.loc[i, "H_Entrada"] = ""
                    df2.loc[i, "H_Saida"] = ""
                else:
                    if df2.loc[i, "Status"] == "Férias":
                        df2.loc[i, "Status"] = "Trabalho"
                        df2.loc[i, "H_Entrada"] = ent_pad
                        df2.loc[i, "H_Saida"] = _saida_from_entrada(ent_pad)

            hist_db[ch] = df2

    return hist_db

# =========================================================
# MOTOR
# =========================================================
def _dias_mes(ano: int, mes: int):
    qtd = calendar.monthrange(ano, mes)[1]
    return pd.date_range(start=f"{ano}-{mes:02d}-01", periods=qtd, freq="D")

def _nao_consecutiva_folga(df, idx):
    """
    Verifica se o índice 'idx' NÃO fica colado com outra folga (idx-1 ou idx+1).
    Usa iloc (posição) para evitar KeyError quando o índice do DF não é 0..N-1.
    """
    n = len(df)
    if n == 0:
        return True
    if idx > 0 and df.iloc[idx - 1]["Status"] == "Folga":
        return False
    if idx < n - 1 and df.iloc[idx + 1]["Status"] == "Folga":
        return False
    return True

def _set_trabalho(df, idx, ent_padrao, locked_status: set[int] | None = None):
    if _locked(locked_status, idx):
        return
    df.loc[idx, "Status"] = "Trabalho"
    if not (df.loc[idx, "H_Entrada"] or ""):
        df.loc[idx, "H_Entrada"] = ent_padrao
    df.loc[idx, "H_Saida"] = _saida_from_entrada(df.loc[idx, "H_Entrada"])

def _set_folga(df, idx, locked_status: set[int] | None = None):
    if _locked(locked_status, idx):
        return
    df.loc[idx, "Status"] = "Folga"
    df.loc[idx, "H_Entrada"] = ""
    df.loc[idx, "H_Saida"] = ""

def _set_ferias(df, idx, locked_status: set[int] | None = None):
    if _locked(locked_status, idx):
        return
    df.loc[idx, "Status"] = "Férias"
    df.loc[idx, "H_Entrada"] = ""
    df.loc[idx, "H_Saida"] = ""

def _set_balanco(df, idx, locked_status: set[int] | None = None):
    if _locked(locked_status, idx):
        return
    df.loc[idx, "Status"] = BALANCO_STATUS
    df.loc[idx, "H_Entrada"] = BALANCO_DIA_ENTRADA
    df.loc[idx, "H_Saida"] = BALANCO_DIA_SAIDA

def _semana_seg_dom_indices(datas: pd.DatetimeIndex, idx_any: int):
    d = datas[idx_any]
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return [i for i, dd in enumerate(datas) if monday.date() <= dd.date() <= sunday.date()]

def _all_weeks_seg_dom(datas: pd.DatetimeIndex):
    weeks, seen = [], set()
    for i in range(len(datas)):
        w = tuple(_semana_seg_dom_indices(datas, i))
        if w and w not in seen:
            seen.add(w)
            weeks.append(list(w))
    return weeks

# =========================================================
# ✅ DOMINGO 1x1 POR COLABORADOR (GLOBAL, RESPEITA LOCK/FÉRIAS)
# =========================================================
def enforce_sundays_1x1_for_employee(
    df: pd.DataFrame,
    ent_padrao: str,
    locked_status: set[int] | None = None,
    base_first: str | None = None
):
    domingos = [i for i in range(len(df)) if df.loc[i, "Data"].day_name() == "Sunday"]
    if not domingos:
        return

    def _normalize_dom_status(i: int) -> str | None:
        stt = df.loc[i, "Status"]
        if stt == "Férias":
            return None
        if stt == "Folga":
            return "Folga"
        if stt in WORK_STATUSES:
            return "Trabalho"
        return None

    def _force_dom(i: int, val: str):
        if _locked(locked_status, i):
            return
        if df.loc[i, "Status"] == "Férias":
            return
        if val == "Folga":
            _set_folga(df, i, locked_status=locked_status)
        else:
            df.loc[i, "H_Entrada"] = ent_padrao
            _set_trabalho(df, i, ent_padrao, locked_status=locked_status)

    first_idx = domingos[0]
    if not _locked(locked_status, first_idx) and df.loc[first_idx, "Status"] != "Férias":
        if base_first in ("Trabalho", "Folga"):
            _force_dom(first_idx, base_first)

    cur = None
    for i in domingos:
        norm = _normalize_dom_status(i)
        if norm in ("Trabalho", "Folga"):
            cur = norm
            break
    if cur is None:
        return

    for i in domingos:
        if df.loc[i, "Status"] == "Férias":
            continue

        if _locked(locked_status, i):
            norm = _normalize_dom_status(i)
            if norm in ("Trabalho", "Folga"):
                cur = norm
            continue

        _force_dom(i, cur)
        cur = "Folga" if cur == "Trabalho" else "Trabalho"

# =========================================================
# ✅ DESCANSO GLOBAL 11:10 (corrigido para NÃO criar folga consecutiva)
# =========================================================
def enforce_global_rest_keep_targets(df: pd.DataFrame, ent_padrao: str, locked_status: set[int] | None = None, ultima_saida_prev: str | None = None):
    # mantém horário fixo de balanço
    for i in range(len(df)):
        if df.loc[i, "Status"] == BALANCO_STATUS:
            df.loc[i, "H_Entrada"] = BALANCO_DIA_ENTRADA
            df.loc[i, "H_Saida"] = BALANCO_DIA_SAIDA

    last_saida = (ultima_saida_prev or "").strip()

    for i in range(len(df)):
        stt = df.loc[i, "Status"]

        if stt not in WORK_STATUSES:
            df.loc[i, "H_Entrada"] = ""
            df.loc[i, "H_Saida"] = ""
            last_saida = ""
            continue

        if stt == BALANCO_STATUS:
            last_saida = (df.loc[i, "H_Saida"] or "").strip()
            continue

        target = (df.loc[i, "H_Entrada"] or "").strip() or ent_padrao

        if not last_saida:
            df.loc[i, "H_Entrada"] = target
            df.loc[i, "H_Saida"] = _saida_from_entrada(target)
            last_saida = df.loc[i, "H_Saida"]
            continue

        min_ent = _add_min(last_saida, INTERSTICIO_MIN)

        s = _to_min(last_saida)
        e_t = _to_min(target)
        e_min = _to_min(min_ent)
        if e_t <= s: e_t += 1440
        if e_min <= s: e_min += 1440

        if e_t >= e_min:
            df.loc[i, "H_Entrada"] = target
            df.loc[i, "H_Saida"] = _saida_from_entrada(target)
            last_saida = df.loc[i, "H_Saida"]
            continue

        prev = i - 1
        if prev >= 0:
            # tenta ajustar o dia anterior (saída mais cedo) sem virar folga
            if (
                df.loc[prev, "Status"] == "Trabalho"
                and not _locked(locked_status, prev)
            ):
                saida_req = _sub_min(target, INTERSTICIO_MIN)
                ent_req = _sub_min(saida_req, DURACAO_JORNADA)
                df.loc[prev, "H_Entrada"] = ent_req
                df.loc[prev, "H_Saida"] = _saida_from_entrada(ent_req)
                last_saida = df.loc[prev, "H_Saida"]

                df.loc[i, "H_Entrada"] = target
                df.loc[i, "H_Saida"] = _saida_from_entrada(target)
                last_saida = df.loc[i, "H_Saida"]
                continue

            # plano B: folgar o dia anterior SÓ se NÃO gerar folga consecutiva
            if prev >= 0 and not _locked(locked_status, prev) and df.loc[prev, "Status"] != "Férias":
                if _nao_consecutiva_folga(df, prev):
                    _set_folga(df, prev, locked_status=locked_status)
                    last_saida = ""
                    df.loc[i, "H_Entrada"] = target
                    df.loc[i, "H_Saida"] = _saida_from_entrada(target)
                    last_saida = df.loc[i, "H_Saida"]
                    continue
                else:
                    # alternativa: empurra o dia atual (não cria folga seguida)
                    ent_ok = _ajustar_para_intersticio(target, last_saida)
                    df.loc[i, "H_Entrada"] = ent_ok
                    df.loc[i, "H_Saida"] = _saida_from_entrada(ent_ok)
                    last_saida = df.loc[i, "H_Saida"]
                    continue

        # fallback final: empurra entrada
        ent_ok = _ajustar_para_intersticio(target, last_saida)
        df.loc[i, "H_Entrada"] = ent_ok
        df.loc[i, "H_Saida"] = _saida_from_entrada(ent_ok)
        last_saida = df.loc[i, "H_Saida"]

# =========================================================
# ✅ 5x2: máxima sequência de trabalho = 5
# =========================================================
def enforce_max_5_consecutive_work(df, ent_padrao, pode_folgar_sabado: bool, initial_consec: int = 0):
    # Segurança: garante índice 0..N-1 (evita KeyError por índice quebrado)
    df.reset_index(drop=True, inplace=True)

    def can_make_folga(i):
        # Só converte TRABALHO normal em folga (não mexe em Balanço)
        if df.iloc[i]["Status"] != "Trabalho":
            return False
        dia = df.iloc[i]["Dia"]
        if dia == "dom":
            return False
        if dia == "sáb" and not pode_folgar_sabado:
            return False
        if not _nao_consecutiva_folga(df, i):
            return False
        return True

    consec, i = int(initial_consec), 0
    while i < len(df):
        if df.iloc[i]["Status"] in WORK_STATUSES:
            consec += 1
            if consec > 5:
                block_start = i - (consec - 1)
                block_end = i
                candidatos = []
                for j in range(block_start, block_end + 1):
                    if can_make_folga(j):
                        dia = df.iloc[j]["Dia"]
                        weekday_prio = 0 if dia in ["seg", "ter", "qua", "qui", "sex"] else 1
                        mid = (block_start + block_end) / 2
                        dist = abs(j - mid)
                        candidatos.append((weekday_prio, dist, j))
                if candidatos:
                    candidatos.sort()
                    escolhido = candidatos[0][2]
                    _set_folga(df, escolhido)
                    consec = 0
                    i = max(0, escolhido - 2)
                    continue
                else:
                    consec = 0
        else:
            consec = 0
        i += 1

def enforce_weekly_folga_targets(df: pd.DataFrame, df_ref: pd.DataFrame, pode_folgar_sabado: bool, locked_status: set[int] | None = None):
    """
    SEMANA SEG->DOM (regra geral):
      - Se DOM = Folga => 1 folga SEG-SÁB
      - Se DOM = Trabalho/Balanço => 2 folgas SEG-SÁB
      - Sábado só se permitido
      - Não cria folga consecutiva (exceto travado)
    Ajusta semana para cumprir o alvo (se outras regras mexerem depois).
    """
    datas = pd.to_datetime(df["Data"])
    weeks = _all_weeks_seg_dom(pd.DatetimeIndex(datas))

    def is_dom(i): return df_ref.loc[i, "Dia"] == "dom"

    def target_for_week(week):
        doms = [i for i in week if is_dom(i)]
        if not doms:
            return 2
        stt = df.loc[doms[0], "Status"]
        return 1 if stt == "Folga" else 2

    def can_turn_folga(i):
        if _locked(locked_status, i): return False
        if is_dom(i): return False
        if df.loc[i, "Status"] != "Trabalho": return False
        if df_ref.loc[i, "Dia"] == "sáb" and not pode_folgar_sabado: return False
        if not _nao_consecutiva_folga(df, i): return False
        return True

    def can_turn_trabalho(i):
        if _locked(locked_status, i): return False
        if is_dom(i): return False
        return df.loc[i, "Status"] == "Folga"

    for week in weeks:
        week = list(week)
        weekdays = [i for i in week if not is_dom(i)]
        t = target_for_week(week)

        cur = int((df.loc[weekdays, "Status"] == "Folga").sum())

        # excesso => remove
        if cur > t:
            cands = [i for i in weekdays if can_turn_trabalho(i)]
            def pr(i):
                return (0 if df_ref.loc[i, "Dia"] == "sáb" else 1, i)
            cands.sort(key=pr)
            for i in cands:
                if cur <= t: break
                _set_trabalho(df, i, ent_padrao="", locked_status=locked_status)  # entrada será re-setada depois pelo descanso global
                cur -= 1

        # falta => adiciona
        if cur < t:
            cands = [i for i in weekdays if can_turn_folga(i)]
            def pr2(i):
                return (0 if df_ref.loc[i, "Dia"] in ["seg","ter","qua","qui","sex"] else 1, i)
            cands.sort(key=pr2)
            for i in cands:
                if cur >= t: break
                _set_folga(df, i, locked_status=locked_status)
                cur += 1

    enforce_no_consecutive_folga(df, locked_status=locked_status)

def _counts_folgas_day_and_hour(hist_by_chapa: dict, colab_by_chapa: dict, chapas_grupo: list, idxs_semana: list, df_ref):
    counts_day = {i: 0 for i in idxs_semana}
    counts_day_hour = {}
    for ch in chapas_grupo:
        df = hist_by_chapa[ch]
        bucket = colab_by_chapa[ch].get("Entrada", "06:00")
        for i in idxs_semana:
            if df_ref.loc[i, "Dia"] == "dom":
                continue
            if df.loc[i, "Status"] == "Folga":
                counts_day[i] += 1
                counts_day_hour[(i, bucket)] = counts_day_hour.get((i, bucket), 0) + 1
    return counts_day, counts_day_hour

# =========================================================
# ✅ REBALANCE (corrigido): recebe estado_prev e respeita locked_idx
# =========================================================
def rebalance_folgas_dia(
    hist_by_chapa: dict,
    colab_by_chapa: dict,
    chapas_grupo: list,
    weeks: list,
    df_ref,
    estado_prev: dict | None = None,
    locked_idx: dict | None = None,
    max_iters=2200
):
    """
    Correções:
    - NÃO usa variável global: estado_prev é parâmetro (evita NameError)
    - Não faz swap em células travadas por override (locked_idx)
    """
    estado_prev = estado_prev or {}
    locked_idx = locked_idx or {}

    def is_dom(i): return df_ref.loc[i, "Dia"] == "dom"

    def is_locked(ch, i):
        return bool(i in (locked_idx.get(ch, set()) or set()))

    def can_swap(ch, i_from, i_to):
        df = hist_by_chapa[ch]
        pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))

        if is_dom(i_from) or is_dom(i_to): return False
        if is_locked(ch, i_from) or is_locked(ch, i_to): return False

        if df.loc[i_from, "Status"] == "Férias" or df.loc[i_to, "Status"] == "Férias": return False
        if df.loc[i_from, "Status"] != "Folga": return False
        if df.loc[i_to, "Status"] != "Trabalho": return False
        if df_ref.loc[i_to, "Dia"] == "sáb" and not pode_sab: return False
        if (i_to > 0 and df.loc[i_to - 1, "Status"] == "Folga") or (i_to < len(df)-1 and df.loc[i_to + 1, "Status"] == "Folga"):
            return False
        return True

    def do_swap(ch, i_from, i_to):
        df = hist_by_chapa[ch]
        ent = colab_by_chapa[ch].get("Entrada", "06:00")
        pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))

        _set_trabalho(df, i_from, ent, locked_status=locked_idx.get(ch, set()))
        _set_folga(df, i_to, locked_status=locked_idx.get(ch, set()))

        enforce_max_5_consecutive_work(
            df, ent, pode_sab,
            initial_consec=int((estado_prev.get(ch, {}) or {}).get('consec_trab_final', 0))
        )
        hist_by_chapa[ch] = df

    it = 0
    for week in weeks:
        week_idxs = [i for i in week if not is_dom(i)]
        if not week_idxs:
            continue
        while it < max_iters:
            it += 1
            counts = {i: 0 for i in week_idxs}
            for ch in chapas_grupo:
                df = hist_by_chapa[ch]
                for i in week_idxs:
                    if df.loc[i, "Status"] == "Folga":
                        counts[i] += 1
            mx = max(counts, key=lambda x: counts[x])
            mn = min(counts, key=lambda x: counts[x])
            if counts[mx] - counts[mn] <= 1:
                break
            candidates = [ch for ch in chapas_grupo if hist_by_chapa[ch].loc[mx, "Status"] == "Folga" and hist_by_chapa[ch].loc[mn, "Status"] == "Trabalho"]
            random.shuffle(candidates)
            moved = False
            for ch in candidates:
                if can_swap(ch, mx, mn):
                    do_swap(ch, mx, mn)
                    moved = True
                    break
            if not moved:
                break

# =========================================================
# GERAR ESCALA — POR SUBGRUPO
# =========================================================
def gerar_escala_setor_por_subgrupo(setor: str, colaboradores: list[dict], ano: int, mes: int, respeitar_ajustes: bool = True):
    datas = _dias_mes(ano, mes)
    weeks = _all_weeks_seg_dom(datas)
    df_ref = pd.DataFrame({"Data": datas, "Dia": [D_PT[d.day_name()] for d in datas]})
    estado_prev = load_estado_prev(setor, ano, mes)

    ovmap = _ov_map(setor, int(ano), int(mes)) if respeitar_ajustes else {}

    grupos = {}
    for c in colaboradores:
        sg = (c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO"
        grupos.setdefault(sg, []).append(c)

    regras_cache = {}
    for sg in grupos.keys():
        if sg == "SEM SUBGRUPO":
            regras_cache[sg] = {"seg": 0, "ter": 0, "qua": 0, "qui": 0, "sex": 0, "sáb": 0}
        else:
            regras_cache[sg] = get_subgrupo_regras(setor, sg)

    hist_all = {}
    colab_by_chapa = {c["Chapa"]: c for c in colaboradores}
    locked_idx = {}

    # base de cada colaborador
    for c in colaboradores:
        ch = c["Chapa"]
        df = df_ref.copy()
        df["Status"] = "Trabalho"
        df["H_Entrada"] = ""
        df["H_Saida"] = ""

        # ✅ férias só via tabela ferias
        for i, d in enumerate(datas):
            if is_de_ferias(setor, ch, d.date()):
                df.loc[i, "Status"] = "Férias"
                df.loc[i, "H_Entrada"] = ""
                df.loc[i, "H_Saida"] = ""

        if respeitar_ajustes:
            _apply_overrides_to_df_inplace(df, setor, ch, ovmap)

        locked = set()
        if respeitar_ajustes:
            for i in range(len(df)):
                if _is_status_locked(ovmap, ch, pd.to_datetime(df.loc[i, "Data"])):
                    locked.add(i)
        locked_idx[ch] = locked
        hist_all[ch] = df

    # ✅ Domingo 1x1 por colaborador COM CONTINUIDADE ENTRE MESES
    for ch, df in hist_all.items():
        ent = colab_by_chapa[ch].get("Entrada", "06:00")
        locked = locked_idx.get(ch, set())

        prev_dom = (estado_prev.get(ch, {}) or {}).get("ultimo_domingo_status", None)
        if prev_dom == "Folga":
            base_first = "Trabalho"
        elif prev_dom == "Trabalho":
            base_first = "Folga"
        else:
            base_first = None

        enforce_sundays_1x1_for_employee(df, ent, locked_status=locked, base_first=base_first)
        hist_all[ch] = df

    # =====================================================
    # ✅ REGRA SEMANAL NOVA (SEG->DOM) DEPENDE DO DOMINGO
    # =====================================================
    for sg, membros in grupos.items():
        chapas = [m["Chapa"] for m in membros]
        if not chapas:
            continue

        pref = regras_cache.get(sg, {"seg": 0, "ter": 0, "qua": 0, "qui": 0, "sex": 0, "sáb": 0})

        for week in weeks:
            idxs_week = sorted(week, key=lambda i: df_ref.loc[i, "Data"])
            domingos = [i for i in idxs_week if df_ref.loc[i, "Dia"] == "dom"]
            dom_idx = domingos[0] if domingos else None

            for ch in chapas:
                df = hist_all[ch]
                locked = locked_idx.get(ch, set())
                pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))
                ent_bucket = colab_by_chapa[ch].get("Entrada", "06:00")

                segunda_idx = idxs_week[0]
                segunda_date = df_ref.loc[segunda_idx, "Data"].date()
                if is_first_week_after_return(setor, ch, segunda_date):
                    continue

                # candidatos seg-sex e sábado só se permitido
                cand_days = []
                for i in idxs_week:
                    dia = df_ref.loc[i, "Dia"]
                    if dia == "dom":
                        continue
                    if dia == "sáb" and not pode_sab:
                        continue
                    cand_days.append(i)

                if dom_idx is None:
                    target_folgas = 2
                else:
                    dom_status = df.loc[dom_idx, "Status"]
                    target_folgas = 1 if dom_status == "Folga" else 2

                folgas_sem = int((df.loc[cand_days, "Status"] == "Folga").sum()) if cand_days else 0

                while folgas_sem < target_folgas:
                    counts_day, counts_day_hour = _counts_folgas_day_and_hour(hist_all, colab_by_chapa, chapas, cand_days, df_ref)

                    possiveis = []
                    for j in cand_days:
                        if j in locked:
                            continue
                        dia = df_ref.loc[j, "Dia"]
                        if df.loc[j, "Status"] != "Trabalho":
                            continue
                        if dia == "sáb" and not pode_sab:
                            continue
                        if not _nao_consecutiva_folga(df, j):
                            continue
                        possiveis.append(j)

                    if not possiveis:
                        break

                    random.shuffle(possiveis)

                    def score(j):
                        dia = df_ref.loc[j, "Dia"]
                        weekday_prio = 0 if dia in ["seg", "ter", "qua", "qui", "sex"] else 1
                        pref_pen = PREF_EVITAR_PENALTY if pref.get(dia, 0) == 1 else 0
                        return (
                            counts_day.get(j, 0),
                            counts_day_hour.get((j, ent_bucket), 0),
                            pref_pen,
                            weekday_prio,
                            random.random()
                        )

                    possiveis.sort(key=score)
                    pick = possiveis[0]
                    _set_folga(df, pick, locked_status=locked)
                    folgas_sem += 1
                    hist_all[ch] = df

    # Pós: aplica regras globais por colaborador
    for ch, df in hist_all.items():
        ent = colab_by_chapa[ch].get("Entrada", "06:00")
        locked = locked_idx.get(ch, set())
        pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))

        prev_dom = (estado_prev.get(ch, {}) or {}).get("ultimo_domingo_status", None)
        if prev_dom == "Folga":
            base_first = "Trabalho"
        elif prev_dom == "Trabalho":
            base_first = "Folga"
        else:
            base_first = None
        enforce_sundays_1x1_for_employee(df, ent, locked_status=locked, base_first=base_first)

        enforce_max_5_consecutive_work(df, ent, pode_sab, initial_consec=int((estado_prev.get(ch, {}) or {}).get('consec_trab_final', 0)))
        enforce_no_consecutive_folga(df, locked_status=locked)
        enforce_weekly_folga_targets(df, df_ref=df_ref, pode_folgar_sabado=pode_sab, locked_status=locked)

        ultima_saida_prev = estado_prev.get(ch, {}).get("ultima_saida", "") or ""
        enforce_global_rest_keep_targets(df, ent, locked_status=locked, ultima_saida_prev=ultima_saida_prev)

        enforce_no_consecutive_folga(df, locked_status=locked)
        enforce_global_rest_keep_targets(df, ent, locked_status=locked, ultima_saida_prev=ultima_saida_prev)

        if respeitar_ajustes:
            _apply_overrides_to_df_inplace(df, setor, ch, ovmap)

        hist_all[ch] = df

    # rebalance por grupo (com estado_prev e travas)
    for sg, membros in grupos.items():
        chapas = [m["Chapa"] for m in membros]
        if chapas:
            rebalance_folgas_dia(
                hist_all, colab_by_chapa, chapas, weeks, df_ref,
                estado_prev=estado_prev,
                locked_idx=locked_idx,
                max_iters=2200
            )

    # Pós final (garantia)
    for ch, df in hist_all.items():
        ent = colab_by_chapa[ch].get("Entrada", "06:00")
        locked = locked_idx.get(ch, set())
        ultima_saida_prev = estado_prev.get(ch, {}).get("ultima_saida", "") or ""

        prev_dom = (estado_prev.get(ch, {}) or {}).get("ultimo_domingo_status", None)
        if prev_dom == "Folga":
            base_first = "Trabalho"
        elif prev_dom == "Trabalho":
            base_first = "Folga"
        else:
            base_first = None
        enforce_sundays_1x1_for_employee(df, ent, locked_status=locked, base_first=base_first)
        enforce_no_consecutive_folga(df, locked_status=locked)
        enforce_weekly_folga_targets(df, df_ref=df_ref, pode_folgar_sabado=bool(colab_by_chapa[ch].get('Folga_Sab', False)), locked_status=locked)
        enforce_global_rest_keep_targets(df, ent, locked_status=locked, ultima_saida_prev=ultima_saida_prev)

        if respeitar_ajustes:
            _apply_overrides_to_df_inplace(df, setor, ch, ovmap)

        hist_all[ch] = df

    # Estado do mês
    estado_out = {}
    for ch, df in hist_all.items():
        consec = 0
        for i in range(len(df) - 1, -1, -1):
            if df.loc[i, "Status"] in WORK_STATUSES:
                consec += 1
            else:
                break

        ultima_saida = ""
        for i in range(len(df) - 1, -1, -1):
            if df.loc[i, "Status"] in WORK_STATUSES and (df.loc[i, "H_Saida"] or ""):
                ultima_saida = df.loc[i, "H_Saida"]
                break

        ultimo_dom = None
        for i in range(len(df) - 1, -1, -1):
            if df.loc[i, "Dia"] == "dom":
                if df.loc[i, "Status"] == "Folga":
                    ultimo_dom = "Folga"
                    break
                if df.loc[i, "Status"] in WORK_STATUSES:
                    ultimo_dom = "Trabalho"
                    break

        estado_out[ch] = {"consec_trab_final": consec, "ultima_saida": ultima_saida, "ultimo_domingo_status": ultimo_dom}

    return hist_all, estado_out

# =========================================================
# DASHBOARD / CALENDÁRIO / BANCO DE HORAS
# =========================================================
def banco_horas_df(hist_db: dict[str, pd.DataFrame], colab_by: dict, base_min: int):
    rows = []
    for ch, df in hist_db.items():
        nome = colab_by.get(ch, {}).get("Nome", ch)
        saldo = 0
        for _, r in df.iterrows():
            if r["Status"] not in WORK_STATUSES:
                continue
            ent = r.get("H_Entrada", "") or ""
            sai = r.get("H_Saida", "") or ""
            if not ent or not sai:
                continue
            dur = _to_min(sai) - _to_min(ent)
            if dur < 0:
                dur += 24 * 60
            saldo += (dur - base_min)
        rows.append({"Nome": nome, "Chapa": ch, "Saldo_min": saldo, "Saldo_h": round(saldo/60, 2)})
    return pd.DataFrame(rows).sort_values(["Saldo_min"], ascending=False)

def calendario_rh_df(hist_db: dict[str, pd.DataFrame], colab_by: dict):
    if not hist_db:
        return pd.DataFrame()
    any_df = next(iter(hist_db.values()))
    dias = [str(int(r.day)) for r in pd.to_datetime(any_df["Data"]).dt.date]
    cols = ["Nome", "Chapa", "Subgrupo"] + dias
    rows = []
    for ch, df in hist_db.items():
        nome = colab_by.get(ch, {}).get("Nome", ch)
        sg = (colab_by.get(ch, {}).get("Subgrupo", "") or "").strip() or "SEM SUBGRUPO"
        row = [nome, ch, sg]
        for i in range(len(df)):
            stt = df.loc[i, "Status"]
            if stt == "Folga":
                row.append("F")
            elif stt == "Férias":
                row.append("FER")
            else:
                row.append(df.loc[i, "H_Entrada"] or "")
        rows.append(row)
    out = pd.DataFrame(rows, columns=cols)
    return out.sort_values(["Subgrupo", "Nome"]).reset_index(drop=True)

def style_calendario(df: pd.DataFrame, mes: int, ano: int):
    if df.empty:
        return df
    dias_cols = df.columns[3:]
    qtd = calendar.monthrange(int(ano), int(mes))[1]
    dsem = {}
    for d in range(1, qtd + 1):
        ds = pd.Timestamp(year=int(ano), month=int(mes), day=int(d)).day_name()
        dsem[str(d)] = D_PT[ds]

    def cell_style(v, col):
        if col in dias_cols:
            dia_sem = dsem.get(col, "")
            if str(v) == "F":
                return "background-color:#FFF2CC; color:#000000; font-weight:700;"
            if str(v) == "FER":
                return "background-color:#92D050; color:#000000; font-weight:700;"
            if dia_sem == "dom":
                return "background-color:#BDD7EE; color:#000000;"
        return ""

    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for c in df.columns:
        styles[c] = df[c].apply(lambda v: cell_style(v, c))
    return df.style.apply(lambda _: styles, axis=None)

# =========================================================
# UI
# =========================================================
if "auth" not in st.session_state:
    st.session_state["auth"] = None
if "cfg_mes" not in st.session_state:
    st.session_state["cfg_mes"] = datetime.now().month
if "cfg_ano" not in st.session_state:
    st.session_state["cfg_ano"] = datetime.now().year
if "last_seed" not in st.session_state:
    st.session_state["last_seed"] = 0


db_init()

def page_login():
    st.title("🔐 Login por Setor (Usuário / Líder / Admin)")
    tab_login, tab_cadastrar, tab_esqueci = st.tabs(["Entrar", "Cadastrar Usuário do Sistema", "Esqueci a senha"])

    with tab_login:
        con = db_conn()
        setores = pd.read_sql_query("SELECT nome FROM setores ORDER BY nome ASC", con)["nome"].tolist()
        con.close()

        setor = st.selectbox("Setor:", setores, key="lg_setor")
        chapa = st.text_input("Chapa:", key="lg_chapa")
        senha = st.text_input("Senha:", type="password", key="lg_senha")

        if st.button("Entrar", key="lg_btn"):
            u = verify_login(setor, chapa, senha)
            if u:
                st.session_state["auth"] = u
                st.success("Login efetuado!")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")

        st.caption("Admin padrão: setor ADMIN | chapa admin | senha 123")

    with tab_cadastrar:
        st.subheader("Cadastrar usuário do sistema (com senha)")
        st.info("⚠️ Somente usuário do sistema tem senha. Colaborador é SEM senha.")
        nome = st.text_input("Nome:", key="cl_nome")
        setor = st.text_input("Setor:", key="cl_setor").strip().upper()
        chapa = st.text_input("Chapa:", key="cl_chapa")
        senha = st.text_input("Senha:", type="password", key="cl_senha")
        senha2 = st.text_input("Confirmar senha:", type="password", key="cl_senha2")
        is_admin = st.checkbox("Admin?", key="cl_admin")
        is_lider = st.checkbox("Líder?", value=False, key="cl_lider")

        if st.button("Criar usuário", key="cl_btn"):
            if not nome or not setor or not chapa or not senha:
                st.error("Preencha tudo.")
            elif senha != senha2:
                st.error("Senhas não conferem.")
            elif system_user_exists(setor, chapa):
                st.error("Já existe.")
            else:
                create_system_user(nome.strip(), setor, chapa.strip(), senha, is_lider=1 if is_lider else 0, is_admin=1 if is_admin else 0)
                st.success("Criado! Faça login.")
                st.rerun()

    with tab_esqueci:
        st.subheader("Redefinir senha (com chapa do líder do setor)")
        con = db_conn()
        setores = pd.read_sql_query("SELECT nome FROM setores ORDER BY nome ASC", con)["nome"].tolist()
        con.close()

        setor = st.selectbox("Setor:", setores, key="fp_setor")
        chapa = st.text_input("Sua chapa (usuário do sistema):", key="fp_chapa")
        chapa_lider = st.text_input("Chapa do líder:", key="fp_lider")
        nova = st.text_input("Nova senha:", type="password", key="fp_nova")
        nova2 = st.text_input("Confirmar:", type="password", key="fp_nova2")

        if st.button("Redefinir", key="fp_btn"):
            if not chapa or not chapa_lider or not nova:
                st.error("Preencha.")
            elif nova != nova2:
                st.error("Senhas não conferem.")
            elif not system_user_exists(setor, chapa):
                st.error("Usuário não encontrado.")
            elif not is_lider_chapa(setor, chapa_lider):
                st.error("Chapa do líder inválida.")
            else:
                update_password(setor, chapa, nova)
                st.success("Senha alterada.")
                st.rerun()

def _regenerar_mes_inteiro(setor: str, ano: int, mes: int, seed: int = 0, respeitar_ajustes: bool = True):
    """
    Regera a escala do mês inteiro para TODO o setor, respeitando overrides (travas),
    para 'readequar' automaticamente após ajustes manuais.
    """
    colaboradores = load_colaboradores_setor(setor)
    if not colaboradores:
        return False
    random.seed(int(seed))
    hist, estado_out = gerar_escala_setor_por_subgrupo(
        setor, colaboradores, int(ano), int(mes),
        respeitar_ajustes=bool(respeitar_ajustes)
    )
    save_escala_mes_db(setor, int(ano), int(mes), hist)
    save_estado_mes(setor, int(ano), int(mes), estado_out)
    return True

def page_app():
    auth = st.session_state.get("auth") or {}
    setor = auth.get("setor", "GERAL")

    # ---- Competência (mês/ano) compartilhada
    ano_cfg = int(st.session_state.get("cfg_ano", datetime.now().year))
    mes_cfg = int(st.session_state.get("cfg_mes", datetime.now().month))
    st.session_state["cfg_ano"] = ano_cfg
    st.session_state["cfg_mes"] = mes_cfg

    if "last_seed" not in st.session_state:
        st.session_state["last_seed"] = 0

    # =========================
    # SIDEBAR — Sessão + Competência
    # =========================
    with st.sidebar:
        st.title("👤 Sessão")
        st.caption("Acesso por setor (usuário / líder / admin)")

        cA, cB = st.columns([1, 1])
        cA.write(f"**Nome:** {auth.get('nome','-')}")
        cB.write(f"**Perfil:** {'ADMIN' if auth.get('is_admin', False) else ('LÍDER' if auth.get('is_lider', False) else 'USUÁRIO')}")

        st.write(f"**Setor:** {setor}")
        st.write(f"**Chapa:** {auth.get('chapa','-')}")

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        st.subheader("🗓️ Competência")
        m1, m2 = st.columns(2)
        mes_cfg = m1.selectbox("Mês", list(range(1, 13)), index=mes_cfg - 1, key="sb_mes")
        ano_cfg = m2.number_input("Ano", value=ano_cfg, step=1, key="sb_ano")
        st.session_state["cfg_mes"] = int(mes_cfg)
        st.session_state["cfg_ano"] = int(ano_cfg)

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        st.write(
            "• 👥 Colaboradores\n"
            "• 🚀 Gerar Escala\n"
            "• ⚙️ Ajustes\n"
            "• 🏖️ Férias\n"
            "• 📥 Excel"
        )

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        if st.button("🚪 Sair", use_container_width=True, key="logout_btn"):
            st.session_state["auth"] = None
            st.rerun()

        st.title(f"📅 Escala 5x2 — Setor: {setor}")
        st.caption(
            "✅ Regras ativas: Descanso 11:10 + Domingo 1x1 + Sem folga consecutiva automática + "
            "Férias só via Aba Férias + Regra semanal depende do domingo."
        )

    # =========================
    # KPIs — visual
    # =========================
    ano_k = int(st.session_state["cfg_ano"])
    mes_k = int(st.session_state["cfg_mes"])

    colaboradores_k = load_colaboradores_setor(setor)
    total_colab = len(colaboradores_k)

    hist_db_kpi = load_escala_mes_db(setor, ano_k, mes_k)
    if hist_db_kpi:
        hist_db_kpi = apply_overrides_to_hist(setor, ano_k, mes_k, hist_db_kpi)

    folgas_mes = 0
    ferias_mes = 0
    trabalhos_mes = 0
    if hist_db_kpi:
        for _, dfk in hist_db_kpi.items():
            folgas_mes += int((dfk["Status"] == "Folga").sum())
            ferias_mes += int((dfk["Status"] == "Férias").sum())
            trabalhos_mes += int(dfk["Status"].isin(WORK_STATUSES).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Colaboradores</div>"
        f"<p class='kpi-value'>{total_colab}</p></div>",
        unsafe_allow_html=True
    )
    k2.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Dias de Folga (mês)</div>"
        f"<p class='kpi-value'>{folgas_mes}</p></div>",
        unsafe_allow_html=True
    )
    k3.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Dias de Férias (mês)</div>"
        f"<p class='kpi-value'>{ferias_mes}</p></div>",
        unsafe_allow_html=True
    )
    k4.markdown(
        f"<div class='kpi-card'><div class='kpi-title'>Dias de Trabalho (mês)</div>"
        f"<p class='kpi-value'>{trabalhos_mes}</p></div>",
        unsafe_allow_html=True
    )

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    # =========================
    # ABAS
    # =========================
    tabs = ["👥 Colaboradores", "🚀 Gerar Escala", "⚙️ Ajustes", "🏖️ Férias", "📥 Excel"]
    is_admin_area = bool(auth.get("is_admin", False)) and setor == "ADMIN"
    if is_admin_area:
        tabs.append("🔒 Admin")

    abas = st.tabs(tabs)

    # ------------------------------------------------------
    # ABA 1: Colaboradores
    # ------------------------------------------------------
    with abas[0]:
        st.subheader("👥 Colaboradores (SEM senha)")
        colaboradores = load_colaboradores_setor(setor)

        if colaboradores:
            st.dataframe(pd.DataFrame([{
                "Nome": c["Nome"],
                "Chapa": c["Chapa"],
                "Subgrupo": c["Subgrupo"] or "SEM SUBGRUPO",
                "Entrada": c["Entrada"],
                "Folga Sábado": "Sim" if c["Folga_Sab"] else "Não",
            } for c in colaboradores]), use_container_width=True, height=420)
        else:
            st.info("Sem colaboradores.")

        st.markdown("---")

        with st.form("form_add_colaborador", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome_n = c1.text_input("Nome:", key="col_nome")
            chapa_n = c2.text_input("Chapa:", key="col_chapa")
            submitted = st.form_submit_button("Cadastrar colaborador", use_container_width=True)
            if submitted:
                if not nome_n or not chapa_n:
                    st.error("Preencha nome e chapa.")
                elif colaborador_exists(setor, chapa_n.strip()):
                    st.error("Já existe essa chapa.")
                else:
                    create_colaborador(nome_n.strip(), setor, chapa_n.strip())
                    st.success("Cadastrado!")
                    st.rerun()

        st.markdown("---")
        st.markdown("## 🗑️ Excluir colaborador")
        if colaboradores:
            ch_del = st.selectbox("Escolha a chapa para excluir:", [c["Chapa"] for c in colaboradores], key="del_chapa")
            st.warning("⚠️ Excluir remove também férias, ajustes, escala e estado desse colaborador no setor.")
            confirm = st.checkbox("Confirmo que quero excluir definitivamente", key="del_confirm")
            if st.button("Excluir colaborador", key="del_btn"):
                if not confirm:
                    st.error("Marque a confirmação para excluir.")
                else:
                    delete_colaborador_total(setor, ch_del)
                    st.success("Colaborador excluído!")
                    st.rerun()

        st.markdown("---")
        st.markdown("## ✏️ Editar perfil do colaborador")
        if colaboradores:
            chapas = [c["Chapa"] for c in colaboradores]
            ch_sel = st.selectbox("Chapa:", chapas, key="pf_chapa")
            csel = next(x for x in colaboradores if x["Chapa"] == ch_sel)

            colp1, colp2, colp3 = st.columns(3)
            ent = colp1.time_input("Entrada:", value=datetime.strptime(csel["Entrada"], "%H:%M").time(), key="pf_ent")
            sg_opts = [""] + list_subgrupos(setor)
            idx_default = sg_opts.index(csel["Subgrupo"]) if csel["Subgrupo"] in sg_opts else 0
            sg = colp2.selectbox("Subgrupo:", sg_opts, index=idx_default, key="pf_sg")
            sab = colp3.checkbox("Permitir folga sábado", value=bool(csel["Folga_Sab"]), key="pf_sab")

            if st.button("Salvar perfil", key="pf_save"):
                update_colaborador_perfil(setor, ch_sel, sg, ent.strftime("%H:%M"), sab)
                st.success("Salvo!")
                st.rerun()

    # ------------------------------------------------------
    # ABA 2: Gerar Escala
    # ------------------------------------------------------
    with abas[1]:
        st.subheader("🚀 Gerar escala")
        st.caption(f"Competência ativa: **{int(st.session_state['cfg_mes']):02d}/{int(st.session_state['cfg_ano'])}**")

        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, 2])
            mes = c1.selectbox("Mês:", list(range(1, 13)), index=int(st.session_state["cfg_mes"]) - 1, key="gen_mes")
            ano = c2.number_input("Ano:", value=int(st.session_state["cfg_ano"]), step=1, key="gen_ano")
            seed = c3.number_input("Semente (mantém padrão sugerido)", min_value=0, max_value=999999, value=int(st.session_state.get("last_seed", 0)), key="gen_seed")

        st.session_state["cfg_mes"] = int(mes)
        st.session_state["cfg_ano"] = int(ano)

        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Cadastre colaboradores.")
        else:
            b1, b2, _ = st.columns([1, 1, 6])
            if b1.button("🚀 Gerar agora (respeita ajustes)", use_container_width=True, key="gen_btn"):
                st.session_state["last_seed"] = int(seed)
                ok = _regenerar_mes_inteiro(setor, int(ano), int(mes), seed=int(seed), respeitar_ajustes=True)
                if ok:
                    st.success("Escala gerada (ajustes/travas preservados)!")
                else:
                    st.warning("Sem colaboradores.")
                st.rerun()

            if b2.button("🔄 Recarregar do banco", use_container_width=True, key="gen_reload_btn"):
                st.rerun()

            hist_db = load_escala_mes_db(setor, int(ano), int(mes))
            hist_db = apply_overrides_to_hist(setor, int(ano), int(mes), hist_db)

            if hist_db:
                colab_by = {c["Chapa"]: c for c in colaboradores}
                st.markdown("### 📅 Calendário RH (visual por colaborador)")
                cal = calendario_rh_df(hist_db, colab_by)
                show_color = st.checkbox("🎨 Mostrar cores no calendário (pode deixar lento)", value=False, key="cal_color")
                if show_color:
                    st.dataframe(style_calendario(cal, int(mes), int(ano)), use_container_width=True)
                else:
                    st.dataframe(cal, use_container_width=True)

                st.markdown("---")
                st.markdown("### 👤 Visualizar colaborador (detalhado)")
                ch_view = st.selectbox("Chapa:", list(hist_db.keys()), key="view_ch")
                st.dataframe(hist_db[ch_view], use_container_width=True, height=420)
            else:
                st.info("Sem escala no mês. Clique em **Gerar agora**.")

    # ------------------------------------------------------
    # ABA 3: Ajustes
    # ------------------------------------------------------
    with abas[2]:
        st.subheader("⚙️ Ajustes (travas) — sempre entram na geração")

        # ✅ IMPORTANTE: Ajustes/folgas manuais são gravados por MÊS/ANO (competência).
        # Se você editar Fevereiro e gerar Janeiro, não vai aparecer.
        with st.container(border=True):
            c1, c2, c3 = st.columns([1,1,2])
            mes = c1.selectbox("Mês (ajustes)", list(range(1,13)), index=int(st.session_state["cfg_mes"])-1, key="adj_mes")
            ano = c2.number_input("Ano (ajustes)", value=int(st.session_state["cfg_ano"]), step=1, key="adj_ano")
            c3.caption("Dica: deixe o mês/ano aqui igual ao mês/ano da aba 🚀 Gerar Escala.")

        st.session_state["cfg_mes"] = int(mes)
        st.session_state["cfg_ano"] = int(ano)
        st.caption(f"Competência ativa: **{int(mes):02d}/{int(ano)}** | Seed atual: **{int(st.session_state.get('last_seed', 0))}**")

        hist_db = load_escala_mes_db(setor, ano, mes)
        colaboradores = load_colaboradores_setor(setor)
        colab_by = {c["Chapa"]: c for c in colaboradores}

        if not hist_db:
            st.info("Gere a escala primeiro na aba 🚀 Gerar Escala.")
        else:
            hist_db = apply_overrides_to_hist(setor, ano, mes, hist_db)

            t1, tgrid, t2, t3, t4 = st.tabs([
                "🔧 Ajuste por dia",
                "🧩 Folgas manuais em grade",
                "📅 Trocar horário mês inteiro",
                "✅ Preferência por subgrupo",
                "📌 Subgrupos (editável)"
            ])

            with tgrid:
                st.markdown("### 🧩 Folgas manuais em grade (por colaborador)")
                st.caption(
                    "Marque/desmarque as folgas do mês. Isso cria/remove travas (overrides) de Status=Folga. "
                    "Domingo continua 1x1 e não é editável aqui."
                )

                st.markdown("**Competência da grade (mês/ano):**")
                gA, gB, gC = st.columns([1, 1, 2])
                mes_grid = gA.selectbox("Mês", list(range(1, 13)), index=int(mes) - 1, key="grid_mes_sel")
                ano_grid = gB.number_input("Ano", value=int(ano), step=1, key="grid_ano_sel")
                auto_readequar = gC.checkbox("🔄 Readequar escala ao salvar", value=True, key="grid_auto_regen")

                # mantém competência selecionada nas demais abas
                st.session_state["cfg_mes"] = int(mes_grid)
                st.session_state["cfg_ano"] = int(ano_grid)

                # recarrega a escala desta competência
                hist_db_grid = load_escala_mes_db(setor, int(ano_grid), int(mes_grid))
                if hist_db_grid:
                    hist_db_grid = apply_overrides_to_hist(setor, int(ano_grid), int(mes_grid), hist_db_grid)
                else:
                    st.warning("Não há escala salva para esta competência. Gere na aba 🚀 Gerar Escala.")
                    hist_db_grid = {}

                # usa essas variáveis no restante da grade
                ano = int(ano_grid)
                mes = int(mes_grid)
                hist_db = hist_db_grid


                f1, f2, f3 = st.columns([1, 1, 2])
                fil_sub = f1.selectbox("Filtrar subgrupo:", ["(todos)"] + sorted({(c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO" for c in colaboradores}), key="grid_sub")
                fil_nome = f2.text_input("Buscar nome:", "", key="grid_busca").strip().lower()
                somente_permite_sab = f3.checkbox("Mostrar só quem PERMITE folga sábado", value=False, key="grid_sab_only")

                cols_f = []
                for c in colaboradores:
                    sg = (c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO"
                    if fil_sub != "(todos)" and sg != fil_sub:
                        continue
                    if fil_nome and fil_nome not in (c.get("Nome", "").lower()):
                        continue
                    if somente_permite_sab and not bool(c.get("Folga_Sab", False)):
                        continue
                    cols_f.append(c)

                if not cols_f:
                    st.info("Nenhum colaborador no filtro.")
                else:
                    qtd = calendar.monthrange(int(ano), int(mes))[1]
                    dias = list(range(1, qtd + 1))

                    ovdf = load_overrides(setor, ano, mes)
                    ov_status = {}
                    if ovdf is not None and not ovdf.empty:
                        od = ovdf[ovdf["campo"] == "status"]
                        for _, r in od.iterrows():
                            if str(r["valor"]) == "Folga":
                                ov_status.setdefault(str(r["chapa"]), set()).add(int(r["dia"]))

                    rows = []
                    for c in cols_f:
                        chg = str(c["Chapa"])
                        row = {"Nome": c["Nome"], "Chapa": chg}
                        dfh = hist_db.get(chg)
                        for d in dias:
                            is_dom = False
                            is_fer = False
                            if dfh is not None and len(dfh) >= d:
                                is_dom = (dfh.loc[d - 1, "Dia"] == "dom")
                                is_fer = (dfh.loc[d - 1, "Status"] == "Férias")
                            if is_dom or is_fer:
                                row[str(d)] = False
                            else:
                                row[str(d)] = (d in ov_status.get(chg, set()))
                        rows.append(row)

                    df_grid = pd.DataFrame(rows)

                    st.markdown("#### ✅ Marque as folgas (dias)")
                    edited = st.data_editor(
                        df_grid,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={str(d): st.column_config.CheckboxColumn(str(d), width="small") for d in dias},
                        key="grid_editor"
                    )

                    if st.button("💾 Salvar folgas manuais (e readequar mês)", key="grid_save"):
                        saved = 0
                        removed = 0
                        for _, r in edited.iterrows():
                            chg = str(r["Chapa"])
                            dfh = hist_db.get(chg)
                            for d in dias:
                                col = str(d)
                                want = bool(r[col])
                                was = (d in ov_status.get(chg, set()))

                                if dfh is not None and len(dfh) >= d:
                                    if dfh.loc[d - 1, "Dia"] == "dom":
                                        continue
                                    if dfh.loc[d - 1, "Status"] == "Férias":
                                        continue

                                if want and not was:
                                    set_override(setor, ano, mes, chg, d, "status", "Folga")
                                    saved += 1
                                elif (not want) and was:
                                    delete_override(setor, ano, mes, chg, d, "status")
                                    removed += 1

                        if auto_readequar:
                            _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)

                        st.success(f"Salvo! Criadas: {saved} | Removidas: {removed}. Escala readequada mantendo travas!")
                        st.rerun()

            with t2:
                ch2 = st.selectbox("Chapa:", list(hist_db.keys()), key="adjm_ch")
                dfm = hist_db[ch2].copy()
                ent_pad2 = colab_by.get(ch2, {}).get("Entrada", "06:00")
                pode_sab2 = bool(colab_by.get(ch2, {}).get("Folga_Sab", False))
                subgrupo2 = (colab_by.get(ch2, {}).get("Subgrupo", "") or "").strip()

                nova_ent_mes = st.time_input("Nova entrada:", value=datetime.strptime(ent_pad2, "%H:%M").time(), key="adjm_ent")

                if st.button("Aplicar mês inteiro (e readequar)", key="adjm_apply"):
                    e = nova_ent_mes.strftime("%H:%M")
                    s = _saida_from_entrada(e)

                    for i in range(len(dfm)):
                        stt = dfm.loc[i, "Status"]
                        dia_num = int(pd.to_datetime(dfm.loc[i, "Data"]).day)

                        if stt in WORK_STATUSES:
                            dfm.loc[i, "Status"] = "Trabalho"
                            dfm.loc[i, "H_Entrada"] = e
                            dfm.loc[i, "H_Saida"] = s

                            set_override(setor, ano, mes, ch2, dia_num, "status", "Trabalho")
                            set_override(setor, ano, mes, ch2, dia_num, "h_entrada", e)
                            set_override(setor, ano, mes, ch2, dia_num, "h_saida", s)
                        else:
                            dfm.loc[i, "H_Entrada"] = ""
                            dfm.loc[i, "H_Saida"] = ""

                    update_colaborador_perfil(setor, ch2, subgrupo2, e, bool(pode_sab2))

                    save_escala_mes_db(setor, ano, mes, {ch2: dfm})
                    _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)

                    st.success("Horário do mês inteiro FORÇADO e escala readequada.")
                    st.rerun()

                st.dataframe(dfm, use_container_width=True, height=420)

            with t3:
                st.markdown("### ✅ Preferência por subgrupo (Evitar folga se possível)")
                subgrupos = list_subgrupos(setor)

                if subgrupos:
                    sg_sel = st.selectbox("Escolha o subgrupo:", subgrupos, key="pref_sg_sel")
                    regras = get_subgrupo_regras(setor, sg_sel)

                    p1, p2, p3 = st.columns(3)
                    ev_seg = p1.checkbox("Evitar SEG", value=bool(regras["seg"]), key=f"ev_seg_{sg_sel}")
                    ev_ter = p1.checkbox("Evitar TER", value=bool(regras["ter"]), key=f"ev_ter_{sg_sel}")
                    ev_qua = p2.checkbox("Evitar QUA", value=bool(regras["qua"]), key=f"ev_qua_{sg_sel}")
                    ev_qui = p2.checkbox("Evitar QUI", value=bool(regras["qui"]), key=f"ev_qui_{sg_sel}")
                    ev_sex = p3.checkbox("Evitar SEX", value=bool(regras["sex"]), key=f"ev_sex_{sg_sel}")
                    ev_sab = p3.checkbox("Evitar SÁB", value=bool(regras["sáb"]), key=f"ev_sab_{sg_sel}")

                    if st.button("Salvar preferência do subgrupo (e readequar mês)", key="pref_save"):
                        set_subgrupo_regras(setor, sg_sel, {
                            "seg": int(ev_seg), "ter": int(ev_ter), "qua": int(ev_qua),
                            "qui": int(ev_qui), "sex": int(ev_sex), "sáb": int(ev_sab)
                        })
                        _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                        st.success("Preferência salva e escala readequada!")
                        st.rerun()
                else:
                    st.info("Crie pelo menos 1 subgrupo na aba 👥 Colaboradores.")

            with t4:
                st.markdown("## 📌 Subgrupos (editável)")
                subgrupos = list_subgrupos(setor)

                cA, cB = st.columns([1, 1])
                with cA:
                    novo_sub = st.text_input("Novo subgrupo:", key="sg_new")
                    if st.button("Adicionar subgrupo", key="sg_add"):
                        if novo_sub.strip():
                            add_subgrupo(setor, novo_sub.strip())
                            st.success("Subgrupo adicionado!")
                            st.rerun()
                        else:
                            st.error("Digite o nome do subgrupo.")

                with cB:
                    if subgrupos:
                        del_sel = st.selectbox("Remover subgrupo:", ["(nenhum)"] + subgrupos, key="sg_del")
                        if del_sel != "(nenhum)" and st.button("Remover", key="sg_del_btn"):
                            delete_subgrupo(setor, del_sel)
                            _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                            st.success("Subgrupo removido e escala readequada!")
                            st.rerun()
                    else:
                        st.caption("Nenhum subgrupo cadastrado.")

    # ------------------------------------------------------
    # ABA 4: Férias
    # ------------------------------------------------------
    with abas[3]:
        st.subheader("🏖️ Controle de Férias")
        colaboradores = load_colaboradores_setor(setor)

        if not colaboradores:
            st.warning("Sem colaboradores cadastrados.")
        else:
            chapas = [c["Chapa"] for c in colaboradores]
            st.markdown("### ➕ Lançar Férias")
            ch = st.selectbox("Chapa:", chapas, key="fer_ch")
            col1, col2 = st.columns(2)
            ini = col1.date_input("Início:", key="fer_ini")
            fim = col2.date_input("Fim:", key="fer_fim")

            if st.button("Adicionar férias (e readequar mês)", key="fer_add"):
                if fim < ini:
                    st.error("Data final não pode ser menor que a inicial.")
                else:
                    add_ferias(setor, ch, ini, fim)
                    _regenerar_mes_inteiro(setor, int(st.session_state["cfg_ano"]), int(st.session_state["cfg_mes"]), seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                    st.success("Férias adicionadas e escala readequada!")
                    st.rerun()

            st.markdown("---")
            st.markdown("### 📋 Férias cadastradas")
            rows = list_ferias(setor)

            if rows:
                df_f = pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"])
                st.dataframe(df_f, use_container_width=True, height=420)

                st.markdown("### ❌ Remover férias")
                rem_idx = st.number_input("Linha para remover (1,2,3...)", min_value=1, max_value=len(df_f), value=1, key="fer_rem_idx")

                if st.button("Remover linha (e readequar mês)", key="fer_rem_btn"):
                    r = df_f.iloc[int(rem_idx) - 1]
                    delete_ferias_row(setor, r["Chapa"], r["Início"], r["Fim"])
                    _regenerar_mes_inteiro(setor, int(st.session_state["cfg_ano"]), int(st.session_state["cfg_mes"]), seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                    st.success("Férias removidas e escala readequada!")
                    st.rerun()
            else:
                st.info("Nenhuma férias cadastrada.")

    # ------------------------------------------------------
    # ABA 5: Excel
    # ------------------------------------------------------
    with abas[4]:
        st.subheader("📥 Excel modelo RH (separado por subgrupo)")
        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = load_escala_mes_db(setor, ano, mes)
        colaboradores = load_colaboradores_setor(setor)
        colab_by = {c["Chapa"]: c for c in colaboradores}

        if not hist_db:
            st.info("Gere a escala.")
        else:
            hist_db = apply_overrides_to_hist(setor, ano, mes, hist_db)

            if st.button("📊 Gerar Excel", key="xls_btn"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    wb = writer.book
                    ws = wb.create_sheet("Escala Mensal", index=0)

                    fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", patternType="solid")
                    fill_dom = PatternFill(start_color="C00000", end_color="C00000", patternType="solid")
                    fill_folga = PatternFill(start_color="FFF2CC", end_color="FFF2CC", patternType="solid")
                    fill_nome = PatternFill(start_color="D9E1F2", end_color="D9E1F2", patternType="solid")
                    fill_ferias = PatternFill(start_color="92D050", end_color="92D050", patternType="solid")
                    fill_group = PatternFill(start_color="BDD7EE", end_color="BDD7EE", patternType="solid")

                    font_header = Font(color="FFFFFF", bold=True)
                    font_dom = Font(color="FFFFFF", bold=True)

                    border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
                    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

                    ch0 = list(hist_db.keys())[0]
                    df_ref_xls = hist_db[ch0]
                    total_dias = len(df_ref_xls)

                    ws.cell(1, 1, "COLABORADOR").fill = fill_header
                    ws.cell(1, 1).font = font_header
                    ws.cell(1, 1).alignment = center
                    ws.cell(1, 1).border = border
                    ws.cell(2, 1, "").fill = fill_header
                    ws.cell(2, 1).alignment = center
                    ws.cell(2, 1).border = border

                    for i in range(total_dias):
                        dia_num = df_ref_xls.iloc[i]["Data"].day
                        dia_sem = df_ref_xls.iloc[i]["Dia"]
                        cA = ws.cell(1, i + 2, dia_num)
                        cB = ws.cell(2, i + 2, dia_sem)

                        if dia_sem == "dom":
                            cA.fill = fill_dom
                            cB.fill = fill_dom
                            cA.font = font_dom
                            cB.font = font_dom
                        else:
                            cA.fill = fill_header
                            cB.fill = fill_header
                            cA.font = font_header
                            cB.font = font_header

                        cA.alignment = center
                        cB.alignment = center
                        cA.border = border
                        cB.border = border
                        ws.column_dimensions[get_column_letter(i + 2)].width = 7

                    ws.column_dimensions["A"].width = 36

                    subgrupo_map = {}
                    for chx in hist_db.keys():
                        sg = (colab_by.get(chx, {}).get("Subgrupo", "") or "").strip() or "SEM SUBGRUPO"
                        subgrupo_map.setdefault(sg, []).append(chx)

                    subgrupos_ordenados = sorted(subgrupo_map.keys())
                    row_idx = 3

                    for sg in subgrupos_ordenados:
                        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=total_dias + 1)
                        t = ws.cell(row_idx, 1, f"SUBGRUPO: {sg}")
                        t.fill = fill_group
                        t.font = Font(bold=True)
                        t.alignment = Alignment(horizontal="left", vertical="center")
                        t.border = border
                        row_idx += 1

                        chapas_sg = sorted(subgrupo_map[sg], key=lambda chx: colab_by.get(chx, {}).get("Nome", chx))
                        for chx in chapas_sg:
                            df_f = hist_db[chx]
                            nome = colab_by.get(chx, {}).get("Nome", chx)

                            c_nome = ws.cell(row_idx, 1, f"{nome}\nCHAPA: {chx}")
                            c_nome.fill = fill_nome
                            c_nome.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                            c_nome.border = border
                            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx + 1, end_column=1)

                            for i, row in df_f.iterrows():
                                dia_sem = row["Dia"]
                                status = row["Status"]
                                if status == "Férias":
                                    v1, v2 = "FÉRIAS", ""
                                elif status == "Folga":
                                    v1, v2 = "F", ""
                                else:
                                    v1, v2 = row["H_Entrada"], row["H_Saida"]

                                cell1 = ws.cell(row_idx, i + 2, v1)
                                cell2 = ws.cell(row_idx + 1, i + 2, v2)

                                cell1.alignment = center
                                cell2.alignment = center
                                cell1.border = border
                                cell2.border = border

                                if status == "Férias":
                                    cell1.fill = fill_ferias
                                    cell2.fill = fill_ferias
                                elif status == "Folga":
                                    if dia_sem == "dom":
                                        cell1.fill = fill_dom
                                        cell2.fill = fill_dom
                                    else:
                                        cell1.fill = fill_folga
                                        cell2.fill = fill_folga

                            row_idx += 2
                        row_idx += 1

                    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
                        wb.remove(wb["Sheet"])

                st.download_button(
                    "📥 Baixar Excel",
                    data=output.getvalue(),
                    file_name=f"escala_{setor}_{mes:02d}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="xls_down"
                )

    # ------------------------------------------------------
    # ABA 6: Admin (somente ADMIN)
    # ------------------------------------------------------
    if is_admin_area:
        with abas[5]:
            st.subheader("🔒 Admin do Sistema (somente ADMIN)")
            dfu = admin_list_users()
            st.dataframe(dfu, use_container_width=True, height=420)

            st.markdown("### Resetar senha de um usuário")
            if not dfu.empty:
                uid = st.selectbox("ID do usuário", dfu["id"].tolist(), key="adm_uid")
                newp = st.text_input("Nova senha", type="password", key="adm_newp")
                if st.button("Resetar senha", key="adm_reset"):
                    if not newp:
                        st.error("Digite a senha.")
                    else:
                        ok = admin_reset_user_password(int(uid), newp)
                        st.success("Senha resetada!" if ok else "Falha.")
                        st.rerun()

            st.markdown("---")
            st.markdown("### Criar usuário do sistema (com senha)")
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome", key="adm_nome")
            setor_u = c2.text_input("Setor", key="adm_setor").strip().upper()
            chapa = c3.text_input("Chapa", key="adm_chapa")
            c4, c5, c6 = st.columns(3)
            senha = c4.text_input("Senha", type="password", key="adm_senha")
            is_lider = c5.checkbox("Líder", key="adm_lider")
            is_admin = c6.checkbox("Admin", key="adm_admin")
            if st.button("Criar usuário", key="adm_create"):
                if not nome or not setor_u or not chapa or not senha:
                    st.error("Preencha tudo.")
                elif system_user_exists(setor_u, chapa):
                    st.error("Já existe.")
                else:
                    create_system_user(nome.strip(), setor_u, chapa.strip(), senha, is_lider=int(is_lider), is_admin=int(is_admin))
                    st.success("Criado!")
                    st.rerun()

# =========================================================
# MAIN

# =========================================================
db_init()

if st.session_state["auth"] is None:
    page_login()
else:
    page_app()
