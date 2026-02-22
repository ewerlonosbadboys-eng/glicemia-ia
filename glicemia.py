import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids Profissional", page_icon="🩸", layout="wide")
st.title("🩸 Diário de Glicemia para Médicos")

# --- FUNÇÃO PARA SALVAR ---
def salvar_leitura(valor, categoria):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")
    mes_ano = agora.strftime("%m/%Y")
    
    nova_linha = pd.DataFrame([[data, hora, valor, categoria, mes_ano]], 
                             columns=["Data", "Hora", "Valor", "Categoria", "Mês/Ano"])
    
    arquivo = "historico_glicemia.csv"
    if not os.path.isfile(arquivo):
        nova_linha.to_csv(arquivo, index=False)
    else:
        nova_linha.to_csv(arquivo, mode='a', header=False, index=False)
    st.success(f"✅ Salvo no diário: {valor} mg/dL")

# --- ENTRADA DE DADOS ---
st.subheader("📝 Nova Medição")
col_e1, col_e2 = st.columns(2)

categorias_ordem = [
    "Medida antes do café", "Medida após o café",
    "Medida antes do almoço", "Medida após o almoço",
    "Medida antes da merenda", "Medida antes da janta",
    "Medida após a janta", "Medida madrugada", "Medida Extra"
]

with col_e1:
    valor_manual = st.number_input("Valor:", min_value=0, max_value=600, step=1)
    cat_sel = st.selectbox("Momento:", categorias_ordem)

with col_e2:
    foto = st.camera_input("Foto do Visor")

valor_final = valor_manual
if foto and valor_manual == 0:
    try:
        img = PIL.Image.open(foto)
        response = model.generate_content(["Retorne apenas o número central da glicemia.", img])
        res = "".join(re.findall(r'\d+', response.text))
        if res:
            valor_final = int(res)
            st.info(f"IA detectou: {valor_final}")
    except:
        st.error("Erro na leitura da foto.")

if valor_final > 0:
    st.markdown(f"<h1 style='color:#00FF00;'>{valor_final} mg/dL</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR AGORA"):
        salvar_leitura(valor_final, cat_sel)

st.markdown("---")

# --- GERAÇÃO DO RELATÓRIO ---
st.subheader("📊 Relatório Formato Médico")

if os.path.isfile("historico_glicemia.csv"):
    df = pd.read_csv("historico_glicemia.csv")
    
    # CONSERTO PARA O ERRO KEYERROR: Renomeia colunas antigas se existirem
    df.columns = [c.replace('Data/Hora', 'Data') for c in df.columns]
    if 'Data' not in df.columns and 'Data/Hora' not in df.columns:
         st.warning("O histórico antigo é incompatível. Salve uma nova medida para iniciar o novo formato.")
    else:
        try:
            # Organiza a tabela para o formato de colunas por refeição
            relatorio = df.pivot_table(
                index='Data', 
                columns='Categoria', 
                values='Valor', 
                aggfunc='first'
            ).reset_index()

            # Garante que as colunas apareçam na ordem certa do dia
            colunas_existentes = [c for c in categorias_ordem if c in relatorio.columns]
            relatorio = relatorio.reindex(columns=['Data'] + colunas_existentes)

            st.write("Prévia (Cada linha é um dia):")
            st.dataframe(relatorio, use_container_width=True)

            # Exportar para EXCEL
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                relatorio.to_excel(writer, index=False, sheet_name='Glicemia')
            
            excel_data = output.getvalue()
            st.download_button(
                label="📥 Baixar Relatório para Imprimir (Excel)",
                data=excel_data,
                file_name=f"Glicemia_Medico_{datetime.now().strftime('%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Erro ao organizar tabela: {e}")
            st.write("Tente salvar uma nova medida hoje para corrigir o histórico.")
