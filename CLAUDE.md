# CLAUDE.md

Questo file fornisce indicazioni a Claude Code (claude.ai/code) quando lavora con il codice in questo repository.

## Panoramica del Progetto

Questa è un'**applicazione web basata su Streamlit** per la gestione e validazione dei dati di spesa dei Centri Estivi per la Regione Emilia-Romagna (RER). L'applicazione gestisce dati formattati SIFER (Sistema Informativo Fondi Europei Regionali), esegue validazioni complete e memorizza i record in un database SQLite.

### Ruoli Chiave e Flussi di Lavoro

L'applicazione supporta tre ruoli utente con flussi di lavoro distinti:

1. **Richiedente**: Incolla i dati di spesa da Excel, li valida e scarica file CSV per l'invio a SIFER
2. **Controllore**: Carica file CSV SIFER, valida i dati e salva nel database dopo la verifica
3. **Admin**: Accesso completo a tutte le funzionalità più gestione utenti

## Architettura

### Struttura dell'Applicazione

```
app.py                          # Entry point principale con login e flusso Richiedente
pages/
  01_Gestione_Dati_Controllore.py   # Flusso Controllore (carica, valida, salva in DB)
  02_Log_Attivita.py                 # Visualizzatore log attività
  03_Admin_Settings.py               # Gestione utenti Admin
  04_Dashboard_Dati.py               # Dashboard dati e operazioni bulk
utils/
  db.py                         # Operazioni database e logging attività
  common_utils.py               # Funzioni di validazione e processamento dati
  auth.py                       # Utilità autenticazione
  hash_password.py              # Utilità hashing password
config.yaml                     # Credenziali utente e configurazione autenticazione
database/
  spese.db                      # Database SQLite (auto-creato)
  activity.log                  # Log attività applicazione
```

### Flusso dei Dati

**Flusso Richiedente:**
1. L'utente incolla dati Excel a 15 colonne (separati da tab)
2. L'app valida CF (codice fiscale), date, importi, regole contributi
3. L'utente scarica CSV formattato SIFER (con header versione)
4. **I dati NON vengono salvati nel database** in questo flusso

**Flusso Controllore:**
1. Caricamento file CSV SIFER (separato da virgola, valori quotati)
2. Parsing colonne SIFER verso formato interno
3. Validazione dati (stesse validazioni del Richiedente)
4. Verifica unicità Rif. PA nel database
5. Salvataggio nel database se tutte le validazioni passano

### Formati Dati Chiave

**Formato CSV SIFER:**
- Prima riga: Stringa versione (es. "SIFER_costi_reali_1420_v1.0")
- Righe dati: 16 colonne, separate da virgola, tutti i valori quotati
- Mappature chiave:
  - "Rif. PA" → `rif_pa` (formato: AAAA-NUMERO/RER)
  - "ID documento" → parsato in `cup`, `distretto`, `comune_capofila`, progressivo
  - "Voce imputazione" → parsato in `comune_centro_estivo`, `centro_estivo`
  - "Note imputazione" → parsato in `altri_contributi`, `quota_retta_destinatario`, `totale_retta`
  - "Tipo pagamento" → `controlli_formali_dichiarati`

**Schema Database:**
- Tabella: `spese_sostenute`
- 20+ colonne inclusi tutti i campi finanziari e metadati
- Vincolo unique: `(id_trasmissione, codice_fiscale_bambino, data_mandato, centro_estivo, valore_contributo_fse)`
- Usa SQLite con adapter date/datetime personalizzati per type safety

## Comandi di Sviluppo

### Esecuzione dell'Applicazione

```bash
# Attivare ambiente virtuale
source .centiest/bin/activate  # macOS/Linux

# Installare dipendenze
pip install -r requirements.txt

# Eseguire l'applicazione
streamlit run app.py
```

### Esecuzione dei Test

```bash
# Eseguire tutti i test
pytest

# Eseguire file di test specifico
pytest tests/test_common_utils.py

# Eseguire funzione di test specifica
pytest tests/test_common_utils.py::test_validate_codice_fiscale_valid

# Eseguire con report copertura
pytest --cov=utils tests/

# Generare report HTML copertura
pytest --cov=utils --cov-report=html tests/
```

## Dettagli Implementativi Importanti

### Logica di Validazione

**Validazione Codice Fiscale (CF):**
- Deve essere esattamente 16 caratteri alfanumerici
- Pattern rigoroso: 6 lettere, 2 cifre, 1 lettera, 2 cifre, 1 lettera, 3 cifre, 1 lettera
- Sempre convertito in maiuscolo e ripulito prima della validazione

**Validazioni Finanziarie:**
- Totale retta (D) deve essere uguale a: valore_contributo_fse (A) + altri_contributi (B) + quota_retta_destinatario (C)
- Contributo FSE (A) non può superare 300€ per riga
- Contributo FSE non può superare il massimo calcolato: min(totale_retta/settimane, 100€) * settimane
- Totale FSE per bambino (stesso CF) su tutte le righe non può superare 300€

**Gestione Date:**
- Date di input accettate come "GG/MM/AAAA" (dayfirst=True)
- Memorizzate come oggetti `date` Python in SQLite
- Adapter/converter personalizzati registrati per type safety

**Parsing Valute:**
- Accetta sia formato "1.234,56" (europeo) che "1234.56" (US)
- Gestisce formati misti nello stesso dataset
- Restituisce 0.0 per valori non validi (log warning)

### Controlli Formali

**Importante:** Il campo "controlli_formali" è ora gestito come **valore dichiarato** dall'utente/file SIFER, non come calcolo del 5% del contributo FSE. Questo è cambiato durante lo sviluppo:
- Nel CSV SIFER: proviene dalla colonna "Tipo pagamento"
- Valori mancanti o vuoti vengono sostituiti con "dato assente"
- La validazione accetta qualsiasi valore (o vuoto) senza errori
- Salvato nel database come fornito

### Operazioni Database

**Gestione Connessioni:**
- `get_db_connection()` restituisce connessione con PARSE_DECLTYPES abilitato
- Le funzioni accettano parametro `existing_conn` per controllo transazioni
- Usare sempre pattern `existing_conn` per transazioni multi-operazione

**Logging:**
- Tutte le operazioni database loggato via `log_activity(username, action, details)`
- Log memorizzati in `database/activity.log` con rotazione (5MB, 2 backup)
- Formato log include username, timestamp, azione, dettagli

### Pattern Gestione Errori

**Parsing Dati Sicuro:**
```python
# Verificare sempre None/NaN prima delle operazioni
if pd.isna(value) or not value:
    return default_value

# Usare parse_excel_currency() per tutti i campi valuta
amount = parse_excel_currency(row.get('importo_mandato', 0.0))
```

**Risultati Validazione:**
```python
# run_detailed_validations() restituisce (DataFrame, has_blocking_errors)
df_validation, has_errors = run_detailed_validations(...)
if has_errors:
    # Bloccare operazione salvataggio, mostrare errori
```

## Gestione Session State

Chiavi session state critiche in Streamlit:

**Autenticazione:**
- `authentication_status`: True/False/None
- `username`, `name`, `user_role`
- `authenticator`: oggetto stauth.Authenticate

**Flusso Richiedente:**
- `doc_metadati_richiedente`: dict con rif_pa, cup, distretto, comune_capofila
- `metadati_confermati_richiedente`: boolean
- `rif_pa_error_message`: errore validazione per Rif. PA

**Flusso Controllore:**
- `ctrl_df_sifer_loaded`: DataFrame SIFER grezzo
- `ctrl_df_internal_for_validation`: formato interno parsato
- `ctrl_df_ready_for_db`: DataFrame finale pronto per insert
- `ctrl_validation_results_df`: risultati validazione da visualizzare
- `ctrl_has_blocking_errors`: boolean
- `ctrl_current_rif_pa_info`: dict con rif_pa e messaggio
- `ctrl_last_uploaded_filename`: traccia cambi file

**Importante:** Pulire il session state rilevante quando il file cambia o dopo salvataggio riuscito per evitare problemi con dati obsoleti.

## Configurazione e Sicurezza

**config.yaml:**
- Contiene credenziali utente con password hashate bcrypt
- Configurazione cookie per gestione sessione
- Ruoli utente: admin, controllore, richiedente
- **Mai committare password reali** - file corrente ha solo credenziali di test

**Hashing Password:**
```bash
# Generare nuovo hash password
python utils/hash_password.py
```

## Problemi Comuni e Soluzioni

**Problema: Errore "Rif. PA already exists"**
- Soluzione: Ogni Rif. PA può essere salvato una sola volta nel database. Eliminare vecchi record o usare diverso Rif. PA.

**Problema: Errori validazione campo "Controlli formali"**
- Soluzione: Il campo ora accetta qualsiasi valore o vuoto. Se si ricevono errori, verificare di usare la logica di validazione più recente.

**Problema: Parsing date fallisce**
- Soluzione: Assicurarsi che le date siano in formato GG/MM/AAAA. Verificare date non valide come 30/02/2024.

**Problema: Valori valuta mostrati come 0.0**
- Soluzione: Verificare che `parse_excel_currency()` accetti il formato. Loggare valori per debug.

## Linee Guida Testing

- I test usano pytest con fixture in `conftest.py`
- I test database usano database SQLite temporaneo
- Mockare Streamlit session state quando si testa logica UI
- Puntare ad alta copertura della logica di validazione in `common_utils.py`
- Testare sia scenari dati validi che non validi

## Workflow Git

Branch corrente: `CentriEstivi_def` (nessun branch main configurato)

**Modifiche recenti:**
- Modificati: [app.py](app.py), [pages/01_Gestione_Dati_Controllore.py](pages/01_Gestione_Dati_Controllore.py)
- Modificati: [utils/common_utils.py](utils/common_utils.py), [utils/db.py](utils/db.py)
- Focus: Refactoring, miglioramenti type safety e aggiornamenti gestione controlli formali
