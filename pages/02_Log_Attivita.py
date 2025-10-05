#/pages/02_Log_Attivita.py
import streamlit as st
from utils.db import get_log_content, log_activity

st.set_page_config(page_title="Log Attività - Centri Estivi", layout="wide")

# --- Sidebar ---
st.sidebar.title("🏖️ Centri Estivi RER")
st.sidebar.info("Applicazione per la gestione e validazione dati spese Centri Estivi")

# --- Pagina Log Attività ---
st.title("📋 Log Attività Sistema")
log_activity("Utente", "PAGE_VIEW", "Log Attività")

st.markdown("""
Questa pagina mostra il log completo delle attività del sistema.
Il log contiene informazioni su tutte le operazioni effettuate nell'applicazione.
""")

st.markdown("---")

if st.button("🔄 Aggiorna Log", key="refresh_log_btn"):
    st.rerun()

st.subheader("📄 Contenuto Log (ordine inverso: più recenti in alto)")

try:
    log_content = get_log_content()

    if log_content:
        # Mostra il log in un text_area scrollabile
        st.text_area(
            label="Log completo",
            value=log_content,
            height=600,
            key="log_display_area",
            help="Log delle attività (più recenti in alto)"
        )

        # Informazioni aggiuntive
        log_lines = log_content.split('\n')
        total_lines = len([line for line in log_lines if line.strip()])
        st.info(f"📊 Totale righe log: {total_lines}")

    else:
        st.warning("⚠️ Il file di log è vuoto o non ancora creato.")

except Exception as e:
    st.error(f"🚨 Errore durante la lettura del log: {e}")
    log_activity("Sistema", "LOG_READ_ERROR", str(e))

st.markdown("---")
st.caption("💡 Suggerimento: Usa il pulsante 'Aggiorna Log' per visualizzare le operazioni più recenti.")
#/pages/02_Log_Attivita.py