import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

st.set_page_config(page_title="Projeto Escala 5x2 Oficial", layout="wide")

# --- MEMÓRIA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0: diff += 24
        if diff < 11: return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except: pass
    return ent_padrao

def gerar_escala_inteligente(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    # Agrupamento por Categoria para balanceamento setorial
    cats = {}
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        cats.setdefault(c, []).append(u)
    
    for cat_nome, membros in cats.items():
        mapa_folgas_dia = {i: 0 for i in range(31)} 
        random.shuffle(membros)
        
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Divide o mês em semanas reais (7 dias) para garantir 2 folgas em cada ciclo
            for sem in range(0, 31, 7):
                fim_semana = min(sem + 7, 31)
                folgas_alocadas = 0
                
                # 1. REGRA DO DOMINGO (Alternado conforme Offset)
                domingos_na_semana = [j for j in range(sem, fim_semana) if df.loc[j, 'Dia'] == 'dom']
                for d_idx in domingos_na_semana:
                    semana_id = d_idx // 7
                    if semana_id % 2 == user.get('offset_dom', 0):
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_alocadas += 1
                        
                        # Se for FOLGA CASADA, tenta obrigatoriamente a Segunda-feira
                        if user.get("Casada") and (d_idx + 1) < 31:
                            df.loc[d_idx + 1, 'Status'] = 'Folga'
                            mapa_folgas_dia[d_idx + 1] += 1
                            folgas_alocadas += 1

                # 2. ALOCAÇÃO DAS FOLGAS RESTANTES (Garante que não sobrem dias)
                while folgas_alocadas < 2:
                    possiveis = []
                    for j in range(sem, fim_semana):
                        if df.loc[j, 'Status'] == 'Trabalho':
                            # Se não for casada, evita colar em outra folga
                            colado = (j > 0 and df.loc[j-1, 'Status'] == 'Folga') or (j < 30 and df.loc[j+1, 'Status'] == 'Folga')
                            sab_bloqueado = (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))
                            
                            if not sab_bloqueado:
                                if user.get("Casada") or not colado:
                                    possiveis.append(j)
                    
                    if not possiveis: # Se a trava de "não colar" impedir a folga, liberamos a trava para não faltar folga
                        possiveis = [j for j in range(sem, fim_semana) if df.loc[j, 'Status'] == 'Trabalho' and not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    
                    if possiveis:
                        # Escolhe o dia que tem MENOS folgas na mesma categoria (Balanceamento Setorial)
                        possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                        escolhido = possiveis[0]
                        df.loc[escolhido, 'Status'] = 'Folga'
                        mapa_folgas_dia[escolhido] += 1
                        folgas_alocadas += 1
                    else:
                        break # Evita loop infinito se a semana acabar

            # Cálculo de Horários com 11h de descanso
            ents, sais = [], []
            h_padrao = user.get("Entrada", "06:00")
            for i in range(len(df)):
                if df.loc[i, 'Status'] == 'Folga':
                    ents.append(""); sais.append("")
                else:
                    ent_atual = h_padrao
                    if i > 0 and sais[-1] != "":
                        ent_atual = calcular_entrada_segura(sais[-1], h_padrao)
                    ents.append(ent_atual)
                    sais.append((datetime.strptime(ent_atual, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df
            
    return novo_hist

# --- INTERFACE ---
tab1, tab2, tab3, tab4 = st.tabs(["👤 Cadastro", "📅 Escala", "🔧 Ajustes", "📥 Exportar"])

with tab1:
    st.subheader("Cadastro de Equipe")
    c1, c2 = st.columns(2)
    with c1:
        nome_in = st.text_input("Nome do Colaborador")
        cat_in = st.text_input("Setor/Categoria")
    with c2:
        ent_in = st.time_input("Horário Base", value=datetime.strptime("06:00", "%H:%M").time())
        sab_in = st.checkbox("Trabalha aos Sábados?")
        cas_in = st.checkbox("Deseja Folga Casada (Seguidas)?")

    if st.button("Adicionar"):
        if nome_in and cat_in:
            off = len([u for u in st.session_state['db_users'] if u['Categoria'] == cat_in]) % 2
            st.session_state['db_users'].append({
                "Nome": nome_in, "Categoria": cat_in, "Entrada": ent_in.strftime('%H:%M'),
                "Rod_Sab": sab_in, "Casada": cas_in, "offset_dom": off
            })
            st.success(f"{nome_in} salvo!")

with tab2:
    if st.button("🔄 GERAR ESCALA 5x2"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
            st.balloons()
        else: st.warning("Cadastre alguém primeiro.")
    
    if st.session_state['historico']:
        for n, d in st.session_state['historico'].items():
            with st.expander(f"Escala de {n}"):
                st.table(d)

with tab3:
    st.subheader("Ajustes Pontuais")
    if st.session_state['historico']:
        func = st.selectbox("Selecione:", list(st.session_state['historico'].keys()))
        df_temp = st.session_state['historico'][func]
        dia = st.number_input("Dia do Mês:", 1, 31)
        novo_status = st.radio("Status:", ["Trabalho", "Folga"], horizontal=True)
        if st.button("Atualizar"):
            df_temp.loc[dia-1, 'Status'] = novo_status
            st.session_state['historico'][func] = df_temp
            st.rerun()

with tab4:
    if st.session_state['historico']:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala Geral", index=0)
            f_dom = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
            f_fol = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
            border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Cabeçalhos
            ref = list(st.session_state['historico'].values())[0]
            for i in range(31):
                ws.cell(1, i+2, i+1).alignment = center
                ws.cell(2, i+2, ref.iloc[i]['Dia']).alignment = center
            
            row_idx = 3
            for nome, df_f in st.session_state['historico'].items():
                cat = next(u['Categoria'] for u in st.session_state['db_users'] if u['Nome'] == nome)
                ws.cell(row_idx, 1, f"{nome}\n({cat})").alignment = center
                ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                for i, row in df_f.iterrows():
                    is_folga = (row['Status'] == 'Folga')
                    c1 = ws.cell(row_idx, i+2, "FOLGA" if is_folga else row['H_Entrada'])
                    c2 = ws.cell(row_idx+1, i+2, "" if is_folga else row['H_Saida'])
                    c1.border = c2.border = border
                    c1.alignment = c2.alignment = center
                    if is_folga:
                        c1.fill = c2.fill = f_dom if row['Dia'] == 'dom' else f_fol
                row_idx += 2
        
        st.download_button("📥 Baixar Excel", output.getvalue(), "escala_5x2_final.xlsx")
