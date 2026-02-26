import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# --- MEMÓRIA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0: diff += 24
        if diff < 11: 
            return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except:
        pass
    return ent_padrao


# ==============================
# 🔥 NOVA LÓGICA DE DOMINGO INTERCALADO
# ==============================

def gerar_escala_inteligente(lista_usuarios):

    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui',
            'Friday':'sex','Saturday':'sáb','Sunday':'dom'}

    novo_hist = {}
    cats = {}

    # Agrupar por categoria
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        cats.setdefault(c, []).append(u)

    for cat_nome, membros in cats.items():

        domingos_indices = [i for i, d in enumerate(datas) if d.day_name() == "Sunday"]

        # Alternância entre funcionários da categoria
        for idx_membro, user in enumerate(membros):

            nome = user['Nome']
            df = pd.DataFrame({
                'Data': datas,
                'Dia': [d_pt[d.day_name()] for d in datas],
                'Status': 'Trabalho'
            })

            # ==============================
            # 🔁 INTERCALAÇÃO DE DOMINGOS
            # ==============================
            for idx_dom, dia_dom in enumerate(domingos_indices):

                # alterna entre funcionários
                if (idx_dom + idx_membro) % 2 == 0:
                    df.loc[dia_dom, 'Status'] = 'Folga'

            # ==============================
            # REGRA 5x2 (segunda folga)
            # ==============================

            for sem in range(0, 31, 7):

                fim = min(sem + 7, 31)
                folgas_semana = df.iloc[sem:fim]['Status'].value_counts().get('Folga', 0)

                while folgas_semana < 2:

                    possiveis = [
                        j for j in range(sem, fim)
                        if df.loc[j, 'Status'] == 'Trabalho'
                        and not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False)
                        and not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False)
                        and not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))
                    ]

                    if not possiveis:
                        break

                    escolhido = random.choice(possiveis)
                    df.loc[escolhido, 'Status'] = 'Folga'
                    folgas_semana += 1

            # ==============================
            # HORÁRIOS
            # ==============================

            ents, sais = [], []
            hp = user.get("Entrada", "06:00")

            for m in range(len(df)):
                if df.loc[m, 'Status'] == 'Folga':
                    ents.append("")
                    sais.append("")
                else:
                    e = hp
                    if m > 0 and sais and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], hp)
                    ents.append(e)
                    sais.append(
                        (datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                    )

            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df

    return novo_hist


# ==============================
# INTERFACE
# ==============================

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
    s_rk = col_check1.checkbox("Rodízio Sábado")
    c_rk = col_check2.checkbox("Folga Casada")

    if st.button("Salvar Funcionário"):
        if n and ct:
            st.session_state['db_users'].append({
                "Nome": n,
                "Categoria": ct,
                "Entrada": h_in.strftime('%H:%M'),
                "Rod_Sab": s_rk,
                "Casada": c_rk
            })
            st.success(f"{n} cadastrado com sucesso!")
        else:
            st.error("Preencha Nome e Categoria.")


with aba2:
    if st.button("🚀 GERAR ESCALA (5x2 Inteligente)"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(
                st.session_state['db_users']
            )
            st.success("Escala Gerada com Domingos Intercalados!")
        else:
            st.warning("Cadastre os funcionários na Aba 1.")

    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df, use_container_width=True)


with aba3:
    st.subheader("⚙️ Ajustes Manuais")

    if st.session_state['historico']:

        f_ed = st.selectbox(
            "Selecione o Funcionário:",
            list(st.session_state['historico'].keys())
        )

        df_e = st.session_state['historico'][f_ed]

        st.dataframe(df_e, use_container_width=True)


with aba4:
    st.subheader("📥 Exportar para Excel")

    if st.session_state['historico']:

        if st.button("📊 GERAR ARQUIVO PARA DOWNLOAD"):

            output = io.BytesIO()

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Mensal", index=0)

                fill_dom = PatternFill(start_color="FF0000",
                                       end_color="FF0000",
                                       patternType="solid")

                fill_folga = PatternFill(start_color="FFFF00",
                                         end_color="FFFF00",
                                         patternType="solid")

                border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )

                center = Alignment(horizontal="center", vertical="center")

                df_ref = list(st.session_state['historico'].values())[0]

                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center

                row_idx = 3

                for nome, df_f in st.session_state['historico'].items():

                    ws.cell(row_idx, 1, nome)

                    for i, row in df_f.iterrows():

                        is_folga = (row['Status'] == 'Folga')

                        c1 = ws.cell(row_idx, i+2,
                                     "FOLGA" if is_folga else row['H_Entrada'])

                        if is_folga:
                            c1.fill = fill_dom if row['Dia'] == 'dom' else fill_folga

                        c1.border = border
                        c1.alignment = center

                    row_idx += 1

            st.download_button(
                label="📥 Baixar Escala em Excel",
                data=output.getvalue(),
                file_name=f"escala_5x2_{datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
