# WMS Sistema Logging e Recap - Documentazione Claude

## Panoramica
Sistema completo di logging operazioni e recap di conferma implementato per tutte le funzioni del WMS. Ogni operazione viene tracciata con timestamp, dettagli e nome file reale.

## Funzionalità Implementate

### 1. Sistema Logging Completo
-  **Logging Service**: `wms_app/services/logging_service.py`
  - Metodo `log_file_operations()` per operazioni da file senza batch start/end
  - Consolidamento automatico per SKU con nome file reale
  - Tracciamento completo con operation_id condiviso

### 2. Operazioni con Recap Implementate

#### A. Carico/Scarico da File
-  **Endpoint**: `parse-add-stock-file` + `commit-file-operations`
-  **Bug fix**: Consolidamento quantità per SKU duplicati nel file
-  **Logging**: Nome file reale, operazioni consolidate

#### B. Spostamenti da File  
-  **Endpoint**: Esistente con logging aggiunto
-  **Logging**: `SPOSTAMENTO_FILE` con SKU e quantità corretti

#### C. Scarico Container da File
-  **Endpoint**: `parse-unload-container-file` + `commit-unload-container-operations`
-  **Consolidamento**: Automatico per SKU duplicati a TERRA
-  **Recap**: Mostra operazioni consolidate con giacenze prima/dopo

#### D. Ubicazione da Terra da File
-  **Endpoint**: `parse-relocate-from-ground-file` + `commit-relocate-from-ground-operations`
-  **Validazioni**: Ubicazioni inesistenti, giacenze insufficienti, conflitti SKU
-  **Recap**: Mostra movimenti TERRA ’ Ubicazione con controlli preventivi

### 3. Operazioni Manuali con Logging

#### A. Operazioni Inventario
-  **update-stock**: Logging carico/scarico manuale
-  **move-stock**: Logging spostamenti manuali  
-  **unload-container-manual**: Logging scarico container

#### B. Ubicazione da Terra
-  **relocate-from-ground-manual**: Logging spostamenti da TERRA
-  **relocate-from-ground-file**: Logging operazioni da file

## Struttura Database

### Tabella OperationLog
- **operation_id**: ID condiviso per operazioni batch
- **operation_type**: Tipo operazione (CARICO_FILE, SPOSTAMENTO_MANUALE, etc.)
- **operation_category**: MANUAL, FILE, PICKING, SYSTEM
- **product_sku**: SKU prodotto
- **location_from/to**: Ubicazioni origine/destinazione
- **quantity**: Quantità operazione
- **file_name**: Nome file reale (non generico)
- **details**: JSON con dettagli aggiuntivi

## Frontend JavaScript

### Sistema Recap Unificato
- **showRecap()**: Recap generale per carico/scarico
- **showMovementsRecap()**: Recap per spostamenti
- **showUnloadContainerRecap()**: Recap per scarico container
- **showRelocateGroundRecap()**: Recap per ubicazione da terra

### Gestione File Names
- **currentFileName**: Variabile globale per nome file
- **currentRecapFileName**: Nome file mantenuto durante recap
- Passaggio corretto del nome file a tutte le operazioni di commit

## Bug Risolti

### 1. Consolidamento File
**Problema**: File con SKU duplicati creavano operazioni separate invece di consolidare quantità
**Soluzione**: Dizionario `consolidated_operations` che aggrega per (location, sku)

### 2. Logging Batch Noise
**Problema**: Log intasato da entry "BATCH_START" e "BATCH_END"
**Soluzione**: Metodo `log_file_operations()` che logga solo operazioni reali

### 3. Nome File Generico
**Problema**: Tutti i file apparivano come "uploaded_file.txt" nel log
**Soluzione**: Cattura `file.name` nel frontend e passaggio attraverso tutto il flusso

### 4. Consolidamento TERRA
**Problema**: Scarico container da file creava record TERRA multipli
**Soluzione**: Consolidamento automatico a 2 fasi (file ’ SKU consolidati ’ database)

## Comandi di Test

### Linting/Typecheck
Per verificare il codice prima del commit:
```bash
# Aggiungere i comandi specifici del progetto
npm run lint    # o il comando lint del progetto
npm run typecheck # o ruff/mypy se Python
```

## File di Test
- **TEST LOG BILICI.txt**: Scarico container (6x ID, 2x OD, 1x OD_22)
- **TEST LOG CARICO SCARICO.txt**: Carico/scarico generale

## Note Tecniche

### Pattern Consolidamento
1. **Parsing**: Analizza file e accumula quantità per SKU
2. **Validazione**: Controlla esistenza prodotti, ubicazioni, conflitti
3. **Recap**: Mostra anteprima all'utente con possibilità di annullare
4. **Commit**: Esegue operazioni validate con logging completo

### Gestione Errori
- **Errori bloccanti**: SKU inesistenti, ubicazioni non trovate
- **Warning**: Record duplicati, giacenze basse
- **Validazioni**: Conflitti ubicazioni, giacenze insufficienti

## Prossimi Sviluppi Suggeriti
- [ ] Sistema di notifiche per operazioni completate
- [ ] Export logs in CSV/Excel
- [ ] Dashboard analytics sulle operazioni
- [ ] Rollback automatico per operazioni critiche
- [ ] Sistema di backup prima delle operazioni massive

---
*Documentazione aggiornata: 2025-07-30*
*Versione sistema: WMS Logging v1.0*