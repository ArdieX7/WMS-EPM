        document.addEventListener("DOMContentLoaded", function() {
            const productsTableBody = document.querySelector("#products-table tbody");
            const createProductForm = document.getElementById("create-product-form");
            
            // Variabili per ricerca e ordinamento
            let allProducts = [];
            let originalProducts = [];
            let filteredProducts = [];
            let currentSort = { column: null, direction: 'asc' };

            // Enhanced Upload per importa prodotti/EAN (solo drag & drop)
            let productsEanUpload = null;
            if (document.getElementById('products-ean-upload')) {
                console.log('🚀 Inizializzazione Enhanced Upload per prodotti/EAN...');
                productsEanUpload = window.createEnhancedUpload('products-ean-upload', {
                    acceptedTypes: ['.txt'],
                    maxFileSize: 10 * 1024 * 1024, // 10MB
                    enableDragDrop: true,
                    enableScanner: false, // SOLO drag & drop
                    onFileSelect: function(file) {
                        console.log('✅ File prodotti/EAN selezionato:', file.name);
                        syncWithHiddenInput('products-ean-file', file);
                    }
                });
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
            
            // Elementi di ricerca
            const searchSkuInput = document.getElementById('search-sku');
            const searchEanInput = document.getElementById('search-ean');

            // Funzione per caricare i prodotti
            async function fetchProducts() {
                const response = await fetch("/products/");
                allProducts = await response.json();
                originalProducts = [...allProducts];
                filteredProducts = [...allProducts];
                
                // Applica ordinamento corrente se presente
                if (currentSort.column) {
                    sortProducts(currentSort.column, currentSort.direction);
                } else {
                    renderProducts();
                }
            }
            
            // Funzione per renderizzare i prodotti nella tabella
            function renderProducts() {
                productsTableBody.innerHTML = ''; // Pulisce la tabella

                filteredProducts.forEach(product => {
                    const eanList = product.eans.map(ean => ean.ean).join(', ');
                    const formattedValue = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(product.estimated_value || 0);
                    const formattedWeight = product.weight ? `${product.weight} kg` : '0 kg';
                    const palletQty = product.pallet_quantity || 0;
                    
                    const row = `<tr>
                        <td><span class="sku-clickable" onclick="showProductHistory('${product.sku}')" title="Clicca per vedere lo storico movimentazioni">${product.sku}</span></td>
                        <td>${product.description || ''}</td>
                        <td>${formattedValue}</td>
                        <td>${eanList}</td>
                        <td>${formattedWeight}</td>
                        <td>${palletQty}</td>
                        <td>
                            <div class="product-actions">
                                <button class="btn-edit edit-product-button" data-sku="${product.sku}" data-permission="products_manage">✏️ Modifica</button>
                                <button class="btn-delete delete-product-button" data-sku="${product.sku}" data-description="${product.description || ''}" data-permission="products_manage">🗑️ Elimina</button>
                            </div>
                        </td>
                    </tr>`;
                    productsTableBody.innerHTML += row;
                });

                // Applica i controlli dei permessi ai nuovi bottoni
                if (typeof window.applyPermissions === 'function') {
                    window.applyPermissions();
                }

                // Aggiungi listener per i bottoni Modifica
                document.querySelectorAll(".edit-product-button").forEach(button => {
                    button.addEventListener("click", async function() {
                        const skuToEdit = this.dataset.sku;
                        await showEditProductForm(skuToEdit);
                    });
                });
                
                // Aggiungi listener per i bottoni Elimina
                document.querySelectorAll(".delete-product-button").forEach(button => {
                    button.addEventListener("click", async function() {
                        const skuToDelete = this.dataset.sku;
                        const descriptionToDelete = this.dataset.description;
                        await showDeleteProductOverlay(skuToDelete, descriptionToDelete);
                    });
                });
            }

            // Funzione per creare un prodotto
            createProductForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                
                const sku = document.getElementById("sku").value;
                const description = document.getElementById("description").value;
                const estimated_value = parseFloat(document.getElementById("estimated_value").value) || 0.0;
                const weight = parseFloat(document.getElementById("weight").value) || 0.0;
                const pallet_quantity = parseInt(document.getElementById("pallet_quantity").value) || 0;
                const eans = document.getElementById("eans").value.split(',').map(e => e.trim()).filter(e => e);

                // Ottieni token JWT per autenticazione
                const token = await window.modernAuth.getValidAccessToken();
                if (!token) {
                    alert("Errore: Sessione scaduta. Ricarica la pagina e riprova.");
                    window.location.href = '/login';
                    return;
                }

                const response = await fetch("/products/", {
                    method: "POST",
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ sku, description, estimated_value, weight, pallet_quantity, eans })
                });

                if (response.ok) {
                    createProductForm.reset();
                    alert("Prodotto aggiunto con successo!");
                    document.getElementById('add-product-overlay').style.display = 'none';
                    
                    // Pulisci i filtri per assicurarti che il nuovo prodotto sia visibile
                    clearFiltersAndRefresh();
                } else {
                    const error = await response.json();
                    alert(`Errore: ${error.detail}`);
                }
            });
            
            // Funzione per pulire i filtri e ricaricare
            function clearFiltersAndRefresh() {
                // Pulisci i campi di ricerca
                searchSkuInput.value = '';
                searchEanInput.value = '';
                
                // Riabilita entrambi i campi
                searchSkuInput.disabled = false;
                searchEanInput.disabled = false;
                
                // Resetta l'ordinamento
                currentSort = { column: null, direction: 'asc' };
                updateSortArrows();
                
                // Ricarica i prodotti
                fetchProducts();
            }
            
            // Funzioni per filtro e ricerca
            function filterProducts() {
                const skuFilter = searchSkuInput.value.toLowerCase().trim();
                const eanFilter = searchEanInput.value.toLowerCase().trim();
                
                // Usa l'ordine originale o quello ordinato come base
                const baseProducts = currentSort.column ? allProducts : originalProducts;
                
                filteredProducts = baseProducts.filter(product => {
                    const matchesSku = !skuFilter || product.sku.toLowerCase().includes(skuFilter);
                    const eanList = product.eans.map(ean => ean.ean).join(' ').toLowerCase();
                    const matchesEan = !eanFilter || eanList.includes(eanFilter);
                    
                    return matchesSku && matchesEan;
                });
                
                // Mantieni l'ordinamento attuale
                if (currentSort.column) {
                    sortProducts(currentSort.column, currentSort.direction, false);
                } else {
                    renderProducts();
                }
            }
            
            // Gestione disabilitazione mutua dei campi
            searchSkuInput.addEventListener('input', function() {
                if (this.value.trim()) {
                    searchEanInput.disabled = true;
                } else {
                    searchEanInput.disabled = false;
                }
                filterProducts();
            });
            
            searchEanInput.addEventListener('input', function() {
                if (this.value.trim()) {
                    searchSkuInput.disabled = true;
                } else {
                    searchSkuInput.disabled = false;
                }
                filterProducts();
            });
            
            // Funzione per ordinamento
            function sortProducts(column, direction = 'asc', updateFiltered = true) {
                const dataToSort = updateFiltered ? filteredProducts : filteredProducts;
                
                dataToSort.sort((a, b) => {
                    let aValue, bValue;
                    
                    switch(column) {
                        case 'sku':
                            aValue = a.sku.toLowerCase();
                            bValue = b.sku.toLowerCase();
                            break;
                        case 'description':
                            aValue = (a.description || '').toLowerCase();
                            bValue = (b.description || '').toLowerCase();
                            break;
                        case 'estimated_value':
                            aValue = a.estimated_value || 0;
                            bValue = b.estimated_value || 0;
                            break;
                        case 'weight':
                            aValue = a.weight || 0;
                            bValue = b.weight || 0;
                            break;
                        case 'pallet_quantity':
                            aValue = a.pallet_quantity || 0;
                            bValue = b.pallet_quantity || 0;
                            break;
                        case 'eans':
                            aValue = a.eans.map(ean => ean.ean).join(' ').toLowerCase();
                            bValue = b.eans.map(ean => ean.ean).join(' ').toLowerCase();
                            break;
                        default:
                            return 0;
                    }
                    
                    if (typeof aValue === 'number' && typeof bValue === 'number') {
                        return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    } else {
                        if (direction === 'asc') {
                            return aValue.localeCompare(bValue);
                        } else {
                            return bValue.localeCompare(aValue);
                        }
                    }
                });
                
                currentSort = { column, direction };
                updateSortArrows();
                renderProducts();
            }
            
            // Aggiorna le frecce di ordinamento
            function updateSortArrows() {
                document.querySelectorAll('.sort-arrow').forEach(arrow => {
                    arrow.textContent = '';
                });
                
                if (currentSort.column) {
                    const activeHeader = document.querySelector(`th[data-column="${currentSort.column}"] .sort-arrow`);
                    if (activeHeader) {
                        activeHeader.textContent = currentSort.direction === 'asc' ? ' ▲' : ' ▼';
                    }
                }
            }
            
            // Gestione click sulle intestazioni per ordinamento
            document.querySelectorAll('.sortable').forEach(header => {
                header.addEventListener('click', function() {
                    const column = this.dataset.column;
                    let direction = 'asc';
                    
                    if (currentSort.column === column && currentSort.direction === 'asc') {
                        direction = 'desc';
                    }
                    
                    sortProducts(column, direction);
                });
            });
            
            // Funzione comune per azzerare ordinamento
            function resetSorting() {
                currentSort = { column: null, direction: 'asc' };
                
                // Ripristina l'ordine originale
                const skuFilter = searchSkuInput.value.toLowerCase().trim();
                const eanFilter = searchEanInput.value.toLowerCase().trim();
                
                if (skuFilter || eanFilter) {
                    // Se ci sono filtri attivi, riapplica i filtri sull'ordine originale
                    filteredProducts = originalProducts.filter(product => {
                        const matchesSku = !skuFilter || product.sku.toLowerCase().includes(skuFilter);
                        const eanList = product.eans.map(ean => ean.ean).join(' ').toLowerCase();
                        const matchesEan = !eanFilter || eanList.includes(eanFilter);
                        
                        return matchesSku && matchesEan;
                    });
                } else {
                    // Nessun filtro, ripristina tutti i prodotti nell'ordine originale
                    filteredProducts = [...originalProducts];
                }
                
                updateSortArrows();
                renderProducts();
            }
            
            // Gestione pulsante azzera ordinamento inline (accanto a EAN)
            document.getElementById('reset-sort-ean-btn').addEventListener('click', resetSorting);
            
            // Gestione apertura overlay
            document.getElementById('add-product-btn').addEventListener('click', function() {
                document.getElementById('add-product-overlay').style.display = 'block';
            });
            
            document.getElementById('import-products-btn').addEventListener('click', function() {
                document.getElementById('import-products-overlay').style.display = 'block';
                // Reset enhanced upload quando si apre l'overlay
                if (productsEanUpload) {
                    productsEanUpload.reset();
                }
            });
            
            // Gestione chiusura overlay
            document.querySelectorAll('.overlay-close, .btn-secondary').forEach(button => {
                button.addEventListener('click', function() {
                    const overlayId = this.getAttribute('data-overlay');
                    if (overlayId) {
                        document.getElementById(overlayId).style.display = 'none';
                        
                        // Reset enhanced upload per import prodotti
                        if (overlayId === 'import-products-overlay' && productsEanUpload) {
                            productsEanUpload.reset();
                        }
                    }
                });
            });
            
            // Chiusura overlay cliccando fuori
            document.querySelectorAll('.overlay').forEach(overlay => {
                overlay.addEventListener('click', function(e) {
                    if (e.target === this) {
                        this.style.display = 'none';
                    }
                });
            });
            
            // Listener per il pulsante di conferma eliminazione
            document.getElementById('confirm-delete-btn').addEventListener('click', confirmProductDeletion);

            // Funzione per mostrare il form di modifica prodotto
            async function showEditProductForm(sku) {
                const encodedSku = encodeURIComponent(sku);
                const response = await fetch(`/products/${encodedSku}`);
                if (!response.ok) {
                    alert(`Errore: Impossibile trovare il prodotto con SKU ${sku}.`);
                    return;
                }
                const product = await response.json();

                document.getElementById("edit-sku").value = product.sku;
                document.getElementById("edit-description").value = product.description || '';
                document.getElementById("edit-estimated_value").value = product.estimated_value || 0.0;
                document.getElementById("edit-weight").value = product.weight || 0.0;
                document.getElementById("edit-pallet_quantity").value = product.pallet_quantity || 0;
                document.getElementById("edit-eans").value = product.eans.map(ean => ean.ean).join(', ');
                document.getElementById("edit-product-overlay").style.display = "block";
            }
            
            // Funzione per mostrare l'overlay di eliminazione prodotto
            async function showDeleteProductOverlay(sku, description) {
                // Popola i dati del prodotto nell'overlay
                document.getElementById("delete-product-sku").textContent = sku;
                document.getElementById("delete-product-description").textContent = description || 'N/A';
                
                // Reset dello stato dell'overlay
                document.getElementById("delete-validation-status").style.display = "block";
                document.getElementById("delete-dependencies-list").style.display = "none";
                document.getElementById("delete-success-validation").style.display = "none";
                document.getElementById("confirm-delete-btn").style.display = "none";
                document.getElementById("confirm-delete-btn").dataset.sku = sku;
                
                // Mostra l'overlay
                document.getElementById("delete-product-overlay").style.display = "block";
                
                // Avvia la validazione delle dipendenze
                await validateProductDeletion(sku);
            }
            
            // Funzione per validare se un prodotto può essere eliminato
            async function validateProductDeletion(sku) {
                try {
                    // Chiama l'endpoint di validazione
                    const response = await fetch(`/products/${encodeURIComponent(sku)}/validate-deletion`);
                    
                    const validationStatus = document.getElementById("delete-validation-status");
                    const dependenciesList = document.getElementById("delete-dependencies-list");
                    const successValidation = document.getElementById("delete-success-validation");
                    const confirmBtn = document.getElementById("confirm-delete-btn");
                    
                    if (response.ok) {
                        const validationResult = await response.json();
                        
                        validationStatus.style.display = "none";
                        
                        if (validationResult.can_delete) {
                            // Il prodotto può essere eliminato
                            successValidation.style.display = "block";
                            confirmBtn.style.display = "inline-block";
                        } else {
                            // Ci sono dipendenze che bloccano l'eliminazione
                            dependenciesList.style.display = "block";
                            
                            const dependenciesItems = document.getElementById("dependencies-items");
                            dependenciesItems.innerHTML = '';
                            
                            validationResult.dependencies.forEach(dep => {
                                const li = document.createElement('li');
                                li.textContent = dep;
                                dependenciesItems.appendChild(li);
                            });
                        }
                    } else {
                        // Errore generico
                        validationStatus.innerHTML = `
                            <p style="color: #dc3545;">❌ Errore durante la validazione</p>
                            <p>Impossibile verificare le dipendenze del prodotto.</p>
                        `;
                    }
                } catch (error) {
                    console.error('Errore durante la validazione:', error);
                    document.getElementById("delete-validation-status").innerHTML = `
                        <p style="color: #dc3545;">❌ Errore di connessione</p>
                        <p>Impossibile contattare il server per la validazione.</p>
                    `;
                }
            }
            
            // Funzione per confermare ed eseguire l'eliminazione
            async function confirmProductDeletion() {
                const sku = document.getElementById("confirm-delete-btn").dataset.sku;
                const confirmBtn = document.getElementById("confirm-delete-btn");
                
                // Disabilita il pulsante e mostra loading
                confirmBtn.disabled = true;
                confirmBtn.innerHTML = "⏳ Eliminazione in corso...";
                
                try {
                    // Ottieni token JWT per autenticazione
                    const token = await window.modernAuth.getValidAccessToken();
                    if (!token) {
                        alert("Errore: Sessione scaduta. Ricarica la pagina e riprova.");
                        window.location.href = '/login';
                        return;
                    }

                    const response = await fetch(`/products/${encodeURIComponent(sku)}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    if (response.ok) {
                        const result = await response.json();
                        alert(`✅ ${result.message}`);
                        
                        // Chiudi l'overlay e ricarica la lista
                        document.getElementById("delete-product-overlay").style.display = "none";
                        
                        // Mantieni i filtri esistenti dopo l'eliminazione
                        await fetchProducts();
                    } else {
                        const errorData = await response.json();
                        let errorMessage = "Errore durante l'eliminazione del prodotto.";
                        
                        if (errorData.detail) {
                            if (typeof errorData.detail === 'string') {
                                errorMessage = errorData.detail;
                            } else if (errorData.detail.message) {
                                errorMessage = errorData.detail.message;
                            }
                        }
                        
                        alert(`❌ ${errorMessage}`);
                    }
                } catch (error) {
                    console.error('Errore durante l\'eliminazione:', error);
                    alert("❌ Errore di connessione durante l'eliminazione del prodotto.");
                } finally {
                    // Riabilita il pulsante
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = "🗑️ Elimina Definitivamente";
                }
            }

            // Gestione invio form Modifica Prodotto
            const editProductForm = document.getElementById("edit-product-form");
            editProductForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const sku = document.getElementById("edit-sku").value;
                const description = document.getElementById("edit-description").value;
                const estimated_value = parseFloat(document.getElementById("edit-estimated_value").value) || 0.0;
                const weight = parseFloat(document.getElementById("edit-weight").value) || 0.0;
                const pallet_quantity = parseInt(document.getElementById("edit-pallet_quantity").value) || 0;
                const eans = document.getElementById("edit-eans").value.split(',').map(e => e.trim()).filter(e => e);

                // Ottieni token JWT per autenticazione
                const token = await window.modernAuth.getValidAccessToken();
                if (!token) {
                    alert("Errore: Sessione scaduta. Ricarica la pagina e riprova.");
                    window.location.href = '/login';
                    return;
                }

                const response = await fetch(`/products/${sku}`,
                    {
                        method: "PUT",
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ sku, description, estimated_value, weight, pallet_quantity, eans })
                    });

                if (response.ok) {
                    alert("Prodotto aggiornato con successo!");
                    document.getElementById("edit-product-overlay").style.display = "none";
                    
                    // Mantieni i filtri per la modifica prodotto (il prodotto dovrebbe essere già visibile)
                    fetchProducts(); // Ricarica la lista
                } else {
                    const error = await response.json();
                    alert(`Errore nell'aggiornamento prodotto: ${error.detail}`);
                }
            });


            // Carica i prodotti all'avvio
            fetchProducts();

            // Gestione importazione prodotti/EAN da TXT
            const importProductsEanForm = document.getElementById("import-products-ean-form");
            importProductsEanForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const fileInput = document.getElementById("products-ean-file");
                const file = fileInput.files[0];

                if (!file) {
                    console.log('Nessun file selezionato per import prodotti/EAN.');
                    if (productsEanUpload) {
                        productsEanUpload.setStatus('error', '❌ Seleziona un file TXT da importare');
                    }
                    return;
                }

                // Mostra status di elaborazione
                if (productsEanUpload) {
                    productsEanUpload.setStatus('processing', '⏳ Importazione prodotti/EAN in corso...');
                }

                const formData = new FormData();
                formData.append("file", file);

                try {
                    // Ottieni token JWT per autenticazione
                    const token = await window.modernAuth.getValidAccessToken();
                    if (!token) {
                        alert("Errore: Sessione scaduta. Ricarica la pagina e riprova.");
                        window.location.href = '/login';
                        return;
                    }

                    const response = await fetch("/products/import-ean-txt", {
                        method: "POST",
                        headers: {
                            'Authorization': `Bearer ${token}`
                        },
                        body: formData,
                    });

                    if (response.ok) {
                        const result = await response.json();
                        if (productsEanUpload) {
                            productsEanUpload.setStatus('success', `✅ Importazione completata: ${result.message}`);
                        }
                        importProductsEanForm.reset();
                        document.getElementById('import-products-overlay').style.display = 'none';
                        
                        // Pulisci i filtri per vedere tutti i prodotti importati
                        clearFiltersAndRefresh();
                    } else {
                        const error = await response.json();
                        if (productsEanUpload) {
                            productsEanUpload.setStatus('error', `❌ Errore nell'importazione: ${error.detail}`);
                        }
                    }
                } catch (error) {
                    console.error("Errore nell'importazione prodotti/EAN:", error);
                    if (productsEanUpload) {
                        productsEanUpload.setStatus('error', '❌ Errore di rete durante l\'importazione');
                    }
                }
            });

            // Inizializzazione ProductHistoryManager
            window.productHistoryManager = new ProductHistoryManager();
        });

        // ProductHistoryManager - Gestione storico movimentazioni prodotto
        class ProductHistoryManager {
            constructor() {
                this.currentSku = null;
                this.currentPage = 1;
                this.pageSize = 20;
                this.currentFilters = {};
                this.groupedOperationTypes = null;
                this.init();
            }

            init() {
                this.bindEvents();
                this.loadGroupedOperationTypes();
            }

            bindEvents() {
                // Bottoni filtri
                document.getElementById('apply-history-filters-btn')?.addEventListener('click', () => this.applyFilters());
                document.getElementById('reset-history-filters-btn')?.addEventListener('click', () => this.resetFilters());
            }

            async loadGroupedOperationTypes() {
                try {
                    // Riusa la stessa struttura dei logs
                    this.groupedOperationTypes = {
                        "carico": {
                            "label": "📦 Carico",
                            "operations": [
                                {"value": "CARICO_MANUALE", "label": "Carico Manuale"},
                                {"value": "CARICO_FILE", "label": "Carico File"},
                                {"value": "SCARICO_CONTAINER_MANUALE", "label": "Scarico Container Manuale"},
                                {"value": "SCARICO_CONTAINER_FILE", "label": "Scarico Container File"}
                            ]
                        },
                        "scarico": {
                            "label": "📤 Scarico", 
                            "operations": [
                                {"value": "SCARICO_MANUALE", "label": "Scarico Manuale"},
                                {"value": "SCARICO_FILE", "label": "Scarico File"}
                            ]
                        },
                        "movimenti": {
                            "label": "🔄 Movimenti",
                            "operations": [
                                {"value": "SPOSTAMENTO_MANUALE", "label": "Spostamento Manuale"},
                                {"value": "SPOSTAMENTO_FILE", "label": "Spostamento File"},
                                {"value": "UBICAZIONE_DA_TERRA_MANUALE", "label": "Ubicazione Da Terra Manuale"},
                                {"value": "UBICAZIONE_DA_TERRA_FILE", "label": "Ubicazione Da Terra File"},
                                {"value": "RIALLINEAMENTO_MANUALE", "label": "Riallineamento Manuale"},
                                {"value": "RIALLINEAMENTO_FILE", "label": "Riallineamento File"}
                            ]
                        },
                        "prelievo": {
                            "label": "🛒 Prelievo",
                            "operations": [
                                {"value": "PRELIEVO_FILE", "label": "Prelievo File"},
                                {"value": "PRELIEVO_MANUALE", "label": "Prelievo Manuale"},
                                {"value": "PRELIEVO_TEMPO_REALE", "label": "Prelievo Tempo Reale"},
                                {"value": "PICKING_GENERATO", "label": "Picking Generato"},
                                {"value": "PICKING_CONFERMATO", "label": "Picking Confermato"}
                            ]
                        },
                        "ordini": {
                            "label": "📋 Ordini",
                            "operations": [
                                {"value": "ORDINE_CREATO", "label": "Ordine Creato"},
                                {"value": "ORDINE_MODIFICATO", "label": "Ordine Modificato"},
                                {"value": "ORDINE_ELIMINATO", "label": "Ordine Eliminato"},
                                {"value": "ORDINE_COMPLETATO", "label": "Ordine Completato"},
                                {"value": "ORDINE_EVASO", "label": "Ordine Evaso"},
                                {"value": "ORDINE_ANNULLATO", "label": "Ordine Annullato"}
                            ]
                        },
                        "seriali": {
                            "label": "🏷️ Seriali",
                            "operations": [
                                {"value": "SERIALI_ASSEGNATI", "label": "Seriali Assegnati"},
                                {"value": "SERIALI_RIMOSSI", "label": "Seriali Rimossi"}
                            ]
                        }
                    };

                    this.renderOperationTypeFilters();
                } catch (error) {
                    console.error('Error loading operation types:', error);
                }
            }

            renderOperationTypeFilters() {
                const container = document.getElementById('history-operation-type-filter');
                if (!container || !this.groupedOperationTypes) return;

                container.innerHTML = '';

                for (const [groupKey, groupData] of Object.entries(this.groupedOperationTypes)) {
                    const groupDiv = document.createElement('div');
                    groupDiv.className = 'operation-group';

                    // Macro categoria
                    const macroLabel = document.createElement('label');
                    macroLabel.className = 'checkbox-item macro-category';
                    macroLabel.innerHTML = `
                        <input type="checkbox" name="operation-group" value="${groupKey}" class="filter-checkbox group-checkbox" data-group="${groupKey}">
                        <span class="checkbox-label group-label">${groupData.label}</span>
                    `;

                    // Sub operazioni
                    const subDiv = document.createElement('div');
                    subDiv.className = 'sub-operations';
                    subDiv.setAttribute('data-parent-group', groupKey);

                    groupData.operations.forEach(operation => {
                        const operationLabel = document.createElement('label');
                        operationLabel.className = 'checkbox-item sub-operation';
                        operationLabel.innerHTML = `
                            <input type="checkbox" name="operation-type" value="${operation.value}" class="filter-checkbox operation-checkbox" data-parent="${groupKey}">
                            <span class="checkbox-label">${operation.label}</span>
                        `;
                        subDiv.appendChild(operationLabel);
                    });

                    groupDiv.appendChild(macroLabel);
                    groupDiv.appendChild(subDiv);
                    container.appendChild(groupDiv);
                }

                // Bind eventi gerarchici
                this.bindHierarchicalEvents();
            }

            bindHierarchicalEvents() {
                // Gestisce i checkbox delle macro-categorie
                document.querySelectorAll('#history-operation-type-filter .group-checkbox').forEach(groupCheckbox => {
                    groupCheckbox.addEventListener('change', (e) => {
                        const groupKey = e.target.dataset.group;
                        const isChecked = e.target.checked;
                        this.toggleGroupOperations(groupKey, isChecked);
                    });
                });

                // Gestisce i checkbox delle singole operazioni
                document.querySelectorAll('#history-operation-type-filter .operation-checkbox').forEach(operationCheckbox => {
                    operationCheckbox.addEventListener('change', (e) => {
                        const groupKey = e.target.dataset.parent;
                        this.updateGroupCheckboxState(groupKey);
                    });
                });
            }

            toggleGroupOperations(groupKey, isChecked) {
                const operationsInGroup = document.querySelectorAll(`#history-operation-type-filter input.operation-checkbox[data-parent="${groupKey}"]`);
                operationsInGroup.forEach(checkbox => {
                    checkbox.checked = isChecked;
                });
            }

            updateGroupCheckboxState(groupKey) {
                const groupCheckbox = document.querySelector(`#history-operation-type-filter input.group-checkbox[data-group="${groupKey}"]`);
                const operationsInGroup = document.querySelectorAll(`#history-operation-type-filter input.operation-checkbox[data-parent="${groupKey}"]`);
                const checkedOperations = document.querySelectorAll(`#history-operation-type-filter input.operation-checkbox[data-parent="${groupKey}"]:checked`);
                
                if (checkedOperations.length === 0) {
                    groupCheckbox.checked = false;
                    groupCheckbox.indeterminate = false;
                } else if (checkedOperations.length === operationsInGroup.length) {
                    groupCheckbox.checked = true;
                    groupCheckbox.indeterminate = false;
                } else {
                    groupCheckbox.checked = false;
                    groupCheckbox.indeterminate = true;
                }
            }

            async showHistory(sku) {
                this.currentSku = sku;
                this.currentPage = 1;
                
                // Aggiorna UI
                document.getElementById('history-product-title').textContent = `📊 Storico Movimentazioni - ${sku}`;
                document.getElementById('history-product-info').textContent = `Cronologia operazioni per prodotto ${sku}`;
                
                // Imposta filtri di default (ultimi 30 giorni)
                this.setDefaultFilters();
                
                // Carica dati
                await this.loadHistory();
                
                // Mostra overlay
                document.getElementById('product-history-overlay').style.display = 'block';
            }

            setDefaultFilters() {
                const endDate = new Date();
                const startDate = new Date();
                startDate.setDate(startDate.getDate() - 30);
                
                document.getElementById('history-start-date').value = this.formatDateTimeLocal(startDate);
                document.getElementById('history-end-date').value = this.formatDateTimeLocal(endDate);
            }

            formatDateTimeLocal(date) {
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                return `${year}-${month}-${day}T${hours}:${minutes}`;
            }

            async loadHistory() {
                if (!this.currentSku) return;

                this.showLoading();
                
                try {
                    const token = await window.modernAuth.getValidAccessToken();
                    if (!token) {
                        throw new Error('Token non valido');
                    }

                    // Costruisci parametri
                    const params = new URLSearchParams({
                        page: this.currentPage,
                        page_size: this.pageSize,
                        order_by: 'timestamp',
                        order_direction: 'desc'
                    });

                    // Aggiungi filtri
                    if (this.currentFilters.start_date) params.append('start_date', this.currentFilters.start_date);
                    if (this.currentFilters.end_date) params.append('end_date', this.currentFilters.end_date);
                    if (this.currentFilters.operation_types) params.append('operation_types', this.currentFilters.operation_types);

                    const response = await fetch(`/products/${this.currentSku}/history?${params}`, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }

                    const data = await response.json();
                    this.renderHistory(data);
                    this.updateStats(data);

                } catch (error) {
                    console.error('Error loading history:', error);
                    this.showError(`Errore nel caricamento storico: ${error.message}`);
                } finally {
                    this.hideLoading();
                }
            }

            renderHistory(data) {
                const tbody = document.getElementById('history-table-body');
                tbody.innerHTML = '';

                if (!data.history || data.history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="no-data">Nessuna operazione trovata per il periodo selezionato</td></tr>';
                    return;
                }

                data.history.forEach(log => {
                    const locationDisplay = this.formatLocation(log.location_from, log.location_to);
                    const statusClass = this.getStatusClass(log.status);
                    const orderNumber = log.order_number || '-';
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${log.timestamp}</td>
                        <td><span class="operation-type">${log.operation_type}</span></td>
                        <td><span class="status ${statusClass}">${log.status}</span></td>
                        <td>${locationDisplay}</td>
                        <td class="quantity">${log.quantity || '-'}</td>
                        <td>${log.user_id || '-'}</td>
                        <td class="order-number">${orderNumber}</td>
                    `;
                    tbody.appendChild(row);
                });
            }

            formatLocation(locationFrom, locationTo) {
                if (locationFrom && locationTo) {
                    return `${locationFrom} → ${locationTo}`;
                } else if (locationFrom) {
                    return `Da: ${locationFrom}`;
                } else if (locationTo) {
                    return `A: ${locationTo}`;
                } else {
                    return '-';
                }
            }

            getStatusClass(status) {
                switch (status) {
                    case 'SUCCESS': return 'success';
                    case 'ERROR': return 'error';
                    case 'WARNING': return 'warning';
                    case 'PARTIAL': return 'partial';
                    default: return '';
                }
            }

            updateStats(data) {
                document.getElementById('history-total-ops').textContent = data.pagination?.total_count || 0;
                
                const periodInfo = data.period_info;
                let periodText = 'Tutti i record';
                if (periodInfo?.start_date && periodInfo?.end_date) {
                    const startDate = new Date(periodInfo.start_date).toLocaleDateString('it-IT');
                    const endDate = new Date(periodInfo.end_date).toLocaleDateString('it-IT');
                    periodText = `${startDate} - ${endDate}`;
                }
                document.getElementById('history-period').textContent = periodText;
            }

            applyFilters() {
                this.currentFilters = {};
                this.currentPage = 1;

                // Date
                const startDate = document.getElementById('history-start-date').value;
                const endDate = document.getElementById('history-end-date').value;
                
                if (startDate) this.currentFilters.start_date = startDate;
                if (endDate) this.currentFilters.end_date = endDate;

                // Operation types
                const operationTypes = Array.from(document.querySelectorAll('#history-operation-type-filter .operation-checkbox:checked'))
                    .map(checkbox => checkbox.value).filter(v => v);
                if (operationTypes.length > 0) this.currentFilters.operation_types = operationTypes.join(',');

                this.loadHistory();
            }

            resetFilters() {
                // Reset filtri
                document.getElementById('history-start-date').value = '';
                document.getElementById('history-end-date').value = '';
                
                // Reset checkboxes
                document.querySelectorAll('#history-operation-type-filter input[type="checkbox"]').forEach(cb => {
                    cb.checked = false;
                    cb.indeterminate = false;
                });

                // Imposta filtri di default
                this.setDefaultFilters();
                this.currentFilters = {};
                this.currentPage = 1;
                this.loadHistory();
            }

            showLoading() {
                document.getElementById('history-loading').style.display = 'block';
            }

            hideLoading() {
                document.getElementById('history-loading').style.display = 'none';
            }

            showError(message) {
                const tbody = document.getElementById('history-table-body');
                tbody.innerHTML = `<tr><td colspan="8" class="error-message">❌ ${message}</td></tr>`;
            }
        }

        // Funzioni globali
        function showProductHistory(sku) {
            window.productHistoryManager.showHistory(sku);
        }

        function closeProductHistory() {
            document.getElementById('product-history-overlay').style.display = 'none';
        }

