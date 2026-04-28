import streamlit as st
import pandas as pd

# --- 1. BLOCCO PASSWORD SEGRETA ---
def check_password():
    # Sostituisci "segreto123" con la password che preferisci
    if st.session_state.password == "segreto123":
        st.session_state.password_correct = True
    else:
        st.error("🔒 Password errata. Accesso negato.")

if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

if not st.session_state.password_correct:
    st.title("🛡️ Login Bookmaker")
    st.text_input("Inserisci la password per accedere:", type="password", key="password", on_change=check_password)
    st.stop() # Ferma il codice qui se la password è sbagliata

# --- 2. IL MOTORE DELL'APP (Visibile solo a te) ---
st.title("🏆 Freestyle Bookmaker Pro")

# Inizializziamo il database virtuale
if 'partecipanti' not in st.session_state:
    st.session_state.partecipanti = {}
if 'tickets' not in st.session_state:
    st.session_state.tickets = []

margine = 0.20
fondo_iniziale = 150.0

# --- SEZIONE: AGGIUNGI FREESTYLER ---
with st.expander("➕ Aggiungi Freestyler in Gara"):
    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome")
    vittorie = col2.number_input("Vittorie", min_value=0, step=1)
    tentativi = col1.number_input("Tentativi Totali", min_value=0, step=1)
    pericolo = col2.number_input("Fattore Pericolo (1.0 std)", value=1.0, step=0.1)
    
    if st.button("Inserisci nel Torneo"):
        if nome and nome not in st.session_state.partecipanti:
            p_base = ((vittorie / (tentativi + 5)) if tentativi > 0 else 0.02) * pericolo
            st.session_state.partecipanti[nome] = {'p_base': p_base, 'puntato': 0.0, 'in_gara': True}
            st.success(f"{nome} aggiunto con successo!")
            st.rerun()

# --- SEZIONE: LAVAGNA QUOTE IN DIRETTA ---
in_gara = {k: v for k, v in st.session_state.partecipanti.items() if v['in_gara']}

if in_gara:
    somma_p = sum(x['p_base'] for x in in_gara.values())
    cassa = fondo_iniziale + sum(x['puntato'] for x in in_gara.values())
    
    dati_tabella = []
    for nome, dati in in_gara.items():
        quota_partenza = cassa * (dati['p_base'] / somma_p)
        quota_live = (cassa * (1 - margine)) / (quota_partenza + dati['puntato'])
        dati['quota_corrente'] = max(round(quota_live, 2), 1.05)
        
        dati_tabella.append({
            "Freestyler": nome,
            "Puntato (€)": f"€ {dati['puntato']:.2f}",
            "QUOTA": f"{dati['quota_corrente']:.2f}"
        })
    
    st.subheader("📊 Lavagna Quote")
    # Mostriamo una bella tabella ordinata
    st.dataframe(pd.DataFrame(dati_tabella), use_container_width=True)

    # --- SEZIONE: REGISTRA PUNTATA ---
    st.subheader("💶 Nuova Scommessa")
    col3, col4 = st.columns(2)
    chi = col3.selectbox("Su chi puntano?", list(in_gara.keys()))
    soldi = col4.number_input("Importo (€)", min_value=1.0, step=1.0)
    
    if st.button("PUNTA E BLOCCA QUOTA", type="primary"):
        q_fissa = in_gara[chi]['quota_corrente']
        st.session_state.tickets.append({'nome': chi, 'importo': soldi, 'vincita': soldi * q_fissa})
        st.session_state.partecipanti[chi]['puntato'] += soldi
        st.success(f"✅ Registrati €{soldi} su {chi} a quota {q_fissa}")
        st.rerun()

    # --- SEZIONE: ELIMINAZIONE ---
    st.subheader("💀 Elimina Partecipante")
    chi_esce = st.selectbox("Chi ha perso la battle?", list(in_gara.keys()))
    if st.button("Elimina dal Torneo"):
        st.session_state.partecipanti[chi_esce]['in_gara'] = False
        st.warning(f"{chi_esce} è stato eliminato.")
        st.rerun()

else:
    st.info("Nessun freestyler in gara. Aggiungine uno dal menu in alto.")
