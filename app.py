import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os
import plotly.express as px

# --- CONFIGURAZIONE ESTETICA ---
st.set_page_config(page_title="FeniceBet", page_icon="🔥", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #050505;
        font-family: 'Rajdhani', sans-serif;
        color: #d4af37;
    }

    /* CARD STYLES */
    [data-testid="stExpander"], .stTabs [data-baseweb="tab-panel"] {
        background-color: #0f0f0f;
        border: 1px solid #d4af37;
        border-radius: 12px;
        padding: 15px;
    }
    
    /* GOLD NEON BUTTON */
    .stButton>button {
        background: linear-gradient(135deg, #d4af37 0%, #8a6d3b 100%);
        color: black !important;
        font-weight: 800;
        border: none;
        border-radius: 8px;
        transition: 0.3s;
    }
    .stButton>button:hover { box-shadow: 0 0 20px #d4af37; transform: translateY(-2px); }

    /* WHEEL ANIMATION */
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
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE v12 ---
def init_db():
    conn = sqlite3.connect('fenicebet_v12.db', check_same_thread=False)
    c = conn.cursor()
    # MC Table con Fascia automatica
    c.execute('''CREATE TABLE IF NOT EXISTS mcs (
                 nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0, 
                 presenze INT DEFAULT 0, pericolo REAL DEFAULT 1.0, popolarita INT DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (
                 username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, 
                 giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT "NESSUNO")''')
    c.execute('CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS flussi (id INTEGER PRIMARY KEY AUTOINCREMENT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, tipo TEXT, importo REAL, user TEXT)')
    
    # Admin Account
    c.execute('INSERT OR IGNORE INTO utenti (username, email, password, saldo) VALUES ("ADMIN", "admin@fenice.bet", "admin123", 50000)')
    conn.commit()
    return conn

conn = init_db()

# --- ALGORITMO "THE BRAIN" ---
def get_fascia(presenze):
    if presenze < 20: return "Novellino 🐣"
    if 20 <= presenze < 50: return "Fascia Media ⚔️"
    return "Veterano 🏆"

def calcola_quote_brain(nome_mc):
    res = conn.execute("SELECT vittorie, presenze, pericolo, popolarita FROM mcs WHERE nome=?", (nome_mc,)).fetchone()
    if not res or res[1] == 0: return 2.10 # Quota debutto
    v, p, per, pop = res
    win_rate = v / p if p > 0 else 0.5
    
    # Bonus/Malus Fascia
    fascia_mult = 1.2 if p < 20 else 1.0 # Più imprevedibile se novellino
    
    prob = (win_rate * per * (0.8 + pop * 0.05)) * fascia_mult
    quota = 1 / (prob / (prob + 1)) + 0.15
    return round(max(1.15, min(quota, 9.0)), 2)

def registra_flusso(tipo, importo, user):
    conn.execute("INSERT INTO flussi (tipo, importo, user) VALUES (?,?,?)", (tipo, importo, user))
    conn.commit()

# --- SESSION STATE ---
for key in ['user', 'is_admin', 'view_as_player', 'schedina']:
    if key not in st.session_state: st.session_state[key] = None if key != 'schedina' else []

# --- SIDEBAR & LOGO ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("FeniceBet")
    
    if not st.session_state.user:
        mode = st.radio("Accesso", ["Login", "Registrati", "Admin"])
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if mode == "Registrati":
            em = st.text_input("Email")
            if st.button("CREA ACCOUNT"):
                if "@" not in em or "." not in em or any(x in em.lower() for x in ["test","fake"]): st.error("Email invalida!")
                else:
                    try:
                        conn.execute("INSERT INTO utenti (username, email, password) VALUES (?,?,?)", (u, em, p))
                        conn.commit(); registra_flusso("START", 1000, u); st.success("Benvenuto!")
                    except: st.error("Username occupato.")
        elif st.button("ACCEDI"):
            if mode == "Admin" and p == "admin123":
                st.session_state.user, st.session_state.is_admin = "ADMIN", True; st.rerun()
            elif mode == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u,p)).fetchone()
                if res: st.session_state.user = u; st.rerun()
                else: st.error("Dati errati.")
    else:
        st.write(f"🟢 **{st.session_state.user}**")
        if st.session_state.is_admin:
            st.session_state.view_as_player = st.toggle("Admin Player Mode", st.session_state.view_as_player)
            if st.button("💰 BOOST SALDO ADMIN (+10k)"):
                conn.execute("UPDATE utenti SET saldo = saldo + 10000 WHERE username='ADMIN'")
                conn.commit(); st.rerun()
        if st.button("LOGOUT"):
            for k in st.session_state.keys(): st.session_state[k] = None
            st.rerun()

# --- PANNELLO ADMIN ---
if st.session_state.is_admin and not st.session_state.view_as_player:
    st.title("Dashboard Fondatore")
    t_adm = st.tabs(["⚔️ Match", "🎤 Anagrafica MC", "🎫 Token", "📉 Finanza"])
    
    with t_adm[0]:
        c1, c2 = st.columns(2)
        mcs_list = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
        if not mcs_list: st.warning("Aggiungi MC prima!")
        else:
            mc1 = c1.selectbox("MC 1", mcs_list); q1 = c1.number_input("Quota 1", calcola_quote_brain(mc1))
            mc2 = c2.selectbox("MC 2", mcs_list); q2 = c2.number_input("Quota 2", calcola_quote_brain(mc2))
            if st.button("PUBBLICA MATCH LIVE"):
                conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{mc1} vs {mc2}", mc1, mc2, q1, q2, "APERTO"))
                conn.commit(); st.success("Match Online!")
        
        st.divider()
        st.subheader("Chiudi Match")
        aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if aperti:
            s_m = st.selectbox("Scegli", [m[0] for m in aperti], format_func=lambda x: [m[1] for m in aperti if m[0]==x][0])
            m_data = [m for m in aperti if m[0]==s_m][0]
            winner = st.radio("Vincitore", [m_data[2], m_data[3]])
            if st.button("CONFERMA RISULTATO"):
                conn.execute("UPDATE matches SET stato='CHIUSO' WHERE id=?", (s_m,))
                conn.execute("UPDATE mcs SET punti_ranking=punti_ranking+3, vittorie=vittorie+1, presenze=presenze+1 WHERE nome=?", (winner,))
                conn.execute("UPDATE mcs SET presenze=presenze+1 WHERE nome=?", (m_data[2] if winner != m_data[2] else m_data[3],))
                # Payout scommesse
                win_tix = conn.execute("SELECT id, username, vincita_pot FROM ticket WHERE stato='IN CORSO' AND dettagli LIKE ?", (f"%{winner}%",)).fetchall()
                for t in win_tix:
                    conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (t[2], t[1]))
                    conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (t[0],))
                    registra_flusso("VINCITA", t[2], t[1])
                conn.commit(); st.rerun()

    with t_adm[1]:
        st.subheader("Inserimento Dati MC")
        nm = st.text_input("Nome Rapper")
        c_a, c_b, c_c = st.columns(3)
        v_m = c_a.number_input("Vittorie Iniziali", 0)
        p_m = c_b.number_input("Presenze Iniziali", 0)
        per_m = c_c.slider("Grado Pericolo", 0.5, 2.0, 1.0)
        pop_m = st.slider("Popolarità", 1, 10, 5)
        if st.button("SALVA/AGGIORNA MC"):
            conn.execute("INSERT OR REPLACE INTO mcs (nome, vittorie, presenze, pericolo, popolarita) VALUES (?,?,?,?,?)", (nm, v_m, p_m, per_m, pop_m))
            conn.commit(); st.success("Database MC aggiornato!")

    with t_adm[2]:
        if st.button("GENERA TOKEN PREMIUM"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"; conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,)); conn.commit(); st.code(tk)

    with t_adm[3]:
        df_flussi = pd.read_sql_query("SELECT ts, importo FROM flussi", conn)
        if not df_flussi.empty:
            df_flussi['Cumulative'] = df_flussi['importo'].cumsum()
            st.plotly_chart(px.line(df_flussi, x='ts', y='Cumulative', template="plotly_dark", color_discrete_sequence=['#d4af37']), use_container_width=True)

# --- AREA GIOCATORE ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo, giro_punti_usato FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo = u_data[0]
    
    st.title("FeniceBet")
    st.metric("DISPONIBILITÀ", f"{saldo:,.0f} 🪙")
    
    u_tabs = st.tabs(["🎮 Betting", "🎡 Crazy Wheel", "📊 Ranking MC & User"])
    
    with u_tabs[0]:
        cl, cr = st.columns([2, 1.2])
        with cl:
            st.subheader("Match Live")
            active = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            for m in active:
                with st.expander(f"📌 {m[1]}"):
                    c_a, c_b = st.columns(2)
                    if c_a.button(f"{m[2]} @{m[4]}", key=f"q1_{m[0]}"):
                        st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":m[2], "quota":m[4]})
                    if c_b.button(f"{m[3]} @{m[5]}", key=f"q2_{m[0]}"):
                        st.session_state.schedina.append({"id":m[0], "desc":m[1], "scelta":m[3], "quota":m[5]})
        with cr:
            st.subheader("Schedina")
            if not st.session_state.schedina: st.info("Scegli una quota")
            else:
                qt = 1.0
                for s in st.session_state.schedina:
                    st.write(f"🔹 {s['scelta']} (@{s['quota']})")
                    qt *= s['quota']
                st.write(f"📊 Quota: **{qt:.2f}**")
                pnt = st.number_input("Punta", 10, int(saldo))
                vinc = pnt * qt
                if vinc > 500000: vinc = 500000; st.warning("Tetto 500k!")
                if st.button("PIAZZA SCOMMESSA"):
                    conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (pnt, st.session_state.user))
                    det = " | ".join([f"{x['desc']}->{x['scelta']}" for x in st.session_state.schedina])
                    conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)", (st.session_state.user, det, qt, pnt, vinc, "IN CORSO"))
                    registra_flusso("BET", -pnt, st.session_state.user); conn.commit()
                    st.session_state.schedina = []; st.balloons(); st.rerun()
            if st.button("Svuota"): st.session_state.schedina = []; st.rerun()

    with u_tabs[1]:
        st.subheader("🎡 Crazy Wheel v2")
        costo = 500 if u_data[1] == 0 else "TOKEN PREMIUM"
        st.markdown(f"**Costo Giro:** {costo}")
        
        tok = st.text_input("Inserisci Token (se non è il primo giro)")
        if st.button("GIRA LA RUOTA!"):
            paga = False
            if u_data[1] == 0 and saldo >= 500:
                conn.execute("UPDATE utenti SET saldo = saldo - 500, giro_punti_usato = 1 WHERE username=?", (st.session_state.user,))
                paga = True
            else:
                res_t = conn.execute("SELECT usato FROM tokens WHERE codice=?", (tok,)).fetchone()
                if res_t and res_t[0] == 0:
                    conn.execute("UPDATE tokens SET usato = 1 WHERE codice=?", (tok,))
                    paga = True
            
            if paga:
                rot = random.randint(3000, 6000)
                st.markdown(f"<div class='wheel-base' style='--rotation: {rot}deg;'></div>", unsafe_allow_html=True)
                with st.spinner("Decelerazione in corso..."): time.sleep(5)
                vinto = random.choice([0, 500, 1000, 2000, 5000, 10000])
                conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vinto, st.session_state.user))
                conn.commit(); st.success(f"🔥 HAI VINTO {vinto} PUNTI!")
                st.balloons()
            else: st.error("Impossibile girare: controlla saldo o token.")

    with u_tabs[2]:
        st.subheader("🎤 Ranking Ufficiale MC")
        df_mc = pd.read_sql_query("SELECT nome AS MC, punti_ranking AS Punti, vittorie AS Vittorie, presenze AS Presenze FROM mcs ORDER BY Punti DESC", conn)
        df_mc['Fascia'] = df_mc['Presenze'].apply(get_fascia)
        st.table(df_mc)
        
        st.divider()
        st.subheader("🏆 Leaderboard Utenti")
        st.table(pd.read_sql_query("SELECT username AS Utente, saldo AS Punti FROM utenti ORDER BY Punti DESC LIMIT 10", conn))

else:
    c1, c2, c3 = st.columns([1,2,1])
    if os.path.exists("Logo.png"): c2.image("Logo.png")
    st.markdown("<h1 style='text-align: center;'>FeniceBet</h1>", unsafe_allow_html=True)
    st.write("Accedi o Registrati per iniziare.")
