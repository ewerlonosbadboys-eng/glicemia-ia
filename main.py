import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import random
from openpyxl.styles import PatternFill, Font, Alignment

st.set_page_config(page_title="Gestor Escala 2026", layout="wide")

# --- 1. LOGIN ---
if "password_correct" not in st.session_state:
    st.title("🔐 Login do Sistema")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "123":
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# --- 2. MEMÓRIA ---
if 'db_users' not in st.session_state: st.session_state['db_users'] = []
if 'historico' not in st.session_state: st.session_state['historico'] = {}

st.title("📅 Gestão de Escala Profissional")

aba1, aba2, aba3, aba4 = st.tabs(["👥 1. Cadastro", "📅 2. Gerar Escala", "⚙️ 3. Ajustes", "📥 4. Baixar Excel"])

# --- ABA 1: CADASTRO COM TEXTO LIVRE ---
with aba1:
    st.subheader("Cadastrar Novo Funcionário")
    c_cad1, c_cad2 = st.columns(2)
    nome = c_cad1.text_input("Nome do Funcionário")
    # ALTERADO: Agora é text_input para você escrever o que quiser
    categoria = c_cad2.text_input("Categoria / Alocação (Digite o setor)")
    
    h_ent_padrao = st.time_input("Horário Padrão", value=datetime.strptime("06:00", "%H:%M").time())
    
    c1, c2 = st.columns(2)
    f_sab = c1.checkbox("Rodízio de Sábado")
    f_cas = c2.checkbox("Folga Casada (Dom + Seg)")
    
    if st.button("Salvar no Grupo"):
        if nome:
            st.session_state['db_users'] = [i for i in st.session_state['db_users'] if i.get('Nome') != nome]
            st.session_state['db_users'].append({
                "Nome": nome, 
                "Categoria": categoria if categoria else "Geral",
                "Entrada": h_ent_padrao.strftime('%H:%M'),
                "Rod_Sab": f_sab, "Casada": f_cas
            })
            st.success(f"✅ {nome} salvo em {categoria}!")

# --- ABA 2: GERAR ESCALA ---
with aba2:
    if st.session_state['db_users']:
        func_sel = st.selectbox("Selecione o Funcionário", [u.get('Nome') for u in st.session_state['db_users']])
        user = next((i for i in st.session_state['db_users'] if i.get("Nome") == func_sel), {})
        st.info(f"Setor: {user.get('Categoria', 'Geral')}")
        
        if st.button("✨ GERAR ESCALA"):
            datas = pd.date_range(start='2026-03-01', periods=31)
            d_pt = {'Monday':'seg','Tuesday':'ter','Wednesday':'qua','Thursday':'qui','Friday':'sex','Saturday':'sáb','Sunday':'dom'}
            df = pd.DataFrame({'Data': datas, 'Dia': [d_pt[d.day_name()] for d in datas], 'Status': 'Trabalho'})
            
            dom_idx = df[df['Dia'] == 'dom'].index.tolist()
            for i, d_idx in enumerate(dom_idx):
                if i % 2 == 1:
                    df.loc[d_idx, 'Status'] = 'Folga'
                    if user.get("Casada") and (d_idx + 1) < 31: df.loc[d_idx + 1, 'Status'] = 'Folga'

            for sem in range(0, 31, 7):
                bloco = df.iloc[sem:min(sem+7, 31)]
                meta = 1 if any((bloco['Dia'] == 'dom') & (bloco['Status'] == 'Folga')) else 2
                atuais = len(bloco[(bloco['Status'] == 'Folga') & (bloco['Dia'] != 'dom')])
                while atuais < meta:
                    pode = [p for p in bloco[bloco['Status'] == 'Trabalho'].index.tolist() if df.loc[p, 'Dia'] != 'dom']
                    p_real = [p for p in pode if not ((p > 0 and df.loc[p-1, 'Status'] == 'Folga') or (p < 30 and df.loc[p+1, 'Status'] == 'Folga'))]
                    if not p_real: break
                    df.loc[random.choice(p_real), 'Status'] = 'Folga'
                    atuais += 1
            
            df['H_Entrada'] = user.get("Entrada", "06:00")
            df['H_Saida'] = [(datetime.strptime(e, "%H:%M") + timedelta(hours=9, minutes=58)).strftime("%H:%M") for e in df['H_Entrada']]
            st.session_state['historico'][func_sel] = df
            st.table(df)

# --- ABA 3: AJUSTES (EDITAR LIVREMENTE) ---
with aba3:
    if st.session_state['db_users']:
        st.subheader("Editar Cadastro e Categoria")
        f_edit = st.selectbox("Escolha quem editar:", [u.get('Nome') for u in st.session_state['db_users']])
        user_idx = next(i for i, u in enumerate(st.session_state['db_users']) if u['Nome'] == f_edit)
        
        # ALTERADO: Edição de categoria agora é texto livre
        nova_cat_input = st.text_input("Nova Categoria para este usuário:", value=st.session_state['db_users'][user_idx].get('Categoria', ''))
        
        if st.button("💾 Atualizar Categoria"):
            st.session_state['db_users'][user_idx]['Categoria'] = nova_cat_input
            st.success("Categoria atualizada com sucesso!")

        st.divider()
        if f_edit in st.session_state['historico']:
            st.subheader("Ajustar Horário do Dia")
            df_e = st.session_state['historico'][f_edit]
            dia = st.number_input("Dia do Mês", 1, 31)
            novo_h = st.time_input("Nova Entrada")
            if st.button("💾 Aplicar (Descanso 11h10)"):
                idx = int(dia - 1)
                df_e.loc[idx, 'H_Entrada'] = novo_h.strftime("%H:%M")
                df_e.loc[idx, 'H_Saida'] = (datetime.combine(datetime.today(), novo_h) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                for i in range(idx + 1, 31):
                    if df_e.loc[i-1, 'Status'] == 'Trabalho':
                        saida_ant = datetime.strptime(df_e.loc[i-1, 'H_Saida'], "%H:%M")
                        minimo = (saida_ant + timedelta(hours=11, minutes=10)).time()
                        base_ent = datetime.strptime(st.session_state['db_users'][user_idx]['Entrada'], "%H:%M").time()
                        if minimo > base_ent:
                            df_e.loc[i, 'H_Entrada'] = minimo.strftime("%H:%M")
                            df_e.loc[i, 'H_Saida'] = (datetime.combine(datetime.today(), minimo) + timedelta(hours=9, minutes=58)).strftime("%H:%M")
                st.session_state['historico'][f_edit] = df_e
                st.success("Pronto!")

# --- ABA 4: DOWNLOAD ---
with aba4:
    if st.session_state['historico']:
        f_nome = st.selectbox("Baixar Escala de:", list(st.session_state['historico'].keys()))
        df_final = st.session_state['historico'][f_nome]
        u_data = next((u for u in st.session_state['db_users'] if u['Nome'] == f_nome), {})
        u_cat = u_data.get('Categoria', 'Geral')
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            wb = writer.book
            ws = wb.create_sheet("Escala", index=0)
            red, yel = PatternFill(start_color="FF0000", fill_type="solid"), PatternFill(start_color="FFFF00", fill_type="solid")
            center = Alignment(horizontal="center", vertical="center")
            ws.cell(1, 1, "Categoria").font = Font(bold=True)
            ws.cell(1, 2, u_cat)
            ws.cell(2, 1, "Nome").font = Font(bold=True)
            ws.cell(2, 2, f_nome)
            for i in range(31):
                ws.cell(3, i+2, i+1).alignment = center
                ws.cell(4, i+2, df_final.iloc[i]['Dia']).alignment = center
            for i, row in df_final.iterrows():
                col = i + 2
                is_f = (row['Status'] == 'Folga')
                c_e = ws.cell(5, col, "Folga" if is_f else row['H_Entrada'])
                c_s = ws.cell(6, col, "" if is_f else row['H_Saida'])
                if is_f: c_e.fill = c_s.fill = red if row['Dia'] == 'dom' else yel
        st.download_button("📥 BAIXAR EXCEL", out.getvalue(), f"escala_{f_nome}.xlsx")
