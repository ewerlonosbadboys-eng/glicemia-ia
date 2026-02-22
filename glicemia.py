import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Diário Glicemia Kids", page_icon="🩸")
st.title("🩸 Diário Glicemia (Excel)")

# --- FUNÇÃO PARA SALVAR DADOS ---
def salvar_leitura(valor, categoria):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")
    mes_ano = agora.strftime("%m/%Y")
    
    nova_linha = pd.DataFrame([[data, hora, valor, categoria, mes_ano]], 
                             columns=["Data", "Hora", "Valor (mg/dL)", "Categoria", "Mês/Ano"])
    
    arquivo = "historico_glicemia.csv"
    if not os.path.isfile(arquivo):
        nova_linha.to_csv(arquivo, index=False)
    else:
        nova_linha.to_csv(arquivo, mode='a', header=False, index=False)
    st.success(f"✅ Salvo: {valor} mg/dL em '{categoria}'")

# --- INTERFACE DE ENTRADA ---
col1, col2 = st.columns([1, 1])
with col1:
    valor_manual = st.number_input("Valor:", min_value=0, max_value=600, step=1, value=0)
with col2:
    lista_categorias = [
        "Medida antes do café", "Medida após o café",
        "Medida antes do almoço", "Medida após o almoço",
        "Medida antes da merenda", "Medida antes da janta",
        "Medida após a janta", "Medida madrugada", "Medida Extra"
    ]
    categoria_sel = st.selectbox("Momento:", lista_categorias)

foto = st.camera_input("Foto do visor")
valor_detectado = 0

if foto:
    try:
        img = PIL.Image.open(foto)
        with st.spinner("IA lendo..."):
            prompt = "Identifique o maior número central. Responda APENAS o número."
            response = model.generate_content([prompt, img])
            numeros = re.findall(r'\d+', response.text)
            if numeros:
                valor_detectado = int(max(numeros, key=len))
    except:
        st.error("Erro na foto.")

valor_final = valor_manual if valor_manual > 0 else valor_detectado

if valor_final > 0:
    st.markdown(f"<h1 style='text-align: center; color: #00ff00; font-size: 80px;'>{valor_final}</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR E GERAR RELATÓRIO"):
        salvar_leitura(valor_final, categoria_sel)

st.markdown("---")

# --- RELATÓRIOS E EXPORTAÇÃO EXCEL ---
st.subheader("📊 Relatórios Mensais")

if os.path.isfile("historico_glicemia.csv"):
    df = pd.read_csv("historico_glicemia.csv")
    mes_atual = datetime.now().strftime("%m/%Y")
    df_mes = df[df['Mês/Ano'] == mes_atual]
    
    st.write(f"Dados de {mes_atual}:")
    st.dataframe(df_mes, use_container_width=True)
    
    # FUNÇÃO PARA CONVERTER PARA EXCEL
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_mes.to_excel(writer, index=False, sheet_name='Glicemia')
    
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 Baixar Relatório em EXCEL (.xlsx)",
        data=excel_data,
        file_name=f"glicemia_{mes_atual.replace('/','_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.write("Nenhuma medida salva.")
