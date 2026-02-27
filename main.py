# ===============================================
# ESCALA 5x2 PROFISSIONAL COM PREFERÊNCIA SUBGRUPO
# ===============================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import random
import calendar

st.set_page_config(layout="wide")

DB = "escala.db"

# ===============================================
# BANCO
# ===============================================

def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS colaboradores(
        id INTEGER PRIMARY KEY,
        nome TEXT,
        setor TEXT,
        chapa TEXT,
        subgrupo TEXT,
        entrada TEXT,
        folga_sab INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subgrupo_regras(
        setor TEXT,
        subgrupo TEXT,
        evitar_seg INTEGER DEFAULT 0,
        evitar_ter INTEGER DEFAULT 0,
        evitar_qua INTEGER DEFAULT 0,
        evitar_qui INTEGER DEFAULT 0,
        evitar_sex INTEGER DEFAULT 0,
        evitar_sab INTEGER DEFAULT 0,
        UNIQUE(setor, subgrupo)
    )
    """)

    c.commit()
    c.close()

init_db()

# ===============================================
# UTIL
# ===============================================

D_PT = {
    "Monday": "seg",
    "Tuesday": "ter",
    "Wednesday": "qua",
    "Thursday": "qui",
    "Friday": "sex",
    "Saturday": "sáb",
    "Sunday": "dom"
}

INTERSTICIO = timedelta(hours=11, minutes=10)
JORNADA = timedelta(hours=9, minutes=58)

def gerar_datas(ano, mes):
    dias = calendar.monthrange(ano, mes)[1]
    return pd.date_range(f"{ano}-{mes:02d}-01", periods=dias)

def pode_folgar(df, i):
    if df.loc[i,"Status"]!="Trabalho": return False
    if i>0 and df.loc[i-1,"Status"]=="Folga": return False
    if i<len(df)-1 and df.loc[i+1,"Status"]=="Folga": return False
    return True

# ===============================================
# MOTOR ESCALA COM PREFERÊNCIA
# ===============================================

def gerar_escala(setor, colaboradores, ano, mes):

    datas = gerar_datas(ano, mes)
    df_ref = pd.DataFrame({
        "Data": datas,
        "Dia": [D_PT[d.day_name()] for d in datas]
    })

    hist = {}

    # agrupar por subgrupo
    grupos = {}
    for c in colaboradores:
        sg = c["subgrupo"] if c["subgrupo"] else "SEM SUBGRUPO"
        grupos.setdefault(sg, []).append(c)

    for sg, membros in grupos.items():

        # pegar regra de preferência
        c = conn()
        regra = c.execute(
            "SELECT * FROM subgrupo_regras WHERE setor=? AND subgrupo=?",
            (setor, sg)
        ).fetchone()
        c.close()

        evitar = {}
        if regra:
            evitar = {
                "seg": regra[2],
                "ter": regra[3],
                "qua": regra[4],
                "qui": regra[5],
                "sex": regra[6],
                "sáb": regra[7],
            }

        # domingo 1x1
        domingos = [i for i,d in enumerate(datas) if d.day_name()=="Sunday"]
        membros_ord = membros.copy()
        random.shuffle(membros_ord)
        metade = len(membros_ord)//2

        grupo_a = membros_ord[:metade]
        grupo_b = membros_ord[metade:]

        for m in membros:

            df = df_ref.copy()
            df["Status"]="Trabalho"

            # domingo alternado
            for k,idx in enumerate(domingos):
                if k%2==0:
                    if m in grupo_a:
                        df.loc[idx,"Status"]="Folga"
                else:
                    if m in grupo_b:
                        df.loc[idx,"Status"]="Folga"

            # completar 5x2
            for semana_inicio in range(0,len(df),7):

                semana = range(semana_inicio,min(semana_inicio+7,len(df)))
                folgas = sum(df.loc[i,"Status"]=="Folga" for i in semana)

                while folgas<2:
                    candidatos = []
                    for i in semana:
                        dia = df.loc[i,"Dia"]
                        if dia=="dom": continue
                        if not pode_folgar(df,i): continue

                        score = 0

                        # penalidade por preferência
                        if dia in evitar and evitar[dia]==1:
                            score += 100

                        # balanceamento simples
                        score += sum(df.loc[j,"Status"]=="Folga" for j in semana)

                        candidatos.append((score,i))

                    if not candidatos:
                        break

                    candidatos.sort(key=lambda x:x[0])
                    escolhido = candidatos[0][1]
                    df.loc[escolhido,"Status"]="Folga"
                    folgas+=1

            hist[m["chapa"]] = df

    return hist

# ===============================================
# INTERFACE
# ===============================================

st.title("Escala 5x2 com Preferência Subgrupo")

aba1,aba2 = st.tabs(["Subgrupo Preferência","Gerar Escala"])

with aba1:

    st.subheader("Preferência de dias com MENOS folga")

    setor="GERAL"
    subgrupo=st.text_input("Subgrupo")

    col1,col2,col3=st.columns(3)

    ev_seg=col1.checkbox("Evitar SEG")
    ev_ter=col1.checkbox("Evitar TER")
    ev_qua=col2.checkbox("Evitar QUA")
    ev_qui=col2.checkbox("Evitar QUI")
    ev_sex=col3.checkbox("Evitar SEX")
    ev_sab=col3.checkbox("Evitar SAB")

    if st.button("Salvar Regra"):
        c=conn()
        c.execute("""
        INSERT OR REPLACE INTO subgrupo_regras
        VALUES(?,?,?,?,?,?,?,?)
        """,(setor,subgrupo,
             int(ev_seg),int(ev_ter),int(ev_qua),
             int(ev_qui),int(ev_sex),int(ev_sab)))
        c.commit()
        c.close()
        st.success("Regra salva")

with aba2:

    st.subheader("Gerar Escala")

    ano=st.number_input("Ano",2025,2100,2026)
    mes=st.selectbox("Mês",list(range(1,13)))

    c=conn()
    colaboradores=pd.read_sql_query(
        "SELECT * FROM colaboradores WHERE setor=?",
        c,params=("GERAL",)
    ).to_dict("records")
    c.close()

    if st.button("Gerar"):
        hist=gerar_escala("GERAL",colaboradores,ano,mes)

        for ch,df in hist.items():
            st.write(f"Chapa {ch}")
            st.dataframe(df)
