import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

# ================= CONFIGURAÇÕES =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids - v16", page_icon="🩸", layout="wide")

ARQ_G = "dados_glicemia_v16.csv"
ARQ_N = "dados_nutricao_v16.csv"

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}

h1 {font-size: 38px !important; font-weight: 700;}
h2, h3 {color: #1e293b; font-weight: 600;}

.card {
    background-color: white;
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    margin-bottom: 25px;
}

.stButton>button {
    border-radius: 12px;
    font-weight: 600;
    padding: 10px 18px;
}

.stNumberInput, .stSelectbox, .stMultiselect {
    background-color: white;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🩸 Monitoramento Saúde Kids</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#64748b;'>Sistema de acompanhamento glicêmico infantil</p>", unsafe_allow_html=True)

# ================= BANCO DE ALIMENTOS =================
ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

# ================= CORES COM PRIORIDADE =================
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70:
            return 'background-color: #FFFFE0; color: black'
        elif n > 180:
            return 'background-color: #FFB6C1; color: black'
        elif n > 140:
            return 'background-color: #FFFFE0; color: black'
        else:
            return 'background-color: #90EE90; color: black'
    except:
        return ""

# ================= ABAS =================
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "📸 Câmera"])

# =====================================================
# GLICEMIA
# =====================================================
with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    dfg = carregar(ARQ_G)

    with c1:
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0)
        m = st.selectbox("Momento:", [
            "Antes Café", "Após Café", "Antes Almoço", "Após Almoço",
            "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"
        ])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"),
                                  agora.strftime("%H:%M"),
                                  v, m]],
                                columns=["Data", "Hora", "Valor", "Momento"])
            pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo com sucesso!")
            st.rerun()

    with c2:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            dfg = dfg.sort_values("DataHora")

            fig = px.line(
                dfg.tail(10),
                x='DataHora',
                y='Valor',
                markers=True
            )

            fig.update_layout(
                template="simple_white",
                title="Gráfico de Evolução",
                xaxis_title="Data e Hora",
                yaxis_title="mg/dL",
                title_font_size=20
            )

            st.plotly_chart(fig, use_container_width=True)

    if not dfg.empty:
        st.subheader("📋 Relatório Médico Diário")
        dfg['Exibe'] = dfg['Valor'].astype(str) + " (" + dfg['Hora'] + ")"
        tab_pivot = dfg.pivot_table(index='Data', columns='Momento',
                                    values='Exibe', aggfunc='last').fillna("-")
        st.dataframe(tab_pivot.style.applymap(cor_glicemia),
                     use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# ALIMENTAÇÃO
# =====================================================
with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.subheader("🍽️ Controle de Nutrientes")

    ca1, ca2 = st.columns(2)

    with ca1:
        escolha = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
        carb = sum([ALIMENTOS[i][0] for i in escolha])
        prot = sum([ALIMENTOS[i][1] for i in escolha])
        gord = sum([ALIMENTOS[i][2] for i in escolha])

        st.info(f"Totais: Carboidratos: {carb}g | Proteínas: {prot}g | Gorduras: {gord}g")

        if st.button("💾 Salvar Alimentação"):
            agora = datetime.now(fuso_br)
            txt = f"{', '.join(escolha)} (C:{carb} P:{prot} G:{gord})"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"),
                                    txt, carb, prot, gord]],
                                  columns=["Data", "Info", "C", "P", "G"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True)\
              .to_csv(ARQ_N, index=False)
            st.rerun()

    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            fig2 = px.pie(
                values=[dfn['C'].sum(), dfn['P'].sum(), dfn['G'].sum()],
                names=['Carbo', 'Prot', 'Gord'],
                title="Distribuição Nutricional"
            )
            fig2.update_layout(template="simple_white")
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# CÂMERA
# =====================================================
with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.camera_input("📸 Registrar Prato ou Sensor")
    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================
# EXCEL COLORIDO
# =====================================================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic = df_glic.copy()
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data',
                                        columns='Momento',
                                        values='Exibe',
                                        aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']

            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")

            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            val = int(str(cell.value).split(" ")[0])
                            if val < 70:
                                cell.fill = a_fill
                            elif val > 180:
                                cell.fill = r_fill
                            elif val > 140:
                                cell.fill = a_fill
                            else:
                                cell.fill = v_fill
                        except:
                            pass

        if not df_nutri.empty:
            df_nutri.to_excel(writer, index=False, sheet_name='Alimentacao')

    return output.getvalue()

st.markdown("---")

if st.button("📥 BAIXAR RELATÓRIO EXCEL (Regra Corrigida)"):
    dfg = carregar(ARQ_G)
    dfn = carregar(ARQ_N)
    if not dfg.empty:
        excel_data = gerar_excel_colorido(dfg, dfn)
        st.download_button("Clique para Baixar",
                           excel_data,
                           file_name="Relatorio_Medico_Final.xlsx")
