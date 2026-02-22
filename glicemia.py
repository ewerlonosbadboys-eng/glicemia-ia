# --- BANCO DE DADOS DE ALIMENTOS (Exemplo de Valores Médios) ---
# Valores por porção (g): [Carboidratos, Proteínas, Gorduras]
ALIMENTOS = {
    "Pão Francês (1 un)": [28, 4.5, 1],
    "Pão de Forma (1 fatia)": [12, 2, 1],
    "Café com Açúcar (copo)": [10, 0, 0],
    "Café com Adoçante": [0, 0, 0],
    "Leite Inteiro (200ml)": [10, 6, 6],
    "Arroz Branco (colher)": [5, 0.5, 0],
    "Feijão (concha)": [14, 5, 0.5],
    "Frango Grelhado (filé)": [0, 23, 5],
    "Maçã (un)": [15, 0, 0],
    "Bolacha Salgada (un)": [4, 0.5, 1],
}

# --- INTERFACE DE NUTRIÇÃO ---
st.markdown("---")
st.subheader("🍽️ Diário Alimentar e Contagem")

col_n1, col_n2 = st.columns(2)

with col_n1:
    refeicao_tipo = st.selectbox("Refeição:", [
        "Café da Manhã", "Lanche da Manhã", "Almoço", 
        "Merenda", "Jantar", "Lanche da Noite"
    ])
    itens_consumidos = st.multiselect("O que foi consumido?", list(ALIMENTOS.keys()))

# Cálculos Automáticos
total_carb = sum([ALIMENTOS[item][0] for item in itens_consumidos])
total_prot = sum([ALIMENTOS[item][1] for item in itens_consumidos])
total_gord = sum([ALIMENTOS[item][2] for item in itens_consumidos])

with col_n2:
    st.write("**Resumo Nutricional:**")
    st.info(f"🍞 Carboidratos: {total_carb}g | 🥩 Proteína: {total_prot}g | 🥑 Gordura: {total_gord}g")
    
    if st.button("💾 SALVAR ALIMENTAÇÃO"):
        agora_br = datetime.now(fuso_br)
        dados_alimento = pd.DataFrame([[
            agora_br.strftime("%d/%m/%Y"), 
            refeicao_tipo, 
            ", ".join(itens_consumidos), 
            total_carb, total_prot, total_gord
        ]], columns=["Data", "Refeição", "Alimentos", "Carbos", "Proteína", "Gordura"])
        
        # Salva em um arquivo separado
        arq_nutri = "historico_nutricao.csv"
        if not os.path.isfile(arq_nutri):
            dados_alimento.to_csv(arq_nutri, index=False)
        else:
            dados_alimento.to_csv(arq_nutri, mode='a', header=False, index=False)
        st.success("Refeição registrada!")
