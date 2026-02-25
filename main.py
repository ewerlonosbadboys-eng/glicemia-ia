# --- COLE ESTE BLOCO LOGO ABAIXO DA TABELA DA ESCALA ---
try:
    if 'df_escala' in locals() or 'df_escala' in globals():
        st.divider()
        if st.button("📥 Baixar Escala Colorida (Excel)"):
            import io
            from openpyxl.styles import PatternFill, Font
            
            # Dicionário de tradução
            dias_pt = {
                'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 
                'Wednesday': 'Quarta-feira', 'Thursday': 'Quinta-feira', 
                'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }

            # Preparando os dados para o Excel
            df_export = df_escala.copy()
            df_export['Dia'] = df_export['Dia'].map(dias_pt)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Escala')
                
                workbook = writer.book
                worksheet = writer.sheets['Escala']
                
                # Cores solicitadas
                color_folga = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid") # Amarelo
                color_domingo = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid") # Vermelho
                font_branca = Font(color="FFFFFF", bold=True)

                for row_idx, row_data in enumerate(df_export.values, start=2):
                    dia_semana = row_data[1]
                    status = row_data[2]
                    
                    if dia_semana == 'Domingo':
                        for col_idx in range(1, 4):
                            cell = worksheet.cell(row=row_idx, column=col_idx)
                            cell.fill = color_domingo
                            cell.font = font_branca
                    elif status == 'Folga':
                        for col_idx in range(1, 4):
