import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time

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
    conn = sqlite3.connect('fenicebet_v3.db', check_same_thread=False)
    c = conn.cursor()
    # Nuova tabella MCs per il Ranking
    c.execute('''CREATE TABLE IF NOT EXISTS mcs 
                 (nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS utenti 
                 (username TEXT PRIMARY KEY, password TEXT, saldo REAL DEFAULT 1000, 
                  giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT 'NESSUNO')''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ticket 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens 
                 (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)''')
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
        
        if vincita["tipo"] == "punti":
            conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vincita["val"], username))
        elif vincita["tipo"] == "moltiplicatore":
            conn.execute("UPDATE utenti SET saldo = saldo * ? WHERE username=?", (vincita["val"], username))
        elif vincita["tipo"] == "bonus":
            conn.execute("UPDATE utenti SET bonus_attivo = ? WHERE username=?", (vincita["val"], username))
            
        conn.commit()
        st.balloons()
        st.success(f"🎊 RISULTATO: {vincita['label']}")
        time.sleep(2)
        st.rerun()

# --- SIDEBAR: LOGIN & REGISTRAZIONE ---
with st.sidebar:
    st.title("🔥 FENICE BET")
    if not st.session_state.user:
        choice = st.radio("Accesso", ["Login", "Registrati", "Admin"])
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        
        if st.button("ENTRA"):
            if choice == "Admin" and p == "admin123":
                st.session_state.user = "ADMIN"
                st.session_state.is_admin = True
                st.rerun()
            elif choice == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u, p)).fetchone()
                if res:
                    st.session_state.user = u
                    st.rerun()
                else: st.error("Dati errati")
            elif choice == "Registrati":
                try:
                    conn.execute("INSERT INTO utenti (username, password) VALUES (?,?)", (u, p))
                    conn.commit()
                    st.success("Registrato! Ora fai il login.")
                except: st.error("Nome già preso.")
    else:
        st.write(f"Utente: **{st.session_state.user}**")
        if st.button("LOGOUT"):
            st.session_state.user = None
            st.session_state.is_admin = False
            st.rerun()

# --- LOGICA ADMIN ---
if st.session_state.is_admin:
    st.title("🕹️ Dashboard Gestore & Ranking")
    t1, t2, t3 = st.tabs(["Crea Match", "Chiudi Match (Paga & Classifica)", "Genera Token"])
    
    with t1:
        st.subheader("Crea un nuovo scontro")
        colA, colB = st.columns(2)
        with colA:
            mc1 = st.text_input("MC 1 (o Team 1)")
            q1 = st.number_input("Quota 1", value=1.80)
        with colB:
            mc2 = st.text_input("MC 2 (o Team 2)")
            q2 = st.number_input("Quota 2", value=2.10)
        if st.button("PUBBLICA MATCH"):
            # Aggiungi MC al database Ranking se non esistono
            conn.execute("INSERT OR IGNORE INTO mcs (nome) VALUES (?)", (mc1,))
            conn.execute("INSERT OR IGNORE INTO mcs (nome) VALUES (?)", (mc2,))
            conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)",
                         (f"{mc1} vs {mc2}", mc1, mc2, q1, q2, "APERTO"))
            conn.commit()
            st.success("Match Online e Scommesse Aperte!")

    with t2:
        st.subheader("Dichiara Vincitore e Paga Scommesse")
        match_aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if match_aperti:
            opzioni = {m[0]: f"{m[1]}" for m in match_aperti}
            scelta_m = st.selectbox("Seleziona Match Finito", options=list(opzioni.keys()), format_func=lambda x: opzioni[x])
            
            # Trova chi erano i due MC
            dettagli_m = [m for m in match_aperti if m[0] == scelta_m][0]
            vincitore = st.radio("Chi ha vinto?", [dettagli_m[2], dettagli_m[3], "Pareggio (Nessun punto)"])
            
            if st.button("CHIUDI MATCH E AGGIORNA RANKING"):
                # 1. Chiudi il match
                conn.execute("UPDATE matches SET stato='CHIUSO' WHERE id=?", (scelta_m,))
                
                # 2. Assegna +3 Punti Ranking e +1 Vittoria
                if vincitore != "Pareggio (Nessun punto)":
                    conn.execute("UPDATE mcs SET punti_ranking = punti_ranking + 3, vittorie = vittorie + 1 WHERE nome=?", (vincitore,))
                
                # 3. Controlla e Paga i Ticket (Logica semplificata per singole)
                tickets = conn.execute("SELECT id, username, dettagli, vincita_pot FROM ticket WHERE stato LIKE 'IN CORSO%'").fetchall()
                for t in tickets:
                    t_id, t_user, t_dettagli, t_vincita = t
                    if f"{dettagli_m[1]}->{vincitore}" in t_dettagli:
                        conn.execute("UPDATE ticket SET stato='VINTO' WHERE id=?", (t_id,))
                        conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (t_vincita, t_user))
                    elif dettagli_m[1] in t_dettagli: # Se il match è nel ticket ma la scelta è sbagliata
                        conn.execute("UPDATE ticket SET stato='PERSO' WHERE id=?", (t_id,))
                
                conn.commit()
                st.success(f"Match chiuso! 3 Punti assegnati a {vincitore} e scommesse pagate!")
                time.sleep(2)
                st.rerun()
        else:
            st.info("Nessun match da chiudere.")

    with t3:
        if st.button("GENERA TOKEN PREMIUM 🎫"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"
            conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,))
            conn.commit()
            st.code(tk, language="text")
            st.write("Dallo all'utente dopo il pagamento.")

# --- LOGICA UTENTE ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo, giro_punti_usato, bonus_attivo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    saldo, giro_usato, bonus = u_data
    
    st.title(f"🎰 Benvenuto, {st.session_state.user}")
    st.metric("IL TUO SALDO 🪙", f"{saldo:.0f} Points")
    if bonus != "NESSUNO":
        st.info(f"🌟 BONUS ATTIVO: {bonus}")

    tab_scommesse, tab_ranking = st.tabs(["🔥 Scommesse & Ruota", "🏆 Classifica Jam"])
    
    with tab_scommesse:
        c1, c2 = st.columns([2, 1.2])
        with c1:
            st.subheader("Match Live")
            matches = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            if not matches: st.info("Nessun match aperto al momento.")
            for m in matches:
                with st.expander(f"SCOMMETTI: {m[1]}"):
                    scelta = st.radio("Vincitore:", [m[2], m[3]], key=f"m_{m[0]}")
                    q = m[4] if scelta == m[2] else m[5]
                    if bonus == "BOOST_X2": q *= 2
                    if bonus == "BOOST_X3": q *= 3
                    
                    if st.button(f"Aggiungi @{q:.2f}", key=f"btn_{m[0]}"):
                        if not any(x['id'] == m[0] for x in st.session_state.schedina):
                            st.session_state.schedina.append({"id": m[0], "desc": m[1], "scelta": scelta, "quota": q})
                            st.rerun()

        with c2:
            st.subheader("🛒 Schedina")
            if not st.session_state.schedina:
                st.info("Vuota")
            else:
                q_tot = 1.0
                for item in st.session_state.schedina:
                    st.write(f"✅ {item['scelta']} (@{item['quota']:.2f})")
                    q_tot *= item['quota']
                
                st.write(f"📊 Quota Totale: **{q_tot:.2f}**")
                puntata = st.number_input("Puntata", min_value=10, max_value=int(saldo) if saldo > 10 else 10, step=10)
                
                if bonus == "FREE_BET_1000":
                    puntata = 1000
                vincita = puntata * q_tot
                if vincita > 500000: vincita = 500000
                
                st.write(f"💰 Vincita Potenziale: **{vincita:.0f}**")
                
                if st.button("GIOCA ORA", type="primary"):
                    if bonus == "FREE_BET_1000":
                        conn.execute("UPDATE utenti SET bonus_attivo = 'NESSUNO' WHERE username=?", (st.session_state.user,))
                    else:
                        conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (puntata, st.session_state.user))
                        if bonus in ["BOOST_X2", "BOOST_X3"]:
                            conn.execute("UPDATE utenti SET bonus_attivo = 'NESSUNO' WHERE username=?", (st.session_state.user,))
                            
                    desc_final = " | ".join([f"{x['desc']}->{x['scelta']}" for x in st.session_state.schedina])
                    conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)",
                                 (st.session_state.user, desc_final, q_tot, puntata, vincita, f"IN CORSO (Bonus: {bonus})"))
                    conn.commit()
                    st.session_state.schedina = []
                    st.balloons()
                    st.rerun()

            st.divider()
            st.subheader("🎡 Crazy Wheel")
            if giro_usato == 0:
                st.markdown("<div class='bet-card'>🎁 GIRO OMAGGIO (500 Punti)</div>", unsafe_allow_html=True)
                if st.button("GIRA COI PUNTI"):
                    if saldo >= 500:
                        conn.execute("UPDATE utenti SET saldo=saldo-500, giro_punti_usato=1 WHERE username=?", (st.session_state.user,))
                        conn.commit()
                        esegui_giro_pazzo(st.session_state.user)
                    else: st.error("Punti insufficienti!")
            else:
                st.markdown("<div class='bet-card'>🎫 GIRO PREMIUM</div>", unsafe_allow_html=True)
                token_in = st.text_input("Token Premium")
                if st.button("SBLOCCA E GIRA"):
                    check = conn.execute("SELECT usato FROM tokens WHERE codice=?", (token_in,)).fetchone()
                    if check and check[0] == 0:
                        conn.execute("UPDATE tokens SET usato=1 WHERE codice=?", (token_in,))
                        conn.commit()
                        esegui_giro_pazzo(st.session_state.user)
                    else: st.error("Token non valido!")

    with tab_ranking:
        st.header("🏆 Classifica Ufficiale Fenice Jam")
        st.write("Ogni vittoria in un match assegna 3 punti per il ranking.")
        
        # Estrai la classifica
        df_ranking = pd.read_sql_query("SELECT nome AS MC, punti_ranking AS Punti, vittorie AS Vittorie FROM mcs ORDER BY punti_ranking DESC, vittorie DESC", conn)
        
        if not df_ranking.empty:
            st.dataframe(df_ranking, use_container_width=True, hide_index=True)
        else:
            st.info("La classifica è ancora vuota. Fai combattere i tuoi MC!")

else:
    st.title("🔥 FeniceBet")
    st.write("Accedi o Registrati per iniziare a giocare!")
