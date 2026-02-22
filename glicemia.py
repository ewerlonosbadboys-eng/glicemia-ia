import streamlit as st
import pandas as pd
from datetime import datetime
import os, pytz
from io import BytesIO

# Configuração e Fuso
fuso = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saude Kids v47", layout="wide")

# Ficheiros e Colunas Oficiais do Relatório
ARQ = "dados_saude_v47.csv"
COL_RELATORIO = ["Data", "Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"]

def load_data():
    if os.path.exists(ARQ):
        return pd.read_csv(ARQ)
    return pd.DataFrame(columns=["Data", "Hora", "Valor", "Momento"])

def style_excel(v):
    if v == "-" or pd.isna(v): return ""
    try:
        val = int(str(v).split(" ")[0])
        if val < 70: return 'background-color: #FFFF99' # Amarelo (Hipo)
        if val > 180: return 'background-color: #FFCCCC' # Vermelho (Hiper)
        return 'background-color: #CCFFCC' # Verde (Normal)
    except: return ""

st.title("🩸 Monitorização Saude Kids v47")
t1, t2 = st.tabs(["Registos", "Relatório Excel"])

with t1:
    v_g = st.number_input("Valor da Glicemia:", min_value=0)
    m_g = st.selectbox("Momento:", COL_RELATORIO[1:]) # Ignora a coluna 'Data'
    if st.button("Salvar Glicemia"):
        agora = datetime.now(fuso)
        novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_g, m_g]], 
                            columns=["Data", "Hora", "Valor", "Momento"])
        pd.concat([load_data(), novo], ignore_index=True).to_csv(ARQ, index=False)
        st.success("Guardado!")
        st.rerun()
    
    df = load_data()
    if not df.empty:
        # Cria a tabela visual igual à imagem do Excel enviada
        df['Exibe'] = df['Valor'].astype(str) + " (" + df['Hora'] + ")"
        tabela_medica = df.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last')
        # Garante que todas as colunas do relatório apareçam, mesmo vazias
        for c in COL_RELATORIO[1:]:
            if c not in tabela_medica.columns: tabela_medica[c] = "-"
        
        st.subheader("Pré-visualização do Relatório")
        st.dataframe(tabela_medica[COL_RELATORIO[1:]].fillna("-").style.applymap(style_excel), use_container_width=True)

with t2:
    st.write("Gere aqui o ficheiro para enviar ao médico.")
    if st.button("📥 Exportar Relatório Formato Excel"):
        df = load_data()
        if not df.empty:
            df['Exibe'] = df['Valor'].astype(str) + " (" + df['Hora'] + ")"
            # Organiza os dados no formato exato da sua imagem
            final_df = df.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            # Ordena as colunas conforme solicitado
            colunas_existentes = [c for c in COL_RELATORIO[1:] if c in final_df.columns]
            final_df = final_df[colunas_existentes]
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, sheet_name='Relatorio_Glicemia')
            
            st.download_button("Clique para Baixar Excel", output.getvalue(), file_name="Relatorio_Glicemia_Kids.xlsx")
        else:
            st.warning("Sem dados para exportar.")
