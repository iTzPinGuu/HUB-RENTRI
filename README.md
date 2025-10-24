# RENTRI Manager – Complete Edition (v2.0)

Applicazione desktop moderna per la gestione RENTRI: fornitori con certificato P12, vidimazione FIR, gestione e annullamento FIR, strumenti PDF, e verifica stato API. Interfaccia realizzata con CustomTkinter, operazioni lunghe in background con finestre di progresso e annullamento.

## Requisiti

- Python 3.8 o superiore
- Sistema operativo: Windows, macOS o Linux
- Dipendenze Python (vedi `requirements.txt`): `customtkinter`, `requests`, `PyJWT`, `cryptography`, `PyPDF2`, `Pillow`

Installazione dipendenze:
```bash
pip install -r requirements.txt
```

## Avvio rapido

```bash
python main.py
```

Primi passi:
- Apri la sezione “Fornitori” e aggiungi il fornitore selezionando il certificato `.p12` e la sua password.
- Seleziona il fornitore dalla lista per attivare le sezioni “Blocchi”, “Vidimazione”, “Gestione FIR” e “Stato API”.

## Struttura del progetto

```
.
├─ main.py                         # Entry point
├─ api/
│  └─ rentri_client.py            # Client REST RENTRI con JWT e rate limiting
├─ config/
│  └─ constants.py                # Costanti app, colori, endpoint, rate limit
├─ models/
│  ├─ fornitori_db.py             # Persistenza fornitori (fornitori.json)
│  └─ settings_manager.py         # Gestione impostazioni (settings.json)
├─ ui/
│  ├─ main_window.py              # Finestra principale, sidebar, routing sezioni
│  ├─ components/
│  │  ├─ cards.py                 # DashboardCard, CertificateCard, ClickableLabel
│  │  └─ progress_window.py       # Finestra di progresso con annulla
│  └─ views/
│     ├─ api_status_view.py       # Vista stato API (+/status)
│     ├─ fir_view.py              # Ricerca, paginazione, download e annullamento FIR
│     └─ pdf_views.py             # Strumenti PDF (lettera consegna, unione)
├─ utils/
│  ├─ certificate.py              # Utilità P12: CF, ragione sociale, date, scadenza
│  └─ logger.py                   # Debug logging su stderr
├─ workers/
│  ├─ pdf_workers.py              # Worker PDF
│  └─ vidimation_worker.py        # Worker vidimazione con annulla
├─ requirements.txt
├─ settings.json                  # Impostazioni utente (creato/gestito dall’app)
└─ fornitori.json                 # DB fornitori (creato/gestito dall’app)
```

## Architettura (Mermaid)

Panoramica componenti:
```mermaid
flowchart LR
    A[main.py: main()] --> B[ui/main_window.py: ModernRentriManager]
    B --> C[models/settings_manager.py: SettingsManager]
    B --> D[models/fornitori_db.py: FornitoriDB]
    B --> E[api/rentri_client.py: RentriREST]
    B --> F[workers/vidimation_worker.py: Worker]
    B --> G[workers/pdf_workers.py]
    B --> H[ui/components/* e ui/views/*]
    C --> I[settings.json]
    D --> J[fornitori.json]
    E <--> K[(RENTRI API)]
    F --> L[(Cartella PDF)]
    G --> L
```

Flusso di avvio:
```mermaid
flowchart TD
    A[main.py: main()] --> B{Crea ModernRentriManager}
    B --> C[Carica Settings + Tema]
    B --> D[Inizializza DB Fornitori]
    B --> E[Crea Layout/Sidebar/Main content]
    E --> F{DB ha fornitori?}
    F -- No --> G[Mostra vista Fornitori]
    F -- Sì --> H[Mostra Dashboard]
    H --> I[mainloop()]
```

Fornitori (aggiunta, selezione, aggiornamento cert):
```mermaid
flowchart LR
    A[Nuovo Fornitore] --> B[Seleziona .p12]
    B --> C[Inserisci password]
    C --> D[Estrai CF/Ragione Sociale (utils/certificate.py)]
    D --> E[Salva in FornitoriDB]
    E --> F[Aggiorna lista UI]

    G[Seleziona Fornitore] --> H[Crea RentriREST]
    H --> I[Update UI (nome/CF)]
    I --> J[Carica Blocchi REST.blocchi()]

    K[Aggiorna Certificato] --> L[Seleziona nuovo .p12 + pwd]
    L --> M[Verifica CF coincidente]
    M --> N[Aggiorna DB + Ricarica REST]
```

Vidimazione FIR (con finestra di progresso e annulla):
```mermaid
flowchart TD
    A[Vista Vidimazione] --> B[Selezione Blocco + Quantità + Cartella]
    B --> C{Validazione}
    C -- OK --> D[Avvia Worker (thread)]
    D --> E[ModernProgressWindow (2 progress + Annulla)]
    D --> F[Snapshot formulari iniziali]
    D --> G[POST vidimazione N volte]
    G --> H[Attesa registrazione]
    H --> I[Recupero formulari con paginazione]
    I --> J[Calcolo nuovi FIR]
    J --> K[Download PDF]
    K --> L[Aggiorna progress]
    L --> M{Annullato/Errore?}
    M -- Sì --> N[Chiudi progress + Messaggio]
    M -- No --> O[Completato: riepilogo]
```

Gestione FIR: ricerca, paginazione, download, annullamento:
```mermaid
flowchart TD
    A[Apri Gestione FIR] --> B[REST.blocchi()]
    B --> C[Per blocco: REST.formulari() 100/pg]
    C --> D[Dataset FIR (numero, blocco, prog, data, stato)]
    D --> E[Filtri: testo/blocco/stato]
    E --> F[Paginazione 100/pg]
    F --> G[Azioni]
    G --> H[Download PDF -> REST.dl_pdf()]
    G --> I[Annulla selezionati -> REST.annulla_fir()]
    I --> J[Cache annullati + stato locale]
    J --> K[Aggiorna tabella]
```

Stato API:
```mermaid
flowchart LR
    A[Vista Stato API] --> B[check_status() su BASE_URL]
    A --> C[check_service_statuses() su /status]
    B --> D[Reachable + HTTP + Latenza]
    C --> E[Tabella codici con legenda]
```

Strumenti PDF:
```mermaid
flowchart LR
    A[Lettera di Consegna] --> B[Seleziona PDF]
    B --> C[PDFDeliveryWorker: nomi -> join '|']
    C --> D[Testo copiabile]

    E[Unione FIR] --> F[Seleziona PDF]
    F --> G[PDFMergeWorker]
    G --> H[Duplica pagine 1–2 x2]
    H --> I[Ordina per numero]
    I --> J[Unisci -> merged_formulari.pdf]
```

## Funzionalità principali

- Gestione fornitori multipli con certificato `.p12` e ricerca
- Vidimazione automatizzata con tracking progressi e annulla sicuro
- Gestione FIR con paginazione (100/pg), filtri, download e annullamento
- Dashboard con statistiche e stato certificato (emissione/scadenza)
- Strumenti PDF per lettere di consegna e unione FIR
- Verifica raggiungibilità di `BASE_URL` e stato servizi `/status`
- Tema scuro/chiaro e logo personalizzabile

## Dettagli tecnici

- Autenticazione: JWT firmati con chiave privata ricavata dal P12 (`RS256` o `ES256`).
- Rate limiting: finestra di 5s con massimo richieste configurato; gestite anche risposte `429` con backoff.
- Scarico PDF: risposta JSON con `content` base64; salvataggio su nome file normalizzato.
- Annullamento FIR: PUT su endpoint dedicato, con headers firmati e gestione esiti.

## Configurazione e file dati

- `settings.json`: tema, logo, flag vari. Creato/aggiornato da `models/settings_manager.py`.
- `fornitori.json`: elenco fornitori con path certificato e password. Gestito da `models/fornitori_db.py`.
- `config/constants.py`: `BASE_URL`, `AUDIENCE`, colori, tema di default, rate limit, timeout.

Sicurezza certificato:
- Il percorso del `.p12` e la password sono salvati localmente in `fornitori.json`. Proteggi la macchina/utente e la cartella del progetto.
- Usa credenziali con il minimo dei permessi necessari.

## Risoluzione problemi

- Errore certificato P12: verifica password, formato P12 e presenza del CF nel certificato.
- Nessun blocco/FIR: controlla che il fornitore selezionato sia corretto e la connettività verso `BASE_URL` (sezione “Stato API”).
- `429 Too Many Requests`: attendi alcuni secondi; il client applica già un backoff leggero.
- PDF vuoto o assente: verifica che la risposta JSON contenga `content` e che la cartella di destinazione sia scrivibile.

## Sviluppo e build

Esecuzione in sviluppo:
```bash
pip install -r requirements.txt
python main.py
```

Packaging (PyInstaller):
- È presente `RENTRI_Manager.spec` per creare un eseguibile standalone (Windows). Puoi adattarlo al tuo ambiente PyInstaller.

## Crediti

Creato da Giovanni Pio Familiari – Versione 2.0 (Refactored)

