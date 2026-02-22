import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from openpyxl.styles import PatternFill

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸", layout="wide")
st.title("🩸 Diário de Glicemia (Com Edição)")

# --- ARQUIVO DE DADOS ---
ARQUIVO = "historico_glicemia.csv"

def carregar_dados():
    if os.path.isfile(ARQUIVO):
        df = pd.read_csv(ARQUIVO)
        # Padronização de colunas
        df.columns = [c.replace('Valor (mg/dL)', 'Valor').replace('Data/Hora', 'Data') for c in df.columns]
        return df
    return pd.DataFrame(columns=["Data", "Valor", "Categoria", "Mes_Ano"])

def salvar_csv(df):
    df.to_csv(ARQUIVO, index=False)

# --- INTERFACE DE ENTRADA ---
categorias_ordem = [
    "Medida antes do café", "Medida após o café",
    "Medida antes do almoço", "Medida após o almoço",
    "Medida antes da merenda", "Medida antes da janta",
    "Medida após a janta", "Medida madrugada", "Medida Extra"
]

st.subheader("📝 Nova Medição")
col1, col2 = st.columns(2)
with col1:
    valor_manual = st.number_input("Digite o Valor:", min_value=0, max_value=600, step=1)
    cat_sel = st.selectbox("Momento da Medida:", categorias_ordem)
with col2:
    foto = st.camera_input("Tirar Foto do Sensor")

valor_final = valor_manual
if foto and valor_manual == 0:
    try:
        img = PIL.Image.open(foto)
        response = model.generate_content(["Retorne apenas o número da glicemia.", img])
        res = "".join(re.findall(r'\d+', response.text))
        if res: valor_final = int(res)
    except: st.error("Erro na foto.")

if valor_final > 0:
    cor_txt = "yellow" if valor_final <= 69 else "green" if valor_final <= 200 else "red"
    st.markdown(f"<h1 style='color:{cor_txt}; text-align:center;'>{valor_final} mg/dL</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR NO RELATÓRIO"):
        agora = datetime.now()
        df = carregar_dados()
        nova_linha = pd.DataFrame([[agora.strftime("%d/%m/%Y"), valor_final, cat_sel, agora.strftime("%m/%Y")]], 
                                 columns=["Data", "Valor", "Categoria", "Mes_Ano"])
        df = pd.concat([df, nova_linha], ignore_index=True)
        salvar_csv(df)
        st.success("✅ Salvo!")
        st.rerun()

st.markdown("---")

# --- SEÇÃO DE EDIÇÃO ---
df = carregar_dados()
if not df.empty:
    st.subheader("⚙️ Editar ou Excluir Medidas")
    st.write("Se salvou algo errado, corrija abaixo:")
    
    # Criamos uma lista de textos para o usuário escolher qual linha editar
    df_lista = df.copy()
    df_lista['Seleção'] = df_lista['Data'] + " - " + df_lista['Categoria'] + " (" + df_lista['Valor'].astype(str) + ")"
    
    linha_para_editar = st.selectbox("Escolha a medida para alterar:", df_lista['Seleção'].tolist(), index=len(df_lista)-1)
    idx = df_lista[df_lista['Seleção'] == linha_para_editar].index[0]
    
    col_ed1, col_ed2, col_ed3 = st.columns([2, 2, 1])
    with col_ed1:
        novo_valor = st.number_input("Corrigir Valor:", value=int(df.at[idx, 'Valor']))
    with col_ed2:
        nova_cat = st.selectbox("Corrigir Momento:", categorias_ordem, index=categorias_ordem.index(df.at[idx, 'Categoria']))
    with col_ed3:
        st.write("Ação")
        if st.button("🆙 ATUALIZAR"):
            df.at[idx, 'Valor'] = novo_valor
            df.at[idx, 'Categoria'] = nova_cat
            salvar_csv(df)
            st.success("Alterado!")
            st.rerun()
        if st.button("🗑️ EXCLUIR"):
            df = df.drop(idx)
            salvar_csv(df)
            st.warning("Excluído!")
            st.rerun()

st.markdown("---")

# --- RELATÓRIO EXCEL (O mesmo que o médico gosta) ---
if not df.empty:
    try:
        relatorio = df.pivot_table(index='Data', columns='Categoria', values='Valor', aggfunc='last').reset_index()
        col_f = ['Data'] + [c for c in categorias_ordem if c in relatorio.columns]
        relatorio = relatorio.reindex(columns=col_f)

        st.subheader("📊 Relatório para Impressão")
        st.dataframe(relatorio, use_container_width=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            relatorio.to_excel(writer, index=False, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']
            fill_am = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
            fill_vd = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
            fill_vm = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")

            for r in range(2, ws.max_row + 1):
                for c in range(2, ws.max_column + 1):
                    celula = ws.cell(row=r, column=c)
                    if celula.value:
                        v = float(celula.value)
                        if v <= 69: celula.fill = fill_am
                        elif v <= 200: celula.fill = fill_vd
                        else: celula.fill = fill_vm

        st.download_button("📥 Baixar Excel Colorido", output.getvalue(), file_name="Glicemia_Kids.xlsx")
    except:
        st.info("Organizando dados...")
