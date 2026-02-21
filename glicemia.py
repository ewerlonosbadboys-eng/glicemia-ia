import streamlit as st
import google.generativeai as genai
import PIL.Image
import re

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸")
st.title("🩸 Leitura de Glicemia")

foto = st.camera_input("Tire foto do visor")

if foto:
    try:
        img = PIL.Image.open(foto)
        
        # Comando curto e grosso para a IA não se distrair
        prompt = "Identifique o maior número central nesta tela de medidor. Responda APENAS o número, sem letras."
        
        response = model.generate_content([prompt, img])
        
        # Este comando abaixo remove qualquer letra ou símbolo que a IA tente escrever
        so_numeros = re.sub(r'\D', '', response.text)
        
        if so_numeros:
            st.markdown(f"<h1 style='text-align: center; color: #00ff00; font-size: 70px;'>{so_numeros}</h1>", unsafe_allow_html=True)
            st.balloons()
        else:
            st.error("Número não encontrado. Tente focar melhor no visor.")
            
    except Exception as e:
        st.error("Erro na análise. Verifique a iluminação.")
