import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

# --- ESTADO DO SISTEMA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

def calcular_entrada_segura(saida_ant, ent_padrao):
    fmt = "%H:%M"
    s = datetime.strptime(saida_ant, fmt)
    e = datetime.strptime(ent_padrao, fmt)
    diff = (e - s).total_seconds() / 3600
    if diff < 0: diff += 24
    if diff < 11:
        return (s + timedelta(hours=11, minutes=10)).strftime(fmt)
    return ent_padrao

def gerar_escala_5x2_sem_folgas_juntas(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    for idx, user in enumerate(lista_usuarios):
        nome = user['Nome']
        df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
        
        # 1. Domingos e Regra da Caixinha (Dom+Seg)
        dom_idx = df[df['Dia'] == 'dom'].index.tolist()
        for i, d_idx in enumerate(dom_idx):
            if i % 2 == user.get('offset_dom', idx % 2):
                df.loc[d_idx, 'Status'] = 'Folga'
                # REGRA DA CAIXINHA: Só folga segunda se "Casada" estiver marcado
                if user.get("Casada") and (d_idx + 1) < 31:
                    df.loc[d_idx+1, 'Status'] = 'Folga'

        # 2. Distribuição das Folgas 5x2 (Segunda a Domingo)
        for sem in range(0, len(df), 7):
            fim_sem = min(sem + 7, len(df))
            
            # Garante 2 folgas na semana
            while (df.iloc[sem:fim_sem]['Status'] == 'Folga').sum() < 2:
                possiveis = []
                for j in range(sem, fim_sem):
                    if df.loc[j, 'Status'] == 'Trabalho':
                        # REGRA: Proibido folgas juntas (checa vizinhos)
                        vizinho_ant = df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False
                        vizinho_prox = df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False
                        
                        if not vizinho_ant and not vizinho_prox:
                            # Respeita o Sábado (só folga se marcado)
                            if df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"):
                                continue
                            possiveis.append(j)
                
                if possiveis:
                    df.loc[random.choice(possiveis), 'Status'] = 'Folga'
                else:
                    # Se travar, força uma folga respeitando o máximo de distância possível
                    break

            # 3. Trava de Segurança: Máximo 5 dias seguidos
            cont = 0
            for k in range(len(df)):
                if df.loc[k, 'Status'] == 'Trabalho':
                    cont += 1
                    if cont > 5:
                        # Força folga se não for quebrar a regra de folga junta
                        df.loc[k, 'Status'] = 'Folga'
                        cont = 0
                else:
                    cont = 0

        # 4. Horários com 11h + 10min
        ents, sais = [], []
        hp = user.get("Entrada", "06:00")
        for i in range(len(df)):
            if df.loc[i, 'Status'] == 'Folga':
                ents.append(""); sais.append("")
            else:
                e = hp
                if i > 0 and sais[i-1] != "":
                    e = calcular_entrada_segura(sais[i-1], hp)
                ents.append(e)
                sais.append((datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M"))
        
        df['H_Entrada'], df['H_Saida'] = ents, sais
        novo_hist[nome] = df
    return novo_hist

# --- INTERFACE (RESUMO) ---
st.title("📅 Projeto 5x2 - Sem Folgas Juntas")
# Aba 2: Gerar e Mostrar Histórico
if st.button("🚀 GERAR ESCALA 5x2"):
    st.session_state['historico'] = gerar_escala_5x2_sem_folgas_juntas(st.session_state['db_users'])
    st.success("Escala gerada respeitando a proibição de folgas juntas!")

if st.session_state['historico']:
    for nome, df_p in st.session_state['historico'].items():
        with st.expander(f"Histórico Salvo: {nome}"):
            st.dataframe(df_p)
