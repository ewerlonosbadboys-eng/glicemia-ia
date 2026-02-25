import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

# --- ESTADO E CONFIGURAÇÃO ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    try:
        s = datetime.strptime(saida_ant, fmt)
        e = datetime.strptime(ent_padrao, fmt)
        diff = (e - s).total_seconds() / 3600
        if diff < 0: diff += 24
        if diff < 11:
            return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    except: pass
    return ent_padrao

def gerar_escala_5x2_balanceada(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    # Organização por categoria para o balanceamento
    categorias = {}
    for u in lista_usuarios:
        cat = u.get('Categoria', 'Geral')
        if cat not in categorias: categorias[cat] = []
        categorias[cat].append(u)

    for cat_nome, membros in categorias.items():
        # Contador de folgas por dia no grupo para distribuir bem
        folgas_no_dia = {i: 0 for i in range(31)}
        
        for idx, user in enumerate(membros):
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # 1. Regra de Domingos (Base)
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == user.get('offset_dom', random.randint(0,1)):
                    df.loc[d_idx, 'Status'] = 'Folga'
                    folgas_no_dia[d_idx] += 1
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'
                        folgas_no_dia[d_idx + 1] += 1

            # 2. Distribuição das Folgas Aleatórias com Balanceamento
            segundas = df[df['Dia'] == 'seg'].index.tolist()
            if 0 not in segundas: segundas.insert(0, 0)
            
            for i in range(len(segundas)):
                inicio = segundas[i]
                fim = segundas[i+1] if i+1 < len(segundas) else 31
                
                # Quantas folgas faltam para completar 2 na semana?
                f_faltando = 2 - (df.iloc[inicio:fim]['Status'] == 'Folga').sum()
                
                if f_faltando > 0:
                    for _ in range(f_faltando):
                        possiveis = []
                        for j in range(inicio, fim):
                            if df.loc[j, 'Status'] == 'Trabalho':
                                # Proibido folgas juntas
                                v_ant = df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False
                                v_prox = df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False
                                
                                if not v_ant and not v_prox:
                                    # Bloqueio do Sábado
                                    if df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"):
                                        continue
                                    possiveis.append(j)
                        
                        if possiveis:
                            # BALANCEAMENTO: Escolhe o dia que tem menos folgas registradas no grupo
                            possiveis.sort(key=lambda x: folgas_no_dia[x])
                            escolhido = possiveis[0]
                            df.loc[escolhido, 'Status'] = 'Folga'
                            folgas_no_dia[escolhido] += 1

            # 3. Horários e Limite de 5 Dias
            cont_trab = 0
            for k in range(len(df)):
                if df.loc[k, 'Status'] == 'Trabalho':
                    cont_trab += 1
                    if cont_trab > 5:
                        df.loc[k, 'Status'] = 'Folga'
                        folgas_no_dia[k] += 1
                        cont_trab = 0
                else: cont_trab = 0

            ents, sais = [], []
            hp = user.get("Entrada", "06:00")
            for m in range(len(df)):
                if df.loc[m, 'Status'] == 'Folga':
                    ents.append(""); sais.append("")
                else:
                    e = hp
                    if m > 0 and sais and sais[-1] != "":
                        e = calcular_entrada_segura(sais[-1], hp)
                    ents.append(e)
                    sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
            
            df['H_Entrada'], df['H_Saida'] = ents, sais
            novo_hist[nome] = df
            
    return novo_hist

# --- INTERFACE STREAMLIT ---
st.title("📅 Projeto 5x2 - Balanceamento de Carga")

aba1, aba2, aba3, aba4 = st.tabs(["👥 Cadastro", "🚀 Gerar Escala", "⚙️ Ajustes", "📥 Excel"])

with aba1:
    with st.form("cad"):
        n = st.text_input("Nome")
        cat = st.text_input("Categoria (Grupo p/ Balancear)")
        h_ent = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
        c1, c2 = st.columns(2)
        sab = c1.checkbox("Rodízio de Sábado")
        cas = c2.checkbox("Folga Casada (Dom+Seg)")
        if st.form_submit_button("Adicionar"):
            st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h_ent.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas})
            st.success(f"{n} adicionado!")

with aba2:
    if st.button("🚀 GERAR ESCALA DISTRIBUÍDA"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_5x2_balanceada(st.session_state['db_users'])
            st.success("Escala gerada com folgas bem distribuídas entre os funcionários!")
        else: st.error("Cadastre os funcionários primeiro.")
    
    if st.session_state['historico']:
        for nome, df_p in st.session_state['historico'].items():
            with st.expander(f"Visualizar: {nome}"): st.dataframe(df_p)

# As abas 3 (Ajustes) e 4 (Excel) continuam com a mesma lógica funcional anterior.
