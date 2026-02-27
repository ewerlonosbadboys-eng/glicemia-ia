# main.py
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO + MIGRAÇÃO AUTOMÁTICA DO DB
# Corrige erro: pandas DatabaseError por schema antigo
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

st.set_page_config(page_title="Escala 5x2 Oficial", layout="wide")

DB_PATH = "escala.db"

INTERSTICIO_MIN = timedelta(hours=11, minutes=10)
DURACAO_JORNADA = timedelta(hours=9, minutes=58)
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

# =========================================================
# DB Helpers
# =========================================================
def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    rows = cur.fetchall()
    return [r[1] for r in rows]  # name

def db_init_schema():
    con = db_conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS setores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )
    """)

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

    cur.execute("""
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subgrupos_setor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        nome TEXT NOT NULL,
        UNIQUE(setor, nome)
    )
    """)

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ferias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL
    )
    """)

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
    """
    Migração automática: se DB antigo estiver faltando colunas,
    adiciona com ALTER TABLE.
    """
    con = db_conn()
    cur = con.cursor()

    # garante tabelas
    con.close()
    db_init_schema()

    con = db_conn()
    cur = con.cursor()

    # migra estado_mes_anterior (coluna retorno_ferias_ate pode faltar)
    try:
        cols = table_columns(con, "estado_mes_anterior")
        if "retorno_ferias_ate" not in cols:
            cur.execute("ALTER TABLE estado_mes_anterior ADD COLUMN retorno_ferias_ate TEXT")
        # alguns bancos antigos podem não ter ultimo_domingo_status
        if "ultimo_domingo_status" not in cols:
            cur.execute("ALTER TABLE estado_mes_anterior ADD COLUMN ultimo_domingo_status TEXT")
        con.commit()
    except Exception:
        # se tabela não existia, schema já cria
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

def admin_delete_user(user_id: int):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM usuarios_sistema WHERE id=?", (int(user_id),))
    con.commit()
    con.close()

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
# SUBGRUPOS + Preferência
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
    df = pd.read_sql_query("""
        SELECT chapa, inicio, fim
        FROM ferias
        WHERE setor=?
        ORDER BY date(inicio) ASC
    """, con, params=(setor,))
    con.close()
    return df

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
# ESCALA: persistência
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
            """, (
                setor, ano, mes, chapa,
                int(r["DiaMes"]),
                r["Data"].strftime("%Y-%m-%d"),
                r["DiaSem"],
                r["Status"],
                (r.get("Entrada", "") or ""),
                (r.get("Saida", "") or ""),
            ))
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
        g2["DiaSem"] = g2["dia_sem"]
        g2["Status"] = g2["status"]
        g2["Entrada"] = g2["h_entrada"]
        g2["Saida"] = g2["h_saida"]
        g2 = g2[["Data", "DiaMes", "DiaSem", "Status", "Entrada", "Saida"]]
        out[chapa] = g2.reset_index(drop=True)
    return out

def save_estado_mes(setor: str, ano: int, mes: int, estado: Dict[str, dict]):
    con = db_conn()
    cur = con.cursor()
    for chapa, stt in estado.items():
        cur.execute("""
            INSERT OR REPLACE INTO estado_mes_anterior(setor, chapa, ano, mes, consec_trab_final, ultima_saida, ultimo_domingo_status, retorno_ferias_ate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            setor, chapa, ano, mes,
            int(stt.get("consec_trab_final", 0)),
            stt.get("ultima_saida", "00:00"),
            stt.get("ultimo_domingo_status", ""),
            stt.get("retorno_ferias_ate", ""),
        ))
    con.commit()
    con.close()

def load_estado_mes(setor: str, ano: int, mes: int) -> Dict[str, dict]:
    """
    Seguro contra schema antigo: se a coluna retorno_ferias_ate não existir,
    lê sem ela.
    """
    con = db_conn()
    cols = table_columns(con, "estado_mes_anterior")
    try:
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
    finally:
        con.close()

    out = {}
    for _, r in df.iterrows():
        out[r["chapa"]] = {
            "consec_trab_final": int(r["consec_trab_final"]),
            "ultima_saida": r["ultima_saida"],
            "ultimo_domingo_status": r.get("ultimo_domingo_status", "") or "",
            "retorno_ferias_ate": r.get("retorno_ferias_ate", "") or "",
        }
    return out

def load_last_month_state(setor: str, ano: int, mes: int) -> Dict[str, dict]:
    prev_year = ano
    prev_month = mes - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    return load_estado_mes(setor, prev_year, prev_month)

# =========================================================
# Regras de jornada
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

# =========================================================
# GERADOR DE ESCALA (mesmo motor da versão anterior)
# =========================================================
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

def generate_schedule_setor(setor: str, ano: int, mes: int, seed: int = 0) -> Tuple[Dict[str, pd.DataFrame], Dict[str, dict]]:
    random.seed(seed)

    colabs = load_colaboradores_setor(setor)
    if not colabs:
        return {}, {}

    dates = month_dates(ano, mes)
    ndays = len(dates)

    prev_state = load_last_month_state(setor, ano, mes)
    groups = group_by_subgrupo(colabs)

    escala: Dict[str, pd.DataFrame] = {}
    estado_out: Dict[str, dict] = {}

    base = {}
    for c in colabs:
        df = pd.DataFrame({
            "Data": dates,
            "DiaMes": [d.day for d in dates],
            "DiaSem": [day_sem_pt(d) for d in dates],
            "Status": ["Trabalho"] * ndays,
            "Entrada": [""] * ndays,
            "Saida": [""] * ndays,
        })
        base[c["Chapa"]] = df

    # Férias
    for c in colabs:
        chapa = c["Chapa"]
        df = base[chapa]
        for i, d in enumerate(dates):
            if is_de_ferias(setor, chapa, d):
                df.loc[i, "Status"] = "FÉRIAS"
        base[chapa] = df

    # Domingo 1x1 por subgrupo (desde o primeiro domingo)
    for sg, members in groups.items():
        members_sorted = sorted(members, key=lambda x: x["Chapa"])
        if not members_sorted:
            continue
        pointer = 0
        domingos = [i for i, d in enumerate(dates) if d.weekday() == 6]
        if not domingos:
            continue
        k = max(1, len(members_sorted) // 2)

        for idx_dom in domingos:
            folgam = []
            for j in range(k):
                folgam.append(members_sorted[(pointer + j) % len(members_sorted)]["Chapa"])
            pointer = (pointer + k) % len(members_sorted)

            for c in members_sorted:
                chapa = c["Chapa"]
                df = base[chapa]
                if df.loc[idx_dom, "Status"] == "FÉRIAS":
                    continue
                df.loc[idx_dom, "Status"] = "Folga" if chapa in folgam else "Trabalho"
                base[chapa] = df

    # 5x2 semanal Seg->Dom + balanceamento
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

                folgas_week = 0
                for i in idxs:
                    if df.loc[i, "Status"] == "Folga":
                        folgas_week += 1

                idx_dom = None
                for i in idxs:
                    if dates[i].weekday() == 6:
                        idx_dom = i
                        break

                worked_sunday = False
                sunday_is_folga = False
                if idx_dom is not None and df.loc[idx_dom, "Status"] != "FÉRIAS":
                    if df.loc[idx_dom, "Status"] == "Trabalho":
                        worked_sunday = True
                    elif df.loc[idx_dom, "Status"] == "Folga":
                        sunday_is_folga = True

                def is_allowed_folga(i: int) -> bool:
                    if df.loc[i, "Status"] in ("FÉRIAS", "Folga"):
                        return False
                    ds = df.loc[i, "DiaSem"]
                    if ds == "sáb" and not folga_sab_ok:
                        return False
                    if i > 0 and df.loc[i-1, "Status"] == "Folga":
                        return False
                    if i < ndays-1 and df.loc[i+1, "Status"] == "Folga":
                        return False
                    return True

                # força quebra se já tem 5 seguidos
                for i in idxs:
                    if df.loc[i, "Status"] in ("FÉRIAS", "Folga"):
                        consec = 0
                        continue
                    if consec >= 5 and is_allowed_folga(i):
                        df.loc[i, "Status"] = "Folga"
                        day_counts[i] += 1
                        folgas_week += 1
                        consec = 0
                    else:
                        consec += 1

                target_folgas = 2 if not in_free_week else max(1, folgas_week)

                seg_sex = [i for i in idxs if df.loc[i, "DiaSem"] in ("seg", "ter", "qua", "qui", "sex")]

                def ensure_one_folga_seg_sex():
                    nonlocal folgas_week
                    if any(df.loc[i, "Status"] == "Folga" for i in seg_sex):
                        return
                    poss = [i for i in seg_sex if is_allowed_folga(i)]
                    chosen = choose_balanced_day(poss, day_counts, penalties)
                    if chosen is not None:
                        df.loc[chosen, "Status"] = "Folga"
                        day_counts[chosen] += 1
                        folgas_week += 1

                if (worked_sunday or sunday_is_folga) and seg_sex:
                    ensure_one_folga_seg_sex()

                while folgas_week < target_folgas:
                    poss = [i for i in idxs if is_allowed_folga(i)]
                    if idx_dom is not None:
                        poss = [i for i in poss if i != idx_dom]
                    chosen = choose_balanced_day(poss, day_counts, penalties)
                    if chosen is None:
                        break
                    df.loc[chosen, "Status"] = "Folga"
                    day_counts[chosen] += 1
                    folgas_week += 1

            base[chapa] = df

    # Horários + interstício
    for c in colabs:
        chapa = c["Chapa"]
        entrada_padrao = c["Entrada"] or "06:00"
        df = base[chapa]

        last_saida = (prev_state.get(chapa, {}) or {}).get("ultima_saida", "") or ""
        for i in range(ndays):
            status = df.loc[i, "Status"]
            if status in ("Folga", "FÉRIAS"):
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

    for c in colabs:
        escala[c["Chapa"]] = base[c["Chapa"]].copy()

    for c in colabs:
        chapa = c["Chapa"]
        df = escala[chapa]
        consec = 0
        last_saida = ""
        ultimo_domingo_status = ""
        for i in range(ndays):
            if df.loc[i, "Status"] in ("Folga", "FÉRIAS"):
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

    return escala, estado_out

# =========================================================
# Excel RH
# =========================================================
def build_excel_rh(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame]) -> bytes:
    colabs = load_colaboradores_setor(setor)
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
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ndays + 2)

        ws.cell(2, 1, "COLABORADOR").fill = blue
        ws.cell(3, 1, "").fill = blue
        ws.cell(2, 1).font = header_font
        ws.cell(2, 1).alignment = center
        ws.merge_cells(start_row=2, start_column=1, end_row=3, end_column=1)

        for i, d in enumerate(dates):
            col = i + 2
            ws.cell(2, col, d.day).fill = blue
            ws.cell(2, col).font = header_font
            ws.cell(2, col).alignment = center

            ws.cell(3, col, day_sem_pt(d)).alignment = center
            if day_sem_pt(d) == "dom":
                ws.cell(3, col).fill = sunday

            ws.cell(2, col).border = border
            ws.cell(3, col).border = border

        row = 4
        for sg, chapas in by_sg.items():
            ws.cell(row, 1, f"SUBGRUPO: {sg}").fill = blue
            ws.cell(row, 1).font = header_font
            ws.cell(row, 1).alignment = Alignment(horizontal="left", vertical="center")
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ndays + 2)
            row += 1

            for chapa in chapas:
                cinfo = info[chapa]
                nome = cinfo["Nome"]
                df = escala.get(chapa)
                if df is None or df.empty:
                    continue

                ws.cell(row, 1, f"{nome}\n({chapa})").alignment = center
                ws.merge_cells(start_row=row, start_column=1, end_row=row+1, end_column=1)

                for i in range(ndays):
                    col = i + 2
                    status = df.loc[i, "Status"]
                    ent = df.loc[i, "Entrada"]
                    sai = df.loc[i, "Saida"]

                    c1 = ws.cell(row, col, "F" if status == "Folga" else ("FÉRIAS" if status == "FÉRIAS" else ent))
                    c2 = ws.cell(row+1, col, "" if status in ("Folga", "FÉRIAS") else sai)

                    for cc in (c1, c2):
                        cc.alignment = center
                        cc.border = border

                    if status == "Folga":
                        c1.fill = green
                        c2.fill = green
                    elif status == "FÉRIAS":
                        c1.fill = green2
                        c2.fill = green2
                    elif df.loc[i, "DiaSem"] == "dom":
                        c1.fill = sunday
                        c2.fill = sunday

                row += 2
            row += 1

        ws.column_dimensions["A"].width = 28
        for i in range(2, ndays + 2):
            ws.column_dimensions[get_column_letter(i)].width = 6

        if "Sheet" in wb.sheetnames and wb["Sheet"].max_row == 1 and wb["Sheet"].max_column == 1:
            wb.remove(wb["Sheet"])

    return output.getvalue()

# =========================================================
# UI
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

def reset_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db_migrate()

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

    # Botão de reset DB (somente admin)
    if auth.get("is_admin", False) and setor == "ADMIN":
        st.sidebar.markdown("---")
        if st.sidebar.button("🧹 Resetar banco (apaga tudo)", key="reset_db_btn"):
            reset_db()
            st.session_state["auth"] = None
            st.session_state["escala_cache"] = {}
            st.success("Banco resetado. Faça login novamente.")
            st.rerun()

    # === PÁGINAS DO SETOR (mínimo para gerar e exportar já) ===
    st.title(f"📌 Sistema — Setor: {setor}")

    aba1, aba2, aba3, aba4, aba5 = st.tabs(["👥 Colaboradores", "🚀 Gerar Escala", "🏖️ Férias", "📥 Excel", "🔒 Admin"])
    with aba1:
        st.subheader("Colaboradores")
        colaboradores = load_colaboradores_setor(setor)
        st.dataframe(pd.DataFrame(colaboradores) if colaboradores else pd.DataFrame(), use_container_width=True)

        c1, c2 = st.columns(2)
        nome_n = c1.text_input("Nome:", key="col_nome")
        chapa_n = c2.text_input("Chapa:", key="col_chapa")
        if st.button("Cadastrar colaborador", key="col_add"):
            if not nome_n or not chapa_n:
                st.error("Preencha.")
            else:
                create_colaborador(nome_n.strip(), setor, chapa_n.strip())
                st.success("Cadastrado!")
                st.rerun()

    with aba2:
        st.subheader("Gerar escala")
        c1, c2, c3 = st.columns(3)
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=st.session_state["escala_ano"], key="gen_ano")
        mes = c2.selectbox("Mês", list(range(1, 13)), index=int(st.session_state["escala_mes"]) - 1, key="gen_mes")
        seed = c3.number_input("Semente", min_value=0, max_value=999999, value=0, key="gen_seed")

        if st.button("🚀 GERAR", key="gen_btn"):
            escala, estado = generate_schedule_setor(setor, int(ano), int(mes), seed=int(seed))
            if not escala:
                st.error("Sem colaboradores.")
            else:
                clear_escala_mes(setor, int(ano), int(mes))
                save_escala_mes(setor, int(ano), int(mes), escala)
                save_estado_mes(setor, int(ano), int(mes), estado)
                st.session_state["escala_cache"] = escala
                st.session_state["escala_ano"] = int(ano)
                st.session_state["escala_mes"] = int(mes)
                st.success("Gerada e salva!")
                st.rerun()

        if st.button("📥 Carregar do banco", key="load_btn"):
            escala = load_escala_mes(setor, int(ano), int(mes))
            st.session_state["escala_cache"] = escala
            st.session_state["escala_ano"] = int(ano)
            st.session_state["escala_mes"] = int(mes)
            st.success("Carregada!")
            st.rerun()

        if st.session_state["escala_cache"]:
            st.write("✅ Escala carregada na sessão.")

    with aba3:
        st.subheader("Férias")
        colaboradores = load_colaboradores_setor(setor)
        if colaboradores:
            chapas = [c["Chapa"] for c in colaboradores]
            ch = st.selectbox("Chapa:", chapas, key="fer_ch")
            ini = st.date_input("Início", key="fer_ini")
            fim = st.date_input("Fim", key="fer_fim")
            if st.button("Adicionar", key="fer_add"):
                add_ferias(setor, ch, ini, fim)
                st.success("Ok!")
                st.rerun()
            st.dataframe(list_ferias(setor), use_container_width=True)
        else:
            st.info("Cadastre colaboradores primeiro.")

    with aba4:
        st.subheader("Excel")
        ano = st.session_state.get("escala_ano", datetime.now().year)
        mes = st.session_state.get("escala_mes", datetime.now().month)
        escala_cache = st.session_state.get("escala_cache", {})
        if not escala_cache:
            st.warning("Gere ou carregue a escala antes.")
        else:
            if st.button("Gerar Excel RH", key="xl_btn"):
                xbytes = build_excel_rh(setor, int(ano), int(mes), escala_cache)
                st.download_button(
                    "⬇️ Baixar Excel",
                    data=xbytes,
                    file_name=f"Escala_{setor}_{mes:02d}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_excel"
                )

    with aba5:
        if auth.get("is_admin", False) and setor == "ADMIN":
            st.subheader("Admin")
            st.dataframe(admin_list_users(), use_container_width=True)
        else:
            st.info("Apenas admin do setor ADMIN.")

def main():
    if st.session_state.get("auth") is None:
        page_login()
    else:
        page_app()

main()
