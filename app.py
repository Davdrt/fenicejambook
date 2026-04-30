import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os
import plotly.express as px

# --- CONFIGURAZIONE UI PREMIUM ---
st.set_page_config(page_title="FeniceBet", page_icon="🔥", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #050505;
        font-family: 'Rajdhani', sans-serif;
        color: #d4af37;
    }

    /* CARD STYLE */
    [data-testid="stExpander"] { background-color: #111; border: 1px solid #d4af37; border-radius: 10px; }
    
    /* BOTTONE ORO */
    .stButton>button {
        background: linear-gradient(135deg, #d4af37 0%, #b8860b 100%);
        color: black !important;
        font-weight: 800;
        border: none;
        border-radius: 5px;
        text-transform: uppercase;
        transition: 0.3s;
    }
    .stButton>button:hover { box-shadow: 0 0 15px #d4af37; transform: translateY(-2px); }

    /* ANIMAZIONE RUOTA */
    @keyframes wheelSpin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(var(--rotation)); }
    }
    .wheel-base {
        width: 280px; height: 280px;
        border: 10px solid #d4af37;
        border-radius: 50%;
        margin: auto;
        background: conic-gradient(#000, #d4af37, #111, #d4af37, #000, #d4af37);
        animation: wheelSpin 5s cubic-bezier(0.15, 0, 0.15, 1) forwards;
    }

    /* POPUP VINCITA */
    .win-popup {
        background: rgba(212, 175, 55, 0.1);
        border: 2px solid #d4af37;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        animation: fadeIn 1s;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE v11 ---
def init_db():
    conn = sqlite3.connect('fenicebet_v11.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS mcs (nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0, presenze INT DEFAULT 0, pericolo REAL DEFAULT 1.0, popolarita INT DEFAULT 1)')
    c.execute('CREATE TABLE IF NOT EXISTS utenti (username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT "NESSUNO")')
    c.execute('CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT, vincitore TEXT DEFAULT "TBD")')
    c.execute('CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS flussi (id INTEGER PRIMARY KEY AUTOINCREMENT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, tipo TEXT, importo REAL, user TEXT)')
    # Creiamo l'account admin come player se non esiste
    c.execute('INSERT OR IGNORE INTO utenti (username, email, password, saldo) VALUES ("ADMIN", "admin@fenice.bet", "admin123", 10000)')
    conn.commit()
    return conn

conn = init_db()

# --- UTILS ---
def registra_movimento(tipo, importo, user):
    conn.execute("INSERT INTO flussi (tipo, importo, user) VALUES (?,?,?)", (tipo, importo, user))
    conn.commit()

def calcola_quote(mc_nome):
    res = conn.execute("SELECT vittorie, presenze, pericolo, popolarita FROM mcs WHERE nome=?", (mc_nome,)).fetchone()
    if not res or res[1] == 0: return 1.85
    v, p, per, pop = res
    rate = ((v * 12) + 5) / (p + 10)
    prob = rate * per * (0.9 + pop * 0.05)
    return round(max(1.20, min(1 / (prob / (prob + 1)) + 0.10, 8.0)), 2)

# --- SESSION STATE ---
for key in ['user', 'is_admin', 'view_as_player', 'schedina']:
    if key not in st.session_state: st.session_state[key] = None if key != 'schedina' else []

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("FeniceBet")
    
    if not st.session_state.user:
        mode = st.radio("Menu", ["Login", "Registrati", "Admin"])
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if mode == "Registrati":
            em = st.text_input("Email")
            if st.button("UNISCITI ALLA JAM"):
                if "@" not in em or "." not in em: st.error("Email non valida!")
                else:
                    try:
                        conn.execute("INSERT INTO utenti (username, email, password) VALUES (?,?,?)", (u, em, p))
                        conn.commit(); registra_movimento("INGRESSO", 1000, u); st.success("Benvenuto!")
                    except: st.error("Username occupato.")
        elif st.button("ENTRA NELL'ARENA"):
            if mode == "Admin" and p == "admin123":
                st.session_state.user, st.session_state.is_admin = "ADMIN", True; st.rerun()
            elif mode == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u,p)).fetchone()
                if res: st.session_state.user = u; st.rerun()
                else: st.error("Dati errati.")
    else:
        st.write(f"👑 Warrior: **{st.session_state.user}**")
        if st.session_state.is_admin:
            st.session_state.view_as_player = st.toggle("Vista Giocatore", st.session_state.view_as_player)
            if st.button("🚀 BOOST ADMIN SALDO (+10k)"):
                conn.execute("UPDATE utenti SET saldo = saldo + 10000 WHERE username='ADMIN'")
                conn.commit(); st.rerun()
        if st.button("LOGOUT"):
            for k in st.session_state.keys(): st.session_state[k] = None
            st.rerun()

# --- INTERFACCIA ADMIN ---
if st.session_state.is_admin and not st.session_state.view_as_player:
    st.title("🕹️ Dashboard del Fondatore")
    tabs = st.tabs(["📉 Flussi Cassa", "⚔️ Gestione Match", "🎤 Anagrafica MC", "🎫 Token"])
    
    with tabs[0]:
        df_f = pd.read_sql_query("SELECT ts, importo FROM flussi", conn)
        if not df_f.empty:
            df_f['Saldo Sistema'] = df_f['importo'].cumsum()
            st.plotly_chart(px.line(df_f, x='ts', y='Saldo Sistema', template="plotly_dark", color_discrete_sequence=['#d4af37']), use_container_width=True)
        
    with tabs[1]:
        col1, col2 = st.columns(2)
        mcs = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
        m1 = col1.selectbox("MC 1", mcs); q1 = col1.number_input("Quota 1", calcola_quote(m1))
        m2 = col2.selectbox("MC 2", mcs); q2 = col2.number_input("Quota 2", calcola_quote(m2))
        if st.button("LANCIA MATCH"):
            conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{m1} vs {m2}", m1, m2, q1, q2, "APERTO"))
            conn.commit(); st.success("Match Online!")
        
        st.divider()
        st.subheader("Chiudi Match")
        aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if aperti:
            sel_m = st.selectbox("Scegli Match", [m[0] for m in aperti], format_func=lambda x: [m[1] for m in aperti if m[0]==x][0])
            winner = st.radio("Vincitore", [m[2] for m in aperti if m[0]==sel_m][0], [m[3] for m in aperti if m[0]==sel_m][0])
            if st.button("DECRETA VINCITORE"):
                conn.execute("UPDATE matches SET stato='CHIUSO', vincitore=? WHERE id=?", (winner, sel_m))
                conn.execute("UPDATE mcs SET punti_ranking=punti_ranking+3, vittorie=vittorie+1, presenze=presenze+1 WHERE nome=?", (winner,))
                # Payout
                tickets = conn.execute("SELECT id, username, vincita_pot FROM ticket WHERE stato='IN CORSO' AND dettagli LIKE ?", (f"%{winner}%",)).fetchall()
                for t in tickets:
                    conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (t[2], t[1]))
                    conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (t[0],))
                    registra_movimento("VINCITA", t[2], t[1])
                conn.commit(); st.success("Liquidazione completata!"); st.rerun()

    with tabs[2]:
        nm = st.text_input("Nuovo MC")
        if st.button("AGGIUNGI MC"):
            conn.execute("INSERT OR IGNORE INTO mcs (nome) VALUES (?)", (nm,))
            conn.commit(); st.rerun()

# --- INTERFACCIA GIOCATORE ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo = u_data[0]
    
    st.title("🏟️ FeniceBet Arena")
    st.metric("PUNTI DISPONIBILI", f"{saldo:,.0f} 🪙")
    
    u_tabs = st.tabs(["🎮 Scommesse", "🎡 Crazy Wheel", "📊 Leaderboard"])
    
    with u_tabs[0]:
        c1, c2 = st.columns([2, 1.2])
        with c1:
            st.subheader("Match Live")
            matches = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            for m in matches:
                with st.container():
                    st.markdown(f"**{m[1]}**")
                    ca, cb = st.columns(2)
                    if ca.button(f"{m[2]} @{m[4]}", key=f"q1_{m[0]}"):
                        st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":m[2], "quota":m[4]})
                    if cb.button(f"{m[3]} @{m[5]}", key=f"q2_{m[0]}"):
                        st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":m[3], "quota":m[5]})
        with c2:
            st.subheader("Schedina")
            if not st.session_state.schedina: st.info("Scegli una quota")
            else:
                q_t = 1.0
                for s in st.session_state.schedina:
                    st.write(f"✅ {s['scelta']} (@{s['quota']})")
                    q_t *= s['quota']
                pnt = st.number_input("Puntata", 10, int(saldo))
                vinc = pnt * q_t
                if vinc > 500000: vinc = 500000; st.warning("Cap 500k!")
                if st.button("PIAZZA GIOCATA"):
                    conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (pnt, st.session_state.user))
                    det = " | ".join([f"{x['desc']}->{x['scelta']}" for x in st.session_state.schedina])
                    conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)", (st.session_state.user, det, q_t, pnt, vinc, "IN CORSO"))
                    registra_movimento("BET", -pnt, st.session_state.user)
                    conn.commit(); st.session_state.schedina = []; st.balloons(); st.rerun()
            if st.button("Svuota"): st.session_state.schedina = []; st.rerun()

    with u_tabs[1]:
        st.subheader("🎡 Crazy Wheel")
        tok = st.text_input("Inserisci Token Premium")
        if st.button("GIRA!"):
            res = conn.execute("SELECT usato FROM tokens WHERE codice=?", (tok,)).fetchone()
            if res and res[0] == 0:
                conn.execute("UPDATE tokens SET usato=1 WHERE codice=?", (tok,))
                rot = random.randint(3000, 6000)
                st.markdown(f"<div class='wheel-base' style='--rotation: {rot}deg;'></div>", unsafe_allow_html=True)
                with st.spinner("Calcolo premio..."): time.sleep(5)
                vinto = random.choice([500, 1000, 2000, 5000, 10000])
                conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vinto, st.session_state.user))
                conn.commit(); st.markdown(f"<div class='win-popup'><h2>🔥 VINTI {vinto} PUNTI!</h2></div>", unsafe_allow_html=True)
                st.balloons()
            else: st.error("Token non valido")

    with u_tabs[2]:
        ca, cb = st.columns(2)
        ca.write("🏆 Top Warriors")
        ca.table(pd.read_sql_query("SELECT username, saldo FROM utenti ORDER BY saldo DESC LIMIT 5", conn))
        cb.write("🎤 Ranking MC")
        cb.table(pd.read_sql_query("SELECT nome, punti_ranking FROM mcs ORDER BY punti_ranking DESC", conn))

else:
    c1, c2, c3 = st.columns([1,2,1])
    if os.path.exists("Logo.png"): c2.image("Logo.png")
    st.markdown("<h1 style='text-align: center; color: #d4af37;'>FeniceBet</h1>", unsafe_allow_html=True)
    st.write("Registrati per scommettere sui match della Fenice Jam!")
