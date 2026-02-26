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
    cats = {}
    
    # Agrupa usuários por categoria
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        cats.setdefault(c, []).append(u)
    
    for cat_nome, membros in cats.items():
        # mapa_folgas_dia: essencial para o balanceamento (evita folgas no mesmo dia)
        mapa_folgas_dia = {i: 0 for i in range(31)} 
        
        # Embaralha a ordem dos membros para que a prioridade de escolha mude a cada geração
        random.shuffle(membros)
        
        for user in membros:
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # Blocos de 7 dias (Regra 5x2)
            for sem in range(0, 31, 7):
                fim = min(sem + 7, 31)
                folgas_na_semana = 0 
                
                # 1. REGRA DO DOMINGO: 1 sim, 1 não. Se folgar, já conta como 1ª folga.
                dom_no_bloco = [j for j in range(sem, fim) if df.loc[j, 'Dia'] == 'dom']
                for d_idx in dom_no_bloco:
                    # Alternância baseada no bloco (semana)
                    if (d_idx // 7) % 2 == user.get('offset_dom', random.randint(0,1)):
                        df.loc[d_idx, 'Status'] = 'Folga'
                        mapa_folgas_dia[d_idx] += 1
                        folgas_na_semana += 1 
                
                # 2. SEGUNDA FOLGA: Busca o dia mais vazio da categoria
                while folgas_na_semana < 2:
                    possiveis = [j for j in range(sem, fim) if df.loc[j, 'Status'] == 'Trabalho' and 
                                 not (df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False) and 
                                 not (df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False) and
                                 not (df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"))]
                    
                    if possiveis:
                        # Ordena: 1º pelo dia com menos folgas no grupo, 2º aleatório para desempate
                        random.shuffle(possiveis)
                        possiveis.sort(key=lambda x: mapa_folgas_dia[x])
                        
                        escolhido = possiveis[0]
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

# --- INTERFACE ---
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome")
    ct = c2.text_input("Categoria")
    h_in = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    col_check1, col_check2 = st.columns(2)
    s_rk = col_check1.checkbox("Rodízio Sábado")
    c_rk = col_check2.checkbox("Folga Casada")
    
    if st.button("Salvar Funcionário"):
        if n and ct:
            st.session_state['db_users'].append({
                "Nome": n, 
                "Categoria": ct, 
                "Entrada": h_in.strftime('%H:%M'), 
                "Rod_Sab": s_rk, 
                "Casada": c_rk,
                "offset_dom": random.randint(0,1) # Garante que nem todos folguem no mesmo domingo
            })
            st.success(f"{n} cadastrado com sucesso!")
        else:
            st.error("Preencha Nome e Categoria.")

with aba2:
    if st.button("🚀 GERAR ESCALA (5x2 Inteligente)"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_inteligente(st.session_state['db_users'])
            st.success("Escala Gerada! Folgas distribuídas para evitar agrupamento.")
        else:
            st.warning("Cadastre os funcionários na Aba 1.")
            
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Visualizar Escala: {nome}"):
                st.dataframe(df, use_container_width=True)

with aba3:
    st.subheader("⚙️ Ajustes Manuais")
    if st.session_state['historico']:
        f_ed = st.selectbox("Selecione o Funcionário:", list(st.session_state['historico'].keys()))
        df_e = st.session_state['historico'][f_ed]
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 🔄 Trocar Dia de Folga")
            folgas_atuais = df_e[df_e['Status'] == 'Folga'].index.tolist()
            d_tira = st.selectbox("Dia para TRABALHAR (remover folga):", [d+1 for d in folgas_atuais])
            d_poe = st.number_input("Novo dia para FOLGAR:", 1, 31, value=1)
            if st.button("Confirmar Troca"):
                df_e.loc[d_tira-1, 'Status'] = 'Trabalho'
                df_e.loc[d_poe-1, 'Status'] = 'Folga'
                st.session_state['historico'][f_ed] = df_e
                st.rerun()
                
        with col_b:
            st.markdown("#### 🕒 Alterar Horário Específico")
            dia_h = st.number_input("Dia do Mês:", 1, 31, key="dia_h")
            hora_h = st.time_input("Nova Entrada:", key="hora_h")
            if st.button("Salvar Novo Horário"):
                df_e.loc[dia_h-1, 'H_Entrada'] = hora_h.strftime("%H:%M")
                saida_calc = (datetime.combine(datetime.today(), hora_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                df_e.loc[dia_h-1, 'H_Saida'] = saida_calc
                st.session_state['historico'][f_ed] = df_e
                st.success("Horário alterado!")

with aba4:
    st.subheader("📥 Exportar para Excel")
    if st.session_state['historico']:
        if st.button("📊 GERAR ARQUIVO PARA DOWNLOAD"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                wb = writer.book
                ws = wb.create_sheet("Escala Mensal", index=0)
                
                # Cores e Estilos
                fill_dom = PatternFill(start_color="FF0000", end_color="FF0000", patternType="solid")
                fill_folga = PatternFill(start_color="FFFF00", end_color="FFFF00", patternType="solid")
                border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                top=Side(style='thin'), bottom=Side(style='thin'))
                center = Alignment(horizontal="center", vertical="center")
                
                # Cabeçalho (Dias 1-31)
                df_ref = list(st.session_state['historico'].values())[0]
                for i in range(31):
                    ws.cell(1, i+2, i+1).alignment = center
                    ws.cell(2, i+2, df_ref.iloc[i]['Dia']).alignment = center
                
                # Dados dos Funcionários
                row_idx = 3
                for nome, df_f in st.session_state['historico'].items():
                    u_inf = next(u for u in st.session_state['db_users'] if u['Nome'] == nome)
                    cell_nome = ws.cell(row_idx, 1, f"{nome}\n({u_inf['Categoria']})")
                    cell_nome.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
                    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx+1, end_column=1)
                    
                    for i, row in df_f.iterrows():
                        is_folga = (row['Status'] == 'Folga')
                        c1 = ws.cell(row_idx, i+2, "FOLGA" if is_folga else row['H_Entrada'])
                        c2 = ws.cell(row_idx+1, i+2, "" if is_folga else row['H_Saida'])
                        
                        c1.border = c2.border = border
                        c1.alignment = c2.alignment = center
                     
                        if is_folga:
                            c1.fill = fill_dom if row['Dia'] == 'dom' else fill_folga
                            c2.fill = fill_dom if row['Dia'] == 'dom' else fill_folga
                            
                    row_idx += 2
            
            st.download_button(
                label="📥 Baixar Escala em Excel",
                data=output.getvalue(),
                file_name=f"escala_5x2_{datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
