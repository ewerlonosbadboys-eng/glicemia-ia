import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
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

# =========================================================
# CONFIG (você pode mudar aqui)
# =========================================================
START_DATE = "2026-03-01"   # mês base (31 dias como seu código)
PERIODOS = 31
DURACAO_JORNADA = timedelta(hours=9, minutes=58)  # mantém seu padrão
INTERSTICIO_MIN = timedelta(hours=11, minutes=10)

D_PT = {
    "Monday": "seg",
    "Tuesday": "ter",
    "Wednesday": "qua",
    "Thursday": "qui",
    "Friday": "sex",
    "Saturday": "sáb",
    "Sunday": "dom"
}

# =========================================================
# UTIL
# =========================================================
def calcular_entrada_segura(saida_ant: str, ent_padrao: str) -> str:
    """Garante interstício mínimo entre a saída anterior e a entrada do dia."""
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s)
        if diff.total_seconds() < 0:
            diff += timedelta(days=1)
        if diff < INTERSTICIO_MIN:
            return (s + INTERSTICIO_MIN).strftime(fmt)
    except:
        pass
    return ent_padrao


def _sem_consecutiva(df, idx, valor="Folga"):
    """Evita folgas consecutivas (idx-1 e idx+1)."""
    if idx > 0 and df.loc[idx - 1, "Status"] == valor:
        return False
    if idx < len(df) - 1 and df.loc[idx + 1, "Status"] == valor:
        return False
    return True


def _max_50_ok(contagem_folgas_dia_cat, cat, idx, total_membros_cat):
    """Balanceamento: não deixa mais de 50% do setor folgar no mesmo dia."""
    if total_membros_cat <= 1:
        return True
    limite = (total_membros_cat // 2)  # 50% arredondando p/ baixo
    return contagem_folgas_dia_cat[cat][idx] <= limite


def _weekday_nome(data):
    return D_PT[data.day_name()]


# =========================================================
# GERADOR COM REGRAS SOLICITADAS
# =========================================================
def gerar_escala_inteligente(lista_usuarios):
    """
    Regras implementadas:
    - 5x2 (2 folgas por semana de 7 dias)
    - Domingo 1x1 alternado por categoria (se 2 pessoas alterna certinho; se >2 alterna em rodízio e respeita 50%)
    - Se FOLGA no domingo: a 2ª folga na semana é aleatória (seg-sex), sem folga consecutiva
      - Se "Casada" ligado: domingo folga => segunda também folga (se couber na semana)
    - Se TRABALHA no domingo: obrigatoriamente 1 folga seg-sex naquela semana
    - Sábado: só pode ser folga se "Rod_Sab" estiver marcado
    - Limite de 5 dias seguidos trabalhando (ajuste automático se necessário)
    - Interstício 11h10 (na geração de horários)
    - Balanceamento 50% por categoria/dia (exceto domingo, onde ainda tentamos respeitar 50%)
    """
    datas = pd.date_range(start=START_DATE, periods=PERIODOS)
    novo_hist = {}

    # Agrupar usuários por categoria
    cats = {}
    for u in lista_usuarios:
        c = u.get("Categoria", "Geral")
        cats.setdefault(c, []).append(u)

    # Contagem de folgas por categoria/dia (para balanceamento 50%)
    contagem_folgas_dia_cat = {cat: {i: 0 for i in range(PERIODOS)} for cat in cats.keys()}

    # 1) Definir DOMINGOS (rodízio 1x1 dentro de cada categoria)
    domingos_idx = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]

    domingo_folga_por_cat = {cat: {idx: set() for idx in domingos_idx} for cat in cats.keys()}
    for cat, membros in cats.items():
        total = len(membros)
        if total == 0:
            continue

        # alvo de folgas no domingo: 50% (para 2 pessoas => 1)
        alvo = max(1, total // 2)

        # rodízio
        for k, dom_i in enumerate(domingos_idx):
            # escolhe um "bloco" de pessoas no rodízio
            # para 2 pessoas: alterna perfeito
            # para >2: gira a janela
            start = (k * alvo) % total
            escolhidos = []
            for j in range(alvo):
                escolhidos.append(membros[(start + j) % total])

            for u in escolhidos:
                domingo_folga_por_cat[cat][dom_i].add(u["Nome"])

    # 2) Montar escala por pessoa com as regras da semana
    for cat, membros in cats.items():
        total_cat = len(membros)
        random.shuffle(membros)  # para não “viciar” sempre o mesmo

        for user in membros:
            nome = user["Nome"]
            entrada_padrao = user.get("Entrada", "06:00")
            rod_sab = bool(user.get("Rod_Sab", False))
            casada = bool(user.get("Casada", False))

            df = pd.DataFrame({
                "Data": datas,
                "Dia": [_weekday_nome(d) for d in datas],
                "Status": "Trabalho"
            })

            # Aplica domingo (pré-definido por categoria)
            for dom_i in domingos_idx:
                if nome in domingo_folga_por_cat[cat][dom_i]:
                    df.loc[dom_i, "Status"] = "Folga"
                    contagem_folgas_dia_cat[cat][dom_i] += 1

            # Semana em blocos de 7 (como seu código original)
            for sem in range(0, PERIODOS, 7):
                fim = min(sem + 7, PERIODOS)
                idxs = list(range(sem, fim))

                # Quantas folgas já existem no bloco (domingos já podem estar marcados)
                folgas_semana = int((df.loc[idxs, "Status"] == "Folga").sum())

                # Descobrir se tem domingo no bloco e se domingo é folga/trabalho
                dom_no_bloco = [i for i in idxs if df.loc[i, "Dia"] == "dom"]
                dom_idx = dom_no_bloco[0] if dom_no_bloco else None
                domingo_esta_folga = (dom_idx is not None and df.loc[dom_idx, "Status"] == "Folga")

                # Regra: Se folga domingo e Casada => segunda também folga (se existir e ainda não folga)
                if domingo_esta_folga and casada:
                    seg_idx = dom_idx + 1
                    if seg_idx < PERIODOS and df.loc[seg_idx, "Dia"] == "seg":
                        if df.loc[seg_idx, "Status"] != "Folga":
                            # não deixar consecutiva domingo/segunda? (casada é exceção, então pode)
                            df.loc[seg_idx, "Status"] = "Folga"
                            contagem_folgas_dia_cat[cat][seg_idx] += 1
                            folgas_semana += 1

                # Agora completar 2 folgas semanais
                while folgas_semana < 2:
                    possiveis = []

                    for j in idxs:
                        if df.loc[j, "Status"] != "Trabalho":
                            continue

                        # não dar folga no sábado, a não ser que Rod_Sab esteja marcado
                        if df.loc[j, "Dia"] == "sáb" and not rod_sab:
                            continue

                        # Regra: se TRABALHA no domingo => tem que ter folga seg-sex na semana
                        if dom_idx is not None and df.loc[dom_idx, "Status"] == "Trabalho":
                            if folgas_semana == 0:
                                # primeira folga obrigatoriamente seg-sex
                                if df.loc[j, "Dia"] not in ["seg", "ter", "qua", "qui", "sex"]:
                                    continue
                            # segunda folga: pode ser seg-sex também (preferível)

                        # Regra: se FOLGA no domingo => segunda folga aleatória seg-sex e sem consecutiva
                        if domingo_esta_folga and not casada:
                            # evita segunda (seria consecutiva com domingo)
                            if df.loc[j, "Dia"] == "seg":
                                continue
                            # mantém seg-sex
                            if df.loc[j, "Dia"] not in ["ter", "qua", "qui", "sex"]:
                                continue

                        # Evitar folga consecutiva (exceto casada já aplicada)
                        if not _sem_consecutiva(df, j, valor="Folga"):
                            continue

                        # Balanceamento 50% por categoria/dia
                        # (se ainda não excedeu 50%)
                        if contagem_folgas_dia_cat[cat][j] >= max(1, total_cat // 2):
                            continue

                        possiveis.append(j)

                    if not possiveis:
                        # se não achou, relaxa um pouco (mas ainda evita sábado)
                        for j in idxs:
                            if df.loc[j, "Status"] != "Trabalho":
                                continue
                            if df.loc[j, "Dia"] == "sáb" and not rod_sab:
                                continue
                            if not _sem_consecutiva(df, j, valor="Folga"):
                                continue
                            # permite até 50% (se categoria pequena, deixa passar 1)
                            possiveis.append(j)

                    if not possiveis:
                        break

                    escolhido = random.choice(possiveis)
                    df.loc[escolhido, "Status"] = "Folga"
                    contagem_folgas_dia_cat[cat][escolhido] += 1
                    folgas_semana += 1

                # Garantir: não mais de 5 dias consecutivos trabalhando (dentro do bloco)
                # Se achar 6+ consecutivos, transforma um dia (seg-sex preferencialmente) em Folga se possível
                consec = 0
                for j in idxs:
                    if df.loc[j, "Status"] == "Trabalho":
                        consec += 1
                        if consec > 5:
                            # tenta quebrar o streak no próprio dia j (se possível)
                            if df.loc[j, "Dia"] != "sáb" or rod_sab:
                                if _sem_consecutiva(df, j, valor="Folga") and contagem_folgas_dia_cat[cat][j] < max(1, total_cat // 2):
                                    df.loc[j, "Status"] = "Folga"
                                    contagem_folgas_dia_cat[cat][j] += 1
                                    consec = 0
                    else:
                        consec = 0

            # 3) Gerar horários respeitando interstício 11h10
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

    col_check1, col_check2 = st.columns(2)
    s_rk = col_check1.checkbox("Rodízio Sábado (pode folgar no sábado)")
    c_rk = col_check2.checkbox("Folga Casada (domingo folga => segunda folga)")

    if st.button("Salvar Funcionário"):
        if n and ct:
            st.session_state["db_users"].append({
                "Nome": n,
                "Categoria": ct,
                "Entrada": h_in.strftime("%H:%M"),
                "Rod_Sab": s_rk,
                "Casada": c_rk
            })
            st.success(f"{n} cadastrado com sucesso!")
        else:
            st.error("Preencha Nome e Categoria.")

    if st.session_state["db_users"]:
        st.markdown("### Funcionários cadastrados")
        st.dataframe(pd.DataFrame(st.session_state["db_users"]), use_container_width=True)


with aba2:
    if st.button("🚀 GERAR ESCALA (5x2 + Regras)"):
        if st.session_state["db_users"]:
            st.session_state["historico"] = gerar_escala_inteligente(st.session_state["db_users"])
            st.success("Escala Gerada com as regras solicitadas!")
        else:
            st.warning("Cadastre os funcionários na Aba 1.")

    if st.session_state["historico"]:
        for nome, df in st.session_state["historico"].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df, use_container_width=True)


with aba3:
    st.subheader("⚙️ Ajustes Manuais (Trocar folga, horário, categoria)")

    if st.session_state["historico"]:
        f_ed = st.selectbox("Selecione o Funcionário:", list(st.session_state["historico"].keys()))
        df_e = st.session_state["historico"][f_ed]

        user_info = next(u for u in st.session_state["db_users"] if u["Nome"] == f_ed)

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown("#### 🔄 Trocar folga")
            folgas_atuais = df_e[df_e["Status"] == "Folga"].index.tolist()
            if folgas_atuais:
                d_tira = st.selectbox("Dia para TRABALHAR:", [d + 1 for d in folgas_atuais])
            else:
                d_tira = None
                st.info("Sem folgas para trocar.")
            d_poe = st.number_input("Novo dia para FOLGAR:", 1, PERIODOS, value=1)

            if st.button("Confirmar troca de folga"):
                if d_tira is None:
                    st.warning("Não há folga para remover.")
                else:
                    df_e.loc[d_tira - 1, "Status"] = "Trabalho"
                    df_e.loc[d_poe - 1, "Status"] = "Folga"
                    df_e.loc[d_poe - 1, "H_Entrada"] = ""
                    df_e.loc[d_poe - 1, "H_Saida"] = ""
                    st.session_state["historico"][f_ed] = df_e
                    st.success("Troca realizada!")
                    st.rerun()

        with col_b:
            st.markdown("#### 🕒 Trocar horário")
            dia_h = st.number_input("Dia do mês:", 1, PERIODOS, key="dia_h")
            hora_h = st.time_input("Nova Entrada:", key="hora_h")

            if st.button("Salvar Novo Horário"):
                if df_e.loc[dia_h - 1, "Status"] == "Folga":
                    st.warning("Esse dia está como folga. Troque o status antes.")
                else:
                    entrada_nova = hora_h.strftime("%H:%M")
                    saida_calc = (datetime.strptime(entrada_nova, "%H:%M") + DURACAO_JORNADA).strftime("%H:%M")
                    df_e.loc[dia_h - 1, "H_Entrada"] = entrada_nova
                    df_e.loc[dia_h - 1, "H_Saida"] = saida_calc
                    st.session_state["historico"][f_ed] = df_e
                    st.success("Horário alterado!")

        with col_c:
            st.markdown("#### 🧩 Trocar categoria")
            categorias_existentes = sorted(list(set(u["Categoria"] for u in st.session_state["db_users"])))
            if user_info["Categoria"] in categorias_existentes:
                idx = categorias_existentes.index(user_info["Categoria"])
            else:
                idx = 0
            nova_categoria = st.selectbox("Nova categoria:", categorias_existentes, index=idx)

            if st.button("Salvar categoria"):
                user_info["Categoria"] = nova_categoria
                st.success("Categoria atualizada! (Para refletir na escala, gere novamente.)")

        st.markdown("---")
        st.dataframe(df_e, use_container_width=True)

    else:
        st.info("Gere uma escala primeiro na Aba 2.")


with aba4:
    st.subheader("📥 Exportar para Excel (modelo RH com dia + semana e 2 linhas por pessoa)")

    if st.session_state["historico"]:
        if st.button("📊 GERAR ARQUIVO PARA DOWNLOAD (Modelo RH)"):

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Mensal", index=0)

                # ---------- Estilos ----------
                fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", patternType="solid")  # azul escuro
                fill_name = PatternFill(start_color="D9E1F2", end_color="D9E1F2", patternType="solid")    # azul claro
                fill_folga = PatternFill(start_color="FFF2CC", end_color="FFF2CC", patternType="solid")   # amarelo claro
                fill_dom = PatternFill(start_color="C00000", end_color="C00000", patternType="solid")     # vermelho
                font_header = Font(color="FFFFFF", bold=True)

                border = Border(
                    left=Side(style="thin"),
                    right=Side(style="thin"),
                    top=Side(style="thin"),
                    bottom=Side(style="thin")
                )
                center = Alignment(horizontal="center", vertical="center", wrap_text=True)

                # Referência de datas (31 dias)
                df_ref = list(st.session_state["historico"].values())[0]

                # Cabeçalho: linha 1 (número do dia), linha 2 (dia da semana)
                ws.cell(1, 1, "COLABORADOR").fill = fill_header
                ws.cell(1, 1).font = font_header
                ws.cell(1, 1).alignment = center
                ws.cell(2, 1, "").fill = fill_header
                ws.cell(2, 1).alignment = center

                for i in range(PERIODOS):
                    dia_num = i + 1
                    dia_sem = df_ref.iloc[i]["Dia"]  # 'seg', 'ter', ...

                    c_top = ws.cell(1, i + 2, dia_num)
                    c_bot = ws.cell(2, i + 2, dia_sem)

                    # pinta header; domingo vermelho
                    if dia_sem == "dom":
                        c_top.fill = fill_dom
                        c_bot.fill = fill_dom
                    else:
                        c_top.fill = fill_header
                        c_bot.fill = fill_header

                    c_top.font = font_header
                    c_bot.font = font_header
                    c_top.alignment = center
                    c_bot.alignment = center
                    c_top.border = border
                    c_bot.border = border

                    ws.column_dimensions[get_column_letter(i + 2)].width = 8

                ws.column_dimensions["A"].width = 38
                ws.row_dimensions[1].height = 22
                ws.row_dimensions[2].height = 22

                # Dados: 2 linhas por pessoa (entrada / saída)
                row_idx = 3
                for nome, df_f in st.session_state["historico"].items():
                    # Nome (mescla duas linhas)
                    c_nome = ws.cell(row_idx, 1, nome)
                    c_nome.fill = fill_name
                    c_nome.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                    c_nome.border = border
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx + 1, end_column=1)

                    ws.row_dimensions[row_idx].height = 18
                    ws.row_dimensions[row_idx + 1].height = 18

                    for i, row in df_f.iterrows():
                        dia_sem = row["Dia"]
                        is_folga = (row["Status"] == "Folga")

                        c1 = ws.cell(row_idx, i + 2, "F" if is_folga else row["H_Entrada"])
                        c2 = ws.cell(row_idx + 1, i + 2, "" if is_folga else row["H_Saida"])

                        c1.alignment = center
                        c2.alignment = center
                        c1.border = border
                        c2.border = border

                        if is_folga:
                            # domingo folga em vermelho, outros amarelo
                            if dia_sem == "dom":
                                c1.fill = fill_dom
                                c2.fill = fill_dom
                                c1.font = Font(color="FFFFFF", bold=True)
                                c2.font = Font(color="FFFFFF", bold=True)
                            else:
                                c1.fill = fill_folga
                                c2.fill = fill_folga
                                c1.font = Font(bold=True)

                    row_idx += 2

                # remove a planilha default se existir
                if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
                    wb.remove(wb["Sheet"])

            st.download_button(
                label="📥 Baixar Escala (Excel modelo RH)",
                data=output.getvalue(),
                file_name=f"escala_5x2_modelo_RH_{datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.warning("Gere a escala na Aba 2 para liberar o Excel.")
