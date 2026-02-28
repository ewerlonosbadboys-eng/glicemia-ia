# app.py
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO (SUBGRUPO = REGRAS)
# + Preferência "Evitar folga" por subgrupo
# + Persistência real (SQLite) de ajustes (overrides)
# + Calendário RH visual + Dashboard + Banco de Horas
# + Admin (somente setor ADMIN e is_admin)
# + NOVO: Gerar respeitando ajustes (overrides) OU ignorando
#        (botão/checkbox antes de gerar)
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

APP_VERSION = "v1.0.3-balanco-madrugada"

DB_PATH = "escala.db"

# ---- Regras fixas
INTERSTICIO_MIN = timedelta(hours=11, minutes=10)
DURACAO_JORNADA = timedelta(hours=9, minutes=58)

# Penalidade forte para "evitar folga" (não proíbe, só evita)
PREF_EVITAR_PENALTY = 1000

# Status que contam como TRABALHO (inclui marcações especiais)
WORK_STATUSES = {"Trabalho", "Balanço", "Balanço Madrugada"}

def is_work_status(status: str) -> bool:
    return str(status) in WORK_STATUSES


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

    # setores
    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS setores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )
    """)

    # usuários do sistema
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

    # colaboradores (sem senha)
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

    # subgrupos disponíveis por setor
    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS subgrupos_setor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        nome TEXT NOT NULL,
        UNIQUE(setor, nome)
    )
    """)

    # preferências por subgrupo (evitar folga)
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

    # férias
    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS ferias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL
    )
    """)

    # estado mês anterior (escala corrida)
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

    # escala do mês (persistida)
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

    # overrides (ajustes persistidos)
    _safe_exec(cur, """
    CREATE TABLE IF NOT EXISTS overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        chapa TEXT NOT NULL,
        dia INTEGER NOT NULL,
        campo TEXT NOT NULL,   -- status | h_entrada | h_saida
        valor TEXT NOT NULL,
        UNIQUE(setor, ano, mes, chapa, dia, campo)
    )
    """)

    con.commit()

    # setores padrão
    _safe_exec(cur, "INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("GERAL",))
    _safe_exec(cur, "INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("ADMIN",))
    con.commit()

    # admin padrão
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
    cur.execute("UPDATE usuarios_sistema SET senha_hash=?, salt=? WHERE setor=? AND chapa=?", (senha_hash, salt, setor, chapa))
    con.commit()
    con.close()

# =========================================================
# ADMIN
# =========================================================
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
# COLABORADORES (SEM senha)
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
# SUBGRUPOS + REGRAS (Preferência)
# =========================================================
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

def delete_subgrupo(setor: str, nome: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM subgrupos_setor WHERE setor=? AND nome=?", (setor, nome))
    cur.execute("DELETE FROM subgrupo_regras WHERE setor=? AND subgrupo=?", (setor, nome))
    cur.execute("UPDATE colaboradores SET subgrupo='' WHERE setor=? AND subgrupo=?", (setor, nome))
    con.commit()
    con.close()

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

def delete_ferias_row(setor: str, chapa: str, inicio: str, fim: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        DELETE FROM ferias
        WHERE setor=? AND chapa=? AND inicio=? AND fim=?
    """, (setor, chapa, inicio, fim))
    con.commit()
    con.close()

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

# ---- regra “volta de férias”: desconsidera a primeira semana para 5x2 (mas domingo 1x1 continua)
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
# ESTADO (escala corrida)
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
# OVERRIDES (AJUSTES PERSISTIDOS)
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

def del_override(setor: str, ano: int, mes: int, chapa: str, dia: int, campo: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        DELETE FROM overrides
        WHERE setor=? AND ano=? AND mes=? AND chapa=? AND dia=? AND campo=?
    """, (setor, int(ano), int(mes), chapa, int(dia), campo))
    con.commit()
    con.close()

def load_overrides(setor: str, ano: int, mes: int):
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT chapa, dia, campo, valor
        FROM overrides
        WHERE setor=? AND ano=? AND mes=?
    """, con, params=(setor, int(ano), int(mes)))
    con.close()
    return df

# >>> NOVO: mapa rápido de overrides + aplicação antes do gerar
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

def _apply_overrides_to_df_inplace(df: pd.DataFrame, chapa: str, ovmap: dict):
    if chapa not in ovmap:
        return df
    for i in range(len(df)):
        dia_num = int(pd.to_datetime(df.loc[i, "Data"]).day)
        rule = ovmap.get(chapa, {}).get(dia_num, {})
        if not rule:
            continue

        if "status" in rule:
            df.loc[i, "Status"] = rule["status"]
            if rule["status"] != "Trabalho":
                df.loc[i, "H_Entrada"] = ""
                df.loc[i, "H_Saida"] = ""

        if "h_entrada" in rule:
            df.loc[i, "H_Entrada"] = rule["h_entrada"]

        if "h_saida" in rule:
            df.loc[i, "H_Saida"] = rule["h_saida"]

        if is_work_status(df.loc[i, "Status"]):
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
    ov = load_overrides(setor, ano, mes)
    if ov.empty or not hist_db:
        return hist_db
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
        if campo == "status":
            df.loc[idx, "Status"] = valor
            if not is_work_status(valor):
                df.loc[idx, "H_Entrada"] = ""
                df.loc[idx, "H_Saida"] = ""
        elif campo == "h_entrada":
            df.loc[idx, "H_Entrada"] = valor
            if df.loc[idx, "Status"] == "Trabalho":
                df.loc[idx, "H_Saida"] = _saida_from_entrada(valor)
        elif campo == "h_saida":
            df.loc[idx, "H_Saida"] = valor
        hist_db[ch] = df
    return hist_db

# =========================================================
# MOTOR REGRAS
# =========================================================
def _dias_mes(ano: int, mes: int):
    qtd = calendar.monthrange(ano, mes)[1]
    return pd.date_range(start=f"{ano}-{mes:02d}-01", periods=qtd, freq="D")

def _saida_from_entrada(ent: str) -> str:
    return (datetime.strptime(ent, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")

def calcular_entrada_segura(saida_ant: str, ent_padrao: str) -> str:
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = e - s
        if diff.total_seconds() < 0:
            diff += timedelta(days=1)
        if diff < INTERSTICIO_MIN:
            return (s + INTERSTICIO_MIN).strftime(fmt)
    except:
        pass
    return ent_padrao

def _nao_consecutiva_folga(df, idx):
    if idx > 0 and df.loc[idx - 1, "Status"] == "Folga":
        return False
    if idx < len(df) - 1 and df.loc[idx + 1, "Status"] == "Folga":
        return False
    return True

# >>> ALTERADO: setters respeitam lock (status travado por override)
def _set_trabalho(df, idx, ent_padrao, locked_status: set[int] | None = None):
    if locked_status and idx in locked_status:
        return
    df.loc[idx, "Status"] = "Trabalho"
    if not df.loc[idx, "H_Entrada"]:
        df.loc[idx, "H_Entrada"] = ent_padrao
    if not df.loc[idx, "H_Saida"]:
        df.loc[idx, "H_Saida"] = _saida_from_entrada(df.loc[idx, "H_Entrada"])

def _set_folga(df, idx, locked_status: set[int] | None = None):
    if locked_status and idx in locked_status:
        return
    df.loc[idx, "Status"] = "Folga"
    df.loc[idx, "H_Entrada"] = ""
    df.loc[idx, "H_Saida"] = ""

def _set_ferias(df, idx, locked_status: set[int] | None = None):
    if locked_status and idx in locked_status:
        return
    df.loc[idx, "Status"] = "Férias"
    df.loc[idx, "H_Entrada"] = ""
    df.loc[idx, "H_Saida"] = ""

def recompute_hours_with_intersticio(df, ent_padrao, ultima_saida_prev: str | None = None):
    ents, sais = [], []
    first_work_done = False

    for i in range(len(df)):
        stt = df.loc[i, "Status"]

        if not is_work_status(stt):
            ents.append("")
            sais.append("")
            continue

        # preserva horários fixos do balanço (não recalcular)
        if stt in ("Balanço", "Balanço Madrugada") and df.loc[i, "H_Entrada"] and df.loc[i, "H_Saida"]:
            ents.append(df.loc[i, "H_Entrada"])
            sais.append(df.loc[i, "H_Saida"])
            continue

        e = df.loc[i, "H_Entrada"] if df.loc[i, "H_Entrada"] else ent_padrao

        if (not first_work_done) and ultima_saida_prev:
            e = calcular_entrada_segura(ultima_saida_prev, e)
            first_work_done = True

        if i > 0 and sais and sais[-1]:
            e = calcular_entrada_segura(sais[-1], e)

        ents.append(e)
        sais.append(_saida_from_entrada(e))

    df["H_Entrada"] = ents
    df["H_Saida"] = sais

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

def enforce_sundays_alternating_for_employee(df, ent_padrao, start_dom_idx):
    domingos = [i for i in range(len(df)) if df.loc[i, "Data"].day_name() == "Sunday"]
    if start_dom_idx not in domingos:
        return
    base_status = df.loc[start_dom_idx, "Status"]
    if base_status not in ["Trabalho", "Folga"]:
        return
    pos = domingos.index(start_dom_idx)
    current = base_status
    for k in range(pos + 1, len(domingos)):
        idx = domingos[k]
        if df.loc[idx, "Status"] == "Férias":
            continue
        current = "Folga" if current == "Trabalho" else "Trabalho"
        if current == "Folga":
            _set_folga(df, idx)
        else:
            _set_trabalho(df, idx, ent_padrao)

def enforce_max_5_consecutive_work(df, ent_padrao, pode_folgar_sabado: bool):
    def can_make_folga(i):
        if not is_work_status(df.loc[i, "Status"]):
            return False
        dia = df.loc[i, "Dia"]
        if dia == "dom":
            return False
        if dia == "sáb" and not pode_folgar_sabado:
            return False
        if not _nao_consecutiva_folga(df, i):
            return False
        return True

    consec, i = 0, 0
    while i < len(df):
        if is_work_status(df.loc[i, "Status"]):
            consec += 1
            if consec > 5:
                block_start = i - (consec - 1)
                block_end = i
                candidatos = []
                for j in range(block_start, block_end + 1):
                    if can_make_folga(j):
                        dia = df.loc[j, "Dia"]
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

def rebalance_folgas_dia(hist_by_chapa: dict, colab_by_chapa: dict, chapas_grupo: list, weeks: list, df_ref, max_iters=2200):
    def is_dom(i): return df_ref.loc[i, "Dia"] == "dom"

    def can_swap(ch, i_from, i_to):
        df = hist_by_chapa[ch]
        pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))
        if is_dom(i_from) or is_dom(i_to): return False
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
        _set_trabalho(df, i_from, ent)
        _set_folga(df, i_to)
        enforce_max_5_consecutive_work(df, ent, pode_sab)
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
# DOMINGO 1x1 (SUBGRUPO) — REBALANCE APÓS AJUSTE
# =========================================================
def rebalance_sundays_subgrupo(hist_all: dict[str, pd.DataFrame], chapas: list[str], ent_map: dict, datas: pd.DatetimeIndex):
    """
    Garante por domingo: ~metade folga / metade trabalho dentro do subgrupo
    Respeita Férias.
    Não mexe em sábado/semana — só domingo.
    """
    domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    if not domingos:
        return

    chapas_sorted = sorted(chapas)
    n = len(chapas_sorted)
    if n == 0:
        return
    target = (n + 1) // 2  # metade arredondando pra cima

    pointer = 0
    for dom_i in domingos:
        available = [ch for ch in chapas_sorted if hist_all[ch].loc[dom_i, "Status"] != "Férias"]
        if not available:
            continue

        folgando = [ch for ch in available if hist_all[ch].loc[dom_i, "Status"] == "Folga"]
        trabalhando = [ch for ch in available if hist_all[ch].loc[dom_i, "Status"] == "Trabalho"]

        while len(folgando) > min(target, len(available)):
            ch = folgando.pop()
            ent = ent_map.get(ch, "06:00")
            _set_trabalho(hist_all[ch], dom_i, ent)
            trabalhando.append(ch)

        while len(folgando) < min(target, len(available)):
            if not trabalhando:
                break
            ch = available[pointer % len(available)]
            pointer += 1
            if hist_all[ch].loc[dom_i, "Status"] == "Férias":
                continue
            if hist_all[ch].loc[dom_i, "Status"] == "Trabalho":
                _set_folga(hist_all[ch], dom_i)
                folgando.append(ch)
                try:
                    trabalhando.remove(ch)
                except:
                    pass
            else:
                continue

# =========================================================
# GERAR ESCALA — POR SUBGRUPO (com preferências)
# =========================================================
def gerar_escala_setor_por_subgrupo(setor: str, colaboradores: list[dict], ano: int, mes: int, respeitar_ajustes: bool = True):
    datas = _dias_mes(ano, mes)
    weeks = _all_weeks_seg_dom(datas)
    domingos_idx = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]

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

    # base + férias + overrides + lock
    locked_idx = {}
    for c in colaboradores:
        ch = c["Chapa"]
        df = df_ref.copy()
        df["Status"] = "Trabalho"
        df["H_Entrada"] = ""
        df["H_Saida"] = ""

        for i, d in enumerate(datas):
            if is_de_ferias(setor, ch, d.date()):
                df.loc[i, "Status"] = "Férias"
                df.loc[i, "H_Entrada"] = ""
                df.loc[i, "H_Saida"] = ""

        if respeitar_ajustes:
            _apply_overrides_to_df_inplace(df, ch, ovmap)

        locked = set()
        if respeitar_ajustes:
            for i in range(len(df)):
                if _is_status_locked(ovmap, ch, pd.to_datetime(df.loc[i, "Data"])):
                    locked.add(i)
        locked_idx[ch] = locked
        hist_all[ch] = df

    # por subgrupo
    for sg, membros in grupos.items():
        chapas = [m["Chapa"] for m in membros]
        if not chapas:
            continue

        ent_map = {ch: colab_by_chapa[ch].get("Entrada", "06:00") for ch in chapas}

        # domingo 1x1 (base), respeitando lock
        rng = random.Random(9000 + ano + mes + len(chapas) + (hash(sg) % 9999))
        chapas_sh = sorted(chapas)
        rng.shuffle(chapas_sh)
        meio = (len(chapas_sh) + 1) // 2
        grupo_a = set(chapas_sh[:meio])
        grupo_b = set(chapas_sh[meio:])

        for ch in chapas:
            df = hist_all[ch]
            ent = ent_map.get(ch, "06:00")
            locked = locked_idx.get(ch, set())
            for k, dom_i in enumerate(domingos_idx):
                if df.loc[dom_i, "Status"] == "Férias":
                    continue
                if dom_i in locked:
                    continue
                alvo_folga = grupo_a if (k % 2 == 0) else grupo_b
                if ch in alvo_folga:
                    _set_folga(df, dom_i, locked_status=locked)
                else:
                    _set_trabalho(df, dom_i, ent, locked_status=locked)
            hist_all[ch] = df

        # escala corrida (primeiro domingo), respeita lock
        if domingos_idx:
            primeiro_dom = domingos_idx[0]
            for ch in chapas:
                if ch in estado_prev and estado_prev[ch].get("ultimo_domingo_status") in ["Trabalho", "Folga"]:
                    df = hist_all[ch]
                    ent = ent_map.get(ch, "06:00")
                    locked = locked_idx.get(ch, set())
                    if df.loc[primeiro_dom, "Status"] != "Férias" and (primeiro_dom not in locked):
                        if estado_prev[ch]["ultimo_domingo_status"] == "Trabalho":
                            _set_folga(df, primeiro_dom, locked_status=locked)
                        else:
                            _set_trabalho(df, primeiro_dom, ent, locked_status=locked)
                        enforce_sundays_alternating_for_employee(df, ent, primeiro_dom)
                    hist_all[ch] = df

        # rebalance domingos (e reaplica overrides se respeitar)
        rebalance_sundays_subgrupo(hist_all, chapas, ent_map, datas)
        if respeitar_ajustes:
            for ch in chapas:
                _apply_overrides_to_df_inplace(hist_all[ch], ch, ovmap)

        # 5x2
        pref = regras_cache.get(sg, {"seg": 0, "ter": 0, "qua": 0, "qui": 0, "sex": 0, "sáb": 0})

        for week in weeks:
            cand_days = [i for i in week if df_ref.loc[i, "Dia"] != "dom"]

            for ch in chapas:
                df = hist_all[ch]
                locked = locked_idx.get(ch, set())
                pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))
                ent_bucket = colab_by_chapa[ch].get("Entrada", "06:00")

                segunda_idx = min(week, key=lambda i: df_ref.loc[i, "Data"])
                segunda_date = df_ref.loc[segunda_idx, "Data"].date()
                if is_first_week_after_return(setor, ch, segunda_date):
                    continue

                folgas_sem = int((df.loc[week, "Status"] == "Folga").sum())

                dom_idx = next((i for i in week if df_ref.loc[i, "Dia"] == "dom"), None)
                if dom_idx is not None and df.loc[dom_idx, "Status"] == "Trabalho":
                    seg_sex = [i for i in cand_days if df_ref.loc[i, "Dia"] in ["seg", "ter", "qua", "qui", "sex"]]
                    if seg_sex and not any(df.loc[i, "Status"] == "Folga" for i in seg_sex):
                        poss = []
                        for j in seg_sex:
                            if j in locked:
                                continue
                            if df.loc[j, "Status"] != "Trabalho":
                                continue
                            if not _nao_consecutiva_folga(df, j):
                                continue
                            poss.append(j)
                        if poss:
                            counts_day, counts_day_hour = _counts_folgas_day_and_hour(hist_all, colab_by_chapa, chapas, seg_sex, df_ref)
                            random.shuffle(poss)
                            poss.sort(key=lambda j: (
                                counts_day.get(j, 0),
                                counts_day_hour.get((j, ent_bucket), 0),
                                PREF_EVITAR_PENALTY if pref.get(df_ref.loc[j, "Dia"], 0) == 1 else 0,
                                random.random()
                            ))
                            _set_folga(df, poss[0], locked_status=locked)
                            folgas_sem += 1

                while folgas_sem < 2:
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

        # limite 5 seguidos + interstício + reaplica overrides
        for ch in chapas:
            df = hist_all[ch]
            ent = ent_map.get(ch, "06:00")
            locked = locked_idx.get(ch, set())
            pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))

            if ch in estado_prev and int(estado_prev[ch].get("consec_trab_final", 0)) >= 5:
                for i in range(len(df)):
                    if i in locked:
                        continue
                    if df.loc[i, "Status"] == "Trabalho" and df_ref.loc[i, "Dia"] in ["seg", "ter", "qua", "qui", "sex"]:
                        _set_folga(df, i, locked_status=locked)
                        break

            enforce_max_5_consecutive_work(df, ent, pode_sab)
            ultima_saida_prev = estado_prev.get(ch, {}).get("ultima_saida", "")
            recompute_hours_with_intersticio(df, ent, ultima_saida_prev=ultima_saida_prev)

            if respeitar_ajustes:
                _apply_overrides_to_df_inplace(df, ch, ovmap)

            hist_all[ch] = df

        rebalance_folgas_dia(hist_all, colab_by_chapa, chapas, weeks, df_ref, max_iters=2200)
        rebalance_sundays_subgrupo(hist_all, chapas, ent_map, datas)
        if respeitar_ajustes:
            for ch in chapas:
                _apply_overrides_to_df_inplace(hist_all[ch], ch, ovmap)

    estado_out = {}
    for ch, df in hist_all.items():
        consec = 0
        for i in range(len(df)-1, -1, -1):
            if is_work_status(df.loc[i, "Status"]):
                consec += 1
            else:
                break

        ultima_saida = ""
        for i in range(len(df)-1, -1, -1):
            if df.loc[i, "Status"] == "Trabalho" and df.loc[i, "H_Saida"]:
                ultima_saida = df.loc[i, "H_Saida"]
                break

        ultimo_dom = None
        for i in range(len(df)-1, -1, -1):
            if df.loc[i, "Dia"] == "dom" and df.loc[i, "Status"] in ["Trabalho", "Folga"]:
                ultimo_dom = df.loc[i, "Status"]
                break

        estado_out[ch] = {"consec_trab_final": consec, "ultima_saida": ultima_saida, "ultimo_domingo_status": ultimo_dom}

    return hist_all, estado_out

# =========================================================
# DASHBOARD / CALENDÁRIO / BANCO DE HORAS
# =========================================================
def _to_minutes(hhmm: str) -> int:
    if not hhmm:
        return 0
    t = datetime.strptime(hhmm, "%H:%M")
    return t.hour * 60 + t.minute

def banco_horas_df(hist_db: dict[str, pd.DataFrame], colab_by: dict, base_min: int):
    rows = []
    for ch, df in hist_db.items():
        nome = colab_by.get(ch, {}).get("Nome", ch)
        saldo = 0
        for _, r in df.iterrows():
            if not is_work_status(r["Status"]):
                continue
            ent = r.get("H_Entrada", "") or ""
            sai = r.get("H_Saida", "") or ""
            if not ent or not sai:
                continue
            dur = _to_minutes(sai) - _to_minutes(ent)
            if dur < 0:
                dur += 24 * 60
            saldo += (dur - base_min)
        rows.append({"Nome": nome, "Chapa": ch, "Saldo_min": saldo, "Saldo_h": round(saldo/60, 2)})
    return pd.DataFrame(rows).sort_values(["Saldo_min"], ascending=False)

def folgas_por_dia_df(hist_db: dict[str, pd.DataFrame]):
    if not hist_db:
        return pd.DataFrame()
    any_df = next(iter(hist_db.values()))
    out = []
    for i in range(len(any_df)):
        dia = int(any_df.loc[i, "Data"].day)
        ds = any_df.loc[i, "Dia"]
        folgas = 0
        ferias = 0
        trab = 0
        for _, df in hist_db.items():
            stt = df.loc[i, "Status"]
            if stt == "Folga":
                folgas += 1
            elif stt == "Férias":
                ferias += 1
            elif is_work_status(stt):
                trab += 1
        out.append({"Dia": dia, "DiaSem": ds, "Trabalho": trab, "Folga": folgas, "Férias": ferias})
    return pd.DataFrame(out)

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

def page_app():
    auth = st.session_state["auth"] or {}
    setor = auth.get("setor", "GERAL")

    st.sidebar.title("👤 Sessão")
    st.sidebar.caption(f"Versão: {APP_VERSION}")
    st.sidebar.write(f"**Nome:** {auth.get('nome','-')}")
    st.sidebar.write(f"**Setor:** {setor}")
    st.sidebar.write(f"**Chapa:** {auth.get('chapa','-')}")
    st.sidebar.write(f"**Perfil:** {'ADMIN' if auth.get('is_admin', False) else ('LÍDER' if auth.get('is_lider', False) else 'USUÁRIO')}")

    if st.sidebar.button("Sair", key="logout_btn"):
        st.session_state["auth"] = None
        st.rerun()

    st.title(f"📅 Escala 5x2 — Setor: {setor}")
    st.caption("📌 Regras por SUBGRUPO + Preferência 'Evitar folga' por subgrupo + Domingo 1x1 balanceado.")

    tabs = ["👥 Colaboradores", "🚀 Gerar Escala", "⚙️ Ajustes", "🏖️ Férias", "📥 Excel"]
    is_admin_area = bool(auth.get("is_admin", False)) and setor == "ADMIN"
    if is_admin_area:
        tabs.append("🔒 Admin")
    abas = st.tabs(tabs)

    # ------------------------------------------------------
    # ABA 1: Colaboradores
    # ------------------------------------------------------
    with abas[0]:
        colaboradores = load_colaboradores_setor(setor)
        st.subheader("Colaboradores (SEM senha)")

        if colaboradores:
            st.dataframe(pd.DataFrame([{
                "Nome": c["Nome"],
                "Chapa": c["Chapa"],
                "Subgrupo": c["Subgrupo"] or "SEM SUBGRUPO",
                "Entrada": c["Entrada"],
                "Folga Sábado": "Sim" if c["Folga_Sab"] else "Não",
            } for c in colaboradores]), use_container_width=True)
        else:
            st.info("Sem colaboradores.")

        st.markdown("---")

        c1, c2 = st.columns(2)
        nome_n = c1.text_input("Nome:", key="col_nome")
        chapa_n = c2.text_input("Chapa:", key="col_chapa")

        if st.button("Cadastrar colaborador", key="col_add"):
            if not nome_n or not chapa_n:
                st.error("Preencha nome e chapa.")
            elif colaborador_exists(setor, chapa_n.strip()):
                st.error("Já existe essa chapa.")
            else:
                create_colaborador(nome_n.strip(), setor, chapa_n.strip())
                st.success("Cadastrado!")
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
        st.subheader("Gerar escala")

        c1, c2, c3 = st.columns(3)
        mes = c1.selectbox("Mês:", list(range(1, 13)), index=st.session_state["cfg_mes"] - 1, key="gen_mes")
        ano = c2.number_input("Ano:", value=st.session_state["cfg_ano"], step=1, key="gen_ano")
        seed = c3.number_input("Semente (opcional)", min_value=0, max_value=999999, value=0, key="gen_seed")

        st.session_state["cfg_mes"] = int(mes)
        st.session_state["cfg_ano"] = int(ano)

        # >>> NOVO: opção para respeitar ou ignorar ajustes
        respeitar_ajustes = st.checkbox(
            "✅ Gerar respeitando ajustes (marcados em ⚙️ Ajustes)",
            value=True,
            key="gen_respeitar_ajustes",
            help="Quando marcado, o gerador lê overrides (status/horários) antes de montar a escala e evita mexer no que está travado."
        )

        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Cadastre colaboradores.")
        else:
            colG1, colG2 = st.columns(2)
            if colG1.button("🚀 Gerar agora", key="gen_btn"):
                random.seed(int(seed))
                hist, estado_out = gerar_escala_setor_por_subgrupo(
                    setor, colaboradores, int(ano), int(mes),
                    respeitar_ajustes=bool(respeitar_ajustes)
                )
                save_escala_mes_db(setor, int(ano), int(mes), hist)
                save_estado_mes(setor, int(ano), int(mes), estado_out)
                st.success("Escala gerada!")
                st.rerun()

            if colG2.button("📥 Recarregar do banco", key="gen_reload_btn"):
                st.rerun()

            hist_db = load_escala_mes_db(setor, int(ano), int(mes))
            hist_db = apply_overrides_to_hist(setor, int(ano), int(mes), hist_db)

            if hist_db:
                colab_by = {c["Chapa"]: c for c in colaboradores}

                st.markdown("### 📅 Calendário RH (visual por colaborador)")
                cal = calendario_rh_df(hist_db, colab_by)
                st.dataframe(style_calendario(cal, int(mes), int(ano)), use_container_width=True)

                st.markdown("---")
                st.markdown("### 📊 Dashboard estatístico")
                d1, d2 = st.columns(2)
                d1.dataframe(folgas_por_dia_df(hist_db), use_container_width=True)

                sg_rows = []
                for ch, df in hist_db.items():
                    sg = (colab_by.get(ch, {}).get("Subgrupo", "") or "").strip() or "SEM SUBGRUPO"
                    sg_rows.append({"Subgrupo": sg,
                                    "Folgas": int((df["Status"] == "Folga").sum()),
                                    "Férias": int((df["Status"] == "Férias").sum()),
                                    "Trabalho": int(df["Status"].apply(is_work_status).sum())})
                if sg_rows:
                    sg_df = pd.DataFrame(sg_rows).groupby("Subgrupo", as_index=False).sum(numeric_only=True)
                    d2.dataframe(sg_df.sort_values("Subgrupo"), use_container_width=True)

                st.markdown("---")
                st.markdown("### 🧮 Indicador de banco de horas")
                base_min = int(DURACAO_JORNADA.total_seconds() // 60)
                bh = banco_horas_df(hist_db, colab_by, base_min)
                st.dataframe(bh, use_container_width=True)

                st.markdown("---")
                st.markdown("### Visualizar colaborador (detalhado)")
                ch_view = st.selectbox("Chapa:", list(hist_db.keys()), key="view_ch")
                st.dataframe(hist_db[ch_view], use_container_width=True)
            else:
                st.info("Sem escala no mês. Clique em **Gerar agora**.")

    # ------------------------------------------------------
    # ABA 3: Ajustes
    # ------------------------------------------------------
    with abas[2]:
        st.subheader("Ajustes")

        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = load_escala_mes_db(setor, ano, mes)
        colaboradores = load_colaboradores_setor(setor)
        colab_by = {c["Chapa"]: c for c in colaboradores}

        if not hist_db:
            st.info("Gere a escala primeiro.")
        else:
            hist_db = apply_overrides_to_hist(setor, ano, mes, hist_db)

            t1, t2, t3, t4 = st.tabs([
                "🔧 Ajuste por dia",
                "📅 Trocar horário mês inteiro",
                "✅ Preferência por subgrupo",
                "📌 Subgrupos (editável)"
            ])

            with t1:
                ch = st.selectbox("Chapa:", list(hist_db.keys()), key="adj_ch")
                df = hist_db[ch].copy()
                ent_pad = colab_by.get(ch, {}).get("Entrada", "06:00")
                pode_sab = bool(colab_by.get(ch, {}).get("Folga_Sab", False))

                col1, col2, col3 = st.columns(3)
                dia_sel = col1.number_input("Dia:", 1, len(df), value=1, key="adj_dia")
                acao = col2.selectbox("Ação:", ["Marcar Trabalho", "Marcar Folga", "Marcar Férias", "Alterar Entrada", "Marcar Balanço (madrugada)"], key="adj_acao")
                nova_ent = col3.time_input("Entrada:", value=datetime.strptime(ent_pad, "%H:%M").time(), key="adj_ent")

                if st.button("Aplicar", key="adj_apply"):
                    idx = int(dia_sel) - 1
                    dia_sem = df.loc[idx, "Dia"]
                    dia_num = int(pd.to_datetime(df.loc[idx, "Data"]).day)

                    if acao == "Marcar Férias":
                        _set_ferias(df, idx)
                        set_override(setor, ano, mes, ch, dia_num, "status", "Férias")

                    elif acao == "Marcar Folga":
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode (dia está em férias).")
                        elif dia_sem == "sáb" and not pode_sab:
                            st.error("Sábado só se permitir folga no sábado.")
                        else:
                            _set_folga(df, idx)
                            set_override(setor, ano, mes, ch, dia_num, "status", "Folga")

                    elif acao == "Marcar Trabalho":
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode (dia está em férias).")
                        else:
                            e = nova_ent.strftime("%H:%M")
                            df.loc[idx, "H_Entrada"] = e
                            _set_trabalho(df, idx, e)
                            set_override(setor, ano, mes, ch, dia_num, "status", "Trabalho")
                            set_override(setor, ano, mes, ch, dia_num, "h_entrada", e)

                    elif acao == "Marcar Balanço (madrugada)":
                        # Dia marcado: 06:00 → 11:50 (Balanço)
                        # Dia seguinte automático: 00:10 → 10:08 (Balanço Madrugada)
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode (dia está em férias).")
                        else:
                            df.loc[idx, "Status"] = "Balanço"
                            df.loc[idx, "H_Entrada"] = "06:00"
                            df.loc[idx, "H_Saida"] = "11:50"
                            set_override(setor, ano, mes, ch, dia_num, "status", "Balanço")
                            set_override(setor, ano, mes, ch, dia_num, "h_entrada", "06:00")
                            set_override(setor, ano, mes, ch, dia_num, "h_saida", "11:50")

                            if idx + 1 < len(df):
                                dia_num2 = int(pd.to_datetime(df.loc[idx + 1, "Data"]).day)
                                if df.loc[idx + 1, "Status"] != "Férias":
                                    df.loc[idx + 1, "Status"] = "Balanço Madrugada"
                                    df.loc[idx + 1, "H_Entrada"] = "00:10"
                                    df.loc[idx + 1, "H_Saida"] = "10:08"
                                    set_override(setor, ano, mes, ch, dia_num2, "status", "Balanço Madrugada")
                                    set_override(setor, ano, mes, ch, dia_num2, "h_entrada", "00:10")
                                    set_override(setor, ano, mes, ch, dia_num2, "h_saida", "10:08")

                    else:  # Alterar Entrada
                        if not is_work_status(df.loc[idx, "Status"]):
                            st.error("Só em dias de trabalho.")
                        else:
                            e = nova_ent.strftime("%H:%M")
                            df.loc[idx, "H_Entrada"] = e
                            df.loc[idx, "H_Saida"] = _saida_from_entrada(e)
                            set_override(setor, ano, mes, ch, dia_num, "h_entrada", e)
                    if df.loc[idx, "Data"].day_name() == "Sunday":
                        enforce_sundays_alternating_for_employee(df, ent_pad, idx)

                    enforce_max_5_consecutive_work(df, ent_pad, pode_sab)
                    recompute_hours_with_intersticio(df, ent_pad)

                    save_escala_mes_db(setor, ano, mes, {ch: df})

                    sg = (colab_by.get(ch, {}).get("Subgrupo", "") or "").strip() or "SEM SUBGRUPO"
                    chapas_sg = [c["Chapa"] for c in colaboradores if ((c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO") == sg]
                    if chapas_sg:
                        hist_all = load_escala_mes_db(setor, ano, mes)
                        hist_all = apply_overrides_to_hist(setor, ano, mes, hist_all)
                        datas = _dias_mes(ano, mes)
                        ent_map = {cc: colab_by.get(cc, {}).get("Entrada", "06:00") for cc in chapas_sg if cc in hist_all}
                        rebalance_sundays_subgrupo(hist_all, [cc for cc in chapas_sg if cc in hist_all], ent_map, datas)
                        save_escala_mes_db(setor, ano, mes, {cc: hist_all[cc] for cc in chapas_sg if cc in hist_all})

                    st.success("Ajuste salvo (com persistência) e domingos reequilibrados no subgrupo!")
                    st.rerun()

                st.dataframe(df, use_container_width=True)

            with t2:
                ch2 = st.selectbox("Chapa:", list(hist_db.keys()), key="adjm_ch")
                dfm = hist_db[ch2].copy()
                ent_pad2 = colab_by.get(ch2, {}).get("Entrada", "06:00")
                pode_sab2 = bool(colab_by.get(ch2, {}).get("Folga_Sab", False))

                nova_ent_mes = st.time_input("Nova entrada:", value=datetime.strptime(ent_pad2, "%H:%M").time(), key="adjm_ent")
                if st.button("Aplicar mês inteiro", key="adjm_apply"):
                    e = nova_ent_mes.strftime("%H:%M")
                    for i in range(len(dfm)):
                        if dfm.loc[i, "Status"] == "Trabalho":
                            dfm.loc[i, "H_Entrada"] = e
                            dfm.loc[i, "H_Saida"] = _saida_from_entrada(e)
                            dia_num = int(pd.to_datetime(dfm.loc[i, "Data"]).day)
                            set_override(setor, ano, mes, ch2, dia_num, "h_entrada", e)

                    enforce_max_5_consecutive_work(dfm, e, pode_sab2)
                    recompute_hours_with_intersticio(dfm, e)

                    save_escala_mes_db(setor, ano, mes, {ch2: dfm})
                    st.success("Horário do mês inteiro aplicado (persistido)!")
                    st.rerun()

                st.dataframe(dfm, use_container_width=True)

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

                    if st.button("Salvar preferência do subgrupo", key="pref_save"):
                        set_subgrupo_regras(setor, sg_sel, {
                            "seg": int(ev_seg), "ter": int(ev_ter), "qua": int(ev_qua),
                            "qui": int(ev_qui), "sex": int(ev_sex), "sáb": int(ev_sab)
                        })
                        st.success("Preferência salva!")
                        st.rerun()
                else:
                    st.info("Crie pelo menos 1 subgrupo para configurar preferência.")

            with t4:
                st.markdown("## 📌 Subgrupos (editável) + Preferência de dias com menos folga")

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
                            st.success("Subgrupo removido!")
                            st.rerun()
                    else:
                        st.caption("Nenhum subgrupo cadastrado.")

                st.markdown("---")
                st.info("Após criar o subgrupo, configure as regras na aba '✅ Preferência por subgrupo'.")

    # ------------------------------------------------------
    # ABA 4: Férias
    # ------------------------------------------------------
    with abas[3]:
        st.subheader("Férias")
        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Sem colaboradores.")
        else:
            chapas = [c["Chapa"] for c in colaboradores]
            ch = st.selectbox("Chapa:", chapas, key="fer_ch")
            c1, c2 = st.columns(2)
            ini = c1.date_input("Início:", key="fer_ini")
            fim = c2.date_input("Fim:", key="fer_fim")

            if st.button("Adicionar férias", key="fer_add"):
                if fim < ini:
                    st.error("Fim menor que início.")
                else:
                    add_ferias(setor, ch, ini, fim)
                    st.success("Férias adicionadas.")
                    st.rerun()

            rows = list_ferias(setor)
            if rows:
                df_f = pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"])
                st.dataframe(df_f, use_container_width=True)

                st.markdown("### Remover férias")
                rem_idx = st.number_input("Linha (1,2,3...)", min_value=1, max_value=len(df_f), value=1, key="fer_rem_idx")
                if st.button("Remover linha", key="fer_rem_btn"):
                    r = df_f.iloc[int(rem_idx)-1]
                    delete_ferias_row(setor, r["Chapa"], r["Início"], r["Fim"])
                    st.success("Removido!")
                    st.rerun()
            else:
                st.info("Sem férias.")

    # ------------------------------------------------------
    # ABA 5: Excel
    # ------------------------------------------------------
    with abas[4]:
        st.subheader("Excel modelo RH (separado por subgrupo)")
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

                    border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                    top=Side(style="thin"), bottom=Side(style="thin"))
                    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

                    ch0 = list(hist_db.keys())[0]
                    df_ref = hist_db[ch0]
                    total_dias = len(df_ref)

                    ws.cell(1, 1, "COLABORADOR").fill = fill_header
                    ws.cell(1, 1).font = font_header
                    ws.cell(1, 1).alignment = center
                    ws.cell(1, 1).border = border
                    ws.cell(2, 1, "").fill = fill_header
                    ws.cell(2, 1).alignment = center
                    ws.cell(2, 1).border = border

                    for i in range(total_dias):
                        dia_num = df_ref.iloc[i]["Data"].day
                        dia_sem = df_ref.iloc[i]["Dia"]
                        c1 = ws.cell(1, i + 2, dia_num)
                        c2 = ws.cell(2, i + 2, dia_sem)

                        if dia_sem == "dom":
                            c1.fill = fill_dom; c2.fill = fill_dom
                            c1.font = font_dom; c2.font = font_dom
                        else:
                            c1.fill = fill_header; c2.fill = fill_header
                            c1.font = font_header; c2.font = font_header

                        c1.alignment = center; c2.alignment = center
                        c1.border = border; c2.border = border
                        ws.column_dimensions[get_column_letter(i + 2)].width = 7

                    ws.column_dimensions["A"].width = 36

                    subgrupo_map = {}
                    for ch in hist_db.keys():
                        sg = (colab_by.get(ch, {}).get("Subgrupo", "") or "").strip() or "SEM SUBGRUPO"
                        subgrupo_map.setdefault(sg, []).append(ch)

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

                        chapas_sg = sorted(subgrupo_map[sg], key=lambda ch: colab_by.get(ch, {}).get("Nome", ch))
                        for ch in chapas_sg:
                            df_f = hist_db[ch]
                            nome = colab_by.get(ch, {}).get("Nome", ch)

                            c_nome = ws.cell(row_idx, 1, f"{nome}\nCHAPA: {ch}")
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

                                cell1.alignment = center; cell2.alignment = center
                                cell1.border = border; cell2.border = border

                                if status == "Férias":
                                    cell1.fill = fill_ferias; cell2.fill = fill_ferias
                                elif status == "Folga":
                                    if dia_sem == "dom":
                                        cell1.fill = fill_dom; cell2.fill = fill_dom
                                    else:
                                        cell1.fill = fill_folga; cell2.fill = fill_folga

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
    # ABA 6: Admin
    # ------------------------------------------------------
    if is_admin_area:
        with abas[5]:
            st.subheader("🔒 Admin do Sistema (somente ADMIN)")
            dfu = admin_list_users()
            st.dataframe(dfu, use_container_width=True)

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
