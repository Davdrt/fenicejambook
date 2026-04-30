import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os
import math
import plotly.express as px

# --- CONFIGURAZIONE UI PREMIUM ---
st.set_page_config(page_title="FeniceBet", page_icon="🔥", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #050505;
        font-family: 'Rajdhani', sans-serif;
        color: #d4af37;
    }

    /* CARD STYLE */
    [data-testid="stExpander"], .stTabs, .css-1r6slb0 { 
        background-color: #0f0f0f; 
        border: 1px solid #d4af37; 
        border-radius: 12px; 
    }
    
    /* BOTTONE ORO FENICE */
    .stButton>button {
        background: linear-gradient(135deg, #d4af37 0%, #8a6d3b 100%);
        color: black !important;
        font-weight: 800;
        border: none;
        border-radius: 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: 0.3s ease-in-out;
    }
    .stButton>button:hover { 
        box-shadow: 0 0 25px rgba(212, 175, 55, 0.6); 
        transform: scale(1.02); 
    }

    /* ANIMAZIONE RUOTA PREMIUM */
    @keyframes wheelSpin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(var(--rotation)); }
    }
    .wheel-base {
        width: 300px; height: 300px;
        border: 10px solid #d4af37;
        border-radius: 50%;
        margin: 30px auto;
        background: conic-gradient(#000, #d4af37, #111, #d4af37, #000, #d4af37, #111, #d4af37);
        box-shadow: 0 0 50px rgba(212, 175, 55, 0.3);
        animation: wheelSpin 5s cubic-bezier(0.15, 0, 0.15, 1) forwards;
    }

    /* POPUP VINCITA OVERLAY */
    .win-overlay {
        position: fixed;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(0,0,0,0.95);
        border: 3px solid #d4af37;
        padding: 40px;
        border-radius: 20px;
        z-index: 9999;
        text-align: center;
        box-shadow: 0 0 100px #d4af37;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('fenicebet_v13.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS mcs (nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0, presenze INT DEFAULT 0, pericolo REAL DEFAULT 1.0, popolarita INT DEFAULT 1)')
    c.execute('CREATE TABLE IF NOT EXISTS utenti (username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT "NESSUNO")')
    c.execute('CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT, vincitore TEXT DEFAULT "TBD")')
    c.execute('CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS flussi (id INTEGER PRIMARY KEY AUTOINCREMENT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, tipo TEXT, importo REAL, user TEXT)')
    # Tabella Torneo Antepost
    c.execute('CREATE TABLE IF NOT EXISTS torneo_antepost (mc TEXT PRIMARY KEY, quota REAL, eliminato INT DEFAULT 0, turno INT DEFAULT 1)')
    
    # Account Admin pre-configurato
    c.execute('INSERT OR IGNORE INTO utenti (username, email, password, saldo) VALUES ("ADMIN", "admin@fenice.bet", "admin123", 10000)')
    conn.commit()
    return conn

conn = init_db()

# --- UTILS & ALGORITMO ---
def registra_movimento(tipo, importo, user):
    conn.execute("INSERT INTO flussi (tipo, importo, user) VALUES (?,?,?)", (tipo, importo, user))
    conn.commit()

def calcola_quote_tecnica(mc_nome):
    res = conn.execute("SELECT vittorie, presenze, pericolo, popolarita FROM mcs WHERE nome=?", (mc_nome,)).fetchone()
    if not res or res[1] == 0: return 1.85
    v, p, per, pop = res
    rating = ((v * 15) + 10) / (p + 12)
    prob = rating * per * (0.85 + pop * 0.05)
    return round(max(1.15, min(1 / (prob / (prob + 1)) + 0.12, 8.5)), 2)

# --- SESSION STATE ---
for key in ['user', 'is_admin', 'view_as_player', 'schedina', 'spin_active']:
    if key not in st.session_state: st.session_state[key] = None if key != 'schedina' else []

# --- SIDEBAR & LOGIN ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("FeniceBet")
    
    if not st.session_state.user:
        mode = st.radio("Accesso", ["Login", "Registrati", "Admin"])
        u_in = st.text_input("Username")
        p_in = st.text_input("Password", type="password")
        
        if mode == "Registrati":
            e_in = st.text_input("Email")
            if st.button("REGISTRATI"):
                if "@" not in e_in or "." not in e_in or any(x in e_in.lower() for x in ["test","fake"]): st.error("Email non valida!")
                else:
                    try:
                        conn.execute("INSERT INTO utenti (username, email, password) VALUES (?,?,?)", (u_in, e_in, p_in))
                        conn.commit(); registra_movimento("INGRESSO", 1000, u_in); st.success("Benvenuto!")
                    except: st.error("Username occupato.")
        elif st.button("ENTRA"):
            if mode == "Admin" and p_in == "admin123":
                st.session_state.user, st.session_state.is_admin = "ADMIN", True; st.rerun()
            elif mode == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u_in,p_in)).fetchone()
                if res: st.session_state.user = u_in; st.rerun()
                else: st.error("Dati errati.")
    else:
        st.write(f"👤 Warrior: **{st.session_state.user}**")
        if st.session_state.is_admin:
            st.session_state.view_as_player = st.toggle("Vista Giocatore", st.session_state.view_as_player)
            if st.button("🚀 BOOST ADMIN (+10k)"):
                conn.execute("UPDATE utenti SET saldo = saldo + 10000 WHERE username='ADMIN'")
                conn.commit(); st.rerun()
        if st.button("LOGOUT"):
            for k in st.session_state.keys(): st.session_state[k] = None
            st.rerun()

# --- AREA ADMIN ---
if st.session_state.is_admin and not st.session_state.view_as_player:
    st.title("🕹️ Dashboard Suprema")
    adm_tabs = st.tabs(["📉 Finanza", "🧪 Simulatore & Match", "🏆 Torneo Antepost", "🎤 MC Management", "🎫 Token"])
    
    with adm_tabs[0]:
        df_f = pd.read_sql_query("SELECT ts, importo FROM flussi", conn)
        if not df_f.empty:
            df_f['Bilancio'] = df_f['importo'].cumsum()
            st.plotly_chart(px.line(df_f, x='ts', y='Bilancio', template="plotly_dark", color_discrete_sequence=['#d4af37']), use_container_width=True)
            st.metric("Saldo Totale Sistema", f"{conn.execute('SELECT SUM(saldo) FROM utenti').fetchone()[0]:,.0f} 🪙")

    with adm_tabs[1]:
        st.subheader("🧪 Simulatore Torneo (No DB)")
        mcs_all = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
        if not mcs_all: st.warning("Aggiungi MC prima!")
        else:
            sim_mcs = st.multiselect("Seleziona MC per Simulazione", mcs_all, default=mcs_all[:min(8, len(mcs_all))])
            if st.button("AVVIA SIMULAZIONE TORNEO"):
                if len(sim_mcs) < 2:
                    st.error("Seleziona almeno 2 MC!")
                else:
                    attivi = sim_mcs.copy()
                    turno_n = 1
                    while len(attivi) > 1:
                        st.markdown(f"#### 🔴 Turno {turno_n}")
                        next_round = []
                        random.shuffle(attivi) # Mix casuale per gli accoppiamenti
                        for i in range(0, len(attivi), 2):
                            if i + 1 < len(attivi):
                                m1, m2 = attivi[i], attivi[i+1]
                                q1, q2 = calcola_quote_tecnica(m1), calcola_quote_tecnica(m2)
                                p1 = (1/q1) / ((1/q1) + (1/q2))
                                vincitore = m1 if random.random() < p1 else m2
                                st.write(f"⚔️ {m1} (@{q1}) vs {m2} (@{q2}) ➔ **Vince: {vincitore}**")
                                next_round.append(vincitore)
                            else:
                                st.write(f"🟢 {attivi[i]} passa il turno in automatico (Dispari)")
                                next_round.append(attivi[i])
                        attivi = next_round
                        turno_n += 1
                    st.success(f"🏆 VINCITORE SIMULATO DEL TORNEO: **{attivi[0]}**")
        
        st.divider()
        st.subheader("⚔️ Pubblica Match Reale Singolo")
        ca, cb = st.columns(2)
        m_real1 = ca.selectbox("MC 1 Reale", mcs_all, key="mr1")
        q_real1 = ca.number_input("Quota 1", calcola_quote_tecnica(m_real1))
        m_real2 = cb.selectbox("MC 2 Reale", mcs_all, key="mr2")
        q_real2 = cb.number_input("Quota 2", calcola_quote_tecnica(m_real2))
        if st.button("VAI LIVE!"):
            conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{m_real1} vs {m_real2}", m_real1, m_real2, q_real1, q_real2, "APERTO"))
            conn.commit(); st.success("Match pubblicato nell'arena!")

        st.divider()
        st.subheader("🏁 Chiudi Scontri Singoli")
        aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if aperti:
            sel_id = st.selectbox("Match da chiudere", [m[0] for m in aperti], format_func=lambda x: [m[1] for m in aperti if m[0]==x][0])
            m_dat = [m for m in aperti if m[0]==sel_id][0]
            win = st.radio("Vincitore Effettivo", [m_dat[2], m_dat[3]])
            if st.button("LIQUIDA SCOMMESSE SINGOLE"):
                conn.execute("UPDATE matches SET stato='CHIUSO', vincitore=? WHERE id=?", (win, sel_id))
                conn.execute("UPDATE mcs SET punti_ranking=punti_ranking+3, vittorie=vittorie+1, presenze=presenze+1 WHERE nome=?", (win,))
                # Payout
                winners = conn.execute("SELECT id, username, vincita_pot FROM ticket WHERE stato='IN CORSO' AND dettagli LIKE ?", (f"%{win}%",)).fetchall()
                for w in winners:
                    conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (w[2], w[1]))
                    conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (w[0],))
                    registra_movimento("PAYOUT", w[2], w[1])
                conn.commit(); st.success("Match chiuso e Ranking aggiornato!"); st.rerun()

    with adm_tabs[2]:
        st.subheader("🏆 Gestione Torneo (Quote Antepost)")
        
        c_ant1, c_ant2 = st.columns(2)
        with c_ant1:
            mcs_all_ant = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
            partecipanti = st.multiselect("1. Seleziona MC Iniziali", mcs_all_ant)
            if st.button("INIZIALIZZA NUOVO TORNEO"):
                conn.execute("DELETE FROM torneo_antepost") # Reset torneo
                for mc in partecipanti:
                    # Calcolo stima quota antepost: Quota match * fattore torneo
                    quota_base = calcola_quote_tecnica(mc)
                    quota_ant = round((quota_base * 1.5) * (len(partecipanti) / 3), 2)
                    conn.execute("INSERT INTO torneo_antepost (mc, quota) VALUES (?,?)", (mc, quota_ant))
                conn.commit()
                st.success("Torneo Inizializzato! Quote Antepost live.")
                st.rerun()

        with c_ant2:
            st.markdown("**Stato Attuale Torneo**")
            antepost_live = conn.execute("SELECT mc, quota, turno FROM torneo_antepost WHERE eliminato=0").fetchall()
            if antepost_live:
                for a_mc, a_q, a_t in antepost_live:
                    col1, col2, col3 = st.columns([2,1,1])
                    col1.write(f"🎤 {a_mc} (T{a_t}) - @{a_q}")
                    if col2.button("Avanza ⬆️", key=f"up_{a_mc}"):
                        # Dimezza circa la quota per il passaggio del turno
                        nuova_q = round(max(1.10, a_q / 1.8), 2)
                        conn.execute("UPDATE torneo_antepost SET turno=turno+1, quota=? WHERE mc=?", (nuova_q, a_mc))
                        conn.commit(); st.rerun()
                    if col3.button("Elimina ❌", key=f"del_{a_mc}"):
                        conn.execute("UPDATE torneo_antepost SET eliminato=1 WHERE mc=?", (a_mc,))
                        conn.commit(); st.rerun()
            else:
                st.info("Nessun torneo in corso.")

        st.divider()
        st.subheader("👑 Chiudi Torneo (Liquida Antepost)")
        vincitore_assoluto = st.selectbox("Seleziona Vincitore Assoluto", [m[0] for m in antepost_live] if antepost_live else ["-"])
        if st.button("PROCLAMA VINCITORE E LIQUIDA ANTEPOST") and vincitore_assoluto != "-":
            conn.execute("UPDATE torneo_antepost SET eliminato=1 WHERE mc!=?", (vincitore_assoluto,))
            # Payout Antepost
            winners_ant = conn.execute("SELECT id, username, vincita_pot FROM ticket WHERE stato='IN CORSO' AND dettagli LIKE ?", (f"%Vincente Torneo->{vincitore_assoluto}%",)).fetchall()
            for w in winners_ant:
                conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (w[2], w[1]))
                conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (w[0],))
                registra_movimento("PAYOUT_ANTEPOST", w[2], w[1])
            conn.execute("DELETE FROM torneo_antepost") # Pulisci a fine torneo
            conn.commit(); st.success(f"Torneo concluso! {vincitore_assoluto} vince e scommesse liquidate."); st.rerun()

    with adm_tabs[3]:
        st.subheader("Anagrafica MC")
        col_n, col_v, col_p = st.columns(3)
        n_mc = col_n.text_input("Nome Rapper")
        v_mc = col_v.number_input("Vittorie Iniziali", 0)
        p_mc = col_p.number_input("Presenze Iniziali", 0)
        per_mc = st.slider("Livello Pericolo (Rating)", 0.5, 2.0, 1.0)
        if st.button("SALVA MC"):
            conn.execute("INSERT OR REPLACE INTO mcs (nome, vittorie, presenze, pericolo) VALUES (?,?,?,?)", (n_mc, v_mc, p_mc, per_mc))
            conn.commit(); st.rerun()

    with adm_tabs[4]:
        if st.button("GENERA TOKEN 🎫"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"
            conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,)); conn.commit(); st.code(tk)

# --- AREA GIOCATORE ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo = u_data[0]
    
    st.title("🏟️ FeniceBet Arena")
    st.metric("TUO SALDO 🪙", f"{saldo:,.0f}")
    
    u_tabs = st.tabs(["🎮 Scommesse", "🎡 Crazy Wheel", "📊 Leaderboard"])
    
    with u_tabs[0]:
        cl, cr = st.columns([2, 1.2])
        with cl:
            st.subheader("🔥 Match Live")
            live = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            if not live: st.info("Nessun match singolo aperto.")
            for l in live:
                with st.container():
                    st.markdown(f"**{l[1]}**")
                    c_q1, c_q2 = st.columns(2)
                    if c_q1.button(f"{l[2]} @{l[4]}", key=f"btn1_{l[0]}"):
                        st.session_state.schedina.append({"id":l[0], "desc":l[1], "scelta":l[2], "quota":l[4]})
                    if c_q2.button(f"{l[3]} @{l[5]}", key=f"btn2_{l[0]}"):
                        st.session_state.schedina.append({"id":l[0], "desc":l[1], "scelta":l[3], "quota":l[5]})
            
            st.divider()
            st.subheader("🏆 Vincente Torneo (Antepost)")
            antepost_disp = conn.execute("SELECT mc, quota FROM torneo_antepost WHERE eliminato=0").fetchall()
            if non antepost_disp:
                st.info("Quote antepost non disponibili o torneo non iniziato.")
            else:
                cols = st.columns(3)
                for idx, (a_mc, a_q) in enumerate(antepost_disp):
                    with cols[idx % 3]:
                        if st.button(f"👑 {a_mc}\n@{a_q}", key=f"ant_{a_mc}", use_container_width=True):
                            st.session_state.schedina.append({"id": f"ANT_{a_mc}", "desc": "Vincente Torneo", "scelta": a_mc, "quota": a_q})

        with cr:
            st.subheader("Schedina")
            if not st.session_state.schedina: st.info("Seleziona quote")
            else:
                qt = 1.0
                for s in st.session_state.schedina:
                    st.write(f"✅ {s['desc']}: **{s['scelta']}** (@{s['quota']})")
                    qt *= s['quota']
                st.write(f"📈 QUOTA TOT: **{qt:.2f}**")
                pnt = st.number_input("Puntata", 10, int(max(10, saldo)))
                v_pot = pnt * qt
                if v_pot > 500000: v_pot = 500000; st.warning("Tetto 500k!")
                
                if st.button("PIAZZA SCOMMESSA", use_container_width=True):
                    if pnt > saldo:
                        st.error("Saldo insufficiente!")
                    else:
                        conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (pnt, st.session_state.user))
                        det = " | ".join([f"{x['desc']}->{x['scelta']}" for x in st.session_state.schedina])
                        conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)", (st.session_state.user, det, qt, pnt, v_pot, "IN CORSO"))
                        registra_movimento("SCOMMESSA", -pnt, st.session_state.user)
                        conn.commit(); st.session_state.schedina = []; st.balloons(); st.rerun()
            
            if st.button("🗑️ Svuota Schedina", use_container_width=True): st.session_state.schedina = []; st.rerun()

    with u_tabs[1]:
        col_w1, col_w2 = st.columns([2, 1])
        with col_w1:
            st.subheader("🎡 Crazy Wheel")
            t_in = st.text_input("Inserisci Token Premium", placeholder="FENICE-XXXXXX")
            if st.button("GIRA LA RUOTA! ✨"):
                res = conn.execute("SELECT usato FROM tokens WHERE codice=?", (t_in,)).fetchone()
                if res and res[0] == 0:
                    conn.execute("UPDATE tokens SET usato=1 WHERE codice=?", (t_in,))
                    rot = random.randint(3000, 6000)
                    st.markdown(f"<div class='wheel-base' style='--rotation: {rot}deg;'></div>", unsafe_allow_html=True)
                    with st.spinner("Decelerazione in corso..."): time.sleep(5)
                    vinto = random.choice([500, 1000, 2000, 5000, 10000])
                    conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vinto, st.session_state.user))
                    conn.commit(); st.balloons()
                    st.markdown(f"<div class='win-overlay'><h1>🔥 HAI VINTO {vinto} PUNTI! 🔥</h1><p>Saldo aggiornato.</p></div>", unsafe_allow_html=True)
                    time.sleep(3); st.rerun()
                else: st.error("Token non valido o già usato!")
        with col_w2:
            st.markdown("""
            ### 📜 Probabilità Premi
            La Crazy Wheel distribuisce in modo equo uno dei seguenti jackpot ad ogni giro:
            
            * 🪙 **500 Punti:** 20%
            * 🪙 **1.000 Punti:** 20%
            * 🪙 **2.000 Punti:** 20%
            * 🪙 **5.000 Punti:** 20%
            * 🔥 **10.000 Punti:** 20%
            """)

    with u_tabs[2]:
        st.subheader("Classifiche Jam")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.write("🏆 TOP PLAYERS")
            st.table(pd.read_sql_query("SELECT username, saldo FROM utenti ORDER BY saldo DESC LIMIT 10", conn))
        with col_t2:
            st.write("🎤 RANKING MC")
            st.table(pd.read_sql_query("SELECT nome, punti_ranking AS Punti, vittorie FROM mcs ORDER BY Punti DESC", conn))

else:
    c1, c2, c3 = st.columns([1,2,1])
    if os.path.exists("Logo.png"): c2.image("Logo.png")
    st.markdown("<h1 style='text-align: center; color: #d4af37;'>FeniceBet</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>L'arena ufficiale della Fenice Jam. Accedi per iniziare la sfida.</p>", unsafe_allow_html=True)
