import streamlit as st
import google.generativeai as genai
import PIL.Image
import re

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Leitor de Glicemia", page_icon="🩸")
st.title("🩸 Glicemia Kids Inteligente")

# Opção de entrada manual sempre visível para emergências
valor_manual = st.number_input("Se a IA falhar, digite o valor aqui:", min_value=0, max_value=600, step=1)
if valor_manual > 0:
    st.markdown(f"<h1 style='text-align: center; color: #00ff00; font-size: 80px;'>{valor_manual} mg/dL</h1>", unsafe_allow_html=True)

st.markdown("---")

# Interface da Câmera
foto = st.camera_input("Ou tente tirar a foto do visor")

if foto:
    try:
        img = PIL.Image.open(foto)
        st.info("A IA está tentando ler o número...")
        
        prompt = (
            "Esta é uma tela de medidor Match II. Ignore reflexos. "
            "Localize o maior número central. Responda APENAS o número."
        )
        
        response = model.generate_content([prompt, img])
        
        # Filtra apenas os números
        resultado = "".join(re.findall(r'\d+', response.text))
        
        if resultado and 20 <= int(resultado) <= 600:
            st.markdown(f"<h1 style='text-align: center; color: #00ff00; font-size: 100px;'>{resultado}</h1>", unsafe_allow_html=True)
            st.success("Identificado pela IA!")
            st.balloons()
        else:
            st.warning("IA não conseguiu ler com clareza. Por favor, use o campo de digitação manual acima.")
            
    except Exception as e:
        st.error("Erro na leitura automática. Use a digitação manual acima.")
