import streamlit as st
import google.generativeai as genai
import PIL.Image

# Configuração da API
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸")
st.title("🩸 Glicemia Kids Inteligente")

# Interface da Câmera
foto = st.camera_input("Tire foto do sensor")

if foto:
    st.info("A IA está analisando a imagem...")
    try:
        # Converte a foto diretamente para um formato que a IA entende
        img = PIL.Image.open(foto)
        
        # Solicita a leitura para a IA
        response = model.generate_content([
            "Leia o valor da glicemia nesta imagem de sensor de glicose. Retorne APENAS o número que você vê no visor.", 
            img
        ])
        
        st.success(f"Valor identificado: {response.text}")
    except Exception as e:
        st.error("Erro ao ler a imagem. Tente tirar a foto novamente com mais luz.")
