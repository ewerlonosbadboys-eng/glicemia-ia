pandas.errors.DatabaseError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/glicemia-ia/main.py", line 1586, in <module>
    page_app()
    ~~~~~~~~^^
File "/mount/src/glicemia-ia/main.py", line 1571, in page_app
    page_setor_full(setor)
    ~~~~~~~~~~~~~~~^^^^^^^
File "/mount/src/glicemia-ia/main.py", line 1340, in page_setor_full
    escala, estado = generate_schedule_setor(setor, int(ano), int(mes), seed=int(seed))
                     ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/mount/src/glicemia-ia/main.py", line 644, in generate_schedule_setor
    prev_state = load_last_month_state(setor, ano, mes)
File "/mount/src/glicemia-ia/main.py", line 612, in load_last_month_state
    return load_estado_mes(setor, prev_year, prev_month)
File "/mount/src/glicemia-ia/main.py", line 534, in load_estado_mes
    df = pd.read_sql_query("""
        SELECT chapa, consec_trab_final, ultima_saida, ultimo_domingo_status, retorno_ferias_ate
        FROM estado_mes_anterior
        WHERE setor=? AND ano=? AND mes=?
    """, con, params=(setor, ano, mes))
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/io/sql.py", line 528, in read_sql_query
    return pandas_sql.read_query(
           ~~~~~~~~~~~~~~~~~~~~~^
        sql,
        ^^^^
    ...<6 lines>...
        dtype_backend=dtype_backend,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/io/sql.py", line 2728, in read_query
    cursor = self.execute(sql, params)
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/io/sql.py", line 2676, in execute
    raise ex from exc
