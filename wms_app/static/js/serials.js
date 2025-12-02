// JavaScript per la gestione seriali prodotto con sistema recap

// Variabili globali
let currentSerialRecapData = null;
let currentSerialFile = null;
let currentHighlightedOrder = null;
let currentSerialFileName = null;

document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    
    // Enhanced Upload per caricamento file seriali
    let serialFileUpload = null;
    if (document.getElementById('serial-file-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per seriali...');
        serialFileUpload = window.createEnhancedUpload('serial-file-upload', {
            acceptedTypes: ['.txt', '.csv'],
            maxFileSize: 10 * 1024 * 1024, // 10MB
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\\n\\nEsempio:\\n1234\\n9788838668001\\nSN001\\n9788838668001\\nSN002\\n5678\\n9788838668002\\nSN100\\n...',
            onFileSelect: function(file) {
                console.log('✅ File seriali selezionato:', file.name);
                syncWithHiddenInput('serial-file-input', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati per seriali:', content.split('\\n').length, 'righe');
                syncWithHiddenInput('serial-file-input', virtualFile);
            }
        });
        
        // Imposta la tab scanner come predefinita attiva
        if (serialFileUpload) {
            serialFileUpload.switchMode('scanner');
        }
    }

    // Utility function per sincronizzazione con input nascosto
    function syncWithHiddenInput(inputId, file) {
        const hiddenInput = document.getElementById(inputId);
        if (hiddenInput) {
            const dt = new DataTransfer();
            dt.items.add(file);
            hiddenInput.files = dt.files;
        }
    }

    // Aggiorna closeSerialUploadOverlay per reset enhanced upload
    const originalCloseFunction = window.closeSerialUploadOverlay || closeSerialUploadOverlay;
    window.closeSerialUploadOverlay = function() {
        if (serialFileUpload) {
            serialFileUpload.reset();
        }
        if (originalCloseFunction) {
            originalCloseFunction();
        } else {
            closeSerialUploadOverlay();
        }
    };

    // ========== MOBILE OPTIMIZATION ==========
    // Inietta badge status mobile nella cella Numero Ordine
    injectMobileOrderStatus();
});

/**
 * MOBILE OPTIMIZATION: Inietta badge status nella cella Numero Ordine su mobile
 */
function injectMobileOrderStatus() {
    if (window.innerWidth <= 768) {
        const rows = document.querySelectorAll('#ordersTable tbody tr');
        rows.forEach(row => {
            const orderNumberCell = row.querySelector('td:nth-child(1)');
            const statusCell = row.querySelector('td:nth-child(2)');

            if (orderNumberCell && statusCell && !orderNumberCell.querySelector('.mobile-status-badge')) {
                const statusBadge = statusCell.querySelector('.status-badge');
                if (statusBadge) {
                    const mobileBadge = statusBadge.cloneNode(true);
                    mobileBadge.classList.add('mobile-status-badge');
                    mobileBadge.style.cssText = 'position: absolute; top: 0.25rem; left: 0.25rem; font-size: 0.6rem;';
                    orderNumberCell.style.position = 'relative';
                    orderNumberCell.style.paddingTop = '2rem';
                    orderNumberCell.insertBefore(mobileBadge, orderNumberCell.firstChild);
                }
            }
        });
    }
}

function setupEventListeners() {
    // Form upload seriali
    const serialUploadForm = document.getElementById('serial-upload-form');
    if (serialUploadForm) {
        serialUploadForm.addEventListener('submit', handleSerialFileUpload);
    }
    
    // Upload form vecchio (da rimuovere gradualmente)
    const oldUploadForm = document.getElementById('uploadForm');
    if (oldUploadForm) {
        oldUploadForm.addEventListener('submit', handleFileUpload);
    }
}

// === SISTEMA OVERLAY UPLOAD ===

function openSerialUploadOverlay() {
    document.getElementById('serial-upload-overlay').style.display = 'flex';
}

function closeSerialUploadOverlay() {
    document.getElementById('serial-upload-overlay').style.display = 'none';
    // Reset form
    document.getElementById('serial-upload-form').reset();
}

function closeSerialRecapOverlay() {
    document.getElementById('serial-recap-overlay').style.display = 'none';
    currentSerialRecapData = null;
    currentSerialFile = null;
    currentSerialFileName = null;
}

// === GESTIONE UPLOAD E PARSING ===

async function handleSerialFileUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('serial-file-input');
    const uploadedBy = document.getElementById('uploaded-by-input').value;
    
    if (!fileInput.files.length) {
        console.log('Nessun file selezionato per seriali.');
        const serialFileUpload = window.enhancedUploads && window.enhancedUploads['serial-file-upload'];
        if (serialFileUpload) {
            serialFileUpload.setStatus('error', '❌ Seleziona un file o inserisci dati scanner');
        }
        return;
    }

    // Mostra status di elaborazione
    const serialFileUpload = window.enhancedUploads && window.enhancedUploads['serial-file-upload'];
    if (serialFileUpload) {
        serialFileUpload.setStatus('processing', '⏳ Analisi file seriali in corso...');
    }
    
    const file = fileInput.files[0];
    currentSerialFile = file;
    currentSerialFileName = file.name;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        // Mostra loading
        const submitBtn = event.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Analizzando...';
        submitBtn.disabled = true;
        
        // Chiamata API per parsing
        const response = await fetch('/serials/parse-file', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
        
        if (response.ok && result.success) {
            // Status di successo
            if (serialFileUpload) {
                serialFileUpload.setStatus('success', '✅ File analizzato correttamente. Controlla il riepilogo.');
            }
            // Chiudi overlay upload e mostra recap
            closeSerialUploadOverlay();
            showSerialRecap(result, uploadedBy);
        } else {
            // Status di errore
            if (serialFileUpload) {
                serialFileUpload.setStatus('error', `❌ Errore nell'analisi del file: ${result.message || 'Errore sconosciuto'}`);
            }
            // Mostra errori nel form
            showParsingErrors(result);
        }
        
    } catch (error) {
        console.error('Errore durante parsing:', error);
        if (serialFileUpload) {
            serialFileUpload.setStatus('error', '❌ Errore di rete durante l\'analisi del file');
        }
        
        const submitBtn = event.target.querySelector('button[type="submit"]');
        submitBtn.textContent = 'Analizza File';
        submitBtn.disabled = false;
    }
}

function showParsingErrors(result) {
    let message = result.message || 'Errore durante il parsing del file';
    
    if (result.errors && result.errors.length > 0) {
        message += '\n\nErrori trovati:\n' + result.errors.join('\n');
    }
    
    alert(message);
}

// === SISTEMA RECAP ===

function showSerialRecap(data, uploadedBy) {
    currentSerialRecapData = data;
    currentSerialRecapData.uploaded_by = uploadedBy;
    currentHighlightedOrder = null; // Reset highlight quando si apre nuovo recap
    
    // DEBUG: Log della struttura dati per diagnostica
    console.log('DEBUG showSerialRecap - orders_summary:', data.orders_summary ? Object.keys(data.orders_summary) : 'missing');
    
    // Aggiorna statistiche
    document.getElementById('serial-recap-total').textContent = data.stats.total || 0;
    document.getElementById('serial-recap-ok').textContent = data.stats.ok || 0;
    document.getElementById('serial-recap-warnings').textContent = data.stats.warnings || 0;
    document.getElementById('serial-recap-errors').textContent = data.stats.errors || 0;
    
    // RECAP INIZIALE ORDINI E REQUISITI
    const recapOrdersList = document.getElementById('serial-recap-orders-list');
    
    if (data.orders_summary) {
        let ordersHtml = '<div class="orders-requirements-recap">';
        ordersHtml += '<div class="orders-horizontal-container" style="display: flex !important; flex-wrap: wrap !important; gap: 15px !important; align-items: flex-start !important; width: 100% !important; max-width: none !important;">';
        
        for (const [orderNumber, summary] of Object.entries(data.orders_summary)) {
            const accordionId = `accordion-${orderNumber}`;
            
            // Calcola statistiche ordine per header usando expected_products e found_skus
            let totalExpected = 0, totalFound = 0, hasProblems = false;
            const expected = summary.expected_products || {};
            const found = summary.found_skus || {};
            
            for (const [sku, expectedQty] of Object.entries(expected)) {
                totalExpected += expectedQty;
                const foundQty = found[sku] || 0;
                totalFound += foundQty;
                if (foundQty !== expectedQty) hasProblems = true;
            }
            
            const problemIcon = hasProblems ? '⚠️' : '✅';
            const problemClass = hasProblems ? 'has-problems' : 'no-problems';
            
            ordersHtml += `<div class="order-requirements-card ${problemClass}" data-order="${orderNumber}" style="flex: 1 1 280px !important; min-width: 280px !important; max-width: 500px !important; margin-bottom: 0 !important;">`;
            
            // Header cliccabile dell'accordion
            ordersHtml += `<div class="order-header accordion-header" data-accordion-id="${accordionId}" data-order="${orderNumber}">`;
            ordersHtml += `<div class="order-info">`;
            ordersHtml += `<h5>${problemIcon} Ordine ${orderNumber}</h5>`;
            ordersHtml += `<span class="customer-name">${summary.customer_name || 'N/A'}</span>`;
            ordersHtml += `<span class="order-stats">${totalFound}/${totalExpected} seriali</span>`;
            ordersHtml += `</div>`;
            ordersHtml += `<div class="accordion-controls">`;
            ordersHtml += `<button class="btn-highlight" data-order-highlight="${orderNumber}" title="Evidenzia seriali di questo ordine">🔍</button>`;
            ordersHtml += `<span class="accordion-arrow">▼</span>`;
            ordersHtml += `</div>`;
            ordersHtml += `</div>`;
            
            // Contenuto accordion (chiuso di default)
            ordersHtml += `<div id="${accordionId}" class="accordion-content" style="display: none;">`;
            if (summary.expected_products && Object.keys(summary.expected_products).length > 0) {
                ordersHtml += '<div class="requirements-table">';
                ordersHtml += '<table class="requirements-mini-table">';
                ordersHtml += '<thead><tr><th>SKU</th><th>Richiesti</th><th>Trovati</th></tr></thead>';
                ordersHtml += '<tbody>';
                
                for (const [sku, expectedQty] of Object.entries(summary.expected_products)) {
                    const foundQty = summary.found_skus ? (summary.found_skus[sku] || 0) : 0;
                    let statusClass;
                    
                    if (foundQty === expectedQty) {
                        statusClass = 'status-perfect';
                    } else if (foundQty < expectedQty) {
                        statusClass = 'status-missing';
                    } else {
                        statusClass = 'status-excess';
                    }
                    
                    ordersHtml += `<tr class="${statusClass}">`;
                    ordersHtml += `<td><strong>${sku}</strong></td>`;
                    ordersHtml += `<td>${expectedQty}</td>`;
                    ordersHtml += `<td>${foundQty}</td>`;
                    ordersHtml += '</tr>';
                }
                
                ordersHtml += '</tbody></table>';
                ordersHtml += '</div>';
            }
            ordersHtml += '</div>'; // close accordion-content
            ordersHtml += '</div>'; // close order-requirements-card
        }
        
        ordersHtml += '</div>'; // close orders-horizontal-container
        ordersHtml += '</div>'; // close orders-requirements-recap
        recapOrdersList.innerHTML = ordersHtml;
        
        // DEBUG: Verifica che l'elemento container sia presente nel DOM
        setTimeout(() => {
            const horizontalContainer = recapOrdersList.querySelector('.orders-horizontal-container');
            console.log('DEBUG - Container orizzontale trovato nel DOM:', horizontalContainer);
            if (horizontalContainer) {
                console.log('DEBUG - Larghezza recapOrdersList:', recapOrdersList.offsetWidth + 'px');
                console.log('DEBUG - Larghezza horizontalContainer:', horizontalContainer.offsetWidth + 'px');
                console.log('DEBUG - Numero figli nel container:', horizontalContainer.children.length);
                
                // Forza larghezza completa del contenitore padre
                recapOrdersList.style.width = '100%';
                
                // Forza lo stile inline se il CSS non funziona - METODO BRUTALE
                horizontalContainer.style.setProperty('display', 'flex', 'important');
                horizontalContainer.style.setProperty('flex-wrap', 'wrap', 'important');
                horizontalContainer.style.setProperty('gap', '15px', 'important');
                horizontalContainer.style.setProperty('align-items', 'flex-start', 'important');
                horizontalContainer.style.setProperty('width', '1081px', 'important');
                horizontalContainer.style.setProperty('max-width', 'none', 'important');
                horizontalContainer.style.setProperty('min-width', '1081px', 'important');
                
                // Forza anche gli stili sui singoli card con setProperty
                const cards = horizontalContainer.querySelectorAll('.order-requirements-card');
                cards.forEach(card => {
                    card.style.setProperty('flex', '1 1 280px', 'important');
                    card.style.setProperty('min-width', '280px', 'important');
                    card.style.setProperty('max-width', '500px', 'important');
                    card.style.setProperty('margin-bottom', '0', 'important');
                });
                
                console.log('DEBUG - Stili forzati applicati su container e', cards.length, 'cards');
            }
        }, 200);
    } else {
        console.log('DEBUG - orders_summary non disponibile, mostrando messaggio di fallback');
        recapOrdersList.innerHTML = '<p>❌ Nessun ordine valido trovato</p>';
    }
    
    // Mostra/nasconde sezioni errori e warning
    const errorsSection = document.getElementById('serial-recap-errors-section');
    const warningsSection = document.getElementById('serial-recap-warnings-section');  
    const errorsList = document.getElementById('serial-recap-errors-list');
    const warningsList = document.getElementById('serial-recap-warnings-list');
    
    // Popola errori
    if (data.errors && data.errors.length > 0) {
        errorsList.innerHTML = data.errors.map(error => 
            `<div class="error-item">${error}</div>`
        ).join('');
        errorsSection.style.display = 'block';
    } else {
        errorsSection.style.display = 'none';
    }
    
    // Popola warning  
    if (data.warnings && data.warnings.length > 0) {
        warningsList.innerHTML = data.warnings.map(warning => 
            `<div class="warning-item">${warning}</div>`
        ).join('');
        warningsSection.style.display = 'block';
    } else {
        warningsSection.style.display = 'none';
    }
    
    // RIMOSSO: Vecchio codice riepilogo ordini - ora gestito nella sezione accordion sopra
    
    // Popola tabella operazioni
    const tableBody = document.getElementById('serial-recap-table-body');
    if (data.recap_items && data.recap_items.length > 0) {
        tableBody.innerHTML = data.recap_items.map(item => {
            // Status icons and classes migliorati
            let statusIcon, statusText, statusClass;
            
            switch(item.status) {
                case 'ok':
                    statusIcon = '✅'; statusText = 'OK'; statusClass = 'status-ok';
                    break;
                case 'missing_order':
                    statusIcon = '📋'; statusText = 'ORDINE MANCANTE'; statusClass = 'status-error';
                    break;
                case 'missing_ean':
                    statusIcon = '🏷️'; statusText = 'EAN MANCANTE'; statusClass = 'status-error';
                    break;
                case 'missing_serial':
                    statusIcon = '🔢'; statusText = 'SERIALE MANCANTE'; statusClass = 'status-error';
                    break;
                case 'missing_context':
                    statusIcon = '❓'; statusText = 'CONTESTO MANCANTE'; statusClass = 'status-error';
                    break;
                case 'wrong_sku':
                    statusIcon = '🚫'; statusText = 'SKU ERRATO'; statusClass = 'status-error';
                    break;
                case 'invalid_ean':
                    statusIcon = '⚠️'; statusText = 'EAN INVALIDO'; statusClass = 'status-warning';
                    break;
                case 'excess_quantity':
                    statusIcon = '📈'; statusText = 'QUANTITÀ ECCESSIVA'; statusClass = 'status-warning';
                    break;
                case 'error':
                    statusIcon = '❌'; statusText = 'ERRORE'; statusClass = 'status-error';
                    break;
                default:
                    statusIcon = '⚠️'; statusText = item.status.toUpperCase(); statusClass = 'status-warning';
            }
            
            // TUTTI I CAMPI SONO SEMPRE EDITABILI per massima flessibilità
            const orderEditable = true;
            const eanEditable = true;
            const serialEditable = true;
            
            return `<tr class="${statusClass}" data-status="${item.status}" data-order-number="${item.order_number}">
                <td>${item.line}</td>
                <td>
                    <input type="text" class="recap-input" value="${item.order_number}" 
                           data-line="${item.line}" data-field="order_number"
                           ${orderEditable ? '' : 'readonly'}
                           placeholder="${orderEditable ? 'Inserisci numero ordine' : ''}">
                </td>
                <td>
                    <input type="text" class="recap-input" value="${item.ean_code}" 
                           data-line="${item.line}" data-field="ean_code"
                           ${eanEditable ? '' : 'readonly'}
                           placeholder="${eanEditable ? 'Inserisci EAN code' : ''}">
                </td>
                <td>
                    <input type="text" class="recap-input" value="${item.serial_number}" 
                           data-line="${item.line}" data-field="serial_number"
                           ${serialEditable ? '' : 'readonly'}
                           placeholder="${serialEditable ? 'Inserisci numero seriale' : ''}">
                </td>
                <td><span class="sku-display">${item.sku}</span></td>
                <td><span class="${statusClass}">${statusIcon} ${statusText}</span></td>
                <td>
                    <div class="recap-actions">
                        ${item.status !== 'ok' ? 
                            `<button class="btn-small btn-primary" onclick="fixSerialOperation(${item.line})" title="Applica correzioni">
                                ✏️ Correggi
                             </button>
                             <button class="btn-small btn-danger" onclick="removeSerialOperation(${item.line})" title="Rimuovi questa riga">
                                🗑️ Rimuovi
                             </button>` : 
                            '<span class="status-ok">✅ Valido</span>'
                        }
                    </div>
                </td>
            </tr>`;
        }).join('');
    } else {
        tableBody.innerHTML = '<tr><td colspan="7">Nessuna operazione trovata</td></tr>';
    }
    
    // Aggiungi event listeners per accordion e highlighting
    setTimeout(() => {
        console.log('DEBUG - Attaching event listeners...');
        console.log('DEBUG - recapOrdersList contenuto:', recapOrdersList.innerHTML.substring(0, 200));
        
        // Cerca gli elementi all'interno del contenitore specifico
        const accordionHeaders = recapOrdersList.querySelectorAll('.accordion-header');
        console.log('DEBUG - Trovati', accordionHeaders.length, 'accordion headers in recapOrdersList');
        
        accordionHeaders.forEach((header, index) => {
            console.log(`DEBUG - Aggiungendo listener a header ${index}:`, header);
            header.addEventListener('click', function() {
                console.log('DEBUG - Click su header:', this);
                const accordionId = this.getAttribute('data-accordion-id');
                console.log('DEBUG - accordionId:', accordionId);
                toggleOrderAccordion(accordionId, this);
            });
        });
        
        // Listener per bottoni highlight
        const highlightBtns = recapOrdersList.querySelectorAll('.btn-highlight');
        console.log('DEBUG - Trovati', highlightBtns.length, 'bottoni highlight in recapOrdersList');
        
        highlightBtns.forEach((btn, index) => {
            console.log(`DEBUG - Aggiungendo listener a bottone ${index}:`, btn);
            btn.addEventListener('click', function(e) {
                console.log('DEBUG - Click su bottone highlight:', this);
                e.stopPropagation();
                const orderNumber = this.getAttribute('data-order-highlight');
                console.log('DEBUG - orderNumber:', orderNumber);
                highlightOrderSerials(orderNumber);
            });
        });
        
        console.log('DEBUG - Event listeners attached completato');
    }, 100);
    
    // Mostra overlay recap
    document.getElementById('serial-recap-overlay').style.display = 'flex';
    
    // Setup pulsante execute
    const executeBtn = document.getElementById('serial-recap-execute-btn');
    const validOperations = data.recap_items.filter(item => item.status === 'ok').length;
    executeBtn.disabled = validOperations === 0;
    executeBtn.textContent = validOperations > 0 ? 
        `✅ Esegui ${validOperations} Operazioni` : 
        '❌ Nessuna Operazione Valida';
}

// === CORREZIONE OPERAZIONI ===

async function fixSerialOperation(line) {
    // Trova item nel recap
    const item = currentSerialRecapData.recap_items.find(item => item.line === line);
    if (!item) return;
    
    // Ottieni valori corretti dagli input
    const orderInput = document.querySelector(`input[data-line="${line}"][data-field="order_number"]`);
    const eanInput = document.querySelector(`input[data-line="${line}"][data-field="ean_code"]`);
    const serialInput = document.querySelector(`input[data-line="${line}"][data-field="serial_number"]`);
    
    const newOrderNumber = orderInput.value.trim();
    const newEanCode = eanInput.value.trim();
    const newSerialNumber = serialInput.value.trim();
    
    // Validazioni specifiche per ogni tipo di errore
    if (!validateSerialOperation(item.status, newOrderNumber, newEanCode, newSerialNumber)) {
        return;
    }
    
    try {
        // Validazione EAN -> SKU in tempo reale se necessario
        let newSku = item.sku;
        if (newEanCode && newEanCode !== item.ean_code) {
            newSku = await validateAndGetSku(newEanCode, newOrderNumber);
            if (!newSku) return; // Validazione fallita
        }
        
        // Aggiorna item
        item.order_number = newOrderNumber;
        item.ean_code = newEanCode;
        item.serial_number = newSerialNumber;
        item.sku = newSku;
        item.status = 'ok'; // Correzione applicata
        
        // Rimuovi errori relativi a questa riga
        currentSerialRecapData.errors = currentSerialRecapData.errors.filter(error => 
            !error.includes(`Riga ${line}:`));
        currentSerialRecapData.warnings = currentSerialRecapData.warnings.filter(warning => 
            !warning.includes(`Riga ${line}:`));
        
        // Aggiorna stats
        updateRecapStats();
        
        // Refresh recap
        showSerialRecap(currentSerialRecapData, currentSerialRecapData.uploaded_by);
        
        // Messaggio di conferma
        showToast(`✅ Riga ${line} corretta con successo`, 'success');
        
    } catch (error) {
        console.error('Errore durante correzione:', error);
        alert('Errore durante la correzione. Riprova.');
    }
}

function validateSerialOperation(status, orderNumber, eanCode, serialNumber) {
    switch(status) {
        case 'missing_order':
            if (!orderNumber) {
                alert('Numero ordine obbligatorio per questo tipo di errore.');
                return false;
            }
            break;
        case 'missing_ean':
            if (!eanCode) {
                alert('EAN code obbligatorio per questo tipo di errore.');
                return false;
            }
            break;
        case 'missing_serial':
            if (!serialNumber) {
                alert('Numero seriale obbligatorio per questo tipo di errore.');
                return false;
            }
            break;
        case 'missing_context':
            if (!orderNumber || !eanCode || !serialNumber) {
                alert('Tutti i campi sono obbligatori per completare il contesto.');
                return false;
            }
            break;
        case 'wrong_sku':
        case 'invalid_ean':
            if (!eanCode) {
                alert('EAN code corretto obbligatorio.');
                return false;
            }
            break;
    }
    return true;
}

async function validateAndGetSku(eanCode, orderNumber) {
    try {
        // Valida EAN tramite API (potremmo aggiungere un endpoint per questo)
        // Per ora, usa validazione semplice dal recap esistente
        
        // Cerca nell'orders_summary se questo EAN è previsto per l'ordine
        const orderSummary = currentSerialRecapData.orders_summary[orderNumber];
        if (orderSummary && orderSummary.expected_products) {
            // Cerca EAN che corrisponde a un SKU atteso
            for (const [sku, qty] of Object.entries(orderSummary.expected_products)) {
                if (sku === eanCode) {
                    return sku; // Assume EAN = SKU per semplicità
                }
            }
        }
        
        // Se non trovato negli attesi, chiedi conferma
        const confirm = window.confirm(
            `EAN '${eanCode}' non è previsto nell'ordine ${orderNumber}. ` +
            `Vuoi procedere comunque? (Sarà marcato come warning)`
        );
        
        if (confirm) {
            return eanCode; // Usa EAN come SKU placeholder
        } else {
            return null; // Cancella operazione
        }
        
    } catch (error) {
        console.error('Errore validazione EAN:', error);
        alert('Errore durante la validazione dell\'EAN.');
        return null;
    }
}

function updateRecapStats() {
    if (!currentSerialRecapData) return;
    
    const okItems = currentSerialRecapData.recap_items.filter(i => i.status === 'ok').length;
    const errorItems = currentSerialRecapData.recap_items.filter(i => 
        ['error', 'missing_order', 'missing_ean', 'missing_serial', 'missing_context', 'wrong_sku'].includes(i.status)
    ).length;
    const warningItems = currentSerialRecapData.recap_items.filter(i => 
        ['invalid_ean', 'excess_quantity', 'warning'].includes(i.status)
    ).length;
    
    currentSerialRecapData.stats = {
        total: currentSerialRecapData.recap_items.length,
        ok: okItems,
        errors: errorItems,
        warnings: warningItems
    };
}

function showToast(message, type = 'info') {
    // Simple toast notification (potrebbero implementare una libreria più completa)
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        padding: 12px 20px; border-radius: 8px; color: white;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        opacity: 0; transition: opacity 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    // Fade in
    setTimeout(() => toast.style.opacity = '1', 10);
    
    // Fade out and remove
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

function removeSerialOperation(line) {
    if (confirm('Sei sicuro di voler rimuovere questa operazione?')) {
        // Rimuovi item dal recap
        currentSerialRecapData.recap_items = currentSerialRecapData.recap_items.filter(item => item.line !== line);
        currentSerialRecapData.errors = currentSerialRecapData.errors.filter(error => !error.includes(`Riga ${line}:`));
        currentSerialRecapData.warnings = currentSerialRecapData.warnings.filter(warning => !warning.includes(`Riga ${line}:`));
        
        // Aggiorna stats
        updateRecapStats();
        
        // Refresh recap
        showSerialRecap(currentSerialRecapData, currentSerialRecapData.uploaded_by);
        showToast(`🗑️ Riga ${line} rimossa`, 'success');
    }
}

function addNewSerialRow() {
    if (!currentSerialRecapData) return;
    
    // Trova il numero di riga più alto
    const maxLine = Math.max(...currentSerialRecapData.recap_items.map(item => item.line), 0);
    const newLine = maxLine + 1;
    
    // Crea nuova riga vuota
    const newItem = {
        line: newLine,
        order_number: '',
        ean_code: '',
        serial_number: '',
        sku: '',
        status: 'missing_context'
    };
    
    currentSerialRecapData.recap_items.push(newItem);
    updateRecapStats();
    
    // Refresh recap
    showSerialRecap(currentSerialRecapData, currentSerialRecapData.uploaded_by);
    showToast(`➕ Nuova riga ${newLine} aggiunta`, 'success');
}

async function revalidateAllOperations() {
    if (!currentSerialRecapData || !currentSerialFileName) {
        alert('Nessun dato da rivalidare.');
        return;
    }
    
    try {
        // Mostra loading
        const revalidateBtn = document.querySelector('.btn-warning');
        const originalText = revalidateBtn.textContent;
        revalidateBtn.textContent = '🔄 Rivalidando...';
        revalidateBtn.disabled = true;
        
        // Costruisci contenuto file dalle righe correnti
        let reconstructedFileContent = '';
        
        // Ordina per numero di riga per ricostruire il file
        const sortedItems = currentSerialRecapData.recap_items
            .sort((a, b) => a.line - b.line);
        
        let currentOrder = '';
        for (const item of sortedItems) {
            // Aggiungi numero ordine se cambiato
            if (item.order_number && item.order_number !== currentOrder) {
                reconstructedFileContent += item.order_number + '\n';
                currentOrder = item.order_number;
            }
            
            // Aggiungi EAN se presente
            if (item.ean_code) {
                reconstructedFileContent += item.ean_code + '\n';
            }
            
            // Aggiungi seriale se presente
            if (item.serial_number) {
                reconstructedFileContent += item.serial_number + '\n';
            }
        }
        
        // Crea FormData per rivalidazione
        const blob = new Blob([reconstructedFileContent], { type: 'text/plain' });
        const formData = new FormData();
        formData.append('file', blob, currentSerialFileName || 'rivalidated_file.txt');
        
        // Chiamata API per re-parsing
        const response = await fetch('/serials/parse-file', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok && result.success !== undefined) {
            // Aggiorna recap con risultati rivalidati
            currentSerialRecapData = result;
            currentSerialRecapData.uploaded_by = currentSerialRecapData.uploaded_by || 'rivalidated_user';
            
            showSerialRecap(currentSerialRecapData, currentSerialRecapData.uploaded_by);
            showToast('✅ Rivalidazione completata con successo', 'success');
        } else {
            showToast('❌ Errore durante rivalidazione: ' + (result.message || 'Errore sconosciuto'), 'error');
        }
        
        // Ripristina tasto
        revalidateBtn.textContent = originalText;
        revalidateBtn.disabled = false;
        
    } catch (error) {
        console.error('Errore rivalidazione:', error);
        showToast('❌ Errore di rete durante rivalidazione', 'error');
        
        // Ripristina tasto
        const revalidateBtn = document.querySelector('.btn-warning');
        revalidateBtn.textContent = '🔄 Rivalidate Tutto';
        revalidateBtn.disabled = false;
    }
}

// === ACCORDION E HIGHLIGHTING ===

function toggleOrderAccordion(accordionId, headerElement) {
    const accordionContent = document.getElementById(accordionId);
    const arrowIcon = headerElement.querySelector('.accordion-arrow');
    
    if (accordionContent) {
        const isExpanded = accordionContent.style.display !== 'none';
        accordionContent.style.display = isExpanded ? 'none' : 'block';
        
        if (arrowIcon) {
            arrowIcon.textContent = isExpanded ? '▶' : '▼';
        }
        
        // Aggiungi classe per animazione
        headerElement.classList.toggle('expanded', !isExpanded);
    }
}

function highlightOrderSerials(orderNumber) {
    // Se l'ordine cliccato è già evidenziato, rimuovi l'evidenziazione
    if (currentHighlightedOrder === orderNumber) {
        // Rimuovi tutti gli highlight
        document.querySelectorAll('.recap-table tbody tr').forEach(row => {
            row.classList.remove('highlighted-order');
        });
        currentHighlightedOrder = null;
        console.log('DEBUG - Highlight rimosso per ordine:', orderNumber);
    } else {
        // Rimuovi tutti gli highlight esistenti
        document.querySelectorAll('.recap-table tbody tr').forEach(row => {
            row.classList.remove('highlighted-order');
        });
        
        // Aggiungi highlight alle righe dell'ordine specifico
        document.querySelectorAll(`.recap-table tbody tr[data-order-number="${orderNumber}"]`).forEach(row => {
            row.classList.add('highlighted-order');
        });
        
        currentHighlightedOrder = orderNumber;
        console.log('DEBUG - Highlight aggiunto per ordine:', orderNumber);
    }
}

function toggleShowOnlyErrors() {
    const toggle = document.getElementById('toggle-errors-only');
    const isShowingOnlyErrors = toggle.classList.contains('active');
    const allRows = document.querySelectorAll('.recap-table tbody tr');
    
    if (isShowingOnlyErrors) {
        // Mostra tutte le righe
        allRows.forEach(row => {
            row.style.display = '';
        });
        toggle.classList.remove('active');
        toggle.textContent = '🔍 Mostra Solo Errori';
    } else {
        // Mostra solo le righe con errori
        allRows.forEach(row => {
            const status = row.classList.contains('status-error') || row.classList.contains('status-warning');
            row.style.display = status ? '' : 'none';
        });
        toggle.classList.add('active');
        toggle.textContent = '📋 Mostra Tutto';
    }
}

// === ESECUZIONE OPERAZIONI ===

async function executeSerialOperations() {
    if (!currentSerialRecapData || !currentSerialFileName) {
        alert('Dati recap non trovati. Riprova il caricamento.');
        return;
    }
    
    const validOperations = currentSerialRecapData.recap_items.filter(item => item.status === 'ok');
    if (validOperations.length === 0) {
        alert('Nessuna operazione valida da eseguire.');
        return;
    }
    
    if (!confirm(`Vuoi eseguire ${validOperations.length} operazioni seriali?`)) {
        return;
    }
    
    try {
        const executeBtn = document.getElementById('serial-recap-execute-btn');
        executeBtn.textContent = 'Esecuzione in corso...';
        executeBtn.disabled = true;
        
        // Prepara richiesta commit
        const commitRequest = {
            file_name: currentSerialFileName,
            recap_items: currentSerialRecapData.recap_items,
            uploaded_by: currentSerialRecapData.uploaded_by || 'file_user'
        };
        
        const response = await fetch('/serials/commit-operations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(commitRequest)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            alert(`✅ Operazioni completate con successo!\n\n${result.message}`);
            closeSerialRecapOverlay();
            
            // Refresh lista ordini dopo qualche secondo
            setTimeout(() => {
                refreshOrdersList();
            }, 1000);
        } else {
            alert(`❌ Errore durante l'esecuzione:\n\n${result.message}`);
        }
        
    } catch (error) {
        console.error('Errore durante esecuzione:', error);
        alert('Errore di rete durante l\'esecuzione delle operazioni.');
    } finally {
        const executeBtn = document.getElementById('serial-recap-execute-btn');
        executeBtn.textContent = '✅ Esegui Operazioni';
        executeBtn.disabled = false;
    }
}

// === FUNZIONI LEGACY (mantenute per compatibilità) ===

async function handleFileUpload(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const resultDiv = document.getElementById('uploadResult');
    
    // Show loading
    showLoading(form);
    resultDiv.style.display = 'none';
    
    try {
        const response = await fetch('/serials/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        hideLoading(form);
        
        console.log('Upload response:', result); // Debug
        
        if (response.ok && result.success) {
            showUploadResult(result, 'success');
            // Refresh orders list after successful upload
            setTimeout(() => {
                refreshOrdersList();
            }, 1000);
        } else {
            showUploadResult(result, 'error');
        }
        
    } catch (error) {
        hideLoading(form);
        showUploadResult({
            success: false,
            message: 'Errore di rete durante il caricamento',
            errors: [error.message]
        }, 'error');
    }
}

function showUploadResult(result, type) {
    const resultDiv = document.getElementById('uploadResult');
    resultDiv.className = `result-container ${type}`;
    
    let html = `<h4>${result.success ? '✅ Upload Completato' : '❌ Errore Upload'}</h4>`;
    html += `<p><strong>Messaggio:</strong> ${result.message || 'Errore sconosciuto'}</p>`;
    
    if (result.total_lines_processed) {
        html += `<p><strong>Righe processate:</strong> ${result.total_lines_processed}</p>`;
    }
    
    if (result.total_serials_found !== undefined) {
        html += `<p><strong>Seriali trovati:</strong> ${result.total_serials_found}</p>`;
    }
    
    if (result.total_orders_found !== undefined) {
        html += `<p><strong>Ordini coinvolti:</strong> ${result.total_orders_found}</p>`;
    }
    
    if (result.upload_batch_id) {
        html += `<p><strong>Batch ID:</strong> <code>${result.upload_batch_id}</code></p>`;
    }
    
    if (result.errors && result.errors.length > 0) {
        html += '<div class="errors-section">';
        html += '<h5>❌ Errori:</h5>';
        html += '<ul>';
        result.errors.forEach(error => {
            html += `<li>${error}</li>`;
        });
        html += '</ul>';
        html += '</div>';
    }
    
    if (result.warnings && result.warnings.length > 0) {
        html += '<div class="warnings-section">';
        html += '<h5>⚠️ Warning:</h5>';
        html += '<ul>';
        result.warnings.forEach(warning => {
            html += `<li>${warning}</li>`;
        });
        html += '</ul>';
        html += '</div>';
    }
    
    resultDiv.innerHTML = html;
    resultDiv.style.display = 'block';
}

// === FUNZIONI UTILITY ===

function showLoading(element) {
    const button = element.querySelector('button[type="submit"]');
    if (button) {
        button.textContent = 'Caricamento...';
        button.disabled = true;
    }
}

function hideLoading(element) {
    const button = element.querySelector('button[type="submit"]');
    if (button) {
        button.textContent = '📤 Carica e Analizza File';
        button.disabled = false;
    }
}

// === ALTRE FUNZIONI ESISTENTI ===

async function refreshOrdersList() {
    try {
        const response = await fetch('/serials/orders');
        const orders = await response.json();
        
        const tableBody = document.querySelector('#ordersTable tbody');
        if (!tableBody) return;
        
        if (orders.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7">Nessun ordine con seriali trovato</td></tr>';
            return;
        }
        
        tableBody.innerHTML = orders.map(order => {
            const statusBadge = getOrderStatusBadge(order.order_status);
            
            // Status di validazione migliorato
            let validationStatus = 'pending';
            let validationText = 'Da Validare';
            
            if (order.validation_summary) {
                validationStatus = order.validation_summary.overall_status;
                validationText = order.validation_summary.overall_status === 'valid' ? 'Valido' :
                               order.validation_summary.overall_status === 'invalid' ? 'Non Valido' : 'Con Problemi';
            }
            
            const validationBadge = getValidationStatusBadge(validationStatus);
            const lastUpdate = order.last_upload_date ? 
                new Date(order.last_upload_date).toLocaleDateString('it-IT') + ' ' + 
                new Date(order.last_upload_date).toLocaleTimeString('it-IT', {hour: '2-digit', minute: '2-digit'}) : 'N/A';
            
            // Conteggio prodotti attesi vs trovati
            const expectedCount = Object.keys(order.expected_products || {}).length;
            const foundCount = Object.keys(order.found_serials || {}).length;
            const totalSerials = Object.values(order.found_serials || {})
                .reduce((sum, serials) => sum + serials.length, 0);
            
            return `
                <tr data-order-status="${order.order_status || 'pending'}">
                    <td><strong>${order.order_number}</strong></td>
                    <td>${statusBadge}</td>
                    <td>${expectedCount}</td>
                    <td>${totalSerials}</td>
                    <td>${validationBadge}</td>
                    <td>${lastUpdate}</td>
                    <td class="actions">
                        <button onclick="viewOrderDetails('${order.order_number}')"
                                class="btn btn-small btn-info" title="Visualizza Dettagli">
                            👁️ Dettagli
                        </button>
                        <button onclick="validateOrder('${order.order_number}')"
                                class="btn btn-small btn-warning mobile-hide" title="Valida Seriali">
                            ✅ Valida
                        </button>
                        <button onclick="generateOrderPDF('${order.order_number}')"
                                class="btn btn-small btn-success mobile-hide" title="Genera PDF">
                            📄 PDF
                        </button>
                        <button onclick="generateOrderCSV('${order.order_number}')"
                                class="btn btn-small btn-primary mobile-hide" title="Esporta CSV">
                            📊 CSV
                        </button>
                        <button onclick="generateOrderExcel('${order.order_number}')"
                                class="btn btn-small btn-info mobile-hide" title="Esporta Excel">
                            📈 Excel
                        </button>
                        <button onclick="deleteOrderSerials('${order.order_number}')"
                                class="btn btn-small btn-danger mobile-hide" title="Elimina Seriali">
                            🗑️ Elimina
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // MOBILE OPTIMIZATION: Inietta badge status dopo rebuild tabella
        injectMobileOrderStatus();

    } catch (error) {
        console.error('Errore nel refresh della lista ordini:', error);
    }
}

function getOrderStatusBadge(status) {
    const statusMap = {
        'pending': { class: 'status-pending', text: 'In Attesa' },
        'processing': { class: 'status-processing', text: 'In Lavorazione' },
        'completed': { class: 'status-completed', text: 'Completato' },
        'cancelled': { class: 'status-cancelled', text: 'Annullato' }
    };
    
    const statusInfo = statusMap[status] || { class: 'status-unknown', text: 'Sconosciuto' };
    return `<span class="status-badge ${statusInfo.class}">${statusInfo.text}</span>`;
}

function getValidationStatusBadge(status) {
    const statusMap = {
        'valid': { class: 'validation-valid', text: '✓ Valido' },
        'invalid': { class: 'validation-invalid', text: '✗ Non Valido' },
        'partial': { class: 'validation-partial', text: '⚠ Parziale' },
        'pending': { class: 'validation-pending', text: '⏳ Da Validare' }
    };
    
    const statusInfo = statusMap[status] || { class: 'validation-unknown', text: 'N/A' };
    return `<span class="status-badge ${statusInfo.class}">${statusInfo.text}</span>`;
}

// === FUNZIONI GESTIONE ORDINI ===

async function viewOrderDetails(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}`);
        const orderData = await response.json();
        
        if (!response.ok) {
            alert(`Errore caricamento dettagli: ${orderData.detail || 'Errore sconosciuto'}`);
            return;
        }
        
        showOrderDetailsModal(orderData);
        
    } catch (error) {
        console.error('Errore nel caricamento dettagli ordine:', error);
        alert('Errore di rete durante il caricamento dei dettagli.');
    }
}

function showOrderDetailsModal(orderData) {
    const modal = document.getElementById('orderDetailsModal');
    const title = document.getElementById('modalOrderTitle');
    const content = document.getElementById('orderDetailsContent');
    
    title.textContent = `Dettagli Seriali - Ordine ${orderData.order_number}`;
    
    let html = '';
    
    // Info ordine
    html += '<div class="order-info">';
    html += `<h4>📋 Informazioni Ordine</h4>`;
    html += `<p><strong>Status:</strong> ${getOrderStatusBadge(orderData.order_status)}</p>`;
    html += `<p><strong>Ultima modifica:</strong> ${orderData.last_upload_date ? new Date(orderData.last_upload_date).toLocaleDateString('it-IT') : 'N/A'}</p>`;
    html += '</div>';
    
    // Prodotti attesi vs trovati
    html += '<div class="products-comparison">';
    html += '<h4>📦 Confronto Prodotti</h4>';
    html += '<table class="comparison-table">';
    html += '<thead><tr><th>SKU</th><th>Attesi</th><th>Trovati</th><th>Status</th></tr></thead>';
    html += '<tbody>';
    
    const allSkus = new Set([...Object.keys(orderData.expected_products), ...Object.keys(orderData.found_serials)]);
    
    for (const sku of allSkus) {
        const expected = orderData.expected_products[sku] || 0;
        const found = orderData.found_serials[sku] ? orderData.found_serials[sku].length : 0;
        const status = expected === found ? 'ok' : (expected > found ? 'missing' : 'excess');
        const statusIcon = status === 'ok' ? '✅' : (status === 'missing' ? '⚠️' : '❌');
        
        html += `<tr class="status-${status}">`;
        html += `<td>${sku}</td>`;
        html += `<td>${expected}</td>`;
        html += `<td>${found}</td>`;
        html += `<td>${statusIcon}</td>`;
        html += '</tr>';
    }
    
    html += '</tbody></table>';
    html += '</div>';
    
    // Seriali per prodotto
    if (Object.keys(orderData.found_serials).length > 0) {
        html += '<div class="serials-detail">';
        html += '<h4>🏷️ Dettaglio Seriali</h4>';
        
        for (const [sku, serials] of Object.entries(orderData.found_serials)) {
            html += `<div class="product-serials">`;
            html += `<h5>${sku} (${serials.length} seriali)</h5>`;
            html += '<div class="serials-list">';
            serials.forEach((serial, index) => {
                html += `<div class="serial-item">${index + 1}. ${serial}</div>`;
            });
            html += '</div>';
            html += '</div>';
        }
        
        html += '</div>';
    }
    
    // Show validation errors if any
    if (orderData.validation_summary && orderData.validation_summary.errors && orderData.validation_summary.errors.length > 0) {
        html += '<div class="validation-errors">';
        html += '<h4>❌ Errori di Validazione</h4>';
        orderData.validation_summary.errors.forEach(error => {
            html += `<div class="error-item">`;
            html += `<span class="error-type">${error.error_type}</span>: ${error.message}`;
            html += `</div>`;
        });
        html += '</div>';
    }

    // MOBILE OPTIMIZATION: Aggiungi pulsanti azione per mobile
    if (window.innerWidth <= 768) {
        html += '<div class="modal-actions" style="margin-top: 1.5rem; display: flex; flex-direction: column; gap: 0.5rem;">';
        html += `<button onclick="validateOrder('${orderData.order_number}')" class="btn btn-warning" style="width: 100%; min-height: 44px;">✅ Valida Seriali</button>`;
        html += `<button onclick="generateOrderPDF('${orderData.order_number}')" class="btn btn-success" style="width: 100%; min-height: 44px;">📄 Genera PDF</button>`;
        html += `<button onclick="generateOrderCSV('${orderData.order_number}')" class="btn btn-primary" style="width: 100%; min-height: 44px;">📊 Esporta CSV</button>`;
        html += `<button onclick="generateOrderExcel('${orderData.order_number}')" class="btn btn-info" style="width: 100%; min-height: 44px;">📈 Esporta Excel</button>`;
        html += `<button onclick="if(confirm('Sei sicuro di voler eliminare i seriali per questo ordine?')) deleteOrderSerials('${orderData.order_number}')" class="btn btn-danger" style="width: 100%; min-height: 44px;">🗑️ Elimina Seriali</button>`;
        html += '</div>';
    }

    content.innerHTML = html;
    modal.style.display = 'flex';
}

async function validateOrder(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/validate`);
        const validationData = await response.json();
        
        if (!response.ok) {
            alert(`Errore validazione: ${validationData.detail || 'Errore sconosciuto'}`);
            return;
        }
        
        showValidationModal(validationData);
        
    } catch (error) {
        console.error('Errore nella validazione ordine:', error);
        alert('Errore di rete durante la validazione.');
    }
}

function showValidationModal(validationData) {
    const modal = document.getElementById('validationModal');
    const title = document.getElementById('validationModalTitle');
    const content = document.getElementById('validationContent');
    
    title.textContent = `Validazione Ordine ${validationData.order_number}`;
    
    let html = '';
    
    // Status generale
    const statusIcon = validationData.overall_status === 'valid' ? '✅' : 
                      validationData.overall_status === 'warning' ? '⚠️' : '❌';
    const statusColor = validationData.overall_status === 'valid' ? '#28a745' : 
                       validationData.overall_status === 'warning' ? '#ffc107' : '#dc3545';
    
    html += '<div class="validation-summary">';
    html += `<h4 style="color: ${statusColor}">${statusIcon} Status: ${validationData.overall_status.toUpperCase()}</h4>`;
    html += `<p><strong>Seriali trovati:</strong> ${validationData.total_serials_found}</p>`;
    html += `<p><strong>Seriali attesi:</strong> ${validationData.total_serials_expected}</p>`;
    html += '</div>';
    
    // Flags di problemi
    if (validationData.has_quantity_mismatch || validationData.has_wrong_products || validationData.has_duplicate_serials) {
        html += '<div class="validation-flags">';
        html += '<h4>🚩 Problemi Rilevati</h4>';
        html += '<ul>';
        if (validationData.has_quantity_mismatch) html += '<li>❌ Quantità non corrispondenti</li>';
        if (validationData.has_wrong_products) html += '<li>❌ Prodotti non previsti nell\'ordine</li>';
        if (validationData.has_duplicate_serials) html += '<li>❌ Seriali duplicati</li>';
        html += '</ul>';
        html += '</div>';
    }
    
    // Errori dettagliati
    if (validationData.errors && validationData.errors.length > 0) {
        html += '<div class="validation-errors">';
        html += '<h4>❌ Errori Dettagliati</h4>';
        validationData.errors.forEach(error => {
            html += `<div class="error-item">`;
            html += `<span class="error-type">${error.error_type}</span>: ${error.message}`;
            if (error.sku) html += ` (SKU: ${error.sku})`;
            html += `</div>`;
        });
        html += '</div>';
    }
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

async function generateOrderPDF(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/pdf`);
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Errore generazione PDF: ${error.detail || 'Errore sconosciuto'}`);
            return;
        }
        
        // Download del file PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seriali_ordine_${orderNumber}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
    } catch (error) {
        console.error('Errore nella generazione PDF:', error);
        alert('Errore di rete durante la generazione del PDF.');
    }
}

async function generateOrderCSV(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/csv`);
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Errore generazione CSV: ${error.detail || 'Errore sconosciuto'}`);
            return;
        }
        
        // Download del file CSV
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seriali_ordine_${orderNumber}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
    } catch (error) {
        console.error('Errore nella generazione CSV:', error);
        alert('Errore di rete durante la generazione del CSV.');
    }
}

async function generateOrderExcel(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/excel`);
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Errore generazione Excel: ${error.detail || 'Errore sconosciuto'}`);
            return;
        }
        
        // Download del file Excel
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seriali_ordine_${orderNumber}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
    } catch (error) {
        console.error('Errore nella generazione Excel:', error);
        alert('Errore di rete durante la generazione del file Excel.');
    }
}

async function exportAllSerialsExcel() {
    try {
        // Mostra loading per operazioni lunghe
        const loadingMsg = document.createElement('div');
        loadingMsg.innerHTML = '⏳ Generazione file Excel in corso...';
        loadingMsg.style.cssText = 'position:fixed;top:20px;right:20px;background:#007bff;color:white;padding:10px;border-radius:5px;z-index:10000;';
        document.body.appendChild(loadingMsg);
        
        const response = await fetch('/serials/export-all-excel');
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Errore generazione Excel: ${error.detail || 'Errore sconosciuto'}`);
            return;
        }
        
        // Download del file Excel
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Il nome file viene determinato dal server
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'tutti_seriali.xlsx';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename=([^;]+)/);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        
        // Rimuovi loading message
        document.body.removeChild(loadingMsg);
        
    } catch (error) {
        console.error('Errore nell\'export Excel globale:', error);
        alert('Errore di rete durante l\'export Excel globale.');
        
        // Rimuovi loading message se presente
        const loadingMsg = document.querySelector('div[style*="position:fixed"]');
        if (loadingMsg) {
            document.body.removeChild(loadingMsg);
        }
    }
}

async function deleteOrderSerials(orderNumber) {
    if (!confirm(`Sei sicuro di voler eliminare tutti i seriali dell'ordine ${orderNumber}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/serials/orders/${orderNumber}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert(`✅ ${result.message}`);
            refreshOrdersList();
        } else {
            alert(`❌ Errore eliminazione: ${result.detail || 'Errore sconosciuto'}`);
        }
        
    } catch (error) {
        console.error('Errore nell\'eliminazione seriali:', error);
        alert('Errore di rete durante l\'eliminazione.');
    }
}

// === FUNZIONI MODAL ===

function closeOrderDetailsModal() {
    document.getElementById('orderDetailsModal').style.display = 'none';
}

function closeValidationModal() {
    document.getElementById('validationModal').style.display = 'none';
}

// === FUNZIONI PER SEZIONI COLLASSABILI (legacy) ===
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const icon = section.previousElementSibling.querySelector('.toggle-icon');
    
    if (section.style.display === 'none' || section.style.display === '') {
        section.style.display = 'block';
        icon.textContent = '▲';
    } else {
        section.style.display = 'none';
        icon.textContent = '▼';
    }
}

function toggleFormatInfo() {
    const formatInfo = document.getElementById('format-info');
    const icon = document.getElementById('format-toggle-icon');
    
    if (formatInfo.style.display === 'none' || formatInfo.style.display === '') {
        formatInfo.style.display = 'block';
        icon.textContent = '▼';
    } else {
        formatInfo.style.display = 'none';
        icon.textContent = '▶';
    }
}

// ========== FUNZIONI PER RICERCA E ORDINAMENTO TABELLA ==========

// Variabili globali per ordinamento
let currentSortColumn = null;
let currentSortDirection = 'asc';

// Funzione per ordinare la tabella
function sortTable(column) {
    const table = document.getElementById('ordersTable');
    const tbody = table.getElementsByTagName('tbody')[0];
    const rows = Array.from(tbody.getElementsByTagName('tr'));
    
    // Cambia direzione se stessa colonna, altrimenti ascendente
    if (currentSortColumn === column) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortDirection = 'asc';
        currentSortColumn = column;
    }
    
    // Ordina le righe
    rows.sort((a, b) => {
        let aVal, bVal;
        
        if (column === 'order_number') {
            aVal = parseInt(a.cells[0].textContent.trim()) || 0;
            bVal = parseInt(b.cells[0].textContent.trim()) || 0;
        } else if (column === 'last_modified') {
            // Estrai la data dalla colonna (formato dd/mm/yyyy hh:mm)
            const aText = a.cells[5].textContent.trim();
            const bText = b.cells[5].textContent.trim();
            aVal = aText === 'N/A' ? new Date(0) : parseDate(aText);
            bVal = bText === 'N/A' ? new Date(0) : parseDate(bText);
        }
        
        if (currentSortDirection === 'asc') {
            return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
            return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
    });
    
    // Ricostruisci la tabella
    rows.forEach(row => tbody.appendChild(row));
    
    // Aggiorna le icone
    updateSortIcons(column, currentSortDirection);
}

// Funzione helper per parsare le date
function parseDate(dateString) {
    // Formato: dd/mm/yyyy hh:mm
    const parts = dateString.split(' ');
    const dateParts = parts[0].split('/');
    const timeParts = parts[1] ? parts[1].split(':') : ['00', '00'];
    
    return new Date(
        parseInt(dateParts[2]), // anno
        parseInt(dateParts[1]) - 1, // mese (0-based)
        parseInt(dateParts[0]), // giorno
        parseInt(timeParts[0]), // ora
        parseInt(timeParts[1]) // minuti
    );
}

// Aggiorna le icone di ordinamento
function updateSortIcons(column, direction) {
    // Reset tutte le icone
    document.getElementById('sort-order-icon').textContent = '↕️';
    document.getElementById('sort-date-icon').textContent = '↕️';
    
    // Imposta l'icona per la colonna attiva
    const icon = direction === 'asc' ? '⬆️' : '⬇️';
    if (column === 'order_number') {
        document.getElementById('sort-order-icon').textContent = icon;
    } else if (column === 'last_modified') {
        document.getElementById('sort-date-icon').textContent = icon;
    }
}

// Funzione per pulire la ricerca
function clearSearch() {
    const searchInput = document.getElementById('search-order');
    searchInput.value = '';
    filterTable('');
}

// Funzione per filtrare la tabella
function filterTable(searchTerm) {
    const table = document.getElementById('ordersTable');
    const tbody = table.getElementsByTagName('tbody')[0];
    const rows = tbody.getElementsByTagName('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const orderNumber = rows[i].cells[0].textContent.toLowerCase();
        const shouldShow = orderNumber.includes(searchTerm.toLowerCase());
        rows[i].style.display = shouldShow ? '' : 'none';
    }
}

// Setup event listeners per ricerca in tempo reale
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-order');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterTable(this.value);
        });
        
        // Enter key per cercare
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                filterTable(this.value);
            }
        });
    }
});

// MOBILE OPTIMIZATION: Resize listener per re-inject badge su cambio orientamento
let resizeTimeout;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(injectMobileOrderStatus, 250);
});

// ========================================
// REALTIME SCANNER - STATE MANAGEMENT
// ========================================

let realtimeScannerState = {
    selectedOrders: [],
    ordersData: {},
    scannedSerials: [],
    scannedSerialsSet: new Set(),
    errors: [],
    productsProgress: {},
    scanStep: 'EAN',           // 'EAN' o 'SERIAL'
    currentEan: null,          // EAN appena scansionato in attesa di seriale
    currentSku: null           // SKU corrispondente all'EAN
};

// ========================================
// MODAL SELEZIONE ORDINI
// ========================================

async function openOrderSelectionModal() {
    try {
        const response = await fetch('/serials/open-orders-for-scanning', {
            credentials: 'include'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Orders data:', data);

        if (!data.orders) {
            throw new Error('Formato risposta non valido: manca "orders"');
        }

        const list = document.getElementById('open-orders-list');
        list.innerHTML = data.orders.map(order => `
            <label class="order-checkbox">
                <input type="checkbox"
                       value="${order.order_number}"
                       data-order='${JSON.stringify(order)}'>
                <div class="order-details">
                    <div class="order-num">#${order.order_number}</div>
                    <div class="order-customer">${order.customer_name}</div>
                    <div class="order-stats">
                        ${order.serials_loaded}/${order.total_expected} seriali
                        ${order.is_complete ? '✅' : '⏳'}
                    </div>
                </div>
            </label>
        `).join('');

        document.getElementById('order-selection-modal').style.display = 'flex';

    } catch (error) {
        console.error('Errore caricamento ordini:', error);
        alert('Errore nel caricamento degli ordini');
    }
}

function closeOrderSelectionModal() {
    document.getElementById('order-selection-modal').style.display = 'none';
}

function startRealtimeScanner() {
    const checkboxes = document.querySelectorAll('#open-orders-list input:checked');

    if (checkboxes.length === 0) {
        alert('⚠️ Seleziona almeno un ordine');
        return;
    }

    realtimeScannerState = {
        selectedOrders: [],
        ordersData: {},
        scannedSerials: [],
        scannedSerialsSet: new Set(),
        errors: [],
        productsProgress: {},
        scanStep: 'EAN',
        currentEan: null,
        currentSku: null
    };

    checkboxes.forEach(cb => {
        const orderData = JSON.parse(cb.dataset.order);
        realtimeScannerState.selectedOrders.push(orderData.order_number);
        realtimeScannerState.ordersData[orderData.order_number] = orderData;

        for (const [sku, info] of Object.entries(orderData.expected_products)) {
            const key = `${orderData.order_number}_${sku}`;
            realtimeScannerState.productsProgress[key] = {
                order_number: orderData.order_number,
                sku: sku,
                product_name: info.product_name,
                expected: info.quantity,
                scanned: info.serials_loaded || 0  // USA i seriali già salvati
            };
        }
    });

    closeOrderSelectionModal();
    document.getElementById('realtime-scanner-overlay').style.display = 'flex';
    renderScannerState();

    // Autofocus con delay per garantire rendering DOM completo
    setTimeout(() => {
        document.getElementById('scanner-barcode-input').focus();
    }, 150);
}

// ========================================
// INPUT SCANNER - VALIDAZIONE REAL-TIME
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    const scannerInput = document.getElementById('scanner-barcode-input');
    if (scannerInput) {
        // Gestione readonly per mobile (come inventory.js)
        scannerInput.addEventListener('keydown', function(e) {
            if (this.readOnly && e.key !== 'Tab') {
                this.readOnly = false;
            }
        });

        // Gestione scansione a due step
        scannerInput.addEventListener('keypress', async function(e) {
            if (e.key === 'Enter') {
                const input = this.value.trim();
                if (!input) return;

                if (realtimeScannerState.scanStep === 'EAN') {
                    // STEP 1: Scansiona EAN
                    await handleEanScan(input);
                } else {
                    // STEP 2: Scansiona SERIALE
                    await handleSerialScan(input);
                }

                this.value = '';
            }
        });
    }
});

// STEP 1: Gestione scansione EAN
async function handleEanScan(eanCode) {
    const feedback = document.getElementById('scan-feedback');
    const input = document.getElementById('scanner-barcode-input');

    if (!eanCode || eanCode.trim() === '') {
        showScanFeedback('❌ Codice vuoto', 'error');
        playErrorBeep();
        return;
    }

    feedback.className = 'scan-feedback loading';
    feedback.textContent = '⏳ Verifica prodotto...';

    try {
        // Converti EAN→SKU tramite backend
        const response = await fetch('/serials/convert-ean-to-sku', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({
                ean_code: eanCode.trim(),
                order_numbers: realtimeScannerState.selectedOrders
            })
        });

        const result = await response.json();

        if (!result.valid) {
            showScanFeedback(`❌ ${result.error}`, 'error');
            playErrorBeep();
            return;
        }

        // Passa allo step SERIAL con SKU convertito
        realtimeScannerState.scanStep = 'SERIAL';
        realtimeScannerState.currentEan = eanCode.trim();
        realtimeScannerState.currentSku = result.sku;

        input.placeholder = 'SCANSIONA SERIALE';
        showScanFeedback(`📦 ${result.sku} - Scansiona SERIALE`, 'success');
        playSuccessBeep();

    } catch (error) {
        console.error('Errore conversione EAN:', error);
        showScanFeedback('❌ Errore verifica prodotto', 'error');
        playErrorBeep();
    }
}

// STEP 2: Gestione scansione SERIALE
async function handleSerialScan(serialNumber) {
    const feedback = document.getElementById('scan-feedback');
    const input = document.getElementById('scanner-barcode-input');

    feedback.className = 'scan-feedback loading';
    feedback.textContent = '⏳ Validazione seriale...';

    // Usa la funzione esistente per validare con il backend
    await validateAndAddSerial(realtimeScannerState.currentEan, serialNumber);

    // Torna allo step EAN
    realtimeScannerState.scanStep = 'EAN';
    realtimeScannerState.currentEan = null;
    realtimeScannerState.currentSku = null;
    input.placeholder = 'SCANSIONA EAN';
}

async function validateAndAddSerial(eanCode, serialNumber) {
    const feedback = document.getElementById('scan-feedback');
    feedback.className = 'scan-feedback loading';
    feedback.textContent = '⏳ Validazione...';

    try {
        const response = await fetch('/serials/validate-serial-realtime', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({
                order_numbers: realtimeScannerState.selectedOrders,
                ean_code: eanCode,
                serial_number: serialNumber,
                scanned_serials: Array.from(realtimeScannerState.scannedSerialsSet),
                scanned_serials_detail: realtimeScannerState.scannedSerials
            })
        });

        const result = await response.json();

        if (result.valid) {
            // Aggiungi alla lista locale (per tracking UI)
            realtimeScannerState.scannedSerials.push({
                ean_code: eanCode,
                serial_number: serialNumber,
                sku: result.sku,
                order_number: result.order_number,
                timestamp: new Date().toISOString()
            });
            realtimeScannerState.scannedSerialsSet.add(serialNumber);

            const key = `${result.order_number}_${result.sku}`;
            if (realtimeScannerState.productsProgress[key]) {
                realtimeScannerState.productsProgress[key].scanned++;
            }

            // Feedback con indicazione salvataggio automatico
            showScanFeedback(`✅ ${result.sku} - ${result.progress} | 💾 Salvato`, 'success');
            playSuccessBeep();

        } else {
            realtimeScannerState.errors.push({
                ean_code: eanCode,
                serial_number: serialNumber,
                error: result.error,
                status: result.status,
                timestamp: new Date().toISOString()
            });

            showScanFeedback(`❌ ${result.error}`, 'error');
            playErrorBeep();
        }

        renderScannerState();

    } catch (error) {
        console.error('Errore validazione:', error);
        showScanFeedback('❌ Errore di rete', 'error');
        playErrorBeep();
    }
}

// ========================================
// RENDER STATE
// ========================================

function renderScannerState() {
    renderSelectedOrders();
    renderProductsTracker();
    renderScannedSerialsLog();
    renderErrorsLog();

    document.getElementById('valid-count').textContent = realtimeScannerState.scannedSerials.length;
    document.getElementById('error-count').textContent = realtimeScannerState.errors.length;
    // commit-count rimosso: non più necessario con auto-save
}

function renderSelectedOrders() {
    const list = document.getElementById('scanner-orders-list');
    list.innerHTML = realtimeScannerState.selectedOrders.map(orderNum => {
        const order = realtimeScannerState.ordersData[orderNum];
        return `
            <div class="selected-order-badge">
                #${orderNum} - ${order.customer_name}
            </div>
        `;
    }).join('');
}

function renderProductsTracker() {
    const list = document.getElementById('products-tracker-list');

    const items = Object.values(realtimeScannerState.productsProgress)
        .sort((a, b) => {
            const aMissing = a.expected - a.scanned;
            const bMissing = b.expected - b.scanned;
            return bMissing - aMissing;
        });

    list.innerHTML = items.map(item => {
        const missing = item.expected - item.scanned;
        const isComplete = missing === 0;
        const percent = (item.scanned / item.expected) * 100;

        return `
            <div class="product-tracker ${isComplete ? 'complete' : 'incomplete'}">
                <div class="product-header">
                    <span class="sku">${item.sku}</span>
                    <span class="name">${item.product_name}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percent}%"></div>
                </div>
                <div class="progress-text">
                    ${item.scanned}/${item.expected}
                    ${isComplete ? '✅' : `<span class="missing">(${missing} mancanti)</span>`}
                </div>
            </div>
        `;
    }).join('');
}

function renderScannedSerialsLog() {
    const log = document.getElementById('scanned-serials-log');
    const recent = realtimeScannerState.scannedSerials.slice(-20).reverse();

    log.innerHTML = recent.map(item => `
        <div class="serial-log-item">
            <span class="serial-num">${item.serial_number}</span>
            <span class="serial-sku">${item.sku}</span>
        </div>
    `).join('');
}

function renderErrorsLog() {
    const section = document.getElementById('errors-section');
    const log = document.getElementById('scan-errors-log');

    if (realtimeScannerState.errors.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    const recent = realtimeScannerState.errors.slice(-20).reverse();

    log.innerHTML = recent.map(item => `
        <div class="error-log-item">
            <div class="error-serial">${item.serial_number}</div>
            <div class="error-msg">${item.error}</div>
        </div>
    `).join('');
}

// ========================================
// COMMIT & CLEAR
// ========================================

async function commitScannedSerials() {
    if (realtimeScannerState.scannedSerials.length === 0) {
        alert('⚠️ Nessun seriale da salvare');
        return;
    }

    const count = realtimeScannerState.scannedSerials.length;
    if (!confirm(`💾 Salvare ${count} seriali?`)) {
        return;
    }

    try {
        const response = await fetch('/serials/commit-realtime-serials', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({
                serials: realtimeScannerState.scannedSerials,
                uploaded_by: document.body.dataset.username || 'operatore'
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ ${result.inserted_count} seriali salvati!`);
            closeRealtimeScanner();
            refreshOrdersList();
        }

    } catch (error) {
        console.error('Errore salvataggio:', error);
        alert('❌ Errore durante il salvataggio');
    }
}

function clearScannedSerials() {
    if (!confirm('🗑️ Cancellare tutti i seriali scansionati?')) {
        return;
    }

    realtimeScannerState.scannedSerials = [];
    realtimeScannerState.scannedSerialsSet.clear();
    realtimeScannerState.errors = [];

    for (const key in realtimeScannerState.productsProgress) {
        realtimeScannerState.productsProgress[key].scanned = 0;
    }

    renderScannerState();
}

function closeRealtimeScanner() {
    document.getElementById('realtime-scanner-overlay').style.display = 'none';
}

// ========================================
// UTILITY
// ========================================

function showScanFeedback(message, type) {
    const feedback = document.getElementById('scan-feedback');
    feedback.className = `scan-feedback ${type}`;
    feedback.textContent = message;

    setTimeout(() => {
        feedback.className = 'scan-feedback';
        feedback.textContent = '';
    }, 3000);
}

function playSuccessBeep() {
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+Pw=');
    audio.play().catch(() => {});
}

function playErrorBeep() {
    const audio = new Audio('data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=');
    audio.play().catch(() => {});
}