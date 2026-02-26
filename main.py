import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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

# =========================================================
# CONFIG
# =========================================================
INTERSTICIO_MIN = timedelta(hours=11, minutes=10)
DURACAO_JORNADA = timedelta(hours=9, minutes=58)  # mantém seu padrão (entrada + 9:58)

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


def _dias_mes(ano: int, mes: int):
    qtd = calendar.monthrange(ano, mes)[1]
    datas = pd.date_range(start=f"{ano}-{mes:02d}-01", periods=qtd, freq="D")
    return datas


def _semana_id_por_indice(datas, idx):
    """
    Semana definida como SEG->DOM.
    Retorna um ID de semana baseado em 'segunda' do bloco.
    """
    d = datas[idx]
    # weekday: Monday=0 ... Sunday=6
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def _indices_da_semana(datas, idx):
    """Retorna índices do bloco SEG->DOM que contém 'idx'."""
    d = datas[idx]
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    idxs = []
    for i, dd in enumerate(datas):
        if monday.date() <= dd.date() <= sunday.date():
            idxs.append(i)
    return idxs


# =========================================================
# REGRA DOMINGO 1x1 POR CATEGORIA
# - Para categoria com 2+ pessoas: 1 folga por domingo, revezando
# - Para categoria com 1 pessoa: folga domingo sim / não
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
            elif n == 1:
                # alterna domingo sim/não
                rodizio[cat][dom_i] = {nomes[0]} if (k % 2 == 0) else set()
            else:
                # 1 por 1: 1 folga por domingo, revezando
                escolhido = nomes[k % n]
                rodizio[cat][dom_i] = {escolhido}

    return rodizio


# =========================================================
# GERAR ESCALA (REGRAS SOLICITADAS)
# - Semana SEG->DOM
# - 5x2 por semana (2 folgas)
# - Domingo 1x1 por categoria
# - Sábado só pode ser folga se checkbox "Folga no sábado" marcado
# - Folgas aleatórias sem consecutivas
# =========================================================
def gerar_escala_inteligente(lista_usuarios, ano, mes):
    datas = _dias_mes(ano, mes)

    # agrupa por categoria
    cats = {}
    for u in lista_usuarios:
        c = u.get("Categoria", "Geral")
        cats.setdefault(c, []).append(u)

    # rodízio de domingo por categoria (1 folga por domingo)
    rod_dom = montar_rodizio_domingo_por_categoria(cats, datas)

    # contador de folgas por categoria/dia (balanceamento 50%)
    cont_folga_cat_dia = {cat: {i: 0 for i in range(len(datas))} for cat in cats.keys()}

    novo_hist = {}

    for cat, membros in cats.items():
        total_cat = len(membros)

        # embaralha para variar os sorteios
        random.shuffle(membros)

        for user in membros:
            nome = user["Nome"]
            entrada_padrao = user.get("Entrada", "06:00")
            pode_folgar_sabado = bool(user.get("Folga_Sab", False))  # <<< sua caixinha
            # (se quiser manter o nome antigo Rod_Sab, pode mapear na UI)

            df = pd.DataFrame({
                "Data": datas,
                "Dia": [D_PT[d.day_name()] for d in datas],
                "Status": "Trabalho"
            })

            # aplica domingo 1x1 (conta como folga dentro da semana)
            for dom_i, set_folga in rod_dom[cat].items():
                if nome in set_folga:
                    df.loc[dom_i, "Status"] = "Folga"
                    cont_folga_cat_dia[cat][dom_i] += 1

            # Agora fecha 5x2 semana SEG->DOM
            # Para cada semana, garantir exatamente 2 folgas
            semanas_ids = sorted(list({_semana_id_por_indice(datas, i) for i in range(len(datas))}))

            for sem_id in semanas_ids:
                # pega índices desta semana dentro do mês
                # sem_id é a data da segunda-feira
                monday = datetime.strptime(sem_id, "%Y-%m-%d")
                sunday = monday + timedelta(days=6)

                idxs = [i for i, d in enumerate(datas) if monday.date() <= d.date() <= sunday.date()]
                if not idxs:
                    continue

                # folgas já existentes na semana (por causa do domingo 1x1)
                folgas_semana = int((df.loc[idxs, "Status"] == "Folga").sum())

                # precisamos completar até 2
                # Observação: as folgas devem ser aleatórias, sem consecutivas,
                # sábado só entra se pode_folgar_sabado
                while folgas_semana < 2:
                    possiveis = []

                    for j in idxs:
                        if df.loc[j, "Status"] != "Trabalho":
                            continue

                        dia = df.loc[j, "Dia"]

                        # sábado só pode ser folga se marcado
                        if dia == "sáb" and not pode_folgar_sabado:
                            continue

                        # não permitir folga consecutiva
                        if not _nao_consecutiva(df, j):
                            continue

                        # balanceamento 50% por categoria/dia
                        # (não deixa metade+ folgar no mesmo dia)
                        if total_cat > 1:
                            limite = max(1, total_cat // 2)
                            if cont_folga_cat_dia[cat][j] >= limite:
                                continue

                        possiveis.append(j)

                    if not possiveis:
                        # relaxa balanceamento se for impossível (ainda respeita sábado e sem consecutivas)
                        for j in idxs:
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

                # garantia extra: não ter mais de 5 dias seguidos trabalhando na semana
                # (com 2 folgas sem consecutivas, normalmente já garante, mas vamos checar)
                consec = 0
                for j in idxs:
                    if df.loc[j, "Status"] == "Trabalho":
                        consec += 1
                        if consec > 5:
                            # tenta virar este dia em folga se permitido
                            dia = df.loc[j, "Dia"]
                            if dia != "sáb" or pode_folgar_sabado:
                                if _nao_consecutiva(df, j):
                                    df.loc[j, "Status"] = "Folga"
                                    cont_folga_cat_dia[cat][j] += 1
                                    consec = 0
                    else:
                        consec = 0

            # horários com interstício
            ents, sais = [], []
            for i in range(len(df)):
                if df.loc[i, "Status"] == "Folga":
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
aba1, aba2, aba3, aba4 = st.tabs(
    ["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"]
)

with aba1:
    st.subheader("Cadastro")

    c1, c2 = st.columns(2)
    n = c1.text_input("Nome")
    ct = c2.text_input("Categoria")

    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())

    # sua regra: sábado só pode virar folga se marcar
    folga_sab = st.checkbox("Folga no sábado (permitir escolher sábado como folga)")

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


with aba2:
    st.subheader("Configurar mês/ano")
    colm1, colm2 = st.columns(2)
    mes = colm1.selectbox("Mês", list(range(1, 13)), index=st.session_state["cfg_mes"] - 1)
    ano = colm2.number_input("Ano", value=st.session_state["cfg_ano"], step=1)

    st.session_state["cfg_mes"] = mes
    st.session_state["cfg_ano"] = int(ano)

    if st.button("🚀 GERAR ESCALA (5x2 + Domingo 1x1 + Sábado restrito)"):
        if st.session_state["db_users"]:
            st.session_state["historico"] = gerar_escala_inteligente(
                st.session_state["db_users"],
                int(ano),
                int(mes)
            )
            st.success("Escala gerada conforme regras!")
        else:
            st.warning("Cadastre os funcionários na Aba 1.")

    if st.session_state["historico"]:
        for nome, df in st.session_state["historico"].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df, use_container_width=True)


with aba3:
    st.subheader("⚙️ Ajustes Manuais (básico)")

    if st.session_state["historico"]:
        f_ed = st.selectbox(
            "Selecione o Funcionário:",
            list(st.session_state["historico"].keys())
        )
        df_e = st.session_state["historico"][f_ed]
        st.dataframe(df_e, use_container_width=True)
    else:
        st.info("Gere a escala na Aba 2.")


with aba4:
    st.subheader("📥 Exportar para Excel (formato igual sua imagem)")

    if st.session_state["historico"]:
        if st.button("📊 GERAR EXCEL (MODELO RH)"):
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Mensal", index=0)

                # Estilos
                fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", patternType="solid")  # azul
                fill_dom = PatternFill(start_color="C00000", end_color="C00000", patternType="solid")     # vermelho
                fill_folga = PatternFill(start_color="FFF2CC", end_color="FFF2CC", patternType="solid")   # amarelo
                fill_nome = PatternFill(start_color="D9E1F2", end_color="D9E1F2", patternType="solid")    # azul claro

                font_header = Font(color="FFFFFF", bold=True)
                font_dom = Font(color="FFFFFF", bold=True)

                border = Border(
                    left=Side(style="thin"),
                    right=Side(style="thin"),
                    top=Side(style="thin"),
                    bottom=Side(style="thin")
                )
                center = Alignment(horizontal="center", vertical="center", wrap_text=True)

                df_ref = list(st.session_state["historico"].values())[0]
                total_dias = len(df_ref)

                # Cabeçalho: COLABORADOR + dias
                ws.cell(1, 1, "COLABORADOR").fill = fill_header
                ws.cell(1, 1).font = font_header
                ws.cell(1, 1).alignment = center
                ws.cell(1, 1).border = border

                ws.cell(2, 1, "").fill = fill_header
                ws.cell(2, 1).alignment = center
                ws.cell(2, 1).border = border

                for i in range(total_dias):
                    dia_num = df_ref.iloc[i]["Data"].day
                    dia_sem = df_ref.iloc[i]["Dia"]  # dom/seg/...

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

                # Linhas: 2 por colaborador (entrada e saída)
                row_idx = 3
                for nome, df_f in st.session_state["historico"].items():
                    # Nome mesclado em 2 linhas
                    c_nome = ws.cell(row_idx, 1, nome)
                    c_nome.fill = fill_nome
                    c_nome.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                    c_nome.border = border
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx + 1, end_column=1)

                    ws.row_dimensions[row_idx].height = 18
                    ws.row_dimensions[row_idx + 1].height = 18

                    for i, row in df_f.iterrows():
                        dia_sem = row["Dia"]
                        folga = (row["Status"] == "Folga")

                        v1 = "F" if folga else row["H_Entrada"]
                        v2 = "" if folga else row["H_Saida"]

                        cell1 = ws.cell(row_idx, i + 2, v1)
                        cell2 = ws.cell(row_idx + 1, i + 2, v2)

                        cell1.alignment = center
                        cell2.alignment = center
                        cell1.border = border
                        cell2.border = border

                        if folga:
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

                # Remove sheet padrão se existir
                if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
                    wb.remove(wb["Sheet"])

            st.download_button(
                label="📥 Baixar Escala (Excel modelo RH)",
                data=output.getvalue(),
                file_name=f"escala_5x2_modelo_RH_{st.session_state['cfg_mes']:02d}_{st.session_state['cfg_ano']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.warning("Gere a escala na Aba 2 para liberar o Excel.")
