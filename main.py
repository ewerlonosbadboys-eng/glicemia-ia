# main.py (arquivo único)
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO + ADMIN
# - Usuários comuns VEEM tudo do setor
# - Painel ADMIN restrito (somente setor ADMIN e is_admin=1)
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
# DB
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
# FÉRIAS (corrige seu NameError)
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

# =========================================================
# UI
# =========================================================
db_init()

if "auth" not in st.session_state:
    st.session_state["auth"] = None

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
            ev_seg = p1.checkbox("Evitar SEG", value=bool(regras["seg"]), key=f"ev_seg_{sg_sel}")
            ev_ter = p1.checkbox("Evitar TER", value=bool(regras["ter"]), key=f"ev_ter_{sg_sel}")
            ev_qua = p2.checkbox("Evitar QUA", value=bool(regras["qua"]), key=f"ev_qua_{sg_sel}")
            ev_qui = p2.checkbox("Evitar QUI", value=bool(regras["qui"]), key=f"ev_qui_{sg_sel}")
            ev_sex = p3.checkbox("Evitar SEX", value=bool(regras["sex"]), key=f"ev_sex_{sg_sel}")
            ev_sab = p3.checkbox("Evitar SÁB", value=bool(regras["sáb"]), key=f"ev_sab_{sg_sel}")

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

    with aba2:
        st.info("Motor completo de escala entra aqui (você já tem a versão grande).")

    with aba3:
        st.info("Ajustes completos entram aqui (troca dia/horário/mês).")

    with aba4:
        st.subheader("Férias")
        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Cadastre colaboradores.")
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

    with aba5:
        st.info("Excel modelo RH entra aqui (você já tem a versão completa).")

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

    # ✅ Agora TODO usuário vê o sistema completo do setor
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
