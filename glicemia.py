import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import pytz
import matplotlib.pyplot as plt
import shutil

# ================= CONFIG =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v34 PRO", layout="wide")

ARQ_G = "dados_glicemia_v34.csv"
PASTA_BACKUP = "backup"

if not os.path.exists(PASTA_BACKUP):
    os.makedirs(PASTA_BACKUP)

# ================= VISUAL INFANTIL =================
st.markdown("""
<style>
.card {
    padding:25px;
    border-radius:20px;
    text-align:center;
    font-size:28px;
    font-weight:bold;
}
.green {background-color:#C8F7C5;}
.yellow {background-color:#FFF3B0;}
.red {background-color:#F8C8C8;}
</style>
""", unsafe_allow_html=True)

# ================= FUNÇÕES =================

def carregar():
    return pd.read_csv(ARQ_G) if os.path.exists(ARQ_G) else pd.DataFrame()

def salvar_backup():
    if os.path.exists(ARQ_G):
        hoje = datetime.now(fuso_br).strftime("%Y%m%d_%H%M%S")
        shutil.copy(ARQ_G, f"{PASTA_BACKUP}/backup_{hoje}.csv")

def classificar(valor):
    if valor < 70:
        return "HIPO"
    elif valor > 180:
        return "HIPER"
    elif valor > 140:
        return "ATENÇÃO"
    else:
        return "NORMAL"

def sugestao_ia(media):
    if media > 180:
        return "Reduzir carboidratos simples e revisar jantar."
    elif media < 70:
        return "Adicionar lanche antes de dormir."
    elif media > 140:
        return "Monitorar arroz, pão e bolachas."
    else:
        return "Controle alimentar adequado."

def alerta_sonoro():
    st.audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3")

# ================= TÍTULO =================
st.title("📱 Saúde Kids v34 PRO")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard",
    "🩸 Registro",
    "📈 Gráfico Profissional",
    "📥 Relatório Médico"
])

# =========================================================
# DASHBOARD
# =========================================================
with tab1:
    df = carregar()

    if not df.empty:
        df['DataHora'] = pd.to_datetime(df['Data'] + " " + df['Hora'], dayfirst=True)
        df = df.sort_values("DataHora")

        hoje = datetime.now(fuso_br).strftime("%d/%m/%Y")
        df_hoje = df[df['Data'] == hoje]

        if not df_hoje.empty:
            media = round(df_hoje['Valor'].mean(),1)
            maior = df_hoje['Valor'].max()
            menor = df_hoje['Valor'].min()

            col1,col2,col3 = st.columns(3)
            col1.metric("Média do Dia", f"{media} mg/dL")
            col2.metric("Maior", maior)
            col3.metric("Menor", menor)

            ultimo = df_hoje.iloc[-1]['Valor']

            if ultimo < 70:
                cor="red"; emoji="😟"
            elif ultimo > 180:
                cor="red"; emoji="⚠"
            elif ultimo > 140:
                cor="yellow"; emoji="🙂"
            else:
                cor="green"; emoji="😃"

            st.markdown(f"<div class='card {cor}'>{emoji} {ultimo} mg/dL</div>", unsafe_allow_html=True)

            if ultimo < 70 or ultimo > 180:
                alerta_sonoro()
                st.warning("⚠ Glicemia fora da meta!")

            st.subheader("🧠 Sugestão Inteligente")
            st.info(sugestao_ia(media))

        # Comparação semanal automática
        df['Semana'] = df['DataHora'].dt.isocalendar().week
        media_semana = df.groupby("Semana")['Valor'].mean()
        st.subheader("📊 Média Semanal")
        st.line_chart(media_semana)

# =========================================================
# REGISTRO
# =========================================================
with tab2:
    valor = st.number_input("Valor da Glicemia", min_value=0)
    momento = st.selectbox("Momento", [
        "Antes Cafe","Apos Cafe",
        "Antes Almoco","Apos Almoco",
        "Antes Janta","Apos Janta",
        "Madrugada"
    ])

    if st.button("Salvar"):
        agora = datetime.now(fuso_br)
        novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"),
                              agora.strftime("%H:%M"),
                              valor,
                              momento]],
                            columns=["Data","Hora","Valor","Momento"])
        df = pd.concat([carregar(),novo],ignore_index=True)
        df.to_csv(ARQ_G,index=False)
        salvar_backup()
        st.success("Salvo com sucesso!")
        st.rerun()

    df = carregar()
    if not df.empty:
        df['DataHora'] = pd.to_datetime(df['Data'] + " " + df['Hora'], dayfirst=True)
        df = df.sort_values("DataHora")
        st.dataframe(df[['Data','Hora','Valor','Momento']], use_container_width=True)
        st.write("Meta ideal: 70–180 mg/dL")

# =========================================================
# GRÁFICO PROFISSIONAL
# =========================================================
with tab3:
    df = carregar()

    if not df.empty:
        df['DataHora'] = pd.to_datetime(df['Data'] + " " + df['Hora'], dayfirst=True)
        df = df.sort_values("DataHora")

        fig, ax = plt.subplots(figsize=(10,5))
        ax.plot(df['DataHora'], df['Valor'], marker='o')

        ax.axhline(70)
        ax.axhline(180)

        ax.set_ylim(0,600)
        ax.set_yticks(range(0,601,100))

        ax.set_title("Evolução da Glicemia")
        ax.set_ylabel("mg/dL")

        st.pyplot(fig)
        st.write("Linha inferior: 70 mg/dL")
        st.write("Linha superior: 180 mg/dL")
        st.write(f"Média Geral: {round(df['Valor'].mean(),1)} mg/dL")

# =========================================================
# RELATÓRIO MÉDICO
# =========================================================
with tab4:
    if st.button("📥 Gerar Excel Médico"):
        df = carregar()
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Glicemia', index=False)

        st.download_button(
            "Clique para baixar",
            output.getvalue(),
            file_name="Relatorio_Saude_Kids_v34.xlsx"
        )
