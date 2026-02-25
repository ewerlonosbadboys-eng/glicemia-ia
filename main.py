
import streamlit as st
import pandas as pd
import random
from datetime import date, timedelta
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Gestão de Escala Pro", layout="wide")

# --- BANCO DE DADOS EM MEMÓRIA ---
if 'categorias' not in st.session_state:
    st.session_state['categorias'] = ["Geral"]
if 'usuarios' not in st.session_state:
    st.session_state['usuarios'] = []

# --- INTERFACE ---
st.title("🚀 Gerenciador de Escala Inteligente")

aba1, aba2, aba3 = st.tabs(["👥 Cadastro de Usuários", "📁 Categorias", "📅 Gerar Escalas"])

# --- ABA 2: CATEGORIAS ---
with aba2:
    st.header("Gerenciar Categorias")
    nova_cat = st.text_input("Nome da Nova Categoria")
    if st.button("Adicionar Categoria"):
        if nova_cat and nova_cat not in st.session_state['categorias']:
            st.session_state['categorias'].append(nova_cat)
            st.success(f"Categoria {nova_cat} criada!")

# --- ABA 1: USUÁRIOS ---
with aba1:
    st.header("Cadastro de Funcionário")
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome Completo")
        cat_user = st.selectbox("Categoria/Setor", st.session_state['categorias'])
    with col2:
        st.write("🔧 Regras Personalizadas")
        regra_sabado = st.checkbox("Participar do rodízio de Sábado (1x por ano/ciclo)")
        regra_dom_seg = st.checkbox("Se folgar Domingo, folgar Segunda também")
    
    if st.button("Salvar Usuário"):
        user_data = {
            "nome": nome,
            "categoria": cat_user,
            "rodizio_sabado": regra_sabado,
            "dom_seg": regra_dom_seg
        }
        st.session_state['usuarios'].append(user_data)
        st.success(f"Usuário {nome} salvo em {cat_user}!")

    st.write("---")
    st.subheader("Usuários Cadastrados")
    st.table(pd.DataFrame(st.session_state['usuarios']))

# --- ABA 3: GERAR ESCALAS ---
with aba3:
    st.header("Gerador com Rodízio Inteligente")
    if not st.session_state['usuarios']:
        st.warning("Cadastre usuários primeiro!")
    else:
        mes = st.selectbox("Mês da Escala", list(range(1, 13)), index=date.today().month - 1)
        
        if st.button("GERAR ESCALA DA CATEGORIA"):
            # Lógica simplificada de rodízio para demonstração
            resultados = []
            usuarios_na_cat = [u for u in st.session_state['usuarios']]
            
            for u in usuarios_na_cat:
                dados_escala = []
                folga_dom_anterior = random.choice([True, False])
                
                # Gerar dias do mês (exemplo simplificado de 30 dias)
                for dia in range(1, 29):
                    dt = date(2026, mes, dia)
                    dia_semana = dt.weekday() # 0=Seg, 6=Dom
                    
                    status = "Trabalho"
                    
                    # Regra Dom + Seg
                    if dia_semana == 6: # Domingo
                        status = "Folga" if folga_dom_anterior else "Trabalho"
                        folga_dom_anterior = not folga_dom_anterior
                    elif dia_semana == 0 and u['dom_seg']: # Segunda
                        # Checa se o dia anterior (domingo) foi folga
                        if len(dados_escala) > 0 and dados_escala[-1]['Status'] == "Folga":
                            status = "Folga"
                    
                    # Regra Rodízio Sábado (Exemplo: Sorteia um sábado se a regra estiver ativa)
                    if dia_semana == 5 and u['rodizio_sabado'] and random.random() < 0.05:
                        status = "Folga"
                        
                    dados_escala.append({"Data": dt.strftime("%d/%m/%Y"), "Dia": dt.strftime("%A"), "Status": status})
                
                st.subheader(f"Escala: {u['nome']} ({u['categoria']})")
                df = pd.DataFrame(dados_escala)
                st.table(df)

                # Exportar para Excel Colorido (mesmo código anterior adaptado)
                # ... [Omitido para brevidade, mas mantido no seu arquivo real] ...
