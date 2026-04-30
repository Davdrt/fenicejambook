import streamlit as st
import pandas as pd
import os
import math
from datetime import datetime

# --- CONFIGURAZIONE ---
NOME_FILE_DB = "database_fenicebet.csv"
NOME_FILE_TICKET = "registro_ticket_fenicebet.csv"
PASS_SEGRETA = "segreto123"

# --- FUNZIONI DI SISTEMA ---
def carica_db():
    if os.path.exists(NOME_FILE_DB): return pd.read_csv(NOME_FILE_DB)
    return pd.DataFrame(columns=['Nome', 'Vittorie', 'Finali', 'Semi', 'Quarti', 'Presenze', 'Pericolo', 'Popolarita', 'Media_Forma'])

def carica_ticket():
    if os.path.exists(NOME_FILE_TICKET): return pd.read_csv(NOME_FILE_TICKET)
    return pd.DataFrame(columns=['ID', 'Data', 'Scommettitore', 'Scelta', 'Quota', 'Puntata', 'Vincita_Pot', 'Stato'])

def salva_file(df, nome_file):
    if not st.session_state.get('sandbox', False):
        df.to_csv(nome_file, index=False)

# --- LOGIN FENICEBET ---
if "autenticato" not in st.session_state: st.session_state.autenticato = False

if not st.session_state.autenticato:
    st.set_page_config(page_title="FeniceBet - Login", page_icon="🔥")
    st.title("🔥 FeniceBet")
    st.subheader("Accedi al Terminale Bookmaker")
    pwd = st.text_input("Codice Autorizzazione:", type="password")
    if st.button("Entra nel Sistema"):
        if pwd == PASS_SEGRETA:
            st.session_state.autenticato = True
            st.rerun()
    st.stop()

# --- SETUP DATI ---
df = carica_db()
ticket_df = carica_ticket()

# --- SIDEBAR FENICEBET ---
st.sidebar.title("🦅 FeniceBet Menu")
st.session_state.sandbox = st.sidebar.toggle("🛠️ MODALITÀ TEST", value=False)
margine_base = st.sidebar.slider("Margine Banco (%)", 5, 40, 20) / 100

menu = st.sidebar.radio("Navigazione", ["📊 Lavagna Quote", "🎟️ Emetti Ticket", "💰 Cassa & Risultati", "🏆 Hall of Fame", "⚙️ Database MC"])

# --- MOTORE DI CALCOLO FeniceBet ---
def calcola_rating_pro(nome_mc, dataframe):
    r = dataframe[dataframe['Nome'] == nome_mc].iloc[0]
    punti_tot = (r['Vittorie']*10) + (r['Finali']*6) + (r['Semi']*3) + (r['Quarti']*1)
    # Protezione novellini (fede statistica)
    rating_storico = (punti_tot + 5) / (r['Presenze'] + 10)
    # Fattore forma
    affidabilita = min(r['Presenze'] / 10, 1.0)
    forma_recente = r.get('Media_Forma', rating_storico)
    if pd.isna(forma_recente): forma_recente = rating_storico
    
    rating_base = (rating_storico * (1 - (0.5 * affidabilita))) + (forma_recente * (0.5 * affidabilita))
    hype = 0.7 + (r['Popolarita'] * 0.1)
    return rating_base * r['Pericolo'] * hype

def genera_quota_blindata(rating_mc, tot_rating, presenze, pericolo, margine_base):
    p = rating_mc / tot_rating
    # o-piccolo per incertezza
    o_piccolo = 1 / math.sqrt(presenze + 5)
    margine_reale = margine_base + (o_piccolo * 0.15)
    quota = (1 / p) * (1 - margine_reale)
    # Tetto ai BIG
    if pericolo >= 1.6: quota = min(quota, 3.50)
    return max(round(quota, 2), 1.10)

# --- 1. LAVAGNA QUOTE (PUBBLICA) ---
if menu == "📊 Lavagna Quote":
    st.header("📢 FeniceBet: Quote della Serata")
    presenti = st.multiselect("Seleziona MC in gara:", df['Nome'].tolist())
    if presenti:
        p_df = df[df['Nome'].isin(presenti)].copy()
        p_df['rating_calc'] = p_df.apply(lambda x: calcola_rating_pro(x['Nome'], df), axis=1)
        tot_r = p_df['rating_calc'].sum()
        lavagna = []
        for _, r in p_df.iterrows():
            q = genera_quota_blindata(r['rating_calc'], tot_r, r['Presenze'], r['Pericolo'], margine_base)
            lavagna.append({"Freestyler": r['Nome'], "Quota": q, "Hype": "🔥" * int(r['Popolarita'])})
        st.table(pd.DataFrame(lavagna))
        st.info("💡 Schermata sicura da mostrare al pubblico.")

# --- 2. EMISSIONE TICKET ---
elif menu == "🎟️ Emetti Ticket":
    st.header("🎟️ Registrazione Scommessa")
    incasso = ticket_df[ticket_df['Stato'] == 'In Corso']['Puntata'].sum()
    esposizione = ticket_df[ticket_df['Stato'] == 'In Corso'].groupby('Scelta')['Vincita_Pot'].sum()
    
    c1, c2 = st.columns(2)
    scommettitore = c1.text_input("Nome Cliente")
    puntata = c2.number_input("Cifra Puntata (€)", min_value=1.0, step=1.0)
    
    attivi = st.multiselect("Seleziona MC:", df['Nome'].tolist())
    if attivi and scommettitore:
        p_df = df[df['Nome'].isin(attivi)].copy()
        p_df['rating_calc'] = p_df.apply(lambda x: calcola_rating_pro(x['Nome'], df), axis=1)
        tot_r = p_df['rating_calc'].sum()
        scelta = st.selectbox("Punta su:", attivi)
        r_scelta = p_df[p_df['Nome'] == scelta].iloc[0]
        q_scelta = genera_quota_blindata(r_scelta['rating_calc'], tot_r, r_scelta['Presenze'], r_scelta['Pericolo'], margine_base)
        vincita_pot = round(puntata * q_scelta, 2)
        
        # ALERT RISCHIO
        esposizione_futura = esposizione.get(scelta, 0) + vincita_pot
        st.metric("Vincita Potenziale", f"{vincita_pot} €", f"Quota: {q_scelta}")
        
        accetta = True
        if incasso > 0:
            if esposizione_futura > incasso:
                st.error("🛑 BLOCCO: Rischio troppo alto per il banco su questo MC.")
                accetta = False
            elif esposizione_futura > (incasso * 0.7):
                st.warning("⚠️ Rischio Elevato.")

        if st.button("Stampa Ticket", disabled=not accetta):
            nuovo_t = pd.DataFrame([[len(ticket_df)+1, datetime.now().strftime("%H:%M"), scommettitore, scelta, q_scelta, puntata, vincita_pot, "In Corso"]], columns=ticket_df.columns)
            ticket_df = pd.concat([ticket_df, nuovo_t], ignore_index=True)
            salva_file(ticket_df, NOME_FILE_TICKET)
            st.success("Ticket FeniceBet Eseguito!")
            st.code(f"--- FENICEBET TICKET ---\nID: {len(ticket_df)}\nCliente: {scommettitore}\nSu: {scelta}\nQuota: {q_scelta}\nVincita: {vincita_pot}€\n------------------------")

# --- 3. CASSA & RISULTATI ---
elif menu == "💰 Cassa & Risultati":
    st.header("💰 Bilancio Live FeniceBet")
    incasso_t = ticket_df['Puntata'].sum()
    rischio_t = ticket_df[ticket_df['Stato'] == 'In Corso']['Vincita_Pot'].sum()
    st.columns(2)[0].metric("Incasso Reale", f"{incasso_t} €")
    st.columns(2)[1].metric("Debito Potenziale", f"{rischio_t} €", delta_color="inverse")
    st.bar_chart(pd.DataFrame({'Euro': [incasso_t, rischio_t]}, index=['Entrate', 'Rischio']))
    
    st.subheader("🏁 Chiusura Serata")
    vincitore = st.selectbox("Vincitore Ufficiale:", ["-"] + df['Nome'].tolist())
    if st.button("Paga Ticket & Aggiorna Ranking"):
        ticket_df.loc[(ticket_df['Scelta'] == vincitore) & (ticket_df['Stato'] == 'In Corso'), 'Stato'] = 'VINTO ✅'
        ticket_df.loc[(ticket_df['Scelta'] != vincitore) & (ticket_df['Stato'] == 'In Corso'), 'Stato'] = 'PERSO ❌'
        salva_file(ticket_df, NOME_FILE_TICKET)
        # Aggiorna Rating & Pericolo Autom.
        p_att = df.loc[df['Nome'] == vincitore, 'Pericolo'].values[0]
        df.loc[df['Nome'] == vincitore, ['Vittorie', 'Presenze', 'Pericolo']] = [df.loc[df['Nome'] == vincitore, 'Vittorie'].values[0]+1, df.loc[df['Nome'] == vincitore, 'Presenze'].values[0]+1, round(min(p_att + 0.1, 2.0), 2)]
        salva_file(df, NOME_FILE_DB)
        st.success("FeniceBet ha aggiornato la Hall of Fame e pagato i vincitori!")

# --- 5. DATABASE MC ---
elif menu == "⚙️ Database MC":
    st.header("⚙️ Gestione Anagrafica")
    st.dataframe(df.sort_values(by="Vittorie", ascending=False))
    with st.form("edit"):
        n = st.text_input("Nome d'arte")
        v = st.number_input("Vittorie Storiche", 0)
        p = st.number_input("Presenze Storiche", 0)
        per = st.slider("Livello Pericolo", 0.5, 2.0, 1.0)
        pop = st.slider("Hype (Popolarità)", 1, 5, 3)
        if st.form_submit_button("Salva"):
            if n in df['Nome'].values:
                df.loc[df['Nome'] == n, ['Vittorie', 'Presenze', 'Pericolo', 'Popolarita']] = [v, p, per, pop]
            else:
                nuovo = pd.DataFrame([[n, v, 0, 0, 0, p, per, pop, 0.5]], columns=df.columns)
                df = pd.concat([df, nuovo], ignore_index=True)
            salva_file(df, NOME_FILE_DB)
            st.rerun()
