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
# Construir DOMINGO 1x1 (padrão)
# - dividido em dois grupos A/B, alterna por domingo (A folga no domingo 1, B folga no domingo 2, ...)
# - a função retorna um dict: {categoria: {indice_domingo: set(nomes que folgam neste domingo)}}
# =========================================================
def montar_domingo_1x1_por_categoria(cats, datas, seed_base=None):
    domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    esquema = {cat: {} for cat in cats.keys()}

    for cat, membros in cats.items():
        nomes = sorted([u["Nome"] for u in membros])

        # se não tem ninguém
        if not nomes:
            for dom_i in domingos:
                esquema[cat][dom_i] = set()
            continue

        # se tem 1 pessoa: alterna sim/não
        if len(nomes) == 1:
            nome = nomes[0]
            for k, dom_i in enumerate(domingos):
                data_dom = datas[dom_i].date()
                if _esta_de_ferias(nome, data_dom):
                    esquema[cat][dom_i] = set()
                else:
                    esquema[cat][dom_i] = {nome} if (k % 2 == 0) else set()
            continue

        # 2+ pessoas -> dividir em 2 grupos equilibrados
        rng = random.Random(42 + (seed_base or 0) + datas[0].month + datas[0].year)
        nomes_mix = nomes[:]
        rng.shuffle(nomes_mix)

        meio = (len(nomes_mix) + 1) // 2
        grupo_a = set(nomes_mix[:meio])
        grupo_b = set(nomes_mix[meio:])

        for k, dom_i in enumerate(domingos):
            data_dom = datas[dom_i].date()
            alvo = grupo_a if (k % 2 == 0) else grupo_b
            folgam = set(nm for nm in alvo if not _esta_de_ferias(nm, data_dom))
            esquema[cat][dom_i] = folgam

    return esquema


# =========================================================
# Quando o usuário altera manualmente um domingo para um funcionário,
# ancoramos a alternância naquele domingo: construímos grupos A/B de forma que
# o funcionário modificado pertença ao grupo que folga nesse domingo (se marcou folga).
# Depois aplicamos alternância para todos os domingos do mês (respeitando férias).
# =========================================================
def enforce_domingo_1x1_anchor(historico, db_users, nome_modificado, dom_index, ano, mes):
    """
    historico: dict nome->df (escala atual)
    db_users: lista de dicts com 'Nome' e 'Categoria'
    nome_modificado: nome da pessoa que foi alterada manualmente
    dom_index: índice do dia (0-based) que é domingo e foi alterado
    ano, mes: para gerar datas consistentes
    """
    # datas do mês usado na geração atual (todas escalas usam mesmo mês)
    datas = _dias_mes(ano, mes)

    # identificar categoria do nome_modificado
    user_info = next((u for u in db_users if u["Nome"] == nome_modificado), None)
    if not user_info:
        return
    cat = user_info["Categoria"]

    # obter membros desta categoria
    membros = [u["Nome"] for u in db_users if u["Categoria"] == cat]
    if not membros:
        return

    membros = sorted(membros)

    # construir lista de indices dos domingos do mês (na ordem)
    domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
    if dom_index not in domingos:
        return

    # posição do dom_index na lista de domingos: k_dom
    k_dom = domingos.index(dom_index)

    # decidir parity (k) para formar grupos A/B tal que nome_modificado esteja no grupo que folga neste domingo
    pos = membros.index(nome_modificado) if nome_modificado in membros else 0
    # We'll choose parity = pos % 2 so that nome_modificado falls into groupA defined by parity.
    parity = pos % 2

    # definir grupos A/B por parity: grupoA = nomes where (pos % 2) == parity
    grupo_a = set([nm for idx, nm in enumerate(membros) if (idx % 2) == parity])
    grupo_b = set([nm for idx, nm in enumerate(membros) if (idx % 2) != parity])

    # Agora aplicar alternância dos domingos: k=0 -> grupoA folga, k=1 -> grupoB folga, etc.
    for k, dom_i in enumerate(domingos):
        data_dom = datas[dom_i].date()
        # folga_atual_para = grupo_a if (k % 2 == 0) else grupo_b
        folga_para = grupo_a if (k % 2 == 0) else grupo_b

        for nm in membros:
            df_nm = historico.get(nm)
            if df_nm is None:
                continue
            # Respeita férias: se nm estiver de férias, mantém Férias
            if _esta_de_ferias(nm, data_dom):
                df_nm.loc[dom_i, "Status"] = "Férias"
                continue
            # Aplica folga/trabalho conforme folga_para (forçando Trabalho no contrario)
            if nm in folga_para:
                df_nm.loc[dom_i, "Status"] = "Folga"
            else:
                df_nm.loc[dom_i, "Status"] = "Trabalho"

    # atualiza prefira alterar também contagens etc. Depois de enforce, precisamos
    # recalcular horários H_Entrada/H_Saida para todos os membros da categoria (ou para todos)
    for nm in membros:
        df_nm = historico.get(nm)
        if df_nm is None:
            continue
        # recalcular horários simples: se Trabalho -> manter entrada existente se presente,
        # ou usar db_users entrada padrao; se Folga/Férias -> esvaziar horários.
        uinfo = next((u for u in db_users if u["Nome"] == nm), None)
        padrao = uinfo.get("Entrada", "06:00") if uinfo else "06:00"
        ents, sais = [], []
        for i in range(len(df_nm)):
            status = df_nm.loc[i, "Status"]
            if status in ["Folga", "Férias"]:
                ents.append("")
                sais.append("")
            else:
                # tentar manter entrada anterior se já havia (não sobrescreve manualmente definidos)
                prev_ent = df_nm.loc[i, "H_Entrada"] if "H_Entrada" in df_nm.columns else ""
                if prev_ent and prev_ent != "":
                    e = prev_ent
                else:
                    # garantir intersticio relativo ao dia anterior (usa ultima saida calculada)
                    if ents and sais and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], padrao)
                    else:
                        e = padrao
                ents.append(e)
                sais.append((datetime.strptime(e, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M"))
        df_nm["H_Entrada"] = ents
        df_nm["H_Saida"] = sais

    # escreve de volta no historico (mutação in-place suficiente)
    return


# =========================================================
# Função auxiliar para escolher dia balanceado (semana)
# =========================================================
def escolher_dia_balanceado(possiveis, cont_semana_cat):
    if not possiveis:
        return None
    random.shuffle(possiveis)
    possiveis.sort(key=lambda j: cont_semana_cat.get(j, 0))
    return possiveis[0]


# =========================================================
# Função principal de geração (mantida)
# =========================================================
def gerar_escala_inteligente(lista_usuarios, ano, mes):
    datas = _dias_mes(ano, mes)

    # agrupar por categoria
    cats = {}
    for u in lista_usuarios:
        c = u.get("Categoria", "Geral")
        cats.setdefault(c, []).append(u)

    # Domingo 1x1 padrão
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

            # 2) Aplicar dom 1x1 padrão (forçando Trabalho para quem não é do grupo de folga)
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

            # 3) semanas do mês
            semanas = []
            seen = set()
            for i in range(len(datas)):
                idxs = tuple(_semana_seg_dom(datas, i))
                if idxs and idxs not in seen:
                    seen.add(idxs)
                    semanas.append(list(idxs))

            # 4) aplicar 5x2 por semana (exceto semana de retorno)
            for idxs in semanas:
                monday_week = _monday_of(datas[idxs[0]].date())

                if monday_week in semanas_skip_5x2:
                    continue

                idxs_nao_ferias = [j for j in idxs if df.loc[j, "Status"] != "Férias"]
                if not idxs_nao_ferias:
                    continue

                cont_semana_cat = {j: 0 for j in idxs}
                for j in idxs:
                    if df.loc[j, "Status"] == "Folga":
                        cont_semana_cat[j] += 1

                folgas_semana = int((df.loc[idxs_nao_ferias, "Status"] == "Folga").sum())

                while folgas_semana < 2:
                    possiveis = []
                    for j in idxs_nao_ferias:
                        if df.loc[j, "Status"] != "Trabalho":
                            continue

                        dia = df.loc[j, "Dia"]
                        if dia == "sáb" and not pode_folgar_sabado:
                            continue
                        if not _nao_consecutiva(df, j):
                            continue
                        if total_cat > 1:
                            limite = max(1, total_cat // 2)
                            if cont_folga_cat_dia[cat][j] >= limite:
                                continue
                        possiveis.append(j)

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

                # segurança: max 5 dias seguidos
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

            # 5) horários
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
# ABA 3 - AJUSTES (inclui enforce DOM manual)
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
            st.markdown("#### 🔄 Trocar Folga")
            folgas_atuais = df_e[df_e["Status"] == "Folga"].index.tolist()
            d_tira = st.selectbox("Dia para TRABALHAR (remover folga):", [d + 1 for d in folgas_atuais]) if folgas_atuais else None
            d_poe = st.number_input("Novo dia para FOLGAR:", 1, len(df_e), value=1, key="aj_folga_poe")

            if st.button("Confirmar troca", key="btn_troca_folga"):
                if d_tira is None:
                    st.warning("Sem folgas para trocar.")
                elif df_e.loc[d_poe - 1, "Status"] == "Férias" or df_e.loc[d_tira - 1, "Status"] == "Férias":
                    st.error("Não pode trocar dias de FÉRIAS.")
                else:
                    # aplica troca simples
                    df_e.loc[d_tira - 1, "Status"] = "Trabalho"
                    df_e.loc[d_poe - 1, "Status"] = "Folga"
                    df_e.loc[d_poe - 1, "H_Entrada"] = ""
                    df_e.loc[d_poe - 1, "H_Saida"] = ""
                    st.session_state["historico"][f_ed] = df_e

                    # se o dia alterado é DOMINGO, força regra 1x1 ancorada nesse domingo
                    if df_e.loc[d_poe - 1, "Dia"] == "dom":
                        # dom_index é 0-based
                        dom_index = d_poe - 1
                        enforce_domingo_1x1_anchor(
                            st.session_state["historico"],
                            st.session_state["db_users"],
                            f_ed,
                            dom_index,
                            st.session_state["cfg_ano"],
                            st.session_state["cfg_mes"]
                        )
                    st.success("Troca aplicada! (Se domingo, apliquei regra 1x1 ancorada.)")
                    st.rerun()

        with col_b:
            st.markdown("#### 🕒 Trocar Horário")
            dia_h = st.number_input("Dia:", 1, len(df_e), value=1, key="aj_dia_h")
            hora_h = st.time_input("Nova entrada:", key="aj_hora_h")
            if st.button("Salvar horário", key="btn_salvar_hora"):
                if df_e.loc[dia_h - 1, "Status"] != "Trabalho":
                    st.warning("Dia não está como TRABALHO.")
                else:
                    ent = hora_h.strftime("%H:%M")
                    sai = (datetime.strptime(ent, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
                    df_e.loc[dia_h - 1, "H_Entrada"] = ent
                    df_e.loc[dia_h - 1, "H_Saida"] = sai
                    st.session_state["historico"][f_ed] = df_e
                    st.success("Horário alterado!")
                    st.rerun()

        with col_c:
            st.markdown("#### 🧩 Trocar Categoria")
            categorias = sorted(list(set(u["Categoria"] for u in st.session_state["db_users"])))
            idx = categorias.index(user_info["Categoria"]) if user_info["Categoria"] in categorias else 0
            nova_cat = st.selectbox("Nova categoria:", categorias, index=idx)
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
