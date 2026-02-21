import streamlit as st
import google.generativeai as genai
import PIL.Image
import re

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia", page_icon="🩸")
st.title("🩸 Leitor de Glicemia")

foto = st.camera_input("Tire a foto do visor")

if foto:
    try:
        img = PIL.Image.open(foto)
        st.info("Lendo visor...")
        
        # Comando simplificado: pede para a IA listar todos os números que vê
        prompt = "Liste todos os números que aparecem nesta tela de medidor de saúde, especialmente o maior deles."
        
        response = model.generate_content([prompt, img])
        texto_ia = response.text
        
        # Procura por todos os números no texto da IA e pega o maior
        numeros = re.findall(r'\d+', texto_ia)
        
        if numeros:
            # Converte para número e pega o maior valor (que é a glicemia)
            valor_glicemia = max([int(n) for n in numeros if len(n) <= 3])
            
            st.markdown(f"<h1 style='text-align: center; color: #00ff00; font-size: 80px;'>{valor_glicemia}</h1>", unsafe_allow_html=True)
            st.success("Leitura concluída!")
        else:
            st.warning("Não consegui isolar o número. Tente tirar a foto sem o brilho da luz em cima do visor.")
            
    except Exception as e:
        st.error("Erro ao processar. Tente novamente.")
