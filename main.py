import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

# 1. Configuração e Segurança
st.set_page_config(page_title="Gestor Escala 5x2 Pro", layout="wide")

if "password_correct" not in st.session_state:
    st.title("🔐 Login Administrativo")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# Inicialização de memória robusta
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

# 2. Interface
aba1, aba2, aba3 = st.tabs(["👥 Cadastro", "📅 Gerar Escala", "📜 Histórico"])

with aba1:
    st.subheader("Cadastro de Equipe")
    nome = st.text_input("Nome do Funcionário")
    h_entrada = st.time_input("Horário de Entrada", value=datetime.strptime("06:00", "%H:%M").time())
    
    # Cálculo: 8:48 trabalho + 1:10 almoço = 9:58 total de permanência
    delta_total = timedelta(hours=9, minutes=58)
    h_saida = (datetime.combine(datetime.today(), h_entrada) + delta_total).time()
    
    st.write(f"⏱️ **Saída Calculada (Carga + Almoço):** {h_saida.strftime('%H:%M')}")
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Participar de Rodízio no Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar Funcionário"):
        if nome:
            # Proteção: Limpa dados antigos com mesmo nome para evitar conflito de chaves
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, 
                "Entrada": h_entrada.strftime('%H:%M'),
                "Saida": h_saida.strftime('%H:%M'), 
                "Rodizio_Sab": f_sab, 
                "Casada": f_cas
            })
            st.success(f"{nome} cadastrado com sucesso!")
    
    if st.session_state['db_users']:
        st.dataframe(pd.DataFrame(st.session_state['db_users']))

with aba2:
    st.subheader("Gerar Escala Mensal")
    if st.session_state['db_users']:
        lista_nomes = [u.get('Nome') for u in st.session_state['db_users'] if u.get('Nome')]
        func_sel = st.selectbox("Escolha o Funcionário", lista_nomes)
        
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            
            # Busca segura com .get() para não dar KeyError
            user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), None)
            
            if user:
                df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
                
                # Regra Domingos 1x1
                dom_idx = df[df['Dia'] == 'dom'].index.tolist()
                for idx, d_idx in enumerate(dom_idx):
                    if idx % 2 == 1:
                        df.loc[d_idx, 'Status'] = 'Folga'
                        if user.get("Casada") and (d_idx + 1) < 31:
                            df.loc[d_idx + 1, 'Status'] = 'Folga'
                
                # Regra 5x2 Semanal
                for i in range(0, 31, 7):
                    sem = df.iloc[i:i+7]
                    if len(sem[sem['Status'] == 'Folga']) < 2:
                        cond = (sem['Status'] == 'Trabalho')
                        if not user.get("Rodizio_Sab", False): cond &= (sem['Dia'] != 'sáb')
                        pode = sem[cond].index.tolist()
                        if pode: df.loc[random.choice(pode), 'Status'] = 'Folga'
                
                # Trava Final: Máximo 5 dias seguidos
                cont = 0
                for i in range(len(df)):
                    cont = cont + 1 if df.loc[i, 'Status'] == 'Trabalho' else 0
                    if cont > 5:
                        df.loc[i, 'Status'] = 'Folga'
                        cont = 0
                
                st.session_state['historico'][func_sel] = df
                st.table(df)

with aba3:
    st.subheader("📜 Exportar Histórico")
    if st.session_state['historico']:
        f_nome = st.selectbox("Selecione a Escala", list(st.session_state['historico'].keys()))
        df_h = st.session_state['historico'][f_nome]
        u_info = next((i for i in st.session_state['db_users'] if i.get("Nome") == f_nome), None)
        
        if u_info:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala", index=0)
                
                red = PatternFill(start_color="FF0000", fill_type="solid")
                yel = PatternFill(start_color="FFFF00", fill_type="solid")
                white_font = Font(color="FFFFFF", bold=True)
                center = Alignment(horizontal="center", vertical="center")

                # Layout Horizontal (Igual à imagem)
                ws.cell(1, 1, "Nome")
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center # Números
                    ws.cell(2, i+2, df_h.iloc[i]['Dia']).alignment = center # Nome do dia
                
                ws.cell(3, 1, f_nome)
                ws.cell(4, 1, "Horário")
                
                for i, row in df_h.iterrows():
                    col = i + 2
                    is_folga = (row['Status'] == 'Folga')
                    
                    c_top = ws.cell(3, col, "Folga" if is_folga else u_info.get("Entrada", "06:00"))
                    c_bot = ws.cell(4, col, "" if is_folga else u_info.get("Saida", "15:58"))
                    
                    c_top.alignment = center
                    c_bot.alignment = center
                    
                    if is_folga:
                        cor = red if row['Dia'] == 'dom' else yel
                        c_top.fill = cor
                        c_bot.fill = cor
                        if row['Dia'] == 'dom':
                            c_top.font = white_font
                            c_bot.font = white_font
                
                for col in range(1, 33): ws.column_dimensions[ws.cell(1, col).column_letter].width = 7

            st.download_button("📥 Baixar Planilha Horizontal Colorida", out.getvalue(), f"escala_{f_nome}.xlsx")
