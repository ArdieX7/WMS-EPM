document.addEventListener("DOMContentLoaded", function() {
    const kpiContainer = document.getElementById("kpi-container");
    const totalStockTableBody = document.querySelector("#total-stock-table tbody");
    const productSkusDatalist = document.getElementById("product-skus");
    
    // Variabili per ricerca e ordinamento tabella principale
    let allStockData = [];
    let originalStockData = [];
    let filteredStockData = [];
    let currentSort = { column: null, direction: 'asc' };
    
    // Elementi di ricerca tabella principale
    const searchSkuTableInput = document.getElementById('search-sku-table');
    const resetSortBtn = document.getElementById('reset-sort-btn');
    
    // Variabili per export
    let currentSkuForExport = '';
    let currentRowForExport = '';

    // Caricamento dati iniziali della dashboard
    async function loadDashboardData() {
        try {
            const response = await fetch("/analysis/data");
            if (!response.ok) throw new Error("Errore nel caricamento dei dati di analisi.");
            const data = await response.json();

            // Popola i KPI organizzati per sezioni
            const kpis = data.kpis;
            const formattedInventoryValue = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(kpis.total_inventory_value);
            
            // Calcola giacenza totale in magazzino (scaffali + terra + uscita)
            const totalWarehouseStock = kpis.total_pieces_in_shelves + kpis.total_pieces_on_ground + kpis.total_pieces_outgoing;

            // Carica i dati pallet
            await loadPalletSummary();

            // Popola dashboard ultra-compatta (principale)
            loadUltraCompactDashboard(kpis, formattedInventoryValue, totalWarehouseStock);

            // Salva i dati per ordinamento e ricerca
            allStockData = data.total_stock_by_product;
            originalStockData = [...allStockData];
            filteredStockData = [...allStockData];
            
            // Applica ordinamento corrente se presente
            if (currentSort.column) {
                sortStockData(currentSort.column, currentSort.direction);
            } else {
                renderStockTable();
            }

        } catch (error) {
            console.error(error);
            kpiContainer.innerHTML = `<p>Impossibile caricare i dati della dashboard.</p>`;
        }
    }

    // Funzione per renderizzare la tabella delle giacenze
    function renderStockTable() {
        totalStockTableBody.innerHTML = '';
        filteredStockData.forEach(item => {
            const row = `<tr>
                <td>${item.sku}</td>
                <td>${item.description || 'N/D'}</td>
                <td>${item.quantity_in_shelves}</td>
                <td>${item.quantity_on_ground}</td>
                <td>${item.quantity_outgoing}</td>
                <td>${item.total_quantity}</td>
            </tr>`;
            totalStockTableBody.innerHTML += row;
        });
    }

    // Funzione per ordinare i dati delle giacenze
    function sortStockData(column, direction = 'asc') {
        const dataToSort = filteredStockData;
        
        dataToSort.sort((a, b) => {
            let aValue, bValue;
            
            switch(column) {
                case 'sku':
                    aValue = a.sku || '';
                    bValue = b.sku || '';
                    return direction === 'asc' ? 
                        aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
                        
                case 'description':
                    aValue = a.description || '';
                    bValue = b.description || '';
                    return direction === 'asc' ? 
                        aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
                        
                case 'scaffalata':
                    aValue = parseFloat(a.quantity_in_shelves) || 0;
                    bValue = parseFloat(b.quantity_in_shelves) || 0;
                    return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    
                case 'terra':
                    aValue = parseFloat(a.quantity_on_ground) || 0;
                    bValue = parseFloat(b.quantity_on_ground) || 0;
                    return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    
                case 'uscita':
                    aValue = parseFloat(a.quantity_outgoing) || 0;
                    bValue = parseFloat(b.quantity_outgoing) || 0;
                    return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    
                case 'totale':
                    aValue = parseFloat(a.total_quantity) || 0;
                    bValue = parseFloat(b.total_quantity) || 0;
                    return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    
                default:
                    return 0;
            }
        });
        
        currentSort = { column, direction };
        updateSortIndicators(column, direction);
        renderStockTable();
    }

    // Funzione per aggiornare gli indicatori di ordinamento
    function updateSortIndicators(column, direction) {
        // Rimuovi tutti gli indicatori esistenti
        document.querySelectorAll('#total-stock-table th[data-sort]').forEach(th => {
            th.removeAttribute('data-sort');
        });
        
        // Aggiungi indicatore alla colonna corrente
        const headerElement = document.querySelector(`#total-stock-table th[data-column="${column}"]`);
        if (headerElement) {
            headerElement.setAttribute('data-sort', direction);
        }
    }

    // Funzione per filtrare i dati per SKU
    function filterStockDataBySku(searchTerm) {
        if (!searchTerm.trim()) {
            filteredStockData = [...allStockData];
        } else {
            const searchLower = searchTerm.toLowerCase();
            filteredStockData = allStockData.filter(item => 
                (item.sku || '').toLowerCase().includes(searchLower)
            );
        }
        
        // Riapplica ordinamento se presente
        if (currentSort.column) {
            sortStockData(currentSort.column, currentSort.direction);
        } else {
            renderStockTable();
        }
    }

    // Funzione per pulire filtri e ordinamento
    function clearFiltersAndReset() {
        searchSkuTableInput.value = '';
        currentSort = { column: null, direction: 'asc' };
        filteredStockData = [...originalStockData];
        allStockData = [...originalStockData];
        
        // Rimuovi tutti gli indicatori di ordinamento
        document.querySelectorAll('#total-stock-table th[data-sort]').forEach(th => {
            th.removeAttribute('data-sort');
        });
        
        renderStockTable();
    }

    // Event listeners per ordinamento tabella principale
    document.querySelectorAll('#total-stock-table th.sortable').forEach(header => {
        header.addEventListener('click', function() {
            const column = this.getAttribute('data-column');
            const currentDirection = this.getAttribute('data-sort') || 'asc';
            const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
            
            sortStockData(column, newDirection);
        });
    });

    // Event listener per ricerca SKU tabella principale
    if (searchSkuTableInput) {
        searchSkuTableInput.addEventListener('input', function() {
            const searchTerm = this.value;
            filterStockDataBySku(searchTerm);
        });
    }

    // Event listener per reset ordinamento
    if (resetSortBtn) {
        resetSortBtn.addEventListener('click', clearFiltersAndReset);
    }

    // Caricamento SKU per il datalist
    async function loadProductSkus() {
        try {
            const productsResponse = await fetch("/products/");
            if (!productsResponse.ok) throw new Error("Errore nel caricamento degli SKU.");
            const products = await productsResponse.json();
            productSkusDatalist.innerHTML = '';
            products.forEach(product => {
                const option = document.createElement("option");
                option.value = product.sku;
                productSkusDatalist.appendChild(option);
            });
        } catch (error) {
            console.error(error);
        }
    }

    // Gestione ricerca prodotto per ubicazione
    const productLocationForm = document.getElementById("product-location-form");
    const productLocationModal = document.getElementById("product-location-modal");

    productLocationForm.addEventListener("submit", async function(event) {
        event.preventDefault();
        const sku = document.getElementById("product-sku").value;
        currentSkuForExport = sku;
        const encodedSku = encodeURIComponent(sku);

        try {
            const response = await fetch(`/analysis/product-locations/${encodedSku}`);
            const data = await response.json();
            
            productLocationModal.querySelector("#modal-title").innerText = `Ubicazioni per SKU: ${sku}`;
            let modalBodyHtml = '<table><thead><tr><th>Ubicazione</th><th>Quantità</th></tr></thead><tbody>';
            if (!response.ok) {
                 modalBodyHtml += `<tr><td colspan="2">${data.detail}</td></tr>`;
            } else {
                data.forEach(item => {
                    modalBodyHtml += `<tr><td>${item.location_name}</td><td>${item.quantity}</td></tr>`;
                });
            }
            modalBodyHtml += '</tbody></table>';
            productLocationModal.querySelector("#modal-body").innerHTML = modalBodyHtml;
            productLocationModal.style.display = "block";

        } catch (error) {
            console.error(error);
        }
    });

    // Gestione ricerca prodotti per fila
    const productsByRowForm = document.getElementById("products-by-row-form");
    const productsByRowModal = document.getElementById("products-by-row-modal");

    productsByRowForm.addEventListener("submit", async function(event) {
        event.preventDefault();
        const rowNumber = document.getElementById("row-number").value;
        currentRowForExport = rowNumber;

        try {
            const response = await fetch(`/analysis/products-by-row/${rowNumber}`);
            const data = await response.json();

            productsByRowModal.querySelector("#row-modal-title").innerText = `Prodotti nella Fila: ${rowNumber}`;
            let modalBodyHtml = '<table><thead><tr><th>Ubicazione</th><th>SKU</th><th>Descrizione</th><th>Quantità</th></tr></thead><tbody>';
            if (!response.ok) {
                modalBodyHtml += `<tr><td colspan="4">${data.detail}</td></tr>`;
            } else {
                data.forEach(item => {
                    modalBodyHtml += `<tr><td>${item.location_name}</td><td>${item.product_sku}</td><td>${item.product_description || 'N/D'}</td><td>${item.quantity}</td></tr>`;
                });
            }
            modalBodyHtml += '</tbody></table>';
            productsByRowModal.querySelector("#row-modal-body").innerHTML = modalBodyHtml;
            productsByRowModal.style.display = "block";

        } catch (error) {
            console.error(error);
        }
    });

    // Export buttons per ricerca ubicazione
    document.getElementById("export-location-csv").addEventListener("click", function() {
        if (currentSkuForExport) {
            const encodedSku = encodeURIComponent(currentSkuForExport);
            window.location.href = `/analysis/export-product-locations/${encodedSku}`;
        }
    });

    document.getElementById("export-location-pdf").addEventListener("click", function() {
        if (currentSkuForExport) {
            const encodedSku = encodeURIComponent(currentSkuForExport);
            window.location.href = `/analysis/export-product-locations-pdf/${encodedSku}`;
        }
    });

    // Export buttons per ricerca fila
    document.getElementById("export-row-csv").addEventListener("click", function() {
        if (currentRowForExport) {
            window.location.href = `/analysis/export-products-by-row/${currentRowForExport}`;
        }
    });

    document.getElementById("export-row-pdf").addEventListener("click", function() {
        if (currentRowForExport) {
            window.location.href = `/analysis/export-products-by-row-pdf/${currentRowForExport}`;
        }
    });

    // Export button per giacenza totale
    document.getElementById("export-total-stock-csv").addEventListener("click", function() {
        // Avvia il download del CSV con tutta la giacenza
        window.location.href = '/analysis/export-total-stock-csv';
    });

    // Gestione chiusura modali
    window.closeModal = function(modalId) {
        document.getElementById(modalId).style.display = "none";
    };

    // Gestione chiusura modali cliccando fuori
    window.onclick = (event) => {
        if (event.target.classList.contains('overlay')) {
            event.target.style.display = "none";
        }
    }


    // Dashboard ultra-compatta
    function loadUltraCompactDashboard(kpis, formattedInventoryValue, totalWarehouseStock) {
        // Giacenze
        document.getElementById('ultra-total-stock').querySelector('.mini-value').textContent = totalWarehouseStock;
        document.getElementById('ultra-shelves-stock').querySelector('.mini-value').textContent = kpis.total_pieces_in_shelves;
        document.getElementById('ultra-ground-stock').querySelector('.mini-value').textContent = kpis.total_pieces_on_ground;
        document.getElementById('ultra-outgoing-stock').querySelector('.mini-value').textContent = kpis.total_pieces_outgoing;
        document.getElementById('ultra-critical-stock').querySelector('.mini-value').textContent = kpis.critical_stock_skus;

        // Ubicazioni
        document.getElementById('ultra-total-locations').querySelector('.mini-value').textContent = kpis.total_locations;
        document.getElementById('ultra-occupied-locations').querySelector('.mini-value').textContent = kpis.occupied_locations;
        document.getElementById('ultra-free-locations').querySelector('.mini-value').textContent = kpis.free_locations;
        document.getElementById('ultra-ground-locations').querySelector('.mini-value').textContent = kpis.ground_floor_locations;

        // Inventario
        document.getElementById('ultra-inventory-value').querySelector('.mini-value').textContent = formattedInventoryValue;
        document.getElementById('ultra-unique-skus').querySelector('.mini-value').textContent = kpis.unique_skus_in_stock;
    }


    // Funzione per mostrare il modal degli SKU critici
    window.showCriticalStockModal = async function() {
        const modal = document.getElementById('critical-stock-modal');
        const loading = document.getElementById('critical-stock-loading');
        const content = document.getElementById('critical-stock-content');
        const error = document.getElementById('critical-stock-error');
        const tableBody = document.getElementById('critical-stock-table-body');

        // Mostra il modal e reset dei contenuti
        modal.style.display = 'block';
        loading.style.display = 'block';
        content.style.display = 'none';
        error.style.display = 'none';

        try {
            const response = await fetch('/analysis/critical-stock-details');
            if (!response.ok) throw new Error('Errore nel caricamento');
            
            const data = await response.json();
            
            // Aggiorna i contatori
            document.getElementById('critical-count').textContent = data.count;
            document.getElementById('critical-threshold').textContent = data.threshold;
            
            // Pulisce e popola la tabella
            tableBody.innerHTML = '';
            
            if (data.critical_items.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--success-color); font-weight: bold;">🎉 Nessun SKU critico trovato!</td></tr>';
            } else {
                data.critical_items.forEach(item => {
                    const row = document.createElement('tr');
                    
                    // Colore di sfondo basato sulla criticità
                    let rowClass = '';
                    if (item.total_quantity === 0) rowClass = 'critical-zero';
                    else if (item.total_quantity <= 5) rowClass = 'critical-very-low';
                    else if (item.total_quantity <= 10) rowClass = 'critical-low';
                    
                    row.className = rowClass;
                    row.innerHTML = `
                        <td><strong style="word-break: keep-all; white-space: nowrap;">${item.sku}</strong></td>
                        <td><strong style="color: var(--danger-color);">${item.total_quantity}</strong></td>
                        <td>${item.quantity_in_shelves}</td>
                        <td>${item.quantity_on_ground}</td>
                        <td>${item.quantity_outgoing}</td>
                        <td>${item.primary_location}</td>
                    `;
                    tableBody.appendChild(row);
                });
            }

            loading.style.display = 'none';
            content.style.display = 'block';

        } catch (err) {
            console.error('Errore caricamento SKU critici:', err);
            loading.style.display = 'none';
            error.style.display = 'block';
        }
    };

    // Export CSV per SKU critici
    document.getElementById('export-critical-stock').addEventListener('click', async function() {
        try {
            const response = await fetch('/analysis/critical-stock-details');
            const data = await response.json();
            
            // Genera CSV
            let csvContent = 'SKU,Giacenza Totale,Scaffali,Terra,Uscita,Ubicazione Principale\n';
            data.critical_items.forEach(item => {
                csvContent += `${item.sku},${item.total_quantity},${item.quantity_in_shelves},${item.quantity_on_ground},${item.quantity_outgoing},${item.primary_location}\n`;
            });
            
            // Download
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            
            const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
            link.download = `sku_critici_${timestamp}.csv`;
            link.click();
            
        } catch (err) {
            console.error('Errore export CSV SKU critici:', err);
            alert('Errore durante l\'export del CSV');
        }
    });

    // === FUNZIONALITÀ PALLET ===
    
    // Variabili per i dati pallet
    let palletDetailsData = [];
    let filteredPalletData = [];
    let currentPalletSort = { column: 'pallets_total', direction: 'desc' };

    // Funzione per caricare i dati pallet summary
    async function loadPalletSummary() {
        try {
            const response = await fetch('/analysis/pallet-summary');
            if (!response.ok) throw new Error('Errore nel caricamento pallet summary');
            
            const palletData = await response.json();
            
            // Aggiorna la card pallet nella dashboard
            const palletCard = document.getElementById('ultra-total-pallets');
            if (palletCard) {
                palletCard.querySelector('.mini-value').textContent = palletData.total_pallets;
            }
            
        } catch (error) {
            console.error('Errore caricamento pallet summary:', error);
        }
    }

    // Funzione per mostrare il modal dei dettagli pallet
    window.showPalletDetailsModal = async function() {
        const modal = document.getElementById('pallet-details-modal');
        const loading = document.getElementById('pallet-loading');
        const content = document.getElementById('pallet-content');
        const error = document.getElementById('pallet-error');

        // Mostra il modal e reset dei contenuti
        modal.style.display = 'block';
        loading.style.display = 'block';
        content.style.display = 'none';
        error.style.display = 'none';

        try {
            const response = await fetch('/analysis/pallet-details');
            if (!response.ok) throw new Error('Errore nel caricamento dettagli pallet');
            
            const data = await response.json();
            
            // Aggiorna i summary statistics
            document.getElementById('summary-total-pallets').textContent = data.summary.total_pallets;
            document.getElementById('summary-pallets-shelves').textContent = data.summary.pallets_in_shelves;
            document.getElementById('summary-pallets-ground').textContent = data.summary.pallets_on_ground;
            document.getElementById('summary-products-analyzed').textContent = data.summary.products_analyzed;
            
            // Salva i dati per ordinamento e ricerca
            palletDetailsData = data.products;
            filteredPalletData = [...palletDetailsData];
            
            // Applica ordinamento di default (pallet totali decrescenti)
            sortPalletData(currentPalletSort.column, currentPalletSort.direction);
            
            // Mostra il contenuto
            loading.style.display = 'none';
            content.style.display = 'block';
            
        } catch (error) {
            console.error('Errore dettagli pallet:', error);
            loading.style.display = 'none';
            error.style.display = 'block';
        }
    };

    // Funzione per renderizzare la tabella pallet
    function renderPalletTable() {
        const tableBody = document.getElementById('pallet-details-table-body');
        tableBody.innerHTML = '';
        
        if (filteredPalletData.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #666;">Nessun risultato trovato</td></tr>';
            return;
        }
        
        filteredPalletData.forEach(item => {
            const row = document.createElement('tr');
            
            // Evidenzia prodotti con pallet quantity = 0 (default)
            if (item.pallet_quantity === 0) {
                row.style.backgroundColor = '#fff3cd';
                row.title = 'Prodotto senza pallettizzazione configurata (usa default 1)';
            }
            
            row.innerHTML = `
                <td><strong style="word-break: keep-all;">${item.sku}</strong></td>
                <td><strong style="color: #0097E0;">${item.pallets_total}</strong></td>
                <td>${item.pallets_in_shelves}</td>
                <td>${item.pallets_on_ground}</td>
                <td style="text-align: center; ${item.pallet_quantity === 0 ? 'color: #856404; font-style: italic;' : ''}">${item.pallet_quantity || '1 (def)'}</td>
                <td>${item.quantity_in_shelves}</td>
                <td>${item.quantity_on_ground}</td>
            `;
            tableBody.appendChild(row);
        });
    }

    // Funzione per ordinare i dati pallet
    function sortPalletData(column, direction = 'desc') {
        currentPalletSort = { column, direction };
        
        filteredPalletData.sort((a, b) => {
            let aValue, bValue;
            
            switch(column) {
                case 'sku':
                    aValue = a.sku || '';
                    bValue = b.sku || '';
                    return direction === 'asc' ? 
                        aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
                        
                case 'pallets_total':
                    aValue = parseFloat(a.pallets_total) || 0;
                    bValue = parseFloat(b.pallets_total) || 0;
                    break;
                    
                case 'pallets_in_shelves':
                    aValue = parseFloat(a.pallets_in_shelves) || 0;
                    bValue = parseFloat(b.pallets_in_shelves) || 0;
                    break;
                    
                case 'pallets_on_ground':
                    aValue = parseFloat(a.pallets_on_ground) || 0;
                    bValue = parseFloat(b.pallets_on_ground) || 0;
                    break;
                    
                case 'pallet_quantity':
                    aValue = parseInt(a.pallet_quantity) || 1;
                    bValue = parseInt(b.pallet_quantity) || 1;
                    break;
                    
                default:
                    return 0;
            }
            
            // Per colonne numeriche
            return direction === 'asc' ? aValue - bValue : bValue - aValue;
        });
        
        updatePalletSortIndicators(column, direction);
        renderPalletTable();
    }

    // Funzione per aggiornare gli indicatori di ordinamento pallet
    function updatePalletSortIndicators(column, direction) {
        // Reset tutti gli indicatori
        document.querySelectorAll('.sort-indicator').forEach(indicator => {
            indicator.textContent = '↕️';
        });
        
        // Aggiorna l'indicatore della colonna corrente
        const indicator = document.getElementById(`sort-${column}`);
        if (indicator) {
            indicator.textContent = direction === 'asc' ? '⬆️' : '⬇️';
        }
    }

    // Funzione per ordinare la tabella pallet (chiamata dai click sugli header)
    window.sortPalletTable = function(column) {
        const newDirection = (currentPalletSort.column === column && currentPalletSort.direction === 'desc') ? 'asc' : 'desc';
        sortPalletData(column, newDirection);
    };

    // Ricerca nella tabella pallet
    function setupPalletSearch() {
        const searchInput = document.getElementById('pallet-search');
        if (searchInput) {
            searchInput.addEventListener('input', function(e) {
                const searchTerm = e.target.value.toLowerCase().trim();
                
                if (searchTerm === '') {
                    filteredPalletData = [...palletDetailsData];
                } else {
                    filteredPalletData = palletDetailsData.filter(item => 
                        item.sku.toLowerCase().includes(searchTerm)
                    );
                }
                
                // Riapplica ordinamento corrente ai dati filtrati
                sortPalletData(currentPalletSort.column, currentPalletSort.direction);
            });
        }
    }

    // Setup della ricerca quando il modal viene aperto
    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'ultra-total-pallets') {
            // Timeout per aspettare che il modal sia completamente caricato
            setTimeout(setupPalletSearch, 100);
        }
    });

    // Chiusura modal (funzione già esistente ma aggiungiamo per sicurezza)
    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    };

    // Click fuori dal modal per chiudere
    document.addEventListener('click', function(e) {
        const palletModal = document.getElementById('pallet-details-modal');
        if (e.target === palletModal) {
            palletModal.style.display = 'none';
        }
    });

    // Chiamate iniziali
    loadDashboardData();
    loadProductSkus();
});