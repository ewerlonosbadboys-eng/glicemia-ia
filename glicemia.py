import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from openpyxl.styles import PatternFill
import plotly.express as px

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸", layout="wide")
st.title("🩸 Monitoramento com Horários Detalhados")

ARQUIVO = "historico_glicemia.csv"

def carregar_dados():
    if os.path.isfile(ARQUIVO):
        df = pd.read_csv(ARQUIVO)
        # Limpeza de colunas antigas para evitar erros (KeyError/NameError)
        df.columns = [c.replace('Valor (mg/dL)', 'Valor').replace('Data/Hora', 'Data') for c in df.columns]
        if 'Hora' not in df.columns: df['Hora'] = "00:00"
        return df
    return pd.DataFrame(columns=["Data", "Hora", "Valor", "Categoria", "Mes_Ano"])

def salvar_csv(df):
    df.to_csv(ARQUIVO, index=False)

# --- ENTRADA DE DADOS ---
categorias_ordem = [
    "Medida antes do café", "Medida após o café",
    "Medida antes do almoço", "Medida após o almoço",
    "Medida antes da merenda", "Medida antes da janta",
    "Medida após a janta", "Medida madrugada", "Medida Extra"
]

st.subheader("📝 Novo Registro")
col1, col2 = st.columns(2)
with col1:
    valor_manual = st.number_input("Valor:", min_value=0, max_value=600, step=1)
    cat_sel = st.selectbox("Momento:", categorias_ordem)
with col2:
    foto = st.camera_input("Foto do Sensor")

valor_final = valor_manual
if foto and valor_manual == 0:
    try:
        img = PIL.Image.open(foto)
        response = model.generate_content(["Retorne apenas o número central.", img])
        res = "".join(re.findall(r'\d+', response.text))
        if res: valor_final = int(res)
    except: st.error("Erro na leitura da foto.")

if valor_final > 0:
    cor = "yellow" if valor_final <= 69 else "green" if valor_final <= 200 else "red"
    st.markdown(f"<h1 style='color:{cor}; text-align:center;'>{valor_final} mg/dL</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR MEDIDA"):
        agora = datetime.now()
        df = carregar_dados()
        nova = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), valor_final, cat_sel, agora.strftime("%m/%Y")]], 
                           columns=["Data", "Hora", "Valor", "Categoria", "Mes_Ano"])
        df = pd.concat([df, nova], ignore_index=True)
        salvar_csv(df)
        st.success("✅ Salvo com sucesso!")
        st.rerun()

st.markdown("---")

# --- GRÁFICO E RELATÓRIO ---
df = carregar_dados()
if not df.empty:
    # Gráfico de Picos de 24h
    st.subheader("📈 Análise de Picos (Hoje)")
    hoje = datetime.now().strftime("%d/%m/%Y")
    df_hoje = df[df['Data'] == hoje].sort_values('Hora')
    if not df_hoje.empty:
        fig = px.line(df_hoje, x='Hora', y='Valor', markers=True, title=f"Tendência em {hoje}")
        st.plotly_chart(fig, use_container_width=True)

    # Relatório com Horários: ex "193 (20:45)"
    try:
        df['Valor_Hora'] = df['Valor'].astype(str) + " (" + df['Hora'].astype(str) + ")"
        rel = df.pivot_table(index='Data', columns='Categoria', values='Valor_Hora', aggfunc='last').reset_index()
        rel = rel.reindex(columns=['Data'] + [c for c in categorias_ordem if c in rel.columns])

        st.subheader("📊 Relatório Formato Médico (Valor + Hora)")
        st.dataframe(rel, use_container_width=True)

        # Excel Colorido
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            rel.to_excel(writer, index=False, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            # Estilos de cores
            f_am = PatternFill("solid", "FFFF00") # Hipo
            f_vd = PatternFill("solid", "92D050") # Ok
            f_vm = PatternFill("solid", "FF0000") # Hiper

            for r in range(2, ws.max_row + 1):
                for c in range(2, ws.max_column + 1):
                    cel = ws.cell(row=r, column=c)
                    if cel.value:
                        try:
                            # Extrai apenas o número antes do parênteses para colorir
                            v = float(cel.value.split(" ")[0])
                            if v <= 69: cel.fill = f_am
                            elif v <= 200: cel.fill = f_vd
                            else: cel.fill = f_vm
                        except: pass

        st.download_button("📥 Baixar Excel Colorido com Horários", output.getvalue(), file_name="Relatorio_Glicemia.xlsx")
    except Exception as e:
        st.warning(f"Ajustando dados: {e}")

if st.sidebar.button("🗑️ Limpar Erros (Resetar)"):
    if os.path.exists(ARQUIVO): os.remove(ARQUIVO)
    st.rerun()
