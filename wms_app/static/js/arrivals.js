// arrivals.js - Gestione completa feature Arrivi

// ========== STATE MANAGEMENT ==========
let currentArrivalId = null;
let currentRecapData = null;
let scannerState = {
    arrivalId: null,
    arrivalData: null,
    currentEAN: null,
    currentProduct: null,
    isWaitingQuantity: false
};

// Anti-duplicate system per prevenire scansioni accidentali
let scanAntiDuplicate = {
    recentBarcodes: [],      // Sliding window ultimi 5 scan
    lastScanTime: 0,         // Timestamp ultimo scan
    lastBarcodeValue: null,  // Ultimo barcode scansionato
    MIN_SCAN_INTERVAL: 3000  // 3 secondi minimo tra scan dello stesso codice
};

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Arrivals module inizializzato');
    initializeArrivals();
});

function initializeArrivals() {
    // Setup event listeners
    setupFormListeners();

    // Setup mobile scanner listeners
    setupScannerListeners();

    // Load products for SKU autocomplete
    loadProductsForAutocomplete();
}

// ========== DESKTOP: CREATE FORM ==========

function openCreateArrivalOverlay() {
    document.getElementById('create-arrival-overlay').style.display = 'flex';

    // Reset form
    document.getElementById('create-arrival-form').reset();
    document.getElementById('products-container').innerHTML = '';

    // Aggiungi prima riga prodotto
    addProductRow();

    // Set data odierna come default
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('arrival-date').value = today;
}

function closeCreateArrivalOverlay() {
    document.getElementById('create-arrival-overlay').style.display = 'none';
}

function addProductRow() {
    const container = document.getElementById('products-container');
    const rowIndex = container.children.length;

    const rowHtml = `
        <div class="product-row" data-row-index="${rowIndex}">
            <div class="form-group">
                <label>SKU</label>
                <input type="text" class="product-sku" list="product-sku-list" placeholder="Inserisci o seleziona SKU" required autocomplete="off">
            </div>
            <div class="form-group">
                <label>Quantità</label>
                <input type="number" class="product-quantity" value="1" min="1" required>
            </div>
            <button type="button" class="btn-remove" onclick="removeProductRow(${rowIndex})">🗑️</button>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', rowHtml);
}

function removeProductRow(rowIndex) {
    const row = document.querySelector(`.product-row[data-row-index="${rowIndex}"]`);
    if (row) {
        row.remove();
    }

    // Se non ci sono più righe, aggiungine una
    const container = document.getElementById('products-container');
    if (container.children.length === 0) {
        addProductRow();
    }
}

function setupFormListeners() {
    const form = document.getElementById('create-arrival-form');
    if (form) {
        form.addEventListener('submit', handleCreateArrival);
    }
}

async function handleCreateArrival(event) {
    event.preventDefault();

    const arrivalNumber = document.getElementById('arrival-number').value;
    const supplierName = document.getElementById('supplier-name').value;
    const arrivalDate = document.getElementById('arrival-date').value;
    const notes = document.getElementById('arrival-notes').value;

    // Raccolta prodotti
    const productRows = document.querySelectorAll('.product-row');
    const lines = [];

    for (const row of productRows) {
        const sku = row.querySelector('.product-sku').value.trim();
        const qty = parseInt(row.querySelector('.product-quantity').value);

        if (sku && qty > 0) {
            lines.push({
                product_sku: sku,
                expected_quantity: qty
            });
        }
    }

    if (lines.length === 0) {
        alert('❌ Aggiungi almeno un prodotto');
        return;
    }

    // Payload
    const payload = {
        arrival_number: arrivalNumber,
        supplier_name: supplierName,
        arrival_date: arrivalDate ? new Date(arrivalDate).toISOString() : null,
        notes: notes || null,
        lines: lines
    };

    try {
        const response = await fetch('/arrivals/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            showToast(`✅ Documento ${result.arrival_number} creato con successo`, 'success');
            closeCreateArrivalOverlay();

            // Reload page per mostrare nuovo documento
            setTimeout(() => window.location.reload(), 1000);
        } else {
            const error = await response.json();
            showToast(`❌ Errore: ${error.detail || 'Creazione fallita'}`, 'error');
        }
    } catch (error) {
        console.error('Errore creazione documento:', error);
        showToast('❌ Errore di rete', 'error');
    }
}

// ========== DESKTOP: CONFIRM WORKFLOW ==========

async function confirmArrivalDesktop(arrivalId) {
    currentArrivalId = arrivalId;

    try {
        // Carica dettagli documento
        const response = await fetch(`/arrivals/${arrivalId}`);

        if (!response.ok) {
            throw new Error('Documento non trovato');
        }

        const arrival = await response.json();
        currentRecapData = arrival;

        // Mostra recap
        showConfirmRecap(arrival);

    } catch (error) {
        console.error('Errore caricamento documento:', error);
        showToast('❌ Errore caricamento documento', 'error');
    }
}

function showConfirmRecap(arrival) {
    // Popola info documento
    const infoHtml = `
        <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
            <p><strong>Numero Documento:</strong> ${arrival.arrival_number}</p>
            <p><strong>Fornitore:</strong> ${arrival.supplier_name}</p>
            <p><strong>Data Arrivo:</strong> ${new Date(arrival.arrival_date).toLocaleDateString('it-IT')}</p>
            ${arrival.notes ? `<p><strong>Note:</strong> ${arrival.notes}</p>` : ''}
        </div>
    `;

    document.getElementById('arrival-recap-info').innerHTML = infoHtml;

    // Popola tabella prodotti
    const tbody = document.getElementById('arrival-recap-tbody');
    tbody.innerHTML = '';

    arrival.lines.forEach((line, index) => {
        const row = `
            <tr data-sku="${line.product_sku}">
                <td><strong>${line.product_sku}</strong></td>
                <td>${line.product && line.product.description ? line.product.description : '-'}</td>
                <td>
                    <input type="number"
                           class="recap-quantity-input"
                           data-sku="${line.product_sku}"
                           value="${line.expected_quantity}"
                           min="1">
                </td>
                <td>
                    <button class="btn-icon btn-danger" onclick="removeRecapLine('${line.product_sku}')" title="Rimuovi">🗑️</button>
                </td>
            </tr>
        `;
        tbody.insertAdjacentHTML('beforeend', row);
    });

    // Mostra overlay
    document.getElementById('confirm-arrival-overlay').style.display = 'flex';
}

function removeRecapLine(sku) {
    if (confirm(`Rimuovere il prodotto ${sku} dal carico?`)) {
        const row = document.querySelector(`tr[data-sku="${sku}"]`);
        if (row) {
            row.remove();
        }
    }
}

function closeConfirmArrivalOverlay() {
    document.getElementById('confirm-arrival-overlay').style.display = 'none';
    currentArrivalId = null;
    currentRecapData = null;
}

async function finalConfirmArrival() {
    if (!currentArrivalId) {
        showToast('❌ Nessun documento selezionato', 'error');
        return;
    }

    // Raccogli quantità modificate
    const inputs = document.querySelectorAll('.recap-quantity-input');
    const modifiedLines = [];

    inputs.forEach(input => {
        const sku = input.dataset.sku;
        const qty = parseInt(input.value);

        if (qty > 0) {
            modifiedLines.push({
                product_sku: sku,
                expected_quantity: qty
            });
        }
    });

    if (modifiedLines.length === 0) {
        showToast('❌ Nessun prodotto da caricare', 'error');
        return;
    }

    // Conferma finale
    if (!confirm('⚠️ Confermi il carico di tutte le referenze a TERRA? Questa operazione non è reversibile.')) {
        return;
    }

    const payload = {
        arrival_id: currentArrivalId,
        modified_lines: modifiedLines
    };

    try {
        const response = await fetch('/arrivals/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            showToast(`✅ ${result.message}`, 'success');
            closeConfirmArrivalOverlay();

            // Reload page
            setTimeout(() => window.location.reload(), 1500);
        } else {
            const error = await response.json();
            showToast(`❌ Errore: ${error.detail || 'Conferma fallita'}`, 'error');
        }
    } catch (error) {
        console.error('Errore conferma documento:', error);
        showToast('❌ Errore di rete', 'error');
    }
}

// ========== VIEW/EDIT/DELETE ==========

async function viewArrivalDetails(arrivalId) {
    try {
        const response = await fetch(`/arrivals/${arrivalId}`);

        if (!response.ok) {
            throw new Error('Documento non trovato');
        }

        const arrival = await response.json();

        let detailsHtml = `
            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <p><strong>Numero Documento:</strong> ${arrival.arrival_number}</p>
                <p><strong>Fornitore:</strong> ${arrival.supplier_name}</p>
                <p><strong>Data Arrivo:</strong> ${new Date(arrival.arrival_date).toLocaleDateString('it-IT')}</p>
                <p><strong>Stato:</strong> ${arrival.is_completed ? '✅ Completato' : '📦 Precarico'}</p>
                ${arrival.notes ? `<p><strong>Note:</strong> ${arrival.notes}</p>` : ''}
                ${arrival.completed_date ? `<p><strong>Data Completamento:</strong> ${new Date(arrival.completed_date).toLocaleString('it-IT')}</p>` : ''}
            </div>

            <h3>Referenze</h3>
            <table class="recap-table">
                <thead>
                    <tr>
                        <th>SKU</th>
                        <th>Descrizione</th>
                        <th>Quantità Attesa</th>
                        <th>Quantità Ricevuta</th>
                    </tr>
                </thead>
                <tbody>
        `;

        arrival.lines.forEach(line => {
            detailsHtml += `
                <tr>
                    <td><strong>${line.product_sku}</strong></td>
                    <td>${line.product && line.product.description ? line.product.description : '-'}</td>
                    <td>${line.expected_quantity}</td>
                    <td>${line.received_quantity}</td>
                </tr>
            `;
        });

        detailsHtml += `
                </tbody>
            </table>
        `;

        document.getElementById('arrival-details-content').innerHTML = detailsHtml;
        document.getElementById('details-arrival-overlay').style.display = 'flex';

    } catch (error) {
        console.error('Errore caricamento dettagli:', error);
        showToast('❌ Errore caricamento dettagli', 'error');
    }
}

function closeDetailsArrivalOverlay() {
    document.getElementById('details-arrival-overlay').style.display = 'none';
}

async function deleteArrival(arrivalId) {
    if (!confirm('⚠️ Sei sicuro di voler eliminare questo documento? Operazione irreversibile.')) {
        return;
    }

    try {
        const response = await fetch(`/arrivals/${arrivalId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('✅ Documento eliminato', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            const error = await response.json();
            showToast(`❌ Errore: ${error.detail || 'Eliminazione fallita'}`, 'error');
        }
    } catch (error) {
        console.error('Errore eliminazione:', error);
        showToast('❌ Errore di rete', 'error');
    }
}

// ========== MOBILE SCANNER ==========

// ========== ANTI-DUPLICATE SYSTEM ==========

function isDuplicateScan(barcodeValue) {
    const now = Date.now();
    const timeSinceLastScan = now - scanAntiDuplicate.lastScanTime;

    // Check SOLO per stesso codice troppo veloce (< 1 secondo)
    // Questo previene doppi scan accidentali dalla pistola
    if (scanAntiDuplicate.lastBarcodeValue === barcodeValue &&
        timeSinceLastScan < 1000) {  // Solo 1 secondo invece di 3
        console.log('⏳ Scan duplicato troppo veloce (< 1s)');
        return true;
    }

    return false;
}

function updateAntiDuplicateCache(barcodeValue) {
    scanAntiDuplicate.lastBarcodeValue = barcodeValue;
    scanAntiDuplicate.lastScanTime = Date.now();
    scanAntiDuplicate.recentBarcodes.push(barcodeValue);

    // Mantieni solo ultimi 5
    if (scanAntiDuplicate.recentBarcodes.length > 5) {
        scanAntiDuplicate.recentBarcodes.shift();
    }
}

// ========== EXPECTED CODES LIST ==========

function renderExpectedCodesList(lines) {
    const container = document.getElementById('expected-codes-list');
    if (!container) return;

    container.innerHTML = '';

    lines.forEach(line => {
        const itemHtml = `
            <div class="expected-code-item ${line.received_quantity >= line.expected_quantity ? 'completed' : ''}"
                 data-sku="${line.product_sku}">
                <div class="code-header">
                    <div class="code-info">
                        <strong>${line.product_sku}</strong> - ${line.product ? line.product.description || '' : ''}
                    </div>
                    <div class="code-quantity">
                        <input type="number"
                               class="manual-quantity-input"
                               value="${line.received_quantity}"
                               min="0"
                               data-sku="${line.product_sku}"
                               onchange="handleManualQuantityChange('${line.product_sku}', this.value)">
                        <span class="quantity-divider">/</span>
                        <span class="quantity-expected">${line.expected_quantity}</span>
                        <span class="quantity-percentage">(${calculatePercentage(line.received_quantity, line.expected_quantity)}%)</span>
                    </div>
                </div>
                <div class="code-progress-bar">
                    <div class="code-progress-fill"
                         style="width: ${calculatePercentage(line.received_quantity, line.expected_quantity)}%"></div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', itemHtml);
    });
}

function updateExpectedCodeItem(sku, received, expected) {
    const item = document.querySelector(`.expected-code-item[data-sku="${sku}"]`);
    if (!item) return;

    // Aggiorna input
    const input = item.querySelector('.manual-quantity-input');
    if (input) input.value = received;

    // Aggiorna percentuale
    const percentage = calculatePercentage(received, expected);
    const percentageSpan = item.querySelector('.quantity-percentage');
    if (percentageSpan) percentageSpan.textContent = `(${percentage}%)`;

    // Aggiorna progress bar
    const progressFill = item.querySelector('.code-progress-fill');
    if (progressFill) progressFill.style.width = `${percentage}%`;

    // Aggiorna classe completed
    if (received >= expected) {
        item.classList.add('completed');
    } else {
        item.classList.remove('completed');
    }
}

function calculatePercentage(received, expected) {
    if (expected === 0) return 0;
    return Math.round((received / expected) * 100);
}

// ========== AUTO-INCREMENT SCAN ==========

async function handleAutoIncrementScan(ean) {
    // 1. Check duplicate
    if (isDuplicateScan(ean)) {
        const remainingSeconds = Math.ceil((scanAntiDuplicate.MIN_SCAN_INTERVAL - (Date.now() - scanAntiDuplicate.lastScanTime)) / 1000);
        showScannerFeedback(`⏳ Scan troppo veloce, attendi ${remainingSeconds}s...`, 'warning');
        return;
    }

    try {
        // 2. Validate EAN
        const validationResponse = await fetch('/arrivals/validate-ean', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                arrival_id: scannerState.arrivalId,
                ean_code: ean,
                allow_unexpected: true  // NUOVO: permetti creazione nuove righe
            })
        });

        if (!validationResponse.ok) {
            throw new Error('Errore validazione');
        }

        const validationResult = await validationResponse.json();

        if (!validationResult.valid) {
            // Usa alert() per errori critici - visibile anche su palmare
            alert('❌ ERRORE\n\n' + validationResult.message);
            return;
        }

        // 3. Se codice non atteso, chiedi conferma
        if (validationResult.unexpected_code) {
            const confirmed = confirm(
                `⚠️ Codice ${validationResult.product_sku} NON previsto.\nVuoi aggiungerlo al documento?`
            );
            if (!confirmed) {
                showScannerFeedback('Scan annullato', 'warning');
                return;
            }

            // Aggiungi nuova riga alla UI
            const newLine = {
                product_sku: validationResult.product_sku,
                product: { description: validationResult.product_description },
                expected_quantity: 0,
                received_quantity: 0
            };
            scannerState.arrivalData.lines.push(newLine);
            renderExpectedCodesList(scannerState.arrivalData.lines);
        }

        // 4. Update cache anti-duplicate
        updateAntiDuplicateCache(ean);

        // 5. Confirm scan with server (NO optimistic update - wait for server)
        const confirmResponse = await fetch('/arrivals/scan-confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                arrival_id: scannerState.arrivalId,
                product_sku: validationResult.product_sku,
                quantity: 1  // Sempre +1 per auto-increment
            })
        });

        if (!confirmResponse.ok) {
            throw new Error('Errore conferma scan');
        }

        const confirmResult = await confirmResponse.json();

        // 6. Reload documento completo dal server per garantire sync perfetto
        const reloadResponse = await fetch(`/arrivals/${scannerState.arrivalId}`);
        if (reloadResponse.ok) {
            const freshData = await reloadResponse.json();
            scannerState.arrivalData = freshData;

            // Re-render tutta la lista con dati freschi
            renderExpectedCodesList(freshData.lines);
            updateScannerProgress();

            console.log(`✅ Sync completo dopo scan: ${validationResult.product_sku} → ${confirmResult.received_quantity}`);
        } else {
            // Fallback: aggiorna solo visualmente
            const line = scannerState.arrivalData.lines.find(l => l.product_sku === validationResult.product_sku);
            if (line) {
                line.received_quantity = confirmResult.received_quantity;
            }
            updateExpectedCodeItem(
                validationResult.product_sku,
                confirmResult.received_quantity,
                confirmResult.expected_quantity
            );
            updateScannerProgress();
        }

        // 7. Feedback
        showScannerFeedback(`✅ +1 aggiunto (${confirmResult.received_quantity}/${confirmResult.expected_quantity})`, 'success');

    } catch (error) {
        console.error('Errore handleAutoIncrementScan:', error);
        // Usa alert() per errori critici
        alert('❌ ERRORE SCANSIONE\n\n' + error.message);
    }
}

// ========== MANUAL QUANTITY CHANGE ==========

async function handleManualQuantityChange(sku, newQuantity) {
    try {
        const quantity = parseInt(newQuantity);
        if (isNaN(quantity) || quantity < 0) {
            showScannerFeedback('❌ Quantità non valida', 'error');
            return;
        }

        const response = await fetch(`/arrivals/${scannerState.arrivalId}/update-quantity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_sku: sku,
                received_quantity: quantity
            })
        });

        if (!response.ok) {
            throw new Error('Errore aggiornamento');
        }

        const result = await response.json();

        if (result.success) {
            // IMPORTANTE: Ricarica documento dal server per sync perfetto
            const syncResponse = await fetch(`/arrivals/${scannerState.arrivalId}`);
            if (!syncResponse.ok) {
                throw new Error('Errore reload documento');
            }

            const freshData = await syncResponse.json();
            scannerState.arrivalData = freshData;

            // Ri-renderizza la lista con dati freschi
            renderExpectedCodesList(freshData.lines);
            updateScannerProgress();

            console.log(`✅ Sync completo dopo modifica manuale: ${sku} → ${result.received_quantity}`);
            showScannerFeedback('💾 Quantità salvata', 'success');
        }
    } catch (error) {
        console.error('Errore handleManualQuantityChange:', error);
        alert('❌ ERRORE SALVATAGGIO\n\n' + error.message);
    }
}

// ========== FINALIZE ARRIVAL ==========

async function finalizeArrival() {
    try {
        const response = await fetch(`/arrivals/${scannerState.arrivalId}/finalize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: false })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Errore finalizzazione (${response.status}): ${errorText}`);
        }

        const result = await response.json();

        if (result.ask_confirmation && result.discrepancies.length > 0) {
            // Mostra recap discrepanze
            let message = '⚠️ DISCREPANZE RILEVATE:\n\n';
            result.discrepancies.forEach(d => {
                const sign = d.difference > 0 ? '+' : '';
                message += `${d.product_sku}: Ricevuto ${d.received}, Atteso ${d.expected} (${sign}${d.difference})\n`;
            });
            message += '\nProcedere comunque con il carico a TERRA?';

            if (!confirm(message)) {
                return;
            }

            // Richiama con force=true
            const forceResponse = await fetch(`/arrivals/${scannerState.arrivalId}/finalize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force: true })
            });

            if (!forceResponse.ok) {
                throw new Error('Errore finalizzazione forzata');
            }

            const forceResult = await forceResponse.json();

            if (forceResult.success) {
                // Mostra alert di successo con dettagli
                alert(
                    `✅ PRECARICO FINALIZZATO!\n\n` +
                    `Operazioni completate: ${forceResult.operations_logged}\n` +
                    `Totale caricato a TERRA: ${forceResult.total_loaded_to_terra} unità\n\n` +
                    `La pagina si aggiornerà automaticamente.`
                );
                closeMobileScannerOverlay();
                location.reload();
            } else {
                throw new Error(forceResult.message || 'Finalizzazione fallita');
            }
        } else if (result.success) {
            // Mostra alert di successo con dettagli
            alert(
                `✅ PRECARICO FINALIZZATO!\n\n` +
                `Operazioni completate: ${result.operations_logged}\n` +
                `Totale caricato a TERRA: ${result.total_loaded_to_terra} unità\n\n` +
                `La pagina si aggiornerà automaticamente.`
            );
            closeMobileScannerOverlay();
            location.reload();
        } else {
            // Caso inaspettato: success=false ma nessuna conferma richiesta
            throw new Error(result.message || 'Finalizzazione fallita senza motivo specificato');
        }
    } catch (error) {
        console.error('Errore finalizeArrival:', error);
        alert('❌ ERRORE FINALIZZAZIONE\n\n' + error.message);
    }
}

// ========== SCANNER LISTENERS ==========

function setupScannerListeners() {
    const eanInput = document.getElementById('scanner-ean-input');
    if (eanInput) {
        // Gestione readonly per mobile
        eanInput.addEventListener('keydown', function(e) {
            if (this.readOnly && e.key !== 'Tab') {
                this.readOnly = false;
            }
        });

        // Gestione enter per scansione
        eanInput.addEventListener('keypress', async function(e) {
            if (e.key === 'Enter') {
                const input = this.value.trim();
                if (!input) return;

                await handleEANInput(input);
                this.value = '';
            }
        });
    }
}

function openMobileScannerOverlay() {
    document.getElementById('mobile-scanner-overlay').style.display = 'flex';

    // Carica lista documenti disponibili
    loadAvailableArrivals();
}

function closeMobileScannerOverlay() {
    document.getElementById('mobile-scanner-overlay').style.display = 'none';

    // Reset scanner state
    scannerState = {
        arrivalId: null,
        arrivalData: null,
        currentEAN: null,
        currentProduct: null,
        isWaitingQuantity: false
    };
}

function openMobileScannerForArrival(arrivalId) {
    openMobileScannerOverlay();

    // Seleziona automaticamente questo documento
    setTimeout(() => {
        selectArrivalForScanner(arrivalId);
    }, 500);
}

async function loadAvailableArrivals() {
    try {
        const response = await fetch('/arrivals/?include_completed=false');

        if (!response.ok) {
            throw new Error('Errore caricamento documenti');
        }

        const arrivals = await response.json();

        const listContainer = document.getElementById('scanner-arrivals-list');
        listContainer.innerHTML = '';

        if (arrivals.length === 0) {
            listContainer.innerHTML = '<p class="no-data">Nessun documento disponibile per la scansione</p>';
            return;
        }

        arrivals.forEach(arrival => {
            const totalExpected = arrival.lines.reduce((sum, line) => sum + line.expected_quantity, 0);
            const totalReceived = arrival.lines.reduce((sum, line) => sum + line.received_quantity, 0);
            const progress = totalExpected > 0 ? (totalReceived / totalExpected * 100).toFixed(0) : 0;

            const cardHtml = `
                <div class="scanner-arrival-card" data-arrival-id="${arrival.id}" onclick="selectArrivalForScanner(${arrival.id})">
                    <h4>${arrival.arrival_number}</h4>
                    <p><strong>Fornitore:</strong> ${arrival.supplier_name}</p>
                    <p><strong>Referenze:</strong> ${arrival.lines.length}</p>
                    <p><strong>Progress:</strong> ${totalReceived}/${totalExpected} (${progress}%)</p>
                </div>
            `;

            listContainer.insertAdjacentHTML('beforeend', cardHtml);
        });

    } catch (error) {
        console.error('Errore caricamento documenti:', error);
        showToast('❌ Errore caricamento documenti', 'error');
    }
}

async function selectArrivalForScanner(arrivalId) {
    try {
        // Carica dettagli documento
        const response = await fetch(`/arrivals/${arrivalId}`);

        if (!response.ok) {
            throw new Error('Documento non trovato');
        }

        const arrival = await response.json();

        // Aggiorna scanner state
        scannerState.arrivalId = arrivalId;
        scannerState.arrivalData = arrival;

        // Evidenzia card selezionata
        document.querySelectorAll('.scanner-arrival-card').forEach(card => {
            card.classList.remove('selected');
        });
        const selectedCard = document.querySelector(`.scanner-arrival-card[data-arrival-id="${arrivalId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('selected');
        }

        // Mostra area scanner
        document.getElementById('scanner-document-selector').style.display = 'none';
        document.getElementById('scanner-area').style.display = 'block';

        // Popola numero ordine nell'header
        document.getElementById('scanner-header-number').textContent = arrival.arrival_number;

        // Render expected codes list (NUOVO)
        renderExpectedCodesList(arrival.lines);

        // Aggiorna progress
        updateScannerProgress();

        // Focus su input con delay
        setTimeout(() => {
            document.getElementById('scanner-ean-input').focus();
        }, 200);

        showScannerFeedback('✅ Documento selezionato. Scansiona un prodotto.', 'success');

    } catch (error) {
        console.error('Errore selezione documento:', error);
        showToast('❌ Errore selezione documento', 'error');
    }
}

function updateScannerProgress() {
    if (!scannerState.arrivalData) return;

    const totalExpected = scannerState.arrivalData.lines.reduce((sum, line) => sum + line.expected_quantity, 0);
    const totalReceived = scannerState.arrivalData.lines.reduce((sum, line) => sum + line.received_quantity, 0);
    const completedProducts = scannerState.arrivalData.lines.filter(line => line.received_quantity >= line.expected_quantity).length;

    const progress = totalExpected > 0 ? (totalReceived / totalExpected * 100) : 0;

    document.getElementById('scanner-progress-fill').style.width = progress + '%';
    document.getElementById('scanner-progress-text').textContent =
        `${completedProducts}/${scannerState.arrivalData.lines.length} referenze completate (${progress.toFixed(0)}%)`;
}

async function handleEANInput(ean) {
    if (!scannerState.arrivalId) {
        showScannerFeedback('❌ Seleziona prima un documento', 'error');
        return;
    }

    // NUOVO: Auto-increment scan (sostituisce il vecchio two-step)
    await handleAutoIncrementScan(ean);
}

async function validateAndShowProduct(ean) {
    try {
        const response = await fetch('/arrivals/validate-ean', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                arrival_id: scannerState.arrivalId,
                ean_code: ean
            })
        });

        if (!response.ok) {
            throw new Error('Errore validazione EAN');
        }

        const validation = await response.json();

        if (!validation.valid) {
            showScannerFeedback(`❌ ${validation.message}`, 'error');
            return;
        }

        // Mostra prodotto validato
        scannerState.currentEAN = ean;
        scannerState.currentProduct = validation;
        scannerState.isWaitingQuantity = true;

        document.getElementById('scanner-product-sku').textContent = validation.product_sku;
        document.getElementById('scanner-product-description').textContent = validation.product_description;
        document.getElementById('scanner-product-received').textContent = validation.received_quantity;
        document.getElementById('scanner-product-expected').textContent = validation.expected_quantity;
        document.getElementById('scanner-product-percentage').textContent = validation.progress_percentage + '%';

        document.getElementById('scanner-current-product').style.display = 'block';
        document.getElementById('scanner-quantity-input').value = 1;
        document.getElementById('scanner-quantity-input').focus();

        showScannerFeedback(`✅ ${validation.product_sku} - ${validation.received_quantity}/${validation.expected_quantity}`, 'success');

    } catch (error) {
        console.error('Errore validazione EAN:', error);
        showScannerFeedback('❌ Errore validazione EAN', 'error');
    }
}

async function confirmScan() {
    if (!scannerState.currentProduct) {
        showScannerFeedback('❌ Nessun prodotto selezionato', 'error');
        return;
    }

    const quantity = parseInt(document.getElementById('scanner-quantity-input').value);

    if (quantity <= 0) {
        showScannerFeedback('❌ Quantità non valida', 'error');
        return;
    }

    try {
        const response = await fetch('/arrivals/scan-confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                arrival_id: scannerState.arrivalId,
                product_sku: scannerState.currentProduct.product_sku,
                quantity: quantity
            })
        });

        if (!response.ok) {
            throw new Error('Errore conferma scansione');
        }

        const result = await response.json();

        showScannerFeedback(`✅ ${result.message} - ${result.received_quantity}/${result.expected_quantity}`, 'success');

        // Aggiorna dati locali
        const line = scannerState.arrivalData.lines.find(l => l.product_sku === scannerState.currentProduct.product_sku);
        if (line) {
            line.received_quantity = result.received_quantity;
        }

        // Aggiorna progress
        updateScannerProgress();

        // Reset stato
        scannerState.currentProduct = null;
        scannerState.currentEAN = null;
        scannerState.isWaitingQuantity = false;

        document.getElementById('scanner-current-product').style.display = 'none';
        document.getElementById('scanner-ean-input').focus();

        // Se tutto completato, mostra messaggio
        if (result.all_completed) {
            if (confirm('🎉 Tutte le referenze sono state scansionate! Vuoi confermare il documento ora?')) {
                closeMobileScannerOverlay();
                confirmArrivalDesktop(scannerState.arrivalId);
            }
        }

    } catch (error) {
        console.error('Errore conferma scansione:', error);
        showScannerFeedback('❌ Errore conferma scansione', 'error');
    }
}

function showScannerFeedback(message, type) {
    const feedback = document.getElementById('scanner-feedback');
    feedback.textContent = message;
    feedback.className = `scanner-feedback ${type}`;

    setTimeout(() => {
        feedback.className = 'scanner-feedback';
        feedback.textContent = '';
    }, 3000);
}

// ========== UTILITY FUNCTIONS ==========

function toggleCompletedSection() {
    const section = document.getElementById('completed-arrivals-section');
    const icon = document.getElementById('toggle-icon');

    if (section.style.display === 'none') {
        section.style.display = 'block';
        icon.textContent = '▲';
    } else {
        section.style.display = 'none';
        icon.textContent = '▼';
    }
}

// ========== AUTOCOMPLETE PRODOTTI ==========

async function loadProductsForAutocomplete() {
    try {
        const response = await fetch('/products/');
        if (!response.ok) {
            console.error('Errore caricamento prodotti per autocomplete');
            return;
        }

        const products = await response.json();
        const datalist = document.getElementById('product-sku-list');

        if (!datalist) {
            console.error('Datalist product-sku-list non trovato');
            return;
        }

        // Popola datalist con SKU prodotti
        datalist.innerHTML = '';
        products.forEach(product => {
            const option = document.createElement('option');
            option.value = product.sku;
            // Aggiungi descrizione come label per aiutare l'utente
            option.textContent = `${product.sku} - ${product.description || ''}`;
            datalist.appendChild(option);
        });

        console.log(`✅ Caricati ${products.length} prodotti per autocomplete`);
    } catch (error) {
        console.error('Errore caricamento prodotti:', error);
    }
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        padding: 12px 20px; border-radius: 8px; color: white;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : '#17a2b8'};
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        opacity: 0; transition: opacity 0.3s ease;
    `;

    document.body.appendChild(toast);

    setTimeout(() => toast.style.opacity = '1', 10);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

console.log('✅ arrivals.js loaded');
