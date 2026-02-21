import streamlit as st
import google.generativeai as genai

# Configurando a sua IA com a chave que você pegou
genai.configure(api_key="SUA_CHAVE_AQUI")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸")
st.title("🩸 Glicemia Kids Inteligente")

# Interface do App
foto = st.camera_input("Tire foto do sensor")

if foto:
    st.info("A IA está lendo o valor...")
    # Processando a imagem com IA
    img = genai.upload_file(foto)
    response = model.generate_content(["Qual o valor de glicemia nesta imagem? Responda apenas o número.", img])
    
    valor = response.text
    st.success(f"Valor identificado: {valor} mg/dL")
    
    if st.button("Salvar Registro"):
        st.write("Salvo com sucesso!")
        st.balloons()