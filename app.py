import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="FeniceBet Pro", page_icon="🔥", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    .bet-card { 
        background-color: #1e1e2f; padding: 15px; border-radius: 10px; 
        border: 2px solid #ff00ff; box-shadow: 0px 0px 10px #ff00ff;
        text-align: center; color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('fenicebet_v4.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mcs (nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT 'NESSUNO')''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)''')
    conn.commit()
    return conn

conn = init_db()

# --- SESSION STATE ---
if "user" not in st.session_state: st.session_state.user = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "schedina" not in st.session_state: st.session_state.schedina = []

# --- LOGICA ESTRAZIONE RUOTA ---
def esegui_giro_pazzo(username):
    with st.spinner("ESTRAZIONE PREMIO CRAZY... 🌀"):
        time.sleep(2)
        premi = [
            {"label": "💰 +500 Points", "tipo": "punti", "val": 500},
            {"label": "🔥 +1000 Points", "tipo": "punti", "val": 1000},
            {"label": "🛡️ SCUDO FENICE (Cashback 50%)", "tipo": "bonus", "val": "CASHBACK_50"},
            {"label": "📈 BOOST QUOTA X2", "tipo": "bonus", "val": "BOOST_X2"},
            {"label": "🎟️ FREE BET da 1000 Punti", "tipo": "bonus", "val": "FREE_BET_1000"},
            {"label": "🏆 +2000 Points", "tipo": "punti", "val": 2000},
            {"label": "🚑 ASSICURAZIONE K.O. (Cashback 100%)", "tipo": "bonus", "val": "CASHBACK_100"},
            {"label": "🚀 BOOST QUOTA X3", "tipo": "bonus", "val": "BOOST_X3"},
            {"label": "💎 RADDOPPIO SALDO ATTUALE", "tipo": "moltiplicatore", "val": 2},
            {"label": "🎰 MEGA JACKPOT: 5000 Points!", "tipo": "punti", "val": 5000}
        ]
        pesi = [0.30, 0.25, 0.15, 0.10, 0.07, 0.05, 0.04, 0.02, 0.015, 0.005]
        vincita = random.choices(premi, weights=pesi, k=1)[0]
        
        if vincita["tipo"] == "punti": conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vincita["val"], username))
        elif vincita["tipo"] == "moltiplicatore": conn.execute("UPDATE utenti SET saldo = saldo * ? WHERE username=?", (vincita["val"], username))
        elif vincita["tipo"] == "bonus": conn.execute("UPDATE utenti SET bonus_attivo = ? WHERE username=?", (vincita["val"], username))
        conn.commit(); st.balloons(); st.success(f"🎊 RISULTATO: {vincita['label']}"); time.sleep(2); st.rerun()

# --- SIDEBAR E LOGIN ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("🔥 FENICE BET")
    if not st.session_state.user:
        choice = st.radio("Accesso", ["Login", "Registrati", "Admin"])
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if choice == "Registrati":
            e = st.text_input("Indirizzo Email")
            if st.button("REGISTRATI"):
                if not e or "@" not in e or "." not in e or any(f in e.lower() for f in ["asdf", "test", "fake"]):
                    st.error("Inserisci un'email valida!")
                else:
                    try:
                        conn.execute("INSERT INTO utenti (username, email, password) VALUES (?,?,?)", (u, e, p))
                        conn.commit(); st.success("Registrato! Login ora.")
                    except: st.error("Username preso.")
        elif st.button("ENTRA"):
            if choice == "Admin" and p == "admin123":
                st.session_state.user = "ADMIN"; st.session_state.is_admin = True; st.rerun()
            elif choice == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u, p)).fetchone()
                if res: st.session_state.user = u; st.rerun()
                else: st.error("Dati errati")
    else:
        st.write(f"Utente: **{st.session_state.user}**")
        if st.button("LOGOUT"): st.session_state.user = None; st.session_state.is_admin = False; st.rerun()

# --- LOGICA ADMIN E UTENTE ---
if st.session_state.is_admin:
    st.title("🕹️ Dashboard Gestore")
    t1, t2, t3 = st.tabs(["Crea Match", "Chiudi Match/Ranking", "Genera Token"])
    with t1:
        c1, c2 = st.columns(2)
        mc1 = c1.text_input("MC 1"); q1 = c1.number_input("Quota 1", 1.8)
        mc2 = c2.text_input("MC 2"); q2 = c2.number_input("Quota 2", 2.1)
        if st.button("PUBBLICA"):
            conn.execute("INSERT OR IGNORE INTO mcs (nome) VALUES (?)", (mc1,)); conn.execute("INSERT OR IGNORE INTO mcs (nome) VALUES (?)", (mc2,))
            conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{mc1} vs {mc2}", mc1, mc2, q1, q2, "APERTO")); conn.commit(); st.success("Online!")
    with t2:
        m_aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if m_aperti:
            s_m = st.selectbox("Match", options=[m[0] for m in m_aperti], format_func=lambda x: [m[1] for m in m_aperti if m[0]==x][0])
            d_m = [m for m in m_aperti if m[0] == s_m][0]
            v = st.radio("Vincitore", [d_m[2], d_m[3]])
            if st.button("CHIUDI E PAGA"):
                conn.execute("UPDATE matches SET stato='CHIUSO' WHERE id=?", (s_m,)); conn.execute("UPDATE mcs SET punti_ranking = punti_ranking + 3, vittorie = vittorie + 1 WHERE nome=?", (v,))
                tickets = conn.execute("SELECT id, username, dettagli, vincita_pot FROM ticket WHERE stato LIKE 'IN CORSO%'").fetchall()
                for t in tickets:
                    if f"{d_m[1]}->{v}" in t[2]:
                        conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (t[0],)); conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (t[3], t[1]))
                conn.commit(); st.rerun()
    with t3:
        if st.button("GENERA TOKEN"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"; conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,)); conn.commit(); st.code(tk)
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo, giro_punti_usato FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    st.metric("SALDO 🪙", f"{u_data[0]:.0f}")
    t_scomm, t_rank = st.tabs(["🔥 Scommesse", "🏆 Classifica"])
    with t_scomm:
        matches = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
        for m in matches:
            if st.button(f"🛒 Aggiungi alla Schedina: {m[1]} (@{m[4]})"): st.session_state.schedina.append({"id": m[0], "desc": m[1], "quota": m[4]})
        if st.session_state.schedina:
            if st.button("✅ GIOCA SCHEDINA"): 
                conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)", (st.session_state.user, str(st.session_state.schedina), 1.0, 100, 500, "IN CORSO")); conn.commit(); st.session_state.schedina = []; st.rerun()
    with t_rank:
        st.dataframe(pd.read_sql_query("SELECT nome AS MC, punti_ranking AS Punti FROM mcs ORDER BY punti_ranking DESC", conn))
else:
    c1, c2, c3 = st.columns([1,2,1])
    if os.path.exists("Logo.png"): c2.image("Logo.png", use_container_width=True)
    st.markdown("<h1 style='text-align: center;'>🔥 FeniceBet</h1>", unsafe_allow_html=True)
