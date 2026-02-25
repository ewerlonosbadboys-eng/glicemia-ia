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
    
    # Agrupar por categoria para balancear o setor
    cats = {}
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        cats.setdefault(c, []).append(u)
    
    for cat_nome, membros in cats.items():
        # mapa_folgas_dia: conta quantas pessoas da mesma categoria folgam em cada dia
        mapa_folgas_dia = {i: 0 for i in range(31)} 
        
        # Shuffle para evitar que o primeiro da lista sempre pegue os melhores dias
        random.shuffle(membros)
        
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                folgas_na_semana = 0 
                
                # 1. REGRA DO DOMINGO (Alternado)
                dom_no_bloco = [j for j in range(sem, fim) if df.loc[j, 'Dia'] == 'dom']
                for d_idx in dom_no_bloco:
                    semana_do_mes = d_idx // 7
                    if semana_do_mes % 2 == user.get('offset_dom', 0):
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_na_semana += 1 
                        
                        # Se for folga casada, tenta colocar na segunda
                        if user.get("Casada") and (d_idx + 1) < fim:
                            df.loc[d_idx+1, 'Status'] = 'Folga'
                            mapa_folgas_dia[d_idx+1] += 1
                            folgas_na_semana += 1

                # 2. SEGUNDA FOLGA (Apenas se ainda não completou 2 na semana)
                while folgas_na_semana < 2:
                    # Critérios para escolher o dia da folga:
                    # - Deve ser 'Trabalho' atualmente
                    # - Se NÃO for casada, não pode ser colado em outra folga
                    # - Não pode ser sábado se não for rodízio
                    possiveis = []
                    for j in range(sem, fim):
                        if df.loc[j, 'Status'] == 'Trabalho':
                            colado = (j > 0 and df.loc[j-1, 'Status'] == 'Folga') or (j < 30 and df.loc[j+1, 'Status'] == 'Folga')
                            sab_restrito = (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))
                            
                            if not sab_restrito:
                                if user.get("Casada") or not colado:
                                    possiveis.append(j)
                    
                    if possiveis:
                        # BALANCEAMENTO REAL: Escolhe o dia que tem MENOS pessoas da categoria de folga
                        # Se houver empate, randomiza entre os dias mais vazios
                        menor_valor = min(mapa_folgas_dia[p] for p in possiveis)
                        melhores_escolhas = [p for p in possiveis if mapa_folgas_dia[p] == menor_valor]
                        escolhido = random.choice(melhores_escolhas)
                        
                        df.loc[escolhido, 'Status'] = 'Folga'
                        mapa_folgas_dia[escolhido] += 1
                        folgas_na_semana += 1
                    else:
                        break
            
            # Geração de Horários
            ents, sais = [], []
            hp = user.get("Entrada", "06:00")
            for m in range(len(df)):
                if df.loc[m, 'Status'] == 'Folga':
                    ents.append(""); sais.append("")
                else:
                    e = hp
                    if m > 0 and len(sais) > 0 and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], hp)
                    ents.append(e)
                    sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df
    return novo_hist

# --- INTERFACE (Ajustada para chaves únicas para evitar erros de duplicidade) ---
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro de Funcionários")
    c1, c2 = st.columns(2)
    with c1:
        n = st.text_input("Nome completo")
        ct = st.text_input("Categoria/Setor")
    with c2:
        h_in = st.time_input("Horário de Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
        s_rk = st.checkbox("Participa do Rodízio de Sábado?")
        c_rk = st.checkbox("Deseja Folgas Seguidas (Casadas)?")
    
    if st.button("Salvar Funcionário"):
        if n and ct:
            # Atribui offset para balancear domingos automaticamente
            total_na_cat = len([u for u in st.session_state['db_users'] if u['Categoria'] == ct])
            st.session_state['db_users'].append({
                "Nome": n, "Categoria": ct, "Entrada": h_in.strftime('%H:%M'), 
                "Rod_Sab": s_rk, "Casada": c_rk, "offset_dom": total_na_cat % 2
            })
            st.success(f"{n} adicionado com sucesso!")
        else:
            st.error("Preencha Nome e Categoria.")

with aba2:
    if st.button("🚀 GERAR NOVA ESCALA 5x2"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
            st.success("Escala gerada! As folgas foram espalhadas para não esvaziar o setor.")
        else: st.warning("Adicione funcionários no Cadastro primeiro.")
    
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Folha de Escala: {nome}"):
                st.dataframe(df, use_container_width=True)

with aba3:
    st.subheader("⚙️ Ajustes Pontuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Escolha o Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🔄 Trocar Dia de Folga")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_tira = st.selectbox("Dia que vai trabalhar (era folga):", [d+1 for d in folgas_atuais])
            d_poe = st.number_input("Novo dia para folgar:", 1, 31, value=1)
            if st.button("Confirmar Troca de Folga"):
                df_e.loc[d_tira-1, 'Status'], df_e.loc[d_poe-1, 'Status'] = 'Trabalho', 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()
        with col_b:
            st.markdown("#### 🕒 Alterar Horário Específico")
            d_h = st.number_input("Dia do Mês:", 1, 31, key="dia_ajuste")
            n_h = st.time_input("Nova Entrada para este dia:", key="hora_ajuste")
            if st.button("Salvar Horário"):
                df_e.loc[d_h-1, 'H_Entrada'] = n_h.strftime("%H:%M")
                df_e.loc[d_h-1, 'H_Saida'] = (datetime.combine(datetime.today(), n_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário alterado com sucesso!")

with aba4:
    if st.session_state['historico']:
        if st.button("📊 GERAR EXCEL PARA IMPRESSÃO"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala", index=0)
                
                # Cores
                red = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                yel = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                center = Alignment(horizontal="center", vertical="center")
                
                # Cabeçalho de Dias
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center
                
                # Dados dos Funcionários
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})").alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, row in df_f.iterrows():
                        is_f = (row['Status'] == 'Folga')
                        c1 = ws.cell(row_idx, i+2, "FOLGA" if is_f else row['H_Entrada'])
                        c2 = ws.cell(row_idx+1, i+2, "" if is_f else row['H_Saida'])
                        c1.border = c2.border = border
                        c1.alignment = c2.alignment = center
                        if is_f:
                            c1.fill = c2.fill = red if row['Dia'] == 'dom' else yel
                    row_idx += 2
            
            st.download_button("📥 Baixar Arquivo Excel", output.getvalue(), "escala_equipe_5x2.xlsx")
