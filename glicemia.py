import streamlit as st
import google.generativeai as genai
import PIL.Image

# Configuração da API do Google (Sua chave já está aqui)
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

# Configuração da página do Aplicativo
st.set_page_config(page_title="Glicemia Kids", page_icon="🩸")
st.title("🩸 Glicemia Kids Inteligente")
st.write("Tire uma foto nítida do sensor para realizar a leitura.")

# Interface da Câmera
foto = st.camera_input("Tire foto do sensor")

if foto:
    st.info("A IA está analisando a imagem... Por favor, aguarde.")
    try:
        # Abre a foto tirada pelo celular
        img = PIL.Image.open(foto)
        
        # Comando aprimorado para a IA ser mais precisa
        instrucao = (
            "Você é um especialista em leitura de sensores de glicose. "
            "Identifique o valor numérico grande central nesta imagem. "
            "Ignore reflexos de luz, sombras ou outros números menores (como horários). "
            "Retorne APENAS o número principal que você vê no visor."
        )
        
        # Solicita a análise ao Google Gemini
        response = model.generate_content([instrucao, img])
        
        # Exibe o resultado com destaque
        st.success(f"### Valor identificado: {response.text}")
        
    except Exception as e:
        st.error("Ops! A IA não conseguiu ler esta foto. Tente novamente com menos reflexo ou mais luz.")
        # Opcional: st.write(e) # Use esta linha apenas se precisar ver o erro técnico
