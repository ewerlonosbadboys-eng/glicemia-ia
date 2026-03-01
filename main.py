# ------------------------------------------------------
# ABA 4: Férias (GRÁFICO BARRAS + % TIME + ALERTA + PREVISÃO)
# ------------------------------------------------------
with abas[3]:
    st.subheader("🏖️ Controle de Férias (com visão anual)")

    colaboradores = load_colaboradores_setor(setor)

    if not colaboradores:
        st.warning("Sem colaboradores cadastrados.")
    else:
        chapas = [c["Chapa"] for c in colaboradores]
        total_time = len(colaboradores)

        # ==========================================================
        # 1) LANÇAR FÉRIAS
        # ==========================================================
        st.markdown("### ➕ Lançar Férias")

        ch = st.selectbox("Chapa:", chapas, key="fer_ch")
        col1, col2 = st.columns(2)
        ini = col1.date_input("Início:", key="fer_ini")
        fim = col2.date_input("Fim:", key="fer_fim")

        if st.button("Adicionar férias", key="fer_add"):
            if fim < ini:
                st.error("Data final não pode ser menor que a inicial.")
            else:
                add_ferias(setor, ch, ini, fim)
                st.success("Férias adicionadas com sucesso!")
                st.rerun()

        # ==========================================================
        # 2) LISTAR / REMOVER FÉRIAS
        # ==========================================================
        st.markdown("---")
        st.markdown("### 📋 Férias cadastradas")

        rows = list_ferias(setor)

        if rows:
            df_f = pd.DataFrame(rows, columns=["Chapa", "Início", "Fim"])
            st.dataframe(df_f, use_container_width=True)

            st.markdown("### ❌ Remover férias")
            rem_idx = st.number_input(
                "Linha para remover (1,2,3...)",
                min_value=1,
                max_value=len(df_f),
                value=1,
                key="fer_rem_idx"
            )

            if st.button("Remover linha", key="fer_rem_btn"):
                r = df_f.iloc[int(rem_idx) - 1]
                delete_ferias_row(setor, r["Chapa"], r["Início"], r["Fim"])
                st.success("Férias removidas.")
                st.rerun()
        else:
            st.info("Nenhuma férias cadastrada.")

        # ==========================================================
        # 3) VISÃO ANUAL: CONTAGEM + % + ALERTA + GRÁFICO BARRAS
        # ==========================================================
        st.markdown("---")
        st.markdown("## 📊 Visão Anual (Pessoas em férias por mês)")

        ano_grafico = st.number_input(
            "Ano para visualizar:",
            value=datetime.now().year,
            step=1,
            key="fer_ano_grafico"
        )

        # Limites para alerta
        st.markdown("### 🚨 Alertas (limites)")
        cA, cB, cC = st.columns(3)
        limite_pessoas = cA.number_input(
            "Limite de pessoas por mês",
            min_value=0,
            value=max(1, round(total_time * 0.2)),
            step=1,
            key="fer_limite_pessoas"
        )
        limite_percentual = cB.number_input(
            "Limite % do time por mês",
            min_value=0.0,
            max_value=100.0,
            value=20.0,
            step=1.0,
            key="fer_limite_percentual"
        )
        modo_alerta = cC.selectbox(
            "Modo do alerta",
            ["Disparar se passar em QUALQUER um (pessoas OU %)", "Disparar se passar em AMBOS (pessoas E %)"],
            key="fer_modo_alerta"
        )

        # Modo previsão
        st.markdown("### 🔮 Previsão automática")
        modo_previsao = st.selectbox(
            "O que mostrar no gráfico?",
            [
                "Planejado (banco): férias cadastradas no ano",
                "Planejado + Previsão (base ano anterior)",
                "Somente Previsão (base ano anterior)"
            ],
            key="fer_modo_previsao"
        )

        def _count_distinct_chapas_on_vacation_in_month(setor_: str, ano_: int, mes_: int) -> int:
            inicio_mes = date(int(ano_), int(mes_), 1)
            ultimo_dia = calendar.monthrange(int(ano_), int(mes_))[1]
            fim_mes = date(int(ano_), int(mes_), int(ultimo_dia))

            con = db_conn()
            cur = con.cursor()
            cur.execute("""
                SELECT COUNT(DISTINCT chapa)
                FROM ferias
                WHERE setor=?
                  AND (date(inicio) <= date(?) AND date(fim) >= date(?))
            """, (
                setor_,
                fim_mes.strftime("%Y-%m-%d"),
                inicio_mes.strftime("%Y-%m-%d")
            ))
            total = cur.fetchone()[0] or 0
            con.close()
            return int(total)

        meses = list(range(1, 13))

        # Planejado (banco)
        cont_planejado = [_count_distinct_chapas_on_vacation_in_month(setor, int(ano_grafico), m) for m in meses]

        # Previsão (ano anterior)
        ano_base = int(ano_grafico) - 1
        cont_prev = [_count_distinct_chapas_on_vacation_in_month(setor, int(ano_base), m) for m in meses]

        # Decide o que plotar
        if modo_previsao == "Planejado (banco): férias cadastradas no ano":
            series_plot = cont_planejado
            label_plot = f"Planejado {ano_grafico}"
            series_extra = None
            label_extra = None
        elif modo_previsao == "Somente Previsão (base ano anterior)":
            series_plot = cont_prev
            label_plot = f"Previsão {ano_grafico} (base {ano_base})"
            series_extra = None
            label_extra = None
        else:
            # Planejado + Previsão
            series_plot = cont_planejado
            label_plot = f"Planejado {ano_grafico}"
            series_extra = cont_prev
            label_extra = f"Previsão {ano_grafico} (base {ano_base})"

        # Tabela resumo + percentuais
        def _to_pct(n: int) -> float:
            if total_time <= 0:
                return 0.0
            return round((n / total_time) * 100.0, 2)

        df_resumo = pd.DataFrame({
            "Mês": meses,
            "Pessoas (Planejado)": cont_planejado,
            "% do time (Planejado)": [_to_pct(x) for x in cont_planejado],
            "Pessoas (Previsão)": cont_prev,
            "% do time (Previsão)": [_to_pct(x) for x in cont_prev],
        })

        st.markdown("### 📌 Resumo (contagem e percentual)")
        st.dataframe(df_resumo, use_container_width=True)

        # Alertas com base no que está sendo exibido principal
        st.markdown("### 🚨 Meses em alerta")

        alert_rows = []
        for m, val in zip(meses, series_plot):
            pct = _to_pct(val)

            passa_pessoas = (val > int(limite_pessoas)) if int(limite_pessoas) > 0 else False
            passa_pct = (pct > float(limite_percentual)) if float(limite_percentual) > 0 else False

            if modo_alerta.startswith("Disparar se passar em QUALQUER"):
                em_alerta = passa_pessoas or passa_pct
            else:
                em_alerta = passa_pessoas and passa_pct

            if em_alerta:
                alert_rows.append({
                    "Mês": m,
                    "Pessoas": val,
                    "% do time": pct,
                    "Limite pessoas": int(limite_pessoas),
                    "Limite %": float(limite_percentual),
                })

        if alert_rows:
            st.warning("Atenção: há meses que ultrapassam o limite definido.")
            st.dataframe(pd.DataFrame(alert_rows), use_container_width=True)
        else:
            st.success("Sem meses em alerta com os limites atuais.")

        # Gráfico de barras (matplotlib)
        st.markdown("### 📊 Gráfico (Barras)")

        import matplotlib.pyplot as plt

        x = meses
        plt.figure()
        plt.bar(x, series_plot, label=label_plot)

        # Se tiver extra (previsão junto), desenha outra série deslocada
        if series_extra is not None:
            # desloca levemente para caber lado a lado (sem mexer em cores)
            x2 = [v + 0.35 for v in x]
            plt.bar(x2, series_extra, label=label_extra)
            plt.xticks([v + 0.175 for v in x], x)
        else:
            plt.xticks(x, x)

        plt.xlabel("Mês")
        plt.ylabel("Pessoas em férias")
        plt.title(f"Férias — Setor {setor} — Ano {ano_grafico}")
        plt.legend()

        st.pyplot(plt)

        # Gráfico de percentual (opcional, mais visível)
        st.markdown("### 📈 Percentual do time (linha)")

        pct_series = [_to_pct(v) for v in series_plot]

        plt.figure()
        plt.plot(x, pct_series, marker="o")
        plt.xticks(x, x)
        plt.xlabel("Mês")
        plt.ylabel("% do time em férias")
        plt.title(f"% do time em férias — {ano_grafico}")

        # linhas de limite (%)
        if float(limite_percentual) > 0:
            plt.axhline(float(limite_percentual))
        st.pyplot(plt)
