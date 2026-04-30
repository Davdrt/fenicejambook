import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os

# --- CONFIGURAZIONE UI AVANZATA ---
st.set_page_config(page_title="FeniceBet Ultimate", page_icon="🔥", layout="wide")

# CSS PER EFFETTI NEON, ANIMAZIONE RUOTA E POP-UP
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #050505;
        font-family: 'Orbitron', sans-serif;
        color: #e0e0e0;
    }

    /* CARD MATCH NEON */
    .match-card {
        background: linear-gradient(145deg, #0f0f1a, #1a1a2e);
        border: 1px solid #d4af37; /* Oro come il tuo token */
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 0 15px rgba(212, 175, 55, 0.2);
        transition: 0.3s;
    }
    .match-card:hover {
        box-shadow: 0 0 25px rgba(212, 175, 55, 0.5);
        transform: translateY(-5px);
    }

    /* BOTTONI PREMIUM */
    .stButton>button {
        background: linear-gradient(90deg, #d4af37, #f2d472);
        color: black !important;
        border: none;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-radius: 50px;
        box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
    }

    /* ANIMAZIONE RUOTA DINAMICA */
    @keyframes spin-decelerate {
        0% { transform: rotate(0deg); }
        20% { transform: rotate(1000deg); }
        50% { transform: rotate(1800deg); }
        80% { transform: rotate(2400deg); }
        100% { transform: rotate(var(--final-rotation)); }
    }
    .wheel-container {
        width: 300px;
        height: 300px;
        margin: auto;
        border: 10px solid #d4af37;
        border-radius: 50%;
        position: relative;
        overflow: hidden;
        background: conic-gradient(#1a1a2e, #d4af37, #1a1a2e, #d4af37, #1a1a2e, #d4af37);
        animation: spin-decelerate 4s cubic-bezier(0.15, 0, 0.15, 1) forwards;
    }

    /* POP-UP VINCITA */
    .win-popup {
        position: fixed;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0,0,0,0.9);
        padding: 40px;
        border: 3px solid #d4af37;
        border-radius: 20px;
        z-index: 9999;
        text-align: center;
        box-shadow: 0 0 100px #d4af37;
        animation: bounce 0.5s ease;
    }
    </style>
    """, unsafe_allow_html=True)

# --- MOTORE DATABASE v9 ---
def init_db():
    conn = sqlite3.connect('fenicebet_v9.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mcs (nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0, presenze INT DEFAULT 0, pericolo REAL DEFAULT 1.0, popolarita INT DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT 'NESSUNO')''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)''')
    conn.commit()
    return conn

conn = init_db()

# --- LOGICA RUOTA CON POP-UP ---
def esegui_giro_premium(username):
    # Generiamo un premio "pesato"
    premi = ["💰 +1000", "🔥 QUOTA X3", "💎 RADDOPPIO", "🛡️ CASHBACK 100%", "🏆 +5000"]
    vincita = random.choice(premi)
    
    # Animazione e Sospensione
    rotation = random.randint(2500, 5000)
    st.markdown(f"<div class='wheel-container' style='--final-rotation: {rotation}deg;'></div>", unsafe_allow_html=True)
    
    with st.spinner("La Fenice sta scegliendo il tuo destino..."):
        time.sleep(4) # Durata animazione CSS
        
    # POP-UP FINALE
    st.markdown(f"""
        <div class='win-popup'>
            <h1 style='color: #d4af37;'>🎉 VITTORIA! 🎉</h1>
            <h2 style='color: white;'>Hai vinto: {vincita}</h2>
            <p>Il premio è stato accreditato sul tuo profilo.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Aggiornamento DB (Esempio semplificato)
    if vincita == "💰 +1000": conn.execute("UPDATE utenti SET saldo = saldo + 1000 WHERE username=?", (username,))
    conn.commit()
    time.sleep(3)
    st.rerun()

# --- SESSION STATE ---
if "user" not in st.session_state: st.session_state.user = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "schedina" not in st.session_state: st.session_state.schedina = []

# --- INTERFACCIA ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("🔥 FENICE BET ULTIMATE")
    
    if not st.session_state.user:
        mode = st.radio("Accesso", ["Login", "Registrati", "Admin"])
        u_in = st.text_input("Username")
        p_in = st.text_input("Password", type="password")
        if st.button("ACCEDI"):
            if mode == "Admin" and p_in == "admin123":
                st.session_state.user = "ADMIN"; st.session_state.is_admin = True; st.rerun()
            elif mode == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u_in, p_in)).fetchone()
                if res: st.session_state.user = u_in; st.rerun()
                else: st.error("Dati errati")
    else:
        st.write(f"👑 **{st.session_state.user}**")
        if st.button("LOGOUT"):
            st.session_state.user = None; st.session_state.is_admin = False; st.rerun()

# --- AREA ADMIN ---
if st.session_state.is_admin:
    st.title("🕹️ Controllo Supremo")
    t1, t2, t3 = st.tabs(["⚔️ Gestione Match", "🪙 Generatore Token", "📊 Utenti"])
    with t1:
        st.subheader("Crea Match")
        c1, c2 = st.columns(2)
        m1 = c1.text_input("MC 1")
        m2 = c2.text_input("MC 2")
        q1 = c1.number_input("Quota 1", 1.8)
        q2 = c2.number_input("Quota 2", 1.8)
        if st.button("PUBBLICA MATCH"):
            conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{m1} vs {m2}", m1, m2, q1, q2, "APERTO"))
            conn.commit(); st.success("Match Online!")
    with t2:
        if st.button("GENERA TOKEN FENICE 🎫"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"
            conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,)); conn.commit()
            st.code(tk)

# --- AREA UTENTE ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo = u_data[0]
    
    st.markdown(f"### 🪙 Saldo: **{saldo:,.0f} Punti**")
    
    col_main, col_bet = st.columns([2, 1.2])
    
    with col_main:
        st.subheader("🔥 Match Live")
        matches = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
        for m in matches:
            st.markdown(f"""
            <div class='match-card'>
                <h4>{m[1]}</h4>
                <p>Quota {m[2]}: <b>{m[4]}</b> | Quota {m[3]}: <b>{m[5]}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            # SCELTA SINGOLA O AGGIUNTA A MULTIPLA
            c_a, c_b, c_c = st.columns([1, 1, 1.5])
            if c_a.button(f"Punta {m[2]}", key=f"s1_{m[0]}"):
                st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":m[2], "quota":m[4]})
            if c_b.button(f"Punta {m[3]}", key=f"s2_{m[0]}"):
                st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":m[3], "quota":m[5]})
    
    with col_bet:
        st.subheader("📝 Schedina")
        if not st.session_state.schedina:
            st.info("Aggiungi match per puntare!")
        else:
            q_tot = 1.0
            for s in st.session_state.schedina:
                st.write(f"🔹 {s['scelta']} (@{s['quota']})")
                q_tot *= s['quota']
            
            tipo = "SINGOLA" if len(st.session_state.schedina) == 1 else "MULTIPLA"
            st.markdown(f"**Tipo: {tipo}**")
            st.markdown(f"**Quota Totale: {q_tot:.2f}**")
            
            puntata = st.number_input("Puntata", 10, int(saldo))
            if st.button("Piazza Scommessa 🔥"):
                conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (puntata, st.session_state.user))
                conn.commit(); st.session_state.schedina = []; st.balloons(); st.rerun()
            if st.button("Svuota"): st.session_state.schedina = []; st.rerun()

        st.divider()
        st.subheader("🎡 Crazy Wheel")
        # MOSTRIAMO IL TOKEN COME NEL TUO FILE
        if os.path.exists("Logo.png"):
            st.image("Logo.png", width=150, caption="Usa un Token per girare!")
        
        t_in = st.text_input("Inserisci Token Premium")
        if st.button("GIRA LA RUOTA 🌀"):
            check = conn.execute("SELECT usato FROM tokens WHERE codice=?", (t_in,)).fetchone()
            if check and check[0] == 0:
                conn.execute("UPDATE tokens SET usato=1 WHERE codice=?", (t_in,))
                esegui_giro_premium(st.session_state.user)
            else:
                st.error("Token invalido!")

else:
    st.markdown("<h1 style='text-align: center; color: #d4af37;'>🔥 FENICE BET ULTIMATE</h1>", unsafe_allow_html=True)
    if os.path.exists("Logo.png"):
        st.image("Logo.png", width=400)
