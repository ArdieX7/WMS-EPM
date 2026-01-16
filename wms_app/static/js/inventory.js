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
    let relocateGroundFileUpload = null;

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

    // Enhanced Upload per il nuovo tab ubicazione da terra (nelle operazioni da file)
    if (document.getElementById('relocate-ground-file-upload')) {
        console.log('🚀 Inizializzazione Enhanced Upload per ubicazione da terra (operazioni file)...');
        relocateGroundFileUpload = window.createEnhancedUpload('relocate-ground-file-upload', {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024,
            enableDragDrop: true,
            enableScanner: true,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nA01P1P1\nSKU123\nSKU456_5\n...',
            onFileSelect: function(file) {
                console.log('✅ File selezionato via Enhanced Upload ubicazione da terra:', file.name);
                syncWithHiddenInput('relocate-ground-file', file);
            },
            onScannerProcess: function(virtualFile, content) {
                console.log('✅ Dati scanner elaborati ubicazione da terra:', content.split('\n').length, 'righe');
                syncWithHiddenInput('relocate-ground-file', virtualFile);
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

        // NUOVO: Autofocus su campo scanner per mobile quando si apre file-operations
        if (overlayId === 'file-operations-overlay') {
            const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
                             || window.innerWidth < 768;

            if (isMobile) {
                // Aspetta che il tab attivo sia completamente renderizzato
                setTimeout(() => {
                    // Cerca il primo textarea scanner visibile nel tab attivo
                    const activeTab = document.querySelector('.tab-content.active');
                    if (activeTab) {
                        const scannerInput = activeTab.querySelector('.scanner-textarea');
                        if (scannerInput) {
                            scannerInput.focus();
                        }
                    }
                }, 200);  // Delay maggiore per dare tempo al tab system
            }
        }
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
                alert(`❌ Errore carico manuale: ${error.message}`);
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
                alert(`❌ Errore scarico manuale: ${error.message}`);
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
                alert(`❌ Errore spostamento manuale: ${error.message}`);
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
        backupBtn.addEventListener('click', async function() {
            try {
                const response = await window.modernAuth.authenticatedFetch('/inventory/backup-stock');

                if (!response.ok) {
                    throw new Error('Errore durante il backup');
                }

                // Gestione download file
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;

                // Estrai filename dall'header Content-Disposition se presente
                const disposition = response.headers.get('Content-Disposition');
                const filename = disposition
                    ? disposition.split('filename=')[1].replace(/"/g, '')
                    : 'backup_stock.json';

                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);

                alert('Backup creato con successo!');
            } catch (error) {
                console.error('Errore:', error);
                alert('Errore durante la creazione del backup: ' + error.message);
            }
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

                window.modernAuth.authenticatedFetch('/inventory/restore-stock', {
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
                window.modernAuth.authenticatedFetch('/inventory/delete-all-stock', {
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
                window.modernAuth.authenticatedFetch(`/inventory/delete-stock-by-row?row_prefix=${encodeURIComponent(rowPrefix)}`, {
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
            alert(`❌ Errore scarico container: ${error.message}`);
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
            alert(`❌ Errore ubicazione da terra: ${error.message}`);
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

    // === NUOVI FORM UBICAZIONE DA TERRA ===
    
    // Form ubicazione da terra manuale (nuovo tab nelle operazioni manuali)
    document.getElementById('relocate-ground-manual-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const sku = document.getElementById('relocate-ground-product-sku').value.trim();
        const quantity = parseInt(document.getElementById('relocate-ground-quantity').value) || 0;
        const location = document.getElementById('relocate-ground-location').value.trim().toUpperCase();
        
        if (!sku) {
            alert('Inserisci un SKU valido');
            return;
        }
        
        if (!location) {
            alert('Inserisci un\'ubicazione valida');
            return;
        }
        
        if (quantity <= 0) {
            alert('Inserisci una quantità valida maggiore di 0');
            return;
        }
        
        // Utilizza la stessa logica del form originale
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Elaborazione...';
        
        fetch('/inventory/relocate-from-ground-manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku: sku,
                quantity: quantity,
                location: location
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errorData => {
                    throw new Error(errorData.detail || 'Errore sconosciuto');
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Risposta server:', data);
            if (data.message) {
                alert(`✅ ${data.message}`);
                closeOverlay('manual-operations-overlay');
                window.location.reload();
            } else {
                alert(`❌ Errore: ${JSON.stringify(data)}`);
            }
        })
        .catch(error => {
            console.error('Errore nella richiesta di ubicazione:', error);
            alert(`❌ Errore: ${error.message}`);
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        });
    });

    // Form ubicazione da terra da file (nuovo tab nelle operazioni da file)
    document.getElementById('relocate-ground-file-form').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('relocate-ground-file');
        const file = fileInput.files[0];
        
        if (!file) {
            console.log('Nessun file selezionato.');
            return;
        }
        
        // Utilizza la stessa logica del form originale
        const formData = new FormData();
        formData.append('file', file);
        
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Elaborazione...';
        
        fetch('/inventory/parse-relocate-from-ground-file', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.detail) {
                alert('Errore: ' + data.detail);
            } else {
                currentRecapFileName = file.name;
                showRelocateGroundRecap(data, 'Ubicazione da Terra da File');
                closeOverlay('file-operations-overlay');
            }
        })
        .catch(error => {
            console.error('Errore nell\'elaborazione del file:', error);
            alert('❌ Errore nell\'elaborazione del file');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        });
    });

    // Funzione per consolidare i record duplicati in TERRA
    window.consolidateGroundInventory = function() {
        if (!confirm('Vuoi consolidare i record duplicati dello stesso SKU in TERRA?\n\nQuesta operazione unirà tutti i record dello stesso prodotto in un singolo record con la quantità totale.')) {
            return;
        }

        window.modernAuth.authenticatedFetch('/inventory/consolidate-ground-inventory', {
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

// ========================================================================
// OPERAZIONI IN TEMPO REALE - HELPERS CONDIVISI
// ========================================================================

/**
 * Parse barcode prodotto con supporto qty esplicita
 * @param {string} barcodeValue - Barcode scansionato (es: "SKU123" o "SKU123_5")
 * @returns {object} - {sku, quantity, has_suffix}
 */
function parseProductBarcode(barcodeValue) {
    const parts = barcodeValue.split('_');

    if (parts.length === 2 && !isNaN(parts[1])) {
        return {
            sku: parts[0],
            quantity: parseInt(parts[1]),
            has_suffix: true
        };
    }

    return {
        sku: barcodeValue,
        quantity: 1,
        has_suffix: false
    };
}

/**
 * Valida se un barcode è un'ubicazione valida
 * @param {string} barcodeValue - Barcode da validare
 * @returns {Promise<boolean>} - true se è ubicazione valida
 */
async function validateLocation(barcodeValue) {
    const maxRetries = 2;
    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 sec timeout

            const response = await fetch('/inventory/validate-location', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({location: barcodeValue.toUpperCase()}),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            return result.is_location || false;
        } catch (error) {
            lastError = error;
            console.warn(`⚠️ Tentativo ${attempt + 1}/${maxRetries + 1} validazione ubicazione fallito:`, error.message);

            // Se non è l'ultimo tentativo, aspetta un po' prima di riprovare
            if (attempt < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, 300));
            }
        }
    }

    // Tutti i tentativi falliti
    console.error('❌ Validazione ubicazione fallita dopo tutti i tentativi:', lastError);
    showRealtimeFeedback('⚠️ Errore di rete. Riprova la scansione.', '#ffc107');
    return false;
}

/**
 * Valida e converte barcode prodotto (EAN → SKU se necessario)
 * @param {string} barcodeValue - Barcode da validare
 * @returns {Promise<string|null>} - SKU prodotto o null se non trovato
 */
async function validateProductBarcode(barcodeValue) {
    const maxRetries = 2;
    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 sec timeout

            const response = await fetch('/inventory/validate-barcode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({barcode: barcodeValue}),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();

            // Se prodotto non trovato (ma risposta OK), ritorna subito null
            if (!result.found) {
                return null;
            }

            return result.product_sku;
        } catch (error) {
            lastError = error;
            console.warn(`⚠️ Tentativo ${attempt + 1}/${maxRetries + 1} validazione prodotto fallito:`, error.message);

            // Se non è l'ultimo tentativo, aspetta un po' prima di riprovare
            if (attempt < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, 300));
            }
        }
    }

    // Tutti i tentativi falliti - errore di rete
    console.error('❌ Validazione prodotto fallita dopo tutti i tentativi:', lastError);
    showRealtimeFeedback('⚠️ Errore di rete. Riprova la scansione.', '#ffc107');
    return null;
}

/**
 * Mostra feedback visivo per operazioni realtime
 * @param {string} message - Messaggio da mostrare
 * @param {string} color - Colore del messaggio (hex)
 * @param {string} containerId - ID del container feedback (default: 'realtime-feedback')
 */
function showRealtimeFeedback(message, color, containerId = 'realtime-feedback') {
    const feedback = document.getElementById(containerId);
    if (!feedback) {
        console.warn(`Container feedback ${containerId} non trovato`);
        return;
    }

    feedback.textContent = message;
    feedback.style.color = color;
    feedback.style.backgroundColor = color + '22';
    feedback.style.padding = '10px';
    feedback.style.borderRadius = '5px';
    feedback.style.marginBottom = '10px';
    feedback.style.transition = 'all 0.3s ease';

    // Auto-fade dopo 3 secondi
    setTimeout(() => {
        feedback.style.backgroundColor = 'transparent';
    }, 3000);
}

/**
 * Aggiorna lista prodotti visualizzata
 * @param {Array} products - Array di prodotti [{sku, quantity, scanned_count}]
 * @param {string} containerId - ID del container lista prodotti
 */
function updateRealtimeProductList(products, containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.warn(`Container ${containerId} non trovato`);
        return;
    }

    if (products.length === 0) {
        container.innerHTML = '<p style="color: #6c757d; text-align: center; padding: 20px;">Nessun prodotto scansionato</p>';
        return;
    }

    container.innerHTML = products.map((p, index) => {
        const displayQty = (p.explicit_qty || 0) + (p.scanned_count || 0) || p.quantity || 1;

        // Check if this product is in edit mode
        if (p._isEditing) {
            return `
                <div class="realtime-product-item editing" data-index="${index}">
                    <span class="realtime-product-sku"><strong>${p.sku}</strong></span>
                    <div class="realtime-qty-edit">
                        <input type="number"
                               id="qty-edit-${index}"
                               class="realtime-qty-input"
                               value="${displayQty}"
                               min="1"
                               step="1"
                               inputmode="numeric"
                               onkeypress="if(event.key==='Enter') saveRealtimeQuantity(${index})">
                        <button class="realtime-qty-btn save" onclick="saveRealtimeQuantity(${index})" title="Salva">✓</button>
                        <button class="realtime-qty-btn cancel" onclick="cancelRealtimeQuantityEdit(${index})" title="Annulla">✕</button>
                    </div>
                </div>
            `;
        }

        return `
            <div class="realtime-product-item" data-index="${index}">
                <span class="realtime-product-sku"><strong>${p.sku}</strong></span>
                <span class="realtime-product-qty clickable"
                      onclick="editRealtimeQuantity(${index}, ${displayQty})"
                      title="Clicca per modificare">
                    ${displayQty} pz ✏️
                </span>
                <button class="realtime-product-remove" onclick="removeRealtimeProduct(${index})" title="Rimuovi">
                    ❌
                </button>
            </div>
        `;
    }).join('');
}

/**
 * Attiva modalità modifica quantità per un prodotto
 * @param {number} index - Indice prodotto in realtimeProducts[]
 * @param {number} currentQty - Quantità attuale visualizzata
 */
function editRealtimeQuantity(index, currentQty) {
    if (index >= 0 && index < realtimeProducts.length) {
        // Imposta flag editing
        realtimeProducts[index]._isEditing = true;
        realtimeProducts[index]._originalQty = currentQty;

        // Ri-render lista
        updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

        // Auto-focus sull'input
        setTimeout(() => {
            const input = document.getElementById(`qty-edit-${index}`);
            if (input) {
                input.focus();
                input.select();
            }
        }, 50);
    }
}

/**
 * Salva la quantità modificata
 * @param {number} index - Indice prodotto in realtimeProducts[]
 */
function saveRealtimeQuantity(index) {
    if (index >= 0 && index < realtimeProducts.length) {
        const input = document.getElementById(`qty-edit-${index}`);
        if (!input) return;

        const newQty = parseInt(input.value);

        // Validazione
        if (isNaN(newQty) || newQty < 1) {
            showRealtimeFeedback('⚠️ Quantità non valida (minimo 1)', '#dc3545');
            input.focus();
            return;
        }

        // Aggiorna il prodotto: imposta explicit_qty e azzera scanned_count
        realtimeProducts[index].explicit_qty = newQty;
        realtimeProducts[index].scanned_count = 0;
        realtimeProducts[index]._isEditing = false;
        delete realtimeProducts[index]._originalQty;

        // Ri-render lista
        updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

        // Feedback positivo
        showRealtimeFeedback(`✅ Quantità ${realtimeProducts[index].sku} aggiornata a ${newQty}`, '#28a745');
    }
}

/**
 * Annulla la modifica quantità
 * @param {number} index - Indice prodotto in realtimeProducts[]
 */
function cancelRealtimeQuantityEdit(index) {
    if (index >= 0 && index < realtimeProducts.length) {
        // Rimuovi flag editing
        realtimeProducts[index]._isEditing = false;
        delete realtimeProducts[index]._originalQty;

        // Ri-render lista
        updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

        // Feedback
        showRealtimeFeedback('↩️ Modifica annullata', '#6c757d');
    }
}

/**
 * Valida esistenza ubicazione (verifica nel database)
 * @param {string} location - Nome ubicazione
 * @returns {Promise<boolean>} - true se esiste
 */
async function validateLocationExists(location) {
    return await validateLocation(location);
}

/**
 * Setup autofocus e readonly per input scanner mobile
 * @param {string} inputId - ID dell'input scanner
 */
function setupRealtimeScannerInput(inputId) {
    const input = document.getElementById(inputId);
    if (!input) {
        console.warn(`Input scanner ${inputId} non trovato`);
        return;
    }

    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
                     || window.innerWidth < 768;

    if (isMobile) {
        // Impedisce tastiera virtuale
        input.readOnly = true;
        input.setAttribute('inputmode', 'none');

        // Autofocus immediato
        setTimeout(() => {
            input.focus();
        }, 150);

        // Toggle readonly al primo input
        input.addEventListener('keydown', function(e) {
            if (this.readOnly && e.key !== 'Tab') {
                this.readOnly = false;
            }
        });

        // Auto-refocus quando perde focus
        input.addEventListener('blur', function() {
            setTimeout(() => {
                const overlayVisible = document.getElementById('realtime-scanner-interface')?.style.display !== 'none';
                // NON refocus se l'utente sta editando una quantità
                const qtyEditActive = document.querySelector('.realtime-qty-input');
                if (overlayVisible && !qtyEditActive) {
                    this.focus();
                    if (!this.value) {
                        this.readOnly = true;
                    }
                }
            }, 100);
        });
    }

    // Enter per processare
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();

            // Piccolo delay per assicurarsi che lo scanner finisca di scrivere
            // Prima di processare il barcode
            setTimeout(() => {
                const value = this.value.trim();
                if (value) {
                    processRealtimeBarcode(value);
                    this.value = '';
                }
            }, 50); // 50ms di delay
        }
    });
}

// ========================================================================
// OPERAZIONI IN TEMPO REALE - GESTIONE INTERFACCIA
// ========================================================================

// Variabili globali per stato operazione
let currentRealtimeOperation = null;
let realtimeProducts = [];
let realtimeSessionData = {};

/**
 * Avvia un'operazione in tempo reale
 * @param {string} operationType - Tipo operazione (CARICO, SCARICO, etc.)
 */
function startRealtimeOperation(operationType) {
    currentRealtimeOperation = operationType;
    realtimeProducts = [];
    realtimeSessionData = {
        operationType: operationType,
        awaitingLocation: false,
        locationValidated: false,
        location: null,
        originLocation: null,
        destinationLocation: null
    };

    // Chiudi menu principale
    closeOverlay('realtime-operations-overlay');

    // Mostra interfaccia scanner
    document.getElementById('realtime-scanner-interface').style.display = 'block';

    // Aggiorna titolo
    const titles = {
        'SCARICO_CONTAINER': '📦 Scarico Container in Tempo Reale',
        'CARICO': '🔼 Carico in Tempo Reale',
        'SCARICO': '🔽 Scarico in Tempo Reale',
        'SPOSTAMENTO': '🔄 Spostamento in Tempo Reale',
        'UBICAZIONE_TERRA': '📍 Posiziona da TERRA in Tempo Reale'
    };
    document.getElementById('scanner-title').textContent = titles[operationType] || '⚡ Operazione in Tempo Reale';

    // Setup input scanner
    setupRealtimeScannerInput('realtime-barcode-input');

    // Mostra feedback iniziale
    showRealtimeFeedback('📱 Pronto per la scansione...', '#007bff');
}

/**
 * Processa barcode scansionato (dispatcher per operazione corrente)
 * @param {string} barcodeValue - Barcode scansionato
 */
async function processRealtimeBarcode(barcodeValue) {
    if (!currentRealtimeOperation) {
        console.error('Nessuna operazione attiva');
        return;
    }

    // Dispatch alla funzione specifica dell'operazione
    switch (currentRealtimeOperation) {
        case 'SCARICO_CONTAINER':
            await processScaricoContainerBarcode(barcodeValue);
            break;
        case 'CARICO':
            await processCaricoBarcode(barcodeValue);
            break;
        case 'SCARICO':
            await processScaricoBarcode(barcodeValue);
            break;
        case 'SPOSTAMENTO':
            await processSpostamentoBarcode(barcodeValue);
            break;
        case 'UBICAZIONE_TERRA':
            await processUbicazioneTerraBarcode(barcodeValue);
            break;
        default:
            console.error('Operazione non supportata:', currentRealtimeOperation);
    }
}

/**
 * Annulla operazione in corso
 */
function cancelRealtimeOperation() {
    if (realtimeProducts.length > 0) {
        if (!confirm('Annullare l\'operazione in corso? Tutti i dati scansionati saranno persi.')) {
            return;
        }
    }

    // Reset stato
    currentRealtimeOperation = null;
    realtimeProducts = [];
    realtimeSessionData = {};

    // Reset UI
    document.getElementById('realtime-scanner-interface').style.display = 'none';
    document.getElementById('scanned-products-list').innerHTML = '';
    document.getElementById('realtime-feedback').textContent = '';
    document.getElementById('realtime-barcode-input').value = '';
    document.getElementById('finalize-realtime-btn').style.display = 'none';

    // Riapri menu principale
    openOverlay('realtime-operations-overlay');
}

/**
 * Finalizza operazione in corso (dispatcher)
 */
async function finalizeRealtimeOperation() {
    if (!currentRealtimeOperation) {
        console.error('Nessuna operazione attiva');
        return;
    }

    // Dispatch alla funzione di finalizzazione specifica
    switch (currentRealtimeOperation) {
        case 'SCARICO_CONTAINER':
            await finalizeScaricoContainer();
            break;
        case 'CARICO':
            await finalizeCarico();
            break;
        case 'SCARICO':
            await finalizeScarico();
            break;
        case 'SPOSTAMENTO':
            await finalizeSpostamento();
            break;
        case 'UBICAZIONE_TERRA':
            await finalizeUbicazioneTerra();
            break;
        default:
            console.error('Operazione non supportata:', currentRealtimeOperation);
    }
}

/**
 * Rimuovi prodotto dalla lista scansionata
 * @param {number} index - Indice prodotto da rimuovere
 */
function removeRealtimeProduct(index) {
    if (index >= 0 && index < realtimeProducts.length) {
        const removed = realtimeProducts.splice(index, 1)[0];
        updateRealtimeProductList(realtimeProducts, 'scanned-products-list');
        showRealtimeFeedback(`🗑️ Rimosso ${removed.sku}`, '#6c757d');
    }
}

// ========================================================================
// OPERAZIONE: SCARICO CONTAINER IN TEMPO REALE
// ========================================================================

/**
 * Processa barcode per scarico container (modalità continua)
 * @param {string} barcodeValue - Barcode scansionato
 */
async function processScaricoContainerBarcode(barcodeValue) {
    // Parse barcode prodotto
    const parsed = parseProductBarcode(barcodeValue);

    // Valida che esista il prodotto
    const validSku = await validateProductBarcode(parsed.sku);
    if (!validSku) {
        showRealtimeFeedback(`❌ Prodotto ${parsed.sku} non trovato!`, '#dc3545');
        return;
    }

    // Aggiorna SKU se era EAN
    if (validSku !== parsed.sku) {
        parsed.sku = validSku;
    }

    // Trova se già scansionato
    const existing = realtimeProducts.find(p => p.sku === parsed.sku);

    if (existing) {
        // Scarico Container: SEMPRE accumula quantità (anche qty esplicite multiple)
        if (parsed.has_suffix) {
            // Scansione con qty esplicita: aggiungi alla qty esplicita totale (NON resettare scanned_count!)
            existing.explicit_qty = (existing.explicit_qty || 0) + parsed.quantity;
            const totalQty = (existing.explicit_qty || 0) + (existing.scanned_count || 0);
            showRealtimeFeedback(`✅ ${parsed.sku} +${parsed.quantity} (totale: ${totalQty} pz)`, '#28a745');
        } else {
            // Scansione senza qty: incrementa count
            existing.scanned_count = (existing.scanned_count || 0) + 1;
            const totalQty = (existing.explicit_qty || 0) + existing.scanned_count;
            showRealtimeFeedback(`✅ ${parsed.sku} +1 (totale: ${totalQty} pz)`, '#28a745');
        }
    } else {
        // Nuovo prodotto
        realtimeProducts.push({
            sku: parsed.sku,
            scanned_count: parsed.has_suffix ? 0 : 1,
            explicit_qty: parsed.has_suffix ? parsed.quantity : 0,
            has_qty_suffix: parsed.has_suffix
        });
        const qty = parsed.quantity || 1;
        showRealtimeFeedback(`✅ ${parsed.sku} aggiunto (${qty} pz) → TERRA`, '#28a745');
    }

    // Aggiorna display lista prodotti
    updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

    // Mostra tasto finalizza se ci sono prodotti
    if (realtimeProducts.length > 0) {
        document.getElementById('finalize-realtime-btn').style.display = 'block';
    }
}

/**
 * Finalizza scarico container
 */
async function finalizeScaricoContainer() {
    if (realtimeProducts.length === 0) {
        showRealtimeFeedback('❌ Nessun prodotto scansionato!', '#dc3545');
        return;
    }

    // Conferma operazione
    const totalProducts = realtimeProducts.length;
    const totalQty = realtimeProducts.reduce((sum, p) => sum + ((p.explicit_qty || 0) + p.scanned_count), 0);

    if (!confirm(`Confermare scarico container?\n\n${totalProducts} prodotti diversi\n${totalQty} pezzi totali\n\nTutto verrà spostato a TERRA.`)) {
        return;
    }

    // Mostra loading
    showRealtimeFeedback('⏳ Finalizzazione in corso...', '#ffc107');
    document.getElementById('finalize-realtime-btn').disabled = true;

    try {
        // Prepara operazioni (somma explicit_qty + scanned_count)
        const operations = realtimeProducts.map(p => ({
            product_sku: p.sku,
            quantity: (p.explicit_qty || 0) + p.scanned_count
        }));

        // API Call
        const response = await fetch('/inventory/realtime/scarico-container/finalize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                operations: operations
            })
        });

        const result = await response.json();

        if (result.success) {
            showRealtimeFeedback(`✅ Scarico container completato! ${totalProducts} prodotti aggiunti a TERRA`, '#28a745');

            // Mostra riepilogo
            setTimeout(() => {
                alert(`Scarico Container Completato!\n\n` +
                      `✅ ${totalProducts} prodotti diversi\n` +
                      `✅ ${totalQty} pezzi totali\n` +
                      `✅ Tutto aggiunto a TERRA con consolidamento automatico`);

                // Reset e chiudi
                resetScaricoContainerSession();
                setTimeout(() => {
                    document.getElementById('realtime-scanner-interface').style.display = 'none';
                    openOverlay('realtime-operations-overlay');

                    // Ricarica inventario per mostrare aggiornamenti
                    if (typeof loadInventoryData === 'function') {
                        loadInventoryData();
                    }
                }, 1000);
            }, 500);
        } else {
            showRealtimeFeedback(`❌ Errore: ${result.message}`, '#dc3545');
            document.getElementById('finalize-realtime-btn').disabled = false;
        }
    } catch (error) {
        console.error('Errore finalizzazione scarico container:', error);
        showRealtimeFeedback(`❌ Errore durante la finalizzazione: ${error.message}`, '#dc3545');
        document.getElementById('finalize-realtime-btn').disabled = false;
    }
}

/**
 * Reset sessione scarico container
 */
function resetScaricoContainerSession() {
    realtimeProducts = [];
    realtimeSessionData = {};
    currentRealtimeOperation = null;
    document.getElementById('scanned-products-list').innerHTML = '';
    document.getElementById('realtime-feedback').textContent = '';
    document.getElementById('realtime-barcode-input').value = '';
    document.getElementById('finalize-realtime-btn').style.display = 'none';
    document.getElementById('finalize-realtime-btn').disabled = false;
}

// ========================================================================
// OPERAZIONE: CARICO IN TEMPO REALE
// ========================================================================

/**
 * CARICO - Scansiona ubicazione → Scansiona prodotti → Premi Finalizza (come Scarico)
 * @param {string} barcodeValue - Barcode scansionato
 */
async function processCaricoBarcode(barcodeValue) {
    // STEP 1: Prima scansione deve essere l'ubicazione
    if (!realtimeSessionData.location) {
        const isLocation = await validateLocation(barcodeValue);

        if (!isLocation) {
            showRealtimeFeedback('❌ Prima scansione deve essere un\'ubicazione valida!', '#dc3545');
            return;
        }

        // Salva ubicazione
        realtimeSessionData.location = barcodeValue.toUpperCase();
        showRealtimeFeedback(`📍 Ubicazione: ${realtimeSessionData.location}. Scansiona prodotti da caricare...`, '#007bff');
        return;
    }

    // STEP 2: È un prodotto - accumula quantità
    const parsed = parseProductBarcode(barcodeValue);

    // Valida che esista il prodotto
    const validSku = await validateProductBarcode(parsed.sku);
    if (!validSku) {
        showRealtimeFeedback(`❌ Prodotto ${parsed.sku} non trovato!`, '#dc3545');
        return;
    }

    // Aggiorna SKU se era EAN
    if (validSku !== parsed.sku) {
        parsed.sku = validSku;
    }

    // Trova se già scansionato
    const existing = realtimeProducts.find(p => p.sku === parsed.sku);

    if (existing) {
        // Accumula quantità (come Scarico Container)
        if (parsed.has_suffix) {
            existing.explicit_qty = (existing.explicit_qty || 0) + parsed.quantity;
            const totalQty = (existing.explicit_qty || 0) + (existing.scanned_count || 0);
            showRealtimeFeedback(`✅ ${parsed.sku} +${parsed.quantity} (totale: ${totalQty} pz)`, '#28a745');
        } else {
            existing.scanned_count = (existing.scanned_count || 0) + 1;
            const totalQty = (existing.explicit_qty || 0) + existing.scanned_count;
            showRealtimeFeedback(`✅ ${parsed.sku} +1 (totale: ${totalQty} pz)`, '#28a745');
        }
    } else {
        // Nuovo prodotto
        realtimeProducts.push({
            sku: parsed.sku,
            scanned_count: parsed.has_suffix ? 0 : 1,
            explicit_qty: parsed.has_suffix ? parsed.quantity : 0,
            has_qty_suffix: parsed.has_suffix
        });
        const qty = parsed.quantity || 1;
        showRealtimeFeedback(`✅ ${parsed.sku} aggiunto (${qty} pz)`, '#28a745');
    }

    // Aggiorna display
    updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

    // Mostra pulsante finalizza
    if (realtimeProducts.length > 0) {
        document.getElementById('finalize-realtime-btn').style.display = 'block';
        document.getElementById('realtime-status').textContent = '✅ Prodotti scansionati. Premi Finalizza quando pronto';
    }
}

/**
 * Finalizza carico
 */
async function finalizeCarico() {
    if (realtimeProducts.length === 0) {
        showRealtimeFeedback('❌ Nessun prodotto scansionato!', '#dc3545');
        return;
    }

    // Se ubicazione non ancora scansionata, avvisa
    if (!realtimeSessionData.location) {
        showRealtimeFeedback('❌ Scansiona prima l\'ubicazione destinazione!', '#dc3545');
        return;
    }

    // Procedi con finalizzazione
    await executeCaricoFinalization();
}

/**
 * Esegue la finalizzazione del carico
 */
async function executeCaricoFinalization() {
    if (!realtimeSessionData.location) {
        showRealtimeFeedback('❌ Ubicazione destinazione non specificata!', '#dc3545');
        return;
    }

    // Conferma operazione
    const totalProducts = realtimeProducts.length;
    const totalQty = realtimeProducts.reduce((sum, p) => sum + ((p.explicit_qty || 0) + p.scanned_count), 0);

    if (!confirm(`Confermare carico?\n\n${totalProducts} prodotti diversi\n${totalQty} pezzi totali\n\n→ Ubicazione: ${realtimeSessionData.location}`)) {
        realtimeSessionData.awaitingLocation = false;
        realtimeSessionData.location = null;
        return;
    }

    // Mostra loading
    showRealtimeFeedback('⏳ Finalizzazione in corso...', '#ffc107');

    try {
        // Prepara operazioni
        const operations = realtimeProducts.map(p => ({
            product_sku: p.sku,
            quantity: (p.explicit_qty || 0) + p.scanned_count
        }));

        // API Call
        const response = await fetch('/inventory/realtime/carico/finalize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                location: realtimeSessionData.location,
                operations: operations
            })
        });

        const result = await response.json();

        if (result.success) {
            showRealtimeFeedback(`✅ Carico completato! ${totalProducts} prodotti aggiunti a ${realtimeSessionData.location}`, '#28a745');

            // Mostra riepilogo
            setTimeout(() => {
                alert(`Carico Completato!\n\n` +
                      `✅ ${totalProducts} prodotti diversi\n` +
                      `✅ ${totalQty} pezzi totali\n` +
                      `✅ Ubicazione: ${realtimeSessionData.location}`);

                // Reset e chiudi
                resetCaricoSession();
                setTimeout(() => {
                    document.getElementById('realtime-scanner-interface').style.display = 'none';
                    openOverlay('realtime-operations-overlay');

                    // Ricarica inventario
                    if (typeof loadInventoryData === 'function') {
                        loadInventoryData();
                    }
                }, 1000);
            }, 500);
        } else {
            showRealtimeFeedback(`❌ Errore: ${result.message}`, '#dc3545');
            realtimeSessionData.awaitingLocation = false;
            realtimeSessionData.location = null;
        }
    } catch (error) {
        console.error('Errore finalizzazione carico:', error);
        showRealtimeFeedback(`❌ Errore durante la finalizzazione: ${error.message}`, '#dc3545');
        realtimeSessionData.awaitingLocation = false;
        realtimeSessionData.location = null;
    }
}

/**
 * Reset sessione carico
 */
function resetCaricoSession() {
    realtimeProducts = [];
    realtimeSessionData = {};
    currentRealtimeOperation = null;
    document.getElementById('scanned-products-list').innerHTML = '';
    document.getElementById('realtime-feedback').textContent = '';
    document.getElementById('realtime-barcode-input').value = '';
    document.getElementById('realtime-status').textContent = '📱 Pronto per la scansione...';
}

/**
 * SCARICO - Scansiona ubicazione → Scansiona prodotti da scaricare
 */
async function processScaricoBarcode(barcodeValue) {
    // STEP 1: Prima scansione deve essere l'ubicazione
    if (!realtimeSessionData.location) {
        const isLocation = await validateLocation(barcodeValue);

        if (!isLocation) {
            showRealtimeFeedback('❌ Prima scansione deve essere un\'ubicazione valida!', '#dc3545');
            return;
        }

        // Salva ubicazione
        realtimeSessionData.location = barcodeValue.toUpperCase();
        showRealtimeFeedback(`📍 Ubicazione: ${realtimeSessionData.location}. Scansiona prodotti da scaricare...`, '#007bff');
        return;
    }

    // STEP 2: È un prodotto - valida e accumula
    const parsed = parseProductBarcode(barcodeValue);
    const validSku = await validateProductBarcode(parsed.sku);

    if (!validSku) {
        showRealtimeFeedback(`❌ Prodotto ${parsed.sku} non trovato nel sistema`, '#dc3545');
        return;
    }

    // Verifica se prodotto già scansionato (usa validSku convertito da EAN)
    const existing = realtimeProducts.find(p => p.sku === validSku);

    if (existing) {
        // Accumula quantità (come in Scarico Container e Carico)
        if (parsed.has_suffix) {
            // Scansione con qty esplicita: aggiungi (NON resettare scanned_count!)
            existing.explicit_qty = (existing.explicit_qty || 0) + parsed.quantity;
            const totalQty = (existing.explicit_qty || 0) + (existing.scanned_count || 0);
            showRealtimeFeedback(`✅ ${validSku} +${parsed.quantity} (totale: ${totalQty} pz)`, '#28a745');
        } else {
            // Scansione senza qty: incrementa count
            existing.scanned_count = (existing.scanned_count || 0) + 1;
            const totalQty = (existing.explicit_qty || 0) + existing.scanned_count;
            showRealtimeFeedback(`✅ ${validSku} +1 (totale: ${totalQty} pz)`, '#28a745');
        }
    } else {
        // Nuovo prodotto (usa validSku convertito da EAN)
        const newProduct = {
            sku: validSku,
            scanned_count: parsed.has_suffix ? 0 : 1,
            explicit_qty: parsed.has_suffix ? parsed.quantity : 0
        };
        realtimeProducts.push(newProduct);

        const displayQty = parsed.has_suffix ? parsed.quantity : 1;
        showRealtimeFeedback(`✅ ${validSku} aggiunto (${displayQty} pz)`, '#28a745');
    }

    // Aggiorna lista UI
    updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

    // Mostra pulsante finalizza se ci sono prodotti
    if (realtimeProducts.length > 0) {
        document.getElementById('finalize-realtime-btn').style.display = 'block';
    }
}

/**
 * SPOSTAMENTO - Modalità doppia:
 * 1. TOTALE: Scansiona origine → Scansiona destinazione (sposta tutti i prodotti)
 * 2. PARZIALE: Scansiona origine → Scansiona prodotti → Scansiona destinazione (sposta prodotti specifici)
 */
async function processSpostamentoBarcode(barcodeValue) {
    // STEP 1: Prima scansione deve essere ubicazione origine
    if (!realtimeSessionData.locationFrom) {
        const isLocation = await validateLocation(barcodeValue);

        if (!isLocation) {
            showRealtimeFeedback('❌ Prima scansione deve essere ubicazione origine!', '#dc3545');
            return;
        }

        // Salva ubicazione origine
        realtimeSessionData.locationFrom = barcodeValue.toUpperCase();
        showRealtimeFeedback(`📍 Origine: ${realtimeSessionData.locationFrom}. Scansiona prodotti o destinazione...`, '#007bff');
        return;
    }

    // STEP 2: Determina se è ubicazione (destinazione) o prodotto (mode parziale)
    const isLocation = await validateLocation(barcodeValue);

    if (isLocation) {
        // È una ubicazione destinazione
        realtimeSessionData.locationTo = barcodeValue.toUpperCase();

        if (realtimeSessionData.locationFrom === realtimeSessionData.locationTo) {
            showRealtimeFeedback('❌ Origine e destinazione non possono essere uguali!', '#dc3545');
            realtimeSessionData.locationTo = null;
            return;
        }

        // Se ci sono prodotti scansionati → PARTIAL, altrimenti → TOTAL
        if (realtimeProducts.length > 0) {
            // MODALITÀ PARZIALE: Sposta solo i prodotti scansionati
            realtimeSessionData.moveMode = 'PARTIAL';
            showRealtimeFeedback(`📍 Destinazione: ${realtimeSessionData.locationTo}. Premi Finalizza per confermare.`, '#007bff');
            return finalizeSpostamento();
        } else {
            // MODALITÀ TOTALE: Sposta tutti i prodotti
            realtimeSessionData.moveMode = 'TOTAL';
            showRealtimeFeedback(`📍 Destinazione: ${realtimeSessionData.locationTo}. Spostamento TOTALE in corso...`, '#ffc107');
            return finalizeSpostamento();
        }
    }

    // MODALITÀ PARZIALE: È un prodotto - accumula
    realtimeSessionData.moveMode = 'PARTIAL';

    const parsed = parseProductBarcode(barcodeValue);
    const validSku = await validateProductBarcode(parsed.sku);

    if (!validSku) {
        showRealtimeFeedback(`❌ Prodotto ${parsed.sku} non trovato nel sistema`, '#dc3545');
        return;
    }

    // Verifica se prodotto già scansionato (usa validSku convertito da EAN)
    const existing = realtimeProducts.find(p => p.sku === validSku);

    if (existing) {
        // Accumula quantità
        if (parsed.has_suffix) {
            existing.explicit_qty = (existing.explicit_qty || 0) + parsed.quantity;
            const totalQty = (existing.explicit_qty || 0) + (existing.scanned_count || 0);
            showRealtimeFeedback(`✅ ${validSku} +${parsed.quantity} (totale: ${totalQty} pz)`, '#28a745');
        } else {
            existing.scanned_count = (existing.scanned_count || 0) + 1;
            const totalQty = (existing.explicit_qty || 0) + existing.scanned_count;
            showRealtimeFeedback(`✅ ${validSku} +1 (totale: ${totalQty} pz)`, '#28a745');
        }
    } else {
        // Nuovo prodotto (usa validSku convertito da EAN)
        const newProduct = {
            sku: validSku,
            scanned_count: parsed.has_suffix ? 0 : 1,
            explicit_qty: parsed.has_suffix ? parsed.quantity : 0
        };
        realtimeProducts.push(newProduct);

        const displayQty = parsed.has_suffix ? parsed.quantity : 1;
        showRealtimeFeedback(`✅ ${validSku} aggiunto (${displayQty} pz). Scansiona altri prodotti o destinazione...`, '#28a745');
    }

    // Aggiorna lista UI
    updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

    // In modalità parziale, mostra pulsante finalizza per scansionare destinazione
    if (realtimeProducts.length > 0) {
        document.getElementById('finalize-realtime-btn').style.display = 'block';
        document.getElementById('finalize-realtime-btn').textContent = 'Scansiona destinazione o premi qui';
    }
}

/**
 * POSIZIONA DA TERRA - Scansiona prodotti da TERRA → Scansiona ubicazione destinazione
 */
/**
 * UBICAZIONE DA TERRA - Scansiona ubicazione → Scansiona prodotti → Premi Finalizza (come Carico)
 */
async function processUbicazioneTerraBarcode(barcodeValue) {
    // STEP 1: Prima scansione deve essere l'ubicazione di destinazione
    if (!realtimeSessionData.location) {
        const isLocation = await validateLocation(barcodeValue);

        if (!isLocation) {
            showRealtimeFeedback('❌ Prima scansione deve essere un\'ubicazione valida!', '#dc3545');
            return;
        }

        // Salva ubicazione
        realtimeSessionData.location = barcodeValue.toUpperCase();
        showRealtimeFeedback(`📍 Ubicazione: ${realtimeSessionData.location}. Scansiona prodotti da spostare da TERRA...`, '#007bff');
        return;
    }

    // STEP 2: È un prodotto - valida e accumula
    const parsed = parseProductBarcode(barcodeValue);
    const validSku = await validateProductBarcode(parsed.sku);

    if (!validSku) {
        showRealtimeFeedback(`❌ Prodotto ${parsed.sku} non trovato nel sistema`, '#dc3545');
        return;
    }

    // Verifica se prodotto già scansionato (usa validSku convertito da EAN)
    const existing = realtimeProducts.find(p => p.sku === validSku);

    if (existing) {
        // Accumula quantità
        if (parsed.has_suffix) {
            existing.explicit_qty = (existing.explicit_qty || 0) + parsed.quantity;
            const totalQty = (existing.explicit_qty || 0) + (existing.scanned_count || 0);
            showRealtimeFeedback(`✅ ${validSku} +${parsed.quantity} (totale: ${totalQty} pz)`, '#28a745');
        } else {
            existing.scanned_count = (existing.scanned_count || 0) + 1;
            const totalQty = (existing.explicit_qty || 0) + existing.scanned_count;
            showRealtimeFeedback(`✅ ${validSku} +1 (totale: ${totalQty} pz)`, '#28a745');
        }
    } else {
        // Nuovo prodotto (usa validSku convertito da EAN)
        const newProduct = {
            sku: validSku,
            scanned_count: parsed.has_suffix ? 0 : 1,
            explicit_qty: parsed.has_suffix ? parsed.quantity : 0
        };
        realtimeProducts.push(newProduct);

        const displayQty = parsed.has_suffix ? parsed.quantity : 1;
        showRealtimeFeedback(`✅ ${validSku} aggiunto (${displayQty} pz)`, '#28a745');
    }

    // Aggiorna lista UI
    updateRealtimeProductList(realtimeProducts, 'scanned-products-list');

    // Mostra pulsante finalizza se ci sono prodotti
    if (realtimeProducts.length > 0) {
        document.getElementById('finalize-realtime-btn').style.display = 'block';
        document.getElementById('realtime-status').textContent = '✅ Prodotti scansionati. Premi Finalizza quando pronto';
    }
}

/**
 * Finalizza operazione Scarico
 */
async function finalizeScarico() {
    if (realtimeProducts.length === 0) {
        showRealtimeFeedback('❌ Nessun prodotto da scaricare!', '#dc3545');
        return;
    }

    if (!realtimeSessionData.location) {
        showRealtimeFeedback('❌ Ubicazione non impostata!', '#dc3545');
        return;
    }

    // Conferma operazione
    const totalItems = realtimeProducts.length;
    const totalQty = realtimeProducts.reduce((sum, p) => {
        return sum + (p.explicit_qty || 0) + p.scanned_count;
    }, 0);

    if (!confirm(`Confermare scarico di ${totalQty} pezzi (${totalItems} SKU) da ${realtimeSessionData.location}?`)) {
        return;
    }

    try {
        showRealtimeFeedback('⏳ Scarico in corso...', '#ffc107');

        // Prepara payload
        const operations = realtimeProducts.map(p => ({
            product_sku: p.sku,
            quantity: (p.explicit_qty || 0) + p.scanned_count
        }));

        const payload = {
            location: realtimeSessionData.location,
            operations: operations
        };

        // Chiamata API
        const response = await fetch('/inventory/realtime/scarico/finalize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (result.success) {
            showRealtimeFeedback(`✅ ${result.message}`, '#28a745');

            // Reset dopo successo
            setTimeout(() => {
                resetScaricoSession();
                cancelRealtimeOperation();
                loadInventory(); // Ricarica inventario
            }, 1500);
        } else {
            showRealtimeFeedback(`❌ ${result.message}`, '#dc3545');
        }
    } catch (error) {
        console.error('Errore finalizzazione scarico:', error);
        showRealtimeFeedback('❌ Errore durante la finalizzazione: ' + error.message, '#dc3545');
    }
}

/**
 * Reset sessione Scarico
 */
function resetScaricoSession() {
    realtimeProducts = [];
    realtimeSessionData = {};
    document.getElementById('scanned-products-list').innerHTML = '';
    document.getElementById('finalize-realtime-btn').style.display = 'none';
    document.getElementById('realtime-barcode-input').value = '';
    document.getElementById('realtime-status').textContent = '📱 Pronto per la scansione...';
}

/**
 * Finalizza operazione Spostamento
 */
async function finalizeSpostamento() {
    if (!realtimeSessionData.locationFrom) {
        showRealtimeFeedback('❌ Ubicazione origine non impostata!', '#dc3545');
        return;
    }

    // In modalità parziale, richiedi destinazione se non ancora scansionata
    if (realtimeSessionData.moveMode === 'PARTIAL' && !realtimeSessionData.locationTo) {
        // Mostra prompt per scansionare destinazione
        showRealtimeFeedback('📍 Scansiona ubicazione destinazione...', '#ffc107');

        // Imposta flag per aspettare destinazione
        realtimeSessionData.awaitingDestination = true;

        // Listener temporaneo per catturare prossima scansione come destinazione
        const originalHandler = document.getElementById('realtime-barcode-input').onkeypress;

        document.getElementById('realtime-barcode-input').onkeypress = async function(e) {
            if (e.key === 'Enter' && this.value.trim()) {
                const destValue = this.value.trim();
                this.value = '';

                const isLocation = await validateLocation(destValue);

                if (!isLocation) {
                    showRealtimeFeedback('❌ Deve essere una ubicazione valida!', '#dc3545');
                    return;
                }

                realtimeSessionData.locationTo = destValue.toUpperCase();

                if (realtimeSessionData.locationFrom === realtimeSessionData.locationTo) {
                    showRealtimeFeedback('❌ Origine e destinazione non possono essere uguali!', '#dc3545');
                    realtimeSessionData.locationTo = null;
                    return;
                }

                // Ripristina handler originale
                document.getElementById('realtime-barcode-input').onkeypress = originalHandler;

                // Procedi con finalizzazione
                await executeSpostamentoFinalization();
            }
        };

        return;
    }

    // Modalità totale o modalità parziale con destinazione già impostata
    await executeSpostamentoFinalization();
}

/**
 * Esegue la finalizzazione dello spostamento
 */
async function executeSpostamentoFinalization() {
    const mode = realtimeSessionData.moveMode || 'TOTAL';

    // Conferma operazione
    let confirmMessage;
    if (mode === 'TOTAL') {
        confirmMessage = `Confermare spostamento TOTALE da ${realtimeSessionData.locationFrom} a ${realtimeSessionData.locationTo}?`;
    } else {
        const totalQty = realtimeProducts.reduce((sum, p) => {
            return sum + (p.explicit_qty || 0) + p.scanned_count;
        }, 0);
        confirmMessage = `Confermare spostamento di ${totalQty} pezzi (${realtimeProducts.length} SKU) da ${realtimeSessionData.locationFrom} a ${realtimeSessionData.locationTo}?`;
    }

    if (!confirm(confirmMessage)) {
        return;
    }

    try {
        showRealtimeFeedback('⏳ Spostamento in corso...', '#ffc107');

        // Prepara payload
        const payload = {
            location_from: realtimeSessionData.locationFrom,
            location_to: realtimeSessionData.locationTo,
            move_mode: mode
        };

        // In modalità parziale, aggiungi prodotti
        if (mode === 'PARTIAL') {
            payload.operations = realtimeProducts.map(p => ({
                product_sku: p.sku,
                quantity: (p.explicit_qty || 0) + p.scanned_count
            }));
        }

        // Chiamata API
        const response = await fetch('/inventory/realtime/spostamento/finalize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (result.success) {
            showRealtimeFeedback(`✅ ${result.message}`, '#28a745');

            // Reset dopo successo
            setTimeout(() => {
                resetSpostamentoSession();
                cancelRealtimeOperation();
                loadInventory(); // Ricarica inventario
            }, 1500);
        } else {
            showRealtimeFeedback(`❌ ${result.message}`, '#dc3545');
        }
    } catch (error) {
        console.error('Errore finalizzazione spostamento:', error);
        showRealtimeFeedback('❌ Errore durante la finalizzazione: ' + error.message, '#dc3545');
    }
}

/**
 * Reset sessione Spostamento
 */
function resetSpostamentoSession() {
    realtimeProducts = [];
    realtimeSessionData = {};
    document.getElementById('scanned-products-list').innerHTML = '';
    document.getElementById('finalize-realtime-btn').style.display = 'none';
    document.getElementById('finalize-realtime-btn').textContent = 'Finalizza';
    document.getElementById('realtime-barcode-input').value = '';
    document.getElementById('realtime-status').textContent = '📱 Pronto per la scansione...';
}

/**
 * Finalizza operazione Posiziona da TERRA
 */
async function finalizeUbicazioneTerra() {
    if (realtimeProducts.length === 0) {
        showRealtimeFeedback('❌ Nessun prodotto da posizionare!', '#dc3545');
        return;
    }

    if (!realtimeSessionData.location) {
        showRealtimeFeedback('❌ Ubicazione destinazione non impostata!', '#dc3545');
        return;
    }

    // Conferma operazione
    const totalItems = realtimeProducts.length;
    const totalQty = realtimeProducts.reduce((sum, p) => {
        return sum + (p.explicit_qty || 0) + p.scanned_count;
    }, 0);

    if (!confirm(`Confermare posizionamento di ${totalQty} pezzi (${totalItems} SKU) da TERRA a ${realtimeSessionData.location}?`)) {
        return;
    }

    try {
        showRealtimeFeedback('⏳ Posizionamento in corso...', '#ffc107');

        // Prepara payload
        const operations = realtimeProducts.map(p => ({
            product_sku: p.sku,
            quantity: (p.explicit_qty || 0) + p.scanned_count
        }));

        const payload = {
            destination: realtimeSessionData.location,
            operations: operations
        };

        // Chiamata API
        const response = await fetch('/inventory/realtime/ubicazione-terra/finalize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (result.success) {
            showRealtimeFeedback(`✅ ${result.message}`, '#28a745');

            // Reset dopo successo
            setTimeout(() => {
                resetUbicazioneTerraSession();
                cancelRealtimeOperation();
                loadInventory(); // Ricarica inventario
            }, 1500);
        } else {
            showRealtimeFeedback(`❌ ${result.message}`, '#dc3545');
        }
    } catch (error) {
        console.error('Errore finalizzazione ubicazione terra:', error);
        showRealtimeFeedback('❌ Errore durante la finalizzazione: ' + error.message, '#dc3545');
    }
}

/**
 * Reset sessione Ubicazione TERRA
 */
function resetUbicazioneTerraSession() {
    realtimeProducts = [];
    realtimeSessionData = {};
    document.getElementById('scanned-products-list').innerHTML = '';
    document.getElementById('finalize-realtime-btn').style.display = 'none';
    document.getElementById('realtime-barcode-input').value = '';
    document.getElementById('realtime-status').textContent = '📱 Pronto per la scansione...';
}