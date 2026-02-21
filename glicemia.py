import streamlit as st
import google.generativeai as genai
import PIL.Image
import re

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Leitor de Glicemia", page_icon="🩸")
st.title("🩸 Leitor de Glicemia")

foto = st.camera_input("Tire a foto do visor")

if foto:
    try:
        img = PIL.Image.open(foto)
        st.info("Buscando número principal...")
        
        # O SEGREDO: Instrução para descrever a imagem e extrair o MAIOR valor
        prompt = (
            "Analise esta imagem de um medidor Match II. "
            "Existem vários números na tela (hora, data), mas eu quero apenas o valor da glicemia. "
            "O valor da glicemia é o número MAIOR e mais centralizado. "
            "Ignore brilhos ou reflexos brancos. "
            "Retorne apenas os dígitos do número maior."
        )
        
        response = model.generate_content([prompt, img])
        
        # Filtra apenas os números da resposta da IA
        numeros_encontrados = re.findall(r'\d+', response.text)
        
        if numeros_encontrados:
            # Pega o maior número da lista (que será a glicemia)
            resultado = max(numeros_encontrados, key=len)
            st.markdown(f"<h1 style='text-align: center; color: #00ff00; font-size: 100px;'>{resultado}</h1>", unsafe_allow_html=True)
            st.success("Valor identificado!")
        else:
            st.warning("IA não conseguiu ler. Tente tirar a foto um pouco mais de longe ou de lado.")
            
    except Exception as e:
        st.error("Erro na leitura. Tente novamente.")
