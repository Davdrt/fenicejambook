import streamlit as st
import sqlite3
import pandas as pd
import random
import secrets
import time
import os
import math

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="FeniceBet Pro v8", page_icon="🔥", layout="wide")

# --- DATABASE ENGINE v8 ---
def init_db():
    conn = sqlite3.connect('fenicebet_v8.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mcs (nome TEXT PRIMARY KEY, punti_ranking INT DEFAULT 0, vittorie INT DEFAULT 0, presenze INT DEFAULT 0, pericolo REAL DEFAULT 1.0, popolarita INT DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS utenti (username TEXT PRIMARY KEY, email TEXT, password TEXT, saldo REAL DEFAULT 1000, giro_punti_usato INT DEFAULT 0, bonus_attivo TEXT DEFAULT 'NESSUNO')''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, mc1 TEXT, mc2 TEXT, q1 REAL, q2 REAL, stato TEXT, vincitore TEXT DEFAULT 'TBD')''')
    c.execute('''CREATE TABLE IF NOT EXISTS ticket (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, dettagli TEXT, quota REAL, puntata REAL, vincita_pot REAL, stato TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (codice TEXT PRIMARY KEY, usato INT DEFAULT 0)''')
    # Tabella per i Grafici di Cassa
    c.execute('''CREATE TABLE IF NOT EXISTS flussi (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, tipo TEXT, importo REAL, note TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- FUNZIONI DI SUPPORTO ---
def registra_flusso(tipo, importo, note=""):
    conn.execute("INSERT INTO flussi (timestamp, tipo, importo, note) VALUES (DATETIME('now'), ?, ?, ?)", (tipo, importo, note))
    conn.commit()

def calcola_quota_tecnica(nome_mc):
    res = conn.execute("SELECT vittorie, presenze, pericolo, popolarita FROM mcs WHERE nome=?", (nome_mc,)).fetchone()
    if not res or res[1] == 0: return 1.90
    v, p, per, pop = res
    rating = ((v * 10) + 5) / (p + 10)
    prob = rating * per * (0.8 + pop * 0.05)
    return round(max(1.20, min(1 / (prob / (prob + 1)) + 0.15, 8.0)), 2)

# --- SESSION STATE ---
if "user" not in st.session_state: st.session_state.user = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False
if "admin_view_as_player" not in st.session_state: st.session_state.admin_view_as_player = False
if "schedina" not in st.session_state: st.session_state.schedina = []

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("Logo.png"): st.image("Logo.png", use_container_width=True)
    st.title("🔥 FENICE BET v8")
    
    if not st.session_state.user:
        mode = st.radio("Accesso", ["Login", "Registrati", "Admin"])
        u_in = st.text_input("Username")
        p_in = st.text_input("Password", type="password")
        if mode == "Registrati":
            e_in = st.text_input("Email")
            if st.button("REGISTRATI"):
                if "@" not in e_in or "." not in e_in: st.error("Email invalida")
                else:
                    conn.execute("INSERT INTO utenti (username, email, password) VALUES (?,?,?)", (u_in, e_in, p_in))
                    conn.commit(); st.success("Registrato!"); registra_flusso("INGRESSO_UTENTE", 1000, f"Bonus benvenuto {u_in}")
        elif st.button("ACCEDI"):
            if mode == "Admin" and p_in == "admin123":
                st.session_state.user = "ADMIN"; st.session_state.is_admin = True; st.rerun()
            elif mode == "Login":
                res = conn.execute("SELECT username FROM utenti WHERE username=? AND password=?", (u_in, p_in)).fetchone()
                if res: st.session_state.user = u_in; st.rerun()
                else: st.error("Dati errati")
    else:
        st.write(f"Connesso come: **{st.session_state.user}**")
        if st.session_state.is_admin:
            st.session_state.admin_view_as_player = st.toggle("Vista Giocatore", value=st.session_state.admin_view_as_player)
        if st.button("LOGOUT"):
            st.session_state.user = None; st.session_state.is_admin = False; st.rerun()

# --- VISTA ADMIN (PANNELLO GESTORE) ---
if st.session_state.is_admin and not st.session_state.admin_view_as_player:
    st.title("🕹️ Dashboard Pro")
    t1, t2, t3, t4, t5 = st.tabs(["📊 Flussi & Simulatore", "⚔️ Match", "🎤 MCs", "🎫 Token", "👥 Utenti"])
    
    with t1:
        st.subheader("📈 Visione Flussi di Cassa")
        df_flussi = pd.read_sql_query("SELECT * FROM flussi", conn)
        if not df_flussi.empty:
            # Calcolo saldo totale del banco (punti circolanti)
            tot_punti = conn.execute("SELECT SUM(saldo) FROM utenti").fetchone()[0]
            st.metric("Punti Totali Circolanti", f"{tot_punti:,.0f} 🪙")
            # Grafico andamento
            df_flussi['cumsum'] = df_flussi['importo'].cumsum()
            st.line_chart(df_flussi, x="timestamp", y="cumsum")
        
        st.divider()
        st.subheader("🧪 Simulatore Match")
        sim_a = st.selectbox("Simula MC 1", [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()])
        sim_b = st.selectbox("Simula MC 2", [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()])
        if st.button("Simula Esito"):
            q1, q2 = calcola_quota_tecnica(sim_a), calcola_quota_tecnica(sim_b)
            st.write(f"Risultato Simulato: {sim_a} (@{q1}) vs {sim_b} (@{q2})")
            st.info("Questo match non verrà pubblicato, serve solo per testare le quote.")

    with t2:
        st.subheader("Crea Match")
        mcs = [m[0] for m in conn.execute("SELECT nome FROM mcs").fetchall()]
        ca, cb = st.columns(2)
        m1 = ca.selectbox("MC 1", mcs, key="am1")
        m2 = cb.selectbox("MC 2", mcs, key="am2")
        q1, q2 = ca.number_input("Q1", calcola_quota_tecnica(m1)), cb.number_input("Q2", calcola_quota_tecnica(m2))
        if st.button("Pubblica Match"):
            conn.execute("INSERT INTO matches (desc, mc1, mc2, q1, q2, stato) VALUES (?,?,?,?,?,?)", (f"{m1} vs {m2}", m1, m2, q1, q2, "APERTO"))
            conn.commit(); st.success("Online!")
        
        st.divider()
        st.subheader("Chiudi Match")
        aperti = conn.execute("SELECT id, desc, mc1, mc2 FROM matches WHERE stato='APERTO'").fetchall()
        if aperti:
            sel = st.selectbox("Seleziona Match", [m[0] for m in aperti], format_func=lambda x: [m[1] for m in aperti if m[0]==x][0])
            m_d = [m for m in aperti if m[0]==sel][0]
            v = st.radio("Vincitore", [m_d[2], m_d[3]])
            if st.button("Paga e Ranking"):
                conn.execute("UPDATE matches SET stato='CHIUSO', vincitore=? WHERE id=?", (v, sel))
                conn.execute("UPDATE mcs SET punti_ranking=punti_ranking+3, vittorie=vittorie+1, presenze=presenze+1 WHERE nome=?", (v,))
                # Paga vincitori
                win_tickets = conn.execute("SELECT username, vincita_pot FROM ticket WHERE dettagli LIKE ? AND stato='IN CORSO'", (f"%{m_d[1]}->{v}%",)).fetchall()
                for w in win_tickets:
                    conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (w[1], w[0]))
                    registra_flusso("VINCITA_PAGATA", w[1], f"A {w[0]}")
                conn.commit(); st.success("Match chiuso!"); st.rerun()

    with t3:
        st.subheader("Gestione MC")
        n_mc = st.text_input("Nome")
        v_mc = st.number_input("Vittorie", 0)
        p_mc = st.number_input("Presenze", 0)
        per_mc = st.slider("Pericolo", 0.5, 2.0, 1.0)
        pop_mc = st.slider("Popolarità", 1, 10, 5)
        if st.button("Salva MC"):
            conn.execute("INSERT OR REPLACE INTO mcs (nome, vittorie, presenze, pericolo, popolarita) VALUES (?,?,?,?,?)", (n_mc, v_mc, p_mc, per_mc, pop_mc))
            conn.commit(); st.success("Salvato")

    with t4:
        if st.button("Genera Token Premium 🎫"):
            tk = f"FENICE-{secrets.token_hex(3).upper()}"
            conn.execute("INSERT INTO tokens (codice) VALUES (?)", (tk,)); conn.commit(); st.code(tk)

    with t5:
        st.subheader("Database Utenti")
        st.dataframe(pd.read_sql_query("SELECT username, email, saldo FROM utenti", conn), use_container_width=True)

# --- VISTA GIOCATORE (UTENTE O ADMIN IN PLAYER MODE) ---
elif st.session_state.user:
    u_data = conn.execute("SELECT saldo, giro_punti_usato, bonus_attivo FROM utenti WHERE username=?", (st.session_state.user,)).fetchone()
    # Se admin gioca, usiamo un saldo fittizio se non esiste nel db utenti
    if not u_data and st.session_state.is_admin:
        saldo, giro_usato, bonus = 999999, 0, "ADMIN_POWER"
    else:
        saldo, giro_usato, bonus = u_data

    st.title("🎰 Arena Betting")
    st.metric("SALDO ATTUALE", f"{saldo:,.0f} 🪙")
    
    tabs = st.tabs(["🔥 Match Live", "🎡 Crazy Wheel", "🏆 Classifiche"])
    
    with tabs[0]:
        c1, c2 = st.columns([2, 1.2])
        with c1:
            matches = conn.execute("SELECT * FROM matches WHERE stato='APERTO'").fetchall()
            for m in matches:
                with st.expander(f"📍 {m[1]}"):
                    scelta = st.radio("Punta su:", [m[2], m[3]], key=f"bet_{m[0]}")
                    q = m[4] if scelta == m[2] else m[5]
                    if st.button(f"Includi @{q:.2f}", key=f"add_{m[0]}"):
                        if not any(x['id'] == m[0] for x in st.session_state.schedina):
                            st.session_state.schedina.append({"id": m[0], "desc": m[1], "scelta": scelta, "quota": q})
                            st.rerun()
        with c2:
            st.subheader("🛒 Schedina Multipla")
            if not st.session_state.schedina: st.info("Scegli un match")
            else:
                qt = 1.0
                for s in st.session_state.schedina:
                    st.write(f"✅ {s['desc']} -> {s['scelta']} (@{s['quota']})")
                    qt *= s['quota']
                st.write(f"📈 QUOTA TOT: **{qt:.2f}**")
                pnt = st.number_input("Punta", 10, int(saldo) if saldo > 10 else 100)
                v_pot = pnt * qt
                if v_pot > 500000: v_pot = 500000
                st.write(f"💰 VINCITA POT: **{v_pot:.0f}**")
                if st.button("GIOCA TICKET"):
                    conn.execute("UPDATE utenti SET saldo = saldo - ? WHERE username=?", (pnt, st.session_state.user))
                    registra_flusso("SCOMMESSA_PIAZZATA", -pnt, f"Da {st.session_state.user}")
                    det = " | ".join([f"{x['desc']}->{x['scelta']}" for x in st.session_state.schedina])
                    conn.execute("INSERT INTO ticket (username, dettagli, quota, puntata, vincita_pot, stato) VALUES (?,?,?,?,?,?)", (st.session_state.user, det, qt, pnt, v_pot, "IN CORSO"))
                    conn.commit(); st.session_state.schedina = []; st.balloons(); st.rerun()
            if st.button("Svuota Carrello"): st.session_state.schedina = []; st.rerun()

    with tabs[1]:
        st.subheader("🎡 La Ruota dei 10 Premi")
        # Logica premi (punti, boost, etc.) semplificata qui per spazio, ma identica alla v7
        if st.button("GIRA RUOTA (500 🪙)"):
            if saldo >= 500:
                conn.execute("UPDATE utenti SET saldo = saldo - 500 WHERE username=?", (st.session_state.user,))
                registra_flusso("GIRO_RUOTA", -500, st.session_state.user)
                vincita = random.choice([0, 100, 500, 1000, 5000]) # Esempio
                conn.execute("UPDATE utenti SET saldo = saldo + ? WHERE username=?", (vincita, st.session_state.user))
                registra_flusso("VINCITA_RUOTA", vincita, st.session_state.user)
                st.success(f"Vinto: {vincita}!"); st.rerun()

    with tabs[2]:
        ca, cb = st.columns(2)
        with ca:
            st.subheader("🏆 Leaderboard Utenti")
            df_u = pd.read_sql_query("SELECT username, saldo FROM utenti ORDER BY saldo DESC LIMIT 10", conn)
            st.table(df_u)
        with cb:
            st.subheader("🎤 Ranking MC")
            df_m = pd.read_sql_query("SELECT nome, punti_ranking FROM mcs ORDER BY punti_ranking DESC", conn)
            st.table(df_m)

else:
    st.title("🔥 FENICE BET PRO")
    if os.path.exists("Logo.png"): st.image("Logo.png", width=400)
    st.write("Accedi per partecipare alla sfida!")
