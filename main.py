import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# ==============================
# REGRAS DO SISTEMA
# ==============================

AS_SISTEMA = {
    "ESCALA": "5x2 (5 dias de trabalho, 2 folgas semanais)",
    "INTERSTICIO": "Mínimo de 11h 10min de descanso entre jornadas",
    "DOMINGOS": "Regra 1x1 (Alternado por funcionário do mesmo setor)",
    "FOLGA_CASADA": "Se ativado, folga obrigatoriamente na segunda após domingo",
    "RODIZIO_SABADO": "Priorizar trabalho aos sábados conforme cadastro",
    "BALANCEAMENTO": "Evitar que mais de 50% do setor folgue no mesmo dia",
    "LIMITE_CONSECUTIVO": "Máximo de 5 dias seguidos de trabalho"
}

# ==============================
# MEMÓRIA
# ==============================

if 'db_users' not in st.session_state:
    st.session_state['db_users'] = []

if 'historico' not in st.session_state:
    st.session_state['historico'] = {}

# ==============================
# FUNÇÕES
# ==============================

def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0:
            diff += 24
        if diff < 11:
            return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except:
        pass
    return ent_padrao


def gerar_escala_inteligente(lista_usuarios):

    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua',
            'Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}

    novo_hist = {}
    categorias = {}

    # Agrupar por categoria
    for u in lista_usuarios:
        categorias.setdefault(u['Categoria'], []).append(u)

    for cat, membros in categorias.items():

        domingos = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]
        total_membros = len(membros)

        for idx_membro, user in enumerate(membros):

            nome = user['Nome']

            df = pd.DataFrame({
                "Data": datas,
                "Dia": [d_pt[d.day_name()] for d in datas],
                "Status": "Trabalho"
            })

            # ==============================
            # DOMINGO INTERCALADO
            # ==============================

            for idx_dom, dia_dom in enumerate(domingos):
                if (idx_dom + idx_membro) % 2 == 0:
                    df.loc[dia_dom, 'Status'] = "Folga"

                    # Folga casada (segunda)
                    if user.get("Casada"):
                        if dia_dom + 1 < 31:
                            df.loc[dia_dom + 1, 'Status'] = "Folga"

            # ==============================
            # COMPLETAR 5x2
            # ==============================

            for sem in range(0, 31, 7):

                fim = min(sem + 7, 31)
                folgas = df.iloc[sem:fim]['Status'].value_counts().get('Folga', 0)

                while folgas < 2:

                    possiveis = []

                    for j in range(sem, fim):

                        if df.loc[j, 'Status'] == "Trabalho":

                            # limite consecutivo
                            anteriores = df.loc[max(0,j-5):j-1]
                            if (anteriores['Status'] == "Trabalho").sum() >= 5:
                                continue

                            # rodízio sábado
                            if df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"):
                                continue

                            # balanceamento
                            folgas_dia = sum(
                                1 for h in novo_hist.values()
                                if h.loc[j, 'Status'] == "Folga"
                            )
                            if total_membros > 1:
                                if folgas_dia >= total_membros / 2:
                                    continue

                            possiveis.append(j)

                    if not possiveis:
                        break

                    escolhido = random.choice(possiveis)
                    df.loc[escolhido, 'Status'] = "Folga"
                    folgas += 1

            # ==============================
            # HORÁRIOS
            # ==============================

            entradas, saidas = [], []
            hp = user.get("Entrada", "06:00")

            for i in range(len(df)):

                if df.loc[i, 'Status'] == "Folga":
                    entradas.append("")
                    saidas.append("")
                else:
                    e = hp
                    if i > 0 and saidas and saidas[-1] != "":
                        e = calcular_entrada_segura(saidas[-1], hp)

                    entradas.append(e)

                    saidas.append(
                        (datetime.strptime(e,"%H:%M")
                        + timedelta(hours=9,minutes=58)).strftime("%H:%M")
                    )

            df["H_Entrada"] = entradas
            df["H_Saida"] = saidas

            novo_hist[nome] = df

    return novo_hist


# ==============================
# INTERFACE
# ==============================

aba1, aba2, aba3, aba4 = st.tabs(
    ["👥 Cadastro", "🚀 Gerar Escala", "⚙️ Ajustes", "📥 Excel"]
)

# ==============================
# ABA 1
# ==============================

with aba1:

    st.subheader("Cadastro Funcionário")

    nome = st.text_input("Nome")
    categoria = st.text_input("Categoria")

    entrada = st.time_input("Entrada padrão",
                            value=datetime.strptime("06:00","%H:%M").time())

    col1,col2 = st.columns(2)
    rod_sab = col1.checkbox("Rodízio sábado")
    folga_casada = col2.checkbox("Folga casada")

    if st.button("Salvar Funcionário"):
        if nome and categoria:
            st.session_state['db_users'].append({
                "Nome": nome,
                "Categoria": categoria,
                "Entrada": entrada.strftime("%H:%M"),
                "Rod_Sab": rod_sab,
                "Casada": folga_casada
            })
            st.success("Funcionário cadastrado!")
        else:
            st.error("Preencha nome e categoria.")


# ==============================
# ABA 2
# ==============================

with aba2:

    if st.button("GERAR ESCALA"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(
                st.session_state['db_users']
            )
            st.success("Escala gerada com sucesso!")
        else:
            st.warning("Cadastre funcionários primeiro.")

    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(nome):
                st.dataframe(df, use_container_width=True)


# ==============================
# ABA 3 - AJUSTES
# ==============================

with aba3:

    if st.session_state['historico']:

        func = st.selectbox(
            "Funcionário",
            list(st.session_state['historico'].keys())
        )

        df_edit = st.session_state['historico'][func]
        user_info = next(u for u in st.session_state['db_users']
                         if u['Nome']==func)

        st.markdown("### 🔄 Trocar Folga")

        folgas = df_edit[df_edit['Status']=="Folga"].index.tolist()

        if folgas:

            remover = st.selectbox(
                "Remover folga do dia",
                [f+1 for f in folgas]
            )

            adicionar = st.number_input(
                "Adicionar folga no dia",
                1,31,value=1
            )

            if st.button("Confirmar troca"):
                df_edit.loc[remover-1,"Status"]="Trabalho"
                df_edit.loc[adicionar-1,"Status"]="Folga"
                st.success("Folga alterada.")
                st.rerun()

        st.markdown("### 🕒 Alterar Horário")

        dia_h = st.number_input("Dia",1,31)
        nova_hora = st.time_input("Nova entrada")

        if st.button("Salvar horário"):
            df_edit.loc[dia_h-1,"H_Entrada"]=nova_hora.strftime("%H:%M")
            nova_saida=(datetime.combine(datetime.today(),nova_hora)
                        +timedelta(hours=9,minutes=58)).strftime("%H:%M")
            df_edit.loc[dia_h-1,"H_Saida"]=nova_saida
            st.success("Horário atualizado.")

        st.markdown("### 🏢 Alterar Categoria")

        categorias = list(set(u['Categoria']
                              for u in st.session_state['db_users']))

        nova_cat = st.selectbox(
            "Nova categoria",
            categorias,
            index=categorias.index(user_info['Categoria'])
        )

        if st.button("Salvar categoria"):
            user_info['Categoria']=nova_cat
            st.success("Categoria atualizada.")
            st.rerun()

        st.dataframe(df_edit,use_container_width=True)


# ==============================
# ABA 4 - EXCEL
# ==============================

with aba4:

    if st.session_state['historico']:

        if st.button("Gerar Excel"):

            output=io.BytesIO()

            with pd.ExcelWriter(output,engine='openpyxl') as writer:

                wb=writer.book
                ws=wb.create_sheet("Escala",0)

                fill_dom=PatternFill(start_color="FF0000",
                                     end_color="FF0000",
                                     patternType="solid")

                fill_folga=PatternFill(start_color="FFFF00",
                                       end_color="FFFF00",
                                       patternType="solid")

                center=Alignment(horizontal="center",
                                 vertical="center")

                border=Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )

                df_ref=list(st.session_state['historico'].values())[0]

                for i in range(31):
                    ws.cell(1,i+2,i+1).alignment=center
                    ws.cell(2,i+2,df_ref.iloc[i]['Dia']).alignment=center

                row_idx=3

                for nome,df in st.session_state['historico'].items():

                    ws.cell(row_idx,1,nome)

                    for i,row in df.iterrows():

                        is_folga=(row['Status']=="Folga")

                        cell=ws.cell(
                            row_idx,i+2,
                            "FOLGA" if is_folga else row['H_Entrada']
                        )

                        if is_folga:
                            cell.fill=fill_dom if row['Dia']=="dom" else fill_folga

                        cell.alignment=center
                        cell.border=border

                    row_idx+=1

            st.download_button(
                "Baixar Excel",
                data=output.getvalue(),
                file_name="escala_5x2.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
