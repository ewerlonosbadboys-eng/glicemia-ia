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
st.title("🩸 Diário de Glicemia com Alertas Coloridos")

# --- FUNÇÃO PARA SALVAR ---
def salvar_leitura(valor, categoria):
    agora = datetime.now()
    data = agora.strftime("%d/%m/%Y")
    mes_ano = agora.strftime("%m/%Y")
    nova_linha = pd.DataFrame([[data, valor, categoria, mes_ano]], 
                             columns=["Data", "Valor", "Categoria", "Mes_Ano"])
    arquivo = "historico_glicemia.csv"
    if not os.path.isfile(arquivo):
        nova_linha.to_csv(arquivo, index=False)
    else:
        nova_linha.to_csv(arquivo, mode='a', header=False, index=False)
    st.success(f"✅ Salvo: {valor} mg/dL")

# --- INTERFACE DE ENTRADA ---
categorias_ordem = [
    "Medida antes do café", "Medida após o café",
    "Medida antes do almoço", "Medida após o almoço",
    "Medida antes da merenda", "Medida antes da janta",
    "Medida após a janta", "Medida madrugada", "Medida Extra"
]

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
    # Mostra a cor no App também
    cor_txt = "yellow" if valor_final <= 69 else "green" if valor_final <= 200 else "red"
    st.markdown(f"<h1 style='color:{cor_txt}; text-align:center;'>{valor_final} mg/dL</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR NO RELATÓRIO EXCEL"):
        salvar_leitura(valor_final, cat_sel)

st.markdown("---")

# --- RELATÓRIO PARA O MÉDICO ---
if os.path.isfile("historico_glicemia.csv"):
    try:
        df = pd.read_csv("historico_glicemia.csv")
        # Padroniza nomes para evitar erros de versões antigas
        df.columns = [c.replace('Valor (mg/dL)', 'Valor').replace('Data/Hora', 'Data') for c in df.columns]
        
        # Cria a tabela igual à sua imagem (Data na linha, Refeição na coluna)
        relatorio = df.pivot_table(index='Data', columns='Categoria', values='Valor', aggfunc='last').reset_index()
        col_f = ['Data'] + [c for c in categorias_ordem if c in relatorio.columns]
        relatorio = relatorio.reindex(columns=col_f)

        st.subheader("📊 Prévia do Relatório Mensal")
        st.dataframe(relatorio, use_container_width=True)

        # GERAR EXCEL COM CORES AUTOMÁTICAS
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            relatorio.to_excel(writer, index=False, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']

            # Cores: Amarelo (Hipo), Verde (Ok), Vermelho (Alta)
            fill_am = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
            fill_vd = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
            fill_vm = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")

            for r in range(2, ws.max_row + 1):
                for c in range(2, ws.max_column + 1):
                    celula = ws.cell(row=r, column=c)
                    if celula.value is not None:
                        try:
                            v = float(celula.value)
                            if v <= 69: celula.fill = fill_am
                            elif v <= 200: celula.fill = fill_vd
                            else: celula.fill = fill_vm
                        except: pass

        st.download_button("📥 Baixar Relatório Excel Colorido", output.getvalue(), 
                         file_name=f"Glicemia_{datetime.now().strftime('%m_%Y')}.xlsx")
    except: st.warning("Adicione uma medida para atualizar o relatório.")
    
    if st.button("🗑️ Limpar tudo (Usar apenas se der erro)"):
        os.remove("historico_glicemia.csv")
        st.rerun()
