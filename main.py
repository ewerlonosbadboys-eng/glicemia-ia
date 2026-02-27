# app.py
# =========================================================
# PROJETO ESCALA 5x2 OFICIAL — VERSÃO COMPLETA
# =========================================================
# ✅ Login por setor (somente LÍDER/ADMIN tem senha)
# ✅ Colaboradores do setor (SEM senha) — cadastro dentro do setor logado
# ✅ Subgrupos editáveis por setor (criar/remover)
# ✅ Perfil do colaborador persistente (subgrupo, entrada, folga sábado)
# ✅ Escala 5x2 semanal (SEG→DOM) + domingo 1x1 + sábado só folga se marcado
# ✅ Interstício automático 11h10 + limite 5 dias seguidos
# ✅ Balanceamento de folgas por dia + por horário
# ✅ Aba Ajustes: por dia + trocar horário mês inteiro + se mexer no domingo ajusta próximos domingos
# ✅ Aba Férias: cadastra férias e lança automaticamente na escala
# ✅ Excel modelo RH (azul/verde + domingos vermelho + folga + férias)
# ✅ Escala corrida: mês seguinte lê estado do mês anterior
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

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Escala 5x2 Oficial", layout="wide")

DB_PATH = "escala.db"

INTERSTICIO_MIN = timedelta(hours=11, minutes=10)
DURACAO_JORNADA = timedelta(hours=9, minutes=58)

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


def db_init():
    con = db_conn()
    cur = con.cursor()

    # Setores
    cur.execute("""
    CREATE TABLE IF NOT EXISTS setores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    )
    """)

    # Usuários do SISTEMA (somente quem loga: líder/admin)
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

    # Colaboradores (SEM senha) — entram na escala
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

    # Subgrupos editáveis por setor
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subgrupos_setor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        nome TEXT NOT NULL,
        UNIQUE(setor, nome)
    )
    """)

    # Férias
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ferias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        inicio TEXT NOT NULL,
        fim TEXT NOT NULL
    )
    """)

    # Estado mês anterior (escala corrida)
    cur.execute("""
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

    # Escala do mês (salva por dia)
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

    con.commit()

    # setores básicos
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("GERAL",))
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("ADMIN",))
    con.commit()

    # Admin padrão: setor ADMIN | chapa admin | senha 123
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
# AUTH (só líderes/admin)
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
        return {
            "nome": nome,
            "setor": setor,
            "chapa": chapa,
            "is_admin": bool(is_admin),
            "is_lider": bool(is_lider),
        }
    return None


def is_lider_chapa(setor: str, chapa_lider: str) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT is_lider
        FROM usuarios_sistema
        WHERE setor=? AND chapa=?
        LIMIT 1
    """, (setor, chapa_lider))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0] == 1)


def update_password(setor: str, chapa: str, nova_senha: str):
    salt = secrets.token_hex(16)
    senha_hash = hash_password(nova_senha, salt)
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        UPDATE usuarios_sistema
        SET senha_hash=?, salt=?
        WHERE setor=? AND chapa=?
    """, (senha_hash, salt, setor, chapa))
    con.commit()
    con.close()


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
        "Subgrupo": r[2] or "",
        "Entrada": r[3] or "06:00",
        "Folga_Sab": bool(r[4]),
        "Setor": setor,
        "Categoria": setor,  # compatibilidade com motor (categoria= setor)
    } for r in rows]


# =========================================================
# SUBGRUPOS (editável)
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
    con.commit()
    con.close()


def delete_subgrupo(setor: str, nome: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("DELETE FROM subgrupos_setor WHERE setor=? AND nome=?", (setor, nome))
    # remove vínculo no perfil
    cur.execute("UPDATE colaboradores SET subgrupo='' WHERE setor=? AND subgrupo=?", (setor, nome))
    con.commit()
    con.close()


# =========================================================
# FÉRIAS
# =========================================================
def add_ferias(setor: str, chapa: str, inicio: date, fim: date):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO ferias(setor, chapa, inicio, fim)
        VALUES (?, ?, ?, ?)
    """, (setor, chapa, inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")))
    con.commit()
    con.close()


def list_ferias(setor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT chapa, inicio, fim
        FROM ferias
        WHERE setor=?
        ORDER BY date(inicio) ASC
    """, (setor,))
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
        estado[chapa] = {
            "consec_trab_final": int(consec),
            "ultima_saida": ultima_saida or "",
            "ultimo_domingo_status": ultimo_dom
        }
    return estado


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
                row["Data"].strftime("%Y-%m-%d"),
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
            "Data": dt,
            "Dia": dia_sem,
            "Status": status,
            "H_Entrada": h_ent or "",
            "H_Saida": h_sai or "",
        })
    return {ch: pd.DataFrame(items) for ch, items in hist.items()}


# =========================================================
# MOTOR DE REGRAS
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


def _set_trabalho(df, idx, ent_padrao):
    df.loc[idx, "Status"] = "Trabalho"
    if not df.loc[idx, "H_Entrada"]:
        df.loc[idx, "H_Entrada"] = ent_padrao
    df.loc[idx, "H_Saida"] = _saida_from_entrada(df.loc[idx, "H_Entrada"])


def _set_folga(df, idx):
    df.loc[idx, "Status"] = "Folga"
    df.loc[idx, "H_Entrada"] = ""
    df.loc[idx, "H_Saida"] = ""


def _set_ferias(df, idx):
    df.loc[idx, "Status"] = "Férias"
    df.loc[idx, "H_Entrada"] = ""
    df.loc[idx, "H_Saida"] = ""


def recompute_hours_with_intersticio(df, ent_padrao, ultima_saida_prev: str | None = None):
    ents, sais = [], []
    first_work_done = False
    for i in range(len(df)):
        if df.loc[i, "Status"] != "Trabalho":
            ents.append("")
            sais.append("")
        else:
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
        if df.loc[i, "Status"] != "Trabalho":
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
        if df.loc[i, "Status"] == "Trabalho":
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


def _counts_folgas_day_and_hour(hist_by_chapa: dict, colab_by_chapa: dict, chapas_setor: list, idxs_semana: list, df_ref):
    counts_day = {i: 0 for i in idxs_semana}
    counts_day_hour = {}
    for ch in chapas_setor:
        df = hist_by_chapa[ch]
        bucket = colab_by_chapa[ch].get("Entrada", "06:00")
        for i in idxs_semana:
            if df_ref.loc[i, "Dia"] == "dom":
                continue
            if df.loc[i, "Status"] == "Folga":
                counts_day[i] += 1
                counts_day_hour[(i, bucket)] = counts_day_hour.get((i, bucket), 0) + 1
    return counts_day, counts_day_hour


def rebalance_folgas_dia(hist_by_chapa: dict, colab_by_chapa: dict, chapas_setor: list, weeks: list, df_ref, max_iters=1800):
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
            for ch in chapas_setor:
                df = hist_by_chapa[ch]
                for i in week_idxs:
                    if df.loc[i, "Status"] == "Folga":
                        counts[i] += 1
            mx = max(counts, key=lambda x: counts[x])
            mn = min(counts, key=lambda x: counts[x])
            if counts[mx] - counts[mn] <= 1:
                break
            candidates = [ch for ch in chapas_setor if hist_by_chapa[ch].loc[mx, "Status"] == "Folga" and hist_by_chapa[ch].loc[mn, "Status"] == "Trabalho"]
            random.shuffle(candidates)
            moved = False
            for ch in candidates:
                if can_swap(ch, mx, mn):
                    do_swap(ch, mx, mn)
                    moved = True
                    break
            if not moved:
                break


def gerar_escala_setor(setor: str, colaboradores: list[dict], ano: int, mes: int):
    datas = _dias_mes(ano, mes)
    weeks = _all_weeks_seg_dom(datas)
    domingos_idx = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]

    colab_by_chapa = {c["Chapa"]: c for c in colaboradores}
    chapas = [c["Chapa"] for c in colaboradores]

    estado_prev = load_estado_prev(setor, ano, mes)

    # Domingo 1x1: divide setor em dois grupos estáveis no mês
    chapas_sorted = sorted(chapas)
    rng = random.Random(9000 + ano + mes + len(chapas_sorted))
    chapas_sh = chapas_sorted[:]
    rng.shuffle(chapas_sh)
    meio = (len(chapas_sh) + 1) // 2
    grupo_a = set(chapas_sh[:meio])
    grupo_b = set(chapas_sh[meio:])

    # dfs base
    df_ref = pd.DataFrame({"Data": datas, "Dia": [D_PT[d.day_name()] for d in datas]})
    hist = {}
    for ch in chapas:
        df = df_ref.copy()
        df["Status"] = "Trabalho"
        df["H_Entrada"] = ""
        df["H_Saida"] = ""
        hist[ch] = df

    # férias + domingos
    for ch in chapas:
        df = hist[ch]
        ent = colab_by_chapa[ch].get("Entrada", "06:00")

        for i, d in enumerate(datas):
            if is_de_ferias(setor, ch, d.date()):
                _set_ferias(df, i)

        for k, dom_i in enumerate(domingos_idx):
            if df.loc[dom_i, "Status"] == "Férias":
                continue
            alvo_folga = grupo_a if (k % 2 == 0) else grupo_b
            if ch in alvo_folga:
                _set_folga(df, dom_i)
            else:
                _set_trabalho(df, dom_i, ent)

        # escala corrida: ajusta 1º domingo conforme mês anterior
        if ch in estado_prev and estado_prev[ch].get("ultimo_domingo_status") in ["Trabalho", "Folga"] and domingos_idx:
            primeiro_dom = domingos_idx[0]
            if df.loc[primeiro_dom, "Status"] != "Férias":
                if estado_prev[ch]["ultimo_domingo_status"] == "Trabalho":
                    _set_folga(df, primeiro_dom)
                else:
                    _set_trabalho(df, primeiro_dom, ent)
                enforce_sundays_alternating_for_employee(df, ent, primeiro_dom)

        hist[ch] = df

    # 5x2 por semana SEG->DOM, escolhendo folgas seg..sáb (sábado só se permitido)
    for week in weeks:
        cand_days = [i for i in week if df_ref.loc[i, "Dia"] != "dom"]
        for ch in chapas:
            df = hist[ch]
            pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))
            folgas_sem = int((df.loc[week, "Status"] == "Folga").sum())

            while folgas_sem < 2:
                counts_day, counts_day_hour = _counts_folgas_day_and_hour(hist, colab_by_chapa, chapas, cand_days, df_ref)
                bucket = colab_by_chapa[ch].get("Entrada", "06:00")

                possiveis = []
                for j in cand_days:
                    if df.loc[j, "Status"] != "Trabalho":
                        continue
                    if df_ref.loc[j, "Dia"] == "sáb" and not pode_sab:
                        continue
                    if not _nao_consecutiva_folga(df, j):
                        continue
                    possiveis.append(j)

                if not possiveis:
                    break

                random.shuffle(possiveis)

                def score(j):
                    weekday_prio = 0 if df_ref.loc[j, "Dia"] in ["seg", "ter", "qua", "qui", "sex"] else 1
                    return (
                        counts_day.get(j, 0),
                        counts_day_hour.get((j, bucket), 0),
                        weekday_prio
                    )

                possiveis.sort(key=score)
                pick = possiveis[0]
                _set_folga(df, pick)
                folgas_sem += 1
                hist[ch] = df

    # limite 5 dias seguidos + interstício
    for ch in chapas:
        df = hist[ch]
        ent = colab_by_chapa[ch].get("Entrada", "06:00")
        pode_sab = bool(colab_by_chapa[ch].get("Folga_Sab", False))

        # corrida: se mês anterior terminou com 5 dias seguidos, força 1 folga no primeiro dia útil
        if ch in estado_prev and int(estado_prev[ch].get("consec_trab_final", 0)) >= 5:
            for i in range(len(df)):
                if df.loc[i, "Status"] == "Trabalho" and df_ref.loc[i, "Dia"] in ["seg", "ter", "qua", "qui", "sex"]:
                    _set_folga(df, i)
                    break

        enforce_max_5_consecutive_work(df, ent, pode_sab)

        ultima_saida_prev = estado_prev.get(ch, {}).get("ultima_saida", "")
        recompute_hours_with_intersticio(df, ent, ultima_saida_prev=ultima_saida_prev)

        hist[ch] = df

    # rebalance final
    rebalance_folgas_dia(hist, colab_by_chapa, chapas, weeks, df_ref, max_iters=1800)

    # estado para próximo mês
    estado_out = {}
    for ch in chapas:
        df = hist[ch]

        consec = 0
        for i in range(len(df)-1, -1, -1):
            if df.loc[i, "Status"] == "Trabalho":
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

        estado_out[ch] = {
            "consec_trab_final": consec,
            "ultima_saida": ultima_saida,
            "ultimo_domingo_status": ultimo_dom
        }

    return hist, estado_out


# =========================================================
# UI
# =========================================================
if "auth" not in st.session_state:
    st.session_state["auth"] = None

db_init()


def page_login():
    st.title("🔐 Login por Setor (somente Líder/Admin)")

    tab_login, tab_cadastrar_lider, tab_esqueci = st.tabs(["Entrar", "Cadastrar Líder", "Esqueci a senha"])

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

    with tab_cadastrar_lider:
        st.subheader("Cadastrar usuário do sistema (Líder)")
        st.info("⚠️ Aqui cria usuário que FAZ LOGIN (líder/admin). Colaborador comum é cadastrado dentro do setor SEM senha.")
        nome = st.text_input("Nome:", key="cl_nome")
        setor = st.text_input("Setor:", key="cl_setor").strip().upper()
        chapa = st.text_input("Chapa:", key="cl_chapa")
        senha = st.text_input("Senha:", type="password", key="cl_senha")
        senha2 = st.text_input("Confirmar senha:", type="password", key="cl_senha2")
        is_admin = st.checkbox("É admin?", key="cl_admin")
        is_lider = st.checkbox("É líder?", value=True, key="cl_lider")

        if st.button("Criar usuário do sistema", key="cl_btn"):
            if not nome or not setor or not chapa or not senha:
                st.error("Preencha tudo.")
            elif senha != senha2:
                st.error("Senhas não conferem.")
            elif system_user_exists(setor, chapa):
                st.error("Já existe essa chapa nesse setor.")
            else:
                create_system_user(nome.strip(), setor, chapa.strip(), senha, is_lider=1 if is_lider else 0, is_admin=1 if is_admin else 0)
                st.success("Usuário do sistema criado! Faça login.")
                st.rerun()

    with tab_esqueci:
        st.subheader("Redefinir senha (com chapa do líder)")
        con = db_conn()
        setores = pd.read_sql_query("SELECT nome FROM setores ORDER BY nome ASC", con)["nome"].tolist()
        con.close()

        setor = st.selectbox("Setor:", setores, key="fp_setor")
        chapa = st.text_input("Sua chapa (usuário do sistema):", key="fp_chapa")
        chapa_lider = st.text_input("Chapa do líder do setor:", key="fp_lider")
        nova = st.text_input("Nova senha:", type="password", key="fp_nova")
        nova2 = st.text_input("Confirmar nova senha:", type="password", key="fp_nova2")

        if st.button("Redefinir", key="fp_btn"):
            if not chapa or not chapa_lider or not nova:
                st.error("Preencha todos os campos.")
            elif nova != nova2:
                st.error("Senhas não conferem.")
            elif not system_user_exists(setor, chapa):
                st.error("Usuário do sistema não encontrado nesse setor.")
            elif not is_lider_chapa(setor, chapa_lider):
                st.error("Chapa de líder inválida (precisa ser líder do mesmo setor).")
            else:
                update_password(setor, chapa, nova)
                st.success("Senha redefinida! Faça login.")
                st.rerun()


def page_app():
    auth = st.session_state["auth"]
    setor = auth["setor"]

    st.sidebar.title("👤 Sessão")
    st.sidebar.write(f"**Nome:** {auth['nome']}")
    st.sidebar.write(f"**Setor:** {setor}")
    st.sidebar.write(f"**Chapa:** {auth['chapa']}")
    st.sidebar.write(f"**Perfil:** {'ADMIN' if auth['is_admin'] else ('LÍDER' if auth['is_lider'] else 'USUÁRIO')}")

    if st.sidebar.button("Sair", key="logout_btn"):
        st.session_state["auth"] = None
        st.rerun()

    if "cfg_mes" not in st.session_state:
        st.session_state["cfg_mes"] = datetime.now().month
    if "cfg_ano" not in st.session_state:
        st.session_state["cfg_ano"] = datetime.now().year

    st.title(f"📅 Escala 5x2 — Setor: {setor}")
    st.caption("Regras: 5x2 SEG→DOM | Domingo 1x1 | Sábado só folga se permitido | Interstício 11h10 | Máx 5 dias seguidos | Balanceamento dia+horário | Escala corrida mês anterior.")

    aba1, aba2, aba3, aba4, aba5 = st.tabs(["👥 Colaboradores", "🚀 Gerar Escala", "⚙️ Ajustes", "🏖️ Férias", "📥 Excel"])

    # ---------------- ABA 1: COLABORADORES ----------------
    with aba1:
        st.subheader("Colaboradores do setor (SEM senha)")

        colaboradores = load_colaboradores_setor(setor)
        if colaboradores:
            st.dataframe(pd.DataFrame([{
                "Nome": c["Nome"],
                "Chapa": c["Chapa"],
                "Subgrupo": c["Subgrupo"],
                "Entrada": c["Entrada"],
                "Folga sábado?": "Sim" if c["Folga_Sab"] else "Não",
            } for c in colaboradores]), use_container_width=True)
        else:
            st.info("Ainda não há colaboradores no setor.")

        st.markdown("---")
        st.markdown("### 📌 Subgrupos do setor (editável)")
        col1, col2, col3 = st.columns([2, 2, 2])
        subgrupos = list_subgrupos(setor)
        novo_sub = col1.text_input("Novo subgrupo:", key="sg_new")
        if col2.button("Adicionar subgrupo", key="sg_add"):
            add_subgrupo(setor, novo_sub)
            st.rerun()

        if subgrupos:
            del_sel = col3.selectbox("Remover subgrupo:", ["(nenhum)"] + subgrupos, key="sg_del")
            if del_sel != "(nenhum)" and col3.button("Remover", key="sg_del_btn"):
                delete_subgrupo(setor, del_sel)
                st.rerun()

        st.markdown("---")
        st.markdown("### ➕ Cadastrar novo colaborador (SEM senha) — setor vem do login")
        c1, c2 = st.columns(2)
        nome_n = c1.text_input("Nome:", key="col_nome")
        chapa_n = c2.text_input("Chapa:", key="col_chapa")

        if st.button("Cadastrar colaborador", key="col_add"):
            if not nome_n or not chapa_n:
                st.error("Preencha nome e chapa.")
            elif colaborador_exists(setor, chapa_n.strip()):
                st.error("Já existe essa chapa no setor.")
            else:
                create_colaborador(nome_n.strip(), setor, chapa_n.strip())
                st.success("Colaborador cadastrado!")
                st.rerun()

        st.markdown("---")
        st.markdown("### ✏️ Editar perfil do colaborador (entrada / subgrupo / folga sábado)")
        if colaboradores:
            chapas = [c["Chapa"] for c in colaboradores]
            ch_sel = st.selectbox("Chapa:", chapas, key="pf_chapa")
            csel = next(x for x in colaboradores if x["Chapa"] == ch_sel)

            colp1, colp2, colp3 = st.columns(3)
            ent = colp1.time_input("Entrada padrão:", value=datetime.strptime(csel["Entrada"], "%H:%M").time(), key="pf_ent")
            sg_opts = [""] + list_subgrupos(setor)
            idx_default = sg_opts.index(csel["Subgrupo"]) if csel["Subgrupo"] in sg_opts else 0
            sg = colp2.selectbox("Subgrupo:", sg_opts, index=idx_default, key="pf_sg")
            sab = colp3.checkbox("Permitir folga no sábado", value=bool(csel["Folga_Sab"]), key="pf_sab")

            if st.button("Salvar perfil", key="pf_save"):
                update_colaborador_perfil(setor, ch_sel, sg, ent.strftime("%H:%M"), sab)
                st.success("Perfil atualizado!")
                st.rerun()

        if auth["is_lider"] or auth["is_admin"]:
            st.markdown("---")
            st.markdown("### 🛡️ (Líder/Admin) Criar usuário do sistema no setor (com senha)")
            colL1, colL2, colL3 = st.columns(3)
            nome_l = colL1.text_input("Nome:", key="l_nome")
            chapa_l = colL2.text_input("Chapa:", key="l_chapa")
            senha_l = colL3.text_input("Senha:", type="password", key="l_senha")
            is_admin = st.checkbox("Admin?", key="l_admin")
            is_lider = st.checkbox("Líder?", value=True, key="l_lider")

            if st.button("Criar usuário do sistema", key="l_create"):
                if not nome_l or not chapa_l or not senha_l:
                    st.error("Preencha tudo.")
                elif system_user_exists(setor, chapa_l.strip()):
                    st.error("Já existe essa chapa no setor.")
                else:
                    create_system_user(nome_l.strip(), setor, chapa_l.strip(), senha_l, is_lider=1 if is_lider else 0, is_admin=1 if is_admin else 0)
                    st.success("Usuário do sistema criado!")
                    st.rerun()

    # ---------------- ABA 2: GERAR ----------------
    with aba2:
        st.subheader("Gerar escala do mês")
        c1, c2 = st.columns(2)
        mes = c1.selectbox("Mês:", list(range(1, 13)), index=st.session_state["cfg_mes"] - 1, key="gen_mes")
        ano = c2.number_input("Ano:", value=st.session_state["cfg_ano"], step=1, key="gen_ano")
        st.session_state["cfg_mes"] = int(mes)
        st.session_state["cfg_ano"] = int(ano)

        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Cadastre colaboradores na aba Colaboradores.")
        else:
            if st.button("🚀 Gerar agora", key="gen_btn"):
                hist, estado_out = gerar_escala_setor(setor, colaboradores, int(ano), int(mes))
                save_escala_mes_db(setor, int(ano), int(mes), hist)
                save_estado_mes(setor, int(ano), int(mes), estado_out)
                st.success("Escala gerada e salva no banco.")
                st.rerun()

            hist_db = load_escala_mes_db(setor, int(ano), int(mes))
            if hist_db:
                st.markdown("### Escala salva")
                ch_view = st.selectbox("Ver colaborador:", list(hist_db.keys()), key="view_ch")
                st.dataframe(hist_db[ch_view], use_container_width=True)
            else:
                st.info("Ainda não existe escala salva neste mês.")

    # ---------------- ABA 3: AJUSTES ----------------
    with aba3:
        st.subheader("Ajustes")
        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = load_escala_mes_db(setor, ano, mes)
        colaboradores = load_colaboradores_setor(setor)
        colab_by = {c["Chapa"]: c for c in colaboradores}

        if not hist_db:
            st.info("Gere a escala primeiro.")
        else:
            t1, t2 = st.tabs(["🔧 Ajuste por dia", "📅 Trocar horário mês inteiro"])

            with t1:
                ch = st.selectbox("Chapa:", list(hist_db.keys()), key="adj_ch")
                df = hist_db[ch].copy()
                ent_pad = colab_by.get(ch, {}).get("Entrada", "06:00")
                pode_sab = bool(colab_by.get(ch, {}).get("Folga_Sab", False))

                col1, col2, col3 = st.columns(3)
                dia_sel = col1.number_input("Dia do mês:", 1, len(df), value=1, key="adj_dia")
                acao = col2.selectbox("Ação:", ["Marcar Trabalho", "Marcar Folga", "Marcar Férias", "Alterar Entrada"], key="adj_acao")
                nova_ent = col3.time_input("Nova entrada:", value=datetime.strptime(ent_pad, "%H:%M").time(), key="adj_ent")

                if st.button("Aplicar", key="adj_apply"):
                    idx = int(dia_sel) - 1
                    dia_sem = df.loc[idx, "Dia"]

                    if acao == "Marcar Férias":
                        _set_ferias(df, idx)
                    elif acao == "Marcar Folga":
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode folga em férias.")
                        elif dia_sem == "sáb" and not pode_sab:
                            st.error("Sábado só folga se permitir no perfil.")
                        else:
                            _set_folga(df, idx)
                    elif acao == "Marcar Trabalho":
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode trabalho em férias.")
                        else:
                            e = nova_ent.strftime("%H:%M")
                            df.loc[idx, "H_Entrada"] = e
                            _set_trabalho(df, idx, e)
                    else:
                        if df.loc[idx, "Status"] != "Trabalho":
                            st.error("Só altera entrada em trabalho.")
                        else:
                            e = nova_ent.strftime("%H:%M")
                            df.loc[idx, "H_Entrada"] = e
                            df.loc[idx, "H_Saida"] = _saida_from_entrada(e)

                    # se mexer no domingo, propaga alternância
                    if df.loc[idx, "Data"].day_name() == "Sunday":
                        enforce_sundays_alternating_for_employee(df, ent_pad, idx)

                    enforce_max_5_consecutive_work(df, ent_pad, pode_sab)
                    recompute_hours_with_intersticio(df, ent_pad)

                    save_escala_mes_db(setor, ano, mes, {ch: df})
                    st.success("Ajuste salvo.")
                    st.rerun()

                st.dataframe(df, use_container_width=True)

            with t2:
                ch2 = st.selectbox("Chapa:", list(hist_db.keys()), key="adjm_ch")
                dfm = hist_db[ch2].copy()
                ent_pad2 = colab_by.get(ch2, {}).get("Entrada", "06:00")
                pode_sab2 = bool(colab_by.get(ch2, {}).get("Folga_Sab", False))

                nova_ent_mes = st.time_input("Nova entrada do mês:", value=datetime.strptime(ent_pad2, "%H:%M").time(), key="adjm_ent")

                if st.button("Aplicar mês inteiro", key="adjm_apply"):
                    e = nova_ent_mes.strftime("%H:%M")
                    for i in range(len(dfm)):
                        if dfm.loc[i, "Status"] == "Trabalho":
                            dfm.loc[i, "H_Entrada"] = e
                            dfm.loc[i, "H_Saida"] = _saida_from_entrada(e)

                    enforce_max_5_consecutive_work(dfm, e, pode_sab2)
                    recompute_hours_with_intersticio(dfm, e)

                    save_escala_mes_db(setor, ano, mes, {ch2: dfm})
                    st.success("Horário aplicado e salvo.")
                    st.rerun()

                st.dataframe(dfm, use_container_width=True)

    # ---------------- ABA 4: FÉRIAS ----------------
    with aba4:
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
                    st.success("Férias adicionadas. Gere/regenere a escala para refletir.")
                    st.rerun()

            rows = list_ferias(setor)
            if rows:
                st.dataframe(pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"]), use_container_width=True)
            else:
                st.info("Sem férias cadastradas.")

    # ---------------- ABA 5: EXCEL ----------------
    with aba5:
        st.subheader("Excel modelo RH")
        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = load_escala_mes_db(setor, ano, mes)
        colaboradores = load_colaboradores_setor(setor)
        colab_by = {c["Chapa"]: c for c in colaboradores}

        if not hist_db:
            st.info("Gere a escala primeiro.")
        else:
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

                    font_header = Font(color="FFFFFF", bold=True)
                    font_dom = Font(color="FFFFFF", bold=True)
                    font_ferias = Font(color="000000", bold=True)

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

                    chapas_sorted = sorted(hist_db.keys(), key=lambda ch: colab_by.get(ch, {}).get("Nome", ch))

                    row_idx = 3
                    for ch in chapas_sorted:
                        df_f = hist_db[ch]
                        nome = colab_by.get(ch, {}).get("Nome", ch)
                        sub = colab_by.get(ch, {}).get("Subgrupo", "")

                        c_nome = ws.cell(row_idx, 1, f"{nome}\nCHAPA: {ch}\nSUB: {sub}")
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
                                cell1.font = font_ferias
                            elif status == "Folga":
                                if dia_sem == "dom":
                                    cell1.fill = fill_dom; cell2.fill = fill_dom
                                    cell1.font = font_dom; cell2.font = font_dom
                                else:
                                    cell1.fill = fill_folga; cell2.fill = fill_folga
                                    cell1.font = Font(bold=True)

                        row_idx += 2

                    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
                        wb.remove(wb["Sheet"])

                st.download_button(
                    "📥 Baixar Excel",
                    data=output.getvalue(),
                    file_name=f"escala_{setor}_{mes:02d}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="xls_down"
                )


# =========================================================
# ROUTER
# =========================================================
if st.session_state["auth"] is None:
    page_login()
else:
    page_app()
