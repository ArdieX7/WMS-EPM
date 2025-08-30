document.addEventListener('DOMContentLoaded', function() {
    const productSkusDatalist = document.getElementById('product-skus');
    let commitData = null; // Variabile globale per i dati da committare
    let originalInventoryData = [];
    let filteredInventoryData = [];
    let currentSort = { column: null, direction: 'asc' };

    // Inizializza Enhanced Upload Components
    let addStockUpload = null;
    let subtractStockUpload = null;
    let realignStockUpload = null;
    let movementsUpload = null;
    let unloadFileUpload = null;
    let relocateFileUpload = null;

    // Enhanced Upload per tab carico
    if (document.getElementById('add-stock-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per carico inventario...');
        addStockUpload = window.createEnhancedUpload('add-stock-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024, // 10MB
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nUB001\nSKU123\nSKU456_5\nUB002\nSKU789\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload carico:', file.name);
                syncWithHiddenInput('add-stock-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati carico:', content.split('\n').length, 'righe');
                syncWithHiddenInput('add-stock-file', virtualFile);
            }
        });
    }

    // Enhanced Upload per tab scarico
    if (document.getElementById('subtract-stock-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per scarico inventario...');
        subtractStockUpload = window.createEnhancedUpload('subtract-stock-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024,
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nUB001\nSKU123\nSKU456_5\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload scarico:', file.name);
                syncWithHiddenInput('subtract-stock-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati scarico:', content.split('\n').length, 'righe');
                syncWithHiddenInput('subtract-stock-file', virtualFile);
            }
        });
    }

    // Enhanced Upload per tab riallineamento
    if (document.getElementById('realign-stock-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per riallineamento...');
        realignStockUpload = window.createEnhancedUpload('realign-stock-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024,
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nUB001\nSKU123\n8001234567890\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload riallineamento:', file.name);
                syncWithHiddenInput('stock-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati riallineamento:', content.split('\n').length, 'righe');
                syncWithHiddenInput('stock-file', virtualFile);
            }
        });
    }

    // Enhanced Upload per tab spostamenti
    if (document.getElementById('movements-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per spostamenti...');
        movementsUpload = window.createEnhancedUpload('movements-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024,
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nA01\nB01\nB01\nC01\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload spostamenti:', file.name);
                syncWithHiddenInput('movements-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati spostamenti:', content.split('\n').length, 'righe');
                syncWithHiddenInput('movements-file', virtualFile);
            }
        });
    }

    // Enhanced Upload per scarico container
    if (document.getElementById('unload-file-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per scarico container...');
        unloadFileUpload = window.createEnhancedUpload('unload-file-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024,
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nSKU123\nSKU456_5\nSKU789\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload scarico container:', file.name);
                syncWithHiddenInput('unload-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati scarico container:', content.split('\n').length, 'righe');
                syncWithHiddenInput('unload-file', virtualFile);
            }
        });
    }

    // Enhanced Upload per ubicazione da terra
    if (document.getElementById('relocate-file-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per ubicazione da terra...');
        relocateFileUpload = window.createEnhancedUpload('relocate-file-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024,
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nA01P1P1\nSKU123\nSKU456_5\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload ubicazione:', file.name);
                syncWithHiddenInput('relocate-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati ubicazione:', content.split('\n').length, 'righe');
                syncWithHiddenInput('relocate-file', virtualFile);
            }
        });
    }

    // Utility function per sincronizzare con input nascosti
    function syncWithHiddenInput(inputId, file) {
        const hiddenInput = document.getElementById(inputId);
        if (hiddenInput) {
            const dt = new DataTransfer();
            dt.items.add(file);
            hiddenInput.files = dt.files;
        }
    }

    let currentFileName = null; // Nome del file corrente per logging

    // Carica datalist degli SKU per autocompletamento
    async function loadProductSkus() {
        try {
            const productsResponse = await fetch("/products/");
            if (!productsResponse.ok) throw new Error(`Errore HTTP! Stato: ${productsResponse.status}`);
            const products = await productsResponse.json();
            
            productSkusDatalist.innerHTML = '';
            products.forEach(product => {
                const option = document.createElement("option");
                option.value = product.sku;
                productSkusDatalist.appendChild(option);
            });
        } catch (error) {
            console.error("Errore nel caricamento degli SKU per il datalist:", error);
        }
    }

    // Carica i dati originali della tabella
    function loadInventoryData() {
        const tableBody = document.getElementById('inventory-table-body');
        const rows = tableBody.querySelectorAll('tr');
        originalInventoryData = [];
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                originalInventoryData.push({
                    location: cells[0].textContent.trim(),
                    sku: cells[1].textContent.trim(),
                    description: cells[2].textContent.trim(),
                    quantity: parseInt(cells[3].textContent.trim()) || 0,
                    element: row
                });
            }
        });
        filteredInventoryData = [...originalInventoryData];
    }

    // Funzioni per gestione overlay
    window.openOverlay = function(overlayId) {
        document.getElementById(overlayId).style.display = 'block';
    };

    window.closeOverlay = function(overlayId) {
        document.getElementById(overlayId).style.display = 'none';
        
        // Reset enhanced upload components in base all'overlay chiuso
        if (overlayId === 'file-operations-overlay') {
            if (addStockUpload) addStockUpload.reset();
            if (subtractStockUpload) subtractStockUpload.reset();
            if (realignStockUpload) realignStockUpload.reset();
            if (movementsUpload) movementsUpload.reset();
        } else if (overlayId === 'unload-container-overlay') {
            if (unloadFileUpload) unloadFileUpload.reset();
        } else if (overlayId === 'ground-to-location-overlay') {
            if (relocateFileUpload) relocateFileUpload.reset();
        }
    };

    // Chiudi overlay cliccando fuori
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('overlay')) {
            e.target.style.display = 'none';
        }
    });

    // Funzioni per gestione tab nuove sezioni
    window.switchUnloadTab = function(tabId) {
        // Nascondi tutti i tab content
        document.querySelectorAll('#unload-container-overlay .tab-content').forEach(tab => {
            tab.classList.remove('active');
        });
        
        // Rimuovi active da tutti i bottoni
        document.querySelectorAll('#unload-container-overlay .tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Mostra il tab selezionato
        document.getElementById(tabId).classList.add('active');
        
        // Attiva il bottone corrispondente
        event.target.classList.add('active');
    };

    window.switchRelocateTab = function(tabId) {
        // Nascondi tutti i tab content
        document.querySelectorAll('#ground-to-location-overlay .tab-content').forEach(tab => {
            tab.classList.remove('active');
        });
        
        // Rimuovi active da tutti i bottoni
        document.querySelectorAll('#ground-to-location-overlay .tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Mostra il tab selezionato
        document.getElementById(tabId).classList.add('active');
        
        // Attiva il bottone corrispondente
        event.target.classList.add('active');
    };

    // Sistema di ricerca
    function setupSearch() {
        const searchLocation = document.getElementById('search-location');
        const searchSku = document.getElementById('search-sku');

        function performSearch() {
            const locationQuery = searchLocation.value.toLowerCase().trim();
            const skuQuery = searchSku.value.toLowerCase().trim();

            filteredInventoryData = originalInventoryData.filter(item => {
                const locationMatch = !locationQuery || item.location.toLowerCase().includes(locationQuery);
                const skuMatch = !skuQuery || item.sku.toLowerCase().includes(skuQuery);
                return locationMatch && skuMatch;
            });

            renderTable();
        }

        searchLocation.addEventListener('input', performSearch);
        searchSku.addEventListener('input', performSearch);
    }

    // Sistema di ordinamento
    function setupSorting() {
        const sortableHeaders = document.querySelectorAll('.sortable');
        
        sortableHeaders.forEach(header => {
            header.addEventListener('click', function() {
                const column = this.getAttribute('data-column');
                let direction = 'asc';
                
                if (currentSort.column === column && currentSort.direction === 'asc') {
                    direction = 'desc';
                }
                
                sortInventory(column, direction);
                updateSortIndicators(column, direction);
            });
        });
    }

    function sortInventory(column, direction) {
        currentSort = { column, direction };
        
        filteredInventoryData.sort((a, b) => {
            let aValue, bValue;
            
            switch(column) {
                case 'location':
                    aValue = a.location;
                    bValue = b.location;
                    break;
                case 'sku':
                    aValue = a.sku;
                    bValue = b.sku;
                    break;
                case 'description':
                    aValue = a.description;
                    bValue = b.description;
                    break;
                case 'quantity':
                    aValue = a.quantity;
                    bValue = b.quantity;
                    break;
                default:
                    return 0;
            }
            
            if (column === 'quantity') {
                return direction === 'asc' ? aValue - bValue : bValue - aValue;
            } else {
                const comparison = aValue.localeCompare(bValue);
                return direction === 'asc' ? comparison : -comparison;
            }
        });
        
        renderTable();
    }

    function updateSortIndicators(activeColumn, direction) {
        // Reset tutti gli indicatori
        document.querySelectorAll('.sort-arrow').forEach(arrow => {
            arrow.textContent = '';
        });
        
        // Imposta l'indicatore per la colonna attiva
        const activeHeader = document.querySelector(`[data-column="${activeColumn}"] .sort-arrow`);
        if (activeHeader) {
            activeHeader.textContent = direction === 'asc' ? ' ▲' : ' ▼';
        }
    }

    function renderTable() {
        const tableBody = document.getElementById('inventory-table-body');
        tableBody.innerHTML = '';
        
        filteredInventoryData.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.location}</td>
                <td>${item.sku}</td>
                <td>${item.description}</td>
                <td>${item.quantity}</td>
            `;
            tableBody.appendChild(row);
        });
    }

    // Sistema Tab
    window.switchTab = function(tabId) {
        // Nasconde tutti i contenuti tab
        document.querySelectorAll('#file-operations-overlay .tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        // Rimuove active da tutti i pulsanti tab delle operazioni da file
        document.querySelectorAll('#file-operations-overlay .tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Mostra il tab selezionato
        document.getElementById(tabId).classList.add('active');
        
        // Attiva il pulsante del tab corrispondente
        const correspondingBtn = document.querySelector(`#file-operations-overlay .tab-btn[onclick="switchTab('${tabId}')"]`);
        if (correspondingBtn) {
            correspondingBtn.classList.add('active');
        }
    };

    // Funzione separata per i tab delle operazioni manuali
    window.switchManualTab = function(tabId) {
        // Nasconde tutti i contenuti tab delle operazioni manuali
        document.querySelectorAll('#manual-operations-overlay .tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        // Rimuove active da tutti i pulsanti tab delle operazioni manuali
        document.querySelectorAll('#manual-operations-overlay .tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Mostra il contenuto tab selezionato
        document.getElementById(tabId).classList.add('active');
        
        // Attiva il pulsante del tab corrispondente
        const correspondingBtn = document.querySelector(`#manual-operations-overlay .tab-btn[onclick="switchManualTab('${tabId}')"]`);
        if (correspondingBtn) {
            correspondingBtn.classList.add('active');
        }
    };

    // Funzione reset ordinamento
    function setupResetButton() {
        const resetBtn = document.getElementById('reset-sort-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                // Reset ordinamento
                currentSort = { column: null, direction: 'asc' };
                
                // Reset indicatori di ordinamento
                document.querySelectorAll('.sort-arrow').forEach(arrow => {
                    arrow.textContent = '';
                });
                
                // Reset filtri
                document.getElementById('search-location').value = '';
                document.getElementById('search-sku').value = '';
                
                // Ripristina dati originali
                filteredInventoryData = [...originalInventoryData];
                renderTable();
            });
        }
    }

    // Inizializza tutto
    loadInventoryData();
    setupSearch();
    setupSorting();
    setupResetButton();

    // --- Funzione per popolare la datalist degli SKU ---
    function fetchAndPopulateDatalist(query) {
        if (query.length > 1) {
            fetch(`/products/search?query=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    productSkusDatalist.innerHTML = '';
                    data.forEach(product => {
                        const option = document.createElement('option');
                        option.value = product.sku;
                        productSkusDatalist.appendChild(option);
                    });
                });
        } else {
            productSkusDatalist.innerHTML = '';
        }
    }

    // --- Event Listener per i campi di input SKU ---
    const skuInputs = ['product-sku', 'move-product-sku', 'add-product-sku', 'subtract-product-sku'];
    skuInputs.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('input', function() {
                fetchAndPopulateDatalist(this.value);
            });
        }
    });

    // --- Gestione Form Operazioni Manuali (Nuovi Tab) ---
    
    // Form Carico Manuale
    const addStockManualForm = document.getElementById('add-stock-manual-form');
    if (addStockManualForm) {
        addStockManualForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per add-stock-manual-form');
            const sku = document.getElementById('add-product-sku').value;
            const location = document.getElementById('add-location').value.toUpperCase();
            const quantity = document.getElementById('add-quantity').value;

            console.log(`Invio richiesta a /inventory/update-stock per CARICO SKU: ${sku}, Ubicazione: ${location}, Quantità: +${quantity}`);
            fetch('/inventory/update-stock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_sku: sku, location_name: location, quantity: parseInt(quantity) })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                } else {
                    alert(data.message);
                    closeOverlay('manual-operations-overlay');
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Errore nella fetch per add-stock-manual:', error);
                alert('Si è verificato un errore durante il carico manuale.');
            });
        });
    }

    // Form Scarico Manuale  
    const subtractStockManualForm = document.getElementById('subtract-stock-manual-form');
    if (subtractStockManualForm) {
        subtractStockManualForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per subtract-stock-manual-form');
            const sku = document.getElementById('subtract-product-sku').value;
            const location = document.getElementById('subtract-location').value.toUpperCase();
            const quantity = document.getElementById('subtract-quantity').value;

            console.log(`Invio richiesta a /inventory/update-stock per SCARICO SKU: ${sku}, Ubicazione: ${location}, Quantità: -${quantity}`);
            fetch('/inventory/update-stock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_sku: sku, location_name: location, quantity: -parseInt(quantity) })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                } else {
                    alert(data.message);
                    closeOverlay('manual-operations-overlay');
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Errore nella fetch per subtract-stock-manual:', error);
                alert('Si è verificato un errore durante lo scarico manuale.');
            });
        });
    }

    // Form Spostamento Manuale
    const moveStockManualForm = document.getElementById('move-stock-manual-form');
    if (moveStockManualForm) {
        moveStockManualForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per move-stock-manual-form');
            const sku = document.getElementById('move-product-sku').value;
            const fromLocation = document.getElementById('from-location').value.toUpperCase();
            const toLocation = document.getElementById('to-location').value.toUpperCase();
            const quantity = document.getElementById('move-quantity').value;

            console.log(`Invio richiesta a /inventory/move-stock per SKU: ${sku}, Da: ${fromLocation}, A: ${toLocation}, Quantità: ${quantity}`);
            fetch('/inventory/move-stock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_sku: sku, from_location: fromLocation, to_location: toLocation, quantity: parseInt(quantity) })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                } else {
                    alert(data.message);
                    closeOverlay('manual-operations-overlay');
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Errore nella fetch per move-stock-manual:', error);
                alert('Si è verificato un errore durante lo spostamento manuale.');
            });
        });
    }

    // --- Gestione Form per Carico da File con Recap (Enhanced Upload) ---
    const addStockForm = document.getElementById('add-stock-form');
    if (addStockForm) {
        addStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per add-stock-form');
            
            const fileInput = document.getElementById('add-stock-file');
            const file = fileInput.files[0];
            
            if (!file) {
                console.log('Nessun file selezionato.');
                if (addStockUpload) {
                    addStockUpload.setStatus('error', '❌ Seleziona un file o inserisci dati scanner');
                }
                return;
            }
            
            console.log('File selezionato:', file.name);
            currentFileName = file.name; // Salva nome file per logging

            // Mostra status di elaborazione
            if (addStockUpload) {
                addStockUpload.setStatus('processing', '⏳ Elaborazione file in corso...');
            }

            const formData = new FormData();
            formData.append('file', file);

            console.log('Invio richiesta a /inventory/parse-add-stock-file');
            fetch('/inventory/parse-add-stock-file', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                    if (addStockUpload) {
                        addStockUpload.setStatus('error', `❌ Errore: ${data.detail}`);
                    }
                } else {
                    if (addStockUpload) {
                        addStockUpload.setStatus('success', '✅ File elaborato correttamente! Mostrando recap...');
                    }
                    showRecap(data, 'add', 'Carico da File');
                    closeOverlay('file-operations-overlay');
                }
            })
            .catch(error => {
                console.error('Errore nella fetch:', error);
                alert('Si è verificato un errore durante l\'analisi del file.');
                if (addStockUpload) {
                    addStockUpload.setStatus('error', '❌ Errore di rete durante l\'elaborazione');
                }
            });
        });
    }

    // --- Gestione Form per Scarico da File con Recap (Enhanced Upload) ---
    const subtractStockForm = document.getElementById('subtract-stock-form');
    if (subtractStockForm) {
        subtractStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per subtract-stock-form');
            
            const fileInput = document.getElementById('subtract-stock-file');
            const file = fileInput.files[0];
            
            if (!file) {
                console.log('Nessun file selezionato.');
                if (subtractStockUpload) {
                    subtractStockUpload.setStatus('error', '❌ Seleziona un file o inserisci dati scanner');
                }
                return;
            }
            
            console.log('File selezionato:', file.name);
            currentFileName = file.name; // Salva nome file per logging

            // Mostra status di elaborazione
            if (subtractStockUpload) {
                subtractStockUpload.setStatus('processing', '⏳ Elaborazione file in corso...');
            }

            const formData = new FormData();
            formData.append('file', file);

            console.log('Invio richiesta a /inventory/parse-subtract-stock-file');
            fetch('/inventory/parse-subtract-stock-file', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                    if (subtractStockUpload) {
                        subtractStockUpload.setStatus('error', `❌ Errore: ${data.detail}`);
                    }
                } else {
                    if (subtractStockUpload) {
                        subtractStockUpload.setStatus('success', '✅ File elaborato correttamente! Mostrando recap...');
                    }
                    showRecap(data, 'subtract', 'Scarico da File');
                    closeOverlay('file-operations-overlay');
                }
            })
            .catch(error => {
                console.error('Errore nella fetch:', error);
                alert('Si è verificato un errore durante l\'analisi del file.');
                if (subtractStockUpload) {
                    subtractStockUpload.setStatus('error', '❌ Errore di rete durante l\'elaborazione');
                }
            });
        });
    }

    // --- Gestione Form per Spostamenti da File ---
    const movementsForm = document.getElementById('movements-form');
    if (movementsForm) {
        movementsForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per movements-form');
            const fileInput = document.getElementById('movements-file');
            const file = fileInput.files[0];
            if (!file) {
                console.log('Nessun file selezionato.');
                return;
            }
            console.log('File selezionato:', file.name);
            currentFileName = file.name; // Salva nome file per logging

            const formData = new FormData();
            formData.append('file', file);

            console.log('Invio richiesta a /inventory/parse-movements-file');
            fetch('/inventory/parse-movements-file', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                } else {
                    showMovementsRecap(data);
                    closeOverlay('file-operations-overlay');
                }
            })
            .catch(error => {
                console.error('Errore nella fetch:', error);
                alert('Si è verificato un errore durante l\'analisi del file.');
            });
        });
    }

    // --- Gestione Form per Riallineamento (Sostituzione) ---
    const importStockForm = document.getElementById('import-stock-form');
    if (importStockForm) {
        importStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per import-stock-form (Riallineamento)');
            const fileInput = document.getElementById('stock-file');
            const file = fileInput.files[0];
            if (!file) {
                console.log('Nessun file selezionato.');
                return;
            }
            console.log('File selezionato:', file.name);
            currentFileName = file.name; // Salva nome file per logging

            const formData = new FormData();
            formData.append('file', file);

            console.log('Invio richiesta a /inventory/parse-realignment-file');
            fetch('/inventory/parse-realignment-file', { // Endpoint aggiornato
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server (parse-realignment-file):', data);
                if (data.errors && data.errors.length > 0) {
                    let errorString = 'Errori nel file:\n';
                    data.errors.forEach(err => {
                        errorString += `Riga ${err.line_number}: ${err.error}\n`;
                    });
                    alert(errorString);
                }
                if (data.items_to_commit) {
                    commitData = data.items_to_commit; // Salva i dati
                    displayConfirmationModal(data.items_to_commit);
                }
            })
            .catch(error => {
                console.error('Errore nella fetch per parse-realignment-file:', error);
                alert('Si è verificato un errore durante l\'analisi del file.');
            });
        });
    }

    // --- Logica della Modale di Conferma per Riallineamento ---
    const modal = document.getElementById('confirmation-modal');
    const closeButton = document.querySelector('.close-button');
    const confirmButton = document.getElementById('confirm-import-button');
    const cancelButton = document.getElementById('cancel-import-button');

    function displayConfirmationModal(items) {
        const modalBody = document.getElementById('modal-body');
        let tableHtml = `
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Ubicazione</th>
                            <th>SKU</th>
                            <th>Giacenza Attuale</th>
                            <th>Nuova Giacenza</th>
                            <th>Stato</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        items.forEach(item => {
            tableHtml += `
                <tr class="status-${item.status}">
                    <td>${item.location_name}</td>
                    <td>${item.product_sku}</td>
                    <td>${item.current_quantity}</td>
                    <td>${item.new_quantity}</td>
                    <td>${item.status.replace('_', ' ')}</td>
                </tr>
            `;
        });
        tableHtml += '</tbody></table></div>';
        modalBody.innerHTML = tableHtml;
        modal.style.display = 'block';
    }

    if(closeButton) closeButton.onclick = () => modal.style.display = 'none';
    if(cancelButton) cancelButton.onclick = () => modal.style.display = 'none';
    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    };

    if (confirmButton) {
        confirmButton.addEventListener('click', function() {
            if (commitData) {
                console.log('Invio richiesta a /inventory/commit-realignment');
                fetch('/inventory/commit-realignment', { // Endpoint aggiornato
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ items: commitData })
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Risposta dal server (commit-realignment):', data);
                    alert(data.message);
                    modal.style.display = 'none';
                    window.location.reload();
                })
                .catch(error => {
                    console.error('Errore nella fetch per commit-realignment:', error);
                    alert('Si è verificato un errore durante la conferma.');
                });
            }
        });
    }

    // --- Gestione Dati Giacenze (Backup, Restore, Delete) ---

    // Backup
    const backupBtn = document.getElementById('backup-stock-btn');
    if (backupBtn) {
        backupBtn.addEventListener('click', function() {
            window.location.href = '/inventory/backup-stock';
        });
    }

    // Restore
    const restoreForm = document.getElementById('restore-stock-form');
    if (restoreForm) {
        restoreForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const fileInput = document.getElementById('restore-stock-file');
            const file = fileInput.files[0];

            if (!file) {
                alert('Per favore, seleziona un file di backup.');
                return;
            }

            if (confirm('Sei sicuro di voler ripristinare la giacenza da questo file? TUTTE le giacenze attuali verranno eliminate e sostituite.')) {
                const formData = new FormData();
                formData.append('file', file);

                fetch('/inventory/restore-stock', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.detail) {
                        alert('Errore: ' + data.detail);
                    } else {
                        alert(data.message);
                        window.location.reload();
                    }
                })
                .catch(error => {
                    console.error('Errore nel ripristino:', error);
                    alert('Si è verificato un errore durante il ripristino.');
                });
            }
        });
    }

    // Delete All
    const deleteAllBtn = document.getElementById('delete-all-stock-btn');
    if (deleteAllBtn) {
        deleteAllBtn.addEventListener('click', function() {
            if (confirm('ATTENZIONE: Stai per eliminare TUTTE le giacenze presenti in magazzino. Sei assolutamente sicuro?')) {
                fetch('/inventory/delete-all-stock', {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.detail) {
                        alert('Errore: ' + data.detail);
                    } else {
                        alert(data.message);
                        window.location.reload();
                    }
                })
                .catch(error => {
                    console.error('Errore nell\'eliminazione totale:', error);
                    alert('Si è verificato un errore.');
                });
            }
        });
    }

    // Delete by Row
    const deleteByRowForm = document.getElementById('delete-by-row-form');
    if (deleteByRowForm) {
        deleteByRowForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const rowPrefix = document.getElementById('row-prefix').value;

            if (!rowPrefix) {
                alert('Inserisci il prefisso della fila da eliminare.');
                return;
            }

            if (confirm(`Sei sicuro di voler eliminare tutte le giacenze nelle ubicazioni che iniziano con "${rowPrefix}"?`)) {
                fetch(`/inventory/delete-stock-by-row?row_prefix=${encodeURIComponent(rowPrefix)}`, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.detail) {
                        alert('Errore: ' + data.detail);
                    } else {
                        alert(data.message);
                        window.location.reload();
                    }
                })
                .catch(error => {
                    console.error('Errore nell\'eliminazione per fila:', error);
                    alert('Si è verificato un errore.');
                });
            }
        });
    }

    // === SISTEMA RECAP PER OPERAZIONI DA FILE ===
    let currentRecapData = null;
    let currentOperationType = null;
    let currentRecapFileName = null;

    // Mostra il recap delle operazioni
    function showRecap(data, operationType, title) {
        currentRecapData = data;
        currentOperationType = operationType;
        currentRecapFileName = currentFileName; // Salva il nome file per il recap
        
        // Aggiorna il titolo
        document.getElementById('recap-title').textContent = `📋 ${title} - Riepilogo`;
        
        // Aggiorna le statistiche
        const totalOps = data.recap_items ? data.recap_items.length : 0;
        const okOps = data.recap_items ? data.recap_items.filter(item => item.status === 'ok').length : 0;
        const manualInputOps = data.recap_items ? data.recap_items.filter(item => item.status === 'manual_input' || item.needs_input).length : 0;
        const warningOps = data.warnings ? data.warnings.length : 0;
        const errorOps = data.errors ? data.errors.length : 0;
        
        document.getElementById('recap-total').textContent = totalOps;
        document.getElementById('recap-ok').textContent = okOps;
        document.getElementById('recap-warnings').textContent = warningOps;
        document.getElementById('recap-errors').textContent = errorOps;
        
        // Popola sezione errori
        const errorsSection = document.getElementById('recap-errors-section');
        const errorsList = document.getElementById('recap-errors-list');
        if (data.errors && data.errors.length > 0) {
            errorsSection.style.display = 'block';
            errorsList.innerHTML = data.errors.map(error => 
                `<div class="error-item">
                    <strong>Riga ${error.line}</strong>: ${error.message}
                    <div class="recap-edit-controls">
                        <input type="text" class="recap-edit-input" placeholder="Ubicazione" data-type="location" data-line="${error.line}" value="${error.location || ''}" style="width: 100px;">
                        <input type="text" class="recap-edit-input recap-sku-input" placeholder="SKU" data-type="sku" data-line="${error.line}" style="width: 100px;" list="product-skus">
                        <input type="number" class="recap-edit-input" placeholder="Qtà" data-type="quantity" data-line="${error.line}" value="${error.quantity || 1}">
                        <button class="recap-edit-btn" onclick="fixError(${error.line})">Correggi</button>
                        <button class="recap-ignore-btn" onclick="ignoreError(${error.line})">Ignora</button>
                    </div>
                </div>`
            ).join('');
        } else {
            errorsSection.style.display = 'none';
        }
        
        // Popola sezione avvisi
        const warningsSection = document.getElementById('recap-warnings-section');
        const warningsList = document.getElementById('recap-warnings-list');
        if (data.warnings && data.warnings.length > 0) {
            warningsSection.style.display = 'block';
            warningsList.innerHTML = data.warnings.map(warning => 
                `<div class="warning-item">
                    <strong>Riga ${warning.line}</strong>: ${warning.message}
                </div>`
            ).join('');
        } else {
            warningsSection.style.display = 'none';
        }
        
        // Ricontrolla conflitti per tutte le operazioni
        if (data.recap_items) {
            data.recap_items.forEach(item => {
                if (item.status !== 'error') {
                    const hasConflict = checkLocationConflict(item.location, item.sku, data.recap_items, item.line);
                    if (hasConflict && item.status !== 'warning') {
                        item.status = 'warning';
                        // Aggiungi warning se non esiste già
                        const conflictWarning = data.warnings.find(w => 
                            w.line === item.line && w.type === 'location_conflict'
                        );
                        if (!conflictWarning && item.location !== 'TERRA') {
                            data.warnings.push({
                                line: item.line,
                                type: 'location_conflict',
                                message: `CONFLITTO: Ubicazione '${item.location}' contiene più SKU nella stessa operazione`,
                                location: item.location,
                                sku: item.sku
                            });
                        }
                    }
                }
            });
            
            // Aggiorna le statistiche dopo il controllo conflitti
            const okOps = data.recap_items.filter(item => item.status === 'ok').length;
            const manualInputOps = data.recap_items.filter(item => item.status === 'manual_input' || item.needs_input).length;
            const warningOps = data.warnings ? data.warnings.length : 0;
            document.getElementById('recap-ok').textContent = okOps;
            document.getElementById('recap-warnings').textContent = warningOps;
        }

        // Popola tabella operazioni
        const operationsTable = document.getElementById('recap-operations-table');
        if (data.recap_items && data.recap_items.length > 0) {
            operationsTable.innerHTML = data.recap_items.map(item => {
                const quantityColumn = operationType === 'add' ? 
                    `<td>${item.quantity_to_add}</td>` : 
                    `<td>${item.quantity_to_subtract}</td>`;
                
                // Aggiungi indicatore di stato nella riga
                const statusIcon = item.status === 'ok' ? '✅' : 
                                  item.status === 'warning' ? '⚠️' : 
                                  item.status === 'error' ? '❌' : 
                                  item.status === 'manual_input' ? '✏️' : '';
                
                // Gestione speciale per righe che necessitano input manuale
                if (item.needs_input || item.status === 'manual_input') {
                    return `<tr class="status-${item.status}" data-line="${item.line}">
                        <td>${statusIcon} ${item.line}</td>
                        <td>${item.location}</td>
                        <td style="color: #6c757d; font-style: italic;">- Inserisci manualmente -</td>
                        <td style="color: #6c757d; font-style: italic;">- Inserisci manualmente -</td>
                        <td style="color: #6c757d; font-style: italic;">Scansionata ubicazione senza EAN/SKU</td>
                        <td style="color: #6c757d; font-style: italic;">- Da inserire -</td>
                        <td>-</td>
                        <td style="color: #6c757d; font-style: italic;">- Calcolata dopo input -</td>
                        <td>
                            <div class="recap-edit-controls" style="flex-direction: column; gap: 0.25rem;">
                                <div style="display: flex; gap: 0.25rem; flex-wrap: wrap;">
                                    <input type="text" class="recap-edit-input" value="${item.location}" data-line="${item.line}" data-type="location" style="width: 80px;" placeholder="Ubicazione" readonly>
                                    <input type="text" class="recap-edit-input recap-sku-input" value="${item.sku}" data-line="${item.line}" data-type="sku" style="width: 100px;" placeholder="SKU prodotto" list="product-skus" required>
                                    <input type="number" class="recap-edit-input" value="${operationType === 'add' ? (item.quantity_to_add || 1) : (item.quantity_to_subtract || 1)}" data-line="${item.line}" data-type="quantity" style="width: 60px;" min="1" required>
                                </div>
                                <div style="display: flex; gap: 0.25rem;">
                                    <button class="recap-edit-btn" onclick="completeManualInput(${item.line})" style="background-color: #28a745;">Completa</button>
                                    <button class="recap-ignore-btn" onclick="removeOperation(${item.line})">Rimuovi</button>
                                </div>
                            </div>
                        </td>
                    </tr>`;
                } else {
                    return `<tr class="status-${item.status}" data-line="${item.line}">
                        <td>${statusIcon} ${item.line}</td>
                        <td>${item.location}</td>
                        <td>${item.sku}</td>
                        <td>${item.description}</td>
                        <td>${item.input_code}</td>
                        ${quantityColumn}
                        <td>${item.current_quantity}</td>
                        <td>${item.new_quantity}</td>
                        <td>
                            <div class="recap-edit-controls" style="flex-direction: column; gap: 0.25rem;">
                                <div style="display: flex; gap: 0.25rem;">
                                    <input type="text" class="recap-edit-input" value="${item.location}" data-line="${item.line}" data-type="location" style="width: 80px;" placeholder="Ubicazione">
                                    <input type="number" class="recap-edit-input" value="${operationType === 'add' ? item.quantity_to_add : item.quantity_to_subtract}" data-line="${item.line}" data-type="quantity" style="width: 60px;">
                                </div>
                                <div style="display: flex; gap: 0.25rem;">
                                    <button class="recap-edit-btn" onclick="updateOperation(${item.line})">Aggiorna</button>
                                    <button class="recap-ignore-btn" onclick="removeOperation(${item.line})">Rimuovi</button>
                                </div>
                            </div>
                        </td>
                    </tr>`;
                }
            }).join('');
        } else {
            operationsTable.innerHTML = '<tr><td colspan="9">Nessuna operazione da eseguire</td></tr>';
        }
        
        // Mostra l'overlay
        document.getElementById('recap-overlay').style.display = 'block';
        
        // Aggiungi event listener per autocompletamento SKU negli input manuali
        setTimeout(() => {
            const recapSkuInputs = document.querySelectorAll('.recap-sku-input');
            recapSkuInputs.forEach(input => {
                input.addEventListener('input', function() {
                    fetchAndPopulateDatalist(this.value);
                });
            });
        }, 100); // Piccolo delay per assicurarsi che gli elementi siano nel DOM
    }
    
    // Chiude il recap
    window.closeRecap = function() {
        document.getElementById('recap-overlay').style.display = 'none';
        currentRecapData = null;
        currentOperationType = null;
    };
    
    // Mostra il recap per spostamenti
    function showMovementsRecap(data) {
        currentRecapData = data;
        currentOperationType = 'movements';
        
        // Aggiorna il titolo
        document.getElementById('recap-title').textContent = `🔀 Spostamenti da File - Riepilogo`;
        
        // Aggiorna le statistiche
        const totalOps = data.recap_items ? data.recap_items.length : 0;
        const okOps = data.recap_items ? data.recap_items.filter(item => item.status === 'ok').length : 0;
        const warningOps = data.warnings ? data.warnings.length : 0;
        const errorOps = data.errors ? data.errors.length : 0;
        
        document.getElementById('recap-total').textContent = totalOps;
        document.getElementById('recap-ok').textContent = okOps;
        document.getElementById('recap-warnings').textContent = warningOps;
        document.getElementById('recap-errors').textContent = errorOps;
        
        // Popola sezione errori
        const errorsSection = document.getElementById('recap-errors-section');
        const errorsList = document.getElementById('recap-errors-list');
        if (data.errors && data.errors.length > 0) {
            errorsSection.style.display = 'block';
            errorsList.innerHTML = data.errors.map(error => 
                `<div class="error-item">
                    <strong>Riga ${error.line}</strong>: ${error.message}
                </div>`
            ).join('');
        } else {
            errorsSection.style.display = 'none';
        }
        
        // Popola sezione avvisi
        const warningsSection = document.getElementById('recap-warnings-section');
        const warningsList = document.getElementById('recap-warnings-list');
        if (data.warnings && data.warnings.length > 0) {
            warningsSection.style.display = 'block';
            warningsList.innerHTML = data.warnings.map(warning => 
                `<div class="warning-item">
                    <strong>Righe ${warning.line}</strong>: ${warning.message}
                </div>`
            ).join('');
        } else {
            warningsSection.style.display = 'none';
        }
        
        // Popola tabella spostamenti (formato diverso)
        const operationsTable = document.getElementById('recap-operations-table');
        if (data.recap_items && data.recap_items.length > 0) {
            // Cambia headers per spostamenti
            const recapTable = operationsTable.parentElement;
            const thead = recapTable.querySelector('thead tr');
            thead.innerHTML = `
                <th>N°</th>
                <th>Da Ubicazione</th>
                <th>A Ubicazione</th>
                <th>SKU</th>
                <th>Quantità</th>
                <th>Status</th>
                <th>Azioni</th>
            `;
            
            operationsTable.innerHTML = data.recap_items.map(item => {
                const statusIcon = item.status === 'ok' ? '✅' : 
                                  item.status === 'warning' ? '⚠️' : '❌';
                
                return `<tr class="status-${item.status}" data-move="${item.move_number}">
                    <td>${statusIcon} ${item.move_number}</td>
                    <td>${item.from_location}</td>
                    <td>${item.to_location}</td>
                    <td>${item.sku}</td>
                    <td>${item.quantity}</td>
                    <td>${item.status}</td>
                    <td>
                        <div class="recap-edit-controls">
                            <button class="recap-ignore-btn" onclick="removeMovement(${item.move_number})">Rimuovi</button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        } else {
            operationsTable.innerHTML = '<tr><td colspan="7">Nessuno spostamento da eseguire</td></tr>';
        }
        
        // Mostra l'overlay
        document.getElementById('recap-overlay').style.display = 'block';
    }
    
    // Corregge un errore
    window.fixError = function(line) {
        const locationInput = document.querySelector(`input[data-line="${line}"][data-type="location"]`);
        const skuInput = document.querySelector(`input[data-line="${line}"][data-type="sku"]`);
        const quantityInput = document.querySelector(`input[data-line="${line}"][data-type="quantity"]`);
        
        const newLocation = locationInput ? locationInput.value.trim().toUpperCase() : '';
        const newSku = skuInput.value.trim();
        const newQuantity = parseInt(quantityInput.value) || 1;
        
        if (!newLocation) {
            alert('Inserisci una ubicazione valida');
            return;
        }
        
        if (!newSku) {
            alert('Inserisci un SKU valido');
            return;
        }
        
        // Trova l'errore originale e convertilo in operazione
        const errorIndex = currentRecapData.errors.findIndex(e => e.line === line);
        if (errorIndex !== -1) {
            const error = currentRecapData.errors[errorIndex];
            
            // Rimuovi dall'array errori
            currentRecapData.errors.splice(errorIndex, 1);
            
            // Aggiungi alle operazioni
            if (!currentRecapData.recap_items) {
                currentRecapData.recap_items = [];
            }
            
            // Controlla se c'è conflitto con la nuova ubicazione
            const hasConflict = checkLocationConflict(newLocation, newSku, currentRecapData.recap_items);
            
            currentRecapData.recap_items.push({
                line: line,
                location: newLocation,
                sku: newSku,
                description: 'Corretto manualmente',
                input_code: newSku,
                quantity_to_add: currentOperationType === 'add' ? newQuantity : 0,
                quantity_to_subtract: currentOperationType === 'subtract' ? newQuantity : 0,
                current_quantity: 0,
                new_quantity: currentOperationType === 'add' ? newQuantity : -newQuantity,
                status: hasConflict ? 'warning' : 'ok'
            });
            
            // Ricarica il recap
            showRecap(currentRecapData, currentOperationType, document.getElementById('recap-title').textContent.split(' - ')[0].substring(2));
        }
    };
    
    // Ignora un errore
    window.ignoreError = function(line) {
        const errorIndex = currentRecapData.errors.findIndex(e => e.line === line);
        if (errorIndex !== -1) {
            currentRecapData.errors.splice(errorIndex, 1);
            showRecap(currentRecapData, currentOperationType, document.getElementById('recap-title').textContent.split(' - ')[0].substring(2));
        }
    };
    
    // Aggiorna un'operazione
    window.updateOperation = function(line) {
        const locationInput = document.querySelector(`input[data-line="${line}"][data-type="location"]`);
        const quantityInput = document.querySelector(`input[data-line="${line}"][data-type="quantity"]`);
        
        const newLocation = locationInput ? locationInput.value.trim().toUpperCase() : '';
        const newQuantity = parseInt(quantityInput.value) || 0;
        
        if (!newLocation) {
            alert('Inserisci una ubicazione valida');
            return;
        }
        
        const operationIndex = currentRecapData.recap_items.findIndex(item => item.line === line);
        if (operationIndex !== -1) {
            const operation = currentRecapData.recap_items[operationIndex];
            
            // Aggiorna ubicazione
            operation.location = newLocation;
            
            // Aggiorna quantità
            if (currentOperationType === 'add') {
                operation.quantity_to_add = newQuantity;
                operation.new_quantity = operation.current_quantity + newQuantity;
            } else {
                operation.quantity_to_subtract = newQuantity;
                operation.new_quantity = Math.max(0, operation.current_quantity - newQuantity);
            }
            
            // Controlla conflitti con la nuova ubicazione
            const hasConflict = checkLocationConflict(newLocation, operation.sku, currentRecapData.recap_items, line);
            operation.status = hasConflict ? 'warning' : 'ok';
            
            // Ricarica completamente il recap per aggiornare tutti i conflitti
            showRecap(currentRecapData, currentOperationType, document.getElementById('recap-title').textContent.split(' - ')[0].substring(2));
        }
    };
    
    // Rimuove un'operazione
    window.removeOperation = function(line) {
        const operationIndex = currentRecapData.recap_items.findIndex(item => item.line === line);
        if (operationIndex !== -1) {
            currentRecapData.recap_items.splice(operationIndex, 1);
            showRecap(currentRecapData, currentOperationType, document.getElementById('recap-title').textContent.split(' - ')[0].substring(2));
        }
    };
    
    // Rimuove uno spostamento
    window.removeMovement = function(moveNumber) {
        const moveIndex = currentRecapData.recap_items.findIndex(item => item.move_number === moveNumber);
        if (moveIndex !== -1) {
            currentRecapData.recap_items.splice(moveIndex, 1);
            showMovementsRecap(currentRecapData);
        }
    };
    
    // Completa l'input manuale per una ubicazione scansionata senza EAN/SKU
    window.completeManualInput = function(line) {
        const skuInput = document.querySelector(`input[data-line="${line}"][data-type="sku"]`);
        const quantityInput = document.querySelector(`input[data-line="${line}"][data-type="quantity"]`);
        
        const newSku = skuInput.value.trim();
        const newQuantity = parseInt(quantityInput.value) || 1;
        
        if (!newSku) {
            alert('Inserisci un SKU valido');
            skuInput.focus();
            return;
        }
        
        if (newQuantity <= 0) {
            alert('Inserisci una quantità valida (maggiore di 0)');
            quantityInput.focus();
            return;
        }
        
        // Trova l'operazione
        const operation = currentRecapData.recap_items.find(item => item.line === line);
        if (operation) {
            // Verifica se il SKU esiste nel database (chiamata asincrona)
            fetch(`/products/verify-sku/${encodeURIComponent(newSku)}`)
                .then(response => response.json())
                .then(data => {
                    if (!data.exists) {
                        if (!confirm(`Il SKU '${newSku}' non è stato trovato nel database. Vuoi procedere comunque?`)) {
                            return;
                        }
                    }
                    
                    // Prima di aggiornare l'operazione, recupera la giacenza attuale dal database
                    return fetch(`/inventory/get-current-quantity/${encodeURIComponent(newSku)}/${encodeURIComponent(operation.location)}`)
                        .then(response => response.json())
                        .then(quantityData => {
                            const currentQtyFromDB = quantityData.current_quantity || 0;
                            
                            // Aggiorna l'operazione con i dati inseriti
                            operation.sku = newSku;
                            operation.description = data.description || '';
                            operation.input_code = newSku;
                            operation.status = 'ok';
                            operation.needs_input = false;
                            operation.current_quantity = currentQtyFromDB; // Aggiorna con la giacenza reale
                            
                            // Aggiorna quantità in base al tipo di operazione
                            if (currentOperationType === 'add') {
                                operation.quantity_to_add = newQuantity;
                                operation.new_quantity = currentQtyFromDB + newQuantity;
                            } else {
                                operation.quantity_to_subtract = newQuantity;
                                operation.new_quantity = Math.max(0, currentQtyFromDB - newQuantity);
                                
                                // Controlla giacenza insufficiente per scarico
                                if (currentQtyFromDB < newQuantity) {
                                    operation.status = 'error';
                                    // Aggiungi warning se non esiste già
                                    const existingWarning = currentRecapData.warnings.find(w => 
                                        w.line === line && w.type === 'insufficient_stock'
                                    );
                                    if (!existingWarning) {
                                        currentRecapData.warnings.push({
                                            line: line,
                                            type: 'insufficient_stock',
                                            message: `GIACENZA INSUFFICIENTE: Tentativo di scaricare ${newQuantity} pz di '${newSku}' da '${operation.location}'. Disponibile: ${currentQtyFromDB}`,
                                            sku: newSku,
                                            location: operation.location,
                                            quantity: newQuantity,
                                            available: currentQtyFromDB
                                        });
                                    }
                                }
                            }
                            
                            return operation;
                        })
                        .catch(error => {
                            console.warn('Impossibile recuperare giacenza attuale, uso 0:', error);
                            // Fallback con giacenza 0
                            operation.sku = newSku;
                            operation.description = data.description || '';
                            operation.input_code = newSku;
                            operation.status = 'ok';
                            operation.needs_input = false;
                            operation.current_quantity = 0;
                            
                            if (currentOperationType === 'add') {
                                operation.quantity_to_add = newQuantity;
                                operation.new_quantity = newQuantity;
                            } else {
                                operation.quantity_to_subtract = newQuantity;
                                operation.new_quantity = 0;
                                operation.status = 'error';
                            }
                            
                            return operation;
                        })
                        .then(operation => {
                            // Controlla conflitti con altri SKU nella stessa ubicazione
                            const hasConflict = checkLocationConflict(operation.location, newSku, currentRecapData.recap_items, line);
                            if (hasConflict && operation.status !== 'error') {
                                operation.status = 'warning';
                            }
                            
                            // Rimuovi warning di ubicazione vuota se esiste
                            const emptyLocationWarningIndex = currentRecapData.warnings.findIndex(w => 
                                w.line === line && w.type === 'empty_location'
                            );
                            if (emptyLocationWarningIndex !== -1) {
                                currentRecapData.warnings.splice(emptyLocationWarningIndex, 1);
                            }
                            
                            // Ricarica completamente il recap
                            showRecap(currentRecapData, currentOperationType, document.getElementById('recap-title').textContent.split(' - ')[0].substring(2));
                        });
                })
                .catch(error => {
                    console.error('Errore nella verifica SKU:', error);
                    // Procede comunque con l'input dell'utente
                    operation.sku = newSku;
                    operation.description = '';
                    operation.input_code = newSku;
                    operation.status = 'ok';
                    operation.needs_input = false;
                    
                    if (currentOperationType === 'add') {
                        operation.quantity_to_add = newQuantity;
                        operation.new_quantity = operation.current_quantity + newQuantity;
                    } else {
                        operation.quantity_to_subtract = newQuantity;
                        operation.new_quantity = Math.max(0, operation.current_quantity - newQuantity);
                    }
                    
                    showRecap(currentRecapData, currentOperationType, document.getElementById('recap-title').textContent.split(' - ')[0].substring(2));
                });
        }
    };
    
    // Funzione per controllare conflitti di ubicazione
    function checkLocationConflict(location, sku, operations, excludeLine = null) {
        // ECCEZIONE: TERRA può contenere SKU multipli
        if (location === 'TERRA') return false;
        
        return operations.some(op => 
            op.line !== excludeLine && 
            op.location === location && 
            op.sku !== sku && 
            op.status !== 'error'
        );
    }
    
    // Valida tutte le operazioni per conflitti
    function validateAllOperations() {
        if (!currentRecapData || !currentRecapData.recap_items) return true;
        
        const errors = [];
        const warnings = [];
        
        // Controlla errori non risolti
        if (currentRecapData.errors && currentRecapData.errors.length > 0) {
            errors.push(`Ci sono ancora ${currentRecapData.errors.length} errori non risolti`);
        }
        
        // Controlla operazioni che necessitano ancora input manuale
        const manualInputItems = currentRecapData.recap_items.filter(item => 
            item.status === 'manual_input' || item.needs_input
        );
        if (manualInputItems.length > 0) {
            errors.push(`Ci sono ancora ${manualInputItems.length} operazioni che necessitano input manuale`);
        }
        
        // Controlla conflitti di ubicazione (escludi operazioni con input manuale)
        const locationGroups = {};
        currentRecapData.recap_items.forEach(item => {
            if (item.status === 'error' || item.status === 'manual_input' || item.needs_input) return;
            
            if (!locationGroups[item.location]) {
                locationGroups[item.location] = [];
            }
            locationGroups[item.location].push(item);
        });
        
        Object.keys(locationGroups).forEach(location => {
            const items = locationGroups[location];
            const uniqueSkus = [...new Set(items.map(item => item.sku).filter(sku => sku))]; // Filtra SKU vuoti
            
            if (uniqueSkus.length > 1 && location !== 'TERRA') {
                errors.push(`CONFLITTO: Ubicazione '${location}' contiene più SKU: ${uniqueSkus.join(', ')}`);
            }
        });
        
        // Controlla operazioni con status warning
        const warningItems = currentRecapData.recap_items.filter(item => item.status === 'warning');
        if (warningItems.length > 0) {
            warnings.push(`Ci sono ${warningItems.length} operazioni con avvisi`);
        }
        
        return { errors, warnings };
    }
    
    // Esegue le operazioni validate
    document.getElementById('recap-execute-btn').addEventListener('click', function() {
        if (!currentRecapData || !currentRecapData.recap_items || currentRecapData.recap_items.length === 0) {
            alert('Nessuna operazione da eseguire');
            return;
        }
        
        // Gestione speciale per spostamenti
        if (currentOperationType === 'movements') {
            executeMovements();
            return;
        }
        
        // Gestione speciale per scarico container
        if (currentOperationType === 'unload_container') {
            executeUnloadContainerOperations();
            return;
        }
        
        // Gestione speciale per ubicazione da terra
        if (currentOperationType === 'relocate_ground') {
            executeRelocateGroundOperations();
            return;
        }
        
        // Valida tutte le operazioni (per carico/scarico)
        const validation = validateAllOperations();
        
        if (validation.errors.length > 0) {
            alert('❌ IMPOSSIBILE ESEGUIRE LE OPERAZIONI:\n\n' + validation.errors.join('\n\n') + '\n\nCorreggi gli errori prima di procedere.');
            return;
        }
        
        if (validation.warnings.length > 0) {
            const proceed = confirm('⚠️ ATTENZIONE:\n\n' + validation.warnings.join('\n\n') + '\n\nVuoi procedere comunque?');
            if (!proceed) {
                return;
            }
        }
        
        // Filtro solo operazioni valide
        const validOperations = currentRecapData.recap_items.filter(item => 
            item.status !== 'error' && item.status !== 'warning'
        );
        
        if (validOperations.length === 0) {
            alert('Nessuna operazione valida da eseguire dopo la validazione');
            return;
        }
        
        const operationsData = {
            type: currentOperationType,
            operations: validOperations,
            file_name: currentRecapFileName || currentFileName || 'uploaded_file.txt'
        };
        
        fetch('/inventory/commit-file-operations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(operationsData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                closeRecap();
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore nell\'esecuzione:', error);
            alert('Si è verificato un errore durante l\'esecuzione delle operazioni.');
        });
    });
    
    // Esegue gli spostamenti
    function executeMovements() {
        const hasErrors = currentRecapData.errors && currentRecapData.errors.length > 0;
        const hasWarnings = currentRecapData.warnings && currentRecapData.warnings.length > 0;
        
        if (hasErrors) {
            alert('❌ IMPOSSIBILE ESEGUIRE GLI SPOSTAMENTI: Ci sono errori che devono essere corretti.');
            return;
        }
        
        if (hasWarnings) {
            const proceed = confirm('⚠️ ATTENZIONE: Ci sono conflitti negli spostamenti.\n\nAlcune ubicazioni di destinazione contengono già altri prodotti che saranno sovrascritti.\n\nVuoi procedere comunque?');
            if (!proceed) {
                return;
            }
        }
        
        const movementsData = {
            movements: currentRecapData.recap_items,
            file_name: currentRecapFileName || currentFileName || 'movements_file.txt'
        };
        
        fetch('/inventory/commit-movements', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(movementsData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                closeRecap();
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore nell\'esecuzione spostamenti:', error);
            alert('Si è verificato un errore durante l\'esecuzione degli spostamenti.');
        });
    }

    // Handler per form scarico container manuale
    document.getElementById('unload-manual-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const sku = document.getElementById('unload-product-sku').value.trim();
        const quantity = parseInt(document.getElementById('unload-quantity').value) || 0;
        
        if (!sku) {
            alert('Inserisci un SKU valido');
            return;
        }
        
        if (quantity <= 0) {
            alert('Inserisci una quantità valida');
            return;
        }
        
        const formData = {
            sku: sku,
            quantity: quantity
        };
        
        fetch('/inventory/unload-container-manual', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                closeOverlay('unload-container-overlay');
                this.reset();
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore scarico container:', error);
            alert('Si è verificato un errore durante lo scarico container.');
        });
    });

    // Handler per form scarico container da file
    document.getElementById('unload-file-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('unload-file');
        const file = fileInput.files[0];
        
        if (!file) {
            console.log('Nessun file selezionato.');
            return;
        }
        
        if (!file.name.endsWith('.txt')) {
            console.log('Formato file non valido.');
            return;
        }
        
        currentFileName = file.name; // Salva nome file per logging
        
        const formData = new FormData();
        formData.append('file', file);
        
        fetch('/inventory/parse-unload-container-file', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                showUnloadContainerRecap(data, 'Scarico Container da File');
                closeOverlay('unload-container-overlay');
            }
        })
        .catch(error => {
            console.error('Errore nella fetch:', error);
            alert('Si è verificato un errore durante l\'analisi del file.');
        });
    });

    // Handler per form ubicazione da terra manuale
    document.getElementById('relocate-manual-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const sku = document.getElementById('relocate-product-sku').value.trim();
        const quantity = parseInt(document.getElementById('relocate-quantity').value) || 0;
        const location = document.getElementById('relocate-location').value.trim().toUpperCase();
        
        if (!sku) {
            alert('Inserisci un SKU valido');
            return;
        }
        
        if (quantity <= 0) {
            alert('Inserisci una quantità valida');
            return;
        }
        
        if (!location) {
            alert('Inserisci una ubicazione valida');
            return;
        }
        
        const formData = {
            sku: sku,
            quantity: quantity,
            location: location
        };
        
        fetch('/inventory/relocate-from-ground-manual', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                closeOverlay('ground-to-location-overlay');
                this.reset();
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore ubicazione da terra:', error);
            alert('Si è verificato un errore durante l\'ubicazione da terra.');
        });
    });

    // Handler per form ubicazione da terra da file
    document.getElementById('relocate-file-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('relocate-file');
        const file = fileInput.files[0];
        
        if (!file) {
            console.log('Nessun file selezionato.');
            return;
        }
        
        if (!file.name.endsWith('.txt')) {
            console.log('Formato file non valido.');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        currentFileName = file.name; // Salva nome file per logging
        
        fetch('/inventory/parse-relocate-from-ground-file', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                showRelocateGroundRecap(data, 'Ubicazione da Terra da File');
                closeOverlay('ground-to-location-overlay');
            }
        })
        .catch(error => {
            console.error('Errore nella fetch:', error);
            alert('Si è verificato un errore durante l\'analisi del file.');
        });
    });

    // Funzione per consolidare i record duplicati in TERRA
    window.consolidateGroundInventory = function() {
        if (!confirm('Vuoi consolidare i record duplicati dello stesso SKU in TERRA?\n\nQuesta operazione unirà tutti i record dello stesso prodotto in un singolo record con la quantità totale.')) {
            return;
        }
        
        fetch('/inventory/consolidate-ground-inventory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore consolidamento TERRA:', error);
            alert('Si è verificato un errore durante il consolidamento.');
        });
    };

    // === RECAP SCARICO CONTAINER ===
    function showUnloadContainerRecap(data, title) {
        try {
            currentRecapData = data;
            currentOperationType = 'unload_container';
            currentRecapFileName = currentFileName; // Salva il nome file per il recap
        
        // Aggiorna il titolo
        document.getElementById('recap-title').textContent = `📦 ${title} - Riepilogo`;
        
        // Mostra statistiche usando la struttura esistente
        const totalOps = data.recap_items ? data.recap_items.length : 0;
        const totalPieces = data.total_pieces || 0;
        const okOps = data.recap_items ? data.recap_items.filter(item => item.status === 'ok').length : 0;
        const errorOps = data.errors ? data.errors.length : 0;
        const warningOps = data.warnings ? data.warnings.length : 0;
        
        document.getElementById('recap-total').textContent = totalOps;
        document.getElementById('recap-ok').textContent = okOps;
        document.getElementById('recap-warnings').textContent = warningOps;
        document.getElementById('recap-errors').textContent = errorOps;
        
        // Mostra operazioni in formato tabella
        let operationsHTML = '';
        if (data.recap_items && data.recap_items.length > 0) {
            data.recap_items.forEach(item => {
                const statusClass = item.status === 'ok' ? 'status-ok' : 
                                  item.status === 'warning' ? 'status-warning' : 'status-error';
                
                operationsHTML += `
                    <tr class="${statusClass}">
                        <td>${item.line}</td>
                        <td>${item.location}</td>
                        <td>${item.sku}</td>
                        <td>${item.description}</td>
                        <td>${item.input_code}</td>
                        <td class="quantity-add">+${item.quantity_to_add}</td>
                        <td>${item.current_quantity}</td>
                        <td class="quantity-new">${item.new_quantity}</td>
                        <td><span class="status-badge ${statusClass}">${item.status.toUpperCase()}</span></td>
                    </tr>
                `;
            });
        }
        document.getElementById('recap-operations-table').innerHTML = operationsHTML;
        
        // Mostra errori se presenti
        let errorsHTML = '';
        if (data.errors && data.errors.length > 0) {
            data.errors.forEach(error => {
                errorsHTML += `
                    <div class="error-item">
                        <strong>Riga ${error.line}:</strong> ${error.error}
                        <br><em>Input: "${error.input}"</em>
                    </div>
                `;
            });
            document.getElementById('recap-errors-section').style.display = 'block';
        } else {
            document.getElementById('recap-errors-section').style.display = 'none';
        }
        document.getElementById('recap-errors-list').innerHTML = errorsHTML;
        
        // Mostra warnings se presenti
        let warningsHTML = '';
        if (data.warnings && data.warnings.length > 0) {
            data.warnings.forEach(warning => {
                warningsHTML += `
                    <div class="warning-item">
                        <strong>⚠️ Attenzione:</strong> ${warning.message}
                    </div>
                `;
            });
            document.getElementById('recap-warnings-section').style.display = 'block';
        } else {
            document.getElementById('recap-warnings-section').style.display = 'none';
        }
        document.getElementById('recap-warnings-list').innerHTML = warningsHTML;
        
            // Mostra il recap
            document.getElementById('recap-overlay').style.display = 'flex';
        } catch (error) {
            console.error('Error in showUnloadContainerRecap:', error);
            throw error; // Re-throw per far scattare il catch principale
        }
    }
    
    // Funzione per eseguire le operazioni di scarico container
    window.executeUnloadContainerOperations = function() {
        const validOperations = currentRecapData.recap_items.filter(item => item.status === 'ok');
        
        if (validOperations.length === 0) {
            alert('Nessuna operazione valida da eseguire dopo la validazione');
            return;
        }
        
        const operationsData = {
            operations: validOperations,
            file_name: currentRecapFileName || currentFileName || 'container_unload.txt'
        };
        
        fetch('/inventory/commit-unload-container-operations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(operationsData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                closeRecap();
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore nell\'esecuzione:', error);
            alert('Si è verificato un errore durante l\'esecuzione delle operazioni.');
        });
    };

    // === RECAP UBICAZIONE DA TERRA ===
    function showRelocateGroundRecap(data, title) {
        try {
            currentRecapData = data;
            currentOperationType = 'relocate_ground';
            currentRecapFileName = currentFileName; // Salva il nome file per il recap
        
            // Aggiorna il titolo
            document.getElementById('recap-title').textContent = `🏗️ ${title} - Riepilogo`;
            
            // Mostra statistiche usando la struttura esistente
            const totalOps = data.recap_items ? data.recap_items.length : 0;
            const okOps = data.recap_items ? data.recap_items.filter(item => item.status === 'ok').length : 0;
            const errorOps = data.errors ? data.errors.length : 0;
            const warningOps = data.warnings ? data.warnings.length : 0;
            
            document.getElementById('recap-total').textContent = data.total_operations || 0;
            document.getElementById('recap-ok').textContent = okOps;
            document.getElementById('recap-warnings').textContent = warningOps;
            document.getElementById('recap-errors').textContent = errorOps;
            
            // Mostra operazioni in formato tabella
            let operationsHTML = '';
            if (data.recap_items && data.recap_items.length > 0) {
                data.recap_items.forEach(item => {
                    const statusClass = item.status === 'ok' ? 'status-ok' : 
                                      item.status === 'warning' ? 'status-warning' : 'status-error';
                    
                    operationsHTML += `
                        <tr class="${statusClass}">
                            <td>${item.line}</td>
                            <td>TERRA → ${item.location_to}</td>
                            <td>${item.sku}</td>
                            <td>${item.description}</td>
                            <td>${item.input_code}</td>
                            <td class="quantity-move">${item.quantity_to_move}</td>
                            <td>TERRA: ${item.current_ground_quantity} → ${item.new_ground_quantity}</td>
                            <td>${item.location_to}: ${item.current_destination_quantity} → ${item.new_destination_quantity}</td>
                            <td><span class="status-badge ${statusClass}">${item.status.toUpperCase()}</span></td>
                        </tr>
                    `;
                });
            }
            document.getElementById('recap-operations-table').innerHTML = operationsHTML;
            
            // Mostra errori se presenti
            let errorsHTML = '';
            if (data.errors && data.errors.length > 0) {
                data.errors.forEach(error => {
                    errorsHTML += `
                        <div class="error-item">
                            <strong>Riga ${error.line}:</strong> ${error.error}
                            <br><em>Input: "${error.input}"</em>
                        </div>
                    `;
                });
                document.getElementById('recap-errors-section').style.display = 'block';
            } else {
                document.getElementById('recap-errors-section').style.display = 'none';
            }
            document.getElementById('recap-errors-list').innerHTML = errorsHTML;
            
            // Mostra warnings se presenti
            let warningsHTML = '';
            if (data.warnings && data.warnings.length > 0) {
                data.warnings.forEach(warning => {
                    warningsHTML += `
                        <div class="warning-item">
                            <strong>⚠️ Attenzione:</strong> ${warning.message}
                        </div>
                    `;
                });
                document.getElementById('recap-warnings-section').style.display = 'block';
            } else {
                document.getElementById('recap-warnings-section').style.display = 'none';
            }
            document.getElementById('recap-warnings-list').innerHTML = warningsHTML;
            
            // Mostra il recap
            document.getElementById('recap-overlay').style.display = 'flex';
        } catch (error) {
            console.error('Error in showRelocateGroundRecap:', error);
            throw error; // Re-throw per far scattare il catch principale
        }
    }
    
    // Funzione per eseguire le operazioni di ubicazione da terra
    window.executeRelocateGroundOperations = function() {
        const validOperations = currentRecapData.recap_items.filter(item => item.status === 'ok');
        
        if (validOperations.length === 0) {
            alert('Nessuna operazione valida da eseguire dopo la validazione');
            return;
        }
        
        const operationsData = {
            operations: validOperations,
            file_name: currentRecapFileName || currentFileName || 'relocate_ground.txt'
        };
        
        fetch('/inventory/commit-relocate-from-ground-operations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(operationsData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                alert(data.message);
                closeRecap();
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Errore nell\'esecuzione:', error);
            alert('Si è verificato un errore durante l\'esecuzione delle operazioni.');
        });
    };

    // Carica i datalist degli SKU e inizializza la pagina
    loadInventoryData();
    setupSearch();
    setupSorting();
    loadProductSkus();
});

// Funzione per gestire le sezioni collassabili
function toggleCollapsible(header) {
    const content = header.nextElementSibling;
    const icon = header.querySelector('.collapsible-icon');
    
    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        icon.textContent = '▼';
        header.classList.add('active');
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
        header.classList.remove('active');
    }
}

// === CONSIGLI DI CONSOLIDAMENTO ===

async function showConsolidationSuggestions() {
    console.log('🧩 Caricamento consigli di consolidamento...');
    
    try {
        // Mostra overlay con loader
        const overlay = document.getElementById('consolidation-suggestions-overlay');
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'loading-indicator';
        loadingIndicator.innerHTML = '<div class="spinner"></div><p>Analisi inventario in corso...</p>';
        overlay.querySelector('.suggestions-content').appendChild(loadingIndicator);
        overlay.style.display = 'block';
        
        // Chiamata API
        const response = await fetch('/inventory/consolidation-suggestions', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (!response.ok) {
            throw new Error(`Errore API: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('📊 Dati ricevuti:', data);
        
        // Rimuovi loader
        loadingIndicator.remove();
        
        // Aggiorna statistiche
        document.getElementById('suggestions-count').textContent = data.total_suggestions;
        document.getElementById('locations-saveable').textContent = data.locations_saveable;
        document.getElementById('products-analyzed').textContent = data.products_analyzed;
        
        // Aggiorna tabella
        const tableBody = document.getElementById('suggestions-table-body');
        const noSuggestionsMessage = document.getElementById('no-suggestions-message');
        const tableContainer = document.querySelector('.suggestions-table-container');
        
        if (data.suggestions.length === 0) {
            // Nessun suggerimento
            tableContainer.style.display = 'none';
            noSuggestionsMessage.style.display = 'flex';
        } else {
            // Ci sono suggerimenti
            tableContainer.style.display = 'block';
            noSuggestionsMessage.style.display = 'none';
            
            tableBody.innerHTML = '';
            data.suggestions.forEach((suggestion, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="sku-cell">${suggestion.sku}</td>
                    <td class="location-cell from-location">${suggestion.from_location}</td>
                    <td class="quantity-cell from-quantity">${suggestion.from_quantity}</td>
                    <td class="location-cell to-location">${suggestion.to_location}</td>
                    <td class="quantity-cell to-quantity">${suggestion.to_quantity}</td>
                    <td class="quantity-cell combined-quantity"><strong>${suggestion.combined_quantity}</strong></td>
                    <td class="pallet-cell">${suggestion.pallet_quantity}</td>
                    <td class="benefit-cell">${suggestion.efficiency_gain}</td>
                `;
                
                // Aggiungi classe per alternare colori
                if (index % 2 === 0) {
                    row.classList.add('even-row');
                }
                
                tableBody.appendChild(row);
            });
        }
        
        console.log('✅ Overlay consigli consolidamento caricato con successo');
        
    } catch (error) {
        console.error('❌ Errore caricamento consigli:', error);
        
        // Rimuovi loader se presente
        const loader = document.querySelector('.loading-indicator');
        if (loader) loader.remove();
        
        // Mostra messaggio di errore
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <div class="error-icon">⚠️</div>
            <div class="error-text">
                <h4>Errore durante il caricamento</h4>
                <p>Non è stato possibile ottenere i consigli di consolidamento. ${error.message}</p>
            </div>
        `;
        
        const suggestionsContent = document.querySelector('.suggestions-content');
        suggestionsContent.appendChild(errorDiv);
        
        // Mostra comunque l'overlay
        document.getElementById('consolidation-suggestions-overlay').style.display = 'block';
    }
}

function closeConsolidationSuggestions() {
    const overlay = document.getElementById('consolidation-suggestions-overlay');
    overlay.style.display = 'none';
    
    // Pulizia: rimuovi eventuali messaggi di errore o loader
    const errorMessages = overlay.querySelectorAll('.error-message, .loading-indicator');
    errorMessages.forEach(msg => msg.remove());
    
    console.log('🧩 Overlay consigli consolidamento chiuso');
}

// Funzione utilitaria per troncare il testo
function truncateText(text, maxLength) {
    if (!text) return 'N/A';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// Chiude overlay se si clicca fuori
document.addEventListener('click', function(event) {
    const overlay = document.getElementById('consolidation-suggestions-overlay');
    if (event.target === overlay) {
        closeConsolidationSuggestions();
    }
});

// Funzione per esportare i consolidamenti in PDF
async function exportConsolidationPDF() {
    try {
        console.log('📄 Avvio esportazione PDF consolidamenti...');
        
        // Mostra stato di caricamento sul tasto
        const exportButton = document.getElementById('export-consolidation-pdf');
        const originalText = exportButton.innerHTML;
        exportButton.innerHTML = '⏳ Generando PDF...';
        exportButton.disabled = true;
        
        // Chiamata API per generare il PDF
        const response = await fetch('/inventory/consolidation-suggestions/pdf', {
            method: 'GET',
            headers: {
                'Accept': 'application/pdf'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Errore HTTP: ${response.status}`);
        }
        
        // Crea e scarica il file PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        
        // Nome file con data/ora
        const now = new Date();
        const timestamp = now.toISOString().slice(0, 19).replace(/:/g, '-');
        link.href = url;
        link.download = `consolidamenti-${timestamp}.pdf`;
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        
        // Cleanup
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        console.log('✅ PDF consolidamenti esportato con successo');
        
        // Feedback visivo
        exportButton.innerHTML = '✅ PDF Scaricato!';
        setTimeout(() => {
            exportButton.innerHTML = originalText;
            exportButton.disabled = false;
        }, 2000);
        
    } catch (error) {
        console.error('❌ Errore esportazione PDF:', error);
        
        // Ripristina tasto e mostra errore
        const exportButton = document.getElementById('export-consolidation-pdf');
        exportButton.innerHTML = '❌ Errore';
        exportButton.disabled = false;
        
        setTimeout(() => {
            exportButton.innerHTML = 'Esporta PDF';
        }, 3000);
        
        alert(`Errore durante l'esportazione del PDF: ${error.message}`);
    }
}