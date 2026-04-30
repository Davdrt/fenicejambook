import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os
import math

# --- CONFIGURAZIONE ESTETICA ---
st.set_page_config(page_title="FeniceBet Pro", page_icon="🔥", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1a1a2e; padding: 15px; border-radius: 10px; border: 2px solid #4b0082; }
    .bet-card { 
        background-color: #1e1e2f; padding: 20px; border-radius: 15px; 
        border: 2px solid #ff00ff; box-shadow: 0px 0px 15px #ff00ff;
        text-align: center; color: white; margin-bottom: 20px;
    }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- ALGORITMO CALCOLO QUOTE ---
def calcola_quota_tecnica(nome_mc, margine=0.15):
    """
    Calcola la probabilità basata su: 
    Rating = ((Vittorie * 10) + 5) / (Presenze + 10)
    Probabilità = Rating * Pericolo * (0.8 + Popolarità * 0.05)
    """
    res = conn.execute("SELECT vittorie, presenze, pericolo, popolarita FROM mcs WHERE nome=?", (nome_mc,)).fetchone()
    if not res or res[1] == 0: return 2.0 # Quota standard se MC nuovo
    v, p, per, pop = res
    rating = ((v * 10) + 5) / (p + 10)
    prob = rating * per * (0.8 + pop * 0.05)
    # Trasforma in quota decimale invertita e aggiunge margine del banco
    quota = 1 / (prob / (prob + 1)) + margine
    return round(max(1.10, min(quota, 10.0)), 2)

# --- DATABASE ENGINE (v7) ---
def init_db():
    conn = sqlite3.connect('fenicebet_v7.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mcs (
                 nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0, 
                 presenze INT DEFAULT 0, pericolo REAL DEFAULT 1.0, popolarita INT DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (
                 username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, 
                 giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT 'NESSUNO')''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT, vincitore TEXT DEFAULT 'TBD')''')
    c.execute('''CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)''')
    conn.commit()
    return conn

conn = init_db()

# --- SESSION STATE ---
if "user" not in st.session_state: st.session_state.user = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "schedina" not in st.session_state: st.session_state.schedina = []

# --- RUOTA 10 PREMI ---
def esegui_giro_pazzo(username):
    with st.spinner("🌀 LA RUOTA GIRA..."):
        time.sleep(2)
        premi = [
            {"label": "💰 +500 Points", "tipo": "punti", "val": 500},
            {"label": "🔥 +1000 Points", "tipo": "punti", "val": 1000},
            {"label": "🛡️ SCUDO FENICE (50% Cashback)", "tipo": "bonus", "val": "CASHBACK_50"},
            {"label": "📈 BOOST QUOTA X2", "tipo": "bonus", "val": "BOOST_X2"},
            {"label": "🎟️ FREE BET 1000", "tipo": "bonus", "val": "FREE_BET_1000"},
            {"label": "🏆 +2000 Points", "tipo": "punti", "val": 2000},
            {"label": "🚑 ASSICURAZIONE 100%", "tipo": "bonus", "val": "CASHBACK_100"},
            {"label": "🚀 BOOST QUOTA X3", "tipo": "bonus", "val": "BOOST_X3"},
            {"label": "💎 RADDOPPIO SALDO", "tipo": "moltiplicatore", "val": 2},
            {"label": "🎰 MEGA JACKPOT: 5000!", "tipo": "punti", "val": 5000}
        ]
        pesi = [0.30, 0.25, 0.15, 0.10, 0.07, 0.05, 0.04, 0.02, 0.015, 0.005]
        v = random.choices(premi, weights=pesi, k=1)[0]
        if v["tipo"] == "punti": conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (v["val"], username))
        elif v["tipo"] == "moltiplicatore": conn.execute("UPDATE utenti SET saldo = saldo * ? WHERE username=?", (v["val"], username))
        elif v["tipo"] == "bonus": conn.execute("UPDATE utenti SET bonus_attivo = ? WHERE username=?", (v["val"], username))
        conn.commit(); st.balloons(); st.success(f"🎊 {v['label']}"); time.sleep(2); st.rerun()

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("🔥 FENICE BET")
    if not st.session_state.user:
        mode = st.radio("Seleziona", ["Login", "Registrati", "Admin"])
        u_in = st.text_input("Username")
        p_in = st.text_input("Password", type="password")
        if mode == "Registrati":
            e_in = st.text_input("Email")
            if st.button("REGISTRATI"):
                if "@" not in e_in or "." not in e_in: st.error("Email non valida!")
                else:
                    try:
                        conn.execute("INSERT INTO utenti (username, email, password) VALUES (?,?,?)", (u_in, e_in, p_in))
                        conn.commit(); st.success("Registrato!")
                    except: st.error("Username esistente.")
        elif st.button("ACCEDI"):
            if mode == "Admin" and p_in == "admin123":
                st.session_state.user = "ADMIN"; st.session_state.is_admin = True; st.rerun()
            elif mode == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u_in, p_in)).fetchone()
                if res: st.session_state.user = u_in; st.rerun()
                else: st.error("Dati errati.")
    else:
        st.write(f"👤 **{st.session_state.user}**")
        if st.button("LOGOUT"): st.session_state.user = None; st.session_state.is_admin = False; st.rerun()

# --- LOGICA ADMIN ---
if st.session_state.is_admin:
    st.title("🕹️ Dashboard Admin")
    t1, t2, t3, t4, t5 = st.tabs(["Crea Match", "Anagrafica MC", "Chiudi Match", "Token Ruota", "Utenti"])
    
    with t1:
        st.subheader("Algoritmo Quote")
        mcs_list = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
        if not mcs_list: st.warning("Aggiungi MC nell'Anagrafica prima!")
        else:
            col1, col2 = st.columns(2)
            mc_1 = col1.selectbox("Seleziona MC 1", mcs_list)
            q_calc1 = calcola_quota_tecnica(mc_1)
            q_f1 = col1.number_input("Quota Finale 1", value=q_calc1)
            
            mc_2 = col2.selectbox("Seleziona MC 2", mcs_list)
            q_calc2 = calcola_quota_tecnica(mc_2)
            q_f2 = col2.number_input("Quota Finale 2", value=q_calc2)
            
            if st.button("PUBBLICA SCONTRO"):
                conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{mc_1} vs {mc_2}", mc_1, mc_2, q_f1, q_f2, "APERTO"))
                conn.commit(); st.success("Match Online!")

    with t2:
        st.subheader("Gestione Tecnica MC")
        nome_new = st.text_input("Nome MC")
        v_new = st.number_input("Vittorie", 0)
        p_new = st.number_input("Presenze", 0)
        per_new = st.slider("Pericolo (da 0.5 a 2.0)", 0.5, 2.0, 1.0)
        pop_new = st.slider("Popolarità (da 1 a 10)", 1, 10, 5)
        if st.button("AGGIORNA/AGGIUNGI MC"):
            conn.execute("INSERT OR REPLACE INTO mcs (nome, vittorie, presenze, pericolo, popolarita) VALUES (?,?,?,?,?)", (nome_new, v_new, p_new, per_new, pop_new))
            conn.commit(); st.success("Dati MC salvati!")

    with t3:
        m_aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if m_aperti:
            sel = st.selectbox("Scegli Match", [m[0] for m in m_aperti], format_func=lambda x: [m[1] for m in m_aperti if m[0]==x][0])
            m_d = [m for m in m_aperti if m[0]==sel][0]
            vinc = st.radio("Vincitore", [m_d[2], m_d[3]])
            if st.button("CHIUDI E PAGA"):
                conn.execute("UPDATE matches SET stato='CHIUSO', vincitore=? WHERE id=?", (vinc, sel))
                conn.execute("UPDATE mcs SET punti_ranking = punti_ranking + 3, vittorie = vittorie + 1, presenze = presenze + 1 WHERE nome=?", (vinc,))
                conn.execute("UPDATE mcs SET presenze = presenze + 1 WHERE nome=?", (m_d[2] if vinc != m_d[2] else m_d[3],))
                # Logica Payout semplificata
                conn.commit(); st.rerun()

    with t4:
        if st.button("GENERA TOKEN PREMIUM"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"; conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,)); conn.commit(); st.code(tk)
    with t5:
        users = pd.read_sql_query("SELECT username, email, saldo FROM utenti", conn)
        st.dataframe(users, use_container_width=True)

# --- AREA UTENTE ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo, giro_punti_usato, bonus_attivo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo, giro_usato, bonus = u_data
    st.metric("SALDO 🪙", f"{saldo:.0f}")
    if bonus != "NESSUNO": st.info(f"BONUS: {bonus}")
    
    ut1, ut2, ut3 = st.tabs(["Scommesse", "Crazy Wheel", "Ranking"])
    with ut1:
        cl, cr = st.columns([2, 1.2])
        with cl:
            active = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            for m in active:
                with st.expander(f"📌 {m[1]}"):
                    choice = st.radio("Punta su:", [m[2], m[3]], key=f"r_{m[0]}")
                    q = m[4] if choice == m[2] else m[5]
                    if st.button(f"Aggiungi @{q:.2f}", key=f"a_{m[0]}"):
                        if not any(x['id'] == m[0] for x in st.session_state.schedina):
                            st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":choice, "quota":q})
                            st.rerun()
        with cr:
            if not st.session_state.schedina: st.info("Scegli un match")
            else:
                qt = 1.0
                for s in st.session_state.schedina:
                    st.write(f"🔹 {s['desc']} -> {s['scelta']}")
                    qt *= s['quota']
                st.write(f"📈 QUOTA: **{qt:.2f}**")
                pnt = st.number_input("Puntata", 10, int(saldo))
                v_pot = pnt * qt
                if v_pot > 500000: v_pot = 500000
                st.write(f"💰 VINCITA: **{v_pot:.0f}**")
                if st.button("GIOCA"):
                    conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (pnt, st.session_state.user))
                    det = " | ".join([f"{x['desc']}->{x['scelta']}" for x in st.session_state.schedina])
                    conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)", (st.session_state.user, det, qt, pnt, v_pot, "IN CORSO"))
                    conn.commit(); st.session_state.schedina = []; st.balloons(); st.rerun()

    with ut2:
        if giro_usato == 0:
            if st.button("GIRA OMAGGIO (500 Punti)"):
                if saldo >= 500: conn.execute("UPDATE utenti SET saldo=saldo-500, giro_punti_usato=1 WHERE username=?"); esegui_giro_pazzo(st.session_state.user)
        else:
            t_in = st.text_input("Token Premium")
            if st.button("SBLOCCA E GIRA"):
                res = conn.execute("SELECT usato FROM tokens WHERE codice=?", (t_in,)).fetchone()
                if res and res[0]==0: conn.execute("UPDATE tokens SET usato=1 WHERE codice=?"); esegui_giro_pazzo(st.session_state.user)
    with ut3:
        st.dataframe(pd.read_sql_query("SELECT nome AS MC, punti_ranking AS Punti FROM mcs ORDER BY Punti DESC", conn), use_container_width=True)

else:
    c1, c2, c3 = st.columns([1,2,1])
    if os.path.exists("Logo.png"): c2.image("Logo.png")
    st.markdown("<h1 style='text-align: center;'>🔥 FENICE BET PRO</h1>", unsafe_allow_html=True)
