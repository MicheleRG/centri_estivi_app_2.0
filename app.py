#/app.py
import streamlit as st
import pandas as pd
from utils.db import init_db, log_activity
from utils.common_utils import (
    sanitize_filename_component, convert_df_to_excel_bytes, generate_timestamp_filename,
    parse_excel_currency, validate_rif_pa_format,
    run_detailed_validations
)
import os
from io import StringIO
import csv
from typing import Union, Tuple, List, Any

# Configurazione pagina
st.set_page_config(page_title="Verifica Dati - Centri Estivi", layout="wide", initial_sidebar_state="expanded")

# --- Costanti ---
NOMI_COLONNE_PASTED_DATA = [
    'numero_mandato','data_mandato','comune_titolare_mandato','importo_mandato',
    'comune_centro_estivo','centro_estivo','genitore_cognome_nome','bambino_cognome_nome',
    'codice_fiscale_bambino','valore_contributo_fse','altri_contributi',
    'quota_retta_destinatario','totale_retta','numero_settimane_frequenza',
    'controlli_formali_dichiarati'
]

COLONNE_INTERMEDIE_APP = [
    'rif_pa', 'cup', 'distretto', 'comune_capofila', 'numero_mandato', 'data_mandato',
    'comune_titolare_mandato', 'importo_mandato', 'comune_centro_estivo', 'centro_estivo',
    'genitore_cognome_nome', 'bambino_cognome_nome', 'codice_fiscale_bambino',
    'valore_contributo_fse', 'altri_contributi', 'quota_retta_destinatario', 'totale_retta',
    'numero_settimane_frequenza', 'controlli_formali'
]

COLONNE_ORDINE_SIFER = [
    'Rif. PA', 'Numero progetto', 'ID documento', 'Codice organismo',
    'Voce imputazione', 'Importo imputazione', 'Note imputazione',
    'Data pagamento', 'Tipo pagamento', 'Nr. documento', 'Data documento',
    'Importo documento', 'Fornitore/oggetto documento', 'C.F./P.I documento',
    'Descrizione documento', 'Tipo documento'
]
VERSIONE_TRACCIATO_SIFER = "SIFER_costi_reali_1420_v1.0"

# --- Funzione per generare CSV compatibile SIFER ---
def convert_df_to_sifer_csv_bytes(df_input: pd.DataFrame) -> bytes:
    output = StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL, lineterminator='\n')

    writer.writerow([VERSIONE_TRACCIATO_SIFER])
    
    data_for_sifer_rows = []
    for idx, app_row in df_input.iterrows():
        sifer_row = {}
        
        rif_pa_value = str(app_row.get('rif_pa', 'ND/RER')) 
        sifer_row['Rif. PA'] = rif_pa_value

        num_settimane = app_row.get('numero_settimane_frequenza', 0)
        sifer_row['Numero progetto'] = str(num_settimane)[:11]

        cup_val_input = app_row.get('cup', '')
        distretto_val_input = app_row.get('distretto', '')
        capofila_val_input = app_row.get('comune_capofila', '')
        cup_val_sifer = cup_val_input.strip() if cup_val_input and cup_val_input.strip() else "--"
        distretto_val_sifer = distretto_val_input.strip() if distretto_val_input and distretto_val_input.strip() else "--"
        capofila_val_sifer = capofila_val_input.strip() if capofila_val_input and capofila_val_input.strip() else "--"
        progressivo = idx + 1
        id_documento_str = (
            f"cup: {cup_val_sifer} | distretto: {distretto_val_sifer} | capofila: {capofila_val_sifer} | prog: {progressivo}"
        )
        sifer_row['ID documento'] = id_documento_str[:255]

        sifer_row['Codice organismo'] = str(app_row.get('codice_organismo_sifer', "0"))[:11]
        
        # --- NUOVA LOGICA PER VOCE IMPUTAZIONE ---
        com_ce_val_input = app_row.get('comune_centro_estivo', '')
        ce_val_input = app_row.get('centro_estivo', '')
        com_ce_sifer = com_ce_val_input.strip() if com_ce_val_input and com_ce_val_input.strip() else "ComuneCE ND"
        ce_sifer = ce_val_input.strip() if ce_val_input and ce_val_input.strip() else "CentroEstivo ND"
        voce_imputazione_str = f"com centro est: {com_ce_sifer} | centro est: {ce_sifer}"
        sifer_row['Voce imputazione'] = voce_imputazione_str[:255]
        # --- FINE NUOVA LOGICA VOCE IMPUTAZIONE ---
        
        val_A_fse = app_row.get('valore_contributo_fse', 0.0)
        sifer_row['Importo imputazione'] = f"{float(val_A_fse if pd.notna(val_A_fse) else 0.0):.2f}".replace('.', ',')
        
        val_B_altri_contr = app_row.get('altri_contributi', 0.0)
        val_C_retta_dest = app_row.get('quota_retta_destinatario', 0.0)
        val_D_tot_retta = app_row.get('totale_retta', 0.0)
        note_imputazione_str = (
            f"(B altri contr: {float(val_B_altri_contr if pd.notna(val_B_altri_contr) else 0.0):.2f}".replace('.', ',') + 
            f" | C retta: {float(val_C_retta_dest if pd.notna(val_C_retta_dest) else 0.0):.2f}".replace('.', ',') +
            f" | D Tot retta: {float(val_D_tot_retta if pd.notna(val_D_tot_retta) else 0.0):.2f}".replace('.', ',') + ")"
        )
        sifer_row['Note imputazione'] = note_imputazione_str[:255]
        
        data_pag_val = app_row.get('data_mandato')
        sifer_row['Data pagamento'] = pd.to_datetime(data_pag_val, errors='coerce').strftime('%d/%m/%Y') if pd.notna(data_pag_val) else "01/01/1900"
        
        controlli_formali_val = app_row.get('controlli_formali_dichiarati', '')
        # Gestiamo il caso in cui il valore potrebbe essere vuoto o None
        if pd.isna(controlli_formali_val):
            controlli_formali_val = "dato assente"
        # Log per debugging
        log_activity("SIFER_CSV_CONTROLLI", f"Controllo formale per riga {idx}: {controlli_formali_val}")
        sifer_row['Tipo pagamento'] = str(controlli_formali_val)[:255]
        
        sifer_row['Nr. documento'] = str(app_row.get('numero_mandato', 'ND'))[:255]
        
        data_doc_val = app_row.get('data_mandato') 
        sifer_row['Data documento'] = pd.to_datetime(data_doc_val, errors='coerce').strftime('%d/%m/%Y') if pd.notna(data_doc_val) else "01/01/1900"
        
        importo_doc_val = app_row.get('importo_mandato', 0.0)
        sifer_row['Importo documento'] = f"{float(importo_doc_val if pd.notna(importo_doc_val) else 0.0):.2f}".replace('.', ',')
        
        sifer_row['Fornitore/oggetto documento'] = str(app_row.get('comune_titolare_mandato', 'Fornitore ND'))[:255]
        
        cf_bambino_original = app_row.get('codice_fiscale_bambino', '')
        if not cf_bambino_original or pd.isna(cf_bambino_original) or str(cf_bambino_original).strip() == "":
            cf_bambino_per_sifer = "0000000000000000"
        else:
            cf_bambino_per_sifer = str(cf_bambino_original).upper().strip()
        sifer_row['C.F./P.I documento'] = cf_bambino_per_sifer[:16]
        
        sifer_row['Descrizione documento'] = str(app_row.get('bambino_cognome_nome', 'Bambino ND'))[:255]
        sifer_row['Tipo documento'] = str(app_row.get('genitore_cognome_nome', 'Genitore ND'))[:255]
        
        ordered_sifer_values = [sifer_row.get(col_name, "") for col_name in COLONNE_ORDINE_SIFER]
        data_for_sifer_rows.append(ordered_sifer_values)

    for row_values in data_for_sifer_rows:
        writer.writerow(row_values)

    csv_string = output.getvalue()
    output.close()
    return b'\xef\xbb\xbf' + csv_string.encode('utf-8')

# --- Funzioni UI ---
def render_verifica_dati_page():
    st.title("📝 Verifica Dati - Centri Estivi")
    log_activity("Utente", "PAGE_VIEW", "Verifica e Download")

    st.markdown("Benvenuto! Inserisci dati, incolla spese da Excel (15 colonne), verifica e scarica.")
    st.info(f"**Nota:** I dati verificati qui **NON** vengono salvati automaticamente. Dovrai caricare il file CSV per SIFER (formato: {VERSIONE_TRACCIATO_SIFER}) scaricato nel sistema SIFER, se previsto.")

    st.subheader("1. Dati Generali del Documento")

    if 'rif_pa_error_message' in st.session_state and st.session_state.rif_pa_error_message:
        st.error(st.session_state.rif_pa_error_message)

    with st.expander("Inserisci/Modifica Dati Documento", expanded=not st.session_state.get('metadati_confermati_richiedente', False)):
        with st.form("metadati_documento_form_richiedente"):
            doc_meta = st.session_state.doc_metadati_richiedente
            c1, c2 = st.columns(2)
            rif_pa_input_val_form = c1.text_input("Rif. PA n° (AAAA-NUMERO/RER)", value=doc_meta.get('rif_pa', ''), key="rich_rifpa_input_widget", help="Es. 2016-0001/RER o 2023-1234567/RER. Obbligatorio per SIFER.")
            cup_val_form = c2.text_input("CUP", value=doc_meta.get('cup', ''), key="rich_cup_widget")
            distretto_val_form = c1.text_input("Distretto", value=doc_meta.get('distretto', ''), key="rich_distr_widget")
            comune_capofila_val_form = c2.text_input("Comune/Unione Capofila", value=doc_meta.get('comune_capofila', ''), key="rich_capofila_widget")

            metadati_submitted = st.form_submit_button("✅ Conferma Dati Generali")

            if metadati_submitted:
                st.session_state.doc_metadati_richiedente = {
                    'rif_pa': rif_pa_input_val_form.strip(),
                    'cup': cup_val_form.strip(), 
                    'distretto': distretto_val_form.strip(), 
                    'comune_capofila': comune_capofila_val_form.strip(), 
                }
                is_valid_rif, rif_message = validate_rif_pa_format(rif_pa_input_val_form)
                if is_valid_rif:
                    st.session_state.metadati_confermati_richiedente = True
                    st.session_state.rif_pa_error_message = ""
                    st.success(f"Dati generali confermati. {rif_message}")
                else:
                    st.session_state.metadati_confermati_richiedente = False
                    st.session_state.rif_pa_error_message = rif_message

                log_activity("Utente", "METADATA_SUBMITTED", f"RifPA: {rif_pa_input_val_form}, Valid: {is_valid_rif}")
                st.rerun()

    if not st.session_state.get('metadati_confermati_richiedente', False):
        if not st.session_state.get('rif_pa_error_message'):
             st.warning("☝️ Inserisci e conferma i Dati Generali del Documento (con Rif. PA nel formato corretto) per procedere.")
        st.stop()
    else:
        st.session_state.rif_pa_error_message = ""
        doc_meta_show = st.session_state.doc_metadati_richiedente
        st.markdown(f"**Riferimenti Documento:** Rif. PA: `{doc_meta_show['rif_pa']}`, CUP: `{doc_meta_show.get('cup','N/A')}`, Distr: `{doc_meta_show.get('distretto','N/A')}`, Capofila: `{doc_meta_show.get('comune_capofila','N/A')}`")

    st.markdown("---")
    st.subheader("2. Incolla i Dati delle Spese da Excel")
    pasted_data = st.text_area(
        f"Incolla qui le {len(NOMI_COLONNE_PASTED_DATA)} colonne (solo valori, **NO** intestazioni):",
        height=200, key="pasted_excel_data_richiedente",
        help="Formati data (GG/MM/AAAA) e valute (1.234,56 o 1234.56) accettati."
    )

    results_container = st.container()
    if pasted_data:
        try:
            log_activity("Utente", "PASTE_DATA_PROCESSING", f"Len: {len(pasted_data)} chars")
            df_pasted_raw = pd.read_csv(StringIO(pasted_data), sep='\t', header=None, dtype=str, na_filter=False)

            # Gestione robusta del caso in cui manca l'ultima colonna (controlli formali)
            if df_pasted_raw.shape[1] == len(NOMI_COLONNE_PASTED_DATA) - 1:
                # Aggiungiamo una colonna vuota alla fine
                df_pasted_raw_fixed = pd.DataFrame(df_pasted_raw.values, columns=range(df_pasted_raw.shape[1]))
                df_pasted_raw_fixed[df_pasted_raw.shape[1]] = "dato assente"
                df_pasted_raw = df_pasted_raw_fixed
                st.info("ℹ️ Colonna dei controlli formali non presente nei dati incollati. Aggiunto automaticamente 'dato assente'.")
                log_activity("Utente", "PASTE_DATA_ADDED_MISSING_COLUMN", "Aggiunto 'dato assente' per controlli_formali_dichiarati")
            
            if df_pasted_raw.shape[1] != len(NOMI_COLONNE_PASTED_DATA):
                results_container.error(f"🚨 Errore: Incollate {df_pasted_raw.shape[1]} colonne, attese {len(NOMI_COLONNE_PASTED_DATA)}.")
                st.stop()

            df_pasted_raw.columns = NOMI_COLONNE_PASTED_DATA
            
            # Sostituiamo i valori vuoti nella colonna controlli_formali_dichiarati con "dato assente"
            if 'controlli_formali_dichiarati' in df_pasted_raw.columns:
                # Log dei valori originali per debugging
                control_values = df_pasted_raw['controlli_formali_dichiarati'].tolist()
                log_activity("Utente", "CONTROLLI_FORMALI_VALUES", f"Valori originali: {control_values}")
                
                df_pasted_raw['controlli_formali_dichiarati'] = df_pasted_raw['controlli_formali_dichiarati'].apply(
                    lambda x: "dato assente" if pd.isna(x) or (isinstance(x, str) and not x.strip()) else x
                )

            campi_obbligatori_input = [
                col for col in NOMI_COLONNE_PASTED_DATA if col != 'altri_contributi' and col != 'controlli_formali_dichiarati'
            ]

            righe_con_errori_mancanza = []
            for idx, row in df_pasted_raw.iterrows():
                campi_mancanti_riga = []
                for col_obbligatoria in campi_obbligatori_input:
                    valore_cella = row.get(col_obbligatoria)
                    if pd.isna(valore_cella) or (isinstance(valore_cella, str) and not valore_cella.strip()):
                        campi_mancanti_riga.append(f"'{col_obbligatoria}'")
                
                if campi_mancanti_riga:
                    righe_con_errori_mancanza.append(f"Riga {idx + 1} (dati incollati): Campi obbligatori mancanti -> {', '.join(campi_mancanti_riga)}")

            if righe_con_errori_mancanza:
                error_message_display = "🚨 Errore: Dati obbligatori mancanti nelle righe incollate.\nCorreggere e reincollare.\n\n- " + "\n- ".join(righe_con_errori_mancanza)
                results_container.error(error_message_display)
                log_activity("Utente", "PASTE_DATA_MISSING_FIELDS", f"Errori: {'; '.join(righe_con_errori_mancanza)}")
                st.stop() 

            df_check = df_pasted_raw.copy()
            
            for key, value in st.session_state.doc_metadati_richiedente.items():
                df_check[key] = value

            df_check['codice_fiscale_bambino_pulito'] = df_check['codice_fiscale_bambino'].astype(str).str.upper().str.strip()
            df_check['data_mandato_originale'] = df_check['data_mandato']
            df_check['data_mandato'] = pd.to_datetime(df_check['data_mandato_originale'], errors='coerce', dayfirst=True).dt.date

            currency_cols = ['importo_mandato','valore_contributo_fse','altri_contributi',
                               'quota_retta_destinatario','totale_retta']
            for col in currency_cols:
                df_check[col] = df_check[col].apply(parse_excel_currency)

            df_check['numero_settimane_frequenza'] = df_check.get('numero_settimane_frequenza', pd.Series(dtype='str')).apply(
                lambda x: int(float(str(x).replace(',','.'))) if pd.notna(x) and str(x).strip().replace('.','',1).replace(',','.',1).isdigit() else 0
            )

            df_validation_results, has_blocking_errors_rich = run_detailed_validations(
                df_input=df_check,
                cf_col_clean_name='codice_fiscale_bambino_pulito',
                original_date_col_name='data_mandato_originale',
                parsed_date_col_name='data_mandato',
                declared_formal_controls_col_name='controlli_formali_dichiarati',
                row_offset_val=1
            )

            results_container.subheader("3. Risultati della Verifica Dati (interna app)")
            cols_order_results = ['Riga','Bambino','Esito CF','Esito Data Mandato','Esito D=A+B+C',
                                  'Esito Regole Contr.FSE','Esito Contr.Formali 5%',
                                  "Verifica Max 300€ FSE per Bambino (batch)", 'Errori Bloccanti']
            actual_cols_to_display = [col for col in cols_order_results if col in df_validation_results.columns]
            if not df_validation_results.empty:
                 results_container.dataframe(df_validation_results[actual_cols_to_display], use_container_width=True, hide_index=True)
            else:
                 results_container.info("Nessun risultato di validazione da mostrare.")

            if not has_blocking_errors_rich:
                results_container.success("✅ Verifiche interne OK. Puoi scaricare i dati per SIFER.")
                log_activity("Utente", "VALIDATION_SUCCESS", f"Righe: {len(df_check)}")

                df_for_sifer_export = df_check.copy()
                # Assicuriamoci che i controlli formali vengano passati correttamente
                df_for_sifer_export['controlli_formali'] = df_for_sifer_export['controlli_formali_dichiarati']

                if 'codice_fiscale_bambino_pulito' in df_for_sifer_export.columns:
                    if 'codice_fiscale_bambino' in df_for_sifer_export.columns and 'codice_fiscale_bambino_pulito' != 'codice_fiscale_bambino':
                        df_for_sifer_export.drop(columns=['codice_fiscale_bambino'], inplace=True)
                    df_for_sifer_export.rename(columns={'codice_fiscale_bambino_pulito': 'codice_fiscale_bambino'}, inplace=True)
                
                with results_container.expander("⬇️ 4. Anteprima Dati (formato app) e Download SIFER", expanded=True):
                    # Creiamo una copia delle colonne intermedie e aggiungiamo i controlli formali dichiarati per la visualizzazione
                    cols_to_display = [col for col in COLONNE_INTERMEDIE_APP if col in df_for_sifer_export.columns]
                    
                    # Assicuriamoci che il campo controlli_formali sia incluso nella visualizzazione
                    if 'controlli_formali' not in cols_to_display and 'controlli_formali' in df_for_sifer_export.columns:
                        cols_to_display.append('controlli_formali')
                    
                    df_display_anteprima = df_for_sifer_export[cols_to_display].copy()
                    if 'data_mandato' in df_display_anteprima.columns:
                        df_display_anteprima['data_mandato'] = pd.to_datetime(df_display_anteprima['data_mandato'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
                    
                    # Log dell'anteprima per debugging
                    if 'controlli_formali' in df_display_anteprima.columns:
                        control_values_display = df_display_anteprima['controlli_formali'].tolist()
                        log_activity("Utente", "CONTROLLI_FORMALI_ANTEPRIMA", f"Valori anteprima: {control_values_display}")
                    
                    st.dataframe(df_display_anteprima, use_container_width=True, hide_index=True)

                    rif_pa_s = sanitize_filename_component(st.session_state.doc_metadati_richiedente.get('rif_pa',''))

                    sifer_csv_bytes = convert_df_to_sifer_csv_bytes(df_for_sifer_export)
                    fn_sifer_csv = generate_timestamp_filename(f"SIFER_costi_reali_{VERSIONE_TRACCIATO_SIFER.replace('.', '_')}", rif_pa_s) + ".csv"
                    st.download_button(
                        label="📥 Scarica CSV per SIFER",
                        data=sifer_csv_bytes,
                        file_name=fn_sifer_csv,
                        mime='text/csv',
                        key="rich_dl_sifer_csv"
                    )
                    st.caption(f"File CSV per SIFER (versione tracciato: {VERSIONE_TRACCIATO_SIFER}). Separatore: virgola, Qualificatore testo: doppi apici, No header campi.")

                    excel_bytes = convert_df_to_excel_bytes(df_for_sifer_export[[col for col in COLONNE_INTERMEDIE_APP if col in df_for_sifer_export.columns]])
                    fn_excel = generate_timestamp_filename("DatiVerificati_Excel", rif_pa_s) + ".xlsx"
                    st.download_button("📄 Scarica Excel (Dati Verificati App)", excel_bytes, fn_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="rich_dl_excel")

                with results_container.expander("📊 5. Quadro di Controllo (basato su dati app)", expanded=True):
                    qc_data = {
                        "Voce": ["Tot. costi diretti (A - Contr. FSE)", 
                                 "Tot. quote a carico destinatario (C)"],
                        "Valore (€)": [df_for_sifer_export['valore_contributo_fse'].sum(), 
                                     df_for_sifer_export['quota_retta_destinatario'].sum()]
                    }
                    df_qc = pd.DataFrame(qc_data)
                    df_qc_display = df_qc.copy()
                    df_qc_display["Valore (€)"] = df_qc_display["Valore (€)"].apply(lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    st.dataframe(df_qc_display, hide_index=True, use_container_width=True)

                    qc_csv_bytes = df_qc.to_csv(index=False,sep=';',decimal=',',encoding='utf-8-sig').encode('utf-8-sig')
                    fn_qc_csv = generate_timestamp_filename("QuadroControllo", rif_pa_s, False) + ".csv"
                    st.download_button("📥 Scarica Quadro CSV", qc_csv_bytes, fn_qc_csv, 'text/csv', key="rich_qc_csv")

                    qc_excel_bytes = convert_df_to_excel_bytes(df_qc)
                    fn_qc_excel = generate_timestamp_filename("QuadroControllo_Excel", rif_pa_s, False) + ".xlsx"
                    st.download_button("📄 Scarica Quadro Excel", qc_excel_bytes, fn_qc_excel, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="rich_qc_excel")

            elif df_validation_results.empty and not pasted_data.strip():
                results_container.info("Nessun dato valido incollato.")
            else:
                 results_container.error("🚫 Rilevati errori bloccanti (❌) nelle verifiche interne. Correggere i dati e reincollare.")
                 log_activity("Utente", "VALIDATION_FAILED", "Errori bloccanti rilevati.")

        except pd.errors.EmptyDataError:
             results_container.warning("⚠️ Nessun dato da elaborare. Assicurati di aver incollato correttamente.")
        except ValueError as ve:
             results_container.error(f"🚨 Errore nella conversione dei dati: {ve}. Controlla formati numerici e date.")
             log_activity("Utente", "PARSING_ERROR", str(ve))
        except Exception as e:
             results_container.error(f"🚨 Errore imprevisto durante l'elaborazione: {e}")
             log_activity("Utente", "PROCESSING_ERROR", str(e))
             st.exception(e)

if __name__ == "__main__":
    os.makedirs("database", exist_ok=True, mode=0o755)

    if 'db_initialized' not in st.session_state:
        try:
            init_db()
            st.session_state.db_initialized = True
            log_activity("Sistema", "APP_STARTUP", "Database inizializzato per la sessione.")
        except Exception as e_db:
            st.error(f"🚨 Errore critico durante l'inizializzazione del database: {e_db}")
            log_activity("Sistema", "DB_INIT_ERROR", str(e_db))
            st.stop()

    # Inizializzazione session state
    default_session_keys = {
        'doc_metadati_richiedente': st.session_state.get('doc_metadati_richiedente', {
            'rif_pa': '', 'cup': '', 'distretto': '', 'comune_capofila': '',
            }),
        'metadati_confermati_richiedente': st.session_state.get('metadati_confermati_richiedente', False),
        'rif_pa_error_message': st.session_state.get('rif_pa_error_message', "")
    }
    for key, default_value in default_session_keys.items():
        st.session_state.setdefault(key, default_value)

    # Sidebar informazioni
    st.sidebar.title("🏖️ Centri Estivi RER")
    st.sidebar.info("Applicazione per la gestione e validazione dati spese Centri Estivi")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📄 Pagine disponibili")
    st.sidebar.markdown("- **Verifica Dati**: Valida e scarica CSV SIFER")
    st.sidebar.markdown("- **Carica e Salva**: Carica CSV SIFER e salva in DB")
    st.sidebar.markdown("- **Log Attività**: Visualizza log operazioni")

    # Renderizza la pagina principale
    render_verifica_dati_page()
#/app.py