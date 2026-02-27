# app.py
# =========================================================
# Projeto Escala 5x2 Oficial
# ✅ Login por setor (usuário/senha)
# ✅ Cadastro pede: Nome, Setor, Chapa, Senha
# ✅ "Esqueci a senha": redefine usando CHAPA do LÍDER do setor
# ✅ Persistência real em SQLite (usuários + férias + escala + estado mês anterior)
# ✅ Suas regras já existentes continuam (5x2, domingo 1x1, interstício 11h10, balanceamento dia+horário)
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
# APP CONFIG
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
# SQLITE
# =========================================================
def db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


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
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        setor TEXT NOT NULL,
        chapa TEXT NOT NULL,
        senha_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        is_lider INTEGER NOT NULL DEFAULT 0,
        criado_em TEXT NOT NULL,
        UNIQUE(setor, chapa)
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

    # Escala salva por mês (entrada/saída/status por dia)
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

    # cria setor "GERAL" se vazio
    cur.execute("SELECT COUNT(*) FROM setores")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("GERAL",))
        con.commit()

    # cria ADMIN padrão se não existir (setor ADMIN)
    # login: admin / 123
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", ("ADMIN",))
    con.commit()

    if not user_exists("ADMIN", "admin"):
        create_user(nome="Administrador", setor="ADMIN", chapa="admin", senha="123", is_lider=1)

    con.close()


# =========================================================
# PASSWORDS / AUTH
# =========================================================
def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def user_exists(setor: str, chapa: str) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("SELECT 1 FROM usuarios WHERE setor=? AND chapa=? LIMIT 1", (setor, chapa))
    ok = cur.fetchone() is not None
    con.close()
    return ok


def create_user(nome: str, setor: str, chapa: str, senha: str, is_lider: int = 0):
    salt = secrets.token_hex(16)
    senha_hash = hash_password(senha, salt)
    con = db_conn()
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO setores(nome) VALUES (?)", (setor,))
    cur.execute("""
        INSERT INTO usuarios(nome, setor, chapa, senha_hash, salt, is_lider, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (nome, setor, chapa, senha_hash, salt, int(is_lider), datetime.now().isoformat()))
    con.commit()
    con.close()


def verify_login(setor: str, chapa: str, senha: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT nome, senha_hash, salt, is_lider
        FROM usuarios
        WHERE setor=? AND chapa=?
        LIMIT 1
    """, (setor, chapa))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    nome, senha_hash, salt, is_lider = row
    if hash_password(senha, salt) == senha_hash:
        return {"nome": nome, "setor": setor, "chapa": chapa, "is_lider": bool(is_lider)}
    return None


def is_lider_chapa(setor: str, chapa_lider: str) -> bool:
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT is_lider FROM usuarios
        WHERE setor=? AND chapa=? LIMIT 1
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
        UPDATE usuarios
        SET senha_hash=?, salt=?
        WHERE setor=? AND chapa=?
    """, (senha_hash, salt, setor, chapa))
    con.commit()
    con.close()


# =========================================================
# LOAD USERS (SETOR) as "colaboradores" da escala
# =========================================================
def load_users_setor(setor: str):
    con = db_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT nome, setor, chapa, is_lider
        FROM usuarios
        WHERE setor=?
        ORDER BY is_lider DESC, nome ASC
    """, (setor,))
    rows = cur.fetchall()
    con.close()

    # Para a escala, cada usuário tem Entrada e Folga_Sab guardadas em "perfil".
    # Como você ainda não pediu persistência desses campos em tabela própria,
    # vamos armazenar "Entrada" e "Folga_Sab" no session_state por setor, com fallback default.
    # ✅ Se quiser, eu crio a tabela perfil_colaborador depois.
    users = []
    for nome, setor, chapa, is_lider in rows:
        key = f"profile::{setor}::{chapa}"
        prof = st.session_state.get(key, {"Entrada": "06:00", "Folga_Sab": False, "Categoria": setor})
        users.append({
            "Nome": nome,
            "Setor": setor,
            "Chapa": chapa,
            "Entrada": prof.get("Entrada", "06:00"),
            "Folga_Sab": bool(prof.get("Folga_Sab", False)),
            "Categoria": prof.get("Categoria", setor),  # sua “categoria” aqui pode ser subsetor
            "is_lider": bool(is_lider),
        })
    return users


def save_profile(setor: str, chapa: str, entrada: str, folga_sab: bool, categoria: str):
    key = f"profile::{setor}::{chapa}"
    st.session_state[key] = {"Entrada": entrada, "Folga_Sab": bool(folga_sab), "Categoria": categoria}


# =========================================================
# FÉRIAS (DB)
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
        ORDER BY inicio ASC
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
# ESTADO MÊS ANTERIOR (DB)
# =========================================================
def save_estado_mes(setor: str, ano: int, mes: int, estado: dict):
    # estado: {chapa: {consec_trab_final, ultima_saida, ultimo_domingo_status}}
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
    # busca estado do mês anterior
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
# ESCALA DB (salvar / carregar)
# =========================================================
def save_escala_mes_db(setor: str, ano: int, mes: int, historico_df_por_chapa: dict[str, pd.DataFrame]):
    con = db_conn()
    cur = con.cursor()
    for chapa, df in historico_df_por_chapa.items():
        for i, row in df.iterrows():
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
        if chapa not in hist:
            hist[chapa] = []
        hist[chapa].append({
            "Data": dt,
            "Dia": dia_sem,
            "Status": status,
            "H_Entrada": h_ent or "",
            "H_Saida": h_sai or "",
        })

    out = {}
    for chapa, items in hist.items():
        out[chapa] = pd.DataFrame(items)
    return out


# =========================================================
# REGRAS (mesmas do seu app anterior)
# =========================================================
def _dias_mes(ano: int, mes: int):
    qtd = calendar.monthrange(ano, mes)[1]
    return pd.date_range(start=f"{ano}-{mes:02d}-01", periods=qtd, freq="D")


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


def _saida_from_entrada(ent: str) -> str:
    return (datetime.strptime(ent, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")


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


def _bucket_horario(user: dict) -> str:
    return user.get("Entrada", "06:00")


def _counts_folgas_day_and_hour(hist_by_chapa: dict, users_by_chapa: dict, chapas_setor: list, idxs_semana: list, df_ref):
    counts_day = {i: 0 for i in idxs_semana}
    counts_day_hour = {}
    for ch in chapas_setor:
        df = hist_by_chapa[ch]
        bucket = _bucket_horario(users_by_chapa[ch])
        for i in idxs_semana:
            if df_ref.loc[i, "Dia"] == "dom":
                continue
            if df.loc[i, "Status"] == "Folga":
                counts_day[i] += 1
                counts_day_hour[(i, bucket)] = counts_day_hour.get((i, bucket), 0) + 1
    return counts_day, counts_day_hour


def rebalance_folgas_dia(hist_by_chapa: dict, users_by_chapa: dict, chapas_setor: list, weeks: list, df_ref, max_iters=1800):
    def is_dom(i): return df_ref.loc[i, "Dia"] == "dom"

    def can_swap(ch, i_from, i_to):
        df = hist_by_chapa[ch]
        pode_sab = bool(users_by_chapa[ch].get("Folga_Sab", False))
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
        ent = users_by_chapa[ch].get("Entrada", "06:00")
        pode_sab = bool(users_by_chapa[ch].get("Folga_Sab", False))
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


def gerar_escala_setor(setor: str, users: list[dict], ano: int, mes: int):
    datas = _dias_mes(ano, mes)
    weeks = _all_weeks_seg_dom(datas)
    domingos_idx = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]

    users_by_chapa = {u["Chapa"]: u for u in users}
    chapas = [u["Chapa"] for u in users]

    # estado anterior (do mês anterior) vindo do DB
    estado_prev = load_estado_prev(setor, ano, mes)

    # Base domingo 1x1 (divide o setor em A/B de forma estável no mês)
    chapas_sorted = sorted(chapas)
    rng = random.Random(9000 + ano + mes + len(chapas_sorted))
    chapas_sh = chapas_sorted[:]
    rng.shuffle(chapas_sh)
    meio = (len(chapas_sh) + 1) // 2
    grupo_a = set(chapas_sh[:meio])
    grupo_b = set(chapas_sh[meio:])

    # cria dfs vazios
    hist = {}
    df_ref = pd.DataFrame({
        "Data": datas,
        "Dia": [D_PT[d.day_name()] for d in datas],
    })

    for ch in chapas:
        df = df_ref.copy()
        df["Status"] = "Trabalho"
        df["H_Entrada"] = ""
        df["H_Saida"] = ""
        hist[ch] = df

    # 1) férias + domingos base
    for ch in chapas:
        df = hist[ch]
        ent = users_by_chapa[ch].get("Entrada", "06:00")
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

        # ✅ escala corrida: ajusta 1º domingo conforme mês anterior
        if ch in estado_prev and estado_prev[ch].get("ultimo_domingo_status") in ["Trabalho", "Folga"] and domingos_idx:
            primeiro_dom = domingos_idx[0]
            if df.loc[primeiro_dom, "Status"] != "Férias":
                if estado_prev[ch]["ultimo_domingo_status"] == "Trabalho":
                    _set_folga(df, primeiro_dom)
                else:
                    _set_trabalho(df, primeiro_dom, ent)
                enforce_sundays_alternating_for_employee(df, ent, primeiro_dom)

        hist[ch] = df

    # 2) 5x2 por semana SEG->DOM, balanceando por DIA + HORÁRIO (mix)
    for week in weeks:
        cand_days = [i for i in week if df_ref.loc[i, "Dia"] != "dom"]  # seg..sáb
        for ch in chapas:
            df = hist[ch]
            pode_sab = bool(users_by_chapa[ch].get("Folga_Sab", False))
            folgas_sem = int((df.loc[week, "Status"] == "Folga").sum())

            while folgas_sem < 2:
                counts_day, counts_day_hour = _counts_folgas_day_and_hour(
                    hist, users_by_chapa, chapas, cand_days, df_ref
                )
                bucket = _bucket_horario(users_by_chapa[ch])

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
                        counts_day.get(j, 0),                     # menos folgas no dia
                        counts_day_hour.get((j, bucket), 0),      # menos folgas no MESMO HORÁRIO nesse dia
                        weekday_prio
                    )

                possiveis.sort(key=score)
                pick = possiveis[0]
                _set_folga(df, pick)
                folgas_sem += 1
                hist[ch] = df

    # 3) limite 5 seguidos + interstício (com mês anterior)
    for ch in chapas:
        df = hist[ch]
        ent = users_by_chapa[ch].get("Entrada", "06:00")
        pode_sab = bool(users_by_chapa[ch].get("Folga_Sab", False))

        # escala corrida: se terminou com 5+ dias, força folga no 1º dia útil possível
        if ch in estado_prev and int(estado_prev[ch].get("consec_trab_final", 0)) >= 5:
            for i in range(len(df)):
                if df.loc[i, "Status"] == "Trabalho" and df_ref.loc[i, "Dia"] in ["seg", "ter", "qua", "qui", "sex"]:
                    _set_folga(df, i)
                    break

        enforce_max_5_consecutive_work(df, ent, pode_sab)

        ultima_saida_prev = estado_prev.get(ch, {}).get("ultima_saida", "")
        recompute_hours_with_intersticio(df, ent, ultima_saida_prev=ultima_saida_prev)

        hist[ch] = df

    # 4) rebalanceamento final por dia
    rebalance_folgas_dia(hist, users_by_chapa, chapas, weeks, df_ref, max_iters=1800)

    # montar estado do mês atual (para próximo mês)
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

        ultimo_domingo_status = None
        for i in range(len(df)-1, -1, -1):
            if df.loc[i, "Dia"] == "dom" and df.loc[i, "Status"] in ["Trabalho", "Folga"]:
                ultimo_domingo_status = df.loc[i, "Status"]
                break

        estado_out[ch] = {
            "consec_trab_final": consec,
            "ultima_saida": ultima_saida,
            "ultimo_domingo_status": ultimo_domingo_status,
        }

    return hist, estado_out


# =========================================================
# SESSION / ROUTING
# =========================================================
if "auth" not in st.session_state:
    st.session_state["auth"] = None  # {nome,setor,chapa,is_lider}

db_init()

# =========================================================
# LOGIN PAGE (ABA)
# =========================================================
def page_login():
    st.title("🔐 Login por Setor")

    tab_login, tab_cadastro, tab_esqueci = st.tabs(["Entrar", "Cadastrar", "Esqueci a senha"])

    with tab_login:
        st.subheader("Entrar")
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

    with tab_cadastro:
        st.subheader("Cadastrar usuário (no seu setor)")
        nome = st.text_input("Nome completo:", key="cad_nome")
        setor = st.text_input("Setor (ex: depósito, balança, fracionados):", key="cad_setor")
        chapa = st.text_input("Chapa:", key="cad_chapa")
        senha = st.text_input("Senha:", type="password", key="cad_senha")
        senha2 = st.text_input("Confirmar senha:", type="password", key="cad_senha2")
        is_lider = st.checkbox("Sou líder do setor", key="cad_lider")

        st.info("✅ Regra: a recuperação de senha usa a CHAPA de um LÍDER do mesmo setor.")

        if st.button("Criar cadastro", key="cad_btn"):
            setor = (setor or "").strip().upper()
            chapa = (chapa or "").strip()
            if not nome or not setor or not chapa or not senha:
                st.error("Preencha todos os campos.")
            elif senha != senha2:
                st.error("Senhas não conferem.")
            elif user_exists(setor, chapa):
                st.error("Já existe usuário com essa chapa nesse setor.")
            else:
                create_user(nome=nome.strip(), setor=setor, chapa=chapa, senha=senha, is_lider=1 if is_lider else 0)
                st.success("Cadastro criado! Faça login na aba Entrar.")
                st.rerun()

    with tab_esqueci:
        st.subheader("Redefinir senha (usando CHAPA do LÍDER)")
        con = db_conn()
        setores = pd.read_sql_query("SELECT nome FROM setores ORDER BY nome ASC", con)["nome"].tolist()
        con.close()

        setor = st.selectbox("Setor:", setores, key="fp_setor")
        chapa = st.text_input("Sua chapa:", key="fp_chapa")
        chapa_lider = st.text_input("Chapa do líder do setor:", key="fp_lider")
        nova = st.text_input("Nova senha:", type="password", key="fp_nova")
        nova2 = st.text_input("Confirmar nova senha:", type="password", key="fp_nova2")

        if st.button("Redefinir", key="fp_btn"):
            if not chapa or not chapa_lider or not nova:
                st.error("Preencha todos os campos.")
            elif nova != nova2:
                st.error("Senhas não conferem.")
            elif not user_exists(setor, chapa):
                st.error("Usuário não encontrado nesse setor.")
            elif not is_lider_chapa(setor, chapa_lider):
                st.error("Chapa de líder inválida (precisa ser LÍDER do MESMO setor).")
            else:
                update_password(setor, chapa, nova)
                st.success("Senha redefinida! Volte e faça login.")
                st.rerun()


# =========================================================
# MAIN APP (após login)
# =========================================================
def page_app():
    auth = st.session_state["auth"]
    st.sidebar.title("👤 Sessão")
    st.sidebar.write(f"**Nome:** {auth['nome']}")
    st.sidebar.write(f"**Setor:** {auth['setor']}")
    st.sidebar.write(f"**Chapa:** {auth['chapa']}")
    st.sidebar.write(f"**Perfil:** {'LÍDER' if auth['is_lider'] else 'COLABORADOR'}")

    if st.sidebar.button("Sair", key="logout_btn"):
        st.session_state["auth"] = None
        st.rerun()

    setor = auth["setor"]

    # mês/ano correntes
    if "cfg_mes" not in st.session_state: st.session_state["cfg_mes"] = datetime.now().month
    if "cfg_ano" not in st.session_state: st.session_state["cfg_ano"] = datetime.now().year

    st.title("📅 Escala 5x2 — Setor")
    st.caption("Regras ativas: 5x2 semanal (seg→dom), domingo 1x1, interstício 11h10, max 5 dias seguidos, sábado só folga se marcado, balanceamento por dia + horário.")

    # abas
    tabs = ["👥 Colaboradores", "🚀 Gerar escala", "⚙️ Ajustes", "🏖️ Férias", "📥 Excel"]
    aba1, aba2, aba3, aba4, aba5 = st.tabs(tabs)

    # --------- ABA 1: COLABORADORES (perfil de escala) ---------
    with aba1:
        st.subheader("Colaboradores do setor (perfil para escala)")

        users = load_users_setor(setor)
        if not users:
            st.warning("Sem usuários no setor. Cadastre na tela de login (aba Cadastrar).")
        else:
            dfu = pd.DataFrame([{
                "Nome": u["Nome"],
                "Chapa": u["Chapa"],
                "Categoria": u["Categoria"],
                "Entrada": u["Entrada"],
                "Folga Sábado?": "Sim" if u["Folga_Sab"] else "Não",
                "Líder?": "Sim" if u["is_lider"] else "Não"
            } for u in users])
            st.dataframe(dfu, use_container_width=True)

        st.markdown("---")
        st.markdown("### Editar perfil do colaborador (entrada / categoria / folga sábado)")

        if users:
            chapas = [u["Chapa"] for u in users]
            chapa_sel = st.selectbox("Chapa:", chapas, key="pf_chapa")
            u = next(x for x in users if x["Chapa"] == chapa_sel)

            c1, c2, c3 = st.columns(3)
            nova_cat = c1.text_input("Categoria (sub-setor):", value=u["Categoria"], key="pf_cat")
            nova_ent = c2.time_input("Entrada padrão:", value=datetime.strptime(u["Entrada"], "%H:%M").time(), key="pf_ent")
            folga_sab = c3.checkbox("Permitir folga no sábado", value=bool(u["Folga_Sab"]), key="pf_sab")

            if st.button("Salvar perfil", key="pf_save"):
                save_profile(setor, chapa_sel, nova_ent.strftime("%H:%M"), folga_sab, (nova_cat or setor))
                st.success("Perfil salvo (para esta sessão). Gere a escala para refletir.")
                st.rerun()

        if auth["is_lider"] or setor == "ADMIN":
            st.markdown("---")
            st.markdown("### (Líder) Criar usuário no setor")
            nome_n = st.text_input("Nome:", key="add_nome")
            chapa_n = st.text_input("Chapa:", key="add_chapa")
            senha_n = st.text_input("Senha:", type="password", key="add_senha")
            lider_n = st.checkbox("É líder?", key="add_lider")

            if st.button("Criar usuário", key="add_btn"):
                if not nome_n or not chapa_n or not senha_n:
                    st.error("Preencha nome, chapa e senha.")
                elif user_exists(setor, chapa_n):
                    st.error("Já existe essa chapa no setor.")
                else:
                    create_user(nome_n.strip(), setor, chapa_n.strip(), senha_n, 1 if lider_n else 0)
                    st.success("Usuário criado!")
                    st.rerun()

    # --------- ABA 2: GERAR ESCALA ---------
    with aba2:
        st.subheader("Gerar escala do mês (com continuidade do mês anterior)")
        c1, c2, c3 = st.columns([1, 1, 2])

        mes = c1.selectbox("Mês:", list(range(1, 13)), index=st.session_state["cfg_mes"]-1, key="gen_mes")
        ano = c2.number_input("Ano:", value=st.session_state["cfg_ano"], step=1, key="gen_ano")
        st.session_state["cfg_mes"] = int(mes)
        st.session_state["cfg_ano"] = int(ano)

        users = load_users_setor(setor)
        if not users:
            st.warning("Sem colaboradores no setor.")
        else:
            if st.button("🚀 Gerar agora", key="gen_btn"):
                hist, estado_out = gerar_escala_setor(setor, users, int(ano), int(mes))
                save_escala_mes_db(setor, int(ano), int(mes), hist)
                save_estado_mes(setor, int(ano), int(mes), estado_out)
                st.success("Escala gerada e salva no banco (SQLite).")
                st.rerun()

            # mostrar escala atual salva (se existir)
            hist_db = load_escala_mes_db(setor, int(ano), int(mes))
            if hist_db:
                st.markdown("### Escala salva no banco")
                chapa_view = st.selectbox("Ver colaborador (chapa):", list(hist_db.keys()), key="view_chapa")
                st.dataframe(hist_db[chapa_view], use_container_width=True)
            else:
                st.info("Ainda não existe escala salva para este mês/setor.")

    # --------- ABA 3: AJUSTES (por dia + mês inteiro) ---------
    with aba3:
        st.subheader("Ajustes (mantém regra domingo 1x1 e limite 5 dias)")

        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = load_escala_mes_db(setor, ano, mes)
        users = load_users_setor(setor)
        users_by_chapa = {u["Chapa"]: u for u in users}

        if not hist_db:
            st.info("Gere a escala primeiro (aba Gerar escala).")
        else:
            t1, t2 = st.tabs(["🔧 Ajuste por dia", "📅 Trocar horário mês inteiro"])

            with t1:
                chapa_sel = st.selectbox("Chapa:", list(hist_db.keys()), key="adj_chapa")
                df = hist_db[chapa_sel].copy()
                ent_pad = users_by_chapa[chapa_sel]["Entrada"]
                pode_sab = bool(users_by_chapa[chapa_sel]["Folga_Sab"])

                col1, col2, col3 = st.columns(3)
                dia_sel = col1.number_input("Dia do mês:", 1, len(df), value=1, key="adj_dia")
                acao = col2.selectbox("Ação:", ["Marcar Trabalho", "Marcar Folga", "Marcar Férias", "Alterar Entrada"], key="adj_acao")
                nova_ent = col3.time_input("Nova entrada:", value=datetime.strptime(ent_pad, "%H:%M").time(), key="adj_ent")

                if st.button("Aplicar ajuste", key="adj_apply"):
                    idx = int(dia_sel) - 1
                    dia_sem = df.loc[idx, "Dia"]
                    if acao == "Marcar Férias":
                        _set_ferias(df, idx)
                    elif acao == "Marcar Folga":
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode colocar folga em férias.")
                        elif dia_sem == "sáb" and not pode_sab:
                            st.error("Sábado só pode ser folga se permitir no perfil.")
                        else:
                            _set_folga(df, idx)
                    elif acao == "Marcar Trabalho":
                        if df.loc[idx, "Status"] == "Férias":
                            st.error("Não pode colocar trabalho em férias.")
                        else:
                            e = nova_ent.strftime("%H:%M")
                            df.loc[idx, "H_Entrada"] = e
                            _set_trabalho(df, idx, e)
                    else:
                        if df.loc[idx, "Status"] != "Trabalho":
                            st.error("Só altera entrada em dia de trabalho.")
                        else:
                            e = nova_ent.strftime("%H:%M")
                            df.loc[idx, "H_Entrada"] = e
                            df.loc[idx, "H_Saida"] = _saida_from_entrada(e)

                    # ✅ se mexeu em domingo, propaga alternância para os próximos domingos
                    if df.loc[idx, "Data"].day_name() == "Sunday":
                        enforce_sundays_alternating_for_employee(df, ent_pad, idx)

                    enforce_max_5_consecutive_work(df, ent_pad, pode_sab)
                    recompute_hours_with_intersticio(df, ent_pad)

                    # salva no DB
                    save_escala_mes_db(setor, ano, mes, {chapa_sel: df})
                    st.success("Ajuste aplicado e salvo.")
                    st.rerun()

                st.dataframe(df, use_container_width=True)

            with t2:
                chapa_sel2 = st.selectbox("Chapa:", list(hist_db.keys()), key="adjm_chapa")
                dfm = hist_db[chapa_sel2].copy()
                ent_pad2 = users_by_chapa[chapa_sel2]["Entrada"]
                pode_sab2 = bool(users_by_chapa[chapa_sel2]["Folga_Sab"])

                nova_ent_mes = st.time_input("Nova entrada para o mês (dias de trabalho):",
                                             value=datetime.strptime(ent_pad2, "%H:%M").time(),
                                             key="adjm_ent")
                if st.button("Aplicar no mês inteiro", key="adjm_apply"):
                    e = nova_ent_mes.strftime("%H:%M")
                    for i in range(len(dfm)):
                        if dfm.loc[i, "Status"] == "Trabalho":
                            dfm.loc[i, "H_Entrada"] = e
                            dfm.loc[i, "H_Saida"] = _saida_from_entrada(e)

                    enforce_max_5_consecutive_work(dfm, e, pode_sab2)
                    recompute_hours_with_intersticio(dfm, e)

                    # também atualiza o perfil (sessão)
                    save_profile(setor, chapa_sel2, e, bool(users_by_chapa[chapa_sel2]["Folga_Sab"]), users_by_chapa[chapa_sel2]["Categoria"])

                    save_escala_mes_db(setor, ano, mes, {chapa_sel2: dfm})
                    st.success("Horário aplicado e salvo.")
                    st.rerun()

                st.dataframe(dfm, use_container_width=True)

    # --------- ABA 4: FÉRIAS ---------
    with aba4:
        st.subheader("Férias (lança automaticamente na escala)")
        users = load_users_setor(setor)
        if not users:
            st.warning("Sem colaboradores no setor.")
        else:
            chapas = [u["Chapa"] for u in users]
            chapa_sel = st.selectbox("Chapa:", chapas, key="fer_chapa")
            c1, c2 = st.columns(2)
            ini = c1.date_input("Início:", key="fer_ini")
            fim = c2.date_input("Fim:", key="fer_fim")

            if st.button("Adicionar férias", key="fer_add"):
                if fim < ini:
                    st.error("Fim não pode ser menor que início.")
                else:
                    add_ferias(setor, chapa_sel, ini, fim)
                    st.success("Férias adicionadas. Gere ou regenere a escala para refletir.")
                    st.rerun()

            st.markdown("---")
            rows = list_ferias(setor)
            if rows:
                st.dataframe(pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"]), use_container_width=True)
            else:
                st.info("Sem férias cadastradas.")

    # --------- ABA 5: EXCEL ---------
    with aba5:
        st.subheader("Exportar Excel (modelo RH)")
        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = load_escala_mes_db(setor, ano, mes)
        users = load_users_setor(setor)
        users_by_chapa = {u["Chapa"]: u for u in users}

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

                    # pega um DF referência
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
                    ws.row_dimensions[1].height = 22
                    ws.row_dimensions[2].height = 22

                    # ordenar por nome
                    chapas_sorted = sorted(hist_db.keys(), key=lambda ch: users_by_chapa.get(ch, {}).get("Nome", ch))

                    row_idx = 3
                    for ch in chapas_sorted:
                        df_f = hist_db[ch]
                        nome = users_by_chapa.get(ch, {}).get("Nome", ch)

                        c_nome = ws.cell(row_idx, 1, f"{nome}\nCHAPA: {ch}")
                        c_nome.fill = fill_nome
                        c_nome.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                        c_nome.border = border
                        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx + 1, end_column=1)

                        ws.row_dimensions[row_idx].height = 18
                        ws.row_dimensions[row_idx + 1].height = 18

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
