def _to_min(hhmm: str) -> int:
    if not hhmm:
        return 0
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m

def _min_to_hhmm(x: int) -> str:
    x %= (24 * 60)
    return f"{x//60:02d}:{x%60:02d}"

def _add_min(hhmm: str, delta: timedelta) -> str:
    return _min_to_hhmm(_to_min(hhmm) + int(delta.total_seconds()//60))

def _saida_from_entrada(ent: str) -> str:
    return _add_min(ent, DURACAO_JORNADA)

def _ajustar_para_intersticio(ent_desejada: str, saida_anterior: str) -> str:
    """Retorna a entrada mais cedo possível >= desejada, respeitando 11:10 após saída anterior."""
    if not ent_desejada or not saida_anterior:
        return ent_desejada
    min_ent = _add_min(saida_anterior, INTERSTICIO_MIN)
    # Se min_ent "passa" da meia noite, ainda assim está correto em HH:MM (comparação precisa em minutos circular é chata)
    # Então comparamos em linha do tempo relativa assumindo "dia seguinte":
    s = _to_min(saida_anterior)
    e_des = _to_min(ent_desejada)
    e_min = _to_min(min_ent)

    # modela dia seguinte: entrada e_min e e_des podem estar "no dia seguinte"
    # se e_des <= s, então e_des é no dia seguinte -> +1440
    if e_des <= s: e_des += 1440
    if e_min <= s: e_min += 1440

    e_ok = max(e_des, e_min)
    return _min_to_hhmm(e_ok)

def recompute_hours_with_intersticio(df: pd.DataFrame, ent_padrao: str, ultima_saida_prev: str | None = None):
    """
    Regra global:
      - Para dias de trabalho (inclui Balanço/Madrugada): sempre garantir 11:10 desde a última saída.
      - Balanço e Balanço Madrugada: horário fixo (não muda), mas ainda gera 'conflito' com dia anterior.
        (O tratamento do conflito com dia fixo entra na etapa B abaixo.)
      - Trabalho normal: ajusta entrada para cumprir 11:10.
    """
    ents, sais = [], []
    last_saida = ultima_saida_prev or ""

    for i in range(len(df)):
        stt = df.loc[i, "Status"]

        if stt not in WORK_STATUSES:
            ents.append("")
            sais.append("")
            last_saida = ""  # zera cadeia
            continue

        # FIXOS
        if stt == BALANCO_STATUS:
            ent = BALANCO_DIA_ENTRADA
            sai = BALANCO_DIA_SAIDA
            ents.append(ent); sais.append(sai)
            last_saida = sai
            continue

        if stt == BALANCO_MADRUGADA_STATUS:
            ent = BALANCO_MADRUGADA_ENTRADA
            sai = BALANCO_MADRUGADA_SAIDA
            ents.append(ent); sais.append(sai)
            last_saida = sai
            continue

        # TRABALHO NORMAL
        ent_desejada = (df.loc[i, "H_Entrada"] or "").strip() or ent_padrao
        if last_saida:
            ent_ok = _ajustar_para_intersticio(ent_desejada, last_saida)
        else:
            ent_ok = ent_desejada

        sai_ok = _saida_from_entrada(ent_ok)
        ents.append(ent_ok); sais.append(sai_ok)
        last_saida = sai_ok

    df["H_Entrada"] = ents
    df["H_Saida"] = sais
