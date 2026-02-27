# main.py
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO E FUNCIONAL
# Login por Setor (usuários do sistema com senha)
# Colaboradores sem senha (cadastro por setor logado)
# Regras: 5x2 (Seg->Dom), Domingo 1x1 por Subgrupo,
#         Interstício 11h10, Máx 5 dias seguidos,
#         Sem folgas consecutivas, Férias automáticas,
#         Balanceamento de folgas por subgrupo,
#         Ajustes manuais + Excel RH (azul/verde).
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

def db_init():
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

    # estado para "escala corrida" (analisa mês anterior)
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

def ferias_range_for_chapa(setor: str, chapa: str) -> List[Tuple[date, date]]:
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT inicio, fim
        FROM ferias
        WHERE setor=? AND chapa=?
    """, (setor, chapa))
    rows = cur.fetchall()
    con.close()
    out = []
    for ini, fim in rows:
        out.append((datetime.strptime(ini, "%Y-%m-%d").date(), datetime.strptime(fim, "%Y-%m-%d").date()))
    return out

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

def retorno_ferias_ate(setor: str, chapa: str) -> Optional[date]:
    """
    Regra: quando volta de férias, 1ª semana desconsidera 5x2 (só respeita domingo).
    Aqui retornamos a data limite (fim + 7 dias) do último período de férias que termina antes de hoje/mês.
    """
    ranges = ferias_range_for_chapa(setor, chapa)
    if not ranges:
        return None
    # pega a última férias (maior fim)
    last = sorted(ranges, key=lambda x: x[1])[-1]
    return last[1] + timedelta(days=7)

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
                r.get("Entrada", "") or "",
                r.get("Saida", "") or "",
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
    con = db_conn()
    df = pd.read_sql_query("""
        SELECT chapa, consec_trab_final, ultima_saida, ultimo_domingo_status, retorno_ferias_ate
        FROM estado_mes_anterior
        WHERE setor=? AND ano=? AND mes=?
    """, con, params=(setor, ano, mes))
    con.close()
    out = {}
    for _, r in df.iterrows():
        out[r["chapa"]] = {
            "consec_trab_final": int(r["consec_trab_final"]),
            "ultima_saida": r["ultima_saida"],
            "ultimo_domingo_status": r["ultimo_domingo_status"] or "",
            "retorno_ferias_ate": r["retorno_ferias_ate"] or "",
        }
    return out

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
            # ajusta para cumprir 11h10
            return (s + INTERSTICIO_MIN).strftime(fmt)
    except Exception:
        pass
    return ent_padrao

def add_hours_str(hhmm: str, td: timedelta) -> str:
    fmt = "%H:%M"
    t = datetime.strptime(hhmm, fmt)
    return (t + td).strftime(fmt)

# =========================================================
# GERADOR DE ESCALA
# =========================================================
def month_dates(ano: int, mes: int) -> List[date]:
    ndays = calendar.monthrange(ano, mes)[1]
    return [date(ano, mes, d) for d in range(1, ndays + 1)]

def day_sem_pt(d: date) -> str:
    return D_PT[d.strftime("%A")]

def week_index_seg_dom(d: date) -> int:
    # semana iniciando segunda (0..), para 5x2
    # pega o "monday" da semana e calcula índice pelo número de semanas desde início do mês
    # suficiente para agrupar por semanas seg->dom
    first = date(d.year, d.month, 1)
    # desloca para a segunda-feira da semana do dia 1
    offset = (first.weekday() - 0)  # Monday=0
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
    # 1 significa "evitar folga", então penaliza
    return {k: int(reg.get(k, 0)) for k in ["seg", "ter", "qua", "qui", "sex", "sáb"]}

def load_last_month_state(setor: str, ano: int, mes: int) -> Dict[str, dict]:
    # mês anterior
    prev_year = ano
    prev_month = mes - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    return load_estado_mes(setor, prev_year, prev_month)

def choose_balanced_day(candidates: List[int], day_counts: Dict[int, int], penalties: Dict[int, int]) -> Optional[int]:
    """
    candidates: lista de índices de dia no mês (0-based)
    day_counts: quantas folgas já tem no subgrupo nesse dia
    penalties: penalidade por dia (preferência evitar)
    """
    if not candidates:
        return None
    # custo = count + penalty
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

    # estado mês anterior (escala corrida)
    prev_state = load_last_month_state(setor, ano, mes)

    # por subgrupo
    groups = group_by_subgrupo(colabs)

    escala: Dict[str, pd.DataFrame] = {}
    estado_out: Dict[str, dict] = {}

    # Pre-cria DF por colaborador
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

    # 1) Aplica férias (bloqueia trabalho/folga)
    for c in colabs:
        chapa = c["Chapa"]
        df = base[chapa]
        for i, d in enumerate(dates):
            if is_de_ferias(setor, chapa, d):
                df.loc[i, "Status"] = "FÉRIAS"
        base[chapa] = df

    # 2) Regra Domingo 1x1 por subgrupo (desde o primeiro domingo)
    # Estratégia:
    # - para cada subgrupo, ordena pessoas por chapa (estável)
    # - cada domingo: metade folga, metade trabalha (diferença máx 1)
    # - alterna o conjunto a cada domingo (rodízio), usando "ponteiro" por subgrupo
    for sg, members in groups.items():
        members_sorted = sorted(members, key=lambda x: x["Chapa"])
        pointer = 0
        # tenta continuar do mês anterior: se existir último domingo status, usa como referência
        # (simples: se último domingo do mês anterior foi Folga, começamos Trabalha no primeiro domingo para a mesma pessoa)
        # Para isso, usamos pointer baseado na contagem de "Folga no domingo" no último estado salvo (se existir)
        domingos = [i for i, d in enumerate(dates) if d.weekday() == 6]  # Sunday=6
        if not domingos:
            continue

        # tamanho do bloco de folga no domingo
        k = max(1, len(members_sorted) // 2)  # pelo menos 1 folga se houver gente

        for di, idx_dom in enumerate(domingos):
            # escolhe k pessoas pra folgar no domingo (rodízio)
            folgam = []
            for j in range(k):
                folgam.append(members_sorted[(pointer + j) % len(members_sorted)]["Chapa"])
            pointer = (pointer + k) % len(members_sorted)

            for c in members_sorted:
                chapa = c["Chapa"]
                df = base[chapa]
                if df.loc[idx_dom, "Status"] == "FÉRIAS":
                    continue
                if chapa in folgam:
                    df.loc[idx_dom, "Status"] = "Folga"
                else:
                    df.loc[idx_dom, "Status"] = "Trabalho"
                base[chapa] = df

    # 3) Regra 5x2 semanal (Seg->Dom) + balanceamento por subgrupo
    # - em cada semana, cada pessoa deve ter 2 folgas (considerando domingo já marcado)
    # - não folga consecutiva
    # - não pode ultrapassar 5 dias seguidos trabalho
    # - sábado só folga se Folga_Sab=True
    # - quando trabalhar no domingo: deve ter folga na semana seg-sex (garante pelo menos 1 folga seg-sex)
    # - quando folgar no domingo: segunda folga aleatória seg-sex (sem consecutivas)
    for sg, members in groups.items():
        # contagem de folgas por dia no subgrupo (para balanceamento)
        day_counts = {i: 0 for i in range(ndays)}
        # carrega preferências do subgrupo
        pref = build_preferencias_map(setor, sg)
        # mapa de penalidades por índice de dia
        penalties = {}
        for i, d in enumerate(dates):
            ds = day_sem_pt(d)
            penalties[i] = PREF_EVITAR_PENALTY if pref.get(ds, 0) == 1 else 0

        for m in members:
            chapa = m["Chapa"]
            folga_sab_ok = bool(m["Folga_Sab"])
            entrada_padrao = m["Entrada"] or "06:00"

            df = base[chapa]

            # período de "retorno férias": até essa data, não força 5x2 (apenas domingo)
            ret_ate = retorno_ferias_ate(setor, chapa)
            # se não existe, usa None

            # estado anterior para consecutivos e última saída
            prev = prev_state.get(chapa, {})
            consec_prev = int(prev.get("consec_trab_final", 0) or 0)
            ultima_saida_prev = prev.get("ultima_saida", "") or ""

            # calcula consecutivo andando pelo mês (respeita FÉRIAS como quebra)
            consec = consec_prev
            ultima_saida = ultima_saida_prev

            # agrupa índices por semana seg->dom
            weeks = {}
            for i, d in enumerate(dates):
                w = week_index_seg_dom(d)
                weeks.setdefault(w, []).append(i)

            # para cada semana
            for w, idxs in weeks.items():
                # se semana inteira está em retorno de férias (ou parte), a regra 5x2 só aplica após ret_ate
                # aqui: se o primeiro dia da semana <= ret_ate, não força 2 folgas nessa semana
                # mas ainda impede >5 dias seguidos e sem consecutivas, e sábado somente se permitido.
                week_dates = [dates[i] for i in idxs]
                in_free_week = False
                if ret_ate is not None:
                    # se a semana tem dias até ret_ate, consideramos "livre" para 5x2
                    if any(d <= ret_ate for d in week_dates):
                        in_free_week = True

                # conta folgas já marcadas (domingo/ferias)
                folgas_week = 0
                for i in idxs:
                    if df.loc[i, "Status"] in ("Folga", "FÉRIAS"):
                        if df.loc[i, "Status"] == "Folga":
                            folgas_week += 1

                # regra especial de domingo
                # se trabalhou domingo (Status Trabalho no domingo), garantir ao menos 1 folga seg-sex nessa semana
                # se folgou domingo, garantir 1 folga seg-sex (a outra pode ser qualquer dia permitido)
                # mas se in_free_week, só garantimos essa lógica básica
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

                # candidatos possíveis para folga (na semana)
                def is_allowed_folga(i: int) -> bool:
                    if df.loc[i, "Status"] == "FÉRIAS":
                        return False
                    if df.loc[i, "Status"] == "Folga":
                        return False
                    ds = df.loc[i, "DiaSem"]
                    if ds == "sáb" and not folga_sab_ok:
                        return False
                    # não permitir folga consecutiva
                    if i > 0 and df.loc[i-1, "Status"] == "Folga":
                        return False
                    if i < ndays-1 and df.loc[i+1, "Status"] == "Folga":
                        return False
                    return True

                # também não permitir criar >5 dias seguidos de trabalho:
                # (simples) antes de marcar folga, verificamos se já está em 5 e o dia é trabalho.
                # (melhor) ao final do mês, corrigimos. Aqui mantemos: se consec>=5, forçamos folga se permitido.

                # 3.1 Força folga se já tem 5 seguidos e o dia é trabalho e pode folgar
                for i in idxs:
                    if df.loc[i, "Status"] == "FÉRIAS":
                        consec = 0
                        ultima_saida = ""
                        continue
                    if df.loc[i, "Status"] == "Folga":
                        consec = 0
                        ultima_saida = ""
                        continue
                    # trabalho
                    if consec >= 5 and is_allowed_folga(i):
                        df.loc[i, "Status"] = "Folga"
                        day_counts[i] += 1
                        folgas_week += 1
                        consec = 0
                        ultima_saida = ""
                    else:
                        consec += 1

                # 3.2 Se não está em semana livre, garante 2 folgas na semana
                target_folgas = 2 if not in_free_week else max(1, folgas_week)  # semana livre: pelo menos mantém o que já tem

                # 3.3 Garantias seg-sex
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

                # se trabalhou domingo OU folgou domingo, pede 1 folga seg-sex
                if (worked_sunday or sunday_is_folga) and seg_sex:
                    ensure_one_folga_seg_sex()

                # 3.4 Completa folgas até target (quando in_free_week, não força; quando normal, força 2)
                while folgas_week < target_folgas:
                    # candidatos na semana inteira (inclui sáb se permitido)
                    poss = [i for i in idxs if is_allowed_folga(i)]
                    # remove domingo (já decidido)
                    if idx_dom is not None:
                        poss = [i for i in poss if i != idx_dom]
                    chosen = choose_balanced_day(poss, day_counts, penalties)
                    if chosen is None:
                        break
                    df.loc[chosen, "Status"] = "Folga"
                    day_counts[chosen] += 1
                    folgas_week += 1

            base[chapa] = df

    # 4) Gera horários (entrada/saída) com interstício 11h10
    # - se Folga/Férias: vazio
    # - se Trabalho: entrada_padrao, mas ajusta se não cumprir interstício com a saída do dia anterior
    for c in colabs:
        chapa = c["Chapa"]
        entrada_padrao = c["Entrada"] or "06:00"
        df = base[chapa]

        last_saida = prev_state.get(chapa, {}).get("ultima_saida", "") or ""
        for i in range(ndays):
            status = df.loc[i, "Status"]
            if status in ("Folga", "FÉRIAS"):
                df.loc[i, "Entrada"] = ""
                df.loc[i, "Saida"] = ""
                last_saida = ""
                continue

            ent = entrada_padrao
            # interstício com último dia trabalhado
            if i == 0 and last_saida:
                ent = calcular_entrada_segura(last_saida, entrada_padrao)
            elif i > 0 and df.loc[i-1, "Saida"]:
                ent = calcular_entrada_segura(df.loc[i-1, "Saida"], entrada_padrao)

            df.loc[i, "Entrada"] = ent
            df.loc[i, "Saida"] = add_hours_str(ent, DURACAO_JORNADA)

        base[chapa] = df

    # 5) Monta saída escala por chapa (DF)
    for c in colabs:
        escala[c["Chapa"]] = base[c["Chapa"]].copy()

    # 6) Salva estado final do mês (para mês seguinte)
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

        ret_ate = retorno_ferias_ate(setor, chapa)
        estado_out[chapa] = {
            "consec_trab_final": int(consec),
            "ultima_saida": last_saida or "00:00",
            "ultimo_domingo_status": ultimo_domingo_status,
            "retorno_ferias_ate": ret_ate.strftime("%Y-%m-%d") if ret_ate else "",
        }

    return escala, estado_out

# =========================================================
# Ajustes de domingo 1x1 automático após edição manual
# =========================================================
def apply_sunday_rodizio_after_manual(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame], subgrupo: str):
    """
    Quando o usuário altera um domingo manualmente, a regra pede:
    - automaticamente alternar os PRÓXIMOS domingos (trabalha/folga)
    Implementação:
    - pega todos colaboradores do subgrupo
    - para cada colaborador: detecta status no primeiro domingo do mês
    - faz alternância nos domingos seguintes
    Observação: isso mantém 1x1 individual (Folga/Trabalho alternado por domingo).
    """
    colabs = load_colaboradores_setor(setor)
    members = [c for c in colabs if ((c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO") == subgrupo]
    if not members:
        return

    dates = month_dates(ano, mes)
    domingos = [i for i, d in enumerate(dates) if d.weekday() == 6]
    if len(domingos) < 2:
        return

    for m in members:
        chapa = m["Chapa"]
        df = escala.get(chapa)
        if df is None or df.empty:
            continue

        # encontra primeiro domingo não-férias
        first_idx = None
        first_status = None
        for di in domingos:
            if df.loc[di, "Status"] == "FÉRIAS":
                continue
            first_idx = di
            first_status = df.loc[di, "Status"]
            break
        if first_idx is None:
            continue

        # alterna nos próximos domingos
        expected = first_status
        for di in domingos:
            if di == first_idx:
                expected = first_status
                continue
            if df.loc[di, "Status"] == "FÉRIAS":
                continue
            # alterna
            expected = "Folga" if expected == "Trabalho" else "Trabalho"
            df.loc[di, "Status"] = expected

        escala[chapa] = df

# =========================================================
# Excel RH (azul/verde) por Subgrupo
# =========================================================
def build_excel_rh(setor: str, ano: int, mes: int, escala: Dict[str, pd.DataFrame]) -> bytes:
    colabs = load_colaboradores_setor(setor)
    if not colabs or not escala:
        return b""

    # mapa chapa->info
    info = {c["Chapa"]: c for c in colabs}
    # organiza por subgrupo
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

        # estilos
        blue = PatternFill(start_color="1F4E79", end_color="1F4E79", patternType="solid")
        green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", patternType="solid")  # folga
        green2 = PatternFill(start_color="A9D08E", end_color="A9D08E", patternType="solid")  # ferias
        sunday = PatternFill(start_color="BDD7EE", end_color="BDD7EE", patternType="solid")  # domingo col
        header_font = Font(color="FFFFFF", bold=True)
        border = Border(left=Side(style="thin"), right=Side(style="thin"),
                        top=Side(style="thin"), bottom=Side(style="thin"))
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # cabeçalho geral
        ws.cell(1, 1, f"SETOR: {setor}  |  MÊS: {mes:02d}/{ano}").fill = blue
        ws.cell(1, 1).font = header_font
        ws.cell(1, 1).alignment = Alignment(horizontal="left", vertical="center")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ndays + 2)

        # linha 2 e 3: dias e dia da semana
        ws.cell(2, 1, "COLABORADOR").fill = blue
        ws.cell(3, 1, "").fill = blue
        ws.cell(2, 1).font = header_font
        ws.cell(2, 1).alignment = center
        ws.cell(3, 1).alignment = center
        ws.merge_cells(start_row=2, start_column=1, end_row=3, end_column=1)

        for i, d in enumerate(dates):
            col = i + 2
            ws.cell(2, col, d.day).fill = blue
            ws.cell(2, col).font = header_font
            ws.cell(2, col).alignment = center
            ws.cell(3, col, day_sem_pt(d)).alignment = center
            ws.cell(3, col).fill = sunday if day_sem_pt(d) == "dom" else PatternFill()
            ws.cell(2, col).border = border
            ws.cell(3, col).border = border

        row = 4
        for sg, chapas in by_sg.items():
            # título do subgrupo
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

                # duas linhas: entrada/saída
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

                    # cores
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

        # ajustar largura
        ws.column_dimensions["A"].width = 28
        for i in range(2, ndays + 2):
            ws.column_dimensions[get_column_letter(i)].width = 6

        # remove sheet default se existir
        if "Sheet" in wb.sheetnames and wb["Sheet"].max_row == 1 and wb["Sheet"].max_column == 1:
            wb.remove(wb["Sheet"])

    return output.getvalue()

# =========================================================
# UI
# =========================================================
db_init()

if "auth" not in st.session_state:
    st.session_state["auth"] = None

# estado de escala carregada na sessão
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

def page_admin_panel():
    st.subheader("🔒 Painel ADMIN — Gestão de Usuários (restrito)")
    df_users = admin_list_users()
    st.dataframe(df_users, use_container_width=True)

    st.markdown("### ✏️ Editar usuário")
    if df_users.empty:
        st.info("Sem usuários.")
        return

    user_id = st.selectbox("Selecionar ID:", df_users["id"].tolist(), key="adm_user_id")
    urow = df_users[df_users["id"] == user_id].iloc[0]

    c1, c2, c3 = st.columns(3)
    nome = c1.text_input("Nome:", value=str(urow["nome"]), key="adm_nome")
    setor_new = c2.text_input("Setor:", value=str(urow["setor"]), key="adm_setor").strip().upper()
    chapa_new = c3.text_input("Chapa:", value=str(urow["chapa"]), key="adm_chapa")

    c4, c5, c6 = st.columns(3)
    is_admin = c4.checkbox("Admin?", value=bool(urow["is_admin"]), key="adm_isadmin")
    is_lider = c5.checkbox("Líder?", value=bool(urow["is_lider"]), key="adm_islider")
    reset_senha = c6.checkbox("Resetar senha", key="adm_resetsenha")

    nova_senha = ""
    if reset_senha:
        nova_senha = st.text_input("Nova senha:", type="password", key="adm_nova_senha")

    colx1, colx2 = st.columns(2)
    if colx1.button("Salvar", key="adm_save"):
        admin_update_user(user_id, nome.strip(), setor_new, chapa_new.strip(), is_admin, is_lider)
        if reset_senha and nova_senha:
            update_password(setor_new, chapa_new.strip(), nova_senha)
        st.success("Atualizado!")
        st.rerun()

    if colx2.button("Excluir", key="adm_del"):
        if int(user_id) == 1:
            st.error("Não pode excluir admin principal.")
        else:
            admin_delete_user(user_id)
            st.warning("Removido!")
            st.rerun()

def page_setor_full(setor: str):
    st.title(f"📌 Sistema — Setor: {setor}")
    aba1, aba2, aba3, aba4, aba5 = st.tabs(
        ["👥 Colaboradores", "🚀 Gerar Escala", "⚙️ Ajustes", "🏖️ Férias", "📥 Excel"]
    )

    # -------------------------------
    # Aba 1: Colaboradores + Subgrupos
    # -------------------------------
    with aba1:
        st.subheader("Colaboradores (sem senha)")
        colaboradores = load_colaboradores_setor(setor)
        if colaboradores:
            st.dataframe(pd.DataFrame([{
                "Nome": c["Nome"],
                "Chapa": c["Chapa"],
                "Subgrupo": c["Subgrupo"] or "SEM SUBGRUPO",
                "Entrada": c["Entrada"],
                "Folga sábado": "Sim" if c["Folga_Sab"] else "Não",
            } for c in colaboradores]), use_container_width=True)
        else:
            st.info("Sem colaboradores.")

        st.markdown("---")
        st.markdown("## Subgrupos + Preferência (evitar folga)")
        subgrupos = list_subgrupos(setor)

        cA, cB = st.columns(2)
        with cA:
            novo_sub = st.text_input("Novo subgrupo:", key="sg_new")
            if st.button("Adicionar subgrupo", key="sg_add"):
                add_subgrupo(setor, novo_sub)
                st.rerun()
        with cB:
            if subgrupos:
                del_sel = st.selectbox("Remover subgrupo:", ["(nenhum)"] + subgrupos, key="sg_del")
                if del_sel != "(nenhum)" and st.button("Remover", key="sg_del_btn"):
                    delete_subgrupo(setor, del_sel)
                    st.rerun()

        if subgrupos:
            sg_sel = st.selectbox("Escolha o subgrupo:", subgrupos, key="pref_sg_sel")
            regras = get_subgrupo_regras(setor, sg_sel)

            p1, p2, p3 = st.columns(3)
            ev_seg = p1.checkbox("Evitar folga SEG", value=bool(regras["seg"]), key=f"ev_seg_{sg_sel}")
            ev_ter = p1.checkbox("Evitar folga TER", value=bool(regras["ter"]), key=f"ev_ter_{sg_sel}")
            ev_qua = p2.checkbox("Evitar folga QUA", value=bool(regras["qua"]), key=f"ev_qua_{sg_sel}")
            ev_qui = p2.checkbox("Evitar folga QUI", value=bool(regras["qui"]), key=f"ev_qui_{sg_sel}")
            ev_sex = p3.checkbox("Evitar folga SEX", value=bool(regras["sex"]), key=f"ev_sex_{sg_sel}")
            ev_sab = p3.checkbox("Evitar folga SÁB", value=bool(regras["sáb"]), key=f"ev_sab_{sg_sel}")

            if st.button("Salvar preferência", key="pref_save"):
                set_subgrupo_regras(setor, sg_sel, {
                    "seg": int(ev_seg), "ter": int(ev_ter), "qua": int(ev_qua),
                    "qui": int(ev_qui), "sex": int(ev_sex), "sáb": int(ev_sab)
                })
                st.success("Salvo!")
                st.rerun()

        st.markdown("---")
        st.markdown("## ➕ Cadastrar colaborador (sem senha)")
        c1, c2 = st.columns(2)
        nome_n = c1.text_input("Nome:", key="col_nome")
        chapa_n = c2.text_input("Chapa:", key="col_chapa")
        if st.button("Cadastrar", key="col_add"):
            if not nome_n or not chapa_n:
                st.error("Preencha.")
            elif colaborador_exists(setor, chapa_n.strip()):
                st.error("Já existe.")
            else:
                create_colaborador(nome_n.strip(), setor, chapa_n.strip())
                st.success("Cadastrado!")
                st.rerun()

        st.markdown("---")
        st.markdown("## ✏️ Editar perfil do colaborador")
        colaboradores = load_colaboradores_setor(setor)
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

    # -------------------------------
    # Aba 2: Gerar Escala
    # -------------------------------
    with aba2:
        st.subheader("🚀 Gerar escala do mês")
        c1, c2, c3 = st.columns(3)
        ano = c1.number_input("Ano", min_value=2020, max_value=2100, value=st.session_state["escala_ano"], key="gen_ano")
        mes = c2.selectbox("Mês", list(range(1, 13)), index=int(st.session_state["escala_mes"]) - 1, key="gen_mes")
        seed = c3.number_input("Semente (mude para embaralhar)", min_value=0, max_value=999999, value=0, key="gen_seed")

        if st.button("🚀 GERAR", key="gen_btn"):
            escala, estado = generate_schedule_setor(setor, int(ano), int(mes), seed=int(seed))
            if not escala:
                st.error("Sem colaboradores para gerar.")
            else:
                # salva em DB
                clear_escala_mes(setor, int(ano), int(mes))
                save_escala_mes(setor, int(ano), int(mes), escala)
                save_estado_mes(setor, int(ano), int(mes), estado)
                st.session_state["escala_cache"] = escala
                st.session_state["escala_ano"] = int(ano)
                st.session_state["escala_mes"] = int(mes)
                st.success("Escala gerada e salva no banco!")
                st.rerun()

        # carregar do banco
        if st.button("📥 Carregar escala do banco", key="load_db_btn"):
            escala = load_escala_mes(setor, int(ano), int(mes))
            st.session_state["escala_cache"] = escala
            st.session_state["escala_ano"] = int(ano)
            st.session_state["escala_mes"] = int(mes)
            st.success("Carregada!")
            st.rerun()

        escala_cache = st.session_state.get("escala_cache", {})
        if escala_cache:
            st.markdown("### Visualizar (por colaborador)")
            colabs = load_colaboradores_setor(setor)
            map_nome = {c["Chapa"]: c["Nome"] for c in colabs}
            chapas = sorted(list(escala_cache.keys()), key=lambda ch: map_nome.get(ch, ch))
            ch_sel = st.selectbox("Colaborador:", chapas, format_func=lambda ch: f"{map_nome.get(ch,'')} ({ch})", key="vis_ch")
            st.dataframe(escala_cache[ch_sel], use_container_width=True)

    # -------------------------------
    # Aba 3: Ajustes
    # -------------------------------
    with aba3:
        st.subheader("⚙️ Ajustes na escala")
        ano = st.session_state.get("escala_ano", datetime.now().year)
        mes = st.session_state.get("escala_mes", datetime.now().month)

        escala_cache = st.session_state.get("escala_cache", {})
        if not escala_cache:
            st.warning("Carregue ou gere uma escala na aba 'Gerar Escala'.")
        else:
            colabs = load_colaboradores_setor(setor)
            info = {c["Chapa"]: c for c in colabs}
            chapas = sorted(list(escala_cache.keys()), key=lambda ch: info.get(ch, {}).get("Nome", ch))

            tabA, tabB, tabC, tabD = st.tabs(["🔄 Trocar folga", "🕒 Trocar horário (dia)", "🗓️ Trocar horário (mês)", "👥 Trocar subgrupo"])

            with tabA:
                ch = st.selectbox("Colaborador:", chapas, format_func=lambda x: f"{info.get(x,{}).get('Nome','')} ({x})", key="aj_ch1")
                df = escala_cache[ch].copy()
                folgas = df[df["Status"] == "Folga"]["DiaMes"].tolist()
                if not folgas:
                    st.info("Sem folgas para trocar.")
                else:
                    d_tira = st.selectbox("Dia que vai virar TRABALHO:", folgas, key="aj_d_tira")
                    d_poe = st.number_input("Dia que vai virar FOLGA:", min_value=1, max_value=len(df), value=1, key="aj_d_poe")

                    if st.button("Aplicar troca", key="aj_btn_troca"):
                        # aplica
                        df.loc[df["DiaMes"] == int(d_tira), "Status"] = "Trabalho"
                        df.loc[df["DiaMes"] == int(d_poe), "Status"] = "Folga"

                        # se for domingo alterado, aplica rodízio nos próximos domingos do subgrupo
                        subgrupo = (info[ch].get("Subgrupo") or "").strip() or "SEM SUBGRUPO"
                        escala_cache[ch] = df
                        apply_sunday_rodizio_after_manual(setor, int(ano), int(mes), escala_cache, subgrupo)

                        # recalcula horários do colaborador afetado
                        entrada_padrao = info[ch]["Entrada"]
                        for i in range(len(df)):
                            if df.loc[i, "Status"] in ("Folga", "FÉRIAS"):
                                df.loc[i, "Entrada"] = ""
                                df.loc[i, "Saida"] = ""
                            else:
                                ent = entrada_padrao
                                if i > 0 and df.loc[i-1, "Saida"]:
                                    ent = calcular_entrada_segura(df.loc[i-1, "Saida"], entrada_padrao)
                                df.loc[i, "Entrada"] = ent
                                df.loc[i, "Saida"] = add_hours_str(ent, DURACAO_JORNADA)

                        escala_cache[ch] = df

                        # salva no banco
                        clear_escala_mes(setor, int(ano), int(mes))
                        save_escala_mes(setor, int(ano), int(mes), escala_cache)
                        st.session_state["escala_cache"] = escala_cache
                        st.success("Troca aplicada e salva!")
                        st.rerun()

            with tabB:
                ch = st.selectbox("Colaborador:", chapas, format_func=lambda x: f"{info.get(x,{}).get('Nome','')} ({x})", key="aj_ch2")
                df = escala_cache[ch].copy()
                dia = st.number_input("Dia do mês:", min_value=1, max_value=len(df), value=1, key="aj_dia_hr")
                nova_ent = st.time_input("Nova entrada:", value=datetime.strptime(info[ch]["Entrada"], "%H:%M").time(), key="aj_hr_ent")

                if st.button("Salvar horário do dia", key="aj_btn_hr_dia"):
                    idx = int(dia) - 1
                    if df.loc[idx, "Status"] in ("Folga", "FÉRIAS"):
                        st.error("Dia é Folga/Férias — não tem horário.")
                    else:
                        ent_str = nova_ent.strftime("%H:%M")
                        df.loc[idx, "Entrada"] = ent_str
                        df.loc[idx, "Saida"] = add_hours_str(ent_str, DURACAO_JORNADA)

                        escala_cache[ch] = df
                        clear_escala_mes(setor, int(ano), int(mes))
                        save_escala_mes(setor, int(ano), int(mes), escala_cache)
                        st.session_state["escala_cache"] = escala_cache
                        st.success("Horário alterado e salvo!")
                        st.rerun()

            with tabC:
                ch = st.selectbox("Colaborador:", chapas, format_func=lambda x: f"{info.get(x,{}).get('Nome','')} ({x})", key="aj_ch3")
                df = escala_cache[ch].copy()
                nova_ent_mes = st.time_input("Nova entrada (mês inteiro):", value=datetime.strptime(info[ch]["Entrada"], "%H:%M").time(), key="aj_hr_mes")

                if st.button("Aplicar no mês inteiro", key="aj_btn_hr_mes"):
                    ent_str = nova_ent_mes.strftime("%H:%M")
                    for i in range(len(df)):
                        if df.loc[i, "Status"] == "Trabalho":
                            # respeita interstício
                            if i > 0 and df.loc[i-1, "Saida"]:
                                ent = calcular_entrada_segura(df.loc[i-1, "Saida"], ent_str)
                            else:
                                ent = ent_str
                            df.loc[i, "Entrada"] = ent
                            df.loc[i, "Saida"] = add_hours_str(ent, DURACAO_JORNADA)
                    escala_cache[ch] = df
                    clear_escala_mes(setor, int(ano), int(mes))
                    save_escala_mes(setor, int(ano), int(mes), escala_cache)
                    st.session_state["escala_cache"] = escala_cache
                    st.success("Horário mensal aplicado e salvo!")
                    st.rerun()

            with tabD:
                ch = st.selectbox("Colaborador:", chapas, format_func=lambda x: f"{info.get(x,{}).get('Nome','')} ({x})", key="aj_ch4")
                sg_opts = [""] + list_subgrupos(setor)
                current = (info[ch].get("Subgrupo") or "").strip()
                idx_def = sg_opts.index(current) if current in sg_opts else 0
                novo_sg = st.selectbox("Novo subgrupo:", sg_opts, index=idx_def, key="aj_sg_new")

                if st.button("Salvar subgrupo", key="aj_btn_sg"):
                    update_colaborador_perfil(setor, ch, novo_sg, info[ch]["Entrada"], bool(info[ch]["Folga_Sab"]))
                    st.success("Subgrupo alterado. Gere novamente para aplicar domingo 1x1 por subgrupo.")
                    st.rerun()

            st.markdown("### Visualização rápida (escala atual)")
            ch_show = st.selectbox("Visualizar:", chapas, format_func=lambda x: f"{info.get(x,{}).get('Nome','')} ({x})", key="aj_view")
            st.dataframe(escala_cache[ch_show], use_container_width=True)

    # -------------------------------
    # Aba 4: Férias
    # -------------------------------
    with aba4:
        st.subheader("🏖️ Férias (lança automático na escala)")
        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Cadastre colaboradores.")
        else:
            chapas = [c["Chapa"] for c in colaboradores]
            map_nome = {c["Chapa"]: c["Nome"] for c in colaboradores}

            ch = st.selectbox("Colaborador:", chapas, format_func=lambda x: f"{map_nome.get(x,'')} ({x})", key="fer_ch")
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

            df_f = list_ferias(setor)
            if not df_f.empty:
                st.dataframe(df_f, use_container_width=True)
                st.markdown("### Remover férias")
                idx = st.number_input("Linha para remover (1..N):", min_value=1, max_value=len(df_f), value=1, key="fer_rm_idx")
                if st.button("Remover", key="fer_rm_btn"):
                    r = df_f.iloc[int(idx) - 1]
                    delete_ferias_row(setor, r["chapa"], r["inicio"], r["fim"])
                    st.success("Removido!")
                    st.rerun()
            else:
                st.info("Sem férias cadastradas.")

    # -------------------------------
    # Aba 5: Excel
    # -------------------------------
    with aba5:
        st.subheader("📥 Excel modelo RH")
        ano = st.session_state.get("escala_ano", datetime.now().year)
        mes = st.session_state.get("escala_mes", datetime.now().month)
        escala_cache = st.session_state.get("escala_cache", {})

        if not escala_cache:
            st.warning("Gere ou carregue a escala antes.")
        else:
            if st.button("Gerar Excel", key="xl_btn"):
                xbytes = build_excel_rh(setor, int(ano), int(mes), escala_cache)
                if not xbytes:
                    st.error("Falha ao gerar.")
                else:
                    st.download_button(
                        "⬇️ Baixar Excel",
                        data=xbytes,
                        file_name=f"Escala_{setor}_{mes:02d}_{ano}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_excel"
                    )

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

    # ✅ Usuários do setor VEEM tudo
    page_setor_full(setor)

    # ✅ Painel ADMIN restrito
    if auth.get("is_admin", False) and setor == "ADMIN":
        st.markdown("---")
        page_admin_panel()

# =========================================================
# MAIN
# =========================================================
db_init()

if st.session_state["auth"] is None:
    page_login()
else:
    page_app()
