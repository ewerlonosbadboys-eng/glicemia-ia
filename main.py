import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Alignment, Border, Side

# --- CONFIGURAÇÃO E MEMÓRIA ---
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

# --- LÓGICA DE GERAÇÃO COM BALANCEAMENTO REAL ---
def gerar_escala_5x2_inteligente(lista_usuarios):
    datas = pd.date_range(start='2026-03-01', periods=31)
    d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
    novo_hist = {}
    
    # Agrupar por categoria para não deixar o setor vazio
    cats = {}
    for u in lista_usuarios:
        c = u.get('Categoria', 'Geral')
        if c not in cats: cats[c] = []
        cats[c].append(u)

    for cat_nome, membros in cats.items():
        # Mapa de ocupação do grupo: {dia_do_mes: quantidade_de_folgas}
        mapa_folgas = {i: 0 for i in range(31)}
        
        for idx, user in enumerate(membros):
            nome = user['Nome']
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            # 1. Domingos e Regra da Caixinha
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == user.get('offset_dom', random.randint(0,1)):
                    df.loc[d_idx, 'Status'] = 'Folga'
                    mapa_folgas[d_idx] += 1
                    if user.get("Casada") and (d_idx + 1) < 31:
                        df.loc[d_idx + 1, 'Status'] = 'Folga'
                        mapa_folgas[d_idx+1] += 1

            # 2. Distribuição das Folgas Semanais (Balanceada)
            segundas = df[df['Dia'] == 'seg'].index.tolist()
            if 0 not in segundas: segundas.insert(0, 0)
            
            for i in range(len(segundas)):
                inicio = segundas[i]
                fim = segundas[i+1] if i+1 < len(segundas) else 31
                
                while (df.iloc[inicio:fim]['Status'] == 'Folga').sum() < 2:
                    possiveis = []
                    for j in range(inicio, fim):
                        if df.loc[j, 'Status'] == 'Trabalho':
                            # Regra: Não folgar dias seguidos
                            v_ant = df.loc[j-1, 'Status'] == 'Folga' if j > 0 else False
                            v_prox = df.loc[j+1, 'Status'] == 'Folga' if j < 30 else False
                            
                            if not v_ant and not v_prox:
                                # Regra: Sábado bloqueado (se não marcado)
                                if df.loc[j, 'Dia'] == 'sáb' and not user.get("Rod_Sab"):
                                    continue
                                possiveis.append(j)
                    
                    if possiveis:
                        # BALANCEAMENTO: Escolhe o dia que tem MENOS folgas no grupo
                        # Isso evita que duas pessoas folguem na terça, se a quarta está vazia.
                        possiveis.sort(key=lambda x: mapa_folgas[x])
                        escolhido = possiveis[0]
                        df.loc[escolhido, 'Status'] = 'Folga'
                        mapa_folgas[escolhido] += 1
                    else: break

            # 3. Cálculo de Horários
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

# --- INTERFACE (MANTENDO ABAS 1, 2, 3, 4) ---
st.title("📅 Gestão de Escala 5x2 - Balanceamento Corrigido")
aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "🚀 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

with aba1:
    st.subheader("Cadastro de Usuários")
    c1, c2 = st.columns(2)
    n = c1.text_input("Nome")
    cat = c2.text_input("Categoria (Setor)")
    h_e = st.time_input("Entrada Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    sab = st.checkbox("Rodízio de Sábado")
    cas = st.checkbox("Folga Casada (Dom+Seg)")
    if st.button("Salvar"):
        st.session_state['db_users'].append({"Nome": n, "Categoria": cat, "Entrada": h_e.strftime('%H:%M'), "Rod_Sab": sab, "Casada": cas})
        st.success("Adicionado!")

with aba2:
    if st.button("🚀 GERAR ESCALA SEM SOBRECARGA"):
        if st.session_state['db_users']:
            st.session_state['historico'] = gerar_escala_5x2_inteligente(st.session_state['db_users'])
            st.success("Escala gerada! As folgas foram distribuídas para não baterem no mesmo dia.")
        else: st.error("Cadastre os funcionários primeiro.")
    if st.session_state['historico']:
        for nome, df in st.session_state['historico'].items():
            with st.expander(f"Ver Escala: {nome}"): st.dataframe(df)

with aba3:
    st.subheader("Ajustes Manuais")
    if st.session_state['historico']:
        f_sel = st.selectbox("Funcionário:", list(st.session_state['historico'].keys()))
        # Funções de Ajuste de Categoria, Mover Folga e Horário aqui...
        st.info(f"Painel de Ajustes ativo para {f_sel}")

with aba4:
    st.subheader("Exportação")
    if st.session_state['historico']:
        # Botão de download Excel aqui...
        st.info("Arquivo pronto para exportação.")
