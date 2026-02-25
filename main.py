import streamlit as st
import pandas as pd
from datetime import datetime
import io

# 1. Configuração da página
st.set_page_config(page_title="Gestor de Escala Pro", layout="wide")

# 2. Função de Login
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Gerenciador de Escala - Login")
        user = st.text_input("Usuário", key="username")
        pw = st.text_input("Senha", type="password", key="password")
        if st.button("Entrar"):
            if user == "admin" and pw == "123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return False
    return True

if check_password():
    # Inicialização da memória
    if 'db_users' not in st.session_state:
        st.session_state['db_users'] = []
    if 'db_cats' not in st.session_state:
        st.session_state['db_cats'] = ["Geral"]

    st.sidebar.button("Sair", on_click=lambda: st.session_state.clear())
    st.title("🚀 Gerenciador de Escala Inteligente")

    # Abas
    aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📁 Categorias", "📅 Gerar Escala"])

    with aba2:
        st.subheader("Gerenciar Setores")
        nova_cat = st.text_input("Nome do novo setor")
        if st.button("Salvar Categoria"):
            if nova_cat and nova_cat not in st.session_state['db_cats']:
                st.session_state['db_cats'].append(nova_cat)
                st.success("Categoria adicionada!")

    with aba1:
        st.subheader("Cadastro de Equipe")
        nome = st.text_input("Nome do Funcionário")
        setor = st.selectbox("Setor", st.session_state['db_cats'])
        
        col1, col2 = st.columns(2)
        r_sabado = col1.checkbox("Rodízio de Sábado")
        r_dom_seg = col2.checkbox("Folga Casada (Dom+Seg)")
        
        if st.button("Salvar Cadastro"):
            if nome:
                st.session_state['db_users'].append({
                    "Nome": nome, "Setor": setor, 
                    "Rodízio Sáb": r_sabado, "Folga Casada": r_dom_seg
                })
                st.success(f"{nome} cadastrado!")

        if st.session_state['db_users']:
            st.write("### Lista de Funcionários")
            st.table(pd.DataFrame(st.session_state['db_users']))

    with aba3:
        st.subheader("Gerador de Escala Mensal")
        if not st.session_state['db_users']:
            st.warning("Cadastre funcionários na primeira aba antes de gerar.")
        else:
            setor_sel = st.selectbox("Escolha o Setor para Escala", st.session_state['db_cats'])
            
            # BOTÃO QUE VOCÊ PRECISAVA:
            if st.button("✨ GERAR ESCALA AGORA"):
                datas = pd.date_range(start='2026-03-01', end='2026-03-31')
                df_escala = pd.DataFrame({
                    'Data': datas.strftime('%d/%m/%Y'),
                    'Dia': datas.day_name(),
                    'Status': ['Trabalho'] * len(datas)
                })
                
                # Regra: Domingo é Folga
                df_escala.loc[df_escala['Dia'] == 'Sunday', 'Status'] = 'Folga'
                
                st.write(f"### Escala de Março: {setor_sel}")
                st.table(df_escala)

                # --- EXPORTAÇÃO EXCEL COLORIDA ---
                try:
                    from openpyxl.styles import PatternFill, Font
                    dias_pt = {'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira', 
                               'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
                    
                    df_export = df_escala.copy()
                    df_export['Dia'] = df_export['Dia'].map(dias_pt)

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Escala')
                        ws = writer.sheets['Escala']
                        
                        cor_f = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid") # Amarelo
                        cor_d = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid") # Vermelho
                        f_branca = Font(color="FFFFFF", bold=True)

                        for r_idx, r_val in enumerate(df_export.values, start=2):
                            if r_val[1] == 'Domingo':
                                for c in range(1, 4):
                                    ws.cell(row=r_idx, column=c).fill = cor_d
                                    ws.cell(row=r_idx, column=c).font = f_branca
                            elif r_val[2] == 'Folga':
                                for c in range(1, 4):
                                    ws.cell(row=r_idx, column=c).fill = cor_f

                    st.download_button(label="📥 Baixar Excel Colorido", data=output.getvalue(), 
                                     file_name="escala.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception as e:
                    st.error(f"Erro no Excel: {e}")
