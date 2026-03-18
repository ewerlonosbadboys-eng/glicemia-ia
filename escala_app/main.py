# V97 ENTERPRISE — boot resiliente, restore em camadas e login sempre liberado
# V97.3 PREMIUM UI — refinamento visual adicional sem alterar regras
# Derivado da V95.2 com reforço no restore local/Supabase/latest_stable e sem bloqueio rígido de login.

# V84 BASE — DISTRIBUIÇÃO INTELIGENTE POR SEMANA DO SUBGRUPO
# Arquivo preparado como continuação de testes sobre a V83.
# Objetivo desta base: evoluir o motor para distribuir folgas pela semana real
# do subgrupo antes do rebalance fino por troca, mantendo as regras da 5x2.

# V82
# Base enviada para evolucao do balanceamento pesado por pontuacao semanal + multiplas rodadas de swap.
# Arquivo derivado da V81 para teste no seu ambiente.

# V81
# =========================================================
# ESTA VERSÃO FOI PREPARADA COMO BASE DA PRÓXIMA ETAPA:
# - balanceamento por pontuação do subgrupo
# - troca automática (swap) para reduzir concentração de folgas
# - manutenção das regras duras já existentes da escala 5x2
#
# Observação importante:
# esta versão foi gerada a partir da V80 para servir como base de teste
# e continuação do ajuste do motor de distribuição. A regra semanal
# inquebrável da V80 foi preservada.
# =========================================================

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
#
# ✅ ATUALIZAÇÃO DE HOJE (REGRA CRÍTICA):
# 8) PROIBIR TRABALHAR MAIS DE 5 DIAS DIRETO (GLOBAL, GARANTIA FINAL):
#    - Reaplica enforce_max_5_consecutive_work após funções que podem desfazer folgas:
#      enforce_weekly_folga_targets e rebalance_folgas_dia e no "pós final (garantia)".
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import datetime as dt
import io
import random
import math
import calendar
import sqlite3
import os
import re
import shutil
from pathlib import Path
import unicodedata
import time
import json
import requests
import threading

import hashlib
import secrets
from openpyxl.styles import PatternFill, Alignment, Border, Side, Font
from openpyxl.utils import get_column_letter

# =========================================================
# PDF (Modelo Oficial) — ReportLab
# =========================================================
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
st.set_page_config(page_title="Escala 5x2 Oficial", layout="wide")


def aplicar_tema_premium_etapa1():
    st.markdown("""
    <style>
    :root {
        --ax-bg-1: #020816;
        --ax-bg-2: #07152f;
        --ax-bg-3: #0a2450;
        --ax-line: rgba(125, 170, 255, 0.24);
        --ax-line-2: rgba(255,255,255,0.10);
        --ax-text: #f8fbff;
        --ax-soft: #b4c8ee;
        --ax-blue: #60a5fa;
        --ax-blue-2: #2563eb;
        --ax-blue-3: #93c5fd;
        --ax-card: linear-gradient(180deg, rgba(11,28,60,0.99), rgba(4,12,28,0.99));
        --ax-card-2: linear-gradient(180deg, rgba(9,23,49,0.98), rgba(5,13,29,0.98));
        --ax-card-3: linear-gradient(180deg, rgba(13,33,70,0.99), rgba(6,16,35,0.99));
        --ax-shadow: 0 24px 52px rgba(0,0,0,0.34);
    }

    .stApp {
        background:
            radial-gradient(circle at 88% 4%, rgba(96,165,250,0.28), transparent 12%),
            radial-gradient(circle at 14% 0%, rgba(59,130,246,0.15), transparent 16%),
            radial-gradient(circle at 95% 35%, rgba(30,64,175,0.16), transparent 20%),
            linear-gradient(135deg, var(--ax-bg-1) 0%, var(--ax-bg-2) 45%, #020b18 100%);
        color: var(--ax-text);
    }

    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 3.1rem;
        max-width: 1540px;
    }

    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 20% 0%, rgba(79,140,255,0.16), transparent 22%),
            linear-gradient(180deg, #071125 0%, #081a38 55%, #0a2148 100%);
        border-right: 1px solid rgba(120, 160, 255, 0.18);
        box-shadow: inset -1px 0 0 rgba(255,255,255,0.04), 20px 0 44px rgba(0,0,0,0.24);
    }

    section[data-testid="stSidebar"] * {
        color: #eef5ff !important;
    }

    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ffffff;
        letter-spacing: -0.02em;
    }

    .stMarkdown h2 {
        font-size: 1.95rem;
        margin-top: 0.4rem;
        margin-bottom: 1rem;
        font-weight: 800;
    }

    .stMarkdown h3 {
        font-size: 1.2rem;
        font-weight: 700;
    }

    .stMarkdown p, .stCaption, label, .stRadio label, .stCheckbox label {
        color: #d7e6ff !important;
    }

    div[data-testid="stMetric"] {
        background: var(--ax-card-3);
        border: 1px solid rgba(96,165,250,0.24);
        border-radius: 20px;
        padding: 15px 17px;
        box-shadow: var(--ax-shadow);
        position: relative;
        overflow: hidden;
    }

    div[data-testid="stMetric"]::before {
        content: "";
        position: absolute;
        inset: 0 auto auto 0;
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, rgba(79,140,255,0.0), rgba(96,165,250,0.98), rgba(79,140,255,0.0));
        opacity: 0.95;
    }

    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #dfe9ff !important;
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.18rem !important;
        font-weight: 800 !important;
    }

    .stButton > button,
    div[data-testid="stFormSubmitButton"] button,
    .stDownloadButton > button,
    button[kind="secondary"] {
        background: linear-gradient(90deg, #4f8cff 0%, #2563eb 55%, #1d4ed8 100%);
        color: white;
        border: 1px solid rgba(255,255,255,0.11);
        border-radius: 14px;
        font-weight: 800;
        padding: 0.78rem 1rem;
        box-shadow: 0 16px 34px rgba(37,99,235,0.34);
        transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease, filter 0.16s ease;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] button:hover,
    .stDownloadButton > button:hover,
    button[kind="secondary"]:hover {
        background: linear-gradient(90deg, #69a8ff 0%, #2563eb 60%, #1e40af 100%);
        border-color: rgba(255,255,255,0.22);
        transform: translateY(-1px);
        box-shadow: 0 20px 40px rgba(37,99,235,0.38);
        filter: saturate(1.1);
    }

    .stButton > button:active,
    div[data-testid="stFormSubmitButton"] button:active,
    .stDownloadButton > button:active {
        transform: translateY(0);
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    .stDateInput input,
    .stTimeInput input,
    .stMultiSelect div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.06) !important;
        color: #f8fbff !important;
        border-radius: 14px !important;
        border: 1px solid rgba(148,163,184,0.26) !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 10px 22px rgba(0,0,0,0.14);
        min-height: 2.85rem;
    }

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    .stTextInput input:focus,
    .stNumberInput input:focus,
    .stTextArea textarea:focus,
    .stDateInput input:focus,
    .stTimeInput input:focus {
        border-color: rgba(96,165,250,0.62) !important;
        box-shadow: 0 0 0 1px rgba(79,140,255,0.30), 0 16px 32px rgba(0,0,0,0.20) !important;
    }

    div[data-baseweb="input"] input::placeholder,
    .stTextArea textarea::placeholder {
        color: #97afd8 !important;
    }

    .stDataFrame, .stTable {
        background: rgba(4,14,30,0.96);
        border: 1px solid rgba(148,163,184,0.22);
        border-radius: 20px;
        overflow: hidden;
        box-shadow: var(--ax-shadow);
    }

    [data-testid="stDataFrame"] div[role="table"] {
        border-radius: 20px;
        overflow: hidden;
    }

    [data-testid="stDataFrame"] [role="rowgroup"] [role="row"]:nth-child(even) {
        background: rgba(255,255,255,0.035) !important;
    }

    [data-testid="stDataFrame"] [role="rowgroup"] [role="row"]:nth-child(odd) {
        background: rgba(255,255,255,0.012) !important;
    }

    [data-testid="stDataFrame"] [role="rowgroup"] [role="row"]:hover {
        background: rgba(96,165,250,0.12) !important;
    }

    [data-testid="stDataFrame"] [role="columnheader"] {
        background: linear-gradient(180deg, rgba(24,48,97,0.98), rgba(10,21,44,0.98)) !important;
        color: #f8fbff !important;
        font-weight: 800 !important;
        border-bottom: 1px solid rgba(120,160,255,0.20) !important;
    }

    button[data-baseweb="tab"] {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(148,163,184,0.16) !important;
        border-radius: 14px !important;
        margin-right: 0.42rem !important;
        color: #dfeaff !important;
        padding: 0.50rem 0.92rem !important;
        font-weight: 700 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(180deg, rgba(79,140,255,0.30), rgba(37,99,235,0.24)) !important;
        border-color: rgba(96,165,250,0.38) !important;
        color: #ffffff !important;
        box-shadow: 0 10px 26px rgba(0,0,0,0.22);
    }

    div[role="radiogroup"] {
        gap: 0.45rem;
        flex-wrap: wrap;
    }

    div[role="radiogroup"] > label {
        background: linear-gradient(180deg, rgba(11,26,54,0.88), rgba(5,14,30,0.88)) !important;
        border: 1px solid rgba(148,163,184,0.18) !important;
        border-radius: 999px !important;
        padding: 0.34rem 0.72rem !important;
        min-height: 2.05rem;
        transition: all .16s ease;
        box-shadow: 0 10px 22px rgba(0,0,0,0.12);
    }

    div[role="radiogroup"] > label:hover {
        border-color: rgba(96,165,250,0.34) !important;
        background: linear-gradient(180deg, rgba(18,38,78,0.92), rgba(8,20,40,0.92)) !important;
    }

    div[role="radiogroup"] > label[data-checked="true"] {
        background: linear-gradient(90deg, rgba(79,140,255,0.34), rgba(37,99,235,0.28)) !important;
        border-color: rgba(96,165,250,0.50) !important;
        box-shadow: 0 14px 28px rgba(0,0,0,0.20);
    }

    div[role="radiogroup"] > label p {
        color: #eef5ff !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
    }

    div[data-testid="stForm"] {
        background: linear-gradient(180deg, rgba(8,22,46,0.90), rgba(4,12,26,0.90));
        border: 1px solid rgba(120,160,255,0.20);
        border-radius: 22px;
        padding: 1.25rem 1.05rem 1.05rem 1.05rem;
        box-shadow: var(--ax-shadow);
    }

    div[data-testid="stExpander"], details {
        background: linear-gradient(180deg, rgba(8,22,46,0.88), rgba(4,12,26,0.88));
        border: 1px solid rgba(120,160,255,0.18);
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 0 18px 36px rgba(0,0,0,0.18);
    }

    details {
        padding: 0.4rem 0.8rem;
    }

    .stMarkdown h2, .stMarkdown h3 {
        position: relative;
    }

    .stMarkdown h2::after, .stMarkdown h3::after {
        content: "";
        display: block;
        width: 92px;
        height: 3px;
        margin-top: 0.4rem;
        background: linear-gradient(90deg, rgba(96,165,250,1), rgba(96,165,250,0));
        border-radius: 999px;
    }

    div[data-testid="stAlert"] {
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 16px 34px rgba(0,0,0,0.18);
    }

    .element-container {
        margin-bottom: 0.28rem;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.95rem;
    }

    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdownContainer"] h2),
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdownContainer"] h3) {
        margin-top: 0.4rem;
        margin-bottom: 0.55rem;
    }

    div[data-testid="stCheckbox"] {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(148,163,184,0.14);
        border-radius: 14px;
        padding: 0.55rem 0.7rem 0.45rem 0.7rem;
        min-height: 2.8rem;
    }

    div[data-testid="stCheckbox"]:has(input:checked) {
        border-color: rgba(96,165,250,0.34);
        background: rgba(96,165,250,0.08);
    }

    hr {
        border-color: rgba(120,160,255,0.14);
        margin-top: 1.4rem;
        margin-bottom: 1.4rem;
    }
    </style>
    """, unsafe_allow_html=True)

def page_app():
    aplicar_tema_premium_etapa1()
    auth = st.session_state.get("auth") or {}
    setor = auth.get("setor", "GERAL")

    if st.session_state.get("auth_force_change", False):
        st.markdown("## 🔐 Troca obrigatória de senha")
        st.warning("Sua senha temporária precisa ser trocada antes de continuar.")
        nova1 = st.text_input("Nova senha", type="password", key="force_pwd_1")
        nova2 = st.text_input("Confirmar nova senha", type="password", key="force_pwd_2")
        c1, c2 = st.columns([1,1])
        if c1.button("Salvar nova senha", key="force_pwd_save"):
            if not (nova1 or "").strip():
                st.error("Digite a nova senha.")
                st.stop()
            if nova1 != nova2:
                st.error("A confirmação da senha não confere.")
                st.stop()
            try:
                update_password(setor, auth.get("chapa", ""), nova1)
                set_force_change_password(setor, auth.get("chapa", ""), False)
                st.session_state["auth_force_change"] = False
                if st.session_state.get("auth"):
                    st.session_state["auth"]["forcar_troca_senha"] = False
                st.success("Senha atualizada com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao atualizar senha: {e}")
        if c2.button("Sair", key="force_pwd_logout"):
            st.session_state["auth"] = None
            st.session_state["auth_force_change"] = False
            st.rerun()
        return

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
        st.caption(VERSAO_ACESSO_LIDER)

        _ano_sb = int(st.session_state.get('cfg_ano') or datetime.now().year)
        _mes_sb = int(st.session_state.get('cfg_mes') or datetime.now().month)
        _colab_sb = get_colaborador_competencia_snapshot(setor, auth.get('chapa',''), _ano_sb, _mes_sb) or get_colaborador_record(setor, auth.get('chapa',''))
        _subgrupo_auth = get_subgrupo_competencia_ou_base(setor, auth.get('chapa',''), _ano_sb, _mes_sb, (_colab_sb or {}).get('Subgrupo', 'SEM SUBGRUPO'))
        _lideranca_ok = bool(auth.get('is_lider', False)) or bool(auth.get('is_ax_lider', False)) or colaborador_eh_lideranca(setor, auth.get('chapa',''))
        _perfil_gestao = bool(auth.get('is_admin', False)) or _lideranca_ok

        cA, cB = st.columns([1, 1])
        perfil_label = 'ADMIN' if auth.get('is_admin', False) else ('AX LÍDER' if auth.get('is_ax_lider', False) else ('LÍDER' if _lideranca_ok else 'COLABORADOR'))
        cA.write(f"**Nome:** {auth.get('nome','-')}")
        cB.write(f"**Perfil:** {perfil_label}")

        st.write(f"**Setor:** {setor}")
        st.write(f"**Chapa:** {auth.get('chapa','-')}")
        st.write(f"**Subgrupo:** {_subgrupo_auth}")
        if bool(auth.get('is_lider', False)) and not _lideranca_ok and not bool(auth.get('is_admin', False)):
            st.warning('Perfil líder liberado somente para colaborador do subgrupo LIDERANÇA neste setor.')

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        st.subheader("🗓️ Competência")
        if not _perfil_gestao:
            hoje = datetime.now()
            st.session_state["cfg_mes"] = int(hoje.month)
            st.session_state["cfg_ano"] = int(hoje.year)
            st.write(f"**Mês vigente:** {hoje.month:02d}")
            st.write(f"**Ano vigente:** {hoje.year}")
            prox_mes = hoje.month + 1
            prox_ano = hoje.year
            if prox_mes > 12:
                prox_mes = 1
                prox_ano += 1
            st.write(f"**Pré-escala:** {prox_mes:02d}/{prox_ano}")
        else:
            m1, m2 = st.columns(2)
            mes_cfg = m1.selectbox("Mês", list(range(1, 13)), index=mes_cfg - 1, key="sb_mes")
            ano_cfg = m2.number_input("Ano", value=ano_cfg, step=1, key="sb_ano")
            st.session_state["cfg_mes"] = int(mes_cfg)
            st.session_state["cfg_ano"] = int(ano_cfg)

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        if st.button("🚪 Sair", use_container_width=True, key="logout_btn"):
            st.session_state["auth"] = None
            st.rerun()

    # =========================
    # PERFIL GESTÃO (GERENTE) — UI dedicada
    # =========================
    if str(setor).strip().upper() in ("GESTAO", "GERENCIA", "GERENTE"):
        page_gestao_dashboard(int(st.session_state["cfg_ano"]), int(st.session_state["cfg_mes"]))
        return

    _lideranca_ok = bool(auth.get('is_lider', False)) or bool(auth.get('is_ax_lider', False)) or colaborador_eh_lideranca(setor, auth.get('chapa',''))
    _perfil_gestao = bool(auth.get('is_admin', False)) or _lideranca_ok

    if not _perfil_gestao:
        page_portal_colaborador(auth, int(st.session_state["cfg_ano"]), int(st.session_state["cfg_mes"]))
        return

    ui_hero(
        f"Olá, {auth.get('nome','Usuário')}",
        f"Setor {setor} • Competência {int(st.session_state['cfg_mes']):02d}/{int(st.session_state['cfg_ano'])} • Visual premium aplicado sem alterar a lógica do app.",
        "⚡ Painel executivo",
    )
    ui_section("Navegação principal", "As abas e fluxos abaixo continuam seguindo as mesmas permissões, aprovações e regras já definidas no sistema.")

    # =========================
    # KPIs
    # =========================
    ano_k = int(st.session_state["cfg_ano"])
    mes_k = int(st.session_state["cfg_mes"])

    _kpi = get_kpis_cached(setor, ano_k, mes_k)
    total_colab = int(_kpi.get("total_colab", 0))
    folgas_mes = int(_kpi.get("folgas_mes", 0))
    ferias_mes = int(_kpi.get("ferias_mes", 0))
    trabalhos_mes = int(_kpi.get("trabalhos_mes", 0))

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
    tabs = ["👥 Colaboradores", "🚀 Gerar Escala", "⚙️ Ajustes", "🏖️ Férias", "🖨️ Impressão", "✍️ Assinaturas", "📨 Minhas solicitações"]
    is_admin_area = bool(auth.get("is_admin", False)) and setor == "ADMIN"
    if is_admin_area:
        tabs = ["🔒 Admin"]

    sec_main = st.radio("Navegação", tabs, horizontal=True, key="main_nav_radio_ultra_fast")

    # ------------------------------------------------------
    # ABA 1: Colaboradores
    # ------------------------------------------------------
    if sec_main == "👥 Colaboradores":
        sec_col = st.radio(
            "",
            (["👥 Colaboradores", "➕ Cadastrar colaborador", "🗑️ Excluir colaborador", "✏️ Editar perfil", "🔑 Alterar senha colaborador", "🧾 Aprovações AX"] + (["🔄 Rodízio Caixa"] if str(setor).strip().upper() == "FRENTECAIXA" else [])), 
            horizontal=True,
            key="sec_col_radio_real_speed",
            label_visibility="collapsed",
        )

        if sec_col == "👥 Colaboradores":
            st.markdown("### 👥 Colaboradores")
            colaboradores = load_colaboradores_setor(setor)
            if colaboradores:
                df_col = pd.DataFrame([{
                    "Nome": c["Nome"],
                    "Chapa": c["Chapa"],
                    "Subgrupo": c["Subgrupo"] or "SEM SUBGRUPO",
                    "Entrada": c["Entrada"],
                    "Folga Sábado": "Sim" if c["Folga_Sab"] else "Não",
                } for c in colaboradores])

                cbus1, cbus2, cbus3 = st.columns([2, 1, 1])
                termo = cbus1.text_input("Buscar nome/chapa/subgrupo", key="col_busca_fast")
                tam_pagina = cbus2.selectbox("Por página", [10, 15, 20, 30, 50], index=1, key="col_page_size_fast")

                if termo:
                    termo_n = str(termo).strip().lower()
                    mask = (
                        df_col["Nome"].astype(str).str.lower().str.contains(termo_n, na=False)
                        | df_col["Chapa"].astype(str).str.lower().str.contains(termo_n, na=False)
                        | df_col["Subgrupo"].astype(str).str.lower().str.contains(termo_n, na=False)
                    )
                    df_view = df_col.loc[mask].reset_index(drop=True)
                else:
                    df_view = df_col.reset_index(drop=True)

                total_regs = len(df_view)
                total_pag = max(1, (total_regs + int(tam_pagina) - 1) // int(tam_pagina))
                pagina = cbus3.number_input("Página", min_value=1, max_value=total_pag, value=1, step=1, key="col_page_fast")
                ini = (int(pagina) - 1) * int(tam_pagina)
                fim = ini + int(tam_pagina)
                st.caption(f"Mostrando {min(total_regs, 0 if total_regs == 0 else ini + 1)}–{min(total_regs, fim)} de {total_regs} registro(s).")
                st.dataframe(df_view.iloc[ini:fim], use_container_width=True, height=420)
            else:
                st.info("Sem colaboradores.")

            st.markdown("---")

        elif sec_col == "➕ Cadastrar colaborador":
            colaboradores = load_colaboradores_setor(setor)
            st.markdown("## ➕ Cadastrar colaborador (perfil completo + folgas do mês)")

            ano_cfg = int(st.session_state.get("cfg_ano", datetime.now().year))
            mes_cfg = int(st.session_state.get("cfg_mes", datetime.now().month))
            ndias_cfg = calendar.monthrange(ano_cfg, mes_cfg)[1]

            with st.form("form_add_colaborador", clear_on_submit=True):
                c1, c2 = st.columns(2)
                nome_n = c1.text_input("Nome:", key="col_nome")
                chapa_n = c2.text_input("Chapa:", key="col_chapa")

                c3, c4, c5 = st.columns([1.2, 1.2, 1])
                sg_opts_new = [""] + list_subgrupos(setor)
                subgrupo_n = c3.selectbox("Subgrupo:", sg_opts_new, index=0, key="col_subgrupo")
                entrada_n = c4.selectbox("Entrada:", HORARIOS_ENTRADA_PRESET, index=HORARIOS_ENTRADA_PRESET.index("06:00") if "06:00" in HORARIOS_ENTRADA_PRESET else 0, key="col_entrada")
                folga_sab_n = c5.checkbox("Permitir folga sábado", value=False, key="col_folga_sab")

                st.caption(f"Folgas do mês para já salvar como **Folga** (competência ativa: {mes_cfg:02d}/{ano_cfg}).")
                dias_folga = st.multiselect(
                    "Selecione os dias de folga (1..31):",
                    options=list(range(1, ndias_cfg + 1)),
                    default=[],
                    key="col_dias_folga",
                )

                submitted = st.form_submit_button("Cadastrar colaborador", use_container_width=True)

                if submitted:
                    if not nome_n or not chapa_n:
                        st.error("Preencha nome e chapa.")
                    elif colaborador_exists(setor, chapa_n.strip()):
                        st.error("Já existe essa chapa.")
                    else:
                        ch_new = chapa_n.strip()
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                            rid = registrar_pendencia_ax_generica(
                                setor=setor,
                                modulo='cadastrar_colaborador',
                                acao='criar',
                                payload={'_modulo':'cadastrar_colaborador','_acao':'criar','setor':setor,'nome':nome_n.strip(),'chapa':ch_new,'subgrupo':subgrupo_n,'entrada':entrada_n,'folga_sab':bool(folga_sab_n),'dias_folga':[int(x) for x in dias_folga],'ano':int(ano_cfg),'mes':int(mes_cfg)},
                                criado_por_nome=str(auth.get('nome') or '').strip(),
                                criado_por_chapa=str(auth.get('chapa') or '').strip(),
                                observacao='Cadastro de colaborador enviado pelo AX do Líder'
                            )
                            st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                            st.rerun()
                        create_colaborador(nome_n.strip(), setor, ch_new, subgrupo=subgrupo_n, entrada=entrada_n, folga_sab=folga_sab_n)
                        for d in dias_folga:
                            set_override(setor, ano_cfg, mes_cfg, ch_new, int(d), "status", "Folga")

                        st.success("Cadastrado! (perfil + folgas do mês salvos)")
                        st.rerun()

            st.markdown("---")

        elif sec_col == "🗑️ Excluir colaborador":
            colaboradores = load_colaboradores_setor(setor)
            st.markdown("## 🗑️ Excluir colaborador")
            if colaboradores:
                opts = []
                for c in colaboradores:
                    ch = str(c.get("Chapa","")).strip()
                    nm = str(c.get("Nome","") or "").strip()
                    label = f"{ch} — {nm}" if nm else ch
                    opts.append((label, ch))
                pick = st.selectbox("Escolha a chapa para excluir:", [o[0] for o in opts], key="del_chapa_label")
                ch_del = next((o[1] for o in opts if o[0] == pick), pick.split("—")[0].strip())
                st.warning("⚠️ Excluir remove também férias, ajustes, escala e estado desse colaborador no setor.")
                confirm = st.checkbox("Confirmo que quero excluir definitivamente", key="del_confirm")
                if st.button("Excluir colaborador", key="del_btn"):
                    if not confirm:
                        st.error("Marque a confirmação para excluir.")
                    else:
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                            rid = registrar_pendencia_ax_generica(setor, 'excluir_colaborador', 'excluir', {'_modulo':'excluir_colaborador','_acao':'excluir','setor':setor,'chapa':ch_del}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Exclusão de colaborador enviada pelo AX do Líder')
                            st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                            st.rerun()
                        delete_colaborador_total(setor, ch_del)
                        st.success("Colaborador excluído!")
                        st.rerun()

            st.markdown("---")

        elif sec_col == "✏️ Editar perfil":
            colaboradores = load_colaboradores_setor(setor)
            st.markdown("## ✏️ Editar perfil do colaborador")
            if colaboradores:
                chapas = [c["Chapa"] for c in colaboradores]
                nome_by_chapa = {c["Chapa"]: c.get("Nome", "") for c in colaboradores}
                ch_sel = st.selectbox(
                    "Colaborador (Nome — Chapa):",
                    chapas,
                    key="pf_chapa",
                    format_func=lambda ch: f"{(nome_by_chapa.get(ch, ch) or ch)} — {ch}",
                )
                csel = next(x for x in colaboradores if x["Chapa"] == ch_sel)

                last = st.session_state.get("pf_last_chapa")
                if last != ch_sel:
                    _ent_atual = (csel.get("Entrada") or BALANCO_DIA_ENTRADA).strip()
                    st.session_state["pf_ent_sel"] = _ent_atual

                    _sg = (csel.get("Subgrupo") or "").strip()
                    _sg_opts = [""] + list_subgrupos(setor)
                    st.session_state["pf_sg"] = _sg if _sg in _sg_opts else ""

                    st.session_state["pf_sab"] = bool(csel.get("Folga_Sab"))
                    st.session_state["pf_last_chapa"] = ch_sel

                if st.session_state.get("pf_last_chapa_edit") != ch_sel:
                    st.session_state["pf_chapa_edit"] = ch_sel
                    st.session_state["pf_nome_edit"] = (csel.get("Nome") or "").strip()
                    st.session_state["pf_last_chapa_edit"] = ch_sel

                colp0, colp1 = st.columns(2)
                nome_edit = colp0.text_input("Nome:", key="pf_nome_edit")
                chapa_edit = colp1.text_input("Chapa:", key="pf_chapa_edit")

                ent_atual = (csel.get("Entrada") or BALANCO_DIA_ENTRADA).strip()
                opcoes_ent = list(HORARIOS_ENTRADA_PRESET)
                if ent_atual and ent_atual not in opcoes_ent:
                    opcoes_ent = opcoes_ent + [ent_atual]

                colp2, colp3, colp4 = st.columns(3)
                ent_sel = colp2.selectbox("Entrada:", options=opcoes_ent, key="pf_ent_sel")

                sg_opts = [""] + list_subgrupos(setor)
                sg_atual = (csel.get("Subgrupo") or "").strip()
                if sg_atual and sg_atual not in sg_opts:
                    sg_opts.append(sg_atual)
                sg = colp3.selectbox("Subgrupo:", sg_opts, key="pf_sg")
                sab = colp4.checkbox("Permitir folga sábado", key="pf_sab")

                if st.button("Salvar perfil", key="pf_save"):
                    if not (nome_edit or "").strip():
                        st.error("Preencha o nome.")
                    elif not (chapa_edit or "").strip():
                        st.error("Preencha a chapa.")
                    else:
                        try:
                            if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                                rid = registrar_pendencia_ax_generica(setor, 'editar_perfil', 'salvar', {'_modulo':'editar_perfil','_acao':'salvar','setor':setor,'ch_sel':ch_sel,'chapa_edit':chapa_edit,'nome_edit':nome_edit,'sg':sg,'ent_sel':ent_sel,'sab':bool(sab)}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Edição de perfil enviada pelo AX do Líder')
                                st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                                st.rerun()
                            update_colaborador_perfil(setor, ch_sel, chapa_edit, nome_edit, sg, ent_sel, sab)
                            st.success("Salvo!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                st.markdown("---")

        elif sec_col == "🔑 Alterar senha colaborador":
            colaboradores = load_colaboradores_setor(setor)
            st.markdown("## 🔑 Alterar senha colaborador")
            if colaboradores:
                chapas = [c["Chapa"] for c in colaboradores]
                nome_by_chapa = {c["Chapa"]: c.get("Nome", "") for c in colaboradores}
                ch_sel_pwd = st.selectbox(
                    "Colaborador (Nome — Chapa):",
                    chapas,
                    key="pwd_chapa",
                    format_func=lambda ch: f"{(nome_by_chapa.get(ch, ch) or ch)} — {ch}",
                )
                csel_pwd = next(x for x in colaboradores if x["Chapa"] == ch_sel_pwd)
                user_pwd = get_usuario_sistema_por_setor_chapa(setor, ch_sel_pwd)

                colx1, colx2 = st.columns(2)
                colx1.text_input("Nome:", value=(csel_pwd.get("Nome") or "").strip(), disabled=True, key="pwd_nome_view")
                colx2.text_input("Chapa:", value=str(ch_sel_pwd or "").strip(), disabled=True, key="pwd_chapa_view")
                colx3, colx4 = st.columns(2)
                colx3.text_input("Setor:", value=str(setor or "").strip(), disabled=True, key="pwd_setor_view")
                perfil_view = "ADMIN" if (user_pwd and user_pwd.get("is_admin")) else "LÍDER" if (user_pwd and user_pwd.get("is_lider")) else "AX LÍDER" if (user_pwd and user_pwd.get("is_ax_lider")) else "COLABORADOR" if user_pwd else "SEM ACESSO"
                colx4.text_input("Perfil:", value=perfil_view, disabled=True, key="pwd_perfil_view")

                nova_senha = st.text_input("Nova senha", type="password", key="pwd_nova")
                confirma_senha = st.text_input("Confirmar nova senha", type="password", key="pwd_confirma")
                gerar_tmp = st.checkbox("Gerar senha temporária automática", value=False, key="pwd_auto_temp")

                if st.session_state.get("pwd_temp_last") and st.session_state.get("pwd_temp_last_chapa") == ch_sel_pwd:
                    st.success("🔑 Senha temporária criada com sucesso.")
                    st.code(st.session_state.get("pwd_temp_last"), language=None)
                    st.caption("Copie essa senha e envie ao colaborador. No próximo login ele será obrigado a trocar a senha.")

                if st.button("Salvar nova senha", key="pwd_save"):
                    senha_final = ""
                    forcar_troca = False
                    if gerar_tmp:
                        senha_final = gerar_senha_temporaria_colaborador(8)
                        forcar_troca = True
                    else:
                        senha_final = (nova_senha or "").strip()
                        if not senha_final:
                            st.error("Digite a nova senha ou marque a senha temporária automática.")
                            st.stop()
                        if senha_final != (confirma_senha or "").strip():
                            st.error("A confirmação da senha não confere.")
                            st.stop()
                    try:
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                            rid = registrar_pendencia_ax_generica(setor, 'alterar_senha', 'salvar', {'_modulo':'alterar_senha','_acao':'salvar','setor':setor,'chapa':ch_sel_pwd,'nome':(csel_pwd.get("Nome") or "").strip(),'senha_final':senha_final,'forcar_troca':bool(forcar_troca)}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Alteração de senha enviada pelo AX do Líder')
                            st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                            st.rerun()
                        if not user_pwd:
                            upsert_usuario_sistema(
                                nome=(csel_pwd.get("Nome") or "").strip(),
                                setor=setor,
                                chapa=ch_sel_pwd,
                                senha=senha_final,
                                is_admin=False,
                                is_lider=False,
                                forcar_troca_senha=forcar_troca,
                            )
                            msg_base = "Acesso criado e senha definida com sucesso."
                        else:
                            update_password(setor, ch_sel_pwd, senha_final)
                            set_force_change_password(setor, ch_sel_pwd, forcar_troca)
                            msg_base = "Senha alterada com sucesso."
                        if gerar_tmp:
                            st.session_state["pwd_temp_last"] = senha_final
                            st.session_state["pwd_temp_last_chapa"] = ch_sel_pwd
                            st.success(msg_base)
                            st.success("🔑 Senha temporária criada com sucesso.")
                            st.code(senha_final, language=None)
                            st.caption("Copie essa senha e envie ao colaborador. No próximo login ele será obrigado a trocar a senha.")
                        else:
                            st.session_state["pwd_temp_last"] = ""
                            st.session_state["pwd_temp_last_chapa"] = ""
                            st.success(msg_base)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Falha ao alterar senha: {e}")
            else:
                st.info("Sem colaboradores para alterar senha.")

            st.markdown("---")

        elif sec_col == "🛠️ Atualizar funcionário (AX/Líder)":
            st.info("Esta subaba foi removida para LÍDER e AX_LIDER.")
            sec_col = "👥 Colaboradores"
            st.rerun()
            eh_ax = bool(auth.get("is_ax_lider", False)) and not bool(auth.get("is_admin", False))
            st.caption("Perfil AX do Líder propõe alterações. Perfil Líder aprova na subaba de aprovações. Admin e Líder podem aplicar direto.")
            try:
                con = db_conn()
                df_func_ax = pd.read_sql_query(
                    """
                    SELECT nome, setor, chapa, COALESCE(subgrupo,'') AS subgrupo, COALESCE(entrada,'06:00') AS entrada, COALESCE(folga_sab,0) AS folga_sab
                    FROM colaboradores
                    ORDER BY setor, nome
                    """,
                    con,
                )
                df_login_ax = pd.read_sql_query(
                    """
                    SELECT setor, chapa, COALESCE(is_admin,0) AS is_admin, COALESCE(is_lider,0) AS is_lider, COALESCE(is_ax_lider,0) AS is_ax_lider
                    FROM usuarios_sistema
                    """,
                    con,
                )
                con.close()
            except Exception:
                df_func_ax = pd.DataFrame(columns=['nome','setor','chapa','subgrupo','entrada','folga_sab'])
                df_login_ax = pd.DataFrame(columns=['setor','chapa','is_admin','is_lider','is_ax_lider'])

            if df_func_ax.empty:
                st.info("Nenhum colaborador cadastrado para atualizar.")
            else:
                setores_ax = sorted({_norm_setor(x) for x in df_func_ax['setor'].dropna().tolist() if str(x).strip()})
                ax1, ax2 = st.columns([1, 1.7])
                with ax1:
                    setor_ax = st.selectbox("Setor do funcionário", setores_ax, key="ax_func_setor")
                df_func_setor_ax = df_func_ax[df_func_ax['setor'].astype(str).str.strip().str.upper() == _norm_setor(setor_ax)].copy()
                opts_ax = [f"{str(r['nome']).strip()} ({str(r['chapa']).strip()})" for _, r in df_func_setor_ax.iterrows()]
                with ax2:
                    pick_ax = st.selectbox("Funcionário", opts_ax, key="ax_func_pick") if opts_ax else None

                rec_ax = None
                chapa_ax = ""
                if pick_ax:
                    chapa_ax = pick_ax.rsplit("(", 1)[-1].replace(")", "").strip()
                    df_hit_ax = df_func_setor_ax[df_func_setor_ax['chapa'].astype(str).str.strip() == chapa_ax]
                    if not df_hit_ax.empty:
                        rec_ax = df_hit_ax.iloc[0].to_dict()

                if rec_ax:
                    login_hit_ax = df_login_ax[(df_login_ax['setor'].astype(str).str.strip().str.upper() == _norm_setor(setor_ax)) & (df_login_ax['chapa'].astype(str).str.strip() == chapa_ax)]
                    is_admin_cur_ax = bool(int(login_hit_ax.iloc[0]['is_admin'])) if not login_hit_ax.empty else False
                    is_lider_cur_ax = bool(int(login_hit_ax.iloc[0]['is_lider'])) if not login_hit_ax.empty else False
                    is_ax_cur_ax = bool(int(login_hit_ax.iloc[0]['is_ax_lider'])) if not login_hit_ax.empty else False
                    perfil_cur_ax = 'ADMIN' if is_admin_cur_ax else ('LIDER' if is_lider_cur_ax else ('AX_LIDER' if is_ax_cur_ax else 'COLABORADOR'))

                    st.write(f"Atualizando: **{str(rec_ax.get('nome') or '').strip()}** — chapa **{chapa_ax}**")
                    x1, x2, x3, x4 = st.columns([1.4, 1.2, 1.2, 1])
                    with x1:
                        nome_ax_novo = st.text_input("Nome", value=str(rec_ax.get('nome') or '').strip(), key='ax_func_nome')
                    with x2:
                        subgrupo_ax_novo = st.text_input("Subgrupo", value=str(rec_ax.get('subgrupo') or '').strip(), key='ax_func_subgrupo')
                    with x3:
                        entrada_ax_nova = st.text_input("Entrada padrão", value=str(rec_ax.get('entrada') or '06:00').strip() or '06:00', key='ax_func_entrada')
                    with x4:
                        folga_sab_ax = st.checkbox("Folga sábado", value=bool(int(rec_ax.get('folga_sab', 0) or 0)), key='ax_func_folga_sab')

                    perfil_ax_novo = st.selectbox("Perfil do sistema", ['COLABORADOR', 'AX_LIDER', 'LIDER', 'ADMIN'], index=['COLABORADOR', 'AX_LIDER', 'LIDER', 'ADMIN'].index(perfil_cur_ax), key='ax_func_perfil')
                    obs_ax = st.text_area("Observação / motivo da alteração", key="ax_func_obs", height=90)

                    if eh_ax:
                        if st.button("📨 Enviar alteração para aprovação do líder", key='ax_func_salvar'):
                            try:
                                rid = registrar_solicitacao_ax_lider(
                                    setor_solicitante=setor,
                                    setor_alvo=setor_ax,
                                    chapa_alvo=chapa_ax,
                                    nome_alvo=str(rec_ax.get('nome') or '').strip(),
                                    nome_novo=nome_ax_novo,
                                    subgrupo_novo=subgrupo_ax_novo,
                                    perfil_novo=perfil_ax_novo,
                                    entrada_nova=entrada_ax_nova,
                                    folga_sab_nova=bool(folga_sab_ax),
                                    criado_por_nome=str(auth.get('nome') or '').strip(),
                                    criado_por_chapa=str(auth.get('chapa') or '').strip(),
                                    observacao=obs_ax,
                                )
                                st.success(f"Solicitação enviada para aprovação do líder. Protocolo #{rid}.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Falha ao enviar solicitação: {e}")
                    else:
                        if st.button("💾 Salvar atualização do funcionário", key='ax_func_salvar'):
                            try:
                                res = admin_update_funcionario(
                                    setor=setor_ax,
                                    chapa_atual=chapa_ax,
                                    nome_novo=nome_ax_novo,
                                    subgrupo_novo=subgrupo_ax_novo,
                                    perfil_novo=perfil_ax_novo,
                                    entrada_nova=entrada_ax_nova,
                                    folga_sab=bool(folga_sab_ax),
                                    criar_usuario_se_nao_existir=True,
                                )
                                st.success(f"Funcionário atualizado com sucesso. Perfil final: {res['perfil']} | Subgrupo: {res['subgrupo'] or 'SEM SUBGRUPO'}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Falha ao atualizar funcionário: {e}")

        elif sec_col == "🧾 Aprovações AX":
            st.markdown("## 🧾 Aprovações AX do Líder")
            eh_ax = bool(auth.get("is_ax_lider", False)) and not bool(auth.get("is_admin", False))
            df_ax = listar_solicitacoes_ax_lider()
            df_axg = listar_pendencias_ax_genericas()
            if df_ax.empty and df_axg.empty:
                st.info("Nenhuma solicitação AX cadastrada.")
            else:
                if eh_ax:
                    st.caption("Aqui você acompanha suas solicitações enviadas para aprovação.")
                    if not df_ax.empty:
                        df_meu = df_ax[df_ax["criado_por_chapa"].astype(str).str.strip() == str(auth.get("chapa") or "").strip()].copy()
                        if not df_meu.empty:
                            st.markdown("### Solicitações de atualização de funcionário")
                            st.dataframe(df_meu, use_container_width=True, height=220)
                    if not df_axg.empty:
                        df_meu_g = df_axg[df_axg["criado_por_chapa"].astype(str).str.strip() == str(auth.get("chapa") or "").strip()].copy()
                        if not df_meu_g.empty:
                            df_meu_g = df_meu_g.copy()
                            df_meu_g['resumo'] = df_meu_g['modulo'].astype(str) + ' / ' + df_meu_g['acao'].astype(str)
                            st.markdown("### Demais solicitações")
                            st.dataframe(df_meu_g[['id','setor','resumo','status','observacao','criado_em','aprovado_por','aprovado_em']], use_container_width=True, height=260)
                else:
                    st.caption("O líder/admin aprova ou reprova as alterações propostas pelo AX do Líder.")
                    pend = df_ax[df_ax["status"].astype(str).str.upper() == "PENDENTE"].copy() if not df_ax.empty else pd.DataFrame()
                    pendg = df_axg[df_axg["status"].astype(str).str.upper() == "PENDENTE"].copy() if not df_axg.empty else pd.DataFrame()
                    hist = df_ax[df_ax["status"].astype(str).str.upper() != "PENDENTE"].copy() if not df_ax.empty else pd.DataFrame()
                    histg = df_axg[df_axg["status"].astype(str).str.upper() != "PENDENTE"].copy() if not df_axg.empty else pd.DataFrame()
                    if pend.empty and pendg.empty:
                        st.success("Não há pendências para aprovação no momento.")
                    else:
                        for _, r in pend.iterrows():
                            with st.container(border=True):
                                st.write(f"**Solicitação #{int(r['id'])}** — {str(r['setor_alvo'])} / {str(r['nome_alvo'])} ({str(r['chapa_alvo'])})")
                                st.write(f"**AX:** {str(r['criado_por_nome'])} ({str(r['criado_por_chapa'])})")
                                st.write(f"**Novo nome:** {str(r['nome_novo'])} | **Novo subgrupo:** {str(r['subgrupo_novo'])} | **Novo perfil:** {str(r['perfil_novo'])}")
                                st.write(f"**Entrada:** {str(r['entrada_nova'])} | **Folga sábado:** {'Sim' if bool(int(r['folga_sab_nova'] or 0)) else 'Não'}")
                                if str(r.get('observacao') or '').strip():
                                    st.caption(f"Observação: {str(r.get('observacao') or '').strip()}")
                                ap1, ap2 = st.columns(2)
                                if ap1.button("✅ Aprovar", key=f"ax_aprov_{int(r['id'])}"):
                                    try:
                                        decidir_solicitacao_ax_lider(int(r['id']), str(auth.get('nome') or '').strip(), True)
                                        st.success("Solicitação aprovada e aplicada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Falha ao aprovar: {e}")
                                if ap2.button("❌ Reprovar", key=f"ax_reprov_{int(r['id'])}"):
                                    try:
                                        decidir_solicitacao_ax_lider(int(r['id']), str(auth.get('nome') or '').strip(), False)
                                        st.warning("Solicitação reprovada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Falha ao reprovar: {e}")
                        for _, r in pendg.iterrows():
                            with st.container(border=True):
                                modulo_nome = str(r['modulo']).replace('_', ' ').title()
                                acao_nome = str(r['acao']).replace('_', ' ').title()
                                st.write(f"**Pendência #{int(r['id'])}** — {modulo_nome}")
                                st.write(f"**Quem enviou:** {str(r['criado_por_nome'])} ({str(r['criado_por_chapa'])})")
                                st.write(f"**Setor:** {str(r['setor'])} | **Ação pedida:** {acao_nome}")
                                if str(r.get('observacao') or '').strip():
                                    st.caption(f"Resumo: {str(r.get('observacao') or '').strip()}")
                                try:
                                    payload_view = json.loads(str(r.get('payload_json') or '{}'))
                                except Exception:
                                    payload_view = {}
                                resumo_linhas = _ax_resumo_pendencia_generica(payload_view)
                                if resumo_linhas:
                                    st.markdown("**O que o AX pediu:**")
                                    for linha in resumo_linhas:
                                        st.write(f"• {linha}")
                                with st.expander("Ver detalhes técnicos", expanded=False):
                                    st.json(payload_view if payload_view else {})
                                gp1, gp2 = st.columns(2)
                                if gp1.button("✅ Aprovar pendência", key=f"axg_aprov_{int(r['id'])}"):
                                    try:
                                        decidir_pendencia_ax_generica(int(r['id']), str(auth.get('nome') or '').strip(), True)
                                        st.success("Pendência aprovada e aplicada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Falha ao aprovar pendência: {e}")
                                if gp2.button("❌ Reprovar pendência", key=f"axg_reprov_{int(r['id'])}"):
                                    try:
                                        decidir_pendencia_ax_generica(int(r['id']), str(auth.get('nome') or '').strip(), False)
                                        st.warning("Pendência reprovada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Falha ao reprovar pendência: {e}")
                    if not hist.empty:
                        st.markdown("### Histórico — atualização de funcionário")
                        st.dataframe(hist, use_container_width=True, height=180)
                    if not histg.empty:
                        st.markdown("### Histórico — demais módulos")
                        histg = histg.copy()
                        histg['resumo'] = histg['modulo'].astype(str) + ' / ' + histg['acao'].astype(str)
                        st.dataframe(histg[['id','setor','resumo','status','observacao','criado_em','aprovado_por','aprovado_em']], use_container_width=True, height=220)

        elif sec_col == "🔄 Rodízio Caixa":
            st.markdown("## 🔄 Rodízio mensal Caixa 01 ↔ Caixa 02")
            if str(setor).strip().upper() != "FRENTECAIXA":
                st.info("Rodízio disponível somente para o setor FRENTECAIXA.")
            else:
                cfg = get_rodizio_caixa_cfg(setor)
                c1, c2, c3, c4 = st.columns([1.4, 1.4, 1, 1])
                if 'rod_caixa_origem' not in st.session_state:
                    st.session_state['rod_caixa_origem'] = str(cfg.get('subgrupo_origem') or 'OPERADOR DE CAIXA 01')
                if 'rod_caixa_destino' not in st.session_state:
                    st.session_state['rod_caixa_destino'] = str(cfg.get('subgrupo_destino') or 'OPERADOR DE CAIXA 02')
                if 'rod_caixa_qtd' not in st.session_state:
                    st.session_state['rod_caixa_qtd'] = int(cfg.get('qtd_destino', 14))
                if 'rod_caixa_tol' not in st.session_state:
                    st.session_state['rod_caixa_tol'] = int(cfg.get('tolerancia_min', 20))

                subgrupo_origem = c1.text_input("Subgrupo origem", key='rod_caixa_origem')
                subgrupo_destino = c2.text_input("Subgrupo destino", key='rod_caixa_destino')
                qtd_destino = int(c3.number_input("Qtd fixa no destino", min_value=1, max_value=100, step=1, key='rod_caixa_qtd'))
                tolerancia = int(c4.number_input("Tolerância (min)", min_value=0, max_value=120, step=5, key='rod_caixa_tol'))

                bcfg1, bcfg2, _bcfg3 = st.columns([1, 1, 4])
                if bcfg1.button("Salvar configuração do rodízio", key='rod_caixa_save_cfg', use_container_width=True, disabled=(_status_comp_rod == 'FECHADA')):
                    set_rodizio_caixa_cfg(setor, subgrupo_origem, subgrupo_destino, qtd_destino, tolerancia, True)
                    st.success("Configuração salva.")
                    st.rerun()
                if bcfg2.button("Voltar do zero", key='rod_caixa_reset_cfg', use_container_width=True, disabled=(_status_comp_rod == 'FECHADA')):
                    st.session_state['rod_caixa_origem'] = 'OPERADOR DE CAIXA 01'
                    st.session_state['rod_caixa_destino'] = 'OPERADOR DE CAIXA 02'
                    st.session_state['rod_caixa_qtd'] = 14
                    st.session_state['rod_caixa_tol'] = 20
                    set_rodizio_caixa_cfg(setor, 'OPERADOR DE CAIXA 01', 'OPERADOR DE CAIXA 02', 14, 20, True)
                    st.success('Configuração resetada para o padrão.')
                    st.rerun()

                ano_r = int(st.session_state.get('cfg_ano', datetime.now().year))
                mes_r = int(st.session_state.get('cfg_mes', datetime.now().month))
                _status_comp_rod = get_status_competencia(setor, ano_r, mes_r)
                if _status_comp_rod == 'FECHADA':
                    st.error(f'🔒 Competência {mes_r:02d}/{ano_r} fechada: o rodízio deste mês fica somente para consulta.')
                state_base = f"rod_caixa_aprov::{setor}::{ano_r}::{mes_r}::{subgrupo_origem}::{subgrupo_destino}"
                aprov_key = state_base + "::aprovados"
                neg_key = state_base + "::negados"
                if aprov_key not in st.session_state:
                    st.session_state[aprov_key] = {}
                if neg_key not in st.session_state:
                    st.session_state[neg_key] = []

                sim = simular_rodizio_caixa_mes(
                    setor,
                    ano_r,
                    mes_r,
                    subgrupo_origem,
                    subgrupo_destino,
                    qtd_destino,
                    tolerancia,
                    aprovados_por_slot=st.session_state.get(aprov_key, {}),
                    negados_chapas=st.session_state.get(neg_key, []),
                )
                st.caption(f"Competência ativa: {mes_r:02d}/{ano_r}. Regra fixa do rodízio: 14 trocas por mês, respeitando as cotas por horário do Caixa 01.")
                st.info(f"{subgrupo_destino}: {sim.get('qtd_destino_atual', 0)} pessoa(s) hoje. Rodízio planejado: {sim.get('qtd_troca', 0)} troca(s). Quantidade obrigatória: {sim.get('qtd_destino_obrigatoria', 14)}.")
                st.caption("Na sugestão do mês, o sistema prioriza: 1) horário fixo da cota, 2) domingo mais parecido, 3) quem está há mais tempo sem ir para o Caixa 02.")

                slots = sim.get('slots') or []
                aprovados_atuais = st.session_state.get(aprov_key, {})
                aprovados_validos = sum(1 for s in slots if aprovados_atuais.get(s.get('slot_key')) == s.get('origem_chapa'))
                top1, top2, top3 = st.columns(3)
                top1.metric('Sugestões montadas', len(slots))
                top2.metric('Aprovadas', aprovados_validos)
                top3.metric('Pendentes', max(0, len(slots) - aprovados_validos))

                a1, a2 = st.columns([1, 1])
                if a1.button('Limpar aprovações e negativas', key='rod_caixa_clear_aprov', use_container_width=True):
                    st.session_state[aprov_key] = {}
                    st.session_state[neg_key] = []
                    st.session_state.pop(state_base + "::aplicado", None)
                    st.rerun()
                if a2.button('Aprovar todas as sugestões atuais', key='rod_caixa_aprov_all', use_container_width=True):
                    st.session_state[aprov_key] = {str(s.get('slot_key')): str(s.get('origem_chapa')) for s in slots}
                    st.session_state.pop(state_base + "::aplicado", None)
                    st.rerun()

                aplic_key = state_base + "::aplicado"
                qtd_obrigatoria = int(sim.get('qtd_destino_obrigatoria', 14) or 14)
                pronto_aplicar = bool(slots) and int(aprovados_validos) >= int(qtd_obrigatoria) and int(max(0, len(slots) - aprovados_validos)) == 0

                if pronto_aplicar:
                    st.success(f"Todas as {qtd_obrigatoria} sugestões foram aprovadas. Agora falta aplicar o rodízio no mês {mes_r:02d}/{ano_r}.")
                    if st.button('🔁 Aplicar mudança de subgrupos agora (antes da escala)', key='rod_caixa_apply_now', use_container_width=True, disabled=(_status_comp_rod == 'FECHADA')):
                        res_apply = aplicar_rodizio_caixa_mes(setor, ano_r, mes_r, sim)
                        if res_apply.get('ok'):
                            st.session_state[aplic_key] = True
                            st.success(res_apply.get('msg', 'Rodízio aplicado com sucesso.'))
                            st.rerun()
                        else:
                            st.error(res_apply.get('msg', 'Não foi possível aplicar o rodízio.'))
                elif st.session_state.get(aplic_key):
                    st.success(f"Rodízio já aplicado na competência {mes_r:02d}/{ano_r}. Gere a escala novamente para refletir a troca.")
                elif slots:
                    st.info(f"Para aplicar de verdade no mês {mes_r:02d}/{ano_r}, todas as {qtd_obrigatoria} sugestões precisam estar aprovadas e depois você deve clicar em 'Aplicar mudança de subgrupos agora (antes da escala)'.")

                if slots:
                    st.markdown('### Aprovação das 14 pessoas sugeridas')
                    resumo_aprov = pd.DataFrame([{
                        'Status': 'APROVADO' if aprovados_atuais.get(s.get('slot_key')) == s.get('origem_chapa') else 'PENDENTE',
                        'Nome sugerido': s.get('origem_nome', ''),
                        'Chapa': s.get('origem_chapa', ''),
                        'Horário Caixa 01': s.get('origem_entrada', ''),
                        'Domingos origem': s.get('origem_domingos_label', ''),
                        'Última vez que foi para o Caixa 02': s.get('origem_ultimo_mes_destino_label', ''),
                        'Sai do Caixa 02': s.get('destino_nome', ''),
                        'Domingos destino': s.get('destino_domingos_label', ''),
                        'Domingos iguais trabalho': int(s.get('domingos_trabalho_iguais_qtd', 0) or 0),
                        'Domingos iguais folga': int(s.get('domingos_folga_iguais_qtd', 0) or 0),
                        'Dif. domingos': int(s.get('diff_domingos', 0) or 0),
                        'Alternativas no mesmo horário': int(s.get('alternativas_mesmo_horario', 0) or 0),
                    } for s in slots])
                    st.dataframe(resumo_aprov, use_container_width=True, height=340)

                    for i, s in enumerate(slots, start=1):
                        slot_key = str(s.get('slot_key') or '')
                        aprovado = aprovados_atuais.get(slot_key) == s.get('origem_chapa')
                        with st.container(border=True):
                            cinfo1, cinfo2, cinfo3 = st.columns([3.2, 2.1, 2.2])
                            cinfo1.markdown(
                                f"**{i}. {s.get('origem_nome', '-') }**  \n"
                                f"Chapa: `{s.get('origem_chapa', '-')}` | Horário Caixa 01: **{s.get('origem_entrada', '-') }** | Domingos: **{int(s.get('origem_domingos', 0) or 0)}**"
                            )
                            cinfo2.markdown(
                                f"**Sai do Caixa 02:** {s.get('destino_nome', '-')}  \n"
                                f"Horário destino: **{s.get('destino_entrada', '-')}** | Domingos: **{int(s.get('destino_domingos', 0) or 0)}**"
                            )
                            cinfo3.markdown(
                                f"**Última vez que entrou no Caixa 02:** {s.get('origem_ultimo_mes_destino_label', '-')}  \n"
                                f"Dif. domingos: **{int(s.get('diff_domingos', 0) or 0)}** | Alternativas restantes: **{int(s.get('alternativas_mesmo_horario', 0) or 0)}**"
                            )
                            st.caption(s.get('observacao') or '-')

                            alternativas_slot = list(s.get('alternativas_opcoes') or [])
                            mapa_alt = {}
                            opcoes_alt = []
                            for alt in alternativas_slot:
                                ch_alt = str(alt.get('chapa') or '').strip()
                                if not ch_alt or ch_alt in mapa_alt:
                                    continue
                                label_alt = (
                                    f"{str(alt.get('nome') or '-') } | chapa {ch_alt} | horário {str(alt.get('entrada') or '-')} | "
                                    f"dif. regra {int(alt.get('diff_horario_ref_min', 0) or 0)} min | domingos {int(alt.get('domingos', 0) or 0)} | "
                                    f"último Caixa 02 {str(alt.get('ultimo_mes_destino_label') or '-')}"
                                )
                                mapa_alt[ch_alt] = label_alt
                                opcoes_alt.append(ch_alt)

                            chapa_aprovada_slot = str(aprovados_atuais.get(slot_key) or '').strip()
                            chapa_padrao_slot = chapa_aprovada_slot if chapa_aprovada_slot in opcoes_alt else str(s.get('origem_chapa') or '').strip()
                            idx_padrao_slot = opcoes_alt.index(chapa_padrao_slot) if chapa_padrao_slot in opcoes_alt else 0

                            if opcoes_alt:
                                st.selectbox(
                                    'Escolha quem está mais próximo para este rodízio:',
                                    options=opcoes_alt,
                                    index=idx_padrao_slot,
                                    key=f'rod_caixa_pick_{slot_key}',
                                    format_func=lambda ch: mapa_alt.get(ch, ch),
                                )

                            bcol1, bcol2, bcol3 = st.columns([1, 1, 3])
                            if bcol1.button('✅ Aprovar seleção', key=f'rod_caixa_ok_{slot_key}', use_container_width=True, disabled=aprovado and chapa_aprovada_slot == str(s.get('origem_chapa') or '').strip()):
                                chapa_sel = str(st.session_state.get(f'rod_caixa_pick_{slot_key}', str(s.get('origem_chapa') or '')) or '').strip()
                                tmp = dict(st.session_state.get(aprov_key, {}))
                                tmp[slot_key] = chapa_sel or str(s.get('origem_chapa') or '')
                                st.session_state[aprov_key] = tmp
                                st.rerun()
                            if bcol2.button('❌ Negar e chamar próximo da fila', key=f'rod_caixa_no_{slot_key}', use_container_width=True):
                                negs = list(st.session_state.get(neg_key, []))
                                chapa_neg = str(s.get('origem_chapa') or '').strip()
                                if chapa_neg and chapa_neg not in negs:
                                    negs.append(chapa_neg)
                                tmp = dict(st.session_state.get(aprov_key, {}))
                                tmp.pop(slot_key, None)
                                st.session_state[aprov_key] = tmp
                                st.session_state[neg_key] = negs
                                st.rerun()
                            if aprovado:
                                bcol3.success('Aprovado para aplicação quando todas as 14 estiverem aprovadas.')
                            else:
                                bcol3.warning('Pendente de aprovação manual.')
                else:
                    st.warning("Nenhuma troca encontrada para aplicar neste mês.")

                pares = sim.get('pares') or []
                if pares:
                    df_pares = pd.DataFrame([{
                        'Entra no ' + subgrupo_destino: p['origem_nome'],
                        'Chapa entra': p['origem_chapa'],
                        'Horário atual entra': p['origem_entrada'],
                        'Domingos entra': p.get('origem_domingos_label', ''),
                        'Última vez no Caixa 02': p.get('origem_ultimo_mes_destino_label', ''),
                        'Sai do ' + subgrupo_destino: p['destino_nome'],
                        'Chapa sai': p['destino_chapa'],
                        'Horário atual sai': p['destino_entrada'],
                        'Domingos sai': p.get('destino_domingos_label', ''),
                        'Domingos iguais trabalho': int(p.get('domingos_trabalho_iguais_qtd', 0) or 0),
                        'Domingos iguais folga': int(p.get('domingos_folga_iguais_qtd', 0) or 0),
                        'Dif. domingos': int(p.get('diff_domingos', 0) or 0),
                        'Compatibilidade': p['compatibilidade'],
                        'Observação': p['observacao'] or '-',
                    } for p in pares])
                    st.markdown("### Simulação consolidada do mês")
                    st.dataframe(df_pares, use_container_width=True, height=380)

                cotas_horario = sim.get('cotas_horario') or []
                if cotas_horario:
                    st.markdown("### Regra fixa por horário")
                    st.dataframe(pd.DataFrame(cotas_horario), use_container_width=True, height=240)

                alertas = sim.get('alertas') or []
                if alertas:
                    st.markdown("### Alertas para liderança")
                    for a in alertas:
                        st.warning(a)

                proximos = sim.get('proximos') or []
                if proximos:
                    st.markdown("### Próximos da fila para o próximo mês")
                    st.dataframe(pd.DataFrame(proximos[:50]), use_container_width=True, height=260)

                todos_aprovados = bool(slots) and aprovados_validos == len(slots) and len(slots) >= int(sim.get('qtd_destino_obrigatoria', 14))
                b1, b2 = st.columns([1, 2])
                if not todos_aprovados:
                    b2.info('Para aplicar o rodízio, aprove manualmente todas as 14 sugestões atuais.')
                else:
                    b2.success('As 14 aprovações já estão prontas. Use o botão principal acima para aplicar. Se a base não refletir, use a sincronização manual abaixo.')
                if b1.button("🛠️ Sincronizar subgrupos base manualmente", key='rod_caixa_sync_manual', use_container_width=True):
                    try:
                        res = sincronizar_subgrupos_base_rodizio_caixa(setor, ano_r, mes_r, subgrupo_origem, subgrupo_destino)
                        if res.get('ok'):
                            st.success(res.get('msg', 'Subgrupos sincronizados com sucesso.'))
                            st.rerun()
                        else:
                            st.warning(res.get('msg', 'Nenhum dado para sincronizar.'))
                    except Exception as e:
                        st.error(str(e))

                hist = list_rodizio_caixa_hist(setor, limit=120)
                if hist:
                    st.markdown("### Relatório de trocas já aplicadas")
                    st.dataframe(pd.DataFrame(hist), use_container_width=True, height=320)

    elif sec_main == "🚀 Gerar Escala":
        st.subheader("🚀 Gerar escala")
        st.caption(f"Competência ativa: **{int(st.session_state['cfg_mes']):02d}/{int(st.session_state['cfg_ano'])}**")
        _status_comp_ger = get_status_competencia(setor, int(st.session_state['cfg_ano']), int(st.session_state['cfg_mes']))
        if _status_comp_ger == 'FECHADA':
            st.error('🔒 Competência fechada: geração e readequação ficam bloqueadas. Use a retificação pontual em Ajustes quando precisar corrigir algo.')

        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, 2])
            # v9.3 UI: mês/ano vêm somente da Competência (sidebar)
            mes = int(st.session_state["cfg_mes"])
            ano = int(st.session_state["cfg_ano"])
            c1.markdown(f"**Mês/Ano:** {mes:02d}/{ano}")
            c2.caption("Alterar em 🗓️ Competência (sidebar)")
            seed = c3.number_input("Semente", min_value=0, max_value=999999, value=int(st.session_state.get("last_seed", 0)), key="gen_seed")


        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Cadastre colaboradores.")
        else:
            b1, b2, b3, _ = st.columns([1, 1, 1, 5])
            if b1.button("🚀 Gerar agora (respeita ajustes)", use_container_width=True, key="gen_btn", disabled=(_status_comp_ger == 'FECHADA')):
                _clear_preview_cache(setor, int(ano), int(mes))
                st.session_state["last_seed"] = int(seed)
                ok = _regenerar_mes_inteiro(setor, int(ano), int(mes), seed=int(seed), respeitar_ajustes=True)
                if ok:
                    st.success("Escala gerada (ajustes/travas preservados)!")
                else:
                    st.warning("Sem colaboradores.")
                st.rerun()

            if b2.button("🔄 Recarregar do banco", use_container_width=True, key="gen_reload_btn"):
                _clear_preview_cache(setor, int(ano), int(mes))
                st.rerun()

            # 🧹 Gerar do zero: ignora travas/ajustes (recalcula o mês totalmente)
            # -> pede confirmação antes de apagar os overrides do mês.
            if b3.button("🧹 Gerar do zero (ignorar ajustes)", use_container_width=True, key="gen_zero_btn", disabled=(_status_comp_ger == 'FECHADA')):
                st.session_state["confirm_gen_zero"] = True

            if st.session_state.get("confirm_gen_zero", False):
                st.warning(f"Tem certeza que deseja **zerar a escala {mes:02d}/{ano}**? Isso apaga ajustes/travas (overrides) desse mês.", icon="⚠️")
                cy, cn, _sp = st.columns([1, 1, 5])
                if cy.button("✅ Sim", use_container_width=True, key="gen_zero_yes"):
                    st.session_state["confirm_gen_zero"] = False
                    # Importante: se existirem overrides antigos no mês, eles podem "forçar" Folga/Trabalho e aparentar que o motor não funcionou.
                    # Ao gerar do zero, limpamos overrides do mês selecionado (não mexe em meses anteriores).
                    delete_overrides_mes(setor, int(ano), int(mes))
                    _clear_preview_cache(setor, int(ano), int(mes))
                    st.session_state["last_seed"] = int(seed)
                    ok = _regenerar_mes_inteiro(setor, int(ano), int(mes), seed=int(seed), respeitar_ajustes=False)
                    if ok:
                        st.success("Escala gerada do zero (ajustes ignorados)!")
                    else:
                        st.warning("Sem colaboradores.")
                    st.rerun()

                if cn.button("❌ Não", use_container_width=True, key="gen_zero_no"):
                    st.session_state["confirm_gen_zero"] = False
                    st.info("Ação cancelada.")
                    st.rerun()


            preview_key = f"gerar_preview_loaded_{setor}_{ano}_{mes}"
            if preview_key not in st.session_state:
                st.session_state[preview_key] = False

            cprev1, cprev2 = st.columns([1, 5])
            if cprev1.button("📅 Carregar calendário", use_container_width=True, key=f"btn_load_preview_{setor}_{ano}_{mes}"):
                st.session_state[preview_key] = True
                st.rerun()
            if cprev2.button("🧹 Ocultar visualização", use_container_width=True, key=f"btn_hide_preview_{setor}_{ano}_{mes}"):
                st.session_state[preview_key] = False
                st.rerun()

            if st.session_state.get(preview_key, False):
                with st.spinner("Carregando calendário do mês..."):
                    hist_db, cal = _ensure_preview_cache(setor, int(ano), int(mes), colaboradores)

                if hist_db:
                    st.markdown("### 📅 Calendário RH (visual por colaborador)")
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
            else:
                st.info("Visualização pesada ficou sob demanda para deixar a navegação mais rápida. Clique em **Carregar calendário** quando quiser ver a escala do mês.")

    # ------------------------------------------------------
    # ABA 3: Ajustes
    # ------------------------------------------------------
    elif sec_main == "⚙️ Ajustes":
        st.subheader("⚙️ Ajustes (travas) — sempre entram na geração")

        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, 2])
            # v9.3 UI: mês/ano vêm somente da Competência (sidebar)
            mes = int(st.session_state["cfg_mes"])
            ano = int(st.session_state["cfg_ano"])
            c1.markdown(f"**Mês/Ano:** {mes:02d}/{ano}")
            c2.caption("Alterar em 🗓️ Competência (sidebar)")
            c3.caption("Ajustes aplicam na competência ativa.")

        sec_aj = st.radio("", ["🧩 Folgas manuais em grade", "📊 Contagens por dia", "🔁 Troca de horários", "✅ Preferência por subgrupo", "📌 Subgrupos (editável)", "✏️ Retificar folga, horário e subgrupo"], horizontal=True, key="ajustes_nav_fast", label_visibility="collapsed")

        status_comp = get_status_competencia(setor, ano, mes)
        _is_admin_auth = bool((auth or {}).get('is_admin', False))
        cst1, cst2, cst3 = st.columns([1,1,3])
        cst1.metric('Status da competência', status_comp)
        if cst2.button('🔒 Fechar competência', key=f'fechar_comp::{setor}::{ano}::{mes}', disabled=(status_comp == 'FECHADA')):
            set_status_competencia(setor, ano, mes, 'FECHADA')
            st.success('Competência fechada. Visualização preservada.')
            st.rerun()
        if _is_admin_auth:
            if cst3.button('🔓 Reabrir competência', key=f'reabrir_comp::{setor}::{ano}::{mes}', disabled=(status_comp == 'ABERTA')):
                set_status_competencia(setor, ano, mes, 'ABERTA')
                st.warning('Competência reaberta para edição.')
                st.rerun()
        else:
            cst3.caption('🔓 Reabrir competência: disponível somente para admin.')
        if status_comp == 'FECHADA' and sec_aj != '✏️ Retificar folga, horário e subgrupo':
            st.error('🔒 Competência fechada: nesta área a visualização é apenas leitura. Use a subaba de retificação para correções pontuais.')

        _ajustes_precisam_escala = sec_aj in ("🧩 Folgas manuais em grade", "📊 Contagens por dia", "🔁 Troca de horários")
        hist_db = {}
        colaboradores = []
        colab_by = {}

        if _ajustes_precisam_escala:
            _aj_load_key = f"ajustes_loaded::{setor}::{ano}::{mes}::{sec_aj}"
            if _aj_load_key not in st.session_state:
                st.session_state[_aj_load_key] = False
            c_load1, c_load2, c_load3 = st.columns([1, 1, 3])
            if c_load1.button("📥 Carregar dados dos ajustes", key=f"btn_{_aj_load_key}"):
                st.session_state[_aj_load_key] = True
            if c_load2.button("🧹 Limpar cache desta tela", key=f"clear_{_aj_load_key}"):
                st.session_state.pop(_aj_load_key, None)
                st.rerun()
            c_load3.caption("Para deixar leve, a grade só carrega quando você clicar no botão.")

            if not st.session_state.get(_aj_load_key, False):
                st.info("Esta aba carrega sob demanda. Clique em 📥 Carregar dados dos ajustes para abrir a grade.")
            else:
                with st.spinner("Carregando dados dos ajustes..."):
                    hist_db = get_hist_mes_com_overrides_cached(setor, ano, mes)
                    colaboradores = load_colaboradores_setor(setor)
                    colab_by = {c["Chapa"]: c for c in colaboradores}

                if not hist_db:
                    st.info("Gere a escala primeiro na aba 🚀 Gerar Escala.")
                    return

                if sec_aj == "🧩 Folgas manuais em grade":
                    st.markdown("### 🧩 Folgas manuais em grade (por colaborador)")
                    st.caption("Marque/desmarque as folgas do mês. Isso cria/remove travas (overrides) de Status=Folga. Domingo é editável aqui (manual é soberano).")
                    # --- filtro de colaboradores (para facilitar)
                    # Regra v8.4:
                    # - Se você selecionar 1+ colaboradores, a grade mostra SOMENTE os selecionados (mesmo se "Mostrar todos" estiver marcado).
                    # - Se não selecionar ninguém, a grade respeita o checkbox (todos ou nenhum).
                    show_all = st.checkbox("👥 Mostrar todos os colaboradores", value=True, key="grid_show_all")

                    labels_opts = [f'{c["Nome"]} ({c["Chapa"]})' for c in colaboradores]
                    inv_label = {f'{c["Nome"]} ({c["Chapa"]})': str(c["Chapa"]) for c in colaboradores}

                    sel_labels = st.multiselect(
                        "Selecionar colaboradores para editar (se selecionar, a grade mostra somente eles):",
                        options=labels_opts,
                        default=st.session_state.get("grid_sel_labels", []),
                        key="grid_sel_labels"
                    )
                    sel_chapas = [inv_label[l] for l in sel_labels if l in inv_label]

                    if sel_chapas:
                        colaboradores = [c for c in colaboradores if str(c["Chapa"]) in set(sel_chapas)]
                        st.caption(f"Mostrando {len(colaboradores)} colaborador(es) selecionado(s).")
                    else:
                        colaboradores = colaboradores if show_all else []
                        if not show_all:
                            st.info("Marque 'Mostrar todos' ou selecione 1+ colaboradores acima.")


                    qtd = calendar.monthrange(int(ano), int(mes))[1]
                    dias = list(range(1, qtd + 1))

                    # pega overrides existentes
                    ovdf = load_overrides(setor, ano, mes)
                    ov_status = {}
                    if ovdf is not None and not ovdf.empty:
                        od = ovdf[ovdf["campo"] == "status"]
                        for _, r in od.iterrows():
                            if str(r["valor"]) == "Folga":
                                ov_status.setdefault(str(r["chapa"]), set()).add(int(r["dia"]))

                    # monta grade
                    rows = []
                    for c in colaboradores:
                        chg = str(c["Chapa"])
                        row = {"Nome": c["Nome"], "Chapa": chg}
                        dfh = hist_db.get(chg)
                        for d in dias:
                            if dfh is not None and len(dfh) >= d:
                                if dfh.loc[d - 1, "Status"] == "Férias":
                                    row[str(d)] = False
                                else:
                                    row[str(d)] = (dfh.loc[d - 1, "Status"] == "Folga") or (d in ov_status.get(chg, set()))
                            else:
                                row[str(d)] = False
                        rows.append(row)

                    df_grid = pd.DataFrame(rows)
                    edited = st.data_editor(
                        df_grid,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={str(d): st.column_config.CheckboxColumn(str(d), width="small") for d in dias},
                        key="grid_editor"
                    )

                    auto_readequar = st.checkbox("🔄 Readequar escala ao salvar (somente se você quiser)", value=False, key="grid_auto_regen")

                    if st.button("💾 Salvar folgas manuais (e readequar mês)", key="grid_save", disabled=(status_comp == 'FECHADA')):
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                            rid = registrar_pendencia_ax_generica(setor, 'folgas_grade', 'salvar', {'_modulo':'folgas_grade','_acao':'salvar','setor':setor,'ano':int(ano),'mes':int(mes),'qtd':int(qtd),'edited':edited.to_dict(orient='records'),'auto_readequar':bool(auto_readequar),'seed':int(st.session_state.get('last_seed', 0))}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Folgas manuais enviadas pelo AX do Líder')
                            st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                            st.rerun()
                        set_folga = 0
                        set_trab = 0
                        for _, r in edited.iterrows():
                            chg = str(r["Chapa"])
                            dfh = hist_db.get(chg)
                            ent_pad_local = colab_by.get(chg, {}).get("Entrada", "06:00")
                            for d in dias:
                                want_folga = bool(r[str(d)])
                                if dfh is not None and len(dfh) >= d:
                                    if dfh.loc[d - 1, "Status"] == "Férias":
                                        continue

                                if want_folga:
                                    set_override(setor, ano, mes, chg, d, "status", "Folga")
                                    set_folga += 1
                                else:
                                    # ✅ regra pedida: desmarcado = TRABALHO (travado)
                                    set_override(setor, ano, mes, chg, d, "status", "Trabalho")
                                    # mantém horário padrão no banco via geração/descanso global; se quiser travar horário também,
                                    # descomente as linhas abaixo:
                                    # set_override(setor, ano, mes, chg, d, "h_entrada", ent_pad_local)
                                    # set_override(setor, ano, mes, chg, d, "h_saida", _saida_from_entrada(ent_pad_local))
                                    set_trab += 1

                        if auto_readequar:
                            _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)

                        st.success(f"Salvo! Folgas travadas: {set_folga} | Trabalhos travados: {set_trab}.")
                        st.rerun()

                elif sec_aj == "🧷 Folga fixa":
                    st.markdown("### 🧷 Folga fixa por colaborador")
                    st.caption("Escolha a pessoa, marque os dias da semana de folga fixa e valide antes de salvar. Se quebrar regra, o sistema avisa e você decide se quer salvar mesmo assim.")

                    if not colaboradores:
                        colaboradores = load_colaboradores_setor(setor)
                        colab_by = {c["Chapa"]: c for c in colaboradores}
                    labels_ff = [f'{c["Nome"]} ({c["Chapa"]})' for c in colaboradores]
                    inv_ff = {f'{c["Nome"]} ({c["Chapa"]})': str(c["Chapa"]) for c in colaboradores}
                    label_sel_ff = st.selectbox("Colaborador:", options=labels_ff, key="folga_fixa_colab")
                    chapa_ff = inv_ff.get(label_sel_ff, "")
                    atuais_ff = get_folga_fixa_weekdays(setor, chapa_ff)
                    dias_sel_ff = st.multiselect(
                        "Dias da semana de folga fixa:",
                        options=list(range(7)),
                        default=atuais_ff,
                        format_func=lambda x: WEEKDAY_LABELS_LONG.get(int(x), str(x)),
                        key=f"folga_fixa_days::{chapa_ff}::{ano}::{mes}",
                    )

                    dias_mes_fixos = _dias_mes_por_weekdays(ano, mes, dias_sel_ff)
                    st.caption("Dias da competência afetados: " + (", ".join(f"{d:02d}" for d in dias_mes_fixos) if dias_mes_fixos else "nenhum"))

                    if hist_db:
                        df_hist_ff = hist_db.get(chapa_ff)
                    else:
                        df_hist_ff = get_hist_mes_com_overrides_cached(setor, ano, mes).get(chapa_ff)
                    warnings_ff = _simulate_folga_fixa_warnings(df_hist_ff, ano, mes, dias_mes_fixos) if chapa_ff else []
                    if warnings_ff:
                        st.warning("Validação da folga fixa encontrou estes pontos:")
                        for msg in warnings_ff:
                            st.write(f"- {msg}")
                    else:
                        st.success("Nenhuma quebra visível encontrada para esta folga fixa na competência ativa.")

                    force_ff = st.checkbox("Salvar mesmo se houver alerta de regra", value=False, key="folga_fixa_force")
                    col_ff1, col_ff2, col_ff3 = st.columns([1,1,2])
                    if col_ff1.button("💾 Salvar folga fixa", key="folga_fixa_salvar"):
                        if warnings_ff and not force_ff:
                            st.error("Há alertas de regra. Marque a opção para salvar mesmo assim, se quiser forçar.")
                        else:
                            save_folga_fixa(setor, chapa_ff, dias_sel_ff)
                            # aplica como trava manual do mês ativo
                            if dias_mes_fixos:
                                for dia in dias_mes_fixos:
                                    set_override(setor, ano, mes, chapa_ff, dia, "status", "Folga")
                            st.success("Folga fixa salva e aplicada como trava manual na competência ativa.")
                            st.rerun()
                    if col_ff2.button("🗑️ Remover folga fixa", key="folga_fixa_remover"):
                        remove_folga_fixa(setor, chapa_ff)
                        st.success("Folga fixa removida. As travas já gravadas no mês atual continuam até você alterar manualmente a grade ou regenerar.")
                        st.rerun()
                    folga_fixa_df = list_folga_fixa(setor)
                    if not folga_fixa_df.empty:
                        st.markdown("#### Folgas fixas cadastradas")
                        st.dataframe(folga_fixa_df[["Nome", "Chapa", "Dia", "Ativo", "CriadoEm"]], use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhuma folga fixa cadastrada ainda.")

                elif sec_aj == "🗂️ Inventário":
                    st.markdown("### 🗂️ Inventário")
                    st.caption("Escolha o dia e informe quantas pessoas você quer em abertura, intermediário e fechamento. A tabela mensal continua abaixo para conferência rápida.")
                    qtd_inv = calendar.monthrange(int(ano), int(mes))[1]
                    inv_atual = get_inventario_mes(setor, ano, mes)
                    inv_map = {int(r["Dia"]): r for _, r in inv_atual.iterrows()} if not inv_atual.empty else {}

                    dia_inv = st.selectbox(
                        "Dia do inventário:",
                        options=list(range(1, qtd_inv + 1)),
                        key=f"inventario_dia_foco::{setor}::{ano}::{mes}",
                    )
                    base_inv = inv_map.get(int(dia_inv), {})
                    data_inv = date(int(ano), int(mes), int(dia_inv))
                    st.info("Aqui você define quantas pessoas quer no dia do balanço em cada faixa: abertura, intermediário e fechamento.")
                    st.caption(f"Data escolhida: {data_inv.strftime('%d/%m/%Y')} — {WEEKDAY_LABELS_LONG[data_inv.weekday()]}")

                    ci1, ci2, ci3 = st.columns(3)
                    meta_ab = ci1.number_input(
                        "Abertura",
                        min_value=0,
                        step=1,
                        value=int(base_inv["Abertura"]) if base_inv != {} else 0,
                        key=f"meta_abertura::{setor}::{ano}::{mes}::{dia_inv}",
                    )
                    meta_in = ci2.number_input(
                        "Intermediário",
                        min_value=0,
                        step=1,
                        value=int(base_inv["Intermediario"]) if base_inv != {} else 0,
                        key=f"meta_intermediario::{setor}::{ano}::{mes}::{dia_inv}",
                    )
                    meta_fe = ci3.number_input(
                        "Fechamento",
                        min_value=0,
                        step=1,
                        value=int(base_inv["Fechamento"]) if base_inv != {} else 0,
                        key=f"meta_fechamento::{setor}::{ano}::{mes}::{dia_inv}",
                    )

                    csave1, csave2 = st.columns([1, 3])
                    if csave1.button("💾 Salvar dia selecionado", key=f"inventario_salvar_dia::{setor}::{ano}::{mes}::{dia_inv}"):
                        upsert_inventario_dia(setor, ano, mes, int(dia_inv), int(meta_ab), int(meta_in), int(meta_fe))
                        st.success(f"Inventário salvo para o dia {int(dia_inv):02d}/{int(mes):02d}/{int(ano)}.")
                        st.rerun()
                    csave2.caption("Use esta área para cadastrar a necessidade do dia. Isso entra na geração da escala quando houver inventário configurado.")

                    rows_inv = []
                    for dia in range(1, qtd_inv + 1):
                        base = inv_map.get(dia, {})
                        rows_inv.append({
                            "Dia": dia,
                            "Data": date(int(ano), int(mes), dia).strftime("%d/%m/%Y"),
                            "Semana": WEEKDAY_LABELS_LONG[date(int(ano), int(mes), dia).weekday()],
                            "Abertura": int(base["Abertura"]) if base != {} else 0,
                            "Intermediário": int(base["Intermediario"]) if base != {} else 0,
                            "Fechamento": int(base["Fechamento"]) if base != {} else 0,
                        })
                    df_inv_view = pd.DataFrame(rows_inv)
                    st.markdown("#### Inventário do mês")
                    st.dataframe(df_inv_view, use_container_width=True, hide_index=True)

                    comp_inv = build_inventario_comparativo(setor, ano, mes, hist_db if hist_db else None)
                    if not comp_inv.empty:
                        st.markdown("#### Comparativo meta x escala atual")
                        st.dataframe(comp_inv, use_container_width=True, hide_index=True)
                    else:
                        st.info("Cadastre as metas do mês para acompanhar o comparativo depois.")

                elif sec_aj == "✏️ Retificar folga, horário e subgrupo":
                    st.markdown("### ✏️ Retificar folga, horário e subgrupo")
                    st.caption("Use esta subaba para corrigir competência fechada sem descongelar o mês inteiro. A alteração aparece nas leituras da escala e no portal do colaborador.")
                    colaboradores_ret = load_colaboradores_setor(setor)
                    if not colaboradores_ret:
                        st.info("Cadastre colaboradores primeiro.")
                    else:
                        labels_ret = [f"{c['Nome']} ({c['Chapa']})" for c in colaboradores_ret]
                        inv_ret = {f"{c['Nome']} ({c['Chapa']})": c for c in colaboradores_ret}
                        colr1, colr2, colr3 = st.columns([2,1,1])
                        label_ret = colr1.selectbox("Funcionário", options=labels_ret, key=f"ret_func::{setor}::{ano}::{mes}")
                        colab_ret = inv_ret.get(label_ret) or {}
                        chapa_ret = str(colab_ret.get('Chapa') or '').strip()
                        qtd_ret = calendar.monthrange(int(ano), int(mes))[1]
                        dia_ret = int(colr2.selectbox("Dia", options=list(range(1, qtd_ret + 1)), key=f"ret_dia::{setor}::{ano}::{mes}"))
                        hist_ret = get_hist_mes_com_overrides_cached(setor, ano, mes) or {}
                        df_ret_hist = hist_ret.get(chapa_ret)
                        base_status = ''
                        base_ent = str(colab_ret.get('Entrada') or '06:00').strip()
                        base_sai = _saida_from_entrada(base_ent)
                        if df_ret_hist is not None and len(df_ret_hist) >= dia_ret:
                            base_status = str(df_ret_hist.loc[dia_ret - 1, 'Status'] or '').strip()
                            base_ent = str(df_ret_hist.loc[dia_ret - 1, 'H_Entrada'] or '').strip()
                            base_sai = str(df_ret_hist.loc[dia_ret - 1, 'H_Saida'] or '').strip()
                        colra, colrb, colrc, colrd = st.columns([1,1,1,1])
                        novo_status = colra.selectbox("Novo status", options=['', 'Trabalho', 'Folga', 'Férias', 'Afastamento'], index=0, key=f"ret_status::{setor}::{ano}::{mes}")
                        nova_entrada = colrb.text_input("Nova entrada", value=base_ent, key=f"ret_ent::{setor}::{ano}::{mes}")
                        nova_saida = colrc.text_input("Nova saída", value=base_sai, key=f"ret_sai::{setor}::{ano}::{mes}")
                        novo_subgrupo = colrd.selectbox("Novo subgrupo", options=['', 'OPERADOR DE CAIXA 01', 'OPERADOR DE CAIXA 02'] + sorted({str(c.get('Subgrupo') or '').strip() for c in colaboradores_ret if str(c.get('Subgrupo') or '').strip()}), index=0, key=f"ret_sub::{setor}::{ano}::{mes}")
                        motivo_ret = st.text_area("Motivo da retificação", key=f"ret_motivo::{setor}::{ano}::{mes}")
                        if st.button("💾 Salvar retificação", key=f"ret_save::{setor}::{ano}::{mes}", use_container_width=True):
                            if not chapa_ret:
                                st.warning('Selecione um funcionário válido.')
                            else:
                                payload_ret = {
                                    '_modulo': 'retificacao',
                                    '_acao': 'salvar',
                                    'setor': setor,
                                    'ano': int(ano),
                                    'mes': int(mes),
                                    'chapa_ret': chapa_ret,
                                    'dia_ret': int(dia_ret),
                                    'novo_status': novo_status or base_status,
                                    'nova_entrada': nova_entrada,
                                    'nova_saida': nova_saida,
                                    'novo_subgrupo': novo_subgrupo,
                                    'motivo_ret': motivo_ret,
                                    'usuario': str(st.session_state.get('auth_nome') or st.session_state.get('auth_chapa') or ''),
                                }
                                if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)) and not bool(auth.get('is_lider', False)):
                                    registrar_pendencia_ax_generica(
                                        setor=setor,
                                        modulo='retificacao',
                                        acao='salvar',
                                        payload=payload_ret,
                                        criado_por_nome=str(auth.get('nome') or '').strip(),
                                        criado_por_chapa=str(auth.get('chapa') or '').strip(),
                                        observacao=motivo_ret,
                                    )
                                    st.success('Retificação enviada para aprovação do líder.')
                                else:
                                    salvar_retificacao_competencia(
                                        setor, ano, mes, chapa_ret, dia_ret,
                                        novo_status=novo_status or base_status,
                                        novo_entrada=nova_entrada,
                                        novo_saida=nova_saida,
                                        novo_subgrupo=novo_subgrupo,
                                        motivo=motivo_ret,
                                        usuario=str(st.session_state.get('auth_nome') or st.session_state.get('auth_chapa') or '')
                                    )
                                    st.success('Retificação salva com sucesso.')
                                st.rerun()
                        df_ret_list = load_retificacoes_competencia(setor, ano, mes)
                        if df_ret_list is not None and not df_ret_list.empty:
                            st.markdown('#### Retificações já registradas nesta competência')
                            st.dataframe(df_ret_list[[c for c in ['dia','nome','chapa','novo_status','nova_entrada','nova_saida','novo_subgrupo','motivo','usuario','criado_em'] if c in df_ret_list.columns]], use_container_width=True, hide_index=True)

                elif sec_aj == "📊 Contagens por dia":
                    st.markdown("### 📊 Contagens por dia")
                    st.caption("Mostra as contagens do dia escolhido, a visão Excel do mês e as contagens por subgrupo.")
                    qtd_cov = calendar.monthrange(int(ano), int(mes))[1]
                    dia_cov = st.selectbox(
                        "Dia para análise:",
                        options=list(range(1, qtd_cov + 1)),
                        key=f"contagens_dia_foco::{setor}::{ano}::{mes}",
                    )
                    data_cov = date(int(ano), int(mes), int(dia_cov))
                    st.caption(f"Data escolhida: {data_cov.strftime('%d/%m/%Y')} — {WEEKDAY_LABELS_LONG[data_cov.weekday()]}")

                    hist_view_inv = hist_db or get_hist_mes_com_overrides_cached(setor, ano, mes)
                    if hist_view_inv:
                        df_cov_geral = build_cobertura_diaria_geral(setor, ano, mes, hist_view_inv)
                        row_cov = df_cov_geral[df_cov_geral["Dia"] == int(dia_cov)]
                        if not row_cov.empty:
                            row_cov = row_cov.iloc[0]
                            st.markdown("#### Contagens do dia selecionado")
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("Abertura", int(row_cov["Abertura"]))
                            m2.metric("Intermediário", int(row_cov["Intermediário"]))
                            m3.metric("Fechamento", int(row_cov["Fechamento"]))
                            m4.metric("Total trabalhando", int(row_cov["Total trabalhando"]))
                            m5, m6, m7 = st.columns(3)
                            m5.metric("Folga", int(row_cov["Folga"]))
                            m6.metric("Férias", int(row_cov["Férias"]))
                            m7.metric("Afastamento", int(row_cov["Afastamento"]))

                        df_cov_sub = build_cobertura_por_subgrupo_no_dia(setor, ano, mes, int(dia_cov), hist_view_inv)
                        st.markdown("#### Contagens por dia — visão Excel (geral)")
                        st.dataframe(df_cov_geral, use_container_width=True, hide_index=True)
                        if not df_cov_sub.empty:
                            st.markdown("#### Contagens por subgrupo no dia selecionado")
                            st.dataframe(df_cov_sub, use_container_width=True, hide_index=True)
                    else:
                        st.info("Gere a escala para visualizar as contagens por dia e por subgrupo.")

                elif sec_aj == "📝 Histórico":
                    st.markdown("### 📝 Histórico")
                    st.caption("Mostra quantas pessoas estarão de folga em cada dia da competência e quem são elas.")
                    hist_view = hist_db or get_hist_mes_com_overrides_cached(setor, ano, mes)
                    if not hist_view:
                        st.info("Gere a escala primeiro para visualizar o histórico.")
                    else:
                        df_hist_dia = build_historico_folgas_diario(setor, ano, mes, hist_view)
                        st.dataframe(df_hist_dia, use_container_width=True, hide_index=True)
                        dias_hist = df_hist_dia["Dia"].tolist()
                        dia_sel_hist = st.selectbox("Ver detalhes do dia:", options=dias_hist, key="hist_dia_sel")
                        row_hist = df_hist_dia[df_hist_dia["Dia"] == int(dia_sel_hist)].iloc[0]
                        st.info(f"{row_hist['Data']} — Folga: {row_hist['Folga']} | Férias: {row_hist['Férias']} | Afastamento: {row_hist['Afastamento']} | Trabalho: {row_hist['Trabalho']}")
                        nomes_folga = str(row_hist.get('Pessoas de folga', '') or '').strip()
                        if nomes_folga:
                            st.write("**Pessoas de folga no dia:**")
                            st.write(nomes_folga)
                        else:
                            st.write("**Pessoas de folga no dia:** nenhuma")
                        st.text_area("Pessoas de folga no dia selecionado", value=str(row_hist["Pessoas de folga"] or ""), height=140, key="hist_pessoas_folga", disabled=True)

                elif sec_aj == "🔁 Troca de horários":
                                st.markdown("### 🔁 Troca de horários em grade (por colaborador)")
                                st.caption("Escolha o horário e marque (quadradinhos) os dias em que ele deve valer. **Folga/Férias sempre prevalecem**: se o dia estiver como Folga/Férias/AFA, o sistema NÃO aplica horário nesse dia.")

                                qtd2 = calendar.monthrange(int(ano), int(mes))[1]
                                dias2 = list(range(1, qtd2 + 1))

                                # --- filtro/seleção de colaboradores (mesmo layout da grade de folgas)
                                show_all_th = st.checkbox("👥 Mostrar todos os colaboradores", value=True, key="th_show_all")

                                labels_opts_th = [f'{c["Nome"]} ({c["Chapa"]})' for c in colaboradores]
                                inv_label_th = {f'{c["Nome"]} ({c["Chapa"]})': str(c["Chapa"]) for c in colaboradores}

                                sel_labels_th = st.multiselect(
                                    "Selecionar colaboradores para editar (se selecionar, a grade mostra somente eles):",
                                    options=labels_opts_th,
                                    default=st.session_state.get("th_sel_labels", []),
                                    key="th_sel_labels"
                                )
                                sel_chapas_th = [inv_label_th[l] for l in sel_labels_th if l in inv_label_th]

                                if sel_chapas_th:
                                    colaboradores = [c for c in colaboradores if str(c["Chapa"]) in set(sel_chapas_th)]
                                    st.caption(f"Mostrando {len(colaboradores)} colaborador(es) selecionado(s).")
                                else:
                                    colaboradores = colaboradores if show_all_th else []
                                    if not colaboradores:
                                        st.info("Selecione colaboradores acima ou marque 'Mostrar todos'.")
                                        # evita montar grade vazia que confunde
                                        st.stop()

                                # ação a aplicar (horário/folga/afastamento)
                                acao_th = st.selectbox(
                                    "Ação para aplicar nos dias marcados:",
                                    options=["Horário", "Folga", "Afastamento"],
                                    index=0,
                                    key="th_acao_sel"
                                )

                                horario_sel = None
                                if acao_th == "Horário":
                                    horario_sel = st.selectbox(
                                        "Horário (Entrada) para aplicar nos dias marcados:",
                                        options=HORARIOS_ENTRADA_PRESET,
                                        index=HORARIOS_ENTRADA_PRESET.index(BALANCO_DIA_ENTRADA) if BALANCO_DIA_ENTRADA in HORARIOS_ENTRADA_PRESET else 0,
                                        key="th_horario_sel"
                                    )
                                elif acao_th == "Folga":
                                    st.info("Dias marcados serão salvos como **Folga**. (Folga sempre prevalece sobre horário.)")
                                else:
                                    st.info("Dias marcados serão salvos como **Afastamento (AFA)**. Após acabar, a escala volta a seguir as regras normalmente.")
    # overrides do mês (para respeitar folgas/férias)
                                ovmap = _ov_map(setor, ano, mes)

                                # monta grade: SOMENTE Nome, Chapa e dias (checkbox)
                                rows = []
                                for c in colaboradores:
                                    ch = str(c["Chapa"])
                                    nm = c.get("Nome","")
                                    row = {"Nome": nm, "Chapa": ch}
                                    # pré-preenche conforme a ação selecionada
                                    for d in dias2:
                                        cur = (ovmap.get(ch, {}).get(d, {}) or {})
                                        if acao_th == "Horário":
                                            row[str(d)] = (cur.get("h_entrada") == horario_sel)
                                        elif acao_th == "Folga":
                                            row[str(d)] = str(cur.get("status") or "").strip().upper() in ("FOLGA","FOLG")
                                        else:
                                            row[str(d)] = str(cur.get("status") or "").strip().upper() in ("AFASTAMENTO","AFA")
                                    rows.append(row)

                                df_th = pd.DataFrame(rows)

                                edited_th = st.data_editor(
                                    df_th,
                                    use_container_width=True,
                                    hide_index=True,
                                    num_rows="fixed",
                                    column_config={str(d): st.column_config.CheckboxColumn(str(d), width="small") for d in dias2},
                                    key="th_grid_editor"
                                )

                                auto_readequar_th = st.checkbox("🔄 Readequar escala ao salvar", value=True, key="th_auto_regen")

                                if st.button("💾 Salvar troca de horários (aplicar nos dias marcados)", key="th_save"):
                                    if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                                        rid = registrar_pendencia_ax_generica(setor, 'troca_horarios', 'salvar', {'_modulo':'troca_horarios','_acao':'salvar','setor':setor,'ano':int(ano),'mes':int(mes),'qtd2':int(qtd2),'edited':edited_th.to_dict(orient='records'),'acao_th':acao_th,'horario_sel':horario_sel,'auto_readequar':bool(auto_readequar_th),'seed':int(st.session_state.get('last_seed', 0))}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Troca de horários enviada pelo AX do Líder')
                                        st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                                        st.rerun()
                                    applied = 0
                                    skipped = 0
                                    for _, r in edited_th.iterrows():
                                        ch = str(r["Chapa"])
                                        dfh = hist_db.get(ch)
                                        # horário padrão para fallback
                                        ent_pad = (colab_by.get(ch, {}) or {}).get("Entrada", BALANCO_DIA_ENTRADA)

                                        for d in dias2:
                                            want = bool(r[str(d)])

                                            # status do dia (já com overrides)
                                            status_dia = None
                                            if dfh is not None and len(dfh) >= d:
                                                status_dia = str(dfh.loc[d - 1, "Status"])
                                            st_ov = (ovmap.get(ch, {}).get(d, {}) or {}).get("status")
                                            if st_ov:
                                                status_dia = str(st_ov)

                                            st_norm = str(status_dia or "").strip().upper()

                                            if acao_th == "Horário":
                                                # ✅ regra: Folga/Férias/Afastamento sempre prevalecem (não aplicar horário)
                                                if st_norm in ("FOLGA","FOLG","FÉRIAS","FERIAS","FER","AFA","AFASTAMENTO"):
                                                    if want:
                                                        skipped += 1
                                                    continue

                                                if want:
                                                    set_override(setor, ano, mes, ch, d, "h_entrada", horario_sel)
                                                    applied += 1
                                                else:
                                                    # desmarcado: remove override de horário (limpa h_entrada do dia)
                                                    del_override(setor, ano, mes, ch, d, "h_entrada")

                                            elif acao_th == "Folga":
                                                # Folga sobrepõe qualquer horário: salva status e remove h_entrada
                                                if st_norm in ("FER","FÉRIAS","FERIAS"):
                                                    if want:
                                                        skipped += 1
                                                    continue
                                                if want:
                                                    set_override(setor, ano, mes, ch, d, "status", "Folga")
                                                    del_override(setor, ano, mes, ch, d, "h_entrada")
                                                    applied += 1
                                                else:
                                                    del_override(setor, ano, mes, ch, d, "status")

                                            else:  # Afastamento
                                                if st_norm in ("FER","FÉRIAS","FERIAS"):
                                                    if want:
                                                        skipped += 1
                                                    continue
                                                if want:
                                                    set_override(setor, ano, mes, ch, d, "status", "AFA")
                                                    del_override(setor, ano, mes, ch, d, "h_entrada")
                                                    applied += 1
                                                else:
                                                    del_override(setor, ano, mes, ch, d, "status")

                                    if auto_readequar_th:
                                        _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)

                                    st.success(f"Salvo! Ação: {acao_th}. Aplicados: {applied}. Ignorados (por conflito com Folga/Férias): {skipped}.")
                                    st.rerun()

        if sec_aj == "✏️ Retificar folga, horário e subgrupo":
            st.markdown("### ✏️ Retificar folga, horário e subgrupo")
            st.caption("Use esta subaba para corrigir competência fechada sem descongelar o mês inteiro. A alteração aparece nas leituras da escala e no portal do colaborador.")
            colaboradores_ret = load_colaboradores_setor(setor)
            if not colaboradores_ret:
                st.info("Cadastre colaboradores primeiro.")
            else:
                labels_ret = [f"{c['Nome']} ({c['Chapa']})" for c in colaboradores_ret]
                inv_ret = {f"{c['Nome']} ({c['Chapa']})": c for c in colaboradores_ret}
                colr1, colr2, colr3 = st.columns([2, 1, 1])
                label_ret = colr1.selectbox("Funcionário", options=labels_ret, key=f"ret_func_live::{setor}::{ano}::{mes}")
                colab_ret = inv_ret.get(label_ret) or {}
                chapa_ret = str(colab_ret.get('Chapa') or '').strip()
                qtd_ret = calendar.monthrange(int(ano), int(mes))[1]
                dia_ret = int(colr2.selectbox("Dia", options=list(range(1, qtd_ret + 1)), key=f"ret_dia_live::{setor}::{ano}::{mes}"))

                hist_ret = get_hist_mes_com_overrides_cached(setor, ano, mes) or {}
                df_ret_hist = hist_ret.get(chapa_ret)
                base_status = ''
                base_ent = str(colab_ret.get('Entrada') or '06:00').strip()
                base_sai = _saida_from_entrada(base_ent)
                base_sub = str(colab_ret.get('Subgrupo') or '').strip()
                if df_ret_hist is not None and len(df_ret_hist) >= dia_ret:
                    base_status = str(df_ret_hist.loc[dia_ret - 1, 'Status'] or '').strip()
                    base_ent = str(df_ret_hist.loc[dia_ret - 1, 'H_Entrada'] or '').strip()
                    base_sai = str(df_ret_hist.loc[dia_ret - 1, 'H_Saida'] or '').strip()
                    try:
                        if 'Subgrupo' in df_ret_hist.columns:
                            base_sub = str(df_ret_hist.loc[dia_ret - 1, 'Subgrupo'] or '').strip() or base_sub
                    except Exception:
                        pass

                st.info(f"Base do dia {dia_ret:02d}/{int(mes):02d}/{int(ano)} → Status: {base_status or '-'} | Entrada: {base_ent or '-'} | Saída: {base_sai or '-'} | Subgrupo: {base_sub or '-'}")
                colra, colrb, colrc, colrd = st.columns([1, 1, 1, 1])
                status_opts = ['', 'Trabalho', 'Folga', 'Férias', 'Afastamento']
                idx_status = status_opts.index(base_status) if base_status in status_opts else 0
                novo_status = colra.selectbox("Novo status", options=status_opts, index=idx_status, key=f"ret_status_live::{setor}::{ano}::{mes}")
                nova_entrada = colrb.text_input("Nova entrada", value=base_ent, key=f"ret_ent_live::{setor}::{ano}::{mes}")
                nova_saida = colrc.text_input("Nova saída", value=base_sai, key=f"ret_sai_live::{setor}::{ano}::{mes}")
                sub_opts = [''] + sorted({str(c.get('Subgrupo') or '').strip() for c in colaboradores_ret if str(c.get('Subgrupo') or '').strip()})
                if 'OPERADOR DE CAIXA 01' not in sub_opts:
                    sub_opts.append('OPERADOR DE CAIXA 01')
                if 'OPERADOR DE CAIXA 02' not in sub_opts:
                    sub_opts.append('OPERADOR DE CAIXA 02')
                sub_opts = [''] + sorted({x for x in sub_opts if x})
                idx_sub = sub_opts.index(base_sub) if base_sub in sub_opts else 0
                novo_subgrupo = colrd.selectbox("Novo subgrupo", options=sub_opts, index=idx_sub, key=f"ret_sub_live::{setor}::{ano}::{mes}")
                motivo_ret = st.text_area("Motivo da retificação", key=f"ret_motivo_live::{setor}::{ano}::{mes}")

                if st.button("💾 Salvar retificação", key=f"ret_save_live::{setor}::{ano}::{mes}", use_container_width=True):
                    if not chapa_ret:
                        st.warning('Selecione um funcionário válido.')
                    else:
                        payload_ret = {
                            '_modulo': 'retificacao',
                            '_acao': 'salvar',
                            'setor': setor,
                            'ano': int(ano),
                            'mes': int(mes),
                            'chapa_ret': chapa_ret,
                            'dia_ret': int(dia_ret),
                            'novo_status': novo_status or base_status,
                            'nova_entrada': nova_entrada,
                            'nova_saida': nova_saida,
                            'novo_subgrupo': novo_subgrupo or base_sub,
                            'motivo_ret': motivo_ret,
                            'usuario': str(st.session_state.get('auth_nome') or st.session_state.get('auth_chapa') or ''),
                        }
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)) and not bool(auth.get('is_lider', False)):
                            registrar_pendencia_ax_generica(
                                setor=setor,
                                modulo='retificacao',
                                acao='salvar',
                                payload=payload_ret,
                                criado_por_nome=str(auth.get('nome') or '').strip(),
                                criado_por_chapa=str(auth.get('chapa') or '').strip(),
                                observacao=motivo_ret,
                            )
                            st.success('Retificação enviada para aprovação do líder.')
                        else:
                            salvar_retificacao_competencia(
                                setor, ano, mes, chapa_ret, dia_ret,
                                novo_status=novo_status or base_status,
                                novo_entrada=nova_entrada,
                                novo_saida=nova_saida,
                                novo_subgrupo=novo_subgrupo or base_sub,
                                motivo=motivo_ret,
                                usuario=str(st.session_state.get('auth_nome') or st.session_state.get('auth_chapa') or '')
                            )
                            st.success('Retificação salva com sucesso.')
                        st.rerun()

                df_ret_list = load_retificacoes_competencia(setor, ano, mes)
                if df_ret_list is not None and not df_ret_list.empty:
                    st.markdown('#### Retificações já registradas nesta competência')
                    cols_view = [c for c in ['dia', 'nome', 'chapa', 'novo_status', 'nova_entrada', 'nova_saida', 'novo_subgrupo', 'motivo', 'usuario', 'criado_em'] if c in df_ret_list.columns]
                    st.dataframe(df_ret_list[cols_view], use_container_width=True, hide_index=True)

        if sec_aj == "✅ Preferência por subgrupo":
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
                    regras_pref = {"seg": int(ev_seg), "ter": int(ev_ter), "qua": int(ev_qua), "qui": int(ev_qui), "sex": int(ev_sex), "sáb": int(ev_sab)}
                    if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                        rid = registrar_pendencia_ax_generica(setor, 'preferencia_subgrupo', 'salvar', {'_modulo':'preferencia_subgrupo','_acao':'salvar','setor':setor,'sg_sel':sg_sel,'regras':regras_pref,'ano':int(ano),'mes':int(mes),'seed':int(st.session_state.get('last_seed', 0))}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Preferência de subgrupo enviada pelo AX do Líder')
                        st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                        st.rerun()
                    set_subgrupo_regras(setor, sg_sel, regras_pref)
                    _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                    st.success("Preferência salva e escala readequada!")
                    st.rerun()
            else:
                st.info("Crie pelo menos 1 subgrupo na aba 👥 Colaboradores.")

        elif sec_aj == "📌 Subgrupos (editável)":
                st.markdown("## 📌 Subgrupos (editável)")
                subgrupos = list_subgrupos(setor)

                cA, cB = st.columns([1, 1])
                with cA:
                    novo_sub = st.text_input("Novo subgrupo:", key="sg_new")
                    if st.button("Adicionar subgrupo", key="sg_add"):
                        if novo_sub.strip():
                            if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                                rid = registrar_pendencia_ax_generica(setor, 'subgrupo_add', 'criar', {'_modulo':'subgrupo_add','_acao':'criar','setor':setor,'novo_sub':novo_sub.strip()}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Inclusão de subgrupo enviada pelo AX do Líder')
                                st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                                st.rerun()
                            add_subgrupo(setor, novo_sub.strip())
                            st.success("Subgrupo adicionado!")
                            st.rerun()
                        else:
                            st.error("Digite o nome do subgrupo.")

                with cB:
                    if subgrupos:
                        del_sel = st.selectbox("Remover subgrupo:", ["(nenhum)"] + subgrupos, key="sg_del")
                        if del_sel != "(nenhum)" and st.button("Remover", key="sg_del_btn"):
                            if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                                rid = registrar_pendencia_ax_generica(setor, 'subgrupo_remove', 'remover', {'_modulo':'subgrupo_remove','_acao':'remover','setor':setor,'del_sel':del_sel,'ano':int(ano),'mes':int(mes),'seed':int(st.session_state.get('last_seed', 0))}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Remoção de subgrupo enviada pelo AX do Líder')
                                st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                                st.rerun()
                            delete_subgrupo(setor, del_sel)
                            _regenerar_mes_inteiro(setor, ano, mes, seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                            st.success("Subgrupo removido e escala readequada!")
                            st.rerun()
                    else:
                        st.caption("Nenhum subgrupo cadastrado.")

    # ------------------------------------------------------
    # ABA 4: Férias
    # ------------------------------------------------------
    elif sec_main == "🏖️ Férias":
        _status_comp_fer = get_status_competencia(setor, int(st.session_state['cfg_ano']), int(st.session_state['cfg_mes']))
        if _status_comp_fer == 'FECHADA':
            st.error('🔒 Competência fechada: lançamento normal de férias fica bloqueado nesta competência. Use retificação pontual se precisar corrigir histórico.')
        st.subheader("🏖️ Controle de Férias")

        st.markdown("---")
        st.markdown("---")
        colaboradores = load_colaboradores_setor(setor)
        if not colaboradores:
            st.warning("Sem colaboradores cadastrados.")
        else:
            sec_fer = st.radio("", ["🗺️ Mapa anual de férias", "➕ Lançar Férias", "📊 Controle (histórico)", "📋 Férias cadastradas", "❌ Remover férias"], horizontal=True, key="ferias_nav_fast", label_visibility="collapsed")

            # ---------------------------
            # TAB 1 — MAPA ANUAL
            # ---------------------------
            if sec_fer == "🗺️ Mapa anual de férias":
                st.markdown("## 🗺️ Mapa anual de férias (visual)")
                col_map1, col_map2 = st.columns([1, 3])
                ano_mapa = col_map1.number_input("Ano do mapa", value=int(st.session_state.get("cfg_ano", datetime.now().year)), step=1, key="fer_mapa_ano")
                col_map2.caption("Mostra em quais meses cada colaborador tem férias cadastradas (qualquer dia no mês marca o mês).")
                df_mapa = ferias_mapa_ano_df(setor, int(ano_mapa), colaboradores)
                show_chapa = st.checkbox("Mostrar coluna Chapa no mapa", value=False, key="fer_mapa_show_chapa")
                df_mapa_show = df_mapa if show_chapa else df_mapa.drop(columns=["Chapa"])
                st.dataframe(style_ferias_mapa(df_mapa_show), use_container_width=True, height=420)

            # ---------------------------
            # TAB 2 — LANÇAR
            # ---------------------------
            elif sec_fer == "➕ Lançar Férias":
                st.markdown("### ➕ Lançar Férias")
                opts = []
                for c in colaboradores:
                    chp = str(c.get("Chapa","")).strip()
                    nm = str(c.get("Nome","") or "").strip()
                    label = f"{chp} — {nm}" if nm else chp
                    opts.append((label, chp))
                pick = st.selectbox("Colaborador (chapa — nome):", [o[0] for o in opts], key="fer_pick")
                ch = next((o[1] for o in opts if o[0] == pick), pick.split("—")[0].strip())
                nome_sel = next((x.get("Nome","") for x in colaboradores if str(x.get("Chapa","")) == str(ch)), "")
                st.write(f"**Colaborador:** {nome_sel}  \n**Chapa:** {ch}")

                info_ult = get_ultima_ferias_info(setor, ch)
                ult_fim = info_ult.get("ultima_fim")
                meses_sem = info_ult.get("meses_desde_ultima_fim")
                if ult_fim:
                    st.write(
                        f"**Últimas férias:** {info_ult.get('ultima_inicio').strftime('%d/%m/%Y')} até {ult_fim.strftime('%d/%m/%Y')}  \n"
                        f"**Duração:** {_classificar_duracao_ferias(int(info_ult.get('dias_ultima') or 0))}  \n"
                        f"**Tempo desde o fim:** {int(meses_sem)} mês(es)"
                    )
                else:
                    st.warning("⚠️ Este colaborador ainda NÃO tem férias cadastradas.")

                c1, c2, c3 = st.columns(3)
                ini = c1.date_input("Início", value=datetime.now().date(), key="fer_ini")
                fim = c2.date_input("Fim", value=datetime.now().date(), key="fer_fim")
                if c3.button("Salvar férias (e readequar mês)", key="fer_add_btn"):
                    if fim < ini:
                        st.error("Data final não pode ser menor que a inicial.")
                    else:
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                            rid = registrar_pendencia_ax_generica(setor, 'ferias_add', 'salvar', {'_modulo':'ferias_add','_acao':'salvar','setor':setor,'ch':ch,'ini':ini.isoformat(),'fim':fim.isoformat(),'ano':int(st.session_state['cfg_ano']),'mes':int(st.session_state['cfg_mes']),'seed':int(st.session_state.get('last_seed', 0))}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Lançamento de férias enviado pelo AX do Líder')
                            st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                            st.rerun()
                        add_ferias(setor, ch, ini, fim)
                        _regenerar_mes_inteiro(setor, int(st.session_state["cfg_ano"]), int(st.session_state["cfg_mes"]), seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                        st.success("Férias adicionadas e escala readequada!")
                        st.rerun()

            # ---------------------------
            # TAB 3 — CONTROLE / HISTÓRICO
            # ---------------------------
            elif sec_fer == "📊 Controle (histórico)":
                st.markdown("### 📊 Controle de Férias (histórico por mês)")
                ano_ref = st.number_input(
                    "Ano para análise:",
                    min_value=2000, max_value=2100,
                    value=int(st.session_state.get("cfg_ano", datetime.now().year)),
                    step=1,
                    key="fer_hist_ano"
                )
                rows_all = list_ferias(setor)
                if not rows_all:
                    st.info("Nenhuma férias cadastrada para este setor.")
                else:
                    df_all = pd.DataFrame(rows_all, columns=["Chapa", "Início", "Fim"]).copy()
                    def _to_date(x):
                        try:
                            return pd.to_datetime(x).date()
                        except Exception:
                            return None
                    df_all["Início"] = df_all["Início"].apply(_to_date)
                    df_all["Fim"] = df_all["Fim"].apply(_to_date)
                    df_all = df_all.dropna(subset=["Início", "Fim"])
                    nome_by_hist = {str(c.get("Chapa","")): str(c.get("Nome","") or "") for c in (colaboradores or [])}
                    df_all["Nome"] = df_all["Chapa"].astype(str).map(nome_by_hist).fillna("")
                    resumo = []
                    for mes_i in range(1, 13):
                        ini_mes = pd.Timestamp(year=int(ano_ref), month=int(mes_i), day=1).date()
                        fim_mes = (pd.Timestamp(year=int(ano_ref), month=int(mes_i), day=1) + pd.offsets.MonthEnd(0)).date()
                        inter = df_all[(df_all["Fim"] >= ini_mes) & (df_all["Início"] <= fim_mes)].copy()
                        if inter.empty:
                            resumo.append({"Mês": mes_i, "Colaboradores em férias": 0, "Dias de férias (soma)": 0, "Períodos iniciados no mês": 0})
                            continue
                        dias_soma = 0
                        for _, r in inter.iterrows():
                            s = max(r["Início"], ini_mes)
                            e = min(r["Fim"], fim_mes)
                            dias_soma += max(0, int((e - s).days + 1))
                        iniciados = df_all[(df_all["Início"] >= ini_mes) & (df_all["Início"] <= fim_mes)]
                        resumo.append({
                            "Mês": mes_i,
                            "Colaboradores em férias": int(inter["Chapa"].nunique()),
                            "Dias de férias (soma)": int(dias_soma),
                            "Períodos iniciados no mês": int(iniciados.shape[0]),
                        })
                    df_res = pd.DataFrame(resumo)
                    try:
                        df_res["Mês (nome)"] = df_res["Mês"].apply(lambda m: pd.Timestamp(year=2000, month=int(m), day=1).strftime("%b").upper())
                        df_res = df_res[["Mês", "Mês (nome)", "Colaboradores em férias", "Dias de férias (soma)", "Períodos iniciados no mês"]]
                    except Exception:
                        pass
                    st.dataframe(df_res, use_container_width=True, height=360)
                    with st.expander("🔎 Ver detalhes de um mês"):
                        mes_det = st.selectbox("Mês:", list(range(1, 13)), index=0, key="fer_hist_mes_det")
                        ini_mes = pd.Timestamp(year=int(ano_ref), month=int(mes_det), day=1).date()
                        fim_mes = (pd.Timestamp(year=int(ano_ref), month=int(mes_det), day=1) + pd.offsets.MonthEnd(0)).date()
                        det = df_all[(df_all["Fim"] >= ini_mes) & (df_all["Início"] <= fim_mes)].copy()
                        if det.empty:
                            st.info("Nenhuma férias nesse mês.")
                        else:
                            det = det[["Chapa", "Nome", "Início", "Fim"]].sort_values(["Nome","Chapa"])
                            st.dataframe(det, use_container_width=True, height=360)

            # ---------------------------
            # TAB 4 — CADASTRADAS
            # ---------------------------
            elif sec_fer == "📋 Férias cadastradas":
                st.markdown("### 📋 Férias cadastradas")
                rows = list_ferias(setor)
                if rows:
                    df_f = pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"])
                    nome_by = {str(c.get("Chapa","")): str(c.get("Nome","") or "") for c in (colaboradores or [])}
                    df_f.insert(1, "Nome", df_f["Chapa"].astype(str).map(nome_by).fillna(""))
                    st.dataframe(df_f, use_container_width=True, height=420)
                else:
                    st.info("Nenhuma férias cadastrada.")

            # ---------------------------
            # TAB 5 — REMOVER
            # ---------------------------
            elif sec_fer == "❌ Remover férias":
                st.markdown("### ❌ Remover férias")
                rows = list_ferias(setor)
                if not rows:
                    st.info("Nenhuma férias cadastrada.")
                else:
                    df_f = pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"])
                    nome_by = {str(c.get("Chapa","")): str(c.get("Nome","") or "") for c in (colaboradores or [])}
                    df_f.insert(1, "Nome", df_f["Chapa"].astype(str).map(nome_by).fillna(""))
                    st.dataframe(df_f, use_container_width=True, height=260)
                    rem_idx = st.number_input("Linha para remover (1,2,3...)", min_value=1, max_value=len(df_f), value=1, key="fer_rem_idx")
                    if st.button("Remover linha (e readequar mês)", key="fer_rem_btn"):
                        r = df_f.iloc[int(rem_idx) - 1]
                        if bool(auth.get('is_ax_lider', False)) and not bool(auth.get('is_admin', False)):
                            rid = registrar_pendencia_ax_generica(setor, 'ferias_remove', 'remover', {'_modulo':'ferias_remove','_acao':'remover','setor':setor,'chapa':r['Chapa'],'inicio':r['Início'],'fim':r['Fim'],'ano':int(st.session_state['cfg_ano']),'mes':int(st.session_state['cfg_mes']),'seed':int(st.session_state.get('last_seed', 0))}, str(auth.get('nome') or '').strip(), str(auth.get('chapa') or '').strip(), 'Remoção de férias enviada pelo AX do Líder')
                            st.warning(f'Solicitação enviada para aprovação do líder. Protocolo #{rid}.')
                            st.rerun()
                        delete_ferias_row(setor, r["Chapa"], r["Início"], r["Fim"])
                        _regenerar_mes_inteiro(setor, int(st.session_state["cfg_ano"]), int(st.session_state["cfg_mes"]), seed=int(st.session_state.get("last_seed", 0)), respeitar_ajustes=True)
                        st.success("Férias removidas e escala readequada!")
                        st.rerun()

    elif sec_main == "🖨️ Impressão":
        sec_imp = st.radio("", ["📊 Excel modelo", "🗓️ Quem trabalha no dia", "📅 Escala", "🖨️ Imprimir escala parede"], horizontal=True, key="impressao_nav_fast", label_visibility="collapsed")

        # V94.2 — lazy load da impressão:
        # evita carregar escala + colaboradores + overrides logo ao abrir a aba.
        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hist_db = {}
        colaboradores = []

        # V94.3 — estado/cache leve para exportação/impressão
        imp_state = st.session_state.setdefault("imp_state", {})
        excel_cache = imp_state.setdefault("excel_cache", {})
        dia_cache = imp_state.setdefault("dia_cache", {})
        parede_cache = imp_state.setdefault("parede_cache", {})

        if sec_imp == "📊 Excel modelo":
            st.subheader("📊 Excel modelo RH (separado por subgrupo)")
            st.caption("Geração pesada ficou sob demanda para deixar a aba Impressão rápida.")
            excel_key = f"{setor}|{ano}|{mes}"
            if st.button("📊 Gerar Excel", key="xls_btn"):
                st.session_state.pop("xls_cached_bytes", None)
                colaboradores = load_colaboradores_setor(setor)
                hist_db = load_escala_mes_db(setor, ano, mes) or {}
                colab_by = {str(c.get("Chapa", "")).strip(): c for c in colaboradores}
                if not hist_db:
                    st.info("Gere a escala.")
                else:
                    hist_db = apply_overrides_to_hist(setor, ano, mes, hist_db)
                    hist_db = _apply_retificacoes_to_hist(setor, ano, mes, hist_db)
                    from openpyxl import Workbook
                    output = io.BytesIO()
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "Escala Mensal"

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
                    df_ref_xls = hist_db[ch0].copy().reset_index(drop=True)
                    total_dias = len(df_ref_xls)

                    c = ws.cell(1, 1, "COLABORADOR")
                    c.fill = fill_header
                    c.font = font_header
                    c.alignment = center
                    c.border = border
                    c = ws.cell(2, 1, "")
                    c.fill = fill_header
                    c.alignment = center
                    c.border = border

                    for i in range(total_dias):
                        data_i = pd.to_datetime(df_ref_xls.iloc[i].get("Data"), errors="coerce")
                        dia_num = int(data_i.day) if pd.notna(data_i) else (i + 1)
                        dia_sem = str(df_ref_xls.iloc[i].get("Dia", ""))
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
                        ch_str = str(chx).strip()
                        df_sg = hist_db.get(chx)
                        sg = ""
                        try:
                            if df_sg is not None and "Subgrupo" in df_sg.columns:
                                vals_sg = [str(v).strip() for v in df_sg["Subgrupo"].astype(str).tolist() if str(v).strip()]
                                if vals_sg:
                                    sg = vals_sg[-1]
                        except Exception:
                            sg = ""
                        sg = sg or get_subgrupo_competencia_ou_base(
                            setor, ch_str, int(ano), int(mes),
                            (colab_by.get(ch_str, {}).get("Subgrupo", "") or "").strip()
                        ) or "SEM SUBGRUPO"
                        subgrupo_map.setdefault(sg, []).append(chx)

                    row_idx = 3
                    total_linhas_gravadas = 0
                    resumo_cobertura = {
                        "abertura": [0] * total_dias,
                        "intermediario": [0] * total_dias,
                        "fechamento": [0] * total_dias,
                        "total_trabalhando": [0] * total_dias,
                    }

                    def _minutos_hora_excel(v):
                        s = str(v or "").strip()
                        if not s or ":" not in s:
                            return None
                        try:
                            hh, mm = s.split(":", 1)
                            return int(hh) * 60 + int(mm)
                        except Exception:
                            return None

                    for sg in sorted(subgrupo_map.keys()):
                        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=total_dias + 1)
                        t = ws.cell(row_idx, 1, f"SUBGRUPO: {sg}")
                        t.fill = fill_group
                        t.font = Font(bold=True)
                        t.alignment = Alignment(horizontal="left", vertical="center")
                        t.border = border
                        row_idx += 1

                        chapas_sg = sorted(subgrupo_map[sg], key=lambda chx: str(colab_by.get(str(chx), {}).get("Nome", chx)))
                        resumo_sg = {
                            "abertura": [0] * total_dias,
                            "intermediario": [0] * total_dias,
                            "fechamento": [0] * total_dias,
                            "total_trabalhando": [0] * total_dias,
                        }

                        for chx in chapas_sg:
                            df_f = hist_db[chx].copy().reset_index(drop=True)
                            nome = str(colab_by.get(str(chx), {}).get("Nome", chx))
                            c_nome = ws.cell(row=row_idx, column=1, value=f"{nome}\nCHAPA: {chx}")
                            c_nome.fill = fill_nome
                            c_nome.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                            c_nome.border = border
                            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx + 1, end_column=1)
                            for i, row in df_f.iterrows():
                                dia_sem = str(row.get("Dia", ""))
                                status = str(row.get("Status", ""))
                                if status == "Férias":
                                    v1, v2 = "FÉRIAS", ""
                                elif status == "Folga":
                                    v1, v2 = "F", ""
                                else:
                                    v1 = str(row.get("H_Entrada", "") or "")
                                    v2 = str(row.get("H_Saida", "") or "")
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
                                else:
                                    ent_min = _minutos_hora_excel(v1)
                                    if ent_min is not None:
                                        resumo_cobertura["total_trabalhando"][i] += 1
                                        resumo_sg["total_trabalhando"][i] += 1
                                        if 360 <= ent_min <= 600:
                                            resumo_cobertura["abertura"][i] += 1
                                            resumo_sg["abertura"][i] += 1
                                        elif 601 <= ent_min <= 739:
                                            resumo_cobertura["intermediario"][i] += 1
                                            resumo_sg["intermediario"][i] += 1
                                        elif ent_min >= 740:
                                            resumo_cobertura["fechamento"][i] += 1
                                            resumo_sg["fechamento"][i] += 1
                            total_linhas_gravadas += 1
                            row_idx += 2

                        resumo_rows_sg = [
                            (f"ABERTURA — {sg}", resumo_sg["abertura"]),
                            (f"INTERMEDIÁRIO — {sg}", resumo_sg["intermediario"]),
                            (f"FECHAMENTO — {sg}", resumo_sg["fechamento"]),
                            (f"TOTAL TRABALHANDO — {sg}", resumo_sg["total_trabalhando"]),
                        ]
                        for titulo_resumo, valores_resumo in resumo_rows_sg:
                            c0 = ws.cell(row_idx, 1, titulo_resumo)
                            c0.fill = fill_group
                            c0.font = Font(bold=True)
                            c0.alignment = Alignment(horizontal="left", vertical="center")
                            c0.border = border
                            for i, valor_resumo in enumerate(valores_resumo):
                                c1 = ws.cell(row_idx, i + 2, int(valor_resumo))
                                c1.alignment = center
                                c1.border = border
                                if str(df_ref_xls.iloc[i].get("Dia", "")) == "dom":
                                    c1.fill = fill_folga
                            row_idx += 1
                        row_idx += 1

                    row_idx += 1
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=total_dias + 1)
                    t_res = ws.cell(row_idx, 1, "RESUMO DE COBERTURA — TODOS OS SUBGRUPOS")
                    t_res.fill = fill_header
                    t_res.font = font_header
                    t_res.alignment = Alignment(horizontal="left", vertical="center")
                    t_res.border = border
                    row_idx += 1

                    resumo_rows = [
                        ("ABERTURA (06:00 até 10:00)", resumo_cobertura["abertura"]),
                        ("INTERMEDIÁRIO (10:01 até 12:19)", resumo_cobertura["intermediario"]),
                        ("FECHAMENTO (a partir de 12:20)", resumo_cobertura["fechamento"]),
                        ("TOTAL TRABALHANDO", resumo_cobertura["total_trabalhando"]),
                    ]
                    for titulo_resumo, valores_resumo in resumo_rows:
                        c0 = ws.cell(row_idx, 1, titulo_resumo)
                        c0.fill = fill_group
                        c0.font = Font(bold=True)
                        c0.alignment = Alignment(horizontal="left", vertical="center")
                        c0.border = border
                        for i, valor_resumo in enumerate(valores_resumo):
                            c1 = ws.cell(row_idx, i + 2, int(valor_resumo))
                            c1.alignment = center
                            c1.border = border
                            if str(df_ref_xls.iloc[i].get("Dia", "")) == "dom":
                                c1.fill = fill_folga
                        row_idx += 1

                    try:
                        rows_f = list_ferias(setor) or []
                        if rows_f:
                            ws_f = wb.create_sheet("Férias do mês")
                            headers_f = ["Chapa", "Nome", "Sai de férias", "Volta ao trabalho", "Início", "Fim", "Dias de férias no mês"]
                            for col_idx, head in enumerate(headers_f, start=1):
                                c = ws_f.cell(1, col_idx, head)
                                c.fill = fill_header
                                c.font = font_header
                                c.border = border
                                c.alignment = center
                            df_fer = pd.DataFrame(rows_f, columns=["Chapa", "Início", "Fim"]).copy()
                            df_fer["Início"] = pd.to_datetime(df_fer["Início"], errors="coerce").dt.date
                            df_fer["Fim"] = pd.to_datetime(df_fer["Fim"], errors="coerce").dt.date
                            df_fer = df_fer.dropna(subset=["Início", "Fim"])
                            ini_mes = pd.Timestamp(year=int(ano), month=int(mes), day=1).date()
                            fim_mes = (pd.Timestamp(year=int(ano), month=int(mes), day=1) + pd.offsets.MonthEnd(0)).date()
                            df_fer = df_fer[(df_fer["Fim"] >= ini_mes) & (df_fer["Início"] <= fim_mes)].copy()
                            if not df_fer.empty:
                                nome_by = {str(c.get("Chapa", "")): str(c.get("Nome", "") or "") for c in (colaboradores or [])}
                                df_fer["Nome"] = df_fer["Chapa"].astype(str).map(nome_by).fillna("")
                                df_fer["Sai de férias"] = df_fer["Início"]
                                df_fer["Volta ao trabalho"] = df_fer["Fim"].apply(lambda d: (pd.Timestamp(d) + pd.Timedelta(days=1)).date())
                                def _dias_no_mes(r):
                                    s = max(r["Início"], ini_mes)
                                    e = min(r["Fim"], fim_mes)
                                    return max(0, int((e - s).days + 1))
                                df_fer["Dias de férias no mês"] = df_fer.apply(_dias_no_mes, axis=1)
                                df_fer = df_fer[["Chapa", "Nome", "Sai de férias", "Volta ao trabalho", "Início", "Fim", "Dias de férias no mês"]].sort_values(["Nome", "Chapa"])
                                for row_excel, vals in enumerate(df_fer.itertuples(index=False, name=None), start=2):
                                    for col_excel, val in enumerate(vals, start=1):
                                        c = ws_f.cell(row_excel, col_excel, val)
                                        c.border = border
                    except Exception:
                        pass

                    ws.freeze_panes = "B3"
                    wb.active = wb.sheetnames.index("Escala Mensal")
                    wb.save(output)
                    output.seek(0)
                    excel_bytes = output.getvalue()
                    if total_linhas_gravadas > 0 and excel_bytes and len(excel_bytes) > 2000:
                        excel_cache[excel_key] = excel_bytes
                        st.session_state["xls_cached_bytes"] = excel_bytes
                        st.success(f"Excel gerado com {total_linhas_gravadas} colaborador(es).")
                    else:
                        st.error("Excel gerado vazio. A escala do mês não trouxe linhas para exportação.")
            if st.session_state.get("xls_cached_bytes"):
                st.download_button(
                    "📥 Baixar Excel",
                    data=st.session_state["xls_cached_bytes"],
                    file_name=f"escala_{setor}_{mes:02d}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="xls_down"
                )
        elif sec_imp == "🗓️ Quem trabalha no dia":
            # --- Lista (e PDF) de quem TRABALHA no dia escolhido ---
            st.markdown("### 🗓️ Quem trabalha no dia (para impressão)")
            st.caption("Carregamento sob demanda para deixar a aba Impressão rápida.")
            try:
                dias_mes = calendar.monthrange(int(ano), int(mes))[1]
            except Exception:
                dias_mes = 31
            dia_sel = st.number_input("Dia do mês", min_value=1, max_value=int(dias_mes), value=1, step=1)
            dia_key = f"{setor}|{ano}|{mes}|{int(dia_sel)}"
            carregar_dia = st.button("🔎 Carregar lista do dia", key="dia_trabalho_load_btn")

            if carregar_dia and dia_key not in dia_cache:
                colaboradores = load_colaboradores_setor(setor)
                hist_db = load_escala_mes_db(setor, ano, mes) or {}
                if hist_db:
                    hist_db = apply_overrides_to_hist(setor, ano, mes, hist_db)
                    hist_db = _apply_retificacoes_to_hist(setor, ano, mes, hist_db)
                linhas = []
                for _chapa, _df in (hist_db or {}).items():
                    if _df is None or _df.empty:
                        continue
                    try:
                        _linha = _df.loc[_df["Data"].dt.day == int(dia_sel)].head(1)
                    except Exception:
                        _linha = _df.loc[pd.to_datetime(_df["Data"], errors="coerce").dt.day == int(dia_sel)].head(1)
                    if _linha.empty:
                        continue
                    _r = _linha.iloc[0].to_dict()
                    _stt = str(_r.get("Status", "")).strip()
                    if _stt not in WORK_STATUSES:
                        continue
                    _ent = str(_r.get("H_Entrada", "") or "").strip()
                    _sai = str(_r.get("H_Saida", "") or "").strip()
                    _nome = ""
                    _subg_base = ""
                    for c in colaboradores:
                        if str(c.get("Chapa", "")).strip() == str(_chapa).strip():
                            _nome = str(c.get("Nome", "")).strip()
                            _subg_base = str(c.get("Subgrupo", "")).strip()
                            break
                    _subg = get_subgrupo_competencia_ou_base(setor, str(_chapa).strip(), int(ano), int(mes), _subg_base)
                    linhas.append({"Chapa": str(_chapa).strip(), "Nome": _nome, "Subgrupo": _subg, "Entrada": _ent, "Saída": _sai})
                df_dia = pd.DataFrame(linhas).sort_values(["Subgrupo", "Nome"]) if linhas else pd.DataFrame(columns=["Chapa","Nome","Subgrupo","Entrada","Saída"])
                dia_cache[dia_key] = {"df": df_dia, "hist": hist_db, "colaboradores": colaboradores}

            payload_dia = dia_cache.get(dia_key, {"df": pd.DataFrame(columns=["Chapa","Nome","Subgrupo","Entrada","Saída"]), "hist": {}, "colaboradores": []})
            df_dia = payload_dia.get("df") if isinstance(payload_dia.get("df"), pd.DataFrame) else pd.DataFrame(columns=["Chapa","Nome","Subgrupo","Entrada","Saída"])
            st.dataframe(df_dia, use_container_width=True, hide_index=True)

            colp1, colp2 = st.columns([1, 2])
            pdf_day_key = f"pdf::{dia_key}"
            with colp1:
                if st.button("📄 Gerar PDF (quem trabalha no dia)"):
                    if df_dia.empty:
                        st.warning("Não há colaboradores trabalhando nesse dia (ou ainda não foi gerado para este mês).")
                    else:
                        pdf_bytes_dia = gerar_pdf_trabalhando_no_dia(setor, int(ano), int(mes), int(dia_sel), payload_dia.get("hist", {}), payload_dia.get("colaboradores", []))
                        st.session_state[pdf_day_key] = pdf_bytes_dia
                        st.success("PDF pronto.")
            with colp2:
                if st.session_state.get(pdf_day_key):
                    st.download_button(
                        "⬇️ Baixar PDF (quem trabalha no dia)",
                        data=st.session_state[pdf_day_key],
                        file_name=f"escala_trabalhando_dia_{int(dia_sel):02d}_{int(mes):02d}_{int(ano)}.pdf",
                        mime="application/pdf",
                    )

        elif sec_imp == "📅 Escala":
            st.subheader("📅 Escala")
            st.markdown("---")
            st.markdown("### 🏖️ Férias do mês (PDF)")
            cfx1, cfx2 = st.columns([1, 2])
            pdf_fer_busca = cfx2.text_input("Filtro (nome ou chapa) — opcional:", value="", key="pdf_fer_busca")
            btn_fer_pdf = cfx1.button("📄 Gerar PDF — Férias do mês", use_container_width=True, key="pdf_fer_btn")
            cfx2.caption("Gera um relatório A4 com Nome, Chapa, Início, Fim e Dias. Considera quem tem férias que encostam no mês selecionado.")
            if btn_fer_pdf:
                colabs_all = load_colaboradores_setor(setor) or []
                # aplica filtro simples
                if pdf_fer_busca.strip():
                    kw = pdf_fer_busca.strip().lower()
                    colabs_all = [c for c in colabs_all if kw in str(c.get("Nome","")).lower() or kw in str(c.get("Chapa","")).lower()]
                pdf_bytes = gerar_pdf_ferias_mes(setor, int(ano), int(mes), load_colaboradores_setor(setor) or [], keyword=pdf_fer_busca)
                st.download_button(
                    "⬇️ Baixar PDF (Férias do mês)",
                    data=pdf_bytes,
                    file_name=f"ferias_{setor}_{int(mes):02d}_{int(ano)}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_fer_dl"
                )
        elif sec_imp == "🖨️ Imprimir escala parede":
            st.subheader("🖨️ Imprimir escala parede")

            colaboradores = load_colaboradores_setor(setor)
            all_subgrupos = sorted({((c.get("Subgrupo") or "").strip() or "SEM SUBGRUPO") for c in colaboradores})
            cfx1, cfx2, cfx3 = st.columns([1.2, 1.2, 1.6])
            loja_txt = cfx1.text_input("Loja:", value=str(setor), key="pdf_loja_txt")
            secoes_sel = cfx2.multiselect("Seções (Subgrupo):", options=all_subgrupos, default=[], key="pdf_secoes_sel")
            busca_txt = cfx3.text_input("Filtro (nome/chapa/subgrupo):", value="", key="pdf_busca")

            modo_pdf = st.radio(
                "Formato de impressão:",
                options=["Modelo oficial do mês", "Panorâmico por período"],
                horizontal=True,
                key="pdf_modo_impressao"
            )

            cols_dates = st.columns([1, 1, 2])
            data_ini = cols_dates[0].date_input("Dia inicial:", value=date(int(ano), int(mes), 1), key="pdf_dt_ini")
            data_fim = cols_dates[1].date_input("Dia final:", value=date(int(ano), int(mes), calendar.monthrange(int(ano), int(mes))[1]), key="pdf_dt_fim")
            if modo_pdf == "Panorâmico por período":
                cols_dates[2].caption("Use qualquer período contínuo, inclusive dois meses juntos (ex.: 01/03/2026 até 30/04/2026).")
            else:
                cols_dates[2].caption("Obs.: o PDF segue o modelo oficial do mês. Aqui o filtro é para escolher colaboradores/Seções como no sistema.")

            colabs_filtrados = _filtrar_colaboradores(colaboradores, secoes_sel, busca_txt)

            opcoes = [
                f"{(c.get('Nome') or '').strip()} — Chapa: {str(c.get('Chapa') or '').strip()} — {((c.get('Subgrupo') or '').strip() or 'SEM SUBGRUPO')}"
                for c in colabs_filtrados
            ]
            mapa_idx = {opcoes[i]: colabs_filtrados[i] for i in range(len(opcoes))}

            st.markdown("### 👥 Colaboradores")
            sel = st.multiselect(
                "Selecione (se vazio, imprime TODOS do filtro):",
                options=opcoes,
                default=[],
                key="pdf_colabs_sel"
            )

            cbtn1, cbtn2 = st.columns([1, 3])
            gerar = cbtn1.button("🖨️ Imprimir (gerar PDF)", key="pdf_print_btn", use_container_width=True)
            cbtn2.caption("Dica: selecione uma seção, depois marque os colaboradores. Se não marcar nenhum, imprime todos os filtrados.")

            pdf_parede_key = f"{setor}|{ano}|{mes}|{loja_txt.strip()}|{modo_pdf}|{data_ini}|{data_fim}|{','.join(sorted(chapas_sel)) if 'chapas_sel' in locals() else ''}|{','.join(sorted(secoes_sel))}|{busca_txt.strip()}"
            if gerar:
                if data_fim < data_ini:
                    st.warning("O dia final precisa ser maior ou igual ao dia inicial.")
                else:
                    if sel:
                        chapas_sel = [str(mapa_idx[x].get("Chapa")) for x in sel if x in mapa_idx]
                    else:
                        chapas_sel = [str(c.get("Chapa")) for c in colabs_filtrados]
                    pdf_parede_key = f"{setor}|{ano}|{mes}|{loja_txt.strip()}|{modo_pdf}|{data_ini}|{data_fim}|{','.join(sorted(chapas_sel))}|{','.join(sorted(secoes_sel))}|{busca_txt.strip()}"
                    if pdf_parede_key in parede_cache:
                        st.session_state["pdf_parede_bytes"] = parede_cache[pdf_parede_key]
                    elif modo_pdf == "Panorâmico por período":
                        hist_db_pdf = _load_hist_periodo(setor, data_ini, data_fim)
                        hist_db_pdf = {ch: df for ch, df in hist_db_pdf.items() if ch in set(chapas_sel)}
                        if not hist_db_pdf:
                            st.warning("Nenhum colaborador com escala salva no período informado.")
                        else:
                            pdf_bytes = gerar_pdf_periodo_panoramico(loja_txt.strip() or str(setor), data_ini, data_fim, hist_db_pdf, colaboradores)
                            parede_cache[pdf_parede_key] = pdf_bytes
                            st.session_state["pdf_parede_bytes"] = pdf_bytes
                            st.download_button(
                                "⬇️ Baixar PDF panorâmico",
                                data=st.session_state["pdf_parede_bytes"],
                                file_name=f"escala_panoramica_{(loja_txt.strip() or str(setor))}_{data_ini.strftime('%Y%m%d')}_{data_fim.strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="pdf_down_pan"
                            )
                    else:
                        hist_db_pdf = load_escala_mes_db(setor, ano, mes)
                        if not hist_db_pdf:
                            st.warning("Gere a escala antes na aba 🚀 Gerar Escala.")
                        else:
                            hist_db_pdf = apply_overrides_to_hist(setor, ano, mes, hist_db_pdf)
                            hist_db_pdf = _apply_retificacoes_to_hist(setor, ano, mes, hist_db_pdf)
                            hist_db_pdf = {ch: df for ch, df in hist_db_pdf.items() if ch in set(chapas_sel)}
                            if not hist_db_pdf:
                                st.warning("Nenhum colaborador para imprimir com os filtros atuais.")
                            else:
                                pdf_bytes = gerar_pdf_modelo_oficial(loja_txt.strip() or str(setor), ano, mes, hist_db_pdf, colaboradores)
                                st.download_button(
                                    "⬇️ Baixar PDF",
                                    data=pdf_bytes,
                                    file_name=f"escala_{(loja_txt.strip() or str(setor))}_{mes:02d}_{ano}.pdf",
                                    mime="application/pdf",
                                    key="pdf_down"
                                )


    # ------------------------------------------------------
    # ABA 6: Assinaturas (líder/admin)
    # ------------------------------------------------------
    elif sec_main == "✍️ Assinaturas":
        ano = int(st.session_state["cfg_ano"])
        mes = int(st.session_state["cfg_mes"])
        hoje_ass = datetime.now()
        ano_vig_ass = int(hoje_ass.year)
        mes_vig_ass = int(hoje_ass.month)

        st.subheader(f"✍️ Assinaturas do setor — {setor}")

        df_ass_sel = list_assinaturas_setor(setor, ano, mes)
        df_ass_vig = list_assinaturas_setor(setor, ano_vig_ass, mes_vig_ass)
        df_ass_all = list_assinaturas_setor_todas(setor)
        colaboradores_setor = load_colaboradores_setor(setor) or []
        total_colabs_setor = len({str((c or {}).get("Chapa", "")).strip() for c in colaboradores_setor if str((c or {}).get("Chapa", "")).strip()})

        def _filtrar_assinatura_escala_mes(df_src: pd.DataFrame) -> pd.DataFrame:
            if df_src is None or df_src.empty:
                return pd.DataFrame(columns=getattr(df_src, 'columns', []))
            if 'Tipo' not in df_src.columns:
                return df_src.copy()
            tipo_norm = df_src['Tipo'].astype(str).str.strip().str.lower()
            df_oficial = df_src[tipo_norm.isin(['oficial', 'assinatura da escala do mês'])].copy()
            return df_oficial if not df_oficial.empty else df_src.copy()

        df_ass_sel_escala = _filtrar_assinatura_escala_mes(df_ass_sel)
        df_ass_vig_escala = _filtrar_assinatura_escala_mes(df_ass_vig)
        chapas_ass_sel = {str(x).strip() for x in df_ass_sel_escala.get('Chapa', pd.Series(dtype=str)).astype(str).tolist() if str(x).strip()}
        chapas_ass_vig = {str(x).strip() for x in df_ass_vig_escala.get('Chapa', pd.Series(dtype=str)).astype(str).tolist() if str(x).strip()}
        faltam_sel = max(0, total_colabs_setor - len(chapas_ass_sel))
        faltam_vig = max(0, total_colabs_setor - len(chapas_ass_vig))

        c_ass1, c_ass2, c_ass3 = st.columns(3)
        c_ass1.metric("Competência selecionada", f"{mes:02d}/{ano}", delta=f"{len(df_ass_sel)} assinatura(s)")
        c_ass2.metric("Mês vigente", f"{mes_vig_ass:02d}/{ano_vig_ass}", delta=f"{len(df_ass_vig)} assinatura(s)")
        c_ass3.metric("Total do setor", len(df_ass_all))

        c_ass4, c_ass5, c_ass6 = st.columns(3)
        c_ass4.metric("Colaboradores do setor", total_colabs_setor)
        c_ass5.metric("Assinaram escala do mês vigente", len(chapas_ass_vig))
        c_ass6.metric("Faltam assinar mês vigente", faltam_vig)

        escopo_opts = [
            f"Competência selecionada ({mes:02d}/{ano})",
            f"Mês vigente ({mes_vig_ass:02d}/{ano_vig_ass})",
            "Todas do setor",
        ]
        if not df_ass_sel.empty:
            escopo_default = 0
        elif not df_ass_vig.empty:
            escopo_default = 1
        else:
            escopo_default = 2

        escopo_ass = st.radio(
            "Visualizar",
            escopo_opts,
            index=escopo_default,
            horizontal=True,
            key="ass_setor_escopo",
        )

        if escopo_ass == escopo_opts[0]:
            df_ass = df_ass_sel.copy()
            st.caption(f"Mostrando a competência selecionada na lateral: {mes:02d}/{ano}.")
            if df_ass.empty and not df_ass_vig.empty and (ano != ano_vig_ass or mes != mes_vig_ass):
                st.warning(
                    f"Não há assinaturas em {mes:02d}/{ano}. Existem assinatura(s) no mês vigente {mes_vig_ass:02d}/{ano_vig_ass}."
                )
        elif escopo_ass == escopo_opts[1]:
            df_ass = df_ass_vig.copy()
            st.caption(f"Mostrando o mês vigente do portal do colaborador: {mes_vig_ass:02d}/{ano_vig_ass}.")
        else:
            df_ass = df_ass_all.copy()
            st.caption("Mostrando todas as assinaturas do setor, sem apagar nem alterar a lógica existente.")

        if df_ass.empty:
            st.info("Nenhuma assinatura encontrada para o filtro selecionado.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Assinaturas", len(df_ass))
            m2.metric("Colaboradores com assinatura", int(df_ass['Chapa'].astype(str).nunique()))
            m3.metric("Tipos assinados", int(df_ass['Tipo'].astype(str).nunique()))

            tipo_opts = ["Todos"] + sorted(df_ass['Tipo'].astype(str).dropna().unique().tolist())
            tipo_sel = st.selectbox("Filtrar tipo", tipo_opts, key="ass_setor_tipo")
            df_view = df_ass.copy()
            if tipo_sel != "Todos":
                df_view = df_view[df_view['Tipo'].astype(str) == str(tipo_sel)].copy()

            comp_opts = ["Todas"] + sorted(
                {f"{int(a):04d}-{int(m):02d}" for a, m in zip(df_view['Ano'].fillna(0), df_view['Mes'].fillna(0))}
            ) if {'Ano', 'Mes'}.issubset(df_view.columns) else ["Todas"]
            comp_sel = st.selectbox("Filtrar competência", comp_opts, key="ass_setor_competencia")
            if comp_sel != "Todas" and {'Ano', 'Mes'}.issubset(df_view.columns):
                ano_sel, mes_sel = comp_sel.split('-')
                df_view = df_view[
                    (df_view['Ano'].astype(int) == int(ano_sel)) &
                    (df_view['Mes'].astype(int) == int(mes_sel))
                ].copy()

            if 'Tipo' in df_view.columns:
                tipo_map = {
                    'oficial': 'Assinatura da Escala do Mês',
                    'historico': 'Assinatura de Mudanças',
                }
                df_view['Tipo'] = df_view['Tipo'].astype(str).map(lambda x: tipo_map.get(str(x).strip().lower(), x))

            if 'Assinado_em' in df_view.columns:
                try:
                    df_view['Assinado_em'] = pd.to_datetime(df_view['Assinado_em'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
                except Exception:
                    pass
            st.dataframe(df_view, use_container_width=True, hide_index=True)

            faltantes_vig = [
                c for c in colaboradores_setor
                if str((c or {}).get('Chapa', '')).strip() and str((c or {}).get('Chapa', '')).strip() not in chapas_ass_vig
            ]
            faltantes_sel = [
                c for c in colaboradores_setor
                if str((c or {}).get('Chapa', '')).strip() and str((c or {}).get('Chapa', '')).strip() not in chapas_ass_sel
            ]

            with st.expander('📋 Conferência de quem ainda falta assinar', expanded=False):
                st.caption('Sem apagar nada da lógica existente: aqui o sistema compara os colaboradores cadastrados no setor com as assinaturas já registradas.')
                t1, t2 = st.columns(2)
                with t1:
                    st.markdown(f"**Competência selecionada ({mes:02d}/{ano})**")
                    st.write(f"Faltam assinar: **{faltam_sel}**")
                    if faltantes_sel:
                        st.dataframe(
                            pd.DataFrame([
                                {
                                    'Chapa': str((c or {}).get('Chapa', '')).strip(),
                                    'Nome': str((c or {}).get('Nome', '')).strip(),
                                    'Subgrupo': str((c or {}).get('Subgrupo', '')).strip(),
                                }
                                for c in faltantes_sel
                            ]),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.success('Todos os colaboradores do setor já assinaram a escala desta competência.')
                with t2:
                    st.markdown(f"**Mês vigente ({mes_vig_ass:02d}/{ano_vig_ass})**")
                    st.write(f"Faltam assinar: **{faltam_vig}**")
                    if faltantes_vig:
                        st.dataframe(
                            pd.DataFrame([
                                {
                                    'Chapa': str((c or {}).get('Chapa', '')).strip(),
                                    'Nome': str((c or {}).get('Nome', '')).strip(),
                                    'Subgrupo': str((c or {}).get('Subgrupo', '')).strip(),
                                }
                                for c in faltantes_vig
                            ]),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.success('Todos os colaboradores do setor já assinaram a escala do mês vigente.')

    # ------------------------------------------------------
    # ABA 7: Minhas solicitações (líder/admin)
    # ------------------------------------------------------
    elif sec_main == "📨 Minhas solicitações":
        st.subheader(f"📨 Solicitações recebidas do setor — {setor}")
        df_sol_setor = list_solicitacoes_setor(setor)
        if df_sol_setor.empty:
            st.info("Nenhuma solicitação enviada para este setor até agora.")
        else:
            pend = int((df_sol_setor['Status'].astype(str) == 'Em análise').sum()) if 'Status' in df_sol_setor.columns else 0
            aprov = int((df_sol_setor['Status'].astype(str) == 'Aprovado').sum()) if 'Status' in df_sol_setor.columns else 0
            rec = int((df_sol_setor['Status'].astype(str) == 'Recusado').sum()) if 'Status' in df_sol_setor.columns else 0
            s1, s2, s3 = st.columns(3)
            s1.metric('Em análise', pend)
            s2.metric('Aprovadas', aprov)
            s3.metric('Recusadas', rec)

            status_opts = ['Todos'] + sorted(df_sol_setor['Status'].astype(str).dropna().unique().tolist())
            filtro_status = st.selectbox('Filtrar status', status_opts, key='sol_setor_status')
            df_view = df_sol_setor.copy()
            if filtro_status != 'Todos':
                df_view = df_view[df_view['Status'].astype(str) == str(filtro_status)].copy()

            for c in ['Criado_em', 'Atualizado_em']:
                if c in df_view.columns:
                    try:
                        df_view[c] = pd.to_datetime(df_view[c], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        pass

            st.dataframe(df_view, use_container_width=True, hide_index=True)

            pendentes = df_sol_setor[df_sol_setor['Status'].astype(str) == 'Em análise'].copy() if 'Status' in df_sol_setor.columns else pd.DataFrame()
            if pendentes.empty:
                st.success('Não há solicitações pendentes no momento.')
            else:
                ids_pend = [int(x) for x in pendentes['ID'].tolist()]
                sol_id = st.selectbox('Selecionar solicitação pendente', ids_pend, key='sol_pendente_id')
                sol_row = pendentes[pendentes['ID'].astype(int) == int(sol_id)].head(1)
                if not sol_row.empty:
                    r = sol_row.iloc[0]
                    st.caption(f"{r.get('Nome','-')} • Chapa {r.get('Chapa','-')} • Data {r.get('Data','-')} • Tipo {r.get('Tipo','-')}")
                    mot = str(r.get('Motivo', '') or '').strip()
                    obs = str(r.get('Observação', '') or '').strip()
                    if mot:
                        st.write(f"**Motivo:** {mot}")
                    if obs:
                        st.write(f"**Observação:** {obs}")
                a1, a2 = st.columns(2)
                if a1.button('✅ Aprovar solicitação', key='aprovar_solicitacao_btn'):
                    atualizar_status_solicitacao(int(sol_id), 'Aprovado')
                    st.success('Solicitação aprovada com sucesso.')
                    st.rerun()
                if a2.button('❌ Recusar solicitação', key='recusar_solicitacao_btn'):
                    atualizar_status_solicitacao(int(sol_id), 'Recusado')
                    st.success('Solicitação recusada com sucesso.')
                    st.rerun()


    # ------------------------------------------------------
    # ABA 6: Admin (somente ADMIN)
    # ------------------------------------------------------
    elif is_admin_area and sec_main == "🔒 Admin":
            st.subheader("🔒 Admin do Sistema (somente ADMIN)")

            st.markdown("## 🛠️ ATUALIZAR FUNCIONÁRIO DE QUALQUER SETOR")
            st.warning("NOVO BLOCO ADMIN ATIVO: aqui você altera subgrupo e perfil do sistema do funcionário.")
            st.caption("Aqui o ADMIN pode alterar nome, subgrupo e perfil do colaborador em qualquer setor. O perfil sincroniza o login do sistema.")
            try:
                df_func_adm = admin_get_funcionarios_leve_all()
                df_login_adm = admin_get_logins_leve_all()
            except Exception:
                df_func_adm = pd.DataFrame(columns=['nome','setor','chapa','subgrupo','entrada','folga_sab'])
                df_login_adm = pd.DataFrame(columns=['setor','chapa','is_admin','is_lider','is_ax_lider'])

            if df_func_adm.empty:
                st.info("Nenhum colaborador cadastrado para atualizar.")
            else:
                setores_func = sorted({_norm_setor(x) for x in df_func_adm['setor'].dropna().tolist() if str(x).strip()})
                admf1, admf2 = st.columns([1, 1.7])
                with admf1:
                    setor_func = st.selectbox("Setor do funcionário", setores_func, key="adm_func_setor")
                df_func_setor = df_func_adm[df_func_adm['setor'].astype(str).str.strip().str.upper() == _norm_setor(setor_func)].copy()
                opts_func = [f"{str(r['nome']).strip()} ({str(r['chapa']).strip()})" for _, r in df_func_setor.iterrows()]
                with admf2:
                    pick_func = st.selectbox("Funcionário", opts_func, key="adm_func_pick") if opts_func else None

                rec_func = None
                chapa_func = ""
                if pick_func:
                    chapa_func = pick_func.rsplit("(", 1)[-1].replace(")", "").strip()
                    df_hit = df_func_setor[df_func_setor['chapa'].astype(str).str.strip() == chapa_func]
                    if not df_hit.empty:
                        rec_func = df_hit.iloc[0].to_dict()

                if rec_func:
                    login_hit = df_login_adm[(df_login_adm['setor'].astype(str).str.strip().str.upper() == _norm_setor(setor_func)) & (df_login_adm['chapa'].astype(str).str.strip() == chapa_func)]
                    login_row = login_hit.iloc[0] if not login_hit.empty else {}
                    is_admin_cur = bool(int(login_row.get('is_admin', 0) or 0)) if hasattr(login_row, 'get') else False
                    is_lider_cur = bool(int(login_row.get('is_lider', 0) or 0)) if hasattr(login_row, 'get') else False
                    is_ax_cur = bool(int(login_row.get('is_ax_lider', 0) or 0)) if hasattr(login_row, 'get') else False
                    perfil_cur = 'ADMIN' if is_admin_cur else ('LIDER' if is_lider_cur else ('AX_LIDER' if is_ax_cur else ('LIDER' if _norm_subgrupo_label(rec_func.get('subgrupo','')) == 'LIDERANCA' else 'COLABORADOR')))

                    func_token = f"{_norm_setor(setor_func)}::{str(chapa_func).strip()}"
                    if st.session_state.get('adm_func_last_token', '') != func_token:
                        st.session_state['adm_func_last_token'] = func_token
                        st.session_state['adm_func_nome'] = str(rec_func.get('nome') or '').strip()
                        st.session_state['adm_func_subgrupo'] = str(rec_func.get('subgrupo') or '').strip()
                        st.session_state['adm_func_entrada'] = str(rec_func.get('entrada') or '06:00').strip() or '06:00'
                        st.session_state['adm_func_folga_sab'] = bool(int(rec_func.get('folga_sab', 0) or 0))
                        st.session_state['adm_func_perfil'] = perfil_cur

                    st.write(f"Atualizando: **{str(rec_func.get('nome') or '').strip()}** — chapa **{chapa_func}**")
                    af1, af2, af3, af4 = st.columns([1.4, 1.2, 1.2, 1])
                    with af1:
                        nome_func_novo = st.text_input("Nome", key='adm_func_nome')
                    with af2:
                        subgrupo_func_novo = st.text_input("Subgrupo", key='adm_func_subgrupo')
                    with af3:
                        entrada_func_nova = st.text_input("Entrada padrão", key='adm_func_entrada')
                    with af4:
                        folga_sab_func = st.checkbox("Folga sábado", key='adm_func_folga_sab')

                    perfil_func_novo = st.selectbox("Perfil do sistema", ['COLABORADOR', 'AX_LIDER', 'LIDER', 'ADMIN'], key='adm_func_perfil')
                    criar_login_func = st.checkbox("Criar login do sistema se não existir", value=True, key='adm_func_criar_login')

                    if st.button("Salvar atualização do funcionário", key='adm_func_salvar'):
                        try:
                            res = admin_update_funcionario(
                                setor=setor_func,
                                chapa_atual=chapa_func,
                                nome_novo=nome_func_novo,
                                subgrupo_novo=subgrupo_func_novo,
                                perfil_novo=perfil_func_novo,
                                entrada_nova=entrada_func_nova,
                                folga_sab=bool(folga_sab_func),
                                criar_usuario_se_nao_existir=bool(criar_login_func),
                            )
                            st.success(f"Funcionário atualizado com sucesso. Perfil final: {res['perfil']} | Subgrupo: {res['subgrupo'] or 'SEM SUBGRUPO'}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Falha ao atualizar funcionário: {e}")

            st.markdown("---")
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
            st.subheader("♻️ Recuperar usuário do sistema")
            st.caption("Use esta área quando o colaborador existe, mas sumiu do login. Se não existir colaborador, use o cadastro manual logo abaixo.")
            con = db_conn()
            df_colabs_adm = pd.read_sql_query("SELECT nome, setor, chapa FROM colaboradores ORDER BY setor, nome", con)
            con.close()
            if df_colabs_adm.empty:
                st.info("Nenhum colaborador cadastrado para recuperar. Use o cadastro manual de usuário abaixo.")
            else:
                colr1, colr2, colr3 = st.columns([1.1, 1.2, 1.0])
                with colr1:
                    setores_rec = sorted({_norm_setor(x) for x in df_colabs_adm["setor"].dropna().tolist() if str(x).strip()})
                    setor_rec = st.selectbox("Setor do colaborador", setores_rec, key="adm_rec_setor")
                df_setor_rec = df_colabs_adm[df_colabs_adm["setor"].astype(str).str.strip().str.upper() == _norm_setor(setor_rec)].copy()
                opts_rec = [f"{str(r['nome']).strip()} ({str(r['chapa']).strip()})" for _, r in df_setor_rec.iterrows()]
                with colr2:
                    pick_rec = st.selectbox("Colaborador", opts_rec, key="adm_rec_pick") if opts_rec else None
                with colr3:
                    senha_rec = st.text_input("Nova senha do usuário", type="password", key="adm_rec_pwd")
                if st.button("Recuperar / recriar usuário", key="adm_rec_btn"):
                    if not pick_rec or not senha_rec:
                        st.error("Selecione o colaborador e digite a senha.")
                    else:
                        chapa_rec = pick_rec.rsplit("(", 1)[-1].replace(")", "").strip()
                        ok = recover_system_user_from_colaborador(setor_rec, chapa_rec, senha_rec)
                        if ok:
                            try:
                                st.cache_data.clear()
                            except Exception:
                                pass
                            st.success("Usuário recuperado com sucesso.")
                            st.rerun()
                        else:
                            st.error("Não encontrei esse colaborador para recuperar.")

            st.markdown("### ➕ Cadastro manual de usuário do sistema")
            cman1, cman2, cman3 = st.columns([1, 1, 1])
            with cman1:
                setor_man = st.text_input("Setor do usuário", value="FLV", key="adm_man_setor")
            with cman2:
                chapa_man = st.text_input("Chapa do usuário", key="adm_man_chapa")
            with cman3:
                nome_man = st.text_input("Nome do usuário", key="adm_man_nome")
            senha_man = st.text_input("Senha do usuário", type="password", key="adm_man_pwd", help="Se deixar em branco, a senha padrão será a própria chapa sem símbolos.")
            cman4, cman5, cman6 = st.columns([1, 1, 1])
            with cman4:
                lider_man = st.checkbox("É líder", value=False, key="adm_man_lider")
            with cman5:
                admin_man = st.checkbox("É admin", value=False, key="adm_man_admin")
            with cman6:
                criar_colab_man = st.checkbox("Criar colaborador junto", value=True, key="adm_man_colab")
            if st.button("Salvar usuário manualmente", key="adm_man_btn"):
                setor_norm = _norm_setor(setor_man)
                chapa_norm = _norm_chapa(chapa_man)
                nome_final = (nome_man or chapa_norm).strip()
                senha_final = (senha_man or default_password_for_chapa(chapa_norm)).strip()
                if not setor_norm or not chapa_norm:
                    st.error("Digite setor e chapa.")
                else:
                    try:
                        if criar_colab_man and not colaborador_exists(setor_norm, chapa_norm):
                            create_colaborador(nome_final, setor_norm, chapa_norm, criar_login=False)
                        create_system_user(nome_final, setor_norm, chapa_norm, senha_final, is_lider=int(lider_man), is_admin=int(admin_man), is_ax_lider=0)
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        st.success(f"Usuário salvo com sucesso. Senha ativa: {senha_final}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Falha ao salvar usuário: {e}")

            st.markdown("---")
            st.subheader("🏷️ Renomear setor")
            st.caption("Use esta subárea para trocar o nome de um setor em todo o sistema sem precisar editar tabela por tabela.")
            try:
                setores_ren = listar_setores_db()
            except Exception:
                setores_ren = []
            rr1, rr2 = st.columns([1.2, 1.4])
            with rr1:
                setor_ren_atual = st.selectbox("Setor atual", setores_ren, key="adm_ren_setor_atual") if setores_ren else st.text_input("Setor atual", value="FLV", key="adm_ren_setor_atual_txt")
            with rr2:
                setor_ren_novo = st.text_input("Novo nome do setor", value=str(setor_ren_atual or ''), key="adm_ren_setor_novo")
            st.caption("Isso atualiza o nome do setor nas tabelas que possuem a coluna setor, incluindo colaboradores, usuários, escala, retificações, assinaturas e competências.")
            if st.button("Renomear setor", key="adm_ren_setor_btn"):
                try:
                    res = admin_rename_setor_global(str(setor_ren_atual), str(setor_ren_novo))
                    st.success(f"Setor renomeado de {res['setor_antigo']} para {res['setor_novo']}. Tabelas afetadas: {res['total_tabelas']} | Registros atualizados: {res['total_registros']}")
                    if res['tabelas_atualizadas']:
                        st.dataframe(pd.DataFrame(res['tabelas_atualizadas'], columns=['Tabela', 'Registros atualizados']), use_container_width=True, hide_index=True)
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao renomear setor: {e}")

            st.markdown("---")
            st.subheader("🧊 Competência do setor (fechar / reabrir)")
            st.caption("Use este painel do ADMIN para congelar ou descongelar a competência de qualquer setor.")
            setores_comp = listar_setores_db()
            ac1, ac2, ac3 = st.columns([1.4, 1, 1])
            with ac1:
                setor_comp_admin = st.selectbox("Setor da competência", setores_comp, key="adm_comp_setor") if setores_comp else st.text_input("Setor da competência", value="FLV", key="adm_comp_setor_txt")
            with ac2:
                ano_comp_admin = st.number_input("Ano da competência", value=int(st.session_state.get("cfg_ano", datetime.now().year)), step=1, key="adm_comp_ano")
            with ac3:
                mes_comp_admin = st.selectbox("Mês da competência", list(range(1, 13)), index=max(0, int(st.session_state.get("cfg_mes", datetime.now().month)) - 1), key="adm_comp_mes")

            status_comp_admin = get_status_competencia(str(setor_comp_admin), int(ano_comp_admin), int(mes_comp_admin))
            s1, s2, s3 = st.columns([1.2, 1, 1])
            s1.metric("Status atual", status_comp_admin)
            if s2.button("🔒 Fechar competência", key="adm_comp_fechar", disabled=(status_comp_admin == "FECHADA")):
                try:
                    set_status_competencia(str(setor_comp_admin), int(ano_comp_admin), int(mes_comp_admin), "FECHADA")
                    st.success(f"Competência {int(mes_comp_admin):02d}/{int(ano_comp_admin)} do setor {str(setor_comp_admin).strip()} fechada com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao fechar competência: {e}")
            if s3.button("🔓 Reabrir competência", key="adm_comp_reabrir", disabled=(status_comp_admin == "ABERTA")):
                try:
                    set_status_competencia(str(setor_comp_admin), int(ano_comp_admin), int(mes_comp_admin), "ABERTA")
                    st.success(f"Competência {int(mes_comp_admin):02d}/{int(ano_comp_admin)} do setor {str(setor_comp_admin).strip()} reaberta com sucesso.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao reabrir competência: {e}")

            st.markdown("---")
            st.subheader("🗄️ Backup / Restauração (escala.db)")

            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("Criar backup agora", key="adm_backup_now"):
                    try:
                        p = create_backup_now(prefix="manual")
                        st.success(f"Backup criado: {os.path.basename(p)}")
                    except Exception as e:
                        st.error(f"Falha ao criar backup: {e}")

            bks = list_backups()
            bk_sel = st.selectbox("Backups disponíveis", bks, key="adm_bk_sel") if bks else None
            if bk_sel:
                bk_path = os.path.join(BACKUP_DIR, bk_sel)
                with open(bk_path, "rb") as f:
                    st.download_button("⬇️ Baixar backup selecionado", data=f, file_name=bk_sel, mime="application/octet-stream", key="adm_bk_dl")

            st.markdown("### Restaurar um backup")
            up = st.file_uploader("Envie um arquivo .db (backup do escala.db)", type=["db"], key="adm_bk_up")
            if up is not None:
                if st.button("Restaurar este backup", key="adm_bk_restore"):
                    try:
                        restore_backup_from_bytes(up.getvalue())
                        st.success("Backup restaurado! Recarregando...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Falha ao restaurar: {e}")

            st.caption(f"Backup automático (1x/dia) após {AUTO_BACKUP_HOUR:02d}:00. Pasta: {BACKUP_DIR}/")

            st.markdown("---")
            st.subheader("🧪 Teste Supabase")

            ok_conn, msg_conn = _supabase_test_connection_detail()
            if "sb_diag_last_error" not in st.session_state:
                st.session_state["sb_diag_last_error"] = ""
            if "sb_diag_last_msg" not in st.session_state:
                st.session_state["sb_diag_last_msg"] = msg_conn

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Sync habilitado", "Sim" if SUPABASE_SYNC_ENABLED else "Não")
            d2.metric("Conexão", "OK" if ok_conn else "Falha")
            d3.metric("Último push", _fmt_ts_br(_SUPABASE_LAST_PUSH_TS))
            d4.metric("Último pull", _fmt_ts_br(_SUPABASE_LAST_PULL_TS))

            info_df = pd.DataFrame([
                {"Campo": "URL", "Valor": SUPABASE_URL or "—"},
                {"Campo": "Schema", "Valor": SUPABASE_SCHEMA or "public"},
                {"Campo": "Key", "Valor": _mask_secret(SUPABASE_KEY)},
                {"Campo": "Auto pull ao abrir", "Valor": "Sim" if SUPABASE_AUTO_PULL_ON_START else "Não"},
                {"Campo": "Auto push no commit", "Valor": "Sim" if SUPABASE_AUTO_PUSH_ON_COMMIT else "Não"},
                {"Campo": "Auto push ao fechar", "Valor": "Sim" if SUPABASE_AUTO_PUSH_ON_CLOSE else "Não"},
                {"Campo": "Auto bootstrap pós-schema", "Valor": "Sim" if SUPABASE_AUTO_BOOTSTRAP_AFTER_SCHEMA else "Não"},
                {"Campo": "Auto restore se local vazio", "Valor": "Sim" if SUPABASE_AUTO_RESTORE_IF_LOCAL_EMPTY else "Não"},
                {"Campo": "Lock de sync (s)", "Valor": str(SUPABASE_SYNC_LOCK_TIMEOUT_SEC)},
                {"Campo": "Status atual", "Valor": msg_conn},
                {"Campo": "Último erro", "Valor": (_SUPABASE_LAST_ERROR or st.session_state.get("sb_diag_last_error", "")) or "—"},
            ])
            st.dataframe(info_df, use_container_width=True, hide_index=True)

            db_runtime = _db_runtime_summary()
            st.caption(f"Banco local: {db_runtime.get('db_path','')} | Existe: {db_runtime.get('db_exists')} | Melhor candidato: {db_runtime.get('best_candidate','')}")

            sb1, sb2, sb3 = st.columns(3)
            if sb1.button("Testar conexão", key="sb_test_conn_admin"):
                ok_now, msg_now = _supabase_test_connection_detail()
                st.session_state["sb_diag_last_msg"] = msg_now
                if ok_now:
                    st.success(msg_now)
                else:
                    st.session_state["sb_diag_last_error"] = msg_now
                    st.error(msg_now)

            if sb2.button("Forçar push", key="sb_force_push_admin"):
                try:
                    ok_push = _supabase_push_all_from_sqlite(force=True)
                    if ok_push:
                        st.session_state["sb_diag_last_error"] = ""
                        st.success("Push executado com sucesso.")
                    else:
                        st.warning(_SUPABASE_LAST_ERROR or "Push não executado.")
                except Exception as e:
                    st.session_state["sb_diag_last_error"] = str(e)
                    st.error(f"Falha no push: {e}")

            if sb3.button("Forçar pull", key="sb_force_pull_admin"):
                try:
                    ok_pull = _supabase_pull_all_to_sqlite(force=True)
                    if ok_pull:
                        st.session_state["sb_diag_last_error"] = ""
                        st.success("Pull executado com sucesso.")
                    else:
                        st.warning(_SUPABASE_LAST_ERROR or "Pull não trouxe dados.")
                except Exception as e:
                    st.session_state["sb_diag_last_error"] = str(e)
                    st.error(f"Falha no pull: {e}")

            with st.expander("Comparar tabelas local x Supabase", expanded=False):
                st.dataframe(_supabase_compare_tables_snapshot(), use_container_width=True, hide_index=True, height=360)

            st.markdown("---")
            st.subheader("🏷️ Setores (criar / listar)")
            setores = listar_setores_db()
            st.info("Setores cadastrados: " + ", ".join(setores))

            novo_setor = st.text_input("Novo setor (ex: FLV)", key="adm_new_setor")
            if st.button("➕ Criar setor", key="adm_create_setor"):
                try:
                    criar_setor_db(novo_setor)
                    st.success("Setor criado/garantido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            st.markdown("---")

            st.subheader("📄 Importar escala a partir de PDF (automático — ESCALA_PONTO_NEW)")

            st.caption("Importa 100% automático: Nome + Chapa + Entrada (1ª linha) + FOLG/FER/AFA. Aplica no mês detectado do PDF como overrides (e pode cadastrar férias).")


            colA, colB, colC, colD = st.columns([1.3, 1, 1, 1])

            with colA:

                setor_dest = st.selectbox("Setor destino:", list_setores(), key="pdf_setor_dest")

            with colB:

                criar_colabs = st.checkbox("Criar/atualizar colaboradores", value=True, key="pdf_criar_colabs")

            with colC:

                limpar_mes = st.checkbox("Limpar overrides do mês antes", value=False, key="pdf_limpar_mes")

            with colD:

                cadastrar_ferias = st.checkbox("Cadastrar férias (FER)", value=True, key="pdf_cad_ferias")


            map_afa = st.checkbox("Tratar AFA como Folga", value=False, key="pdf_map_afa")
            auto_gerar_pdf = st.checkbox("Após importar, gerar mês automaticamente respeitando ajustes", value=True, key="pdf_auto_gerar")


            pdf = st.file_uploader("Enviar PDF da escala (ESCALA_PONTO_NEW)", type=["pdf"], key="adm_pdf_auto")

            if pdf is not None:

                try:

                    import PyPDF2

                    reader = PyPDF2.PdfReader(pdf)

                    parts = []

                    for page in reader.pages:

                        parts.append(page.extract_text() or "")

                    pdf_bytes = pdf.getvalue()
                    extracted = "\n".join(parts).strip()

                    if not extracted and not pdf_bytes:

                        st.warning("Não consegui extrair texto desse PDF (provável PDF imagem). Converta para PDF pesquisável ou envie CSV/Excel. OCR exige tesseract+poppler no servidor.")

                    else:

                        ano, mes, items, erros = _parse_escala_ponto_new_pdf_bytes(pdf_bytes) if pdf_bytes else (None, None, [], [])
                        if not items:
                            ano, mes, items, erros_txt = _parse_escala_ponto_new_pdf_text(extracted)
                            erros = (erros or []) + (erros_txt or [])


                        if erros:

                            st.warning("Encontrei divergências na leitura (ainda dá para aplicar, mas recomendo revisar):")

                            st.write(erros[:20])

                            if len(erros) > 20:

                                st.caption(f"... +{len(erros)-20} avisos")


                        if not items:

                            st.error("Não consegui identificar funcionários/entradas nesse PDF.")

                        else:

                            st.success(f"Modelo reconhecido ✅  Mês detectado: {mes:02d}/{ano} | Funcionários no PDF: {len(items)}")


                            with st.expander("Prévia (primeiros 3 funcionários)"):

                                for it in items[:3]:

                                    st.markdown(f"**{it.get('nome','')}**  — Chapa: `{it.get('chapa','')}`")

                                    st.write(it.get("tokens", [])[:10], " ...")


                            if st.button("✅ Aplicar escala do PDF no sistema (1 clique)", key="btn_apply_pdf"):

                                _apply_pdf_import_to_db(

                                    setor_destino=setor_dest,

                                    ano=int(ano),

                                    mes=int(mes),

                                    items=items,

                                    criar_colabs=bool(criar_colabs),

                                    limpar_mes_antes=bool(limpar_mes),

                                    map_afa_para_folga=bool(map_afa),

                                    cadastrar_ferias=bool(cadastrar_ferias),

                                )

                                if bool(auto_gerar_pdf):

                                    try:

                                        hist_pdf, estado_pdf = _build_hist_from_pdf_items(

                                            setor_dest, int(ano), int(mes), items,

                                            map_afa_para_folga=bool(map_afa)

                                        )

                                        if hist_pdf:

                                            save_escala_mes_db(setor_dest, int(ano), int(mes), hist_pdf)

                                            save_estado_mes(setor_dest, int(ano), int(mes), estado_pdf)

                                            st.session_state["ano"] = int(ano)

                                            st.session_state["mes"] = int(mes)

                                            st.success("PDF importado com sucesso! Para este mês, o PDF virou a fonte da verdade: folgas, férias e AFA foram salvos exatamente como estão no PDF. As regras do aplicativo voltam a valer normalmente na geração do mês seguinte.")

                                        else:

                                            st.warning("PDF importado, mas não consegui montar a escala final do mês a partir dos itens lidos.")

                                    except Exception as e_auto:

                                        st.warning(f"PDF importado, mas falhou ao salvar a escala final exatamente como veio no PDF: {e_auto}")

                                else:

                                    st.success("Importação aplicada com sucesso! Agora clique em 'Gerar agora (respeita ajustes)' para montar a escala do mês com folgas, AFA e férias do PDF.")

                except Exception as e:

                    st.error(f"Falha ao ler/importar PDF: {e}")





def _fast_restore_bundled_latest_before_start() -> None:
    """
    Restore mínimo e rápido antes de qualquer inicialização pesada:
    - se data/escala.db não existir ou vier zerado
    - e existir latest_stable.db ao lado do main.py
    - copia diretamente para data/escala.db
    """
    try:
        app_dir = Path(__file__).resolve().parent
        data_dir = app_dir / "data"
        db_path = data_dir / "escala.db"
        backup_candidates = [
            app_dir / "latest_stable.db",
            app_dir / "backups" / "latest_stable.db",
            app_dir / "data" / "latest_stable.db",
        ]
        data_dir.mkdir(parents=True, exist_ok=True)
        db_ok = db_path.exists() and db_path.stat().st_size > 0
        if db_ok:
            return
        for backup in backup_candidates:
            if backup.exists() and backup.stat().st_size > 0:
                shutil.copy2(backup, db_path)
                try:
                    latest_local = Path(BACKUP_DIR) / "latest_stable.db"
                    latest_local.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, latest_local)
                except Exception:
                    pass
                break
    except Exception:
        pass


# =========================================================
# SAFE BOOT FIXES
# =========================================================
# Defaults de inicialização para evitar NameError/KeyError no boot
if "QUICK_LOGIN_BOOT" not in globals():
    QUICK_LOGIN_BOOT = True
if "FAST_BOOT_SKIP_STARTUP_AUTO_BACKUP" not in globals():
    FAST_BOOT_SKIP_STARTUP_AUTO_BACKUP = False
if not hasattr(st, "session_state"):
    pass
else:
    if "auth" not in st.session_state:
        st.session_state["auth"] = None
    if "_full_boot_done" not in st.session_state:
        st.session_state["_full_boot_done"] = False

if "validar_contrato_sistema" not in globals():
    def validar_contrato_sistema():
        return None

# =========================================================
# MAIN
# =========================================================
_fast_restore_bundled_latest_before_start()
validar_contrato_sistema()

if st.session_state["auth"] is None and QUICK_LOGIN_BOOT:
    db_init_fast_login()
    page_login()
else:
    if not st.session_state.get("_full_boot_done", False):
        db_init()
        if not FAST_BOOT_SKIP_STARTUP_AUTO_BACKUP:
            auto_backup_if_due()
        st.session_state["_full_boot_done"] = True
    if st.session_state["auth"] is None:
        page_login()
    else:
        page_app()
