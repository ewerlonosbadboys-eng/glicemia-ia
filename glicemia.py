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
            "Você é um especialista em leitura de sensores de glicose. Identifique o valor numérico grande central nesta imagem. Ignore reflexos e retorne apenas o número.", 
            img
        ])
        
        st.success(f"Valor identificado: {response.text}")
    except Exception as e:
        st.error("Erro ao ler a imagem. Tente tirar a foto novamente com mais luz.")

