import streamlit as st
import google.generativeai as genai
import PIL.Image

# Configuração da API do Google Gemini
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

# Configuração visual do App
st.set_page_config(page_title="Glicemia Kids", page_icon="🩸")
st.title("🩸 Glicemia Kids Inteligente")
st.markdown("---")
st.write("Tire uma foto bem nítida do sensor para que a IA realize a leitura.")

# Interface de Captura de Imagem
foto = st.camera_input("Tire foto do sensor")

if foto:
    st.info("A IA está analisando a imagem... Por favor, aguarde.")
    try:
        # Abre a imagem de forma otimizada
        img = PIL.Image.open(foto)
        
        # Comando detalhado para a IA ignorar reflexos
        instrucao = (
            "Você é um especialista em leitura de sensores de glicose. "
            "Identifique o valor numérico central e grande nesta imagem. "
            "IMPORTANTE: Ignore reflexos de luz, sombras e pontos brilhantes sobre os números. "
            "Ignore também horários e unidades. Retorne APENAS o número identificado."
        )
        
        # Processamento da imagem pela IA
        response = model.generate_content([instrucao, img])
        
        # Exibe o resultado final de forma clara
        st.success(f"## Valor identificado: {response.text}")
        st.balloons() # Comemoração visual quando funciona!
        
    except Exception as e:
        st.error("Ops! A IA teve dificuldade com esta foto. Tente inclinar levemente o sensor para tirar o reflexo de cima do número.")
