import streamlit as st
import google.generativeai as genai
import PIL.Image
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from openpyxl.styles import PatternFill
import plotly.express as px # Nova biblioteca para o gráfico

# Configuração da IA
genai.configure(api_key="gen-lang-client-0937121329")
model = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="Glicemia Kids", page_icon="🩸", layout="wide")
st.title("🩸 Diário com Gráfico de Picos")

ARQUIVO = "historico_glicemia.csv"

def carregar_dados():
    if os.path.isfile(ARQUIVO):
        df = pd.read_csv(ARQUIVO)
        # Padroniza colunas e garante que Hora existe (usando agora se faltar)
        if 'Hora' not in df.columns: df['Hora'] = datetime.now().strftime("%H:%M")
        df.columns = [c.replace('Valor (mg/dL)', 'Valor').replace('Data/Hora', 'Data') for c in df.columns]
        return df
    return pd.DataFrame(columns=["Data", "Hora", "Valor", "Categoria", "Mes_Ano"])

def salvar_csv(df):
    df.to_csv(ARQUIVO, index=False)

# --- ENTRADA DE DADOS ---
categorias_ordem = ["Medida antes do café", "Medida após o café", "Medida antes do almoço", "Medida após o almoço", "Medida antes da merenda", "Medida antes da janta", "Medida após a janta", "Medida madrugada", "Medida Extra"]

st.subheader("📝 Nova Medição")
col1, col2 = st.columns(2)
with col1:
    valor_manual = st.number_input("Valor:", min_value=0, max_value=600, step=1)
    cat_sel = st.selectbox("Momento:", categorias_ordem)
with col2:
    foto = st.camera_input("Foto")

valor_final = valor_manual
if foto and valor_manual == 0:
    try:
        img = PIL.Image.open(foto); res = "".join(re.findall(r'\d+', model.generate_content(["Número glicemia", img]).text))
        if res: valor_final = int(res)
    except: st.error("Erro foto")

if valor_final > 0:
    cor = "yellow" if valor_final <= 69 else "green" if valor_final <= 200 else "red"
    st.markdown(f"<h1 style='color:{cor}; text-align:center;'>{valor_final} mg/dL</h1>", unsafe_allow_html=True)
    if st.button("💾 SALVAR"):
        agora = datetime.now()
        df = carregar_dados()
        nova = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), valor_final, cat_sel, agora.strftime("%m/%Y")]], columns=["Data", "Hora", "Valor", "Categoria", "Mes_Ano"])
        df = pd.concat([df, nova], ignore_index=True)
        salvar_csv(df); st.rerun()

st.markdown("---")

# --- GRÁFICO DE PICOS (24 HORAS) ---
df = carregar_dados()
if not df.empty:
    st.subheader("📈 Análise de Picos (Hoje)")
    hoje = datetime.now().strftime("%d/%m/%Y")
    df_hoje = df[df['Data'] == hoje].copy()
    
    if not df_hoje.empty:
        # Ordena por hora para o gráfico fazer sentido
        df_hoje = df_hoje.sort_values(by='Hora')
        
        fig = px.line(df_hoje, x='Hora', y='Valor', title=f"Glicemia em {hoje}",
                      markers=True, line_shape="spline",
                      color_discrete_sequence=["#00FF00"])
        
        # Adiciona faixas de referência no gráfico
        fig.add_hline(y=70, line_dash="dot", line_color="yellow", annotation_text="Limite Baixo")
        fig.add_hline(y=200, line_dash="dot", line_color="red", annotation_text="Limite Alto")
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Ainda não há medidas salvas hoje para gerar o gráfico.")

st.markdown("---")

# --- EDIÇÃO E EXCEL ---
if not df.empty:
    with st.expander("⚙️ Editar/Excluir Medidas"):
        df_l = df.copy(); df_l['Sel'] = df_l['Data'] + " " + df_l['Hora'] + " - " + df_l['Categoria']
        escolha = st.selectbox("Selecione:", df_l['Sel'].tolist(), index=len(df_l)-1)
        idx = df_l[df_l['Sel'] == escolha].index[0]
        c1, c2, c3 = st.columns(3)
        nv = c1.number_input("Novo Valor:", value=int(df.at[idx, 'Valor']))
        nc = c2.selectbox("Nova Categoria:", categorias_ordem, index=categorias_ordem.index(df.at[idx, 'Categoria']))
        if c3.button("🆙 Atualizar"):
            df.at[idx, 'Valor'] = nv; df.at[idx, 'Categoria'] = nc; salvar_csv(df); st.rerun()
        if c3.button("🗑️ Excluir"):
            df = df.drop(idx); salvar_csv(df); st.rerun()

    # Relatório Médico
    try:
        rel = df.pivot_table(index='Data', columns='Categoria', values='Valor', aggfunc='last').reset_index()
        col_f = ['Data'] + [c for c in categorias_ordem if c in rel.columns]
        rel = rel.reindex(columns=col_f)
        st.subheader("📊 Relatório para o Médico")
        st.dataframe(rel, use_container_width=True)
        
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as wr:
            rel.to_excel(wr, index=False, sheet_name='Glicemia')
            ws = wr.sheets['Glicemia']
            f_am, f_vd, f_vm = PatternFill("solid", start_color="FFFF00"), PatternFill("solid", start_color="92D050"), PatternFill("solid", start_color="FF0000")
            for r in range(2, ws.max_row + 1):
                for c in range(2, ws.max_column + 1):
                    cel = ws.cell(row=r, column=c)
                    if cel.value:
                        v = float(cel.value)
                        if v <= 69: cel.fill = f_am
                        elif v <= 200: cel.fill = f_vd
                        else: cel.fill = f_vm
        st.download_button("📥 Baixar Excel Colorido", out.getvalue(), file_name="Glicemia_Kids.xlsx")
    except: pass
