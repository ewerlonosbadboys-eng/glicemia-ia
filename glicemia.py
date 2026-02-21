import streamlit as st
import google.generativeai as genai
import os

# Sua chave configurada
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸")
st.title("🩸 Glicemia Kids Inteligente")

foto = st.camera_input("Tire foto do sensor")

if foto:
    st.info("A IA está analisando a imagem...")
    
    # SALVA A FOTO TEMPORARIAMENTE (Isso resolve o erro!)
    with open("temp_foto.jpg", "wb") as f:
        f.write(foto.getbuffer())
    
    # Envia o arquivo salvo para a IA
    img = genai.upload_file("temp_foto.jpg")
    response = model.generate_content(["Leia o valor da glicemia nesta imagem de sensor. Retorne APENAS o número.", img])
    
    st.success(f"Valor identificado: {response.text}")
    
    # Limpa o arquivo temporário
    os.remove("temp_foto.jpg")
