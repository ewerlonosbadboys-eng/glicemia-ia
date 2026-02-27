# app.py
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO + PAINEL ADMIN
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

# ---- Regras fixas
INTERSTICIO_MIN = timedelta(hours=11, minutes=10)
DURACAO_JORNADA = timedelta(hours=9, minutes=58)
PREF_EVITAR_PENALTY = 1000  # penalidade forte

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
# DB + AUTH
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

# ---- ADMIN: listar/editar usuários
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
# COLABORADORES (sem senha) + subgrupo
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
# SUBGRUPOS + Preferência (evitar folga)
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
# FÉRIAS (mínimo necessário para o app rodar)
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
    df = pd.read_sql_query("SELECT chapa, inicio, fim FROM ferias WHERE setor=? ORDER BY date(inicio) ASC", con, params=(setor,))
    con.close()
    return df

# =========================================================
# APP
# =========================================================
db_init()

if "auth" not in st.session_state:
    st.session_state["auth"] = None

def page_login():
    st.title("🔐 Login por Setor (Líder/Admin)")

    tab_login, tab_cadastrar, tab_esqueci = st.tabs(["Entrar", "Cadastrar Líder", "Esqueci a senha"])

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
        st.subheader("Cadastrar usuário do sistema (Líder/Admin)")
        nome = st.text_input("Nome:", key="cl_nome")
        setor = st.text_input("Setor:", key="cl_setor").strip().upper()
        chapa = st.text_input("Chapa:", key="cl_chapa")
        senha = st.text_input("Senha:", type="password", key="cl_senha")
        senha2 = st.text_input("Confirmar senha:", type="password", key="cl_senha2")
        is_admin = st.checkbox("Admin?", key="cl_admin")
        is_lider = st.checkbox("Líder?", value=True, key="cl_lider")

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
    st.sidebar.write(f"**Nome:** {auth.get('nome','-')}")
    st.sidebar.write(f"**Setor:** {setor}")
    st.sidebar.write(f"**Chapa:** {auth.get('chapa','-')}")
    st.sidebar.write(f"**Perfil:** {'ADMIN' if auth.get('is_admin', False) else ('LÍDER' if auth.get('is_lider', False) else 'USUÁRIO')}")

    if st.sidebar.button("Sair", key="logout_btn"):
        st.session_state["auth"] = None
        st.rerun()

    st.title(f"📌 Sistema de Escala — Setor: {setor}")

    # ========= PAINEL ADMIN =========
    if auth.get("is_admin", False) and setor == "ADMIN":
        st.success("Modo ADMIN ativo.")

        tA, tB, tC = st.tabs(["👥 Usuários do Sistema", "➕ Criar usuário", "📋 Auditoria"])

        with tA:
            st.subheader("Usuários cadastrados (login por setor)")
            df_users = admin_list_users()
            st.dataframe(df_users, use_container_width=True)

            st.markdown("### ✏️ Editar usuário")
            if not df_users.empty:
                user_id = st.selectbox("Selecionar ID:", df_users["id"].tolist(), key="adm_user_id")
                urow = df_users[df_users["id"] == user_id].iloc[0]

                c1, c2, c3 = st.columns(3)
                nome = c1.text_input("Nome:", value=str(urow["nome"]), key="adm_nome")
                setor_new = c2.text_input("Setor:", value=str(urow["setor"]), key="adm_setor").strip().upper()
                chapa_new = c3.text_input("Chapa:", value=str(urow["chapa"]), key="adm_chapa")

                c4, c5, c6 = st.columns(3)
                is_admin = c4.checkbox("Admin?", value=bool(urow["is_admin"]), key="adm_isadmin")
                is_lider = c5.checkbox("Líder?", value=bool(urow["is_lider"]), key="adm_islider")
                reset_senha = c6.checkbox("Resetar senha agora", key="adm_resetsenha")

                nova_senha = ""
                if reset_senha:
                    nova_senha = st.text_input("Nova senha:", type="password", key="adm_nova_senha")

                colx1, colx2 = st.columns(2)
                if colx1.button("Salvar alterações", key="adm_save"):
                    try:
                        admin_update_user(user_id, nome.strip(), setor_new, chapa_new.strip(), is_admin, is_lider)
                        if reset_senha and nova_senha:
                            update_password(setor_new, chapa_new.strip(), nova_senha)
                        st.success("Atualizado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

                if colx2.button("Excluir usuário", key="adm_del"):
                    if int(user_id) == 1:
                        st.error("Bloqueado: não pode excluir o admin principal.")
                    else:
                        admin_delete_user(user_id)
                        st.warning("Usuário removido.")
                        st.rerun()
            else:
                st.info("Sem usuários no banco.")

        with tB:
            st.subheader("Criar usuário do sistema (Admin/Líder)")
            nome = st.text_input("Nome:", key="adm_cr_nome")
            setor_u = st.text_input("Setor:", key="adm_cr_setor").strip().upper()
            chapa = st.text_input("Chapa:", key="adm_cr_chapa")
            senha = st.text_input("Senha:", type="password", key="adm_cr_senha")
            is_admin = st.checkbox("Admin?", key="adm_cr_isadmin")
            is_lider = st.checkbox("Líder?", value=True, key="adm_cr_islider")

            if st.button("Criar", key="adm_cr_btn"):
                if not nome or not setor_u or not chapa or not senha:
                    st.error("Preencha tudo.")
                elif system_user_exists(setor_u, chapa.strip()):
                    st.error("Já existe.")
                else:
                    create_system_user(nome.strip(), setor_u, chapa.strip(), senha, is_lider=1 if is_lider else 0, is_admin=1 if is_admin else 0)
                    st.success("Criado!")
                    st.rerun()

        with tC:
            st.subheader("Auditoria (somente leitura)")
            con = db_conn()
            df_colabs = pd.read_sql_query("""
                SELECT nome, setor, chapa, subgrupo, entrada, folga_sab, criado_em
                FROM colaboradores
                ORDER BY setor, nome
            """, con)
            con.close()
            st.dataframe(df_colabs, use_container_width=True)

        st.markdown("---")
        st.info("O ADMIN pode mudar: **senha / chapa / setor / login** de qualquer usuário do sistema.")

    else:
        st.info("Modo setor: aqui ficam as funcionalidades do setor (colaboradores/escala/ajustes/ferias/excel).")
        st.caption("Se você logar como ADMIN, aparece o painel de usuários.")

# =========================================================
# MAIN
# =========================================================
if st.session_state["auth"] is None:
    page_login()
else:
    page_app()
