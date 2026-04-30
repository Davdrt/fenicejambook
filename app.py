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
st.set_page_config(page_title="FeniceBet v13", page_icon="🔥", layout="wide")

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
    c.execute('CREATE TABLE IF NOT EXISTS torneo_antepost (mc TEXT PRIMARY KEY, quota REAL, eliminato INT DEFAULT 0, turno INT DEFAULT 1)')
    
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

def calcola_quota_coppia(mc1, mc2):
    q1 = calcola_quote_tecnica(mc1)
    q2 = calcola_quote_tecnica(mc2)
    # Rimuoviamo temporaneamente il margine del banco per avere la probabilità pura
    prob_pura_1 = (1 / q1) * 1.12 
    prob_pura_2 = (1 / q2) * 1.12
    # La forza della coppia è la media della loro probabilità pura di vittoria
    forza_coppia = (prob_pura_1 + prob_pura_2) / 2
    # Riconvertiamo in quota riapplicando l'aggio del banco (12%)
    quota_coppia = round((1 / forza_coppia) + 0.12, 2)
    return max(1.10, min(quota_coppia, 15.00))

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
        bonus_user = conn.execute("SELECT bonus_attivo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
        if bonus_user and bonus_user[0] != "NESSUNO":
            st.warning(f"🎁 Bonus Attivo: {bonus_user[0]}")
            
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
    adm_tabs = st.tabs(["📉 Finanza", "🧪 Match Maker", "🏆 Torneo Antepost", "🎤 MC Management", "🎫 Token"])
    
    with adm_tabs[0]:
        df_f = pd.read_sql_query("SELECT ts, importo FROM flussi", conn)
        if not df_f.empty:
            df_f['Bilancio'] = df_f['importo'].cumsum()
            st.plotly_chart(px.line(df_f, x='ts', y='Bilancio', template="plotly_dark", color_discrete_sequence=['#d4af37']), use_container_width=True)
            st.metric("Saldo Totale Sistema", f"{conn.execute('SELECT SUM(saldo) FROM utenti').fetchone()[0]:,.0f} 🪙")

    with adm_tabs[1]:
        mcs_all = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
        if not mcs_all: 
            st.warning("Aggiungi MC prima!")
        else:
            tipo_match = st.radio("Tipo di Match", ["1 vs 1", "2 vs 2"])
            
            st.subheader(f"⚔️ Pubblica Match {tipo_match}")
            if tipo_match == "1 vs 1":
                ca, cb = st.columns(2)
                m_real1 = ca.selectbox("MC 1 Reale", mcs_all, key="mr1")
                q_real1 = ca.number_input("Quota 1", calcola_quote_tecnica(m_real1))
                m_real2 = cb.selectbox("MC 2 Reale", mcs_all, key="mr2")
                q_real2 = cb.number_input("Quota 2", calcola_quote_tecnica(m_real2))
                if st.button("VAI LIVE (1v1)!"):
                    conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{m_real1} vs {m_real2}", m_real1, m_real2, q_real1, q_real2, "APERTO"))
                    conn.commit(); st.success("Match 1v1 pubblicato!")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Team 1**")
                    t1_m1 = st.selectbox("MC 1 - Team 1", mcs_all, key="t1m1")
                    t1_m2 = st.selectbox("MC 2 - Team 1", mcs_all, key="t1m2")
                    q_team1 = st.number_input("Quota Team 1", calcola_quota_coppia(t1_m1, t1_m2))
                with c2:
                    st.markdown("**Team 2**")
                    t2_m1 = st.selectbox("MC 1 - Team 2", mcs_all, key="t2m1")
                    t2_m2 = st.selectbox("MC 2 - Team 2", mcs_all, key="t2m2")
                    q_team2 = st.number_input("Quota Team 2", calcola_quota_coppia(t2_m1, t2_m2))
                
                if st.button("VAI LIVE (2v2)!"):
                    nome_t1 = f"{t1_m1} & {t1_m2}"
                    nome_t2 = f"{t2_m1} & {t2_m2}"
                    conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{nome_t1} vs {nome_t2}", nome_t1, nome_t2, q_team1, q_team2, "APERTO"))
                    conn.commit(); st.success("Match 2v2 pubblicato!")

        st.divider()
        st.subheader("🏁 Chiudi Scontri Singoli/Coppie")
        aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if aperti:
            sel_id = st.selectbox("Match da chiudere", [m[0] for m in aperti], format_func=lambda x: [m[1] for m in aperti if m[0]==x][0])
            m_dat = [m for m in aperti if m[0]==sel_id][0]
            win = st.radio("Vincitore Effettivo", [m_dat[2], m_dat[3]])
            if st.button("LIQUIDA SCOMMESSE"):
                conn.execute("UPDATE matches SET stato='CHIUSO', vincitore=? WHERE id=?", (win, sel_id))
                
                # Se è un team (contiene "&"), splitta per dare punti ranking a entrambi, altrimenti singolo
                vincitori = [mc.strip() for mc in win.split("&")]
                for v in vincitori:
                    conn.execute("UPDATE mcs SET punti_ranking=punti_ranking+3, vittorie=vittorie+1, presenze=presenze+1 WHERE nome=?", (v,))
                
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
            tipo_torneo = st.radio("Formato Torneo", ["Singolo (1v1)", "Coppie (2v2)"], horizontal=True)
            mcs_all_ant = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
            
            if tipo_torneo == "Singolo (1v1)":
                partecipanti = st.multiselect("Seleziona MC Iniziali", mcs_all_ant)
                if st.button("INIZIALIZZA NUOVO TORNEO (1v1)"):
                    conn.execute("DELETE FROM torneo_antepost")
                    for mc in partecipanti:
                        quota_base = calcola_quote_tecnica(mc)
                        quota_ant = round((quota_base * 1.5) * (len(partecipanti) / 3), 2)
                        conn.execute("INSERT INTO torneo_antepost (mc, quota) VALUES (?,?)", (mc, quota_ant))
                    conn.commit()
                    st.success("Torneo Inizializzato! Quote Antepost live."); st.rerun()
            else:
                st.info("Seleziona il numero di team e scegli gli MC dai menu a tendina.")
                num_teams = st.number_input("Numero di Team Partecipanti", min_value=1, max_value=16, value=4)
                
                teams_selezionati = []
                for i in range(num_teams):
                    st.markdown(f"**Team {i+1}**")
                    col_t1, col_t2 = st.columns(2)
                    mc1 = col_t1.selectbox(f"MC 1", mcs_all_ant, key=f"ant_t{i}_m1")
                    # Imposta l'indice a 1 per evitare che selezioni lo stesso MC di default
                    mc2 = col_t2.selectbox(f"MC 2", mcs_all_ant, key=f"ant_t{i}_m2", index=1 if len(mcs_all_ant) > 1 else 0)
                    teams_selezionati.append((mc1, mc2))
                    
                if st.button("INIZIALIZZA NUOVO TORNEO (2v2)"):
                    # Controllo per evitare team con due MC uguali
                    errori = [f"Team {i+1}" for i, (m1, m2) in enumerate(teams_selezionati) if m1 == m2]
                    if errori:
                        st.error(f"Attenzione! I seguenti team hanno lo stesso MC selezionato due volte: {', '.join(errori)}")
                    else:
                        conn.execute("DELETE FROM torneo_antepost")
                        for mc1, mc2 in teams_selezionati:
                            nome_team = f"{mc1} & {mc2}"
                            try:
                                quota_base = calcola_quota_coppia(mc1, mc2)
                                moltiplicatore = max(1, len(teams_selezionati) / 3)
                                quota_ant = round((quota_base * 1.5) * moltiplicatore, 2)
                                quota_ant = max(quota_base + 0.20, quota_ant) # Mai sotto la quota base
                                
                                conn.execute("INSERT INTO torneo_antepost (mc, quota) VALUES (?,?)", (nome_team, quota_ant))
                            except Exception as e:
                                st.error(f"Errore calcolo quota per {nome_team}: MC non trovati?")
                        conn.commit()
                        st.success("Torneo a Coppie Inizializzato!"); st.rerun()


        with c_ant2:
            st.markdown("**Stato Attuale Torneo**")
            antepost_live = conn.execute("SELECT mc, quota, turno FROM torneo_antepost WHERE eliminato=0").fetchall()
            if antepost_live:
                for a_mc, a_q, a_t in antepost_live:
                    col1, col2, col3 = st.columns([2,1,1])
                    col1.write(f"🎤 {a_mc} (T{a_t}) - @{a_q}")
                    if col2.button("Avanza ⬆️", key=f"up_{a_mc}"):
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
            winners_ant = conn.execute("SELECT id, username, vincita_pot FROM ticket WHERE stato='IN CORSO' AND dettagli LIKE ?", (f"%Vincente Torneo->{vincitore_assoluto}%",)).fetchall()
            for w in winners_ant:
                conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (w[2], w[1]))
                conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (w[0],))
                registra_movimento("PAYOUT_ANTEPOST", w[2], w[1])
            conn.execute("DELETE FROM torneo_antepost")
            conn.commit(); st.success(f"Torneo concluso! Scommesse liquidate."); st.rerun()

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
    u_data = conn.execute("SELECT saldo, bonus_attivo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo = u_data[0]
    bonus_attivo = u_data[1]
    
    st.title("🏟️ FeniceBet Arena")
    st.metric("TUO SALDO 🪙", f"{saldo:,.0f}")
    
    u_tabs = st.tabs(["🎮 Scommesse", "🎡 Crazy Wheel", "📊 Leaderboard"])
    
    with u_tabs[0]:
        cl, cr = st.columns([2, 1.2])
        with cl:
            st.subheader("🔥 Match Live")
            live = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            if not live: st.info("Nessun match aperto.")
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
            if not antepost_disp: # <-- ERRORE FIXATO QUI
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
                
                # Info bonus per iteration future della schedina
                if bonus_attivo != "NESSUNO":
                    st.info(f"Bonus disponibile: {bonus_attivo}. Verrà applicato nelle prossime release del sistema.")

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
                    
                    # LOGICA RUOTA CON PESI
                    premi_ruota = [
                        "💰 +500 Punti", "🔥 +1000 Punti", "🛡️ SCUDO FENICE", "📈 BOOST QUOTA X2", 
                        "🎟️ FREE BET 1000", "🏆 +2000 Punti", "🚑 ASSICURAZIONE K.O.", 
                        "🚀 BOOST QUOTA X3", "💎 RADDOPPIO SALDO", "🎰 MEGA JACKPOT (+5000)"
                    ]
                    pesi_probabilita = [30, 25, 15, 10, 7, 5, 4, 2, 1.5, 0.5]
                    vincita_testo = random.choices(premi_ruota, weights=pesi_probabilita, k=1)[0]
                    
                    vinto = 0
                    if "500 Punti" in vincita_testo: vinto = 500
                    elif "1000 Punti" in vincita_testo and "FREE" not in vincita_testo: vinto = 1000
                    elif "2000 Punti" in vincita_testo: vinto = 2000
                    elif "MEGA JACKPOT" in vincita_testo: vinto = 5000
                    elif "RADDOPPIO" in vincita_testo: vinto = saldo
                    else:
                        conn.execute("UPDATE utenti SET bonus_attivo=? WHERE username=?", (vincita_testo, st.session_state.user))
                    
                    if vinto > 0:
                        conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vinto, st.session_state.user))
                    
                    conn.commit(); st.balloons()
                    st.markdown(f"<div class='win-overlay'><h1>{vincita_testo}</h1><p>Inventario Aggiornato.</p></div>", unsafe_allow_html=True)
                    time.sleep(3.5); st.rerun()
                else: st.error("Token non valido o già usato!")
        with col_w2:
            st.markdown("""
            ### 📜 Probabilità Premi
            * 💰 **+500 Punti:** 30%
            * 🔥 **+1.000 Punti:** 25%
            * 🛡️ **SCUDO FENICE:** 15%
            * 📈 **BOOST QUOTA X2:** 10%
            * 🎟️ **FREE BET 1000:** 7%
            * 🏆 **+2.000 Punti:** 5%
            * 🚑 **ASSICURAZIONE K.O.:** 4%
            * 🚀 **BOOST QUOTA X3:** 2%
            * 💎 **RADDOPPIO SALDO:** 1.5%
            * 🎰 **MEGA JACKPOT (+5000):** 0.5%
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
