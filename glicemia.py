import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz

# Fuso Horário Brasil
fuso_br = pytz.timezone('America/Sao_Paulo')

st.set_page_config(page_title="Monitoramento Saúde Kids", page_icon="🩸", layout="wide")

# MUDAMOS OS NOMES AQUI PARA FORÇAR O RESET E LIMPAR O ERRO
ARQUIVO_GLIC = "historico_glicemia_novo_v4.csv"
ARQUIVO_NUTRI = "historico_nutricao_novo_v4.csv"

# Banco de Dados de Alimentos
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Pão de Forma (1 fatia)": [12, 2, 1],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz (3 colheres)": [15, 1.5, 0],
    "Feijão (1 concha)": [14, 5, 0.5],
    "Frango Grelhado": [0, 23, 5],
    "Ovo Cozido": [1, 6, 5],
    "Banana (1 un)": [22, 1, 0],
    "Maçã (1 un)": [15, 0, 0]
}

def carregar_dados(arq):
    if os.path.exists(arq):
        return pd.read_csv(arq)
    return pd.DataFrame()

st.title("🩸 Painel de Controle: Glicemia + Alimentação")

tab1, tab2 = st.tabs(["📊 Glicemia", "🍽️ Alimentação"])

# --- ABA 1: GLICEMIA ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        v_glic = st.number_input("Valor da Glicemia (mg/dL):", min_value=0)
        momento = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        if st.button("💾 Salvar Glicemia"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v_glic, momento]], 
                                columns=["Data", "Hora", "Valor", "Categoria"])
            df_atual = carregar_dados(ARQUIVO_GLIC)
            pd.concat([df_atual, novo], ignore_index=True).to_csv(ARQUIVO_GLIC, index=False)
            st.success("Glicemia registrada!")
            st.rerun()
    with col2:
        df_g = carregar_dados(ARQUIVO_GLIC)
        if not df_g.empty:
            hoje = datetime.now(fuso_br).strftime("%d/%m/%Y")
            df_h = df_g[df_g['Data'] == hoje].sort_values('Hora')
            if not df_h.empty:
                st.plotly_chart(px.line(df_h, x='Hora', y='Valor', title="Evolução de Hoje", markers=True))

# --- ABA 2: ALIMENTAÇÃO ---
with tab2:
    st.subheader("Diário Nutricional")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        refeicao = st.selectbox("Refeição:", ["Café", "Lanche", "Almoço", "Merenda", "Janta", "Ceia"])
        escolhidos = st.multiselect("O que foi consumido?", list(ALIMENTOS.keys()))
        
        # Cálculos
        c = sum([ALIMENTOS[i][0] for i in escolhidos])
        p = sum([ALIMENTOS[i][1] for i in escolhidos])
        g = sum([ALIMENTOS[i][2] for i in escolhidos])
        
        st.info(f"Totais: Carbo {c}g | Prot {p}g | Gord {g}g")
        
        if st.button("💾 Salvar Refeição"):
            agora = datetime.now(fuso_br)
            texto_medico = f"{', '.join(escolhidos)} (C:{c}g P:{p}g G:{g}g)"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), refeicao, texto_medico, c, p, g]], 
                                  columns=["Data", "Ref", "Conteudo", "C", "P", "G"])
            df_n_atual = carregar_dados(ARQUIVO_NUTRI)
            pd.concat([df_n_atual, novo_n], ignore_index=True).to_csv(ARQUIVO_NUTRI, index=False)
            st.success("Refeição salva!")
            st.rerun()
            
    with col_a2:
        df_n = carregar_dados(ARQUIVO_NUTRI)
        if not df_n.empty:
            # Gráfico de Pizza Nutricional
            fig_pizza = px.pie(values=[df_n['C'].sum(), df_n['P'].sum(), df_n['G'].sum()], 
                               names=['Carboidratos', 'Proteínas', 'Gorduras'], 
                               title="Equilíbrio Nutricional Geral")
            st.plotly_chart(fig_pizza, use_container_width=True)

# --- BOTÃO DE DOWNLOAD EXCEL (DUAS ABAS) ---
st.markdown("---")
if st.button("📥 Baixar Relatório Médico Completo"):
    df_g = carregar_dados(ARQUIVO_GLIC)
    df_n = carregar_dados(ARQUIVO_NUTRI)
    
    if not df_g.empty:
        # Organiza aba Glicemia
        df_g['Exibe'] = df_g['Valor'].astype(str) + " (" + df_g['Hora'] + ")"
        rel_g = df_g.pivot_table(index='Data', columns='Categoria', values='Exibe', aggfunc='last').reset_index()
        
        # Organiza aba Alimentação
        rel_n = df_n.pivot_table(index='Data', columns='Ref', values='Conteudo', aggfunc='last').reset_index() if not df_n.empty else pd.DataFrame()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            rel_g.to_excel(writer, index=False, sheet_name='Glicemia')
            if not rel_n.empty:
                rel_n.to_excel(writer, index=False, sheet_name='Alimentacao')
        
        st.download_button("Clique para baixar o Excel", output.getvalue(), file_name="Relatorio_Medico_Completo.xlsx")
