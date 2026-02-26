import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import io
import random
import calendar
from openpyxl.styles import PatternFill, Alignment, Border, Side, Font
from openpyxl.utils import get_column_letter

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# =========================================================
# MEMÓRIA
# =========================================================
if "db_users" not in st.session_state:
    st.session_state["db_users"] = []
if "historico" not in st.session_state:
    st.session_state["historico"] = {}
if "cfg_mes" not in st.session_state:
    st.session_state["cfg_mes"] = datetime.now().month
if "cfg_ano" not in st.session_state:
    st.session_state["cfg_ano"] = datetime.now().year
if "ferias" not in st.session_state:
    st.session_state["ferias"] = {}

# =========================================================
# CONFIG
# =========================================================
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
# UTIL
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


def _nao_consecutiva(df, idx):
    if idx > 0 and df.loc[idx - 1, "Status"] == "Folga":
        return False
    if idx < len(df) - 1 and df.loc[idx + 1, "Status"] == "Folga":
        return False
    return True


def _semana_seg_dom(datas, i):
    d = datas[i]
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    idxs = []
    for k, dd in enumerate(datas):
        if monday.date() <= dd.date() <= sunday.date():
            idxs.append(k)
    return idxs


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _intervalo_ferias_do_nome(nome: str):
    itens = st.session_state["ferias"].get(nome, [])
    out = []
    for it in itens:
        try:
            ini = datetime.strptime(it["inicio"], "%Y-%m-%d").date()
            fim = datetime.strptime(it["fim"], "%Y-%m-%d").date()
            out.append((ini, fim))
        except:
            pass
    return out


def _esta_de_ferias(nome: str, data_obj: date) -> bool:
    for ini, fim in _intervalo_ferias_do_nome(nome):
        if ini <= data_obj <= fim:
            return True
    return False


def _semanas_para_pular_5x2_por_retorno(nome: str) -> set:
    semanas_skip = set()
    for ini, fim in _intervalo_ferias_do_nome(nome):
        retorno = fim + timedelta(days=1)
        semanas_skip.add(_monday_of(retorno))
    return semanas_skip


# =========================================================
# FUNÇÕES DE DOMINGO / GRUPOS
# =========================================================
def build_category_groups(names, datas):
    """
    Deterministic grouping for category (A/B) based on stable seed with month+year
    Returns (grupo_a_set, grupo_b_set)
    """
    if not names:
        return set(), set()
    # Use deterministic seed so same split each run for same month/yr
    seed = 1000 + datas[0].month + datas[0].year
    rng = random.Random(seed)
    names_sh = names[:]
    rng.shuffle(names_sh)
    meio = (len(names_sh) + 1) // 2
    grupo_a = set(names_sh[:meio])
    grupo_b = set(names_sh[meio:])
    return grupo_a, grupo_b


def montar_domingo_1x1_por_categoria(cats, datas):
    """
    Build base domino mapping (without forcing 'Trabalho' on others).
    Returns dict: cat -> {dom_index: set_of_names_that_should_folgar_that_dom}
    Uses deterministic grouping and alternation (A folga 1st, B folga 2nd, etc.)
    """
    domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    esquema = {cat: {} for cat in cats.keys()}

    for cat, membros in cats.items():
        nomes = sorted([u["Nome"] for u in membros])
        if not nomes:
            for dom_i in domingos:
                esquema[cat][dom_i] = set()
            continue

        if len(nomes) == 1:
            nome = nomes[0]
            for k, dom_i in enumerate(domingos):
                data_dom = datas[dom_i].date()
                if _esta_de_ferias(nome, data_dom):
                    esquema[cat][dom_i] = set()
                else:
                    esquema[cat][dom_i] = {nome} if (k % 2 == 0) else set()
            continue

        grupo_a, grupo_b = build_category_groups(nomes, datas)
        for k, dom_i in enumerate(domingos):
            data_dom = datas[dom_i].date()
            alvo = grupo_a if (k % 2 == 0) else grupo_b
            folgam = {nm for nm in alvo if not _esta_de_ferias(nm, data_dom)}
            esquema[cat][dom_i] = folgam

    return esquema


def enforce_domingos_after_manual(category, datas, st_hist, db_users, changed_dom_index, changed_name, new_status):
    """
    Quando um domingo foi alterado manualmente para changed_name em changed_dom_index,
    ajusta TODOS os domingos da mesma categoria para manter alternância 1x1.

    Estratégia:
    - Constrói grupos A/B determinísticos.
    - Descobre qual grupo o usuário pertence (A ou B).
    - Decide offset tal que no domingo changed_dom_index o grupo que tem folga corresponda
      ao fato de changed_name estar em Folga (se user marcou Folga) ou Trabalho (se marcou Trabalho).
    - Para cada domingo k:
        desired_group = A if (k+offset) % 2 == 0 else B
      aplica Folga para membros desse desired_group (exceto férias) e Trabalho para os outros (exceto férias).
    - Mantém outras marcações de Férias intactas.
    - Se houver conflitos muito fortes (ex.: todos de desired_group estão de férias), deixa como está.
    - Atualiza st.session_state['historico'] dfs.
    """
    # get category member names
    membros = [u for u in db_users if u["Categoria"] == category]
    nomes = sorted([u["Nome"] for u in membros])
    if not nomes:
        return

    grupo_a, grupo_b = build_category_groups(nomes, datas)

    domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    if changed_dom_index not in domingos:
        return

    # find position k of changed_dom_index among domingos
    k_pos = domingos.index(changed_dom_index)

    # which group is changed_name in?
    grupo_name = "A" if changed_name in grupo_a else ("B" if changed_name in grupo_b else None)
    if grupo_name is None:
        # changed person not in this category; nothing to do
        return

    # Determine offset:
    # If changed person was set to 'Folga' -> desired_group at k_pos should be group_name
    # If set to 'Trabalho' -> desired_group at k_pos should be the opposite group
    wants_folga = (new_status == "Folga")
    # If wants_folga True => (k_pos + offset) % 2 == 0 => offset %2 == (0 - k_pos)%2
    # If wants_folga False => desired group must be opposite => (k_pos + offset)%2 == 1
    if wants_folga:
        # desired parity = 0 maps to grupo_a; 1 maps to grupo_b
        # we want desired parity such that desired_group == grupo_name
        if grupo_name == "A":
            parity_needed = 0
        else:
            parity_needed = 1
    else:
        # they are set to Trabalho => opposite group must be folga at this sunday
        if grupo_name == "A":
            parity_needed = 1
        else:
            parity_needed = 0

    # compute offset so that (k_pos + offset) %2 == parity_needed
    offset = (parity_needed - (k_pos % 2)) % 2

    # Now enforce for all domingos
    for idx_k, dom_i in enumerate(domingos):
        desired_parity = (idx_k + offset) % 2
        desired_group = grupo_a if desired_parity == 0 else grupo_b

        # Apply folgas/trabalhos to all names in category for dom_i
        # but skip those on Férias
        for nm in nomes:
            df = st_hist.get(nm)
            if df is None:
                continue
            # if is férias in that day, keep
            if df.loc[dom_i, "Status"] == "Férias":
                continue

            if nm in desired_group:
                # set Folga
                df.loc[dom_i, "Status"] = "Folga"
                df.loc[dom_i, "H_Entrada"] = ""
                df.loc[dom_i, "H_Saida"] = ""
            else:
                # set Trabalho
                df.loc[dom_i, "Status"] = "Trabalho"
                # recompute entry/exit using padrão stored in db_users
                user_info = next((u for u in db_users if u["Nome"] == nm), None)
                if user_info:
                    ent_pad = user_info.get("Entrada", "06:00")
                    # try to keep previous entry if it exists and not empty, else set default
                    prev_ent = df.loc[dom_i, "H_Entrada"]
                    if prev_ent:
                        df.loc[dom_i, "H_Entrada"] = prev_ent
                    else:
                        df.loc[dom_i, "H_Entrada"] = ent_pad
                    df.loc[dom_i, "H_Saida"] = (datetime.strptime(df.loc[dom_i, "H_Entrada"], "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
            # update back in historico
            st.session_state["historico"][nm] = df


# =========================================================
# BALANCEAMENTO SEMANAL POR CATEGORIA
# =========================================================
def escolher_dia_balanceado(possiveis, cont_semana_cat):
    if not possiveis:
        return None
    random.shuffle(possiveis)
    possiveis.sort(key=lambda j: cont_semana_cat.get(j, 0))
    return possiveis[0]


# =========================================================
# GERAR ESCALA (REGRAS + BALANCEAMENTO + DOM 1x1 DESDE O 1º DOM)
# =========================================================
def gerar_escala_inteligente(lista_usuarios, ano, mes):
    datas = _dias_mes(ano, mes)

    # agrupar por categoria
    cats = {}
    for u in lista_usuarios:
        c = u.get("Categoria", "Geral")
        cats.setdefault(c, []).append(u)

    # domingo 1x1 real por categoria (grupos A/B)
    dom_1x1 = montar_domingo_1x1_por_categoria(cats, datas)

    # contagem global para limite 50% por dia na categoria
    cont_folga_cat_dia = {cat: {i: 0 for i in range(len(datas))} for cat in cats.keys()}

    novo_hist = {}

    for cat, membros in cats.items():
        total_cat = len(membros)
        random.shuffle(membros)

        for user in membros:
            nome = user["Nome"]
            entrada_padrao = user.get("Entrada", "06:00")
            pode_folgar_sabado = bool(user.get("Folga_Sab", False))
            semanas_skip_5x2 = _semanas_para_pular_5x2_por_retorno(nome)

            df = pd.DataFrame({
                "Data": datas,
                "Dia": [D_PT[d.day_name()] for d in datas],
                "Status": "Trabalho"
            })

            # 1) férias primeiro
            for i, d in enumerate(datas):
                if _esta_de_ferias(nome, d.date()):
                    df.loc[i, "Status"] = "Férias"

            # 2) APLICAR DOMINGO 1x1 DESDE O PRIMEIRO DOMINGO
            for dom_i, folgam_set in dom_1x1.get(cat, {}).items():
                if df.loc[dom_i, "Status"] == "Férias":
                    continue
                if nome in folgam_set:
                    df.loc[dom_i, "Status"] = "Folga"
                else:
                    df.loc[dom_i, "Status"] = "Trabalho"

            # pré-contar folgas de domingo no contador global
            for i in range(len(datas)):
                if df.loc[i, "Status"] == "Folga":
                    cont_folga_cat_dia[cat][i] += 1

            # 3) lista de semanas únicas (SEG->DOM)
            semanas = []
            seen = set()
            for i in range(len(datas)):
                idxs = tuple(_semana_seg_dom(datas, i))
                if idxs and idxs not in seen:
                    seen.add(idxs)
                    semanas.append(list(idxs))

            # 4) aplicar 5x2 por semana SEG->DOM (exceto semana de retorno de férias)
            for idxs in semanas:
                monday_week = _monday_of(datas[idxs[0]].date())

                # semana de retorno: só domingo 1x1
                if monday_week in semanas_skip_5x2:
                    continue

                # elegíveis: não férias
                idxs_nao_ferias = [j for j in idxs if df.loc[j, "Status"] != "Férias"]
                if not idxs_nao_ferias:
                    continue

                # contador semanal (para balancear dentro da semana)
                cont_semana_cat = {j: 0 for j in idxs}
                for j in idxs:
                    if df.loc[j, "Status"] == "Folga":
                        cont_semana_cat[j] += 1

                folgas_semana = int((df.loc[idxs_nao_ferias, "Status"] == "Folga").sum())

                # completar até 2 folgas/semana
                while folgas_semana < 2:
                    possiveis = []
                    for j in idxs_nao_ferias:
                        if df.loc[j, "Status"] != "Trabalho":
                            continue

                        dia = df.loc[j, "Dia"]

                        # sábado só vira folga se marcado
                        if dia == "sáb" and not pode_folgar_sabado:
                            continue

                        # sem folgas consecutivas
                        if not _nao_consecutiva(df, j):
                            continue

                        # limite 50% por dia na categoria
                        if total_cat > 1:
                            limite = max(1, total_cat // 2)
                            if cont_folga_cat_dia[cat][j] >= limite:
                                continue

                        possiveis.append(j)

                    # relaxa 50% se necessário (mantém sábado e não consecutiva)
                    if not possiveis:
                        for j in idxs_nao_ferias:
                            if df.loc[j, "Status"] != "Trabalho":
                                continue
                            dia = df.loc[j, "Dia"]
                            if dia == "sáb" and not pode_folgar_sabado:
                                continue
                            if not _nao_consecutiva(df, j):
                                continue
                            possiveis.append(j)

                    escolhido = escolher_dia_balanceado(possiveis, cont_semana_cat)
                    if escolhido is None:
                        break

                    df.loc[escolhido, "Status"] = "Folga"
                    cont_folga_cat_dia[cat][escolhido] += 1
                    cont_semana_cat[escolhido] = cont_semana_cat.get(escolhido, 0) + 1
                    folgas_semana += 1

                # segurança: máximo 5 seguidos
                consec = 0
                for j in idxs:
                    if df.loc[j, "Status"] == "Trabalho":
                        consec += 1
                        if consec > 5:
                            dia = df.loc[j, "Dia"]
                            if dia != "sáb" or pode_folgar_sabado:
                                if _nao_consecutiva(df, j) and df.loc[j, "Status"] != "Férias":
                                    df.loc[j, "Status"] = "Folga"
                                    cont_folga_cat_dia[cat][j] += 1
                                    consec = 0
                    else:
                        consec = 0

            # 5) horários com interstício
            ents, sais = [], []
            for i in range(len(df)):
                if df.loc[i, "Status"] in ["Folga", "Férias"]:
                    ents.append("")
                    sais.append("")
                else:
                    e = entrada_padrao
                    if i > 0 and sais and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], entrada_padrao)
                    ents.append(e)
                    sais.append((datetime.strptime(e, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M"))

            df["H_Entrada"] = ents
            df["H_Saida"] = sais

            novo_hist[nome] = df

    return novo_hist


# =========================================================
# INTERFACE
# =========================================================
aba1, aba2, aba3, aba4, aba5 = st.tabs(
    ["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel", "🏖️ 5. Férias"]
)

# ---------------------------------------------------------
# ABA 1 - CADASTRO
# ---------------------------------------------------------
with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome")
    ct = c2.text_input("Categoria")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    folga_sab = st.checkbox("Permitir folga no sábado (só se marcado)")

    if st.button("Salvar Funcionário"):
        if n and ct:
            st.session_state["db_users"].append({
                "Nome": n,
                "Categoria": ct,
                "Entrada": h_in.strftime("%H:%M"),
                "Folga_Sab": folga_sab
            })
            st.success(f"{n} cadastrado!")
        else:
            st.error("Preencha Nome e Categoria.")

    if st.session_state["db_users"]:
        st.dataframe(pd.DataFrame(st.session_state["db_users"]), use_container_width=True)

# ---------------------------------------------------------
# ABA 2 - GERAR
# ---------------------------------------------------------
with aba2:
    st.subheader("Gerar escala")
    colm1, colm2 = st.columns(2)
    mes = colm1.selectbox("Mês", list(range(1, 13)), index=st.session_state["cfg_mes"] - 1)
    ano = colm2.number_input("Ano", value=st.session_state["cfg_ano"], step=1)

    st.session_state["cfg_mes"] = int(mes)
    st.session_state["cfg_ano"] = int(ano)

    if st.button("🚀 GERAR ESCALA (balanceado desde o 1º domingo)"):
        if st.session_state["db_users"]:
            st.session_state["historico"] = gerar_escala_inteligente(
                st.session_state["db_users"],
                st.session_state["cfg_ano"],
                st.session_state["cfg_mes"]
            )
            st.success("Gerado! Domingo 1x1 inicia balanceado no primeiro domingo.")
        else:
            st.warning("Cadastre funcionários na Aba 1.")

    if st.session_state["historico"]:
        for nome, df in st.session_state["historico"].items():
            with st.expander(f"Visualizar: {nome}"):
                st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# ABA 3 - AJUSTES (AGORA COM ENFORCE DE DOMINGOS)
# ---------------------------------------------------------
with aba3:
    st.subheader("⚙️ Ajustes Manuais")

    if not st.session_state["historico"]:
        st.info("Gere a escala na Aba 2.")
    else:
        f_ed = st.selectbox("Funcionário:", list(st.session_state["historico"].keys()))
        df_e = st.session_state["historico"][f_ed]
        user_info = next(u for u in st.session_state["db_users"] if u["Nome"] == f_ed)

        col_a, col_b, col_c, col_d = st.columns(4)

        with col_a:
            st.markdown("#### 🔄 Trocar Folga (ou Dia)")
            folgas_atuais = df_e[df_e["Status"] == "Folga"].index.tolist()
            d_tira = st.selectbox("Dia que vai TRABALHAR (remover folga):", [d + 1 for d in folgas_atuais]) if folgas_atuais else None
            d_poe = st.number_input("Novo dia para FOLGAR:", 1, len(df_e), value=1, key="troca_folga_dpoe")

            if st.button("Confirmar troca", key="btn_troca_folga"):
                if d_tira is None:
                    st.warning("Sem folgas para remover.")
                elif df_e.loc[d_poe - 1, "Status"] == "Férias" or df_e.loc[d_tira - 1, "Status"] == "Férias":
                    st.error("Não é permitido trocar dias marcados como FÉRIAS.")
                else:
                    df_e.loc[d_tira - 1, "Status"] = "Trabalho"
                    df_e.loc[d_tira - 1, "H_Entrada"] = next((u["Entrada"] for u in st.session_state["db_users"] if u["Nome"] == f_ed), "06:00")
                    df_e.loc[d_tira - 1, "H_Saida"] = (datetime.strptime(df_e.loc[d_tira - 1, "H_Entrada"], "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
                    df_e.loc[d_poe - 1, "Status"] = "Folga"
                    df_e.loc[d_poe - 1, "H_Entrada"] = ""
                    df_e.loc[d_poe - 1, "H_Saida"] = ""
                    st.session_state["historico"][f_ed] = df_e
                    st.success("Troca aplicada!")
                    st.rerun()

        with col_b:
            st.markdown("#### 🕒 Alterar Status/Horário Específico")
            dia_sel = st.number_input("Dia do mês:", 1, len(df_e), value=1, key="aj_dia_sel")
            opc = st.selectbox("Ação:", ["Marcar Trabalho", "Marcar Folga", "Marcar Férias", "Alterar Entrada"], key="aj_opc")
            nova_hora = st.time_input("Nova Entrada (se aplicável):", key="aj_nova_hora")

            if st.button("Aplicar ação"):
                idx = dia_sel - 1
                antigo = df_e.loc[idx, "Status"]
                if opc == "Marcar Férias":
                    df_e.loc[idx, "Status"] = "Férias"
                    df_e.loc[idx, "H_Entrada"] = ""
                    df_e.loc[idx, "H_Saida"] = ""
                    st.success("Dia marcado como FÉRIAS (manual).")
                elif opc == "Marcar Folga":
                    # prevent overwriting férias
                    if antigo == "Férias":
                        st.error("Não pode marcar folga sobre férias.")
                    else:
                        df_e.loc[idx, "Status"] = "Folga"
                        df_e.loc[idx, "H_Entrada"] = ""
                        df_e.loc[idx, "H_Saida"] = ""
                        st.success("Folga marcada manualmente.")
                elif opc == "Marcar Trabalho":
                    if antigo == "Férias":
                        st.error("Não pode marcar trabalho sobre férias.")
                    else:
                        df_e.loc[idx, "Status"] = "Trabalho"
                        ent = nova_hora.strftime("%H:%M")
                        df_e.loc[idx, "H_Entrada"] = ent
                        df_e.loc[idx, "H_Saida"] = (datetime.strptime(ent, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
                        st.success("Dia marcado como TRABALHO.")
                else:  # Alterar Entrada
                    if df_e.loc[idx, "Status"] != "Trabalho":
                        st.error("Só é possível alterar entrada em dias de TRABALHO.")
                    else:
                        ent = nova_hora.strftime("%H:%M")
                        df_e.loc[idx, "H_Entrada"] = ent
                        df_e.loc[idx, "H_Saida"] = (datetime.strptime(ent, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
                        st.success("Entrada atualizada.")

                # save change
                st.session_state["historico"][f_ed] = df_e

                # If changed day is a Sunday, enforce category alternation
                datas = df_e["Data"].tolist()
                if df_e.loc[idx, "Data"].day_name() == "Sunday":
                    # find category
                    categoria = user_info["Categoria"]
                    changed_dom_index = idx
                    changed_name = f_ed
                    new_status = df_e.loc[idx, "Status"]
                    enforce_domingos_after_manual(categoria, pd.Series(datas), st.session_state["historico"], st.session_state["db_users"], changed_dom_index, changed_name, new_status)
                    st.success("Regra de domingos aplicada na categoria em função da alteração manual.")
                st.rerun()

        with col_c:
            st.markdown("#### 🧩 Trocar Categoria")
            categorias = sorted(list(set(u["Categoria"] for u in st.session_state["db_users"])))
            idx_cat = categorias.index(user_info["Categoria"]) if user_info["Categoria"] in categorias else 0
            nova_cat = st.selectbox("Nova categoria:", categorias, index=idx_cat)
            if st.button("Salvar categoria"):
                user_info["Categoria"] = nova_cat
                st.success("Categoria alterada! Gere novamente para refletir.")

        with col_d:
            st.markdown("#### 🗓️ Sábado")
            novo_flag = st.checkbox("Permitir folga no sábado", value=bool(user_info.get("Folga_Sab", False)))
            if st.button("Salvar sábado"):
                user_info["Folga_Sab"] = bool(novo_flag)
                st.success("Atualizado! Gere novamente para refletir.")

        st.markdown("---")
        st.dataframe(df_e, use_container_width=True)

# ---------------------------------------------------------
# ABA 4 - EXCEL MODELO RH
# ---------------------------------------------------------
with aba4:
    st.subheader("📥 Excel modelo RH")
    if not st.session_state["historico"]:
        st.warning("Gere a escala na Aba 2.")
    else:
        if st.button("📊 GERAR EXCEL"):
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

                df_ref = list(st.session_state["historico"].values())[0]
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

                row_idx = 3
                for nome, df_f in st.session_state["historico"].items():
                    c_nome = ws.cell(row_idx, 1, nome)
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
                file_name=f"escala_modelo_RH_{st.session_state['cfg_mes']:02d}_{st.session_state['cfg_ano']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ---------------------------------------------------------
# ABA 5 - FÉRIAS
# ---------------------------------------------------------
with aba5:
    st.subheader("🏖️ Férias")
    if not st.session_state["db_users"]:
        st.info("Cadastre funcionários na Aba 1.")
    else:
        nomes = [u["Nome"] for u in st.session_state["db_users"]]
        nome_sel = st.selectbox("Funcionário:", nomes)

        colf1, colf2 = st.columns(2)
        ini = colf1.date_input("Início")
        fim = colf2.date_input("Fim")

        if st.button("Adicionar férias"):
            if fim < ini:
                st.error("Fim não pode ser menor que início.")
            else:
                st.session_state["ferias"].setdefault(nome_sel, []).append({
                    "inicio": ini.strftime("%Y-%m-%d"),
                    "fim": fim.strftime("%Y-%m-%d")
                })
                st.success("Férias adicionadas! Gere a escala de novo.")

        st.markdown("---")
        view = []
        for nome, intervalos in st.session_state["ferias"].items():
            for it in intervalos:
                view.append({"Nome": nome, "Início": it["inicio"], "Fim": it["fim"]})
        if view:
            st.dataframe(pd.DataFrame(view), use_container_width=True)
        else:
            st.info("Sem férias cadastradas.")
