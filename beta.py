import streamlit as st
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
import plotly.express as px
import pytz
from openpyxl.styles import PatternFill

# --- CONTROLE DE ACESSO (ADICIONAR NO TOPO) ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

# Se não estiver logado, desenha a tela de login e para o código aqui
if not st.session_state.logado:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.title("🔐 Acesso ao Saúde Kids")
    
    u = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    
    if st.button("Entrar no Sistema"):
        if u == "admin@saude.com" and s == "12345":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Incorreto")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.stop() # Esta linha é o segredo: ela impede que o resto do app apareça

# ================= CONFIGURAÇÕES INICIAIS =================
fuso_br = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Saúde Kids BETA - v17", page_icon="🧪", layout="wide")

# ARQUIVOS DE BANCO DE DADOS
ARQ_G = "dados_glicemia_BETA.csv"
ARQ_N = "dados_nutricao_BETA.csv"
ARQ_R = "config_receita_BETA.csv"

# ================= ESTILO VISUAL =================
st.markdown("""
<style>
.main {background-color: #f8fafc;}
.card { background-color: white; padding: 25px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px; }
.dose-alerta { background-color: #f0fdf4; padding: 20px; border-radius: 12px; border: 2px solid #16a34a; text-align: center; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ================= CORES COM PRIORIDADE =================
def cor_glicemia(v):
    if v == "-" or pd.isna(v): return ""
    try:
        n = int(str(v).split(" ")[0])
        if n < 70:
            return 'background-color: #FFFFE0; color: black'
        elif n > 180:
            return 'background-color: #FFB6C1; color: black'
        elif n > 140:
            return 'background-color: #FFFFE0; color: black'
        else:
            return 'background-color: #90EE90; color: black'
    except:
        return ""

# ================= FUNÇÕES DE APOIO =================
def carregar(arq):
    return pd.read_csv(arq) if os.path.exists(arq) else pd.DataFrame()

ALIMENTOS = {
    "Pão Francês": [28, 4, 1], "Leite (200ml)": [10, 6, 6],
    "Arroz": [15, 1, 0], "Feijão": [14, 5, 0],
    "Frango": [0, 23, 5], "Ovo": [1, 6, 5],
    "Banana": [22, 1, 0], "Maçã": [15, 0, 0]
}

def calcular_insulina_automatica(valor, momento):
    df_r = carregar(ARQ_R)
    if df_r.empty:
        return "Configurar Receita", "⚠️ Vá na aba 'Receita'"
    
    r = df_r.iloc[0]
    prefixo = "manha" if momento in ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda"] else "noite"
    
    if valor < 70: return "0 UI", "⚠️ Hipoglicemia! Tratar agora."
    elif 70 <= valor <= 200: dose = r[f'{prefixo}_f1']
    elif 201 <= valor <= 400: dose = r[f'{prefixo}_f2']
    else: dose = r[f'{prefixo}_f3']
    
    return f"{int(dose)} UI", f"Tabela {prefixo.capitalize()}"

# ================= DEFINIÇÃO DAS ABAS (CÂMERA REMOVIDA) =================
t1, t2, t3 = st.tabs(["📊 Glicemia", "🍽️ Alimentação", "⚙️ Receita"])

# --- ABA 1: GLICEMIA ---
with t1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    dfg = carregar(ARQ_G)

    with c1:
        st.subheader("📝 Novo Registro")
        v = st.number_input("Valor da Glicemia (mg/dL):", min_value=0, value=100)
        m = st.selectbox("Momento:", ["Antes Café", "Após Café", "Antes Almoço", "Após Almoço", "Antes Merenda", "Antes Janta", "Após Janta", "Madrugada"])
        
        dose_sug, ref_tab = calcular_insulina_automatica(v, m)
        st.markdown(f"""<div class="dose-alerta">
            <p style="margin:0; color:#166534;">Dose Sugerida:</p>
            <h1 style="margin:0; color:#15803d;">{dose_sug}</h1>
            <small>{ref_tab}</small>
        </div>""", unsafe_allow_html=True)

        if st.button("💾 Salvar Registro"):
            agora = datetime.now(fuso_br)
            novo = pd.DataFrame([[agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M"), v, m, dose_sug]],
                                columns=["Data", "Hora", "Valor", "Momento", "Dose"])
            pd.concat([dfg, novo], ignore_index=True).to_csv(ARQ_G, index=False)
            st.success("Salvo com sucesso!")
            st.rerun()

    with c2:
        if not dfg.empty:
            dfg['DataHora'] = pd.to_datetime(dfg['Data'] + " " + dfg['Hora'], dayfirst=True)
            fig = px.line(dfg.tail(10), x='DataHora', y='Valor', markers=True, title="Evolução Recente")
            st.plotly_chart(fig, use_container_width=True)

    if not dfg.empty:
        st.subheader("📋 Histórico")
        st.dataframe(dfg.tail(10), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 2: ALIMENTAÇÃO ---
with t2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🍽️ Controle de Nutrientes")
    ca1, ca2 = st.columns(2)

    with ca1:
        escolha = st.multiselect("Alimentos:", list(ALIMENTOS.keys()))
        carb = sum([ALIMENTOS[i][0] for i in escolha])
        prot = sum([ALIMENTOS[i][1] for i in escolha])
        gord = sum([ALIMENTOS[i][2] for i in escolha])

        st.info(f"Totais: Carboidratos: {carb}g | Proteínas: {prot}g | Gorduras: {gord}g")

        if st.button("💾 Salvar Alimentação"):
            agora = datetime.now(fuso_br)
            txt = f"{', '.join(escolha)} (C:{carb} P:{prot} G:{gord})"
            novo_n = pd.DataFrame([[agora.strftime("%d/%m/%Y"), txt, carb, prot, gord]],
                                 columns=["Data", "Info", "C", "P", "G"])
            pd.concat([carregar(ARQ_N), novo_n], ignore_index=True).to_csv(ARQ_N, index=False)
            st.rerun()

    with ca2:
        dfn = carregar(ARQ_N)
        if not dfn.empty:
            fig2 = px.pie(values=[dfn['C'].sum(), dfn['P'].sum(), dfn['G'].sum()],
                         names=['Carbo', 'Prot', 'Gord'], title="Distribuição Nutricional Total")
            st.plotly_chart(fig2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- ABA 3: RECEITA (Antiga Configuração) ---
with t3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚙️ Configurar Doses do Médico (Receita)")
    
    df_r = carregar(ARQ_R)
    v_at = df_r.iloc[0] if not df_r.empty else {'manha_f1':0, 'manha_f2':0, 'manha_f3':0, 'noite_f1':0, 'noite_f2':0, 'noite_f3':0}
    
    col_m, col_n = st.columns(2)
    with col_m:
        st.info("**☀️ Café / Almoço / Merenda**")
        mf1 = st.number_input("Dose 70-200:", value=int(v_at['manha_f1']), key="mf1")
        mf2 = st.number_input("Dose 201-400:", value=int(v_at['manha_f2']), key="mf2")
        mf3 = st.number_input("Dose > 400:", value=int(v_at['manha_f3']), key="mf3")
    with col_n:
        st.info("**🌙 Jantar / Madrugada**")
        nf1 = st.number_input("Dose 70-200:", value=int(v_at['noite_f1']), key="nf1")
        nf2 = st.number_input("Dose 201-400:", value=int(v_at['noite_f2']), key="nf2")
        nf3 = st.number_input("Dose > 400:", value=int(v_at['noite_f3']), key="nf3")
        
    if st.button("💾 Salvar Receita"):
        pd.DataFrame([{'manha_f1':mf1, 'manha_f2':mf2, 'manha_f3':mf3, 'noite_f1':nf1, 'noite_f2':nf2, 'noite_f3':nf3}]).to_csv(ARQ_R, index=False)
        st.success("Receita atualizada!")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ================= EXCEL COLORIDO =================
def gerar_excel_colorido(df_glic, df_nutri):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df_glic.empty:
            df_glic = df_glic.copy()
            df_glic['Exibe'] = df_glic['Valor'].astype(str) + " (" + df_glic['Hora'] + ")"
            pivot = df_glic.pivot_table(index='Data', columns='Momento', values='Exibe', aggfunc='last').fillna("-")
            pivot.to_excel(writer, sheet_name='Glicemia')
            ws = writer.sheets['Glicemia']

            v_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
            a_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")
            r_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")

            for row in ws.iter_rows(min_row=2, min_col=2):
                for cell in row:
                    if cell.value and cell.value != "-":
                        try:
                            val = int(str(cell.value).split(" ")[0])
                            if val < 70: cell.fill = a_fill
                            elif val > 180: cell.fill = r_fill
                            elif val > 140: cell.fill = a_fill
                            else: cell.fill = v_fill
                        except: pass

        if not df_nutri.empty:
            df_nutri.to_excel(writer, index=False, sheet_name='Alimentacao')
    return output.getvalue()

st.markdown("---")
if st.button("📥 BAIXAR RELATÓRIO EXCEL"):
    dfg = carregar(ARQ_G)
    dfn = carregar(ARQ_N)
    if not dfg.empty:
        excel_data = gerar_excel_colorido(dfg, dfn)

        # =========================================================
# BLOCO NOVO: TELA DE LOGIN COM O MESMO LAYOUT
# (Cole no final do arquivo, sem apagar nada acima)
# =========================================================

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    # Usando o mesmo estilo de 'card' que você já tem no código
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.title("🔐 Acesso ao Saúde Kids")
    
    # Criando colunas para o formulário ficar centralizado
    col_login, _ = st.columns([1, 1])
    
    with col_login:
        user_input = st.text_input("Usuário (E-mail)")
        pass_input = st.text_input("Senha", type="password")
        
        if st.button("Entrar no Sistema"):
            # Aqui você define seu usuário e senha padrão
            if user_input == "admin@saude.com" and pass_input == "12345":
                st.session_state.logado = True
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
                
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Este comando impede que o código antigo (que está acima) 
    # apareça antes da pessoa logar
    st.stop() 

# O seu código antigo que está acima deste bloco passará a ser 
# exibido somente quando st.session_state.logado for True.
    st.download_button("Clique para Baixar", excel_data, file_name="Relatorio_Medico.xlsx")
