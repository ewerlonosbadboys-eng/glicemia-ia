# --- RELATÓRIO FORMATO MÉDICO COM HORÁRIOS ---
if not df.empty:
    try:
        # Criamos uma coluna temporária que junta o Valor e a Hora ex: "140 (08:30)"
        df['Valor_Com_Hora'] = df['Valor'].astype(str) + " (" + df['Hora'].astype(str) + ")"
        
        # Montamos a tabela usando essa nova coluna
        relatorio = df.pivot_table(
            index='Data', 
            columns='Categoria', 
            values='Valor_Com_Hora', 
            aggfunc='last'
        ).reset_index()
        
        # Garante a ordem correta das colunas
        colunas_finais = ['Data'] + [c for c in categorias_ordem if c in relatorio.columns]
        relatorio = relatorio.reindex(columns=colunas_finais)

        st.subheader("📊 Relatório Detalhado (Com Horários)")
        st.write("Agora o médico pode ver o valor e o horário exato entre parênteses:")
        st.dataframe(relatorio, use_container_width=True)

        # Exportação para Excel mantendo os horários
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            relatorio.to_excel(writer, index=False, sheet_name='Glicemia Detalhada')
            
            # (Opcional) Você pode manter a lógica de cores aqui se desejar, 
            # mas como agora é um texto "140 (08:30)", a pintura automática por número 
            # precisaria de um ajuste extra.
            
        st.download_button(
            label="📥 Baixar Relatório com Horários para o Médico",
            data=output.getvalue(),
            file_name=f"Glicemia_Detalhada_{datetime.now().strftime('%m_%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Erro ao gerar relatório detalhado: {e}")
