# main.py
# =========================================================
# ESCALA 5x2 OFICIAL (Streamlit + SQLite)
# Abas completas: Colaboradores | Gerar Escala | Férias | Excel | Admin
# Regras principais:
# - 5x2 (2 folgas por semana Seg->Dom)
# - Máx 5 dias seguidos trabalhando
# - Domingo 1x1 por SUBGRUPO (desde o 1º domingo do mês)
# - Sábado só pode ser folga se colaborador estiver com "Folga no Sábado" marcado
# - Interstício 11h10 (ajusta entrada se necessário)
# - Férias entram automaticamente na escala
# - Retorno de férias: 1ª semana "livre" (não força 2 folgas), mas mantém Domingo 1x1
# - Balanceamento: tenta distribuir folgas de forma mais uniforme (por subgrupo)
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
import os
from typing import Dict, List, Tuple, Optional

from openpyxl.styles import PatternFill, Alignment, Border, Side, Font
from openpyxl.utils import get_column_letter

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Escala 5x2 Oficial", layout="wide")

DB_PATH = "escala.db"

INTERSTICIO_MIN = timedelta(hours=11, minutes=10)
DURACAO_JORNADA = timedelta(hours=9, minutes=58)  # 1h10 almoço já embutido na sua jornada padrão anterior
PREF_EVITAR_PENALTY = 1000

D_PT = {
    "Monday": "seg",
    "Tuesday": "ter",
    "Wednesday": "qua",
    "Thursday": "qui",
    "Friday": "sex",
    "Saturday": "sáb",
    "Sunday": "dom",
}

STATUS_TRAB = "Trabalho"
STATUS_FOLGA = "Folga"
STATUS_FERIAS = "FÉRIAS"

AS_SISTEMA = {
    "ESCALA": "5x2 (5 dias de trabalho, 2 folgas semanais)",
    "INTERSTICIO": "Mínimo de 11h 10min de descanso entre jornadas",
    "DOMINGOS": "Regra 1x1 (Alternado por funcionário do mesmo setor/subgrupo)",
    "RODIZIO_SABADO": "Sábado só pode ser folga se colaborador tiver marcado 'Folga no Sábado'",
    "BALANCEAMENTO": "Tenta reduzir concentração de folgas no mesmo dia (por subgrupo)",
    "LIMITE_CONSECUTIVO": "Máximo de 5 dias seguidos de trabalho",
    "FERIAS": "Férias lançadas automaticamente na escala",
}

# =========================================================
# DB helpers
# =========================================================
def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    return [r[1] for r in rows]

def db_init_schema():
    con = db_conn()
    cur = con.cursor()

    # setores
    cur.execute("""
    CREATE TABLE IF NOT EXISTS setores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )
    """)

    # usuários do sistema (login)
    cur.execute("""
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS colaboradores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        subgrupo TEXT DEFAULT '',
        entrada TEXT DEFAULT '06:00',
        folga_sab INTEGER DEFAULT 0,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT NOT NULL,
        UNIQUE(setor, chapa)
    )
    """)

    # subgrupos por setor
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subgrupos_setor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        nome TEXT NOT NULL,
        UNIQUE(setor, nome)
    )
    """)

    # preferências por subgrupo (evitar folga em dias marcados)
    cur.execute("""
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ferias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL
    )
    """)

    # escala do mês (resultado final)
    cur.execute("""
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

    # estado do mês anterior (continuidade)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS estado_mes_anterior (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        consec_trab_final INTEGER NOT NULL,
        ultima_saida TEXT NOT NULL,
        ultimo_domingo_status TEXT,
        retorno_ferias_ate TEXT,
        UNIQUE(setor, chapa, ano, mes)
    )
    """)

    # overrides / ajustes manuais (por mês)
    cur.execute("""
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
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("GERAL",))
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("ADMIN",))
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

def db_migrate():
    db_init_schema()
    con = db_conn()
    cur = con.cursor()
    try:
        cols = table_columns(con, "estado_mes_anterior")
        if "retorno_ferias_ate" not in cols:
            cur.execute("ALTER TABLE estado_mes_anterior ADD COLUMN retorno_ferias_ate TEXT")
        if "ultimo_domingo_status" not in cols:
            cur.execute("ALTER TABLE estado_mes_anterior ADD COLUMN ultimo_domingo_status TEXT")
        con.commit()
    except Exception:
        pass
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
# ADMIN users
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

def admin_update_user(user_id: int, nome: str, setor: str, chapa: str, is_admin: bool, is_lider: bool):
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", (setor,))
    cur.execute("""
        UPDATE usuarios_sistema
        SET nome=?, setor=?, chapa=?, is_admin=?, is_lider=?
        WHERE id=?
    """, (nome, setor, chapa, 1 if is_admin else 0, 1 if is_lider else 0, int(user_id)))
    con.commit()
    con.close()

def admin_reset_user_password(user_id: int, nova_senha: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT setor, chapa FROM usuarios_sistema WHERE id=?", (int(user_id),))
    row = cur.fetchone()
    con.close()
    if not row:
        return False
    setor, chapa = row
    update_password(setor, chapa, nova_senha)
    return True

def admin_delete_user(user_id: int):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM usuarios_sistema WHERE id=?", (int(user_id),))
    con.commit()
    con.close()

# =========================================================
# Colaboradores + Subgrupos + Preferências
# =========================================================
def create_colaborador(nome: str, setor: str, chapa: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO colaboradores(nome, setor, chapa, criado_em)
        VALUES (?, ?, ?, ?)
    """, (nome, setor, chapa, datetime.now().isoformat()))
    con.commit()
    con.close()

def load_colaboradores_setor(setor: str):
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT nome, chapa, subgrupo, entrada, folga_sab, ativo
        FROM colaboradores
        WHERE setor=?
        ORDER BY nome ASC
    """, con, params=(setor,))
    con.close()
    if df.empty:
        return []
    out = []
    for _, r in df.iterrows():
        out.append({
            "Nome": str(r["nome"]),
            "Chapa": str(r["chapa"]),
            "Subgrupo": (str(r["subgrupo"]) if r["subgrupo"] is not None else "").strip() or "SEM SUBGRUPO",
            "Entrada": (str(r["entrada"]) if r["entrada"] is not None else "06:00").strip(),
            "Folga_Sab": bool(int(r["folga_sab"])) if pd.notna(r["folga_sab"]) else False,
            "Ativo": bool(int(r["ativo"])) if pd.notna(r["ativo"]) else True,
            "Setor": setor
        })
    return out

def update_colaborador(setor: str, chapa: str, nome: str, subgrupo: str, entrada: str, folga_sab: bool, ativo: bool):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        UPDATE colaboradores
        SET nome=?, subgrupo=?, entrada=?, folga_sab=?, ativo=?
        WHERE setor=? AND chapa=?
    """, (nome, subgrupo, entrada, 1 if folga_sab else 0, 1 if ativo else 0, setor, chapa))
    con.commit()
    con.close()

def list_subgrupos(setor: str):
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT nome FROM subgrupos_setor WHERE setor=?
        ORDER BY nome ASC
    """, con, params=(setor,))
    con.close()
    return df["nome"].tolist() if not df.empty else []

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
    cur.execute("UPDATE colaboradores SET subgrupo='SEM SUBGRUPO' WHERE setor=? AND subgrupo=?", (setor, nome))
    con.commit()
    con.close()

def get_subgrupo_regras(setor: str, subgrupo: str):
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT evitar_seg, evitar_ter, evitar_qua, evitar_qui, evitar_sex, evitar_sab
        FROM subgrupo_regras
        WHERE setor=? AND subgrupo=?
        LIMIT 1
    """, con, params=(setor, subgrupo))
    con.close()
    if df.empty:
        return {"seg": 0, "ter": 0, "qua": 0, "qui": 0, "sex": 0, "sáb": 0}
    r = df.iloc[0].to_dict()
    return {"seg": int(r["evitar_seg"]), "ter": int(r["evitar_ter"]), "qua": int(r["evitar_qua"]),
            "qui": int(r["evitar_qui"]), "sex": int(r["evitar_sex"]), "sáb": int(r["evitar_sab"])}

def set_subgrupo_regras(setor: str, subgrupo: str, regras: dict):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO subgrupo_regras(setor, subgrupo, evitar_seg, evitar_ter, evitar_qua, evitar_qui, evitar_sex, evitar_sab)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (setor, subgrupo,
          int(regras.get("seg", 0)), int(regras.get("ter", 0)), int(regras.get("qua", 0)),
          int(regras.get("qui", 0)), int(regras.get("sex", 0)), int(regras.get("sáb", 0))))
    con.commit()
    con.close()

# =========================================================
# Férias
# =========================================================
def add_ferias(setor: str, chapa: str, inicio: date, fim: date):
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT INTO ferias(setor, chapa, inicio, fim) VALUES (?, ?, ?, ?)",
                (setor, chapa, inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")))
    con.commit()
    con.close()

def list_ferias(setor: str):
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT chapa, inicio, fim
        FROM ferias
        WHERE setor=?
        ORDER BY date(inicio) ASC
    """, con, params=(setor,))
    con.close()
    return df

def delete_ferias_row(setor: str, chapa: str, inicio: str, fim: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        DELETE FROM ferias
        WHERE setor=? AND chapa=? AND inicio=? AND fim=?
    """, (setor, chapa, inicio, fim))
    con.commit()
    con.close()

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

def ferias_last_ret_ate(setor: str, chapa: str) -> Optional[date]:
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT fim
        FROM ferias
        WHERE setor=? AND chapa=?
        ORDER BY date(fim) DESC
        LIMIT 1
    """, (setor, chapa))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    fim = datetime.strptime(row[0], "%Y-%m-%d").date()
    return fim + timedelta(days=7)

# =========================================================
# Escala persistência + Overrides
# =========================================================
def clear_escala_mes(setor: str, ano: int, mes: int):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM escala_mes WHERE setor=? AND ano=? AND mes=?", (setor, ano, mes))
    con.commit()
    con.close()

def save_escala_mes(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame]):
    con = db_conn()
    cur = con.cursor()
    for chapa, df in escala.items():
        for _, r in df.iterrows():
            cur.execute("""
                INSERT OR REPLACE INTO escala_mes(setor, ano, mes, chapa, dia, data, dia_sem, status, h_entrada, h_saida)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (setor, ano, mes, chapa,
                  int(r["DiaMes"]),
                  r["Data"].strftime("%Y-%m-%d"),
                  r["DiaSem"],
                  r["Status"],
                  (r.get("Entrada", "") or ""),
                  (r.get("Saida", "") or "")))
    con.commit()
    con.close()

def load_escala_mes(setor: str, ano: int, mes: int) -> Dict[str, pd.DataFrame]:
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT chapa, dia, data, dia_sem, status, h_entrada, h_saida
        FROM escala_mes
        WHERE setor=? AND ano=? AND mes=?
        ORDER BY chapa, dia
    """, con, params=(setor, ano, mes))
    con.close()
    if df.empty:
        return {}
    out = {}
    for chapa, g in df.groupby("chapa"):
        g2 = g.copy()
        g2["Data"] = pd.to_datetime(g2["data"]).dt.date
        g2["DiaMes"] = g2["dia"].astype(int)
        g2["DiaSem"] = g2["dia_sem"].astype(str)
        g2["Status"] = g2["status"].astype(str)
        g2["Entrada"] = g2["h_entrada"].fillna("").astype(str)
        g2["Saida"] = g2["h_saida"].fillna("").astype(str)
        out[chapa] = g2[["Data", "DiaMes", "DiaSem", "Status", "Entrada", "Saida"]].reset_index(drop=True)
    return out

def save_estado_mes(setor: str, ano: int, mes: int, estado: Dict[str, dict]):
    con = db_conn()
    cur = con.cursor()
    for chapa, stt in estado.items():
        cur.execute("""
            INSERT OR REPLACE INTO estado_mes_anterior(setor, chapa, ano, mes, consec_trab_final, ultima_saida, ultimo_domingo_status, retorno_ferias_ate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (setor, chapa, ano, mes,
              int(stt.get("consec_trab_final", 0)),
              stt.get("ultima_saida", "00:00"),
              stt.get("ultimo_domingo_status", ""),
              stt.get("retorno_ferias_ate", "")))
    con.commit()
    con.close()

def load_estado_mes(setor: str, ano: int, mes: int) -> Dict[str, dict]:
    con = db_conn()
    cols = table_columns(con, "estado_mes_anterior")
    if "retorno_ferias_ate" in cols:
        df = pd.read_sql_query("""
            SELECT chapa, consec_trab_final, ultima_saida, ultimo_domingo_status, retorno_ferias_ate
            FROM estado_mes_anterior
            WHERE setor=? AND ano=? AND mes=?
        """, con, params=(setor, ano, mes))
    else:
        df = pd.read_sql_query("""
            SELECT chapa, consec_trab_final, ultima_saida, ultimo_domingo_status
            FROM estado_mes_anterior
            WHERE setor=? AND ano=? AND mes=?
        """, con, params=(setor, ano, mes))
        df["retorno_ferias_ate"] = ""
    con.close()

    out = {}
    for _, r in df.iterrows():
        out[str(r["chapa"])] = {
            "consec_trab_final": int(r["consec_trab_final"]),
            "ultima_saida": str(r["ultima_saida"]),
            "ultimo_domingo_status": str(r.get("ultimo_domingo_status", "") or ""),
            "retorno_ferias_ate": str(r.get("retorno_ferias_ate", "") or ""),
        }
    return out

def load_last_month_state(setor: str, ano: int, mes: int) -> Dict[str, dict]:
    prev_year = ano
    prev_month = mes - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    return load_estado_mes(setor, prev_year, prev_month)

def set_override(setor: str, ano: int, mes: int, chapa: str, dia: int, campo: str, valor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO overrides(setor, ano, mes, chapa, dia, campo, valor)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (setor, ano, mes, chapa, int(dia), campo, str(valor)))
    con.commit()
    con.close()

def delete_override(setor: str, ano: int, mes: int, chapa: str, dia: int, campo: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        DELETE FROM overrides
        WHERE setor=? AND ano=? AND mes=? AND chapa=? AND dia=? AND campo=?
    """, (setor, ano, mes, chapa, int(dia), campo))
    con.commit()
    con.close()

def load_overrides(setor: str, ano: int, mes: int) -> pd.DataFrame:
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT chapa, dia, campo, valor
        FROM overrides
        WHERE setor=? AND ano=? AND mes=?
    """, con, params=(setor, ano, mes))
    con.close()
    return df

# =========================================================
# Regras de jornada + datas
# =========================================================
def calcular_entrada_segura(saida_ant: str, ent_padrao: str) -> str:
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0:
            diff += 24
        if diff < 11:
            return (s + INTERSTICIO_MIN).strftime(fmt)
    except Exception:
        pass
    return ent_padrao

def add_hours_str(hhmm: str, td: timedelta) -> str:
    fmt = "%H:%M"
    t = datetime.strptime(hhmm, fmt)
    return (t + td).strftime(fmt)

def month_dates(ano: int, mes: int) -> List[date]:
    ndays = calendar.monthrange(ano, mes)[1]
    return [date(ano, mes, d) for d in range(1, ndays + 1)]

def day_sem_pt(d: date) -> str:
    return D_PT[d.strftime("%A")]

def week_index_seg_dom(d: date) -> int:
    first = date(d.year, d.month, 1)
    offset = first.weekday()  # Monday=0
    monday0 = first - timedelta(days=offset)
    return ((d - monday0).days // 7)

def group_by_subgrupo(colabs: List[dict]) -> Dict[str, List[dict]]:
    groups = {}
    for c in colabs:
        sg = (c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO"
        groups.setdefault(sg, []).append(c)
    return groups

def build_preferencias_map(setor: str, subgrupo: str) -> Dict[str, int]:
    reg = get_subgrupo_regras(setor, subgrupo)
    return {k: int(reg.get(k, 0)) for k in ["seg", "ter", "qua", "qui", "sex", "sáb"]}

def choose_balanced_day(candidates: List[int], day_counts: Dict[int, int], penalties: Dict[int, int]) -> Optional[int]:
    if not candidates:
        return None
    best = None
    best_score = None
    random.shuffle(candidates)
    for idx in candidates:
        score = day_counts.get(idx, 0) + penalties.get(idx, 0)
        if best_score is None or score < best_score:
            best_score = score
            best = idx
    return best

# =========================================================
# Domingo 1x1 helper (para aplicar após ajuste manual)
# =========================================================
def apply_sunday_alternation_for_employee(df: pd.DataFrame, start_sunday_day: int):
    """
    df tem colunas: DiaMes, DiaSem, Status
    Quando usuário muda 1 domingo, recalculamos os próximos domingos alternando:
    se no domingo escolhido ficou Folga => próximo domingo Trabalho => próximo Folga...
    """
    sundays_idx = df.index[df["DiaSem"] == "dom"].tolist()
    if not sundays_idx:
        return df

    # achar o sunday mais próximo >= start_sunday_day
    start_idx = None
    for i in sundays_idx:
        if int(df.loc[i, "DiaMes"]) >= int(start_sunday_day):
            start_idx = i
            break
    if start_idx is None:
        return df

    # status base
    base_status = df.loc[start_idx, "Status"]
    if base_status == STATUS_FERIAS:
        # se por acaso é férias, não altera nada
        return df

    # alterna a partir dele
    toggle = base_status
    started = False
    for i in sundays_idx:
        dia_mes = int(df.loc[i, "DiaMes"])
        if dia_mes < int(start_sunday_day):
            continue
        if df.loc[i, "Status"] == STATUS_FERIAS:
            continue
        if not started:
            toggle = df.loc[i, "Status"]
            started = True
        else:
            toggle = STATUS_TRAB if toggle == STATUS_FOLGA else STATUS_FOLGA
            df.loc[i, "Status"] = toggle

    return df

# =========================================================
# GERADOR DE ESCALA
# =========================================================
def generate_schedule_setor(setor: str, ano: int, mes: int, seed: int = 0) -> Tuple[Dict[str, pd.DataFrame], Dict[str, dict]]:
    random.seed(seed)

    colabs = [c for c in load_colaboradores_setor(setor) if c.get("Ativo", True)]
    if not colabs:
        return {}, {}

    dates = month_dates(ano, mes)
    ndays = len(dates)

    prev_state = load_last_month_state(setor, ano, mes)
    groups = group_by_subgrupo(colabs)

    base: Dict[str, pd.DataFrame] = {}
    for c in colabs:
        df = pd.DataFrame({
            "Data": dates,
            "DiaMes": [d.day for d in dates],
            "DiaSem": [day_sem_pt(d) for d in dates],
            "Status": [STATUS_TRAB] * ndays,
            "Entrada": [""] * ndays,
            "Saida": [""] * ndays,
        })
        base[c["Chapa"]] = df

    # aplicar férias
    for c in colabs:
        chapa = c["Chapa"]
        df = base[chapa]
        for i, d in enumerate(dates):
            if is_de_ferias(setor, chapa, d):
                df.loc[i, "Status"] = STATUS_FERIAS
        base[chapa] = df

    # Domingo 1x1 por subgrupo (desde 1º domingo)
    for sg, members in groups.items():
        members_sorted = sorted(members, key=lambda x: x["Chapa"])
        if not members_sorted:
            continue

        domingos = [i for i, d in enumerate(dates) if d.weekday() == 6]
        if not domingos:
            continue

        # metade folga, metade trabalha (arredonda)
        k = max(1, len(members_sorted) // 2)
        pointer = 0

        for idx_dom in domingos:
            # seleciona quem folga nesse domingo
            folgam = []
            for j in range(k):
                folgam.append(members_sorted[(pointer + j) % len(members_sorted)]["Chapa"])
            pointer = (pointer + k) % len(members_sorted)

            # aplica
            for m in members_sorted:
                chapa = m["Chapa"]
                df = base[chapa]
                if df.loc[idx_dom, "Status"] == STATUS_FERIAS:
                    continue
                df.loc[idx_dom, "Status"] = STATUS_FOLGA if chapa in folgam else STATUS_TRAB
                base[chapa] = df

    # 5x2 por semana Seg->Dom, com balanceamento por subgrupo
    for sg, members in groups.items():
        day_counts = {i: 0 for i in range(ndays)}
        pref = build_preferencias_map(setor, sg)

        penalties = {}
        for i, d in enumerate(dates):
            ds = day_sem_pt(d)
            penalties[i] = PREF_EVITAR_PENALTY if pref.get(ds, 0) == 1 else 0

        for m in members:
            chapa = m["Chapa"]
            folga_sab_ok = bool(m["Folga_Sab"])
            entrada_padrao = m["Entrada"] or "06:00"
            df = base[chapa]

            prev = prev_state.get(chapa, {})
            consec = int(prev.get("consec_trab_final", 0) or 0)
            ret_ate = ferias_last_ret_ate(setor, chapa)

            weeks = {}
            for i, d in enumerate(dates):
                w = week_index_seg_dom(d)
                weeks.setdefault(w, []).append(i)

            for w, idxs in weeks.items():
                week_dates = [dates[i] for i in idxs]
                in_free_week = False
                if ret_ate is not None and any(d <= ret_ate for d in week_dates):
                    in_free_week = True

                folgas_week = int((df.loc[idxs, "Status"] == STATUS_FOLGA).sum())

                idx_dom = None
                for i in idxs:
                    if dates[i].weekday() == 6:
                        idx_dom = i
                        break

                worked_sunday = False
                sunday_is_folga = False
                if idx_dom is not None and df.loc[idx_dom, "Status"] != STATUS_FERIAS:
                    if df.loc[idx_dom, "Status"] == STATUS_TRAB:
                        worked_sunday = True
                    elif df.loc[idx_dom, "Status"] == STATUS_FOLGA:
                        sunday_is_folga = True

                def is_allowed_folga(i: int) -> bool:
                    if df.loc[i, "Status"] in (STATUS_FERIAS, STATUS_FOLGA):
                        return False
                    ds = df.loc[i, "DiaSem"]
                    if ds == "sáb" and not folga_sab_ok:
                        return False
                    if i > 0 and df.loc[i-1, "Status"] == STATUS_FOLGA:
                        return False
                    if i < ndays-1 and df.loc[i+1, "Status"] == STATUS_FOLGA:
                        return False
                    return True

                # quebra se tiver 5 seguidos
                for i in idxs:
                    if df.loc[i, "Status"] in (STATUS_FERIAS, STATUS_FOLGA):
                        consec = 0
                        continue
                    if consec >= 5 and is_allowed_folga(i):
                        df.loc[i, "Status"] = STATUS_FOLGA
                        day_counts[i] += 1
                        folgas_week += 1
                        consec = 0
                    else:
                        consec += 1

                target_folgas = 2 if not in_free_week else max(1, folgas_week)

                # regra: se trabalhou domingo, precisa ter 1 folga seg-sex
                seg_sex = [i for i in idxs if df.loc[i, "DiaSem"] in ("seg", "ter", "qua", "qui", "sex")]

                def ensure_one_folga_seg_sex():
                    nonlocal folgas_week
                    if any(df.loc[i, "Status"] == STATUS_FOLGA for i in seg_sex):
                        return
                    poss = [i for i in seg_sex if is_allowed_folga(i)]
                    chosen = choose_balanced_day(poss, day_counts, penalties)
                    if chosen is not None:
                        df.loc[chosen, "Status"] = STATUS_FOLGA
                        day_counts[chosen] += 1
                        folgas_week += 1

                if (worked_sunday or sunday_is_folga) and seg_sex:
                    ensure_one_folga_seg_sex()

                # completar até target
                while folgas_week < target_folgas:
                    poss = [i for i in idxs if is_allowed_folga(i)]
                    if idx_dom is not None:
                        poss = [i for i in poss if i != idx_dom]
                    chosen = choose_balanced_day(poss, day_counts, penalties)
                    if chosen is None:
                        break
                    df.loc[chosen, "Status"] = STATUS_FOLGA
                    day_counts[chosen] += 1
                    folgas_week += 1

            base[chapa] = df

    # horários + interstício
    for c in colabs:
        chapa = c["Chapa"]
        entrada_padrao = c["Entrada"] or "06:00"
        df = base[chapa]
        last_saida = (prev_state.get(chapa, {}) or {}).get("ultima_saida", "") or ""

        for i in range(ndays):
            status = df.loc[i, "Status"]
            if status in (STATUS_FOLGA, STATUS_FERIAS):
                df.loc[i, "Entrada"] = ""
                df.loc[i, "Saida"] = ""
                last_saida = ""
                continue

            ent = entrada_padrao
            if i == 0 and last_saida:
                ent = calcular_entrada_segura(last_saida, entrada_padrao)
            elif i > 0 and df.loc[i-1, "Saida"]:
                ent = calcular_entrada_segura(df.loc[i-1, "Saida"], entrada_padrao)

            df.loc[i, "Entrada"] = ent
            df.loc[i, "Saida"] = add_hours_str(ent, DURACAO_JORNADA)

        base[chapa] = df

    # construir estado final
    estado_out: Dict[str, dict] = {}
    for c in colabs:
        chapa = c["Chapa"]
        df = base[chapa]
        consec = 0
        last_saida = ""
        ultimo_domingo_status = ""
        for i in range(ndays):
            if df.loc[i, "Status"] in (STATUS_FOLGA, STATUS_FERIAS):
                consec = 0
                last_saida = ""
            else:
                consec += 1
                last_saida = df.loc[i, "Saida"] or last_saida
            if df.loc[i, "DiaSem"] == "dom":
                ultimo_domingo_status = df.loc[i, "Status"]
        ret_ate = ferias_last_ret_ate(setor, chapa)
        estado_out[chapa] = {
            "consec_trab_final": int(consec),
            "ultima_saida": last_saida or "00:00",
            "ultimo_domingo_status": ultimo_domingo_status,
            "retorno_ferias_ate": ret_ate.strftime("%Y-%m-%d") if ret_ate else "",
        }

    return base, estado_out

# =========================================================
# Aplicar overrides no dataframe da escala
# =========================================================
def apply_overrides_to_escala(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    ov = load_overrides(setor, ano, mes)
    if ov.empty:
        return escala
    for _, r in ov.iterrows():
        chapa = str(r["chapa"])
        dia = int(r["dia"])
        campo = str(r["campo"])
        valor = str(r["valor"])

        if chapa not in escala:
            continue
        df = escala[chapa]
        idx = df.index[df["DiaMes"] == dia].tolist()
        if not idx:
            continue
        i = idx[0]
        if campo == "status":
            df.loc[i, "Status"] = valor
            # se mexeu em domingo, alterna próximos domingos
            if df.loc[i, "DiaSem"] == "dom":
                df = apply_sunday_alternation_for_employee(df, start_sunday_day=dia)
        elif campo == "h_entrada":
            df.loc[i, "Entrada"] = valor
            if df.loc[i, "Status"] == STATUS_TRAB:
                df.loc[i, "Saida"] = add_hours_str(valor, DURACAO_JORNADA)
        elif campo == "h_saida":
            df.loc[i, "Saida"] = valor
        escala[chapa] = df
    return escala

# =========================================================
# Calendário visual estilo RH (tabela)
# =========================================================
def build_calendar_table(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    colabs = [c for c in load_colaboradores_setor(setor) if c.get("Ativo", True)]
    if not colabs:
        return pd.DataFrame()

    info = {c["Chapa"]: c for c in colabs}
    dates = month_dates(ano, mes)
    ndays = len(dates)

    cols = ["Nome", "Chapa", "Subgrupo"] + [str(d.day) for d in dates]
    rows = []
    for chapa, df in escala.items():
        if chapa not in info:
            continue
        nome = info[chapa]["Nome"]
        sg = info[chapa]["Subgrupo"]
        row = [nome, chapa, sg]
        for i in range(ndays):
            stt = df.loc[i, "Status"]
            if stt == STATUS_FOLGA:
                row.append("F")
            elif stt == STATUS_FERIAS:
                row.append("FER")
            else:
                row.append(df.loc[i, "Entrada"] or "")
        rows.append(row)

    out = pd.DataFrame(rows, columns=cols)
    out = out.sort_values(by=["Subgrupo", "Nome"]).reset_index(drop=True)
    return out

def build_folgas_por_dia(escala: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    if not escala:
        return pd.DataFrame()
    any_df = next(iter(escala.values()))
    ndays = len(any_df)
    res = []
    for i in range(ndays):
        dia = int(any_df.loc[i, "DiaMes"])
        ds = any_df.loc[i, "DiaSem"]
        folgas = 0
        ferias = 0
        for _, df in escala.items():
            if df.loc[i, "Status"] == STATUS_FOLGA:
                folgas += 1
            if df.loc[i, "Status"] == STATUS_FERIAS:
                ferias += 1
        res.append({"Dia": dia, "DiaSem": ds, "Folgas": folgas, "Férias": ferias})
    return pd.DataFrame(res)

# =========================================================
# Excel RH
# =========================================================
def build_excel_rh(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame]) -> bytes:
    colabs = [c for c in load_colaboradores_setor(setor) if c.get("Ativo", True)]
    if not colabs or not escala:
        return b""

    info = {c["Chapa"]: c for c in colabs}
    by_sg = {}
    for c in colabs:
        sg = (c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO"
        by_sg.setdefault(sg, []).append(c["Chapa"])
    for sg in by_sg:
        by_sg[sg] = sorted(by_sg[sg], key=lambda ch: info[ch]["Nome"])

    dates = month_dates(ano, mes)
    ndays = len(dates)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        wb = writer.book
        ws = wb.create_sheet("Escala Mensal", 0)

        blue = PatternFill(start_color="1F4E79", end_color="1F4E79", patternType="solid")
        green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", patternType="solid")
        green2 = PatternFill(start_color="A9D08E", end_color="A9D08E", patternType="solid")
        sunday = PatternFill(start_color="BDD7EE", end_color="BDD7EE", patternType="solid")
        header_font = Font(color="FFFFFF", bold=True)
        border = Border(left=Side(style="thin"), right=Side(style="thin"),
                        top=Side(style="thin"), bottom=Side(style="thin"))
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.cell(1, 1, f"SETOR: {setor}  |  MÊS: {mes:02d}/{ano}").fill = blue
        ws.cell(1, 1).font = header_font
        ws.cell(1, 1).alignment = Alignment(horizontal="left", vertical="center")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ndays + 3)

        ws.cell(2, 1, "COLABORADOR").fill = blue
        ws.cell(2, 2, "CHAPA").fill = blue
        ws.cell(2, 3, "SUBGRUPO").fill = blue
        for c in (ws.cell(2, 1), ws.cell(2, 2), ws.cell(2, 3)):
            c.font = header_font
            c.alignment = center
            c.border = border

        for i, d in enumerate(dates):
            col = i + 4
            ws.cell(2, col, d.day).fill = blue
            ws.cell(2, col).font = header_font
            ws.cell(2, col).alignment = center
            ws.cell(2, col).border = border

            ws.cell(3, col, day_sem_pt(d)).alignment = center
            ws.cell(3, col).border = border
            if day_sem_pt(d) == "dom":
                ws.cell(3, col).fill = sunday

        ws.cell(3, 1, "").fill = blue
        ws.cell(3, 2, "").fill = blue
        ws.cell(3, 3, "").fill = blue
        for c in (ws.cell(3, 1), ws.cell(3, 2), ws.cell(3, 3)):
            c.border = border

        row = 4
        for sg, chapas in by_sg.items():
            ws.cell(row, 1, f"SUBGRUPO: {sg}").fill = blue
            ws.cell(row, 1).font = header_font
            ws.cell(row, 1).alignment = Alignment(horizontal="left", vertical="center")
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ndays + 3)
            row += 1

            for chapa in chapas:
                if chapa not in escala:
                    continue
                cinfo = info[chapa]
                df = escala[chapa]

                ws.cell(row, 1, cinfo["Nome"]).alignment = center
                ws.cell(row, 2, chapa).alignment = center
                ws.cell(row, 3, cinfo["Subgrupo"]).alignment = center

                for cc in (ws.cell(row, 1), ws.cell(row, 2), ws.cell(row, 3)):
                    cc.border = border

                for i in range(ndays):
                    col = i + 4
                    status = df.loc[i, "Status"]
                    ent = df.loc[i, "Entrada"]
                    c = ws.cell(row, col, "F" if status == STATUS_FOLGA else ("FER" if status == STATUS_FERIAS else ent))
                    c.alignment = center
                    c.border = border
                    if status == STATUS_FOLGA:
                        c.fill = green
                    elif status == STATUS_FERIAS:
                        c.fill = green2
                    elif df.loc[i, "DiaSem"] == "dom":
                        c.fill = sunday

                row += 1
            row += 1

        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 18
        for i in range(4, ndays + 4):
            ws.column_dimensions[get_column_letter(i)].width = 6

        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

    return output.getvalue()

# =========================================================
# UI - Reset DB
# =========================================================
def reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db_migrate()

# =========================================================
# PAGES
# =========================================================
db_migrate()

if "auth" not in st.session_state:
    st.session_state["auth"] = None
if "escala_cache" not in st.session_state:
    st.session_state["escala_cache"] = {}
if "escala_ano" not in st.session_state:
    st.session_state["escala_ano"] = datetime.now().year
if "escala_mes" not in st.session_state:
    st.session_state["escala_mes"] = datetime.now().month

def page_login():
    st.title("🔐 Login por Setor (Usuário/Líder/Admin)")
    tab_login, tab_cadastrar, tab_esqueci = st.tabs(["Entrar", "Cadastrar Usuário", "Esqueci a senha"])

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
        st.subheader("Cadastrar usuário do sistema")
        nome = st.text_input("Nome:", key="cl_nome")
        setor = st.text_input("Setor:", key="cl_setor").strip().upper()
        chapa = st.text_input("Chapa:", key="cl_chapa")
        senha = st.text_input("Senha:", type="password", key="cl_senha")
        senha2 = st.text_input("Confirmar senha:", type="password", key="cl_senha2")
        is_admin = st.checkbox("Admin?", value=False, key="cl_admin")
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
        chapa = st.text_input("Sua chapa:", key="fp_chapa")
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
    st.sidebar.write(f"**Nome:** {auth.get('nome','-')}")
    st.sidebar.write(f"**Setor:** {setor}")
    st.sidebar.write(f"**Chapa:** {auth.get('chapa','-')}")
    st.sidebar.write(f"**Perfil:** {'ADMIN' if auth.get('is_admin', False) else ('LÍDER' if auth.get('is_lider', False) else 'USUÁRIO')}")

    if st.sidebar.button("Sair", key="logout_btn"):
        st.session_state["auth"] = None
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption("📌 Regras do Sistema")
    for k, v in AS_SISTEMA.items():
        st.sidebar.write(f"**{k}:** {v}")

    if auth.get("is_admin", False) and setor == "ADMIN":
        st.sidebar.markdown("---")
        if st.sidebar.button("🧹 Resetar banco (apaga tudo)", key="reset_db_btn"):
            reset_db()
            st.session_state["auth"] = None
            st.session_state["escala_cache"] = {}
            st.success("Banco resetado. Faça login novamente.")
            st.rerun()

    st.title(f"📌 Sistema — Setor: {setor}")

    # Abas que você pediu
    aba1, aba2, aba3, aba4, aba5 = st.tabs(["👥 Colaboradores", "🚀 Gerar Escala", "🏖️ Férias", "📥 Excel", "🔒 Admin"])

    # =========================================================
    # 👥 Colaboradores
    # =========================================================
    with aba1:
        st.subheader("👥 Colaboradores (setor do login)")

        colabs = load_colaboradores_setor(setor)
        df_col = pd.DataFrame(colabs) if colabs else pd.DataFrame(columns=["Nome","Chapa","Subgrupo","Entrada","Folga_Sab","Ativo"])
        st.dataframe(df_col, use_container_width=True)

        st.markdown("### ➕ Cadastrar novo colaborador (SEM senha)")
        c1, c2 = st.columns(2)
        nome_n = c1.text_input("Nome", key="col_nome_add")
        chapa_n = c2.text_input("Chapa", key="col_chapa_add")
        if st.button("Cadastrar colaborador", key="col_add_btn"):
            if not nome_n or not chapa_n:
                st.error("Preencha Nome e Chapa.")
            else:
                create_colaborador(nome_n.strip(), setor, chapa_n.strip())
                st.success("Cadastrado!")
                st.rerun()

        st.markdown("---")
        st.markdown("### ✏️ Editar colaborador")
        if not df_col.empty:
            chapas = df_col["Chapa"].tolist()
            chapa_sel = st.selectbox("Selecionar colaborador (chapa)", chapas, key="col_edit_sel")
            row = df_col[df_col["Chapa"] == chapa_sel].iloc[0]

            sg_list = ["SEM SUBGRUPO"] + list_subgrupos(setor)
            e1, e2, e3 = st.columns(3)
            nome_e = e1.text_input("Nome", value=row["Nome"], key="col_edit_nome")
            subgrupo_e = e2.selectbox("Subgrupo/Categoria", sg_list, index=sg_list.index(row["Subgrupo"]) if row["Subgrupo"] in sg_list else 0, key="col_edit_sg")
            entrada_e = e3.text_input("Entrada padrão (HH:MM)", value=row["Entrada"], key="col_edit_ent")

            e4, e5 = st.columns(2)
            folga_sab_e = e4.checkbox("Pode folgar no sábado", value=bool(row["Folga_Sab"]), key="col_edit_folsab")
            ativo_e = e5.checkbox("Ativo", value=bool(row["Ativo"]), key="col_edit_ativo")

            if st.button("Salvar alterações", key="col_save_btn"):
                update_colaborador(setor, chapa_sel, nome_e.strip(), subgrupo_e, entrada_e.strip(), folga_sab_e, ativo_e)
                st.success("Salvo!")
                st.rerun()

        st.markdown("---")
        st.markdown("### 🧩 Subgrupos (Categorias) do setor")
        sg_current = list_subgrupos(setor)
        s1, s2 = st.columns(2)
        novo_sg = s1.text_input("Novo subgrupo", key="sg_new")
        if s1.button("Adicionar subgrupo", key="sg_add_btn"):
            add_subgrupo(setor, novo_sg.strip())
            st.success("Adicionado!")
            st.rerun()

        if sg_current:
            sg_del = s2.selectbox("Excluir subgrupo", ["(selecione)"] + sg_current, key="sg_del_sel")
            if s2.button("Excluir", key="sg_del_btn"):
                if sg_del != "(selecione)":
                    delete_subgrupo(setor, sg_del)
                    st.success("Excluído!")
                    st.rerun()

        st.markdown("---")
        st.markdown("### ✅ Preferência: dias com menos folga (por subgrupo)")
        sg_all = ["SEM SUBGRUPO"] + list_subgrupos(setor)
        sg_pref = st.selectbox("Subgrupo para configurar", sg_all, key="pref_sg_sel")

        regras = get_subgrupo_regras(setor, sg_pref) if sg_pref != "SEM SUBGRUPO" else {"seg":0,"ter":0,"qua":0,"qui":0,"sex":0,"sáb":0}
        p1, p2, p3 = st.columns(3)
        ev_seg = p1.checkbox("Evitar folga SEG", value=bool(regras["seg"]), key=f"pref_seg_{sg_pref}")
        ev_ter = p1.checkbox("Evitar folga TER", value=bool(regras["ter"]), key=f"pref_ter_{sg_pref}")
        ev_qua = p2.checkbox("Evitar folga QUA", value=bool(regras["qua"]), key=f"pref_qua_{sg_pref}")
        ev_qui = p2.checkbox("Evitar folga QUI", value=bool(regras["qui"]), key=f"pref_qui_{sg_pref}")
        ev_sex = p3.checkbox("Evitar folga SEX", value=bool(regras["sex"]), key=f"pref_sex_{sg_pref}")
        ev_sab = p3.checkbox("Evitar folga SÁB", value=bool(regras["sáb"]), key=f"pref_sab_{sg_pref}")

        if st.button("Salvar preferência do subgrupo", key="pref_save_btn"):
            if sg_pref == "SEM SUBGRUPO":
                st.warning("SEM SUBGRUPO não tem preferência global (crie um subgrupo e use nele).")
            else:
                set_subgrupo_regras(setor, sg_pref, {"seg":ev_seg,"ter":ev_ter,"qua":ev_qua,"qui":ev_qui,"sex":ev_sex,"sáb":ev_sab})
                st.success("Preferência salva!")

    # =========================================================
    # 🚀 Gerar Escala + Ajustes completos
    # =========================================================
    with aba2:
        st.subheader("🚀 Gerar Escala 5x2 + Domingo 1x1 + Interstício")

        c1, c2, c3 = st.columns(3)
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=int(st.session_state["escala_ano"]), key="gen_ano")
        mes = c2.selectbox("Mês", list(range(1, 13)), index=int(st.session_state["escala_mes"]) - 1, key="gen_mes")
        seed = c3.number_input("Semente (para variar distribuição)", min_value=0, max_value=999999, value=0, key="gen_seed")

        b1, b2, b3 = st.columns(3)
        if b1.button("🚀 GERAR E SALVAR", key="gen_btn"):
            escala, estado = generate_schedule_setor(setor, int(ano), int(mes), seed=int(seed))
            if not escala:
                st.error("Sem colaboradores ativos.")
            else:
                # aplicar overrides antes de salvar
                escala = apply_overrides_to_escala(setor, int(ano), int(mes), escala)

                clear_escala_mes(setor, int(ano), int(mes))
                save_escala_mes(setor, int(ano), int(mes), escala)
                save_estado_mes(setor, int(ano), int(mes), estado)

                st.session_state["escala_cache"] = escala
                st.session_state["escala_ano"] = int(ano)
                st.session_state["escala_mes"] = int(mes)

                st.success("Escala gerada e salva!")
                st.rerun()

        if b2.button("📥 CARREGAR DO BANCO", key="load_btn"):
            escala = load_escala_mes(setor, int(ano), int(mes))
            escala = apply_overrides_to_escala(setor, int(ano), int(mes), escala)
            st.session_state["escala_cache"] = escala
            st.session_state["escala_ano"] = int(ano)
            st.session_state["escala_mes"] = int(mes)
            st.success("Escala carregada!")
            st.rerun()

        if b3.button("🧽 LIMPAR OVERRIDES DO MÊS", key="clear_ov_btn"):
            con = db_conn()
            cur = con.cursor()
            cur.execute("DELETE FROM overrides WHERE setor=? AND ano=? AND mes=?", (setor, int(ano), int(mes)))
            con.commit()
            con.close()
            st.success("Overrides do mês removidos. Recarregue/regenere.")
            st.rerun()

        escala_cache = st.session_state.get("escala_cache", {})
        if not escala_cache:
            st.info("Gere ou carregue a escala para visualizar e ajustar.")
        else:
            # Visual RH
            st.markdown("### 📅 Calendário visual (estilo RH)")
            cal_df = build_calendar_table(setor, int(ano), int(mes), escala_cache)
            st.dataframe(cal_df, use_container_width=True)

            st.markdown("### 📊 Indicador de folgas por dia (para balanceamento)")
            folgas_df = build_folgas_por_dia(escala_cache)
            st.dataframe(folgas_df, use_container_width=True)

            st.markdown("---")
            st.markdown("## ⚙️ Ajustes Manuais (com regra de Domingo 1x1 automática)")
            tab_a1, tab_a2, tab_a3, tab_a4 = st.tabs([
                "🔄 Trocar Folgas",
                "🕒 Trocar Horário (1 dia)",
                "🗓️ Trocar Horário (mês inteiro)",
                "🏷️ Trocar Subgrupo/Categoria"
            ])

            # helpers
            colabs = [c for c in load_colaboradores_setor(setor) if c.get("Ativo", True)]
            chapa_list = [c["Chapa"] for c in colabs]
            chapa_to_name = {c["Chapa"]: c["Nome"] for c in colabs}
            ndays = calendar.monthrange(int(ano), int(mes))[1]

            with tab_a1:
                if not chapa_list:
                    st.warning("Sem colaboradores.")
                else:
                    chapa_sel = st.selectbox("Colaborador", chapa_list, format_func=lambda x: f"{chapa_to_name.get(x,x)} ({x})", key="adj_swap_chapa")
                    df_emp = escala_cache[chapa_sel]

                    folgas = df_emp[df_emp["Status"] == STATUS_FOLGA]["DiaMes"].tolist()
                    trabs = df_emp[df_emp["Status"] == STATUS_TRAB]["DiaMes"].tolist()

                    c1, c2 = st.columns(2)
                    dia_trabalhar = c1.selectbox("Dia para TRABALHAR (tirar folga)", folgas if folgas else [1], key="adj_swap_take")
                    dia_folgar = c2.selectbox("Dia para FOLGAR (virar folga)", trabs if trabs else [1], key="adj_swap_put")

                    if st.button("Confirmar troca", key="adj_swap_btn"):
                        # override status nos 2 dias
                        set_override(setor, int(ano), int(mes), chapa_sel, int(dia_trabalhar), "status", STATUS_TRAB)
                        set_override(setor, int(ano), int(mes), chapa_sel, int(dia_folgar), "status", STATUS_FOLGA)

                        # recarrega e aplica alternância de domingo se mexeu em domingo
                        escala_cache2 = load_escala_mes(setor, int(ano), int(mes))
                        escala_cache2 = apply_overrides_to_escala(setor, int(ano), int(mes), escala_cache2)

                        # salvar de volta a escala já ajustada
                        clear_escala_mes(setor, int(ano), int(mes))
                        save_escala_mes(setor, int(ano), int(mes), escala_cache2)

                        st.session_state["escala_cache"] = escala_cache2
                        st.success("Troca aplicada e salva!")
                        st.rerun()

            with tab_a2:
                if not chapa_list:
                    st.warning("Sem colaboradores.")
                else:
                    chapa_sel = st.selectbox("Colaborador", chapa_list, format_func=lambda x: f"{chapa_to_name.get(x,x)} ({x})", key="adj_time_chapa")
                    dia = st.number_input("Dia do mês", min_value=1, max_value=ndays, value=1, step=1, key="adj_time_day")
                    nova_ent = st.text_input("Nova entrada (HH:MM)", value="06:00", key="adj_time_ent")

                    if st.button("Salvar horário do dia", key="adj_time_btn"):
                        set_override(setor, int(ano), int(mes), chapa_sel, int(dia), "h_entrada", nova_ent.strip())

                        escala_cache2 = load_escala_mes(setor, int(ano), int(mes))
                        escala_cache2 = apply_overrides_to_escala(setor, int(ano), int(mes), escala_cache2)

                        clear_escala_mes(setor, int(ano), int(mes))
                        save_escala_mes(setor, int(ano), int(mes), escala_cache2)

                        st.session_state["escala_cache"] = escala_cache2
                        st.success("Horário alterado e salvo!")
                        st.rerun()

            with tab_a3:
                if not chapa_list:
                    st.warning("Sem colaboradores.")
                else:
                    chapa_sel = st.selectbox("Colaborador", chapa_list, format_func=lambda x: f"{chapa_to_name.get(x,x)} ({x})", key="adj_month_time_chapa")
                    nova_ent = st.text_input("Nova entrada para o mês todo (HH:MM)", value="06:00", key="adj_month_time_ent")

                    if st.button("Aplicar no mês inteiro", key="adj_month_time_btn"):
                        # aplica override de entrada em todos os dias de trabalho
                        escala_base = load_escala_mes(setor, int(ano), int(mes))
                        df_emp = escala_base.get(chapa_sel)
                        if df_emp is None or df_emp.empty:
                            st.error("Escala não encontrada. Gere/Carregue primeiro.")
                        else:
                            for _, r in df_emp.iterrows():
                                if r["Status"] == STATUS_TRAB:
                                    set_override(setor, int(ano), int(mes), chapa_sel, int(r["DiaMes"]), "h_entrada", nova_ent.strip())

                            escala_cache2 = load_escala_mes(setor, int(ano), int(mes))
                            escala_cache2 = apply_overrides_to_escala(setor, int(ano), int(mes), escala_cache2)

                            clear_escala_mes(setor, int(ano), int(mes))
                            save_escala_mes(setor, int(ano), int(mes), escala_cache2)

                            st.session_state["escala_cache"] = escala_cache2
                            st.success("Horário do mês inteiro aplicado!")
                            st.rerun()

            with tab_a4:
                if not chapa_list:
                    st.warning("Sem colaboradores.")
                else:
                    chapa_sel = st.selectbox("Colaborador", chapa_list, format_func=lambda x: f"{chapa_to_name.get(x,x)} ({x})", key="adj_sg_chapa")
                    sg_list = ["SEM SUBGRUPO"] + list_subgrupos(setor)
                    novo_sg = st.selectbox("Novo Subgrupo/Categoria", sg_list, key="adj_sg_new")

                    if st.button("Salvar subgrupo do colaborador", key="adj_sg_btn"):
                        # muda cadastro (impacta próximas gerações)
                        colabs_all = load_colaboradores_setor(setor)
                        row = next((c for c in colabs_all if c["Chapa"] == chapa_sel), None)
                        if not row:
                            st.error("Colaborador não encontrado.")
                        else:
                            update_colaborador(setor, chapa_sel, row["Nome"], novo_sg, row["Entrada"], row["Folga_Sab"], row["Ativo"])
                            st.success("Subgrupo alterado! Gere novamente para refletir 100% nas regras do subgrupo.")
                            st.rerun()

            st.markdown("---")
            st.markdown("### 📌 Observação importante dos ajustes")
            st.write("- Se você alterar um **domingo** manualmente, o sistema alterna os **próximos domingos** automaticamente (1x1).")
            st.write("- A regra de **máximo 5 dias seguidos** é garantida principalmente no gerador; em ajustes manuais você consegue forçar algo fora — use com cuidado.")

    # =========================================================
    # 🏖️ Férias
    # =========================================================
    with aba3:
        st.subheader("🏖️ Férias (entra automático na escala)")

        colabs = [c for c in load_colaboradores_setor(setor) if c.get("Ativo", True)]
        if not colabs:
            st.warning("Cadastre colaboradores primeiro.")
        else:
            chapas = [c["Chapa"] for c in colabs]
            nomes = {c["Chapa"]: c["Nome"] for c in colabs}

            c1, c2, c3 = st.columns(3)
            chapa = c1.selectbox("Colaborador", chapas, format_func=lambda x: f"{nomes.get(x,x)} ({x})", key="fer_chapa")
            ini = c2.date_input("Início", key="fer_ini")
            fim = c3.date_input("Fim", key="fer_fim")

            if st.button("Adicionar férias", key="fer_add_btn"):
                if fim < ini:
                    st.error("Fim não pode ser menor que início.")
                else:
                    add_ferias(setor, chapa, ini, fim)
                    st.success("Férias cadastradas!")
                    st.rerun()

            df_f = list_ferias(setor)
            st.dataframe(df_f, use_container_width=True)

            if not df_f.empty:
                st.markdown("### 🗑️ Remover férias")
                r = df_f.copy()
                r["label"] = r.apply(lambda x: f"{x['chapa']} | {x['inicio']} → {x['fim']}", axis=1)
                sel = st.selectbox("Selecionar", r["label"].tolist(), key="fer_del_sel")
                if st.button("Remover", key="fer_del_btn"):
                    row = r[r["label"] == sel].iloc[0]
                    delete_ferias_row(setor, str(row["chapa"]), str(row["inicio"]), str(row["fim"]))
                    st.success("Removido!")
                    st.rerun()

            st.info("Regra retorno: 1ª semana após férias é 'livre' (não força 2 folgas), mas mantém domingo 1x1.")

    # =========================================================
    # 📥 Excel
    # =========================================================
    with aba4:
        st.subheader("📥 Exportar Excel (modelo RH por subgrupo)")

        ano = int(st.session_state.get("escala_ano", datetime.now().year))
        mes = int(st.session_state.get("escala_mes", datetime.now().month))

        escala_cache = st.session_state.get("escala_cache", {})
        if not escala_cache:
            st.warning("Gere ou carregue a escala antes.")
        else:
            if st.button("Gerar Excel RH", key="xl_btn"):
                xbytes = build_excel_rh(setor, ano, mes, escala_cache)
                st.download_button(
                    "⬇️ Baixar Excel",
                    data=xbytes,
                    file_name=f"Escala_{setor}_{mes:02d}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_excel"
                )
            st.caption("No Excel: F = Folga | FER = Férias | Domingo destacado")

    # =========================================================
    # 🔒 Admin
    # =========================================================
    with aba5:
        if auth.get("is_admin", False) and setor == "ADMIN":
            st.subheader("🔒 Admin do Sistema")
            st.write("Aqui você gerencia usuários de login (setores, chapas, senhas).")

            dfu = admin_list_users()
            st.dataframe(dfu, use_container_width=True)

            st.markdown("### ➕ Criar usuário do sistema")
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome", key="adm_new_nome")
            setor_u = c2.text_input("Setor", key="adm_new_setor").strip().upper()
            chapa = c3.text_input("Chapa", key="adm_new_chapa")
            c4, c5, c6 = st.columns(3)
            senha = c4.text_input("Senha", type="password", key="adm_new_senha")
            is_lider = c5.checkbox("Líder", key="adm_new_lider")
            is_admin = c6.checkbox("Admin", key="adm_new_admin")

            if st.button("Criar", key="adm_new_btn"):
                if not nome or not setor_u or not chapa or not senha:
                    st.error("Preencha tudo.")
                elif system_user_exists(setor_u, chapa):
                    st.error("Já existe.")
                else:
                    create_system_user(nome.strip(), setor_u, chapa.strip(), senha, is_lider=1 if is_lider else 0, is_admin=1 if is_admin else 0)
                    st.success("Criado!")
                    st.rerun()

            st.markdown("---")
            st.markdown("### ✏️ Editar / Resetar senha / Excluir usuário")
            if not dfu.empty:
                user_id = st.selectbox("Usuário (id)", dfu["id"].tolist(), key="adm_edit_id")
                row = dfu[dfu["id"] == user_id].iloc[0]

                e1, e2, e3 = st.columns(3)
                nome_e = e1.text_input("Nome", value=row["nome"], key="adm_edit_nome")
                setor_e = e2.text_input("Setor", value=row["setor"], key="adm_edit_setor").strip().upper()
                chapa_e = e3.text_input("Chapa", value=row["chapa"], key="adm_edit_chapa")
                e4, e5 = st.columns(2)
                adm_e = e4.checkbox("Admin", value=bool(row["is_admin"]), key="adm_edit_admin")
                lider_e = e5.checkbox("Líder", value=bool(row["is_lider"]), key="adm_edit_lider")

                b1, b2, b3 = st.columns(3)
                if b1.button("Salvar edição", key="adm_edit_save"):
                    admin_update_user(int(user_id), nome_e.strip(), setor_e, chapa_e.strip(), adm_e, lider_e)
                    st.success("Atualizado!")
                    st.rerun()

                nova_senha = b2.text_input("Nova senha", type="password", key="adm_reset_pwd")
                if b2.button("Resetar senha", key="adm_reset_btn"):
                    if not nova_senha:
                        st.error("Digite a nova senha.")
                    else:
                        ok = admin_reset_user_password(int(user_id), nova_senha)
                        st.success("Senha resetada!" if ok else "Falha.")

                if b3.button("Excluir usuário", key="adm_del_btn"):
                    admin_delete_user(int(user_id))
                    st.success("Excluído!")
                    st.rerun()
        else:
            st.info("Esta aba é somente para ADMIN do setor ADMIN.")

def main():
    if st.session_state.get("auth") is None:
        page_login()
    else:
        page_app()

main()
