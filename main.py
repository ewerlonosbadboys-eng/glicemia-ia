# app.py
# =========================================================
# ESCALA 5x2 OFICIAL — COMPLETO (SUBGRUPO = REGRAS)
# + Preferência "Evitar folga" por subgrupo
# + Persistência real (SQLite) de ajustes (overrides)
# + Calendário RH visual + Banco de Horas
# + Admin (somente setor ADMIN e is_admin)
# + Gerar respeitando ajustes (overrides) OU ignorando
#
# ✅ ATIVO:
# 1) DESCANSO GLOBAL 11:10 (INTERSTÍCIO) PARA A ESCALA INTEIRA
# 2) DOMINGO 1x1 (POR COLABORADOR) GLOBAL
# 3) PROIBIR FOLGAS CONSECUTIVAS AUTOMÁTICAS (exceto se travado por override)
#
# ❌ REMOVIDO (como você pediu):
# - "Marcar Balanço (madrugada)"
# - "Marcar Balanço Madrugada (saída tarde) ✅"
# - TODA a lógica/status/horários/funções relacionadas a Balanço/Madrugada
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
