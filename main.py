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


def _saida_from_entrada(ent: str) -> str:
    return (datetime.strptime(ent, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")


def _nao_consecutiva_folga(df, idx):
    if idx > 0 and df.loc[idx - 1, "Status"] == "Folga":
        return False
    if idx < len(df) - 1 and df.loc[idx + 1, "Status"] == "Folga":
        return False
    return True


def _esta_de_ferias(nome: str, data_obj: date) -> bool:
    itens = st.session_state["ferias"].get(nome, [])
    for it in itens:
        try:
            ini = datetime.strptime(it["inicio"], "%Y-%m-%d").date()
            fim = datetime.strptime(it["fim"], "%Y-%m-%d").date()
            if ini <= data_obj <= fim:
                return True
        except:
            continue
    return False


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


def _semana_seg_dom_indices(datas: pd.DatetimeIndex, idx_any: int):
    d = datas[idx_any]
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    idxs = []
    for i, dd in enumerate(datas):
        if monday.date() <= dd.date() <= sunday.date():
            idxs.append(i)
    return idxs


def _all_weeks_seg_dom(datas: pd.DatetimeIndex):
    weeks = []
    seen = set()
    for i in range(len(datas)):
        w = tuple(_semana_seg_dom_indices(datas, i))
        if w and w not in seen:
            seen.add(w)
            weeks.append(list(w))
    return weeks


def recompute_hours_with_intersticio(df, ent_padrao):
    ents, sais = [], []
    for i in range(len(df)):
        if df.loc[i, "Status"] != "Trabalho":
            ents.append("")
            sais.append("")
        else:
            e = df.loc[i, "H_Entrada"] if df.loc[i, "H_Entrada"] else ent_padrao
            if i > 0 and sais and sais[-1]:
                e = calcular_entrada_segura(sais[-1], e)
            ents.append(e)
            sais.append(_saida_from_entrada(e))
    df["H_Entrada"] = ents
    df["H_Saida"] = sais


# =========================================================
# REGRA: DOMINGO 1x1 POR COLABORADOR (APÓS ALTERAÇÃO MANUAL)
# =========================================================
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


# =========================================================
# REGRA: NÃO TRABALHAR > 5 DIAS SEGUIDOS
# =========================================================
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

    consec = 0
    i = 0
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

    recompute_hours_with_intersticio(df, ent_padrao)


# =========================================================
# REBALANCEAMENTO GLOBAL POR CATEGORIA
# =========================================================
def rebalance_folgas_categoria(historico, users_by_name, nomes_cat, weeks, max_iters=400):
    if not nomes_cat:
        return

    df_ref = historico[nomes_cat[0]]

    def is_dom(i):
        return df_ref.loc[i, "Dia"] == "dom"

    def week_counts(week_idxs):
        counts = {i: 0 for i in week_idxs if not is_dom(i)}
        for nm in nomes_cat:
            df = historico[nm]
            for i in counts.keys():
                if df.loc[i, "Status"] == "Folga":
                    counts[i] += 1
        return counts

    def can_swap(nm, i_from, i_to):
        df = historico[nm]
        u = users_by_name[nm]
        pode_sab = bool(u.get("Folga_Sab", False))

        if df.loc[i_from, "Dia"] == "dom" or df.loc[i_to, "Dia"] == "dom":
            return False
        if df.loc[i_from, "Status"] == "Férias" or df.loc[i_to, "Status"] == "Férias":
            return False
        if df.loc[i_from, "Status"] != "Folga":
            return False
        if df.loc[i_to, "Status"] != "Trabalho":
            return False
        if df.loc[i_to, "Dia"] == "sáb" and not pode_sab:
            return False
        if (i_to > 0 and df.loc[i_to - 1, "Status"] == "Folga") or (i_to < len(df) - 1 and df.loc[i_to + 1, "Status"] == "Folga"):
            return False
        return True

    def do_swap(nm, i_from, i_to):
        df = historico[nm]
        u = users_by_name[nm]
        ent_pad = u.get("Entrada", "06:00")
        pode_sab = bool(u.get("Folga_Sab", False))

        _set_trabalho(df, i_from, ent_pad)
        _set_folga(df, i_to)

        enforce_max_5_consecutive_work(df, ent_pad, pode_sab)
        historico[nm] = df

    iters = 0
    for week in weeks:
        week_idxs = [i for i in week if df_ref.loc[i, "Dia"] != "dom"]
        if not week_idxs:
            continue

        while iters < max_iters:
            iters += 1
            counts = week_counts(week_idxs)
            if not counts:
                break
            max_i = max(counts, key=lambda x: counts[x])
            min_i = min(counts, key=lambda x: counts[x])
            if counts[max_i] - counts[min_i] <= 1:
                break

            candidates = []
            for nm in nomes_cat:
                df = historico[nm]
                if df.loc[max_i, "Status"] == "Folga" and df.loc[min_i, "Status"] == "Trabalho":
                    candidates.append(nm)

            random.shuffle(candidates)
            moved = False
            for nm in candidates:
                if can_swap(nm, max_i, min_i):
                    do_swap(nm, max_i, min_i)
                    moved = True
                    break

            if not moved:
                break


# =========================================================
# GERAR ESCALA (BASE + REBALANCEAMENTO)
# =========================================================
def gerar_escala_inteligente(lista_usuarios, ano, mes):
    datas = _dias_mes(ano, mes)
    users_by_name = {u["Nome"]: u for u in lista_usuarios}

    cats = {}
    for u in lista_usuarios:
        cats.setdefault(u.get("Categoria", "Geral"), []).append(u)

    domingos_idx = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    dom_map = {}
    for cat, membros in cats.items():
        nomes_sorted = sorted([m["Nome"] for m in membros])
        seed = 9000 + ano + mes
        rng = random.Random(seed)
        nomes_sh = nomes_sorted[:]
        rng.shuffle(nomes_sh)
        meio = (len(nomes_sh) + 1) // 2
        dom_map[cat] = {"A": set(nomes_sh[:meio]), "B": set(nomes_sh[meio:])}

    novo_hist = {}

    for cat, membros in cats.items():
        for user in membros:
            nome = user["Nome"]
            ent_padrao = user.get("Entrada", "06:00")
            pode_folgar_sabado = bool(user.get("Folga_Sab", False))

            df = pd.DataFrame({
                "Data": datas,
                "Dia": [D_PT[d.day_name()] for d in datas],
                "Status": "Trabalho",
                "H_Entrada": "",
                "H_Saida": ""
            })

            for i, d in enumerate(datas):
                if _esta_de_ferias(nome, d.date()):
                    _set_ferias(df, i)

            grupo_a = dom_map[cat]["A"]
            grupo_b = dom_map[cat]["B"]
            for k, dom_i in enumerate(domingos_idx):
                if df.loc[dom_i, "Status"] == "Férias":
                    continue
                alvo_folga = grupo_a if (k % 2 == 0) else grupo_b
                if nome in alvo_folga:
                    _set_folga(df, dom_i)
                else:
                    _set_trabalho(df, dom_i, ent_padrao)

            weeks = _all_weeks_seg_dom(datas)
            for week in weeks:
                folgas = 0
                for j in week:
                    if df.loc[j, "Status"] == "Folga":
                        folgas += 1

                tries = 0
                while folgas < 2 and tries < 200:
                    tries += 1
                    cands = []
                    for j in week:
                        if df.loc[j, "Status"] != "Trabalho":
                            continue
                        dia = df.loc[j, "Dia"]
                        if dia == "dom":
                            continue
                        if dia == "sáb" and not pode_folgar_sabado:
                            continue
                        if not _nao_consecutiva_folga(df, j):
                            continue
                        cands.append(j)
                    if not cands:
                        break
                    random.shuffle(cands)
                    cands.sort(key=lambda x: 0 if df.loc[x, "Dia"] in ["seg", "ter", "qua", "qui", "sex"] else 1)
                    pick = cands[0]
                    _set_folga(df, pick)
                    folgas += 1

            enforce_max_5_consecutive_work(df, ent_padrao, pode_folgar_sabado)
            recompute_hours_with_intersticio(df, ent_padrao)

            novo_hist[nome] = df

    weeks = _all_weeks_seg_dom(datas)
    for cat, membros in cats.items():
        nomes_cat = [m["Nome"] for m in membros if m["Nome"] in novo_hist]
        rebalance_folgas_categoria(novo_hist, users_by_name, nomes_cat, weeks, max_iters=600)

    return novo_hist


# =========================================================
# INTERFACE
# =========================================================
aba1, aba2, aba3, aba4, aba5 = st.tabs(
    ["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel", "🏖️ 5. Férias"]
)

# ---------------------------------------------------------
# ABA 1
# ---------------------------------------------------------
with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome", key="cad_nome")
    ct = c2.text_input("Categoria", key="cad_cat")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time(), key="cad_ent")
    folga_sab = st.checkbox("Permitir folga no sábado (só se marcado)", key="cad_sab")

    if st.button("Salvar Funcionário", key="cad_save"):
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
# ABA 2
# ---------------------------------------------------------
with aba2:
    st.subheader("Gerar escala")
    colm1, colm2 = st.columns(2)
    mes = colm1.selectbox("Mês", list(range(1, 13)), index=st.session_state["cfg_mes"] - 1, key="gen_mes")
    ano = colm2.number_input("Ano", value=st.session_state["cfg_ano"], step=1, key="gen_ano")

    st.session_state["cfg_mes"] = int(mes)
    st.session_state["cfg_ano"] = int(ano)

    if st.button("🚀 GERAR ESCALA (balanceada)", key="gen_btn"):
        if st.session_state["db_users"]:
            st.session_state["historico"] = gerar_escala_inteligente(
                st.session_state["db_users"],
                st.session_state["cfg_ano"],
                st.session_state["cfg_mes"]
            )
            st.success("Gerado! Balanceamento aplicado.")
        else:
            st.warning("Cadastre funcionários na Aba 1.")

    if st.session_state["historico"]:
        for nome, df in st.session_state["historico"].items():
            with st.expander(f"Visualizar: {nome}"):
                st.dataframe(df, use_container_width=True)

# ---------------------------------------------------------
# ABA 3
# ---------------------------------------------------------
with aba3:
    st.subheader("⚙️ Ajustes Manuais")
    if not st.session_state["historico"]:
        st.info("Gere a escala na Aba 2.")
    else:
        f_ed = st.selectbox("Funcionário:", list(st.session_state["historico"].keys()), key="aj_func")
        df_e = st.session_state["historico"][f_ed].copy()
        user_info = next(u for u in st.session_state["db_users"] if u["Nome"] == f_ed)
        ent_padrao = user_info.get("Entrada", "06:00")
        pode_folgar_sabado = bool(user_info.get("Folga_Sab", False))

        st.markdown("### Alterar dia específico")
        col1, col2, col3 = st.columns(3)
        dia_sel = col1.number_input("Dia do mês:", 1, len(df_e), value=1, key="aj_dia")
        acao = col2.selectbox("Ação:", ["Marcar Trabalho", "Marcar Folga", "Marcar Férias", "Alterar Entrada"], key="aj_acao")
        nova_hora = col3.time_input("Nova entrada (se aplicável):", value=datetime.strptime(ent_padrao, "%H:%M").time(), key="aj_hora")

        if st.button("Aplicar", key="aj_aplicar"):
            idx = int(dia_sel) - 1
            dia_sem = df_e.loc[idx, "Dia"]
            old_status = df_e.loc[idx, "Status"]

            if acao == "Marcar Férias":
                _set_ferias(df_e, idx)

            elif acao == "Marcar Folga":
                if old_status == "Férias":
                    st.error("Não pode marcar folga sobre férias.")
                else:
                    if dia_sem == "sáb" and not pode_folgar_sabado:
                        st.error("Sábado só pode ser folga se permitir no cadastro.")
                    else:
                        _set_folga(df_e, idx)

            elif acao == "Marcar Trabalho":
                if old_status == "Férias":
                    st.error("Não pode marcar trabalho sobre férias.")
                else:
                    ent = nova_hora.strftime("%H:%M")
                    df_e.loc[idx, "H_Entrada"] = ent
                    _set_trabalho(df_e, idx, ent)

            else:  # Alterar Entrada
                if df_e.loc[idx, "Status"] != "Trabalho":
                    st.error("Só altera entrada em dia de TRABALHO.")
                else:
                    ent = nova_hora.strftime("%H:%M")
                    df_e.loc[idx, "H_Entrada"] = ent
                    df_e.loc[idx, "H_Saida"] = _saida_from_entrada(ent)

            if df_e.loc[idx, "Data"].day_name() == "Sunday":
                enforce_sundays_alternating_for_employee(df_e, ent_padrao, idx)

            enforce_max_5_consecutive_work(df_e, ent_padrao, pode_folgar_sabado)
            recompute_hours_with_intersticio(df_e, ent_padrao)

            st.session_state["historico"][f_ed] = df_e
            st.success("Aplicado!")
            st.rerun()

        st.markdown("---")
        st.dataframe(df_e, use_container_width=True)

# ---------------------------------------------------------
# ABA 4
# ---------------------------------------------------------
with aba4:
    st.subheader("📥 Excel modelo RH")
    if not st.session_state["historico"]:
        st.warning("Gere a escala na Aba 2.")
    else:
        if st.button("📊 GERAR EXCEL", key="xls_btn"):
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
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="xls_down"
            )

# ---------------------------------------------------------
# ABA 5
# ---------------------------------------------------------
with aba5:
    st.subheader("🏖️ Férias")
    if not st.session_state["db_users"]:
        st.info("Cadastre funcionários na Aba 1.")
    else:
        nomes = [u["Nome"] for u in st.session_state["db_users"]]
        nome_sel = st.selectbox("Funcionário:", nomes, key="fer_func")

        colf1, colf2 = st.columns(2)
        ini = colf1.date_input("Início", key="fer_ini")
        fim = colf2.date_input("Fim", key="fer_fim")

        if st.button("Adicionar férias", key="fer_add"):
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
