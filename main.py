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
    # formato: {"Nome": [{"inicio": "YYYY-MM-DD", "fim": "YYYY-MM-DD"}, ...]}
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
    """Garante interstício mínimo 11h10 entre saída anterior e entrada do dia."""
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
    """Não permite folgas consecutivas (idx-1 ou idx+1)."""
    if idx > 0 and df.loc[idx - 1, "Status"] == "Folga":
        return False
    if idx < len(df) - 1 and df.loc[idx + 1, "Status"] == "Folga":
        return False
    return True


def _semana_seg_dom(datas, i):
    """Retorna indices da semana SEG->DOM que contém o índice i."""
    d = datas[i]
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    idxs = []
    for k, dd in enumerate(datas):
        if monday.date() <= dd.date() <= sunday.date():
            idxs.append(k)
    return idxs


def _monday_of(d: date) -> date:
    """Segunda-feira da semana (SEG->DOM) de uma data."""
    return d - timedelta(days=d.weekday())


def _intervalo_ferias_do_nome(nome: str):
    """Retorna lista de intervalos (date, date) das férias do colaborador."""
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
    """
    NOVA REGRA:
    - Semana SEG->DOM da volta de férias: NÃO aplica 5x2, só domingo 1x1.
    Retorna um set com as segundas-feiras (date) das semanas a pular 5x2.
    """
    semanas_skip = set()
    for ini, fim in _intervalo_ferias_do_nome(nome):
        retorno = fim + timedelta(days=1)
        semanas_skip.add(_monday_of(retorno))
    return semanas_skip


# =========================================================
# DOMINGO 1x1 POR CATEGORIA
#  - categoria com 2+ pessoas: 1 folga por domingo, revezando
#  - categoria com 1 pessoa: alterna sim/não
#  - férias: se o escolhido do domingo estiver de férias, passa para o próximo
# =========================================================
def montar_rodizio_domingo_por_categoria(cats, datas):
    domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    rodizio = {cat: {} for cat in cats.keys()}

    for cat, membros in cats.items():
        nomes = [u["Nome"] for u in membros]
        n = len(nomes)

        for k, dom_i in enumerate(domingos):
            if n == 0:
                rodizio[cat][dom_i] = set()
                continue

            data_dom = datas[dom_i].date()

            if n == 1:
                nome = nomes[0]
                # alterna, mas se estiver de férias não marca folga
                if (k % 2 == 0) and (not _esta_de_ferias(nome, data_dom)):
                    rodizio[cat][dom_i] = {nome}
                else:
                    rodizio[cat][dom_i] = set()
                continue

            # n >= 2 : 1 por 1 (1 folga por domingo)
            tentativas = 0
            escolhido_idx = k % n

            while tentativas < n:
                nome_escolhido = nomes[escolhido_idx]
                if not _esta_de_ferias(nome_escolhido, data_dom):
                    rodizio[cat][dom_i] = {nome_escolhido}
                    break
                escolhido_idx = (escolhido_idx + 1) % n
                tentativas += 1
            else:
                rodizio[cat][dom_i] = set()

    return rodizio


# =========================================================
# GERAR ESCALA (REGRAS + FÉRIAS + NOVA REGRA RETORNO)
# - Semana SEG->DOM
# - 5x2 por semana (2 folgas) sem consecutivas (exceto férias)
# - Domingo 1x1 por categoria
# - Sábado só pode virar folga se checkbox marcado
# - Balanceamento 50% por categoria/dia (exceto quando impossível)
# - Férias aplicadas automaticamente (prioridade)
# - NOVO: semana da volta de férias NÃO aplica 5x2 (só domingo 1x1)
# =========================================================
def gerar_escala_inteligente(lista_usuarios, ano, mes):
    datas = _dias_mes(ano, mes)

    # agrupar por categoria
    cats = {}
    for u in lista_usuarios:
        c = u.get("Categoria", "Geral")
        cats.setdefault(c, []).append(u)

    # rodízio domingo por categoria (respeitando férias)
    rod_dom = montar_rodizio_domingo_por_categoria(cats, datas)

    # contador folgas por categoria/dia (balanceamento 50%)
    cont_folga_cat_dia = {cat: {i: 0 for i in range(len(datas))} for cat in cats.keys()}

    novo_hist = {}

    for cat, membros in cats.items():
        total_cat = len(membros)
        random.shuffle(membros)

        for user in membros:
            nome = user["Nome"]
            entrada_padrao = user.get("Entrada", "06:00")
            pode_folgar_sabado = bool(user.get("Folga_Sab", False))

            # semanas para pular 5x2 (semana da volta de férias)
            semanas_skip_5x2 = _semanas_para_pular_5x2_por_retorno(nome)

            df = pd.DataFrame({
                "Data": datas,
                "Dia": [D_PT[d.day_name()] for d in datas],
                "Status": "Trabalho"
            })

            # 1) aplica férias primeiro
            for i, d in enumerate(datas):
                if _esta_de_ferias(nome, d.date()):
                    df.loc[i, "Status"] = "Férias"

            # 2) aplica domingo 1x1 (se não estiver de férias)
            for dom_i, set_folga in rod_dom[cat].items():
                if df.loc[dom_i, "Status"] == "Férias":
                    continue
                if nome in set_folga:
                    df.loc[dom_i, "Status"] = "Folga"
                    cont_folga_cat_dia[cat][dom_i] += 1

            # 3) montar lista única de semanas (SEG->DOM)
            semanas = []
            seen = set()
            for i in range(len(datas)):
                idxs = tuple(_semana_seg_dom(datas, i))
                if idxs and idxs not in seen:
                    seen.add(idxs)
                    semanas.append(list(idxs))

            for idxs in semanas:
                # semana "monday" para comparar com skip
                monday_week = _monday_of(datas[idxs[0]].date())

                # ✅ NOVA REGRA:
                # Se esta é a semana da volta de férias, NÃO aplicar 5x2
                # (mantém o que já existe: férias + domingo 1x1)
                if monday_week in semanas_skip_5x2:
                    continue

                # Dias elegíveis (não férias)
                idxs_nao_ferias = [j for j in idxs if df.loc[j, "Status"] != "Férias"]
                if not idxs_nao_ferias:
                    continue

                folgas_semana = int((df.loc[idxs_nao_ferias, "Status"] == "Folga").sum())

                # completa até 2 folgas na semana
                while folgas_semana < 2:
                    possiveis = []

                    for j in idxs_nao_ferias:
                        if df.loc[j, "Status"] != "Trabalho":
                            continue

                        dia = df.loc[j, "Dia"]

                        # sábado só vira folga se marcado
                        if dia == "sáb" and not pode_folgar_sabado:
                            continue

                        # evitar folga consecutiva
                        if not _nao_consecutiva(df, j):
                            continue

                        # balanceamento 50%
                        if total_cat > 1:
                            limite = max(1, total_cat // 2)
                            if cont_folga_cat_dia[cat][j] >= limite:
                                continue

                        possiveis.append(j)

                    if not possiveis:
                        # relaxa balanceamento se impossível (mantém sábado e não consecutiva)
                        for j in idxs_nao_ferias:
                            if df.loc[j, "Status"] != "Trabalho":
                                continue
                            dia = df.loc[j, "Dia"]
                            if dia == "sáb" and not pode_folgar_sabado:
                                continue
                            if not _nao_consecutiva(df, j):
                                continue
                            possiveis.append(j)

                    if not possiveis:
                        break

                    escolhido = random.choice(possiveis)
                    df.loc[escolhido, "Status"] = "Folga"
                    cont_folga_cat_dia[cat][escolhido] += 1
                    folgas_semana += 1

                # (mantém sua segurança de sequência >5 fora da semana de retorno)
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

            # 4) horários com interstício
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
            st.success(f"{n} cadastrado com sucesso!")
        else:
            st.error("Preencha Nome e Categoria.")

    if st.session_state["db_users"]:
        st.markdown("### Funcionários cadastrados")
        st.dataframe(pd.DataFrame(st.session_state["db_users"]), use_container_width=True)


# ---------------------------------------------------------
# ABA 2 - GERAR ESCALA
# ---------------------------------------------------------
with aba2:
    st.subheader("Configurar mês/ano")

    colm1, colm2 = st.columns(2)
    mes = colm1.selectbox("Mês", list(range(1, 13)), index=st.session_state["cfg_mes"] - 1)
    ano = colm2.number_input("Ano", value=st.session_state["cfg_ano"], step=1)

    st.session_state["cfg_mes"] = int(mes)
    st.session_state["cfg_ano"] = int(ano)

    if st.button("🚀 GERAR ESCALA (Regras completas + Férias + Retorno)"):
        if st.session_state["db_users"]:
            st.session_state["historico"] = gerar_escala_inteligente(
                st.session_state["db_users"],
                st.session_state["cfg_ano"],
                st.session_state["cfg_mes"]
            )
            st.success("Escala gerada! (Semana de retorno: só domingo 1x1; depois volta 5x2 SEG→DOM)")
        else:
            st.warning("Cadastre os funcionários na Aba 1.")

    if st.session_state["historico"]:
        for nome, df in st.session_state["historico"].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df, use_container_width=True)


# ---------------------------------------------------------
# ABA 3 - AJUSTES COMPLETA
# ---------------------------------------------------------
with aba3:
    st.subheader("⚙️ Ajustes Manuais (Trocar folga / horário / categoria / sábado)")

    if not st.session_state["historico"]:
        st.info("Gere a escala na Aba 2 para liberar os ajustes.")
    else:
        f_ed = st.selectbox("Selecione o Funcionário:", list(st.session_state["historico"].keys()))
        df_e = st.session_state["historico"][f_ed]
        user_info = next(u for u in st.session_state["db_users"] if u["Nome"] == f_ed)

        col_a, col_b, col_c, col_d = st.columns(4)

        with col_a:
            st.markdown("#### 🔄 Trocar Folga")
            folgas_atuais = df_e[df_e["Status"] == "Folga"].index.tolist()
            if folgas_atuais:
                d_tira = st.selectbox("Dia que vai TRABALHAR:", [d + 1 for d in folgas_atuais])
            else:
                d_tira = None
                st.info("Sem folgas para remover.")
            d_poe = st.number_input("Novo dia para FOLGAR:", 1, len(df_e), value=1, key="troca_folga_dpoe")

            if st.button("Confirmar troca", key="btn_troca_folga"):
                if d_tira is None:
                    st.warning("Não existe folga para remover.")
                else:
                    if df_e.loc[d_poe - 1, "Status"] == "Férias" or df_e.loc[d_tira - 1, "Status"] == "Férias":
                        st.error("Não é permitido trocar dias marcados como FÉRIAS.")
                    else:
                        df_e.loc[d_tira - 1, "Status"] = "Trabalho"
                        df_e.loc[d_poe - 1, "Status"] = "Folga"
                        df_e.loc[d_poe - 1, "H_Entrada"] = ""
                        df_e.loc[d_poe - 1, "H_Saida"] = ""
                        st.session_state["historico"][f_ed] = df_e
                        st.success("Troca aplicada!")
                        st.rerun()

        with col_b:
            st.markdown("#### 🕒 Trocar Horário")
            dia_h = st.number_input("Dia do mês:", 1, len(df_e), value=1, key="aj_h_dia")
            hora_h = st.time_input("Nova Entrada:", key="aj_h_entrada")

            if st.button("Salvar horário", key="btn_salvar_horario"):
                if df_e.loc[dia_h - 1, "Status"] != "Trabalho":
                    st.warning("Esse dia não está como TRABALHO (Folga/Férias).")
                else:
                    entrada_nova = hora_h.strftime("%H:%M")
                    saida_calc = (datetime.strptime(entrada_nova, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
                    df_e.loc[dia_h - 1, "H_Entrada"] = entrada_nova
                    df_e.loc[dia_h - 1, "H_Saida"] = saida_calc
                    st.session_state["historico"][f_ed] = df_e
                    st.success("Horário alterado!")
                    st.rerun()

        with col_c:
            st.markdown("#### 🧩 Trocar Categoria")
            categorias = sorted(list(set(u["Categoria"] for u in st.session_state["db_users"])))
            idx = categorias.index(user_info["Categoria"]) if user_info["Categoria"] in categorias else 0
            nova_cat = st.selectbox("Nova categoria:", categorias, index=idx)

            if st.button("Salvar categoria", key="btn_salvar_cat"):
                user_info["Categoria"] = nova_cat
                st.success("Categoria atualizada! (Gere novamente para refletir.)")

        with col_d:
            st.markdown("#### 🗓️ Sábado")
            novo_flag = st.checkbox("Permitir folga no sábado", value=bool(user_info.get("Folga_Sab", False)), key="chk_sab")
            if st.button("Salvar sábado", key="btn_salvar_sab"):
                user_info["Folga_Sab"] = bool(novo_flag)
                st.success("Sábado atualizado! (Gere novamente para refletir.)")

        st.markdown("---")
        st.dataframe(df_e, use_container_width=True)


# ---------------------------------------------------------
# ABA 4 - EXPORTAR EXCEL (MODELO RH)
# ---------------------------------------------------------
with aba4:
    st.subheader("📥 Exportar para Excel (formato igual sua imagem)")

    if not st.session_state["historico"]:
        st.warning("Gere a escala na Aba 2 para liberar o Excel.")
    else:
        if st.button("📊 GERAR EXCEL (MODELO RH)"):
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

                border = Border(
                    left=Side(style="thin"),
                    right=Side(style="thin"),
                    top=Side(style="thin"),
                    bottom=Side(style="thin")
                )
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
                        c1.fill = fill_dom
                        c2.fill = fill_dom
                        c1.font = font_dom
                        c2.font = font_dom
                    else:
                        c1.fill = fill_header
                        c2.fill = fill_header
                        c1.font = font_header
                        c2.font = font_header

                    c1.alignment = center
                    c2.alignment = center
                    c1.border = border
                    c2.border = border

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

                        cell1.alignment = center
                        cell2.alignment = center
                        cell1.border = border
                        cell2.border = border

                        if status == "Férias":
                            cell1.fill = fill_ferias
                            cell2.fill = fill_ferias
                            cell1.font = font_ferias
                        elif status == "Folga":
                            if dia_sem == "dom":
                                cell1.fill = fill_dom
                                cell2.fill = fill_dom
                                cell1.font = font_dom
                                cell2.font = font_dom
                            else:
                                cell1.fill = fill_folga
                                cell2.fill = fill_folga
                                cell1.font = Font(bold=True)

                    row_idx += 2

                if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
                    wb.remove(wb["Sheet"])

            st.download_button(
                label="📥 Baixar Escala (Excel modelo RH)",
                data=output.getvalue(),
                file_name=f"escala_5x2_modelo_RH_{st.session_state['cfg_mes']:02d}_{st.session_state['cfg_ano']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# ---------------------------------------------------------
# ABA 5 - FÉRIAS (CADASTRAR)
# ---------------------------------------------------------
with aba5:
    st.subheader("🏖️ Férias (cadastrar e aplicar automático na escala)")

    if not st.session_state["db_users"]:
        st.info("Cadastre funcionários na Aba 1 antes de lançar férias.")
    else:
        nomes = [u["Nome"] for u in st.session_state["db_users"]]
        nome_sel = st.selectbox("Funcionário:", nomes)

        colf1, colf2 = st.columns(2)
        ini = colf1.date_input("Início das férias")
        fim = colf2.date_input("Fim das férias")

        if st.button("Adicionar férias"):
            if fim < ini:
                st.error("A data final não pode ser menor que a inicial.")
            else:
                st.session_state["ferias"].setdefault(nome_sel, []).append({
                    "inicio": ini.strftime("%Y-%m-%d"),
                    "fim": fim.strftime("%Y-%m-%d")
                })
                st.success("Férias adicionadas! Gere a escala novamente para aplicar.")

        st.markdown("---")
        st.markdown("### 📋 Férias cadastradas")
        view = []
        for nome, intervalos in st.session_state["ferias"].items():
            for it in intervalos:
                view.append({"Nome": nome, "Início": it["inicio"], "Fim": it["fim"]})
        if view:
            st.dataframe(pd.DataFrame(view), use_container_width=True)
        else:
            st.info("Nenhuma férias cadastrada ainda.")

        st.info("Regra de retorno: a semana da volta não aplica 5x2, só a regra do DOMINGO 1x1. Da próxima semana em diante, volta 5x2 normal.")
