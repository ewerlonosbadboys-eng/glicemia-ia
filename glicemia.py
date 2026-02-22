import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO

# Configuração da IA (Gemini 1.5 Flash)
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸", layout="wide")
st.title("🩸 Diário de Glicemia Profissional")

# --- FUNÇÃO PARA SALVAR ---
def salvar_leitura(valor, categoria):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    mes_ano = agora.strftime("%m/%Y")
    
    # Criamos o registro com nomes de colunas fixos e limpos
    nova_linha = pd.DataFrame([[data, valor, categoria, mes_ano]], 
                             columns=["Data", "Valor", "Categoria", "Mes_Ano"])
    
    arquivo = "historico_glicemia.csv"
    if not os.path.isfile(arquivo):
        nova_linha.to_csv(arquivo, index=False)
    else:
        # Adiciona sem repetir o cabeçalho
        nova_linha.to_csv(arquivo, mode='a', header=False, index=False)
    st.success(f"✅ Salvo: {valor} mg/dL em {categoria}")

# --- ENTRADA DE DADOS ---
categorias_ordem = [
    "Medida antes do café", "Medida após o café",
    "Medida antes do almoço", "Medida após o almoço",
    "Medida antes da merenda", "Medida antes da janta",
    "Medida após a janta", "Medida madrugada", "Medida Extra"
]

col1, col2 = st.columns(2)
with col1:
    valor_manual = st.number_input("Digite o Valor:", min_value=0, max_value=600, step=1)
    cat_sel = st.selectbox("Momento da Medida:", categorias_ordem)

with col2:
    foto = st.camera_input("Tirar Foto do Sensor")

valor_final = valor_manual
if foto and valor_manual == 0:
    try:
        img = PIL.Image.open(foto)
        response = model.generate_content(["Retorne apenas o número grande da glicemia.", img])
        res = "".join(re.findall(r'\d+', response.text))
        if res:
            valor_final = int(res)
            st.info(f"IA identificou: {valor_final}")
    except:
        st.error("Erro na foto. Use o modo manual.")

if valor_final > 0:
    st.markdown(f"<h1 style='color:#00FF00; text-align:center;'>{valor_final} mg/dL</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR NO RELATÓRIO EXCEL"):
        salvar_leitura(valor_final, cat_sel)

st.markdown("---")

# --- GERAÇÃO DO RELATÓRIO PARA O MÉDICO ---
st.subheader("📊 Relatório para Impressão")

if os.path.isfile("historico_glicemia.csv"):
    try:
        # Carrega os dados e ignora colunas fantasmas de versões antigas
        df = pd.read_csv("historico_glicemia.csv")
        
        # PADRONIZAÇÃO DE COLUNAS (Evita o erro KeyError)
        if "Valor (mg/dL)" in df.columns: df.rename(columns={"Valor (mg/dL)": "Valor"}, inplace=True)
        if "Data/Hora" in df.columns: df.rename(columns={"Data/Hora": "Data"}, inplace=True)

        # Monta a tabela igual à sua imagem (Data na esquerda, Categorias no topo)
        relatorio = df.pivot_table(
            index='Data', 
            columns='Categoria', 
            values='Valor', 
            aggfunc='last' # Pega a última medida caso tenha mais de uma
        ).reset_index()

        # Reordena as colunas para o fluxo do dia
        colunas_final = ['Data'] + [c for c in categorias_ordem if c in relatorio.columns]
        relatorio = relatorio.reindex(columns=colunas_final)

        st.dataframe(relatorio.style.highlight_max(axis=0, color='#ffcccc').highlight_min(axis=0, color='#ccffcc'))

        # Conversão para EXCEL REAL
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            relatorio.to_excel(writer, index=False, sheet_name='Glicemia')
        
        st.download_button(
            label="📥 Baixar Relatório Excel para o Médico",
            data=output.getvalue(),
            file_name=f"Glicemia_Kids_{datetime.now().strftime('%m_%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Erro ao organizar histórico: {e}")
        if st.button("Limpar Histórico e Recomeçar"):
            os.remove("historico_glicemia.csv")
            st.rerun()
else:
    st.info("Aguardando a primeira medição para gerar o relatório.")
