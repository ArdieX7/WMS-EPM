        document.addEventListener("DOMContentLoaded", function() {
            const createOrderForm = document.getElementById("create-order-form");
            const orderLinesContainer = document.getElementById("order-lines-container");
            const addLineButton = document.getElementById("add-line-button");
            const ordersTableBody = document.querySelector("#orders-table tbody");
            const productSkusDatalist = document.getElementById("product-skus");
            const orderDetailsContainer = document.getElementById("order-details-container");

            const importOrdersForm = document.getElementById("import-orders-form");
            const importOrdersResult = document.getElementById("import-orders-result");

            // Enhanced Upload per prelievo da file
            let pickingFileUpload = null;
            if (document.getElementById('picking-file-upload')) {
                console.log('🚀 Inizializzazione Enhanced Upload per picking...');
                pickingFileUpload = window.createEnhancedUpload('picking-file-upload', {
                    acceptedTypes: ['.txt'],
                    maxFileSize: 10 * 1024 * 1024, // 10MB
                    enableDragDrop: true,
                    enableScanner: true,
                    scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\\n\\nEsempio:\\n1888\\n15A1P2\\n9512012430306\\n9512012430306\\nSND-12SFU-OD_10\\n...',
                    onFileSelect: function(file) {
                        console.log('✅ File selezionato per picking:', file.name);
                        syncWithHiddenInput('picking-file', file);
                    },
                    onScannerProcess: function(virtualFile, content) {
                        console.log('✅ Dati scanner elaborati per picking:', content.split('\\n').length, 'righe');
                        syncWithHiddenInput('picking-file', virtualFile);
                    }
                });
                
                // Imposta la tab scanner come predefinita attiva per prelievo
                if (pickingFileUpload) {
                    pickingFileUpload.switchMode('scanner');
                }
            }

            // Enhanced Upload per import ordini da file TXT (solo drag & drop)
            let ordersFileUpload = null;
            if (document.getElementById('orders-file-upload')) {
                console.log('🚀 Inizializzazione Enhanced Upload per import ordini...');
                ordersFileUpload = window.createEnhancedUpload('orders-file-upload', {
                    acceptedTypes: ['.txt'],
                    maxFileSize: 10 * 1024 * 1024, // 10MB
                    enableDragDrop: true,
                    enableScanner: false, // SOLO drag & drop
                    onFileSelect: function(file) {
                        console.log('✅ File ordini selezionato:', file.name);
                        syncWithHiddenInput('orders-file', file);
                    }
                });
            }

            // Enhanced Upload per import ordini da file Excel
            let excelFileUpload = null;
            if (document.getElementById('excel-file-upload')) {
                console.log('🚀 Inizializzazione Enhanced Upload per Excel...');
                excelFileUpload = window.createEnhancedUpload('excel-file-upload', {
                    acceptedTypes: ['.xlsx'],
                    maxFileSize: 10 * 1024 * 1024, // 10MB
                    enableDragDrop: true,
                    enableScanner: false, // Solo drag & drop per Excel
                    onFileSelect: function(file) {
                        console.log('✅ File Excel selezionato:', file.name);
                        syncWithHiddenInput('excel-file', file);
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

            let lineCounter = 0;
            let currentOrderData = null; // Per memorizzare i dati dell'ordine corrente
            
            // Variabili per gestione Excel import
            let currentExcelRecapData = null;
            let currentExcelFileName = null;
            
            // Variabili per gestione ricerca e ordinamento
            let originalOrdersData = [];
            let filteredOrdersData = [];
            let currentOrdersSort = { column: 'id', direction: 'desc' }; // Default: ID decrescente
            
            let originalArchivedData = [];
            let filteredArchivedData = [];
            let currentArchivedSort = { column: 'id', direction: 'desc' }; // Default: ID decrescente

            // Funzioni per gestione overlay
            window.openOverlay = function(overlayId) {
                document.getElementById(overlayId).style.display = 'block';
            };

            window.closeOverlay = function(overlayId) {
                document.getElementById(overlayId).style.display = 'none';
                
                // Reset enhanced upload per picking
                if (overlayId === 'picking-file-overlay' && pickingFileUpload) {
                    pickingFileUpload.reset();
                }
                
                // Reset enhanced upload per import ordini
                if (overlayId === 'import-orders-overlay' && ordersFileUpload) {
                    ordersFileUpload.reset();
                }
                
                // Reset enhanced upload per Excel
                if (overlayId === 'import-orders-overlay' && excelFileUpload) {
                    excelFileUpload.reset();
                }
            };

            // Chiudi overlay cliccando fuori
            document.addEventListener('click', function(e) {
                if (e.target.classList.contains('overlay')) {
                    e.target.style.display = 'none';
                }
            });

            // Funzione per tab ordini
            window.switchOrdersTab = function(tabId) {
                // Nasconde tutti i contenuti tab
                document.querySelectorAll('#import-orders-overlay .tab-content').forEach(content => {
                    content.classList.remove('active');
                });
                
                // Rimuove active da tutti i pulsanti tab
                document.querySelectorAll('#import-orders-overlay .tab-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
                
                // Mostra il tab selezionato
                document.getElementById(tabId).classList.add('active');
                
                // Attiva il pulsante del tab corrispondente
                const correspondingBtn = document.querySelector(`#import-orders-overlay .tab-btn[onclick="switchOrdersTab('${tabId}')"]`);
                if (correspondingBtn) {
                    correspondingBtn.classList.add('active');
                }
            };

            // Funzione per caricare gli SKU nel datalist
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

            // Funzione per aggiungere una nuova riga ordine al form
            addLineButton.addEventListener("click", function() {
                lineCounter++;
                const newLineHtml = `
                    <div class="order-line">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="line-product-sku-${lineCounter}">SKU Prodotto:</label>
                                <input type="text" id="line-product-sku-${lineCounter}" list="product-skus" required>
                            </div>
                            <div class="form-group">
                                <label for="line-quantity-${lineCounter}">Quantità Richiesta:</label>
                                <input type="number" id="line-quantity-${lineCounter}" required>
                            </div>
                        </div>
                    </div>
                `;
                orderLinesContainer.insertAdjacentHTML('beforeend', newLineHtml);
            });

            // Funzione per caricare e visualizzare gli ordini
            async function fetchOrders() {
                try {
                    const response = await fetch("/orders/");
                    const orders = await response.json();
                    
                    // Carica i dati originali e processa per ricerca/ordinamento
                    originalOrdersData = orders.map(order => ({
                        ...order,
                        order_date_formatted: new Date(order.order_date).toLocaleDateString('it-IT'),
                        order_date_sort: new Date(order.order_date)
                    }));
                    
                    filteredOrdersData = [...originalOrdersData];
                    sortOrders('id', 'desc'); // Ordine di default: ID decrescente
                    renderOrdersTable();
                    
                } catch (error) {
                    console.error("Errore nel caricamento degli ordini:", error);
                }
            }

            // Funzione per renderizzare la tabella ordini
            function renderOrdersTable() {
                ordersTableBody.innerHTML = '';

                for (const order of filteredOrdersData) {
                        const row = document.createElement("tr");
                        row.setAttribute("data-order-id", order.id);
                        
                        // Calcola progresso picking
                        let totalRequested = 0;
                        let totalPicked = 0;
                        order.lines.forEach(line => {
                            totalRequested += line.requested_quantity;
                            totalPicked += line.picked_quantity;
                        });
                        
                        const pickingProgress = totalRequested > 0 ? Math.round((totalPicked / totalRequested) * 100) : 0;
                        // Determina lo stato dell'ordine
                        let orderStatus;
                        let orderStatusClass = '';
                        if (order.is_cancelled) {
                            orderStatus = '<span class="order-status-cancelled">Annullato</span>';
                            orderStatusClass = 'order-cancelled';
                        } else if (order.is_completed) {
                            orderStatus = 'Completato';
                        } else {
                            orderStatus = 'In Corso';
                        }

                        const pickingStatus = order.is_cancelled ? 'Annullato' :
                                            order.is_completed ? 'Completato' : 
                                            pickingProgress === 0 ? 'Non Iniziato' :
                                            pickingProgress === 100 ? 'Pronto per Evasione' :
                                            `${pickingProgress}% Prelevato`;
                        
                        // Colore di riempimento della barra (più chiaro per leggibilità)
                        const progressColor = order.is_cancelled ? '#d3d3d3' :
                                            order.is_completed ? '#4ade80' :  // Verde più chiaro
                                            pickingProgress === 0 ? '#ffc107' :  // Arancione anche per 0%
                                            pickingProgress === 100 ? '#4ade80' :  // Verde più chiaro
                                            '#ffc107';  // Arancione per percentuali intermedie
                        
                        // Colore di sfondo della barra (grigio chiaro)
                        const backgroundBarColor = '#f8f9fa';
                        
                        // Genera pulsanti azioni basati sullo stato
                        let actionButtons = '';
                        
                        if (order.is_cancelled) {
                            // Ordine annullato: visualizzazione dettagli e archiviazione
                            actionButtons = `
                                <button class="view-order-button" data-order-id="${order.id}" data-completed="${order.is_completed}">
                                    Dettagli
                                </button>
                                <button class="archive-order-button" data-order-id="${order.id}" style="background-color: #6c757d; margin-left: 5px;">
                                    Archivia
                                </button>
                            `;
                        } else {
                            // Rileva se siamo su mobile per il testo del pulsante
                            const isMobile = window.innerWidth <= 768;
                            const buttonText = order.is_completed ? 'Dettagli' : (isMobile ? 'Picking' : 'Dettagli/Picking');
                            
                            actionButtons = `
                                <button class="view-order-button" data-order-id="${order.id}" data-completed="${order.is_completed}">
                                    ${buttonText}
                                </button>
                            `;

                            if (order.is_completed) {
                                // Ordine completato: può generare DDT e essere archiviato
                                actionButtons += `
                                    <button class="generate-ddt-button" data-order-id="${order.id}" data-order-number="${order.order_number}" style="background-color: #28a745; margin-left: 5px;">
                                        Genera DDT
                                    </button>
                                    <button class="archive-order-button" data-order-id="${order.id}" style="background-color: #17a2b8; margin-left: 5px;">
                                        Archivia
                                    </button>
                                `;
                            } else {
                                // Ordine in corso: può essere evaso, annullato o eliminato
                                actionButtons += `
                                    <button class="fulfill-order-button" data-order-id="${order.id}">
                                        Evadi
                                    </button>
                                    <button class="cancel-order-button" data-order-id="${order.id}" style="background-color: #dc3545; margin-left: 5px;">
                                        ❌
                                    </button>
                                `;
                                
                                // Aggiungi pulsante "Elimina" solo se non ha picking iniziato
                                if (pickingProgress === 0) {
                                    actionButtons += `
                                        <button class="delete-order-button" data-order-id="${order.id}" data-order-number="${order.order_number}" style="background-color: #6c757d; margin-left: 5px;" title="Elimina ordine (solo se non ha picking)">
                                            🗑️ Elimina
                                        </button>
                                    `;
                                }
                            }
                        }
                        
                        // Formatta peso
                        const formattedWeight = order.total_weight ? `${order.total_weight.toFixed(2)} kg` : '0 kg';
                        
                        row.innerHTML = `
                            <td>${order.id}</td>
                            <td>${order.order_number}</td>
                            <td>${order.customer_name}</td>
                            <td>${new Date(order.order_date).toLocaleDateString()}</td>
                            <td>${orderStatus}</td>
                            <td>${order.ddt_number || '-'}</td>
                            <td style="text-align: center;">${formattedWeight}</td>
                            <td style="padding: 0;">
                                <div style="background-color: ${backgroundBarColor}; height: 100%; width: 100%; position: relative; min-height: 50px; border-radius: 4px; overflow: hidden;">
                                    <div style="background-color: ${progressColor}; height: 100%; width: ${pickingProgress}%; position: absolute; top: 0; left: 0; border-radius: 4px; transition: width 0.3s ease;"></div>
                                    <span style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 14px; font-weight: bold; color: #000; text-shadow: 0 0 2px rgba(255,255,255,0.8); z-index: 10;">${pickingStatus}</span>
                                </div>
                            </td>
                            <td style="white-space: nowrap;">
                                ${actionButtons}
                            </td>
                        `;
                        
                        // Aggiungi classe CSS per ordini annullati
                        if (orderStatusClass) {
                            row.className = orderStatusClass;
                        }
                        
                        ordersTableBody.appendChild(row);
                    }

                    // Aggiungi event listeners per i pulsanti
                    document.querySelectorAll(".view-order-button").forEach(button => {
                        button.addEventListener("click", () => showOrderDetails(button.dataset.orderId, button.dataset.completed === 'true'));
                    });

                    document.querySelectorAll(".fulfill-order-button").forEach(button => {
                        button.addEventListener("click", () => {
                            if (confirm("Sei sicuro di voler evadere questo ordine? Questa azione è irreversibile.")) {
                                fulfillOrder(button.dataset.orderId);
                            }
                        });
                    });

                    document.querySelectorAll(".archive-order-button").forEach(button => {
                        button.addEventListener("click", () => archiveOrder(button.dataset.orderId));
                    });

                    // Event listener per annullamento ordini rimosso - gestito nell'event listener generale

                    document.querySelectorAll(".delete-order-button").forEach(button => {
                        button.addEventListener("click", () => {
                            if (confirm(`Sei sicuro di voler eliminare definitivamente l'ordine ${button.dataset.orderNumber}? Questa azione è irreversibile.`)) {
                                deleteOrder(button.dataset.orderId, button.dataset.orderNumber);
                            }
                        });
                    });

                    document.querySelectorAll(".generate-ddt-button").forEach(button => {
                        button.addEventListener("click", () => generateDDT(button.dataset.orderId));
                    });
            }

            // Funzione per ordinare gli ordini
            function sortOrders(column, direction) {
                currentOrdersSort = { column, direction };
                
                filteredOrdersData.sort((a, b) => {
                    let aValue, bValue;
                    
                    switch(column) {
                        case 'id':
                            aValue = parseInt(a.id);
                            bValue = parseInt(b.id);
                            break;
                        case 'order_number':
                            aValue = a.order_number;
                            bValue = b.order_number;
                            break;
                        case 'customer_name':
                            aValue = a.customer_name;
                            bValue = b.customer_name;
                            break;
                        case 'order_date':
                            aValue = a.order_date_sort;
                            bValue = b.order_date_sort;
                            break;
                        case 'status':
                            aValue = a.is_cancelled ? 'Annullato' : (a.is_completed ? 'Completato' : 'In Corso');
                            bValue = b.is_cancelled ? 'Annullato' : (b.is_completed ? 'Completato' : 'In Corso');
                            break;
                        case 'ddt_number':
                            aValue = a.ddt_number || '';
                            bValue = b.ddt_number || '';
                            break;
                        case 'total_weight':
                            aValue = a.total_weight || 0;
                            bValue = b.total_weight || 0;
                            break;
                        default:
                            return 0;
                    }
                    
                    if (column === 'order_date' || column === 'id' || column === 'total_weight') {
                        return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    } else {
                        return direction === 'asc' ? 
                            aValue.localeCompare(bValue) : 
                            bValue.localeCompare(aValue);
                    }
                });
                
                updateSortIndicators(column, direction);
            }

            // Funzione per aggiornare gli indicatori di ordinamento
            function updateSortIndicators(column, direction) {
                document.querySelectorAll('#orders-table .sortable').forEach(header => {
                    header.classList.remove('asc', 'desc');
                });
                
                const activeHeader = document.querySelector(`#orders-table .sortable[data-column="${column}"]`);
                if (activeHeader) {
                    activeHeader.classList.add(direction);
                }
            }

            // Funzione per la ricerca negli ordini
            function searchOrders() {
                const searchOrderNumber = document.getElementById('search-order-number').value.toLowerCase().trim();
                const searchCustomer = document.getElementById('search-customer').value.toLowerCase().trim();
                const searchDate = document.getElementById('search-date').value;
                const searchDDT = document.getElementById('search-ddt').value.toLowerCase().trim();

                filteredOrdersData = originalOrdersData.filter(order => {
                    const orderNumberMatch = !searchOrderNumber || order.order_number.toLowerCase().includes(searchOrderNumber);
                    const customerMatch = !searchCustomer || order.customer_name.toLowerCase().includes(searchCustomer);
                    const dateMatch = !searchDate || order.order_date.startsWith(searchDate);
                    const ddtMatch = !searchDDT || (order.ddt_number && order.ddt_number.toLowerCase().includes(searchDDT));
                    
                    return orderNumberMatch && customerMatch && dateMatch && ddtMatch;
                });

                // Mantieni l'ordinamento corrente sui dati filtrati
                sortOrders(currentOrdersSort.column, currentOrdersSort.direction);
                renderOrdersTable();
            }

            // Funzione per resettare l'ordinamento
            function resetOrdersSort() {
                currentOrdersSort = { column: 'id', direction: 'desc' };
                filteredOrdersData = [...originalOrdersData];
                sortOrders('id', 'desc');
                renderOrdersTable();
                
                // Pulisci i campi di ricerca
                document.getElementById('search-order-number').value = '';
                document.getElementById('search-customer').value = '';
                document.getElementById('search-date').value = '';
                document.getElementById('search-ddt').value = '';
            }

            // Setup degli event listener per ricerca e ordinamento ordini
            function setupOrdersSearchAndSort() {
                // Event listener per i campi di ricerca
                document.getElementById('search-order-number').addEventListener('input', searchOrders);
                document.getElementById('search-customer').addEventListener('input', searchOrders);
                document.getElementById('search-date').addEventListener('change', searchOrders);
                document.getElementById('search-ddt').addEventListener('input', searchOrders);

                // Event listener per reset
                document.getElementById('reset-orders-sort-btn').addEventListener('click', resetOrdersSort);

                // Event listener per headers ordinabili
                document.querySelectorAll('#orders-table .sortable').forEach(header => {
                    header.addEventListener('click', function() {
                        const column = this.getAttribute('data-column');
                        let direction = 'asc';
                        
                        if (currentOrdersSort.column === column && currentOrdersSort.direction === 'asc') {
                            direction = 'desc';
                        }
                        
                        sortOrders(column, direction);
                        renderOrdersTable();
                    });
                });
            }

            // Funzione per mostrare i dettagli dell'ordine e i suggerimenti di picking
            async function showOrderDetails(orderId, isCompleted) {
                try {
                    console.log("🔍 showOrderDetails called for order:", orderId, "completed:", isCompleted);
                    
                    // 1. Recupera sempre i dati base dell'ordine
                    const orderResponse = await fetch(`/orders/${orderId}`);
                    if (!orderResponse.ok) {
                        throw new Error("Errore nel recupero dei dati base dell'ordine.");
                    }
                    const order = await orderResponse.json();
                    currentOrderData = order;

                    // 2. Se l'ordine è completato o annullato, mostra dettagli semplici (senza picking)
                    if (isCompleted || order.is_cancelled) {
                        showCompletedOrderDetails(order);
                        return;
                    }

                    // 3. Per ordini non completati, usa il nuovo overlay picking
                    const suggestions = await getPickingSuggestions(orderId);
                    showModernPickingOverlay(order, suggestions);

                } catch (error) {
                    console.error("Errore in showOrderDetails:", error);
                    orderDetailsContainer.innerHTML = `<p class="error-message">${error.message}</p>`;
                    orderDetailsContainer.style.display = 'block';
                }
            }

            // Funzione per recuperare i suggerimenti di picking
            async function getPickingSuggestions(orderId) {
                try {
                    const response = await fetch(`/orders/${orderId}/picking-suggestions`);
                    if (!response.ok) {
                        console.error("Errore nel recupero dei suggerimenti di picking.");
                        return { error: true };
                    }
                    return await response.json();
                } catch (error) {
                    console.error("Errore nella chiamata picking suggestions:", error);
                    return { error: true };
                }
            }

            // Funzione per mostrare dettagli di ordini completati in overlay moderno
            function showCompletedOrderDetails(order) {
                // Aggiorna il titolo dell'overlay
                document.getElementById('completed-order-title').textContent = 
                    `📋 Dettagli Ordine #${order.order_number}`;
                
                // Informazioni generali dell'ordine
                const orderInfo = document.getElementById('completed-order-info');
                const orderDate = new Date(order.order_date).toLocaleDateString('it-IT');
                const statusText = order.is_cancelled ? 'Annullato' : 'Completato';
                const statusColor = order.is_cancelled ? '#dc3545' : '#28a745';
                
                orderInfo.innerHTML = `
                    <div style="background-color: #f8f9fa; padding: 1rem; border-radius: 6px; margin-bottom: 1rem;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <div>
                                <strong>Cliente:</strong> 
                                <span id="customer-display-${order.id}">${order.customer_name}</span>
                                <button onclick="editCustomerName('${order.order_number}', '${order.customer_name}', ${order.id})" 
                                        style="margin-left: 8px; padding: 2px 6px; font-size: 12px; border: none; 
                                               background: #007bff; color: white; border-radius: 3px; cursor: pointer;"
                                        title="Modifica nome cliente">
                                    ✏️
                                </button><br>
                                <strong>Data Ordine:</strong> ${orderDate}
                            </div>
                            <div>
                                <strong>Stato:</strong> <span style="color: ${statusColor}; font-weight: bold;">${statusText}</span><br>
                                <strong>Righe Totali:</strong> ${order.lines.length}
                            </div>
                        </div>
                    </div>
                `;
                
                // Tabella righe ordine
                const orderLinesTable = document.getElementById('completed-order-lines');
                orderLinesTable.innerHTML = '';
                
                let totalRequested = 0;
                let totalPicked = 0;
                
                order.lines.forEach(line => {
                    const isFullyPicked = line.requested_quantity === line.picked_quantity;
                    const statusIcon = isFullyPicked ? '✅' : '⚠️';
                    const statusText = isFullyPicked ? 'Completo' : 'Parziale';
                    const rowClass = isFullyPicked ? 'status-ok' : 'status-warning';
                    
                    // Accumula i totali
                    totalRequested += line.requested_quantity;
                    totalPicked += line.picked_quantity;
                    
                    const row = document.createElement('tr');
                    row.className = rowClass;
                    row.innerHTML = `
                        <td>${line.product_sku}</td>
                        <td style="text-align: center;">${line.requested_quantity}</td>
                        <td style="text-align: center;">${line.picked_quantity}</td>
                        <td style="text-align: center;">${statusIcon} ${statusText}</td>
                    `;
                    orderLinesTable.appendChild(row);
                });
                
                // Aggiungi riga totale per ordini archiviati
                const totalRow = document.createElement('tr');
                totalRow.style.backgroundColor = '#f8f9fa';
                totalRow.style.borderTop = '2px solid #0066CC';
                totalRow.style.fontWeight = 'bold';
                totalRow.innerHTML = `
                    <td style="font-weight: bold; color: #0066CC;">TOTALE</td>
                    <td style="text-align: center; font-weight: bold; color: #0066CC;">${totalRequested}</td>
                    <td style="text-align: center; font-weight: bold; color: #0066CC;">${totalPicked}</td>
                    <td style="text-align: center;">📊</td>
                `;
                orderLinesTable.appendChild(totalRow);
                
                // Messaggio di stato dinamico basato su completato/annullato
                const statusMessage = document.getElementById('completed-order-status-message');
                if (order.is_cancelled) {
                    statusMessage.innerHTML = `
                        <strong style="color: #721c24;">❌ Ordine Annullato</strong><br>
                        Questo ordine è stato annullato e non sono possibili ulteriori azioni di picking.
                    `;
                    statusMessage.style.backgroundColor = '#f8d7da';
                    statusMessage.style.border = '1px solid #f5c6cb';
                    statusMessage.style.color = '#721c24';
                } else {
                    statusMessage.innerHTML = `
                        <strong style="color: #155724;">✅ Ordine Completato</strong><br>
                        Questo ordine è stato completato e non sono possibili ulteriori azioni di picking.
                    `;
                    statusMessage.style.backgroundColor = '#d4edda';
                    statusMessage.style.border = '1px solid #c3e6cb';
                    statusMessage.style.color = '#155724';
                }
                
                // Carica i dettagli delle posizioni di prelievo per ordini completati
                if (!order.is_cancelled) {
                    loadPickupLocations(order.order_number);
                }
                
                // Mostra l'overlay
                document.getElementById('completed-order-details-overlay').style.display = 'block';
            }
            
            // Funzione per chiudere l'overlay dettagli ordine completato
            window.closeCompletedOrderDetails = function() {
                document.getElementById('completed-order-details-overlay').style.display = 'none';
                // Nascondi anche la sezione posizioni prelievo
                document.getElementById('pickup-locations-section').style.display = 'none';
                currentOrderData = null;
            }
            
            // Funzione per caricare i dettagli delle posizioni di prelievo
            async function loadPickupLocations(orderNumber) {
                const pickupSection = document.getElementById('pickup-locations-section');
                const pickupBody = document.getElementById('pickup-locations-body');
                
                try {
                    // Mostra loading nella sezione
                    pickupSection.style.display = 'block';
                    pickupBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 1rem;">🔄 Caricamento posizioni prelievo...</td></tr>';
                    
                    const response = await window.modernAuth.authenticatedFetch(`/orders/${orderNumber}/pickup-locations`);
                    if (!response.ok) {
                        throw new Error(`Errore ${response.status}: ${response.statusText}`);
                    }
                    
                    const data = await response.json();
                    
                    // Popola la tabella con i dati delle posizioni
                    if (data.pickup_locations && data.pickup_locations.length > 0) {
                        pickupBody.innerHTML = '';
                        
                        data.pickup_locations.forEach(pickup => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${pickup.product_sku}</td>
                                <td><strong>${pickup.location_from || 'N/D'}</strong></td>
                                <td style="text-align: center; font-weight: bold; color: #0066CC;">${pickup.quantity_picked}</td>
                                <td style="font-size: 0.9rem;">${pickup.timestamp}</td>
                                <td style="font-size: 0.9rem;">${pickup.operator}</td>
                            `;
                            pickupBody.appendChild(row);
                        });
                        
                        // Aggiungi riga riepilogativa
                        const totalOperations = data.total_operations;
                        const totalRow = document.createElement('tr');
                        totalRow.style.backgroundColor = '#f8f9fa';
                        totalRow.style.borderTop = '2px solid #0066CC';
                        totalRow.style.fontWeight = 'bold';
                        totalRow.innerHTML = `
                            <td colspan="2" style="font-weight: bold; color: #0066CC;">TOTALE OPERAZIONI</td>
                            <td colspan="3" style="text-align: center; font-weight: bold; color: #0066CC;">${totalOperations}</td>
                        `;
                        pickupBody.appendChild(totalRow);
                    } else {
                        pickupBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 1rem; color: #666; font-style: italic;">📭 Nessuna posizione di prelievo trovata per questo ordine</td></tr>';
                    }
                    
                } catch (error) {
                    console.error('Errore nel caricamento posizioni prelievo:', error);
                    pickupBody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 1rem; color: #dc3545;">❌ Errore nel caricamento: ${error.message}</td></tr>`;
                }
            }

            // Funzione per mostrare il nuovo overlay picking moderno per singoli ordini
            function showModernPickingOverlay(order, suggestions) {
                console.log("🚀 showModernPickingOverlay called with:", order, suggestions);
                
                // Crea dati compatibili con il formato dell'overlay esistente
                const validationData = {
                    stats: {
                        valid_count: 0,
                        warning_count: 0,
                        error_count: 0,
                        orders_count: 1,
                        total_operations: 0
                    },
                    order_summaries: {}
                };

                // Popola i dati dell'ordine
                const orderSummary = {
                    exists: true,
                    is_completed: order.is_completed,
                    customer_name: order.customer_name,
                    order_id: order.id,
                    lines: {},
                    picking_operations: []
                };

                // Aggiungi righe ordine
                order.lines.forEach(line => {
                    orderSummary.lines[line.product_sku] = {
                        requested: line.requested_quantity,
                        picked: line.picked_quantity,
                        remaining: line.requested_quantity - line.picked_quantity
                    };
                });

                // Converte i suggerimenti in operazioni di picking
                if (!suggestions.error && Object.keys(suggestions).length > 0) {
                    for (const sku in suggestions) {
                        const suggestion = suggestions[sku];
                        
                        if (suggestion.status === "out_of_stock") {
                            // Gestisci prodotti fuori stock
                            const operation = {
                                sku: sku,
                                location: "NON DISPONIBILE",
                                quantity: 0,
                                status: "error",
                                issues: [`Prodotto non presente in inventario! Richiesti: ${suggestion.needed} pz`]
                            };
                            
                            orderSummary.picking_operations.push(operation);
                            validationData.stats.error_count++;
                            validationData.stats.total_operations++;
                        } else if (suggestion.available_in_locations.length > 0) {
                            // Gestisci prodotti con ubicazioni disponibili
                            suggestion.available_in_locations.forEach(location => {
                                const operation = {
                                    sku: sku,
                                    location: location.location_name,
                                    quantity: location.quantity,
                                    status: suggestion.status === "partial_stock" ? "warning" : "valid",
                                    issues: suggestion.status === "partial_stock" ? ["Stock parziale disponibile"] : []
                                };
                                
                                orderSummary.picking_operations.push(operation);
                                
                                if (operation.status === "valid") {
                                    validationData.stats.valid_count++;
                                } else if (operation.status === "warning") {
                                    validationData.stats.warning_count++;
                                }
                                validationData.stats.total_operations++;
                            });
                        }
                    }
                } else if (suggestions.error) {
                    // Aggiungi operazione di errore
                    orderSummary.picking_operations.push({
                        sku: "Sistema",
                        location: "N/A",
                        quantity: 0,
                        status: "error",
                        issues: ["Impossibile caricare i suggerimenti di picking"]
                    });
                    validationData.stats.error_count++;
                    validationData.stats.total_operations++;
                }

                // Controlla SKU mancanti (presenti nell'ordine ma non nei suggerimenti)
                order.lines.forEach(line => {
                    if (line.requested_quantity > line.picked_quantity) { // Solo SKU con rimanenti da prelevare
                        const hasPickingSuggestion = suggestions.error || Object.keys(suggestions).includes(line.product_sku);
                        
                        if (!hasPickingSuggestion) {
                            // SKU mancante dalle ubicazioni
                            orderSummary.picking_operations.push({
                                sku: line.product_sku,
                                location: "NON TROVATO",
                                quantity: 0,
                                status: "error",
                                issues: [`Prodotto non presente in nessuna ubicazione! Richiesti: ${line.requested_quantity - line.picked_quantity} pz`]
                            });
                            validationData.stats.error_count++;
                            validationData.stats.total_operations++;
                        }
                    }
                });

                validationData.order_summaries[order.order_number] = orderSummary;

                // Chiama l'overlay esistente con i dati convertiti
                showValidationModal(validationData);
            }


            // Funzione per aggiungere un campo per un articolo prelevato
            function addPickedItemField(orderData = null) {
                const container = document.getElementById("picked-items-container");
                const fieldId = `picked-item-${Date.now()}`;
                const datalistId = `order-skus-${Date.now()}`;
                
                // Crea datalist specifica per l'ordine corrente se orderData è disponibile
                let datalistHtml = '';
                if (orderData && orderData.lines) {
                    datalistHtml = `<datalist id="${datalistId}">`;
                    for (const sku in orderData.lines) {
                        const line = orderData.lines[sku];
                        datalistHtml += `<option value="${sku}">${sku} (Richiesto: ${line.requested}, Rimanente: ${line.remaining})</option>`;
                    }
                    datalistHtml += '</datalist>';
                }
                
                const fieldHtml = `
                    <div class="picked-item-entry">
                        ${datalistHtml}
                        <label for="${fieldId}-sku">SKU:</label>
                        <input type="text" name="sku" list="${orderData ? datalistId : 'product-skus'}" required>
                        <label for="${fieldId}-location">Ubicazione:</label>
                        <input type="text" name="location" required>
                        <label for="${fieldId}-qty">Quantità:</label>
                        <input type="number" name="quantity" required>
                        <button type="button" class="remove-picked-item-button">Rimuovi</button>
                        <br><br>
                    </div>
                `;
                container.insertAdjacentHTML('beforeend', fieldHtml);
                container.querySelector('.remove-picked-item-button:last-of-type').addEventListener('click', (e) => {
                    e.target.closest('.picked-item-entry').remove();
                });
            }

            // Funzione per confermare il picking
            async function confirmPicking(orderId) {
                if (!currentOrderData) {
                    alert("Dati dell'ordine non disponibili. Riprova.");
                    return;
                }

                const pickedItems = [];
                const pickedItemEntries = document.querySelectorAll("#picked-items-container .picked-item-entry");

                for (const entry of pickedItemEntries) {
                    const sku = entry.querySelector('input[name="sku"]').value;
                    const location = entry.querySelector('input[name="location"]').value.toUpperCase();
                    const quantity = parseInt(entry.querySelector('input[name="quantity"]').value);

                    const orderLine = currentOrderData.lines.find(line => line.product_sku === sku);

                    if (!orderLine) {
                        alert(`Errore: SKU ${sku} non trovato nelle righe dell'ordine.`);
                        return; // Interrompe il processo se uno SKU non è valido
                    }

                    pickedItems.push({
                        order_line_id: orderLine.id,
                        product_sku: sku,
                        location_name: location,
                        quantity: quantity
                    });
                }
                
                if (pickedItems.length === 0) {
                    alert("Nessun articolo prelevato inserito.");
                    return;
                }

                try {
                    const response = await fetch(`/orders/${orderId}/confirm-pick`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ order_id: parseInt(orderId), picked_items: pickedItems }),
                    });

                    if (response.ok) {
                        alert("Prelievo confermato con successo!");
                        // Chiudi overlay se aperto, altrimenti chiudi dettagli tradizionali
                        const overlay = document.getElementById("picking-validation-overlay");
                        if (overlay && overlay.style.display === "flex") {
                            closePickingValidationOverlay();
                        } else {
                            orderDetailsContainer.style.display = 'none';
                        }
                        currentOrderData = null;
                        fetchOrders();
                    } else {
                        const error = await response.json();
                        alert(`Errore nella conferma prelievo: ${error.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nella conferma prelievo:", error);
                    alert("Errore di rete nella conferma prelievo.");
                }
            }

            // Funzione per evadere l'ordine
            async function fulfillOrder(orderId) {
                try {
                    // Richiedi il numero DDT all'operatore
                    const ddtNumber = prompt("Inserisci il numero DDT per l'ordine evaso:");
                    
                    // Se l'utente annulla il prompt, non procedere
                    if (ddtNumber === null) {
                        return;
                    }
                    
                    // Valida che il numero DDT non sia vuoto
                    if (ddtNumber.trim() === '') {
                        alert("Il numero DDT non può essere vuoto.");
                        return;
                    }
                    
                    // Prima marca l'ordine come completato
                    const fulfillResponse = await fetch(`/orders/${orderId}/fulfill`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ order_id: parseInt(orderId) }),
                    });

                    if (!fulfillResponse.ok) {
                        const error = await fulfillResponse.json();
                        alert(`Errore nell'evasione ordine: ${error.detail}`);
                        return;
                    }

                    // Poi archivia l'ordine con il numero DDT
                    const archiveResponse = await fetch(`/orders/${orderId}/archive`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            order_id: parseInt(orderId),
                            ddt_number: ddtNumber.trim()
                        })
                    });
                    
                    if (archiveResponse.ok) {
                        alert(`Ordine evaso e archiviato con successo! DDT: ${ddtNumber.trim()}`);
                        fetchOrders();
                    } else {
                        const error = await archiveResponse.json();
                        alert(`Errore nell'archiviazione: ${error.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nell'evasione ordine:", error);
                    alert("Errore di rete nell'evasione ordine.");
                }
            }

            // Gestione invio form Crea Ordine
            createOrderForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const orderNumber = document.getElementById("order-number").value;
                const customerName = document.getElementById("customer-name").value;
                const lines = [];

                document.querySelectorAll(".order-line").forEach(lineDiv => {
                    const productSku = lineDiv.querySelector(`input[id^="line-product-sku-"]`).value;
                    const quantity = parseInt(lineDiv.querySelector(`input[id^="line-quantity-"]`).value);
                    if (productSku && quantity > 0) {
                        lines.push({ product_sku: productSku, requested_quantity: quantity });
                    }
                });

                if (lines.length === 0) {
                    alert("Aggiungere almeno una riga d'ordine valida.");
                    return;
                }

                try {
                    const response = await fetch("/orders/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ order_number: orderNumber, customer_name: customerName, lines: lines }),
                    });

                    if (response.ok) {
                        createOrderForm.reset();
                        orderLinesContainer.innerHTML = `
                            <div class="order-line">
                                <div class="form-row">
                                    <div class="form-group">
                                        <label for="line-product-sku-0">SKU Prodotto:</label>
                                        <input type="text" id="line-product-sku-0" list="product-skus" required>
                                    </div>
                                    <div class="form-group">
                                        <label for="line-quantity-0">Quantità Richiesta:</label>
                                        <input type="number" id="line-quantity-0" required>
                                    </div>
                                </div>
                            </div>
                        `;
                        lineCounter = 0;
                        alert("Ordine creato con successo!");
                        closeOverlay('create-order-overlay');
                        fetchOrders();
                    } else {
                        const error = await response.json();
                        alert(`Errore nella creazione ordine: ${error.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nella creazione ordine:", error);
                    alert("Errore di rete nella creazione ordine.");
                }
            });

            // Gestione importazione ordini da file
            importOrdersForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const fileInput = document.getElementById("orders-file");
                
                if (fileInput.files.length === 0) {
                    console.log('Nessun file selezionato per import ordini.');
                    if (ordersFileUpload) {
                        ordersFileUpload.setStatus('error', '❌ Seleziona un file TXT da importare');
                    }
                    return;
                }

                // Mostra status di elaborazione
                if (ordersFileUpload) {
                    ordersFileUpload.setStatus('processing', '⏳ Importazione ordini in corso...');
                }

                const formData = new FormData();
                formData.append("file", fileInput.files[0]);

                try {
                    const response = await fetch("/orders/import-orders-txt", {
                        method: "POST",
                        body: formData,
                    });

                    const result = await response.json();

                    if (response.ok) {
                        if (ordersFileUpload) {
                            ordersFileUpload.setStatus('success', `✅ ${result.message}`);
                        }
                        importOrdersResult.style.color = 'green';
                        importOrdersResult.textContent = result.message;
                        fetchOrders(); // Ricarica la lista degli ordini
                        setTimeout(() => {
                            closeOverlay('import-orders-overlay');
                        }, 2000); // Chiudi dopo 2 secondi per mostrare il messaggio
                    } else {
                        if (ordersFileUpload) {
                            ordersFileUpload.setStatus('error', `❌ Errore: ${result.detail}`);
                        }
                        importOrdersResult.style.color = 'red';
                        importOrdersResult.textContent = `Errore: ${result.detail}`;
                    }
                } catch (error) {
                    console.error("Errore nell'importazione degli ordini:", error);
                    if (ordersFileUpload) {
                        ordersFileUpload.setStatus('error', '❌ Errore di rete durante l\'importazione');
                    }
                    importOrdersResult.style.color = 'red';
                    importOrdersResult.textContent = "Errore di rete durante l'importazione.";
                }
            });

            // Gestione import Excel
            const importExcelForm = document.getElementById("import-excel-form");
            const importExcelResult = document.getElementById("import-excel-result");

            importExcelForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const fileInput = document.getElementById("excel-file");
                
                if (fileInput.files.length === 0) {
                    console.log('Nessun file Excel selezionato.');
                    if (excelFileUpload) {
                        excelFileUpload.setStatus('error', '❌ Seleziona un file Excel (.xlsx)');
                    }
                    return;
                }

                const file = fileInput.files[0];
                currentExcelFileName = file.name;
                
                if (excelFileUpload) {
                    excelFileUpload.setStatus('loading', '📊 Parsing file Excel...');
                }

                try {
                    const formData = new FormData();
                    formData.append("file", file);

                    const response = await fetch("/orders/parse-excel-orders", {
                        method: "POST",
                        body: formData
                    });

                    const result = await response.json();
                    
                    if (result.success) {
                        console.log('✅ Parsing Excel completato:', result);
                        
                        if (excelFileUpload) {
                            excelFileUpload.setStatus('success', `✅ Import completato: ${result.orders_created} ordini creati, ${result.orders_updated} ordini aggiornati`);
                        }
                        
                        // Mostra risultato diretto
                        if (importExcelResult) {
                            importExcelResult.style.color = 'green';
                            importExcelResult.innerHTML = `
                            <div class="result-success">
                                <h4>✅ Import Excel Completato!</h4>
                                <p><strong>File:</strong> ${result.file_name}</p>
                                <p><strong>Ordini creati:</strong> ${result.orders_created || 0}</p>
                                <p><strong>Ordini aggiornati:</strong> ${result.orders_updated || 0}</p>
                                <p><strong>Righe elaborate:</strong> ${result.summary?.total_lines || 0}</p>
                                ${result.summary?.errors > 0 ? `<p style="color: orange;"><strong>Avvisi:</strong> ${result.summary.errors} righe con problemi (saltate)</p>` : ''}
                            </div>
                        `;
                        }
                        
                        // Ricarica la lista ordini
                        setTimeout(() => {
                            fetchOrders();
                        }, 1000);
                        
                    } else {
                        console.error('❌ Errore parsing Excel:', result);
                        if (excelFileUpload) {
                            excelFileUpload.setStatus('error', '❌ Errore nel parsing Excel');
                        }
                        if (importExcelResult) {
                            importExcelResult.style.color = 'red';
                            importExcelResult.textContent = result.message || "Errore nel parsing del file Excel.";
                        }
                    }
                } catch (error) {
                    console.error("Errore nell'import Excel:", error);
                    if (excelFileUpload) {
                        excelFileUpload.setStatus('error', '❌ Errore di rete durante l\'import Excel');
                    }
                    if (importExcelResult) {
                        importExcelResult.style.color = 'red';
                        importExcelResult.textContent = "Errore di rete durante l'import Excel.";
                    }
                }
            });

            // Gestione prelievo da file TXT (nuovo flusso con recap)
            const importPickingForm = document.getElementById("import-picking-form");
            const importPickingResult = document.getElementById("import-picking-result");
            let currentPickingFile = null;
            let currentPickingRecapData = null;

            importPickingForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const fileInput = document.getElementById("picking-file");
                
                if (fileInput.files.length === 0) {
                    console.log('Nessun file selezionato per picking.');
                    if (pickingFileUpload) {
                        pickingFileUpload.setStatus('error', '❌ Seleziona un file o inserisci dati scanner');
                    }
                    return;
                }

                // Mostra status di elaborazione
                if (pickingFileUpload) {
                    pickingFileUpload.setStatus('processing', '⏳ Validazione file in corso...');
                }

                currentPickingFile = fileInput.files[0];
                const formData = new FormData();
                formData.append("file", currentPickingFile);

                try {
                    importPickingResult.textContent = "Validazione in corso...";
                    importPickingResult.style.color = 'blue';

                    const response = await fetch("/orders/validate-picking-txt", {
                        method: "POST",
                        body: formData,
                    });

                    const result = await response.json();

                    if (response.ok) {
                        if (pickingFileUpload) {
                            pickingFileUpload.setStatus('success', '✅ Validazione completata. Controlla il riepilogo.');
                        }
                        importPickingResult.style.color = 'green';
                        importPickingResult.textContent = "Validazione completata. Controlla il riepilogo.";
                        closeOverlay('picking-file-overlay');
                        showPickingRecap(result);
                    } else {
                        if (pickingFileUpload) {
                            pickingFileUpload.setStatus('error', `❌ Errore: ${result.detail}`);
                        }
                        importPickingResult.style.color = 'red';
                        importPickingResult.textContent = `Errore: ${result.detail}`;
                    }
                } catch (error) {
                    console.error("Errore nella validazione:", error);
                    if (pickingFileUpload) {
                        pickingFileUpload.setStatus('error', '❌ Errore di rete durante la validazione');
                    }
                    importPickingResult.style.color = 'red';
                    importPickingResult.textContent = "Errore di rete durante la validazione.";
                }
            });

            // Funzioni per gestire l'overlay di validazione picking moderno
            window.showValidationModal = function(validationData) {
                console.log("🔍 showValidationModal called with:", validationData); // Debug
                
                const overlay = document.getElementById("picking-validation-overlay");
                const body = document.getElementById("picking-validation-body");
                const title = document.getElementById("picking-validation-title");
                const subtitle = document.getElementById("picking-validation-subtitle");
                const printButton = document.getElementById("print-picking-overlay-button");
                
                console.log("🔍 Overlay elements found:", {
                    overlay: !!overlay,
                    body: !!body,
                    title: !!title,
                    subtitle: !!subtitle,
                    printButton: !!printButton
                });
                
                if (!overlay || !body) {
                    console.error("❌ Picking overlay elements not found!", {overlay, body});
                    alert("Errore: elementi overlay non trovati. Controlla la console.");
                    return;
                }
                
                // Aggiorna titolo e sottotitolo con colori corretti
                title.textContent = `📋 Validazione Picking (${validationData.stats.orders_count} ordini)`;
                title.style.color = "white";
                title.style.fontWeight = "bold";
                subtitle.textContent = `${validationData.stats.total_operations} operazioni trovate • ${validationData.stats.valid_count} valide • ${validationData.stats.error_count} errori`;
                subtitle.style.color = "white";
                
                // Header con statistiche - palette del sito
                let content = `
                    <div style="display: flex; justify-content: space-around; text-align: center; margin-bottom: 30px; padding: 20px; background: #F2F2F2; border-radius: 8px;">
                        <div style="flex: 1;">
                            <div style="font-size: 32px; font-weight: bold; color: #0097E0;">${validationData.stats.valid_count}</div>
                            <div style="color: #00516E; font-size: 14px;">Operazioni Valide</div>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-size: 32px; font-weight: bold; color: #00D4F5;">${validationData.stats.warning_count}</div>
                            <div style="color: #00516E; font-size: 14px;">Avvertimenti</div>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-size: 32px; font-weight: bold; color: #FF5913;">${validationData.stats.error_count}</div>
                            <div style="color: #00516E; font-size: 14px;">Errori</div>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-size: 32px; font-weight: bold; color: #00516E;">${validationData.stats.orders_count}</div>
                            <div style="color: #00516E; font-size: 14px;">Ordini Coinvolti</div>
                        </div>
                    </div>
                `;

                // Pulsante Picking in Tempo Reale (solo per picking singolo ordine)
                const isManualPicking = validationData.stats.orders_count === 1 && !validationData.isFileValidation;
                if (isManualPicking && validationData.stats.valid_count > 0) {
                    const orderData = Object.values(validationData.order_summaries)[0];
                    content += `
                        <div style="text-align: center; margin-bottom: 30px;">
                            <button id="real-time-picking-button" style="
                                background: linear-gradient(135deg, #FF5913, #FF7A44); 
                                color: white; 
                                border: none; 
                                padding: 15px 30px; 
                                border-radius: 8px; 
                                font-size: 18px; 
                                font-weight: bold; 
                                cursor: pointer;
                                box-shadow: 0 4px 8px rgba(255, 89, 19, 0.3);
                                transition: all 0.3s ease;
                                min-width: 250px;
                            " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                                📱 Picking in Tempo Reale
                            </button>
                        </div>
                    `;
                }

                // Raggruppa per ordine con design moderno
                for (const orderNumber in validationData.order_summaries) {
                    const orderSummary = validationData.order_summaries[orderNumber];
                    const orderStatus = !orderSummary.exists ? 'error' : orderSummary.is_completed ? 'warning' : 'success';
                    const statusColors = {
                        'error': { bg: '#FFE6E6', border: '#FF5913', text: '#721c24' },
                        'warning': { bg: '#E6F7FF', border: '#00D4F5', text: '#00516E' },
                        'success': { bg: '#E6F7FF', border: '#0097E0', text: '#00516E' }
                    };
                    
                    content += `
                        <div style="
                            border: 2px solid ${statusColors[orderStatus].border}; 
                            border-radius: 12px; 
                            margin: 20px 0; 
                            overflow: hidden;
                            background: white;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        ">
                            <!-- Header ordine -->
                            <div style="
                                background: ${statusColors[orderStatus].bg}; 
                                padding: 20px; 
                                border-bottom: 1px solid ${statusColors[orderStatus].border};
                            ">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div>
                                        <h3 style="margin: 0 0 5px 0; color: ${statusColors[orderStatus].text}; font-size: 20px;">
                                            📦 Ordine ${orderNumber}
                                        </h3>
                                        <div style="color: ${statusColors[orderStatus].text}; opacity: 0.8; font-size: 14px;">
                                            Cliente: <span id="customer-display-picking-${orderSummary.order_id}">${orderSummary.customer_name}</span>
                                            <button onclick="editCustomerName('${orderNumber}', '${orderSummary.customer_name}', ${orderSummary.order_id})" 
                                                    style="margin-left: 8px; padding: 1px 4px; font-size: 10px; border: none; 
                                                           background: #007bff; color: white; border-radius: 3px; cursor: pointer;"
                                                    title="Modifica nome cliente">
                                                ✏️
                                            </button>
                                        </div>
                                    </div>
                                    <div style="
                                        background: ${statusColors[orderStatus].border}; 
                                        color: white; 
                                        padding: 8px 15px; 
                                        border-radius: 20px; 
                                        font-size: 12px; 
                                        font-weight: bold;
                                        text-transform: uppercase;
                                    ">
                                        ${!orderSummary.exists ? 'NON TROVATO' : orderSummary.is_completed ? 'COMPLETATO' : 'ATTIVO'}
                                    </div>
                                </div>
                            </div>
                            
                            <div style="padding: 20px;">
                    `;
                    
                    // Stato righe ordine con tabella moderna
                    if (orderSummary.exists && Object.keys(orderSummary.lines).length > 0) {
                        content += `
                            <h4 style="margin: 0 0 15px 0; color: #495057; font-size: 16px;">📋 Stato Righe Ordine</h4>
                            <div style="overflow-x: auto; margin-bottom: 25px;">
                                <table style="
                                    width: 100%; 
                                    border-collapse: collapse; 
                                    background: white; 
                                    border-radius: 8px; 
                                    overflow: hidden;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                ">
                                    <thead>
                                        <tr style="background: #f8f9fa;">
                                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: 600;">SKU</th>
                                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6; font-weight: 600;">Richiesto</th>
                                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6; font-weight: 600;">Già Prelevato</th>
                                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6; font-weight: 600;">Rimanente</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        `;
                        
                        let totalRequested = 0;
                        let totalPicked = 0;
                        let totalRemaining = 0;
                        
                        for (const sku in orderSummary.lines) {
                            const line = orderSummary.lines[sku];
                            const isComplete = line.remaining === 0;
                            
                            // Accumula i totali
                            totalRequested += line.requested;
                            totalPicked += line.picked;
                            totalRemaining += line.remaining;
                            
                            content += `
                                <tr style="border-bottom: 1px solid #dee2e6;">
                                    <td style="padding: 12px; font-weight: 500;">${sku}</td>
                                    <td style="padding: 12px; text-align: center;">${line.requested}</td>
                                    <td style="padding: 12px; text-align: center; color: ${isComplete ? '#28a745' : '#6c757d'};">${line.picked}</td>
                                    <td style="padding: 12px; text-align: center; font-weight: bold; color: ${isComplete ? '#28a745' : '#dc3545'};">${line.remaining}</td>
                                </tr>
                            `;
                        }
                        
                        // Aggiungi riga totale per ordini attivi
                        content += `
                            <tr style="border-top: 2px solid #0066CC; background-color: #f8f9fa; font-weight: bold;">
                                <td style="padding: 12px; font-weight: bold; color: #0066CC;">TOTALE</td>
                                <td style="padding: 12px; text-align: center; font-weight: bold; color: #0066CC;">${totalRequested}</td>
                                <td style="padding: 12px; text-align: center; font-weight: bold; color: #0066CC;">${totalPicked}</td>
                                <td style="padding: 12px; text-align: center; font-weight: bold; color: ${totalRemaining === 0 ? '#28a745' : '#0066CC'};">${totalRemaining}</td>
                            </tr>
                        `;
                        
                        content += `
                                    </tbody>
                                </table>
                            </div>
                        `;
                    }
                    
                    // Operazioni di picking con design moderno
                    content += `<h4 style="margin: 0 0 15px 0; color: #495057; font-size: 16px;">🔄 Operazioni di Picking</h4>`;
                    
                    if (orderSummary.picking_operations.length > 0) {
                        orderSummary.picking_operations.forEach((op, index) => {
                            const opColors = {
                                'valid': { bg: '#E6F7FF', border: '#0097E0', text: '#00516E', icon: '✅' },
                                'warning': { bg: '#FFF7E6', border: '#00D4F5', text: '#00516E', icon: '⚠️' },
                                'error': { bg: '#FFE6E6', border: '#FF5913', text: '#721c24', icon: '❌' }
                            };
                            const color = opColors[op.status] || opColors['error'];
                            
                            content += `
                                <div style="
                                    margin: ${index > 0 ? '12px' : '0'} 0; 
                                    padding: 18px; 
                                    background: ${color.bg}; 
                                    border-left: 5px solid ${color.border}; 
                                    border-radius: 8px;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                ">
                                    <div style="display: flex; align-items: center; justify-content: space-between;">
                                        <div style="display: flex; align-items: center; gap: 15px;">
                                            <span style="font-size: 24px;">${color.icon}</span>
                                            <div>
                                                <strong style="color: ${color.text}; font-size: 18px; font-weight: 600;">${op.sku}</strong>
                                                <div style="margin-top: 4px;">
                                                    <span style="
                                                        background: ${color.border}; 
                                                        color: white; 
                                                        padding: 4px 12px; 
                                                        border-radius: 20px; 
                                                        font-size: 14px; 
                                                        font-weight: bold;
                                                        margin-right: 10px;
                                                    ">📍 ${op.location}</span>
                                                    <span style="
                                                        background: ${op.status === 'error' ? '#FF5913' : '#00516E'}; 
                                                        color: white; 
                                                        padding: 4px 12px; 
                                                        border-radius: 20px; 
                                                        font-size: 14px; 
                                                        font-weight: bold;
                                                    ">${op.quantity > 0 ? `${op.quantity} pz` : 'Non disponibile'}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                            `;
                            
                            if (op.issues && op.issues.length > 0) {
                                content += `
                                    <div style="margin-top: 15px; padding-top: 12px; border-top: 1px solid ${color.border};">
                                        <strong style="color: ${color.text}; font-size: 14px;">
                                            💡 ${op.issues.join(' • ')}
                                        </strong>
                                    </div>
                                `;
                            }
                            
                            content += `</div>`;
                        });
                    } else {
                        content += `
                            <div style="text-align: center; padding: 30px; color: #6c757d; font-style: italic;">
                                Nessuna operazione di picking trovata per questo ordine
                            </div>
                        `;
                    }
                    
                    content += `</div></div>`;
                }

                // Verifica se è un picking manuale (un solo ordine e non file validation)
                // isManualPicking già dichiarata prima
                
                // Aggiungi il form di picking manuale PRIMA di settare body.innerHTML
                if (isManualPicking) {
                    // Per picking manuale, aggiungi form direttamente nell'overlay
                    const orderData = Object.values(validationData.order_summaries)[0];
                    
                    content += `
                        <div style="
                            margin-top: 30px; 
                            padding: 25px; 
                            background: #F2F2F2; 
                            border-radius: 12px; 
                            border: 2px solid #0097E0;
                        ">
                            <h3 style="margin: 0 0 20px 0; color: #00516E; font-size: 20px;">
                                🖊️ Conferma Prelievo Manuale
                            </h3>
                            <p style="color: #00516E; margin-bottom: 20px;">
                                Inserisci i dettagli dei prodotti effettivamente prelevati:
                            </p>
                            
                            <form id="confirm-pick-form" data-order-id="${orderData.order_id}">
                                <div id="picked-items-container" style="margin-bottom: 20px;">
                                    <!-- Campi dinamici aggiunti da JavaScript -->
                                </div>
                                
                                <div style="margin-bottom: 20px;">
                                    <button type="button" id="add-picked-item-button" style="
                                        background: #00D4F5; 
                                        color: #00516E; 
                                        border: none; 
                                        padding: 10px 20px; 
                                        border-radius: 6px; 
                                        cursor: pointer;
                                        font-weight: 500;
                                    ">+ Aggiungi Articolo Prelevato</button>
                                </div>
                                
                                <button type="submit" style="
                                    background: #0097E0; 
                                    color: white; 
                                    border: none; 
                                    padding: 15px 30px; 
                                    border-radius: 8px; 
                                    cursor: pointer;
                                    font-size: 16px;
                                    font-weight: 600;
                                    width: 100%;
                                ">✅ Conferma Prelievo</button>
                            </form>
                        </div>
                    `;
                }

                body.innerHTML = content;
                
                // Gestisce il pulsante di stampa
                if (printButton) {
                    printButton.onclick = function() {
                        // Trova il primo ordine per ottenere l'ID (assumendo che ci sia almeno un ordine)
                        const firstOrderNumber = Object.keys(validationData.order_summaries)[0];
                        if (firstOrderNumber) {
                            const orderSummary = validationData.order_summaries[firstOrderNumber];
                            if (orderSummary.order_id) {
                                window.open(`/orders/${orderSummary.order_id}/picking-list-print`, '_blank');
                            }
                        }
                    };
                }
                
                // Gestisci bottoni footer in base al tipo di picking
                const commitAllButton = document.getElementById("commit-all-button");
                const commitForceButton = document.getElementById("commit-force-button");
                
                if (isManualPicking) {
                    // Nasconde i bottoni standard per picking manuale
                    if (commitAllButton) commitAllButton.style.display = "none";
                    if (commitForceButton) commitForceButton.style.display = "none";
                } else {
                    // Per validazione file, usa la logica originale
                    if (commitAllButton) {
                        commitAllButton.disabled = validationData.stats.valid_count === 0;
                        commitAllButton.onclick = function() { commitPicking(false); };
                    }
                    if (commitForceButton) {
                        commitForceButton.disabled = validationData.stats.total_operations === validationData.stats.error_count;
                        commitForceButton.style.display = "block";
                    }
                }
                
                console.log("🚀 Showing overlay...");
                overlay.style.display = "flex";
                console.log("✅ Overlay display set to flex, current style:", overlay.style.display);
                
                // Force reflow per assicurarsi che l'overlay venga renderizzato
                overlay.offsetHeight;
                
                // Aggiungi click-outside-to-close per overlay picking
                overlay.onclick = function(event) {
                    if (event.target === overlay) {
                        closePickingValidationOverlay();
                    }
                };
                
                console.log("📊 Final overlay visibility check:", {
                    display: overlay.style.display,
                    visibility: getComputedStyle(overlay).visibility,
                    opacity: getComputedStyle(overlay).opacity,
                    zIndex: getComputedStyle(overlay).zIndex
                });
                
                // Aggiungi event listeners per il form di picking manuale se presente
                if (isManualPicking) {
                    setTimeout(() => {
                        const addButton = document.getElementById("add-picked-item-button");
                        const pickForm = document.getElementById("confirm-pick-form");
                        
                        if (addButton) {
                            const orderData = Object.values(validationData.order_summaries)[0];
                            addButton.addEventListener("click", () => addPickedItemField(orderData));
                        }
                        
                        if (pickForm) {
                            pickForm.addEventListener("submit", async (event) => {
                                event.preventDefault();
                                const orderData = Object.values(validationData.order_summaries)[0];
                                await confirmPicking(orderData.order_id);
                            });
                        }
                        
                        console.log("✅ Event listeners added for manual picking form");
                        
                        // Event listener per pulsante picking in tempo reale
                        const realTimePickingButton = document.getElementById("real-time-picking-button");
                        if (realTimePickingButton) {
                            realTimePickingButton.addEventListener("click", () => {
                                const orderData = Object.values(validationData.order_summaries)[0];
                                startRealTimePicking(orderData, validationData);
                            });
                        }
                    }, 100);
                }
            }

            window.closeValidationModal = function() {
                closePickingValidationOverlay();
            }
            
            window.closePickingValidationOverlay = function() {
                const overlay = document.getElementById("picking-validation-overlay");
                if (overlay) {
                    overlay.style.display = "none";
                }
            }

            window.commitPicking = async function(force) {
                if (!currentPickingFile) {
                    alert("File non disponibile per il commit.");
                    return;
                }

                const formData = new FormData();
                formData.append("file", currentPickingFile);
                if (force) {
                    formData.append("force", "true");
                }

                try {
                    importPickingResult.textContent = "Esecuzione prelievo in corso...";
                    importPickingResult.style.color = 'blue';

                    const response = await fetch("/orders/commit-picking-txt", {
                        method: "POST",
                        body: formData,
                    });

                    let result;
                    try {
                        result = await response.json();
                    } catch (e) {
                        throw new Error("Risposta del server non valida");
                    }

                    closePickingValidationOverlay();

                    if (response.ok) {
                        importPickingResult.style.color = 'green';
                        const successfulOps = result.successful_operations || [];
                        const skippedOps = result.skipped_operations || [];
                        
                        importPickingResult.innerHTML = `
                            <strong>${result.message || 'Operazione completata'}</strong><br>
                            <details style="margin-top: 10px;">
                                <summary>Dettagli operazioni (${successfulOps.length} riuscite, ${skippedOps.length} saltate)</summary>
                                <div style="margin-top: 10px;">
                                    ${successfulOps.length > 0 ? '<strong>Operazioni riuscite:</strong><ul>' + successfulOps.map(op => `<li>${op}</li>`).join('') + '</ul>' : ''}
                                    ${skippedOps.length > 0 ? '<strong>Operazioni saltate:</strong><ul>' + skippedOps.map(op => `<li>${op}</li>`).join('') + '</ul>' : ''}
                                </div>
                            </details>
                        `;
                        fetchOrders(); // Ricarica la lista degli ordini
                    } else {
                        importPickingResult.style.color = 'red';
                        importPickingResult.textContent = `Errore: ${result.detail || 'Errore sconosciuto'}`;
                    }
                } catch (error) {
                    console.error("Errore nel commit prelievo:", error);
                    importPickingResult.style.color = 'red';
                    importPickingResult.textContent = "Errore di rete durante il commit.";
                    closePickingValidationOverlay();
                }
            }

            // Gestori per i nuovi pulsanti
            ordersTableBody.addEventListener("click", async function(e) {
                if (e.target.classList.contains("archive-order-button")) {
                    const orderId = e.target.getAttribute("data-order-id");
                    if (confirm("Sei sicuro di voler archiviare questo ordine? Verrà rimosso dalla lista principale.")) {
                        await archiveOrder(orderId);
                    }
                } else if (e.target.classList.contains("cancel-order-button")) {
                    const orderId = e.target.getAttribute("data-order-id");
                    if (confirm("Sei sicuro di voler annullare questo ordine? I prodotti prelevati saranno ripristinati in TERRA per riposizionamento.")) {
                        await cancelOrder(orderId);
                    }
                } else if (e.target.classList.contains("generate-ddt-button")) {
                    const orderId = e.target.getAttribute("data-order-id");
                    const orderNumber = e.target.getAttribute("data-order-number");
                    if (confirm(`Vuoi generare il DDT per l'ordine ${orderNumber}?`)) {
                        await generateDDTFromOrder(orderNumber);
                    }
                } else if (e.target.classList.contains("delete-order-button")) {
                    const orderId = e.target.getAttribute("data-order-id");
                    const orderNumber = e.target.getAttribute("data-order-number");
                    if (confirm(`⚠️ ATTENZIONE: Vuoi eliminare COMPLETAMENTE l'ordine ${orderNumber}?\n\nQuesta azione è IRREVERSIBILE e cancellerà l'ordine dal database.\n\nProcedere solo se l'ordine è stato caricato per errore.`)) {
                        await deleteOrderCompletely(orderId, orderNumber);
                    }
                }
            });

            // Gestione apertura sezione ordini archiviati
            document.getElementById("archived-orders-section").addEventListener("toggle", function(e) {
                if (e.target.open) {
                    fetchArchivedOrders();
                }
            });

            // Funzione per archiviare un ordine (per ordini già completati)
            async function archiveOrder(orderId) {
                try {
                    // Per ordini già completati, potrebbe già avere un DDT o richiederne uno nuovo
                    let ddtNumber = prompt("Inserisci il numero DDT per l'ordine (lascia vuoto se già presente):");
                    
                    // Se l'utente annulla il prompt, non procedere
                    if (ddtNumber === null) {
                        return;
                    }
                    
                    // Permetti DDT vuoto per ordini già completati che potrebbero già avere un DDT
                    const response = await fetch(`/orders/${orderId}/archive`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            order_id: parseInt(orderId),
                            ddt_number: ddtNumber ? ddtNumber.trim() : null
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(`Ordine archiviato con successo: ${result.message}`);
                        fetchOrders(); // Ricarica la lista degli ordini
                    } else {
                        alert(`Errore nell'archiviazione: ${result.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nell'archiviazione:", error);
                    alert("Errore di rete durante l'archiviazione");
                }
            }

            // Funzione per annullare un ordine
            async function cancelOrder(orderId) {
                try {
                    const response = await fetch(`/orders/${orderId}/cancel`, {
                        method: "POST"
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        let message = `Ordine annullato con successo: ${result.message}`;
                        
                        if (result.inventory_restored && result.inventory_restored.length > 0) {
                            message += "\n\nProdotti ripristinati automaticamente in TERRA:\n";
                            result.inventory_restored.forEach(item => {
                                message += `- ${item.product_sku}: ${item.quantity} pz → ${item.restored_to}\n`;
                            });
                            message += `\n${result.note}`;
                        }
                        
                        alert(message);
                        fetchOrders(); // Ricarica la lista degli ordini
                    } else {
                        alert(`Errore nell'annullamento: ${result.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nell'annullamento:", error);
                    alert("Errore di rete durante l'annullamento");
                }
            }

            // Funzione per caricare gli ordini archiviati
            async function fetchArchivedOrders() {
                try {
                    const response = await fetch("/orders/archived");
                    const data = await response.json();
                    
                    // Carica i dati originali e processa per ricerca/ordinamento
                    if (data.orders && data.orders.length > 0) {
                        originalArchivedData = data.orders.map(order => ({
                            ...order,
                            order_date_formatted: new Date(order.order_date).toLocaleDateString('it-IT'),
                            order_date_sort: new Date(order.order_date),
                            archived_at_formatted: new Date(order.archived_at).toLocaleDateString('it-IT'),
                            archived_at_sort: new Date(order.archived_at)
                        }));
                    } else {
                        originalArchivedData = [];
                    }
                    
                    filteredArchivedData = [...originalArchivedData];
                    sortArchivedOrders('id', 'desc'); // Ordine di default: ID decrescente
                    renderArchivedOrdersTable();
                    
                } catch (error) {
                    console.error("Errore nel caricamento degli ordini archiviati:", error);
                }
            }

            // Funzione per renderizzare la tabella ordini archiviati
            function renderArchivedOrdersTable() {
                const archivedOrdersTableBody = document.querySelector("#archived-orders-table tbody");
                archivedOrdersTableBody.innerHTML = '';

                if (filteredArchivedData.length > 0) {
                    for (const order of filteredArchivedData) {
                            const row = document.createElement("tr");
                            
                            // Applica stile per ordini annullati anche negli archiviati
                            const orderStatusClass = order.is_cancelled ? 'order-cancelled' : '';
                            const orderStatusText = order.is_cancelled ? '<span class="order-status-cancelled">Annullato</span>' : 'Completato';
                            const formattedWeight = order.total_weight ? `${order.total_weight.toFixed(2)} kg` : '0 kg';
                            
                            row.innerHTML = `
                                <td>${order.id}</td>
                                <td>${order.order_number}</td>
                                <td>${order.customer_name}</td>
                                <td>${new Date(order.order_date).toLocaleDateString()}</td>
                                <td>${order.archived_date ? new Date(order.archived_date).toLocaleDateString() : 'N/A'}</td>
                                <td>${orderStatusText}</td>
                                <td>${order.ddt_number || '-'}</td>
                                <td style="text-align: center;">${formattedWeight}</td>
                                <td>
                                    <button class="view-archived-order-button" data-order-id="${order.id}">
                                        Dettagli
                                    </button>
                                    <button class="unarchive-order-button" data-order-id="${order.id}" style="background-color: #ffc107; margin-left: 5px;">
                                        Ripristina
                                    </button>
                                </td>
                            `;
                            
                            // Aggiungi classe CSS per ordini annullati
                            if (orderStatusClass) {
                                row.className = orderStatusClass;
                            }
                            
                            archivedOrdersTableBody.appendChild(row);
                        }

                        // Gestori per i pulsanti degli ordini archiviati
                        document.querySelectorAll(".unarchive-order-button").forEach(button => {
                            button.addEventListener("click", async function() {
                                const orderId = this.getAttribute("data-order-id");
                                if (confirm("Sei sicuro di voler ripristinare questo ordine dalla lista principale?")) {
                                    await unarchiveOrder(orderId);
                                }
                            });
                        });

                        // Per ora gestiamo i dettagli ordini archiviati come quelli normali
                        document.querySelectorAll(".view-archived-order-button").forEach(button => {
                            button.addEventListener("click", function() {
                                const orderId = this.getAttribute("data-order-id");
                                // Trova l'ordine nei dati filtrati e visualizza i dettagli
                                const order = filteredArchivedData.find(o => o.id == orderId);
                                if (order) {
                                    showOrderDetails(order.id, true);
                                }
                            });
                        });
                    } else {
                        archivedOrdersTableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #666;">Nessun ordine archiviato</td></tr>';
                    }
            }

            // Funzione per ordinare gli ordini archiviati
            function sortArchivedOrders(column, direction) {
                currentArchivedSort = { column, direction };
                
                filteredArchivedData.sort((a, b) => {
                    let aValue, bValue;
                    
                    switch(column) {
                        case 'id':
                            aValue = parseInt(a.id);
                            bValue = parseInt(b.id);
                            break;
                        case 'order_number':
                            aValue = a.order_number;
                            bValue = b.order_number;
                            break;
                        case 'customer_name':
                            aValue = a.customer_name;
                            bValue = b.customer_name;
                            break;
                        case 'order_date':
                            aValue = a.order_date_sort;
                            bValue = b.order_date_sort;
                            break;
                        case 'archived_at':
                            aValue = a.archived_at_sort;
                            bValue = b.archived_at_sort;
                            break;
                        case 'status':
                            aValue = a.is_cancelled ? 'Annullato' : 'Completato';
                            bValue = b.is_cancelled ? 'Annullato' : 'Completato';
                            break;
                        case 'total_weight':
                            aValue = a.total_weight || 0;
                            bValue = b.total_weight || 0;
                            break;
                        default:
                            return 0;
                    }
                    
                    if (column === 'order_date' || column === 'archived_at' || column === 'id' || column === 'total_weight') {
                        return direction === 'asc' ? aValue - bValue : bValue - aValue;
                    } else {
                        return direction === 'asc' ? 
                            aValue.localeCompare(bValue) : 
                            bValue.localeCompare(aValue);
                    }
                });
                
                updateArchivedSortIndicators(column, direction);
            }

            // Funzione per aggiornare gli indicatori di ordinamento archiviati
            function updateArchivedSortIndicators(column, direction) {
                document.querySelectorAll('#archived-orders-table .sortable').forEach(header => {
                    header.classList.remove('asc', 'desc');
                });
                
                const activeHeader = document.querySelector(`#archived-orders-table .sortable[data-column="${column}"]`);
                if (activeHeader) {
                    activeHeader.classList.add(direction);
                }
            }

            // Funzione per la ricerca negli ordini archiviati
            function searchArchivedOrders() {
                const searchOrderNumber = document.getElementById('search-archived-order-number').value.toLowerCase().trim();
                const searchCustomer = document.getElementById('search-archived-customer').value.toLowerCase().trim();
                const searchDate = document.getElementById('search-archived-date').value;
                const searchDDT = document.getElementById('search-archived-ddt').value.toLowerCase().trim();

                filteredArchivedData = originalArchivedData.filter(order => {
                    const orderNumberMatch = !searchOrderNumber || order.order_number.toLowerCase().includes(searchOrderNumber);
                    const customerMatch = !searchCustomer || order.customer_name.toLowerCase().includes(searchCustomer);
                    const dateMatch = !searchDate || order.order_date.startsWith(searchDate);
                    const ddtMatch = !searchDDT || (order.ddt_number && order.ddt_number.toLowerCase().includes(searchDDT));
                    
                    return orderNumberMatch && customerMatch && dateMatch && ddtMatch;
                });

                // Mantieni l'ordinamento corrente sui dati filtrati
                sortArchivedOrders(currentArchivedSort.column, currentArchivedSort.direction);
                renderArchivedOrdersTable();
            }

            // Funzione per resettare l'ordinamento archiviati
            function resetArchivedSort() {
                currentArchivedSort = { column: 'id', direction: 'desc' };
                filteredArchivedData = [...originalArchivedData];
                sortArchivedOrders('id', 'desc');
                renderArchivedOrdersTable();
                
                // Pulisci i campi di ricerca
                document.getElementById('search-archived-order-number').value = '';
                document.getElementById('search-archived-customer').value = '';
                document.getElementById('search-archived-date').value = '';
                document.getElementById('search-archived-ddt').value = '';
            }

            // Setup degli event listener per ricerca e ordinamento ordini archiviati
            function setupArchivedSearchAndSort() {
                // Event listener per i campi di ricerca
                const searchArchivedOrderNumber = document.getElementById('search-archived-order-number');
                const searchArchivedCustomer = document.getElementById('search-archived-customer');
                const searchArchivedDate = document.getElementById('search-archived-date');
                const searchArchivedDDT = document.getElementById('search-archived-ddt');
                const resetArchivedBtn = document.getElementById('reset-archived-sort-btn');

                if (searchArchivedOrderNumber) searchArchivedOrderNumber.addEventListener('input', searchArchivedOrders);
                if (searchArchivedCustomer) searchArchivedCustomer.addEventListener('input', searchArchivedOrders);
                if (searchArchivedDate) searchArchivedDate.addEventListener('change', searchArchivedOrders);
                if (searchArchivedDDT) searchArchivedDDT.addEventListener('input', searchArchivedOrders);
                if (resetArchivedBtn) resetArchivedBtn.addEventListener('click', resetArchivedSort);

                // Event listener per headers ordinabili
                document.querySelectorAll('#archived-orders-table .sortable').forEach(header => {
                    header.addEventListener('click', function() {
                        const column = this.getAttribute('data-column');
                        let direction = 'asc';
                        
                        if (currentArchivedSort.column === column && currentArchivedSort.direction === 'asc') {
                            direction = 'desc';
                        }
                        
                        sortArchivedOrders(column, direction);
                        renderArchivedOrdersTable();
                    });
                });
            }

            // Funzione per ripristinare un ordine dall'archivio
            async function unarchiveOrder(orderId) {
                try {
                    const response = await fetch(`/orders/${orderId}/unarchive`, {
                        method: "DELETE"
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(`Ordine ripristinato con successo: ${result.message}`);
                        fetchArchivedOrders(); // Ricarica la lista degli ordini archiviati
                        fetchOrders(); // Ricarica la lista degli ordini principali
                    } else {
                        alert(`Errore nel ripristino: ${result.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nel ripristino:", error);
                    alert("Errore di rete durante il ripristino");
                }
            }

            // Funzione per generare DDT da ordine
            async function generateDDTFromOrder(orderNumber) {
                try {
                    const response = await fetch('/ddt/generate', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            order_number: orderNumber
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(`DDT generato con successo! Numero DDT: ${result.ddt.ddt_number}`);
                        // Opzionalmente, apri il DDT in una nuova finestra
                        const openDDT = confirm("Vuoi aprire il DDT appena generato?");
                        if (openDDT) {
                            window.open(`/ddt/manage`, '_blank');
                        }
                    } else {
                        alert(`Errore nella generazione del DDT: ${result.detail || result.message}`);
                    }
                } catch (error) {
                    console.error("Errore nella generazione DDT:", error);
                    alert("Errore di rete durante la generazione del DDT");
                }
            }

            // Funzione per eliminare completamente un ordine
            async function deleteOrderCompletely(orderId, orderNumber) {
                try {
                    const response = await fetch(`/orders/${orderId}/delete`, {
                        method: 'DELETE'
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(`✅ Ordine ${orderNumber} eliminato con successo!`);
                        fetchOrders(); // Ricarica la lista degli ordini
                    } else {
                        alert(`❌ Errore nell'eliminazione: ${result.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nell'eliminazione ordine:", error);
                    alert("❌ Errore di rete durante l'eliminazione dell'ordine");
                }
            }

            // --- Gestione Import Automatico da Cartella ---

            const configureFolderForm = document.getElementById("configure-folder-form");
            const folderPathInput = document.getElementById("folder-path");
            const folderConfigStatus = document.getElementById("folder-config-status");
            const runAutoImportButton = document.getElementById("run-auto-import");
            const refreshConfigButton = document.getElementById("refresh-config");
            const autoImportResult = document.getElementById("auto-import-result");

            // Carica la configurazione attuale della cartella
            async function loadFolderConfig() {
                try {
                    const response = await fetch("/orders/auto-import/folder-config");
                    const config = await response.json();
                    
                    if (config.configured) {
                        folderConfigStatus.innerHTML = `
                            <div style="padding: 10px; background-color: ${config.folder_exists ? '#d4edda' : '#f8d7da'}; border-radius: 5px;">
                                <strong>Cartella configurata:</strong> ${config.folder_path}<br>
                                <strong>Stato:</strong> ${config.folder_exists ? '✅ Accessibile' : '❌ Non trovata'}<br>
                                <strong>Ultimo aggiornamento:</strong> ${config.last_updated ? new Date(config.last_updated).toLocaleString() : 'N/A'}
                            </div>
                        `;
                        folderPathInput.value = config.folder_path;
                        runAutoImportButton.disabled = !config.folder_exists;
                    } else {
                        folderConfigStatus.innerHTML = `
                            <div style="padding: 10px; background-color: #fff3cd; border-radius: 5px;">
                                <strong>⚠️ Nessuna cartella configurata</strong><br>
                                Inserisci il percorso della cartella per iniziare.
                            </div>
                        `;
                        runAutoImportButton.disabled = true;
                    }
                } catch (error) {
                    console.error("Errore nel caricamento configurazione:", error);
                    folderConfigStatus.innerHTML = `
                        <div style="padding: 10px; background-color: #f8d7da; border-radius: 5px;">
                            <strong>❌ Errore nel caricamento della configurazione</strong>
                        </div>
                    `;
                    runAutoImportButton.disabled = true;
                }
            }

            // Configura la cartella
            configureFolderForm.addEventListener("submit", async function(e) {
                e.preventDefault();
                
                const folderPath = folderPathInput.value.trim();
                if (!folderPath) {
                    alert("Inserisci il percorso della cartella");
                    return;
                }
                
                try {
                    const response = await fetch("/orders/auto-import/configure-folder", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            folder_path: folderPath
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(`✅ ${result.message}`);
                        loadFolderConfig(); // Ricarica la configurazione
                    } else {
                        alert(`❌ ${result.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nella configurazione:", error);
                    alert("❌ Errore di rete durante la configurazione");
                }
            });

            // Esegui import automatico
            runAutoImportButton.addEventListener("click", async function() {
                if (!confirm("Vuoi importare tutti i file dalla cartella configurata?")) {
                    return;
                }
                
                runAutoImportButton.disabled = true;
                runAutoImportButton.textContent = "Importazione in corso...";
                autoImportResult.innerHTML = `<p style="color: #007bff;">🔄 Processamento file in corso...</p>`;
                
                try {
                    const response = await fetch("/orders/auto-import/from-folder", {
                        method: "POST"
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        console.log("Import result completo:", result); // Debug completo
                        console.log("Details:", result.details); // Debug details
                        
                        // Mostra l'overlay con i risultati dettagliati
                        showImportRecapOverlay(result);
                        
                        // Mostra anche un breve riassunto nella sezione
                        autoImportResult.innerHTML = `
                            <div style="padding: 10px; background-color: #d4edda; border-radius: 5px; margin-top: 10px;">
                                <p style="margin: 0;"><strong>✅ ${result.message}</strong></p>
                                <small>Dettagli completi visualizzati nell'overlay</small>
                                <button onclick="showImportRecapOverlay(window.lastImportResult)" style="margin-top: 5px; background-color: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 3px;">Mostra Recap Dettagliato</button>
                            </div>
                        `;
                        
                        // Salva per permettere riapertura
                        window.lastImportResult = result;
                        
                        // Ricarica la lista degli ordini se sono stati creati ordini
                        if (result.files_processed > 0) {
                            fetchOrders();
                        }
                        
                    } else {
                        autoImportResult.innerHTML = `
                            <div style="padding: 15px; background-color: #f8d7da; border-radius: 5px; margin-top: 10px;">
                                <h4>❌ Errore nell'import automatico</h4>
                                <p>${result.detail}</p>
                            </div>
                        `;
                    }
                } catch (error) {
                    console.error("Errore nell'import automatico:", error);
                    autoImportResult.innerHTML = `
                        <div style="padding: 15px; background-color: #f8d7da; border-radius: 5px; margin-top: 10px;">
                            <h4>❌ Errore di rete</h4>
                            <p>Impossibile eseguire l'import automatico.</p>
                        </div>
                    `;
                } finally {
                    runAutoImportButton.disabled = false;
                    runAutoImportButton.textContent = "Importa Tutti i File";
                }
            });

            // Aggiorna configurazione
            refreshConfigButton.addEventListener("click", function() {
                loadFolderConfig();
                autoImportResult.innerHTML = "";
            });

            // --- Funzioni per gestire l'overlay import recap ---
            
            function showImportRecapOverlay(result) {
                console.log("showImportRecapOverlay called with:", result); // Debug
                
                const overlay = document.getElementById("import-recap-overlay");
                const body = document.getElementById("import-recap-body");
                
                if (!overlay || !body) {
                    console.error("Overlay elements not found!");
                    return;
                }
                
                // Calcolo totali da tutti i file processati
                let totalOrders = 0;
                let totalWarnings = 0;
                let totalErrors = 0;
                
                if (result.details && Array.isArray(result.details)) {
                    result.details.forEach(detail => {
                        console.log("Processing detail:", detail); // Debug
                        if (detail.orders_details && Array.isArray(detail.orders_details)) {
                            totalOrders += detail.orders_details.length;
                            detail.orders_details.forEach(order => {
                                if (order.warnings && Array.isArray(order.warnings)) {
                                    totalWarnings += order.warnings.length;
                                }
                            });
                        }
                        if (detail.status === "error") {
                            totalErrors++;
                        }
                    });
                }
                
                console.log(`Totals calculated: ${totalOrders} orders, ${totalWarnings} warnings, ${totalErrors} errors`); // Debug
                
                // Header con statistiche
                let content = `
                    <div style="background: linear-gradient(135deg, #007bff 0%, #0056b3 100%); color: white; padding: 25px; margin: -20px -20px 25px -20px; border-radius: 8px 8px 0 0;">
                        <h2 style="margin: 0 0 15px 0; font-size: 24px; font-weight: 300;">📊 Riepilogo Import Automatico</h2>
                        <div style="display: flex; justify-content: space-around; text-align: center;">
                            <div>
                                <div style="font-size: 28px; font-weight: bold;">${totalOrders}</div>
                                <div style="opacity: 0.9; font-size: 12px;">Ordini Creati</div>
                            </div>
                            <div>
                                <div style="font-size: 28px; font-weight: bold;">${totalWarnings}</div>
                                <div style="opacity: 0.9; font-size: 12px;">Avvisi Totali</div>
                            </div>
                            <div>
                                <div style="font-size: 28px; font-weight: bold;">${result.files_processed || 0}</div>
                                <div style="opacity: 0.9; font-size: 12px;">File Processati</div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Sezione principale per file e ordini
                if (result.details && Array.isArray(result.details) && result.details.length > 0) {
                    content += `<div style="margin-top: 20px;">`;
                    
                    result.details.forEach((detail, fileIndex) => {
                        console.log(`Processing file ${fileIndex}:`, detail); // Debug
                        
                        // Intestazione file
                        content += `
                            <div style="margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #007bff;">
                                <h4 style="margin: 0 0 10px 0; color: #007bff;">📁 File: ${detail.file}</h4>
                                <div style="font-size: 14px; color: #6c757d;">
                                    Stato: <strong style="color: ${detail.status === 'processed' ? '#28a745' : '#dc3545'};">
                                        ${detail.status === 'processed' ? 'Processato con successo' : 'Errore'}
                                    </strong>
                                </div>
                            </div>
                        `;
                        
                        if (detail.status === "processed" && detail.orders_details && Array.isArray(detail.orders_details)) {
                            // Mostra ordini del file
                            if (detail.orders_details.length > 0) {
                                content += `<div style="margin-left: 20px;">`;
                                
                                detail.orders_details.forEach((order, orderIndex) => {
                                    console.log(`Processing order ${orderIndex}:`, order); // Debug
                                    
                                    const hasWarnings = order.warnings && Array.isArray(order.warnings) && order.warnings.length > 0;
                                    
                                    content += `
                                        <div style="
                                            border: 1px solid ${hasWarnings ? '#ffc107' : '#28a745'}; 
                                            border-radius: 6px; 
                                            margin: 10px 0; 
                                            background: white;
                                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                        ">
                                            <div style="
                                                background: ${hasWarnings ? '#fff3cd' : '#d4edda'}; 
                                                padding: 12px; 
                                                border-bottom: 1px solid ${hasWarnings ? '#ffc107' : '#28a745'};
                                                display: flex;
                                                align-items: center;
                                                justify-content: space-between;
                                            ">
                                                <div style="display: flex; align-items: center;">
                                                    <span style="font-size: 18px; margin-right: 10px;">${hasWarnings ? '⚠️' : '✅'}</span>
                                                    <div>
                                                        <strong style="font-size: 16px;">Ordine ${order.order_number}</strong>
                                                        <div style="font-size: 12px; color: #666; margin-top: 2px;">
                                                            Cliente: ${order.customer_name} • ${order.products_count || 0} prodotti
                                                        </div>
                                                    </div>
                                                </div>
                                                <div style="
                                                    background: ${hasWarnings ? '#ffc107' : '#28a745'}; 
                                                    color: white; 
                                                    padding: 4px 10px; 
                                                    border-radius: 15px; 
                                                    font-size: 11px; 
                                                    font-weight: bold;
                                                ">
                                                    ${hasWarnings ? `${order.warnings.length} avvisi` : 'OK'}
                                                </div>
                                            </div>
                                    `;
                                    
                                    // Mostra avvisi se presenti
                                    if (hasWarnings) {
                                        content += `<div style="padding: 12px;">`;
                                        order.warnings.forEach((warning, wIndex) => {
                                            content += `
                                                <div style="
                                                    margin: ${wIndex > 0 ? '8px' : '0'} 0; 
                                                    padding: 8px; 
                                                    background: #fff3cd; 
                                                    border-left: 3px solid #ffc107; 
                                                    border-radius: 3px;
                                                    font-size: 13px;
                                                    color: #856404;
                                                ">
                                                    ${warning}
                                                </div>
                                            `;
                                        });
                                        content += `</div>`;
                                    }
                                    
                                    content += `</div>`;
                                });
                                
                                content += `</div>`;
                            } else {
                                content += `
                                    <div style="margin-left: 20px; padding: 10px; color: #6c757d; font-style: italic;">
                                        Nessun ordine creato da questo file
                                    </div>
                                `;
                            }
                        } else if (detail.status === "error") {
                            // Mostra errore del file
                            content += `
                                <div style="margin-left: 20px; padding: 12px; background: #f8d7da; border-left: 3px solid #dc3545; border-radius: 3px;">
                                    <strong style="color: #721c24;">Errore:</strong> ${detail.message}
                                </div>
                            `;
                        }
                    });
                    
                    content += `</div>`;
                } else {
                    content += `
                        <div style="text-align: center; padding: 40px; color: #6c757d;">
                            <p>Nessun file è stato processato in questo import.</p>
                        </div>
                    `;
                }
                
                console.log("Final content length:", content.length); // Debug
                body.innerHTML = content;
                overlay.style.display = "flex";
                
                // Aggiungi click-outside-to-close per overlay import recap
                overlay.onclick = function(event) {
                    if (event.target === overlay) {
                        closeImportRecapOverlay();
                    }
                };
            }
            
            // Funzione helper per calcolare il totale degli ordini creati
            function getTotalOrdersCreated(result) {
                if (!result.details) return 0;
                return result.details.reduce((total, detail) => {
                    return total + (detail.orders_created || 0);
                }, 0);
            }
            
            function closeImportRecapOverlay() {
                document.getElementById("import-recap-overlay").style.display = "none";
            }
            
            // Aggiungi funzioni globali per overlay
            window.closeImportRecapOverlay = closeImportRecapOverlay;
            window.showImportRecapOverlay = showImportRecapOverlay;
            
            // ============== PICKING RECAP SYSTEM ==============
            
            // Mostra il recap per picking da file
            window.showPickingRecap = function(data) {
                currentPickingRecapData = data;
                
                // Aggiorna le statistiche
                document.getElementById('picking-recap-total').textContent = data.stats.total || 0;
                document.getElementById('picking-recap-ok').textContent = data.stats.ok || 0;
                document.getElementById('picking-recap-warnings').textContent = data.stats.warnings || 0;
                document.getElementById('picking-recap-errors').textContent = data.stats.errors || 0;
                
                // Mostra/nasconde sezioni
                const errorsSection = document.getElementById('picking-recap-errors-section');
                const warningsSection = document.getElementById('picking-recap-warnings-section');
                const errorsList = document.getElementById('picking-recap-errors-list');
                const warningsList = document.getElementById('picking-recap-warnings-list');
                
                // Popola errori
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
                
                // Popola avvisi
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
                
                // Popola riepilogo ordini
                const ordersList = document.getElementById('picking-recap-orders-list');
                if (data.orders_summary) {
                    ordersList.innerHTML = Object.entries(data.orders_summary).map(([orderNumber, summary]) => 
                        `<div class="order-summary-card">
                            <div class="order-summary-header">
                                Ordine ${orderNumber} - ${summary.customer_name}
                            </div>
                            <div class="order-summary-details">
                                Operazioni: ${summary.total_operations} totali, ${summary.valid_operations} valide
                                ${summary.is_completed ? ' <span style="color: #dc3545;">(GIÀ COMPLETATO)</span>' : ''}
                            </div>
                        </div>`
                    ).join('');
                } else {
                    ordersList.innerHTML = '<div class="order-summary-card">Nessun ordine trovato</div>';
                }
                
                // Popola tabella operazioni
                const operationsTable = document.getElementById('picking-recap-operations-table');
                if (data.recap_items && data.recap_items.length > 0) {
                    operationsTable.innerHTML = data.recap_items.map(item => {
                        const statusIcon = item.status === 'ok' ? '✅' : 
                                          item.status === 'warning' ? '⚠️' : '❌';
                        
                        return `<tr class="status-${item.status}" data-line="${item.line}">
                            <td>${statusIcon} ${item.line}</td>
                            <td>
                                <input type="text" class="recap-order-input" value="${item.order_number}" 
                                       data-line="${item.line}" data-type="order_number" 
                                       style="width: 100%; border: 1px solid #ddd; background: white; padding: 2px;">
                            </td>
                            <td>
                                <input type="text" class="recap-location-input" value="${item.location}" 
                                       data-line="${item.line}" data-type="location" 
                                       ${item.status === 'ok' ? 'readonly' : ''} 
                                       style="width: 100%; border: none; background: transparent; ${item.status === 'ok' ? 'color: inherit;' : 'border: 1px solid #ddd; background: white;'}">
                            </td>
                            <td>
                                <input type="text" class="recap-sku-input" value="${item.sku}" 
                                       data-line="${item.line}" data-type="sku" list="product-skus"
                                       ${item.status === 'ok' ? 'readonly' : ''} 
                                       style="width: 100%; border: none; background: transparent; ${item.status === 'ok' ? 'color: inherit;' : 'border: 1px solid #ddd; background: white;'}">
                            </td>
                            <td>
                                <input type="number" class="recap-quantity-input" value="${item.quantity}" 
                                       data-line="${item.line}" data-type="quantity" min="1"
                                       ${item.status === 'ok' ? 'readonly' : ''} 
                                       style="width: 60px; border: none; background: transparent; ${item.status === 'ok' ? 'color: inherit;' : 'border: 1px solid #ddd; background: white;'}">
                            </td>
                            <td>${item.current_stock || 0}</td>
                            <td>${item.remaining_stock !== undefined ? item.remaining_stock : (item.current_stock || 0) - (item.quantity || 0)}</td>
                            <td>
                                <div class="recap-edit-controls">
                                    ${item.status !== 'ok' ? 
                                        `<button class="recap-edit-btn" onclick="fixPickingOperation(${item.line})">Correggi</button>
                                         <button class="recap-ignore-btn" onclick="removePickingOperation(${item.line})">Rimuovi</button>` : 
                                        '<span style="color: #28a745;">Valido</span>'
                                    }
                                </div>
                            </td>
                        </tr>`;
                    }).join('');
                } else {
                    operationsTable.innerHTML = '<tr><td colspan="9">Nessuna operazione da eseguire</td></tr>';
                }
                
                // Mostra l'overlay
                document.getElementById('picking-recap-overlay').style.display = 'block';
                
                // Setup del pulsante execute
                const executeBtn = document.getElementById('picking-recap-execute-btn');
                executeBtn.onclick = function() {
                    executePickingRecap();
                };
                
                // Setup degli input listeners per modifiche in tempo reale
                setupPickingInputListeners();
            };
            
            // Chiude il recap picking
            window.closePickingRecap = function() {
                document.getElementById('picking-recap-overlay').style.display = 'none';
                currentPickingRecapData = null;
            };
            
            // Corregge un'operazione di picking
            window.fixPickingOperation = function(line) {
                const orderInput = document.querySelector(`input[data-line="${line}"][data-type="order_number"]`);
                const locationInput = document.querySelector(`input[data-line="${line}"][data-type="location"]`);
                const skuInput = document.querySelector(`input[data-line="${line}"][data-type="sku"]`);
                const quantityInput = document.querySelector(`input[data-line="${line}"][data-type="quantity"]`);
                
                const newOrderNumber = orderInput ? orderInput.value.trim() : '';
                const newLocation = locationInput ? locationInput.value.trim().toUpperCase() : '';
                const newSku = skuInput ? skuInput.value.trim() : '';
                const newQuantity = parseInt(quantityInput ? quantityInput.value : 1) || 1;
                
                if (!newOrderNumber) {
                    alert('Inserisci un numero ordine valido');
                    return;
                }
                
                if (!newLocation) {
                    alert('Inserisci una ubicazione valida');
                    return;
                }
                
                if (!newSku) {
                    alert('Inserisci un SKU valido');
                    return;
                }
                
                // Trova l'item nel recap e aggiornalo
                const item = currentPickingRecapData.recap_items.find(item => item.line === line);
                if (item) {
                    item.order_number = newOrderNumber;
                    item.location = newLocation;
                    item.sku = newSku;
                    item.quantity = newQuantity;
                    item.status = 'ok'; // Assumiamo sia corretto dopo la modifica
                    
                    // Rimuovi da errori/warnings se presente
                    currentPickingRecapData.errors = currentPickingRecapData.errors.filter(e => e.line !== line);
                    currentPickingRecapData.warnings = currentPickingRecapData.warnings.filter(w => w.line !== line);
                    
                    // Aggiorna stats
                    currentPickingRecapData.stats.ok = currentPickingRecapData.recap_items.filter(i => i.status === 'ok').length;
                    currentPickingRecapData.stats.errors = currentPickingRecapData.errors.length;
                    currentPickingRecapData.stats.warnings = currentPickingRecapData.warnings.length;
                    
                    // Refresh del recap
                    showPickingRecap(currentPickingRecapData);
                }
            };
            
            // Rimuove un'operazione di picking
            window.removePickingOperation = function(line) {
                if (confirm('Sei sicuro di voler rimuovere questa operazione?')) {
                    // Rimuovi l'item dal recap
                    currentPickingRecapData.recap_items = currentPickingRecapData.recap_items.filter(item => item.line !== line);
                    currentPickingRecapData.errors = currentPickingRecapData.errors.filter(e => e.line !== line);
                    currentPickingRecapData.warnings = currentPickingRecapData.warnings.filter(w => w.line !== line);
                    
                    // Aggiorna stats
                    currentPickingRecapData.stats.total = currentPickingRecapData.recap_items.length;
                    currentPickingRecapData.stats.ok = currentPickingRecapData.recap_items.filter(i => i.status === 'ok').length;
                    currentPickingRecapData.stats.errors = currentPickingRecapData.errors.length;
                    currentPickingRecapData.stats.warnings = currentPickingRecapData.warnings.length;
                    
                    // Refresh del recap
                    showPickingRecap(currentPickingRecapData);
                }
            };
            
            // Esegue le operazioni di picking dopo validazione recap
            window.executePickingRecap = async function() {
                if (!currentPickingFile) {
                    alert('File non trovato. Riprova il caricamento.');
                    return;
                }
                
                const validOperations = currentPickingRecapData.recap_items.filter(item => item.status === 'ok');
                if (validOperations.length === 0) {
                    alert('Nessuna operazione valida da eseguire.');
                    return;
                }
                
                const confirmMessage = `Confermi l'esecuzione di ${validOperations.length} operazioni di prelievo?`;
                if (!confirm(confirmMessage)) {
                    return;
                }
                
                try {
                    const executeBtn = document.getElementById('picking-recap-execute-btn');
                    executeBtn.textContent = 'Esecuzione in corso...';
                    executeBtn.disabled = true;
                    
                    // Creiamo un file modificato con i dati corretti dal recap
                    const correctedData = [];
                    let currentOrder = null;
                    let currentLocation = null;
                    
                    for (const item of currentPickingRecapData.recap_items) {
                        if (item.status === 'ok') {
                            // Aggiungi numero ordine se è cambiato
                            if (currentOrder !== item.order_number) {
                                correctedData.push(item.order_number);
                                currentOrder = item.order_number;
                                currentLocation = null; // Reset location when order changes
                            }
                            
                            // Aggiungi ubicazione se è cambiata
                            if (currentLocation !== item.location) {
                                correctedData.push(item.location);
                                currentLocation = item.location;
                            }
                            
                            // Aggiungi prodotto con quantità
                            if (item.quantity > 1) {
                                correctedData.push(`${item.sku}_${item.quantity}`);
                            } else {
                                correctedData.push(item.sku);
                            }
                        }
                    }
                    
                    // Crea un nuovo file con i dati corretti
                    const correctedContent = correctedData.join('\n');
                    const correctedBlob = new Blob([correctedContent], { type: 'text/plain' });
                    const correctedFile = new File([correctedBlob], 'corrected_picking.txt', { type: 'text/plain' });
                    
                    const formData = new FormData();
                    formData.append('file', correctedFile);
                    formData.append('force', 'false'); // Non serve force con file corretto
                    
                    const response = await fetch('/orders/commit-picking-txt', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(`Prelievo completato: ${result.message}`);
                        closePickingRecap();
                        fetchOrders(); // Aggiorna la lista ordini
                    } else {
                        alert(`Errore: ${result.detail}`);
                    }
                } catch (error) {
                    console.error('Errore nell\'esecuzione:', error);
                    alert('Errore di rete durante l\'esecuzione del prelievo.');
                } finally {
                    const executeBtn = document.getElementById('picking-recap-execute-btn');
                    executeBtn.textContent = 'Esegui Prelievo';
                    executeBtn.disabled = false;
                }
            };

            // Chiamate iniziali
            loadProductSkus();
            fetchOrders();
            loadFolderConfig(); // Carica la configurazione della cartella
            setupOrdersSearchAndSort(); // Setup ricerca e ordinamento ordini
            setupArchivedSearchAndSort(); // Setup ricerca e ordinamento archiviati
        });

        // === FUNZIONI PICKING IN TEMPO REALE ===
        
        // Variabili globali per il picking in tempo reale
        let currentPickingSession = null;
        let currentPickingPosition = 0;
        let pickingOperations = [];
        
        function startRealTimePicking(orderData, validationData) {
            console.log("🚀 Starting real-time picking for:", orderData);
            
            // Prepara le operazioni di picking dal validationData
            pickingOperations = [];
            if (orderData.picking_operations) {
                orderData.picking_operations.forEach(op => {
                    if (op.status === 'valid' && op.quantity > 0) {
                        pickingOperations.push({
                            sku: op.sku,
                            location: op.location,
                            quantity: op.quantity,
                            remaining: op.quantity,
                            ean_codes: [] // Sarà popolato dal backend se necessario
                        });
                    }
                });
            }
            
            if (pickingOperations.length === 0) {
                alert("Nessuna operazione di picking valida trovata per questo ordine.");
                return;
            }
            
            currentPickingSession = {
                orderId: orderData.order_id,
                orderNumber: orderData.order_number || 'N/A',
                customerName: orderData.customer_name || 'N/A'
            };
            currentPickingPosition = 0;
            
            showRealTimePickingInterface();
        }
        
        function showRealTimePickingInterface() {
            const overlay = document.getElementById("picking-validation-overlay");
            const body = document.getElementById("picking-validation-body");
            const title = document.getElementById("picking-validation-title");
            const subtitle = document.getElementById("picking-validation-subtitle");
            
            if (!overlay || !body) {
                console.error("❌ Overlay elements not found for real-time picking!");
                return;
            }
            
            const currentOp = pickingOperations[currentPickingPosition];
            
            // Calcola il progresso reale basato sui pezzi prelevati (non solo posizioni)
            let totalRequired = 0;
            let totalPicked = 0;
            
            pickingOperations.forEach(op => {
                totalRequired += op.quantity;
                totalPicked += (op.quantity - op.remaining);
            });
            
            const realProgress = totalRequired > 0 ? Math.round((totalPicked / totalRequired) * 100) : 0;
            
            // Aggiorna titolo
            title.textContent = `📱 Picking in Tempo Reale - ${currentPickingSession.orderNumber}`;
            title.style.color = "white";
            title.style.fontWeight = "bold";
            
            subtitle.textContent = `${currentPickingSession.customerName} • Pos ${currentPickingPosition + 1}/${pickingOperations.length} • Pezzi: ${realProgress}%`;
            subtitle.style.color = "white";
            
            // Rileva se siamo su mobile per ottimizzare layout
            const isMobile = window.innerWidth <= 768;
            const containerPadding = isMobile ? "10px" : "15px";
            const progressHeight = isMobile ? "12px" : "15px";
            const progressMargin = isMobile ? "15px" : "20px";
            const infoPadding = isMobile ? "15px" : "25px";
            const infoMargin = isMobile ? "15px" : "20px";
            const scannerPadding = isMobile ? "20px" : "30px";
            const scannerMargin = isMobile ? "15px" : "20px";
            
            console.log(`📊 Progresso calcolato: ${realProgress}% (${totalPicked}/${totalRequired} pezzi)`);
            
            // Contenuto principale
            body.innerHTML = `
                <div style="text-align: center; padding: ${containerPadding};">
                    <!-- Barra di Progresso (basata sui pezzi reali) -->
                    <div style="background: #f1f1f1; border-radius: 10px; height: ${progressHeight}; margin-bottom: ${progressMargin};">
                        <div style="background: linear-gradient(135deg, #FF5913, #FF7A44); height: 100%; width: ${realProgress}%; border-radius: 10px; transition: width 0.5s;"></div>
                    </div>
                    
                    <!-- Informazioni Posizione Corrente - Ottimizzate per mobile -->
                    <div class="mobile-picking-info" style="
                        background: linear-gradient(135deg, #00516E, #0097E0); 
                        color: white; 
                        padding: ${infoPadding}; 
                        border-radius: 15px; 
                        margin-bottom: ${infoMargin};
                        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                    ">
                        <div style="font-size: ${isMobile ? '14px' : '18px'}; margin-bottom: ${isMobile ? '8px' : '10px'};">📍 Posizione:</div>
                        <div class="mobile-picking-location" style="font-size: ${isMobile ? '28px' : '36px'}; font-weight: bold; margin-bottom: ${isMobile ? '12px' : '15px'}; color: #00D4F5;">${currentOp.location}</div>
                        
                        <div style="font-size: ${isMobile ? '14px' : '16px'}; margin-bottom: ${isMobile ? '6px' : '8px'};">🏷️ Prodotto:</div>
                        <div class="mobile-picking-sku" style="font-size: ${isMobile ? '20px' : '28px'}; font-weight: bold; margin-bottom: ${isMobile ? '12px' : '15px'}; color: #F2F2F2;">${currentOp.sku}</div>
                        
                        <div style="font-size: ${isMobile ? '14px' : '16px'}; margin-bottom: ${isMobile ? '6px' : '8px'};">📦 Quantità:</div>
                        <div class="mobile-picking-quantity" style="font-size: ${isMobile ? '22px' : '28px'}; font-weight: bold; color: #00D4F5;">${currentOp.remaining} pz</div>
                    </div>
                    
                    <!-- Area Scanner -->
                    <div id="scanner-area" style="
                        background: #F2F2F2; 
                        border: 3px solid #0097E0; 
                        border-radius: 15px; 
                        padding: ${scannerPadding}; 
                        margin-bottom: ${scannerMargin};
                    ">
                        <div id="scanner-status" style="font-size: ${isMobile ? '18px' : '24px'}; font-weight: bold; color: #00516E; margin-bottom: ${isMobile ? '15px' : '20px'};">
                            ${currentPickingSession.waitingForLocation || true ? '📍 Spara il barcode della POSIZIONE' : '🏷️ Spara il barcode del PRODOTTO'}
                        </div>
                        
                        <input type="text" id="barcode-input" style="
                            font-size: ${isMobile ? '18px' : '24px'}; 
                            padding: ${isMobile ? '12px' : '15px'}; 
                            width: 100%; 
                            max-width: 400px; 
                            text-align: center; 
                            border: 2px solid #0097E0; 
                            border-radius: 8px; 
                            background: white;
                            outline: none;
                        " placeholder="Pronto per la scansione..." readonly />
                        
                        <div id="scanner-feedback" style="
                            margin-top: ${isMobile ? '10px' : '15px'}; 
                            font-size: ${isMobile ? '14px' : '18px'}; 
                            min-height: ${isMobile ? '20px' : '25px'}; 
                            font-weight: bold;
                        "></div>
                    </div>
                    
                    <!-- Area Scanner Fotocamera (nascosta inizialmente) -->
                    <div id="camera-scanner-area" style="
                        display: none;
                        background: #000; 
                        border: 3px solid #00D4F5; 
                        border-radius: 15px; 
                        padding: 15px; 
                        margin-bottom: 15px;
                        text-align: center;
                    ">
                        <div style="color: white; font-size: ${isMobile ? '16px' : '18px'}; margin-bottom: 10px;">
                            📷 Scanner Fotocamera Attivo
                        </div>
                        <video id="camera-preview" style="
                            width: 100%; 
                            max-width: 300px; 
                            height: 200px; 
                            border-radius: 8px;
                            object-fit: cover;
                        " autoplay playsinline></video>
                        <canvas id="camera-canvas" style="display: none;"></canvas>
                        <div style="color: #00D4F5; font-size: 14px; margin-top: 10px;">
                            Punta la fotocamera verso il barcode
                        </div>
                    </div>
                    
                    <!-- Pulsanti di Controllo -->
                    <div class="mobile-control-buttons" style="display: flex; gap: ${isMobile ? '10px' : '15px'}; justify-content: center; flex-wrap: wrap;">
                        <button id="camera-scanner-button" onclick="toggleCameraScanner()" style="
                            background: #00D4F5; 
                            color: white; 
                            border: none; 
                            padding: ${isMobile ? '10px 20px' : '12px 25px'}; 
                            border-radius: 8px; 
                            font-size: ${isMobile ? '14px' : '16px'}; 
                            cursor: pointer;
                        ">📷 Avvia Scanner</button>
                        
                        <button onclick="skipCurrentPosition()" style="
                            background: #6c757d; 
                            color: white; 
                            border: none; 
                            padding: ${isMobile ? '10px 20px' : '12px 25px'}; 
                            border-radius: 8px; 
                            font-size: ${isMobile ? '14px' : '16px'}; 
                            cursor: pointer;
                        ">⏭️ Salta Posizione</button>
                        
                        <button onclick="exitRealTimePicking()" style="
                            background: #dc3545; 
                            color: white; 
                            border: none; 
                            padding: ${isMobile ? '10px 20px' : '12px 25px'}; 
                            border-radius: 8px; 
                            font-size: ${isMobile ? '14px' : '16px'}; 
                            cursor: pointer;
                        ">❌ Esci</button>
                    </div>
                </div>
            `;
            
            // Inizializza lo stato del picking
            currentPickingSession.waitingForLocation = true;
            currentPickingSession.locationValidated = false;
            
            // Setup barcode input
            setupBarcodeInput();
            
            // Focus sull'input senza aprire la tastiera (readonly iniziale)
            setTimeout(() => {
                const barcodeInput = document.getElementById("barcode-input");
                if (barcodeInput) {
                    barcodeInput.focus();
                }
            }, 100);
        }
        
        function setupBarcodeInput() {
            const barcodeInput = document.getElementById("barcode-input");
            if (!barcodeInput) return;
            
            // Gestisce l'input della pistola scanner
            barcodeInput.addEventListener('keydown', function(e) {
                // Rimuovi readonly al primo input per permettere la digitazione
                if (this.readOnly) {
                    this.readOnly = false;
                }
                
                if (e.key === 'Enter') {
                    e.preventDefault();
                    processBarcodeInput(this.value.trim());
                    this.value = '';
                    // Rimetti readonly per evitare tastiera su mobile
                    setTimeout(() => {
                        this.readOnly = true;
                        setTimeout(() => {
                            this.readOnly = false;
                        }, 50);
                    }, 100);
                }
            });
            
            // Gestisce l'input diretto (per testing o inserimento manuale)
            barcodeInput.addEventListener('input', function(e) {
                if (this.readOnly) {
                    this.readOnly = false;
                }
            });
            
            // Intercetta il click per abilitare temporaneamente l'input
            barcodeInput.addEventListener('click', function(e) {
                if (this.readOnly) {
                    this.readOnly = false;
                    this.focus();
                    // Rimetti readonly dopo 5 secondi se non viene usato
                    setTimeout(() => {
                        if (!this.value) {
                            this.readOnly = true;
                        }
                    }, 5000);
                }
            });
            
            // Auto-focus quando perde il focus (per pistole barcode)
            barcodeInput.addEventListener('blur', function() {
                setTimeout(() => {
                    this.focus();
                    // Mantieni readonly per evitare tastiera
                    if (!this.value) {
                        this.readOnly = true;
                    }
                }, 100);
            });
        }
        
        async function processBarcodeInput(barcodeValue) {
            const feedback = document.getElementById("scanner-feedback");
            const status = document.getElementById("scanner-status");
            const currentOp = pickingOperations[currentPickingPosition];
            
            if (!barcodeValue) {
                showFeedback("❌ Barcode vuoto!", "#dc3545");
                return;
            }
            
            console.log("📱 Processing barcode:", barcodeValue, "Current state:", currentPickingSession.waitingForLocation ? "location" : "product");
            
            if (currentPickingSession.waitingForLocation) {
                // Validazione posizione
                if (barcodeValue.toUpperCase() === currentOp.location.toUpperCase()) {
                    showFeedback("✅ Posizione corretta!", "#28a745");
                    currentPickingSession.waitingForLocation = false;
                    currentPickingSession.locationValidated = true;
                    
                    // Aggiorna lo status
                    status.textContent = "🏷️ Ora spara il barcode del PRODOTTO";
                    status.style.color = "#00516E";
                    
                    // Cambia colore del bordo
                    const scannerArea = document.getElementById("scanner-area");
                    scannerArea.style.borderColor = "#28a745";
                } else {
                    showFeedback(`❌ Posizione errata! Richiesta: ${currentOp.location}`, "#dc3545");
                }
            } else if (currentPickingSession.locationValidated) {
                // Validazione prodotto e processing
                await processProductBarcode(barcodeValue, currentOp);
            }
        }
        
        async function processProductBarcode(barcodeValue, currentOp) {
            try {
                showFeedback("🔄 Validazione prodotto...", "#007bff");
                
                // Chiamata API per validare EAN e processare picking
                const response = await fetch('/orders/real-time-picking/scan-product', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        order_id: currentPickingSession.orderId,
                        location_name: currentOp.location,
                        scanned_code: barcodeValue,
                        expected_sku: currentOp.sku,
                        quantity: 1 // Per ora 1 pezzo alla volta
                    })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    // Successo - aggiorna quantità rimanente
                    const quantityPicked = result.quantity_picked || 1;
                    currentOp.remaining -= quantityPicked;
                    
                    showFeedback(`✅ ${result.message} (${quantityPicked} pz prelevato)`, "#28a745");
                    
                    // Aggiorna SEMPRE la quantità visualizzata e la barra di progresso
                    updateQuantityDisplay(currentOp.remaining);
                    
                    console.log(`📋 Operazione aggiornata: ${currentOp.sku} - Rimanenti: ${currentOp.remaining}/${currentOp.quantity}`);
                    
                    // Controlla se questa posizione è completata
                    if (currentOp.remaining <= 0) {
                        // Delay più lungo per evitare conflitti con il countdown del barcode
                        setTimeout(() => {
                            console.log("📍 Posizione completata, passaggio alla successiva...");
                            nextPickingPosition();
                        }, 5000); // 5 secondi invece di 1.5 per evitare sovrapposizioni
                    }
                } else {
                    showFeedback(`❌ ${result.message || 'Errore nella validazione prodotto'}`, "#dc3545");
                }
            } catch (error) {
                console.error("Errore nella validazione prodotto:", error);
                showFeedback("❌ Errore di rete nella validazione", "#dc3545");
            }
        }
        
        function showFeedback(message, color) {
            const feedback = document.getElementById("scanner-feedback");
            if (feedback) {
                feedback.textContent = message;
                feedback.style.color = color;
                
                // Clear feedback dopo qualche secondo se è un messaggio di errore
                if (color === "#dc3545") {
                    setTimeout(() => {
                        feedback.textContent = "";
                    }, 3000);
                }
            }
        }
        
        function updateQuantityDisplay(remaining) {
            const body = document.getElementById("picking-validation-body");
            // Aggiorna la quantità nel display mobile
            const quantityDisplay = body ? body.querySelector('.mobile-picking-quantity') : null;
            if (quantityDisplay) {
                quantityDisplay.textContent = `${remaining} pz`;
                console.log(`📦 Quantità aggiornata: ${remaining} pz`);
            }
            
            // Aggiorna anche la barra di progresso basata sui pezzi effettivamente prelevati
            updateProgressBar();
        }
        
        function updateProgressBar() {
            // Calcola il progresso totale basato sui pezzi prelevati
            let totalRequired = 0;
            let totalPicked = 0;
            
            pickingOperations.forEach(op => {
                totalRequired += op.quantity;
                totalPicked += (op.quantity - op.remaining);
            });
            
            const progressPercentage = totalRequired > 0 ? Math.round((totalPicked / totalRequired) * 100) : 0;
            
            // Aggiorna la barra visuale
            const body = document.getElementById("picking-validation-body");
            const progressBar = body ? body.querySelector('[style*="background: linear-gradient(135deg, #FF5913, #FF7A44)"]') : null;
            if (progressBar) {
                progressBar.style.width = `${progressPercentage}%`;
                console.log(`📊 Progresso aggiornato: ${progressPercentage}% (${totalPicked}/${totalRequired} pezzi)`);
            }
            
            // Aggiorna anche il sottotitolo con il progresso reale
            const subtitle = document.getElementById("picking-validation-subtitle");
            if (subtitle) {
                const positionProgress = Math.round(((currentPickingPosition + 1) / pickingOperations.length) * 100);
                subtitle.textContent = `${currentPickingSession.customerName} • Pos ${currentPickingPosition + 1}/${pickingOperations.length} • Pezzi: ${progressPercentage}%`;
            }
        }
        
        function nextPickingPosition() {
            currentPickingPosition++;
            
            // Pulisci cache barcode per la nuova posizione
            clearBarcodeCache();
            
            if (currentPickingPosition >= pickingOperations.length) {
                // Picking completato
                showPickingComplete();
            } else {
                // Prossima posizione
                console.log(`🔄 Passaggio alla posizione ${currentPickingPosition + 1}/${pickingOperations.length}`);
                showRealTimePickingInterface();
            }
        }
        
        function clearBarcodeCache() {
            console.log("🧹 Pulizia cache barcode...");
            lastBarcodeValue = null;
            lastBarcodeTime = 0;
            recentBarcodes = [];
            lastScanTime = 0;
            console.log("✅ Cache pulita per nuova posizione");
        }
        
        function showPickingComplete() {
            const body = document.getElementById("picking-validation-body");
            const title = document.getElementById("picking-validation-title");
            const subtitle = document.getElementById("picking-validation-subtitle");
            
            title.textContent = "🎉 Picking Completato!";
            subtitle.textContent = `Ordine ${currentPickingSession.orderNumber} completato con successo`;
            
            body.innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <div style="font-size: 72px; margin-bottom: 30px;">🎉</div>
                    <div style="font-size: 32px; font-weight: bold; color: #28a745; margin-bottom: 20px;">
                        Picking Completato!
                    </div>
                    <div style="font-size: 20px; color: #6c757d; margin-bottom: 30px;">
                        Ordine <strong>${currentPickingSession.orderNumber}</strong><br>
                        Cliente: <strong>${currentPickingSession.customerName}</strong><br>
                        Posizioni completate: <strong>${pickingOperations.length}</strong>
                    </div>
                    <button onclick="closePickingValidationOverlay(); fetchOrders();" style="
                        background: #28a745; 
                        color: white; 
                        border: none; 
                        padding: 15px 30px; 
                        border-radius: 8px; 
                        font-size: 18px; 
                        font-weight: bold; 
                        cursor: pointer;
                    ">✅ Torna agli Ordini</button>
                </div>
            `;
            
            // Reset sessione
            currentPickingSession = null;
            currentPickingPosition = 0;
            pickingOperations = [];
        }
        
        function skipCurrentPosition() {
            if (confirm("Vuoi saltare questa posizione? Il prodotto non verrà prelevato.")) {
                nextPickingPosition();
            }
        }
        
        async function exitRealTimePicking() {
            if (confirm("Vuoi uscire dal picking in tempo reale? I progressi andranno persi.")) {
                // Pulisci fotocamera se attiva
                await cleanupCameraOnExit();
                
                // Reset sessione
                currentPickingSession = null;
                currentPickingPosition = 0;
                pickingOperations = [];
                
                // Torna all'overlay precedente
                closePickingValidationOverlay();
            }
        }
        
        // === SCANNER FOTOCAMERA CON HTML5-QRCODE ===
        let html5QrCode = null;
        let isCameraActive = false;
        
        async function toggleCameraScanner() {
            const button = document.getElementById("camera-scanner-button");
            const cameraArea = document.getElementById("camera-scanner-area");
            const feedback = document.getElementById("scanner-feedback");
            
            if (!isCameraActive && !isZXingActive) {
                // Avvia scanner ZXing (ora predefinito)
                try {
                    feedback.textContent = "📷 Avvio scanner ZXing...";
                    feedback.style.color = "#ffc107";
                    
                    await startZXingScanner();
                    
                } catch (error) {
                    console.error("Errore avvio scanner:", error);
                    feedback.textContent = `❌ Errore: ${error.message || 'Impossibile avviare scanner'}`;
                    feedback.style.color = "#dc3545";
                    
                    // Reset UI
                    button.textContent = "📷 Avvia Scanner";
                    button.style.background = "#00D4F5";
                    cameraArea.style.display = "none";
                    isCameraActive = false;
                    isZXingActive = false;
                }
            } else {
                // Ferma qualsiasi scanner attivo
                if (isZXingActive) {
                    stopZXingScanner();
                    isZXingActive = false;
                }
                if (isCameraActive) {
                    await stopCameraScanner();
                    isCameraActive = false;
                }
                
                button.textContent = "📷 Avvia Scanner";
                button.style.background = "#00D4F5";
                cameraArea.style.display = "none";
                
                feedback.textContent = "📷 Scanner fermato";
                feedback.style.color = "#6c757d";
            }
        }
        
        // === SCANNER ZXING MIGLIORATO (NUOVO PREDEFINITO) ===
        async function startZXingScanner() {
            const feedback = document.getElementById("scanner-feedback");
            const cameraArea = document.getElementById("camera-scanner-area");
            const button = document.getElementById("camera-scanner-button");
            
            try {
                // Verifica ZXing disponibile
                if (typeof ZXing === 'undefined') {
                    throw new Error("Libreria ZXing non disponibile");
                }
                
                // Mostra area camera
                cameraArea.style.display = "block";
                
                // Ottieni video element
                const videoElement = document.getElementById('camera-preview');
                if (!videoElement) {
                    throw new Error("Elemento video non trovato");
                }
                
                // Ottieni stream fotocamera
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { 
                        facingMode: "environment",
                        width: { ideal: 640 },
                        height: { ideal: 480 }
                    }
                });
                
                // Collega stream a video
                videoElement.srcObject = stream;
                await videoElement.play();
                
                feedback.textContent = "📹 Inizializzazione scanner...";
                
                // Inizializza ZXing scanner
                const codeReader = new ZXing.BrowserMultiFormatReader();
                
                let lastScanTime = 0;
                const MIN_SCAN_INTERVAL = 3000; // 3 secondi per evitare scansioni multiple
                
                // Avvia decodifica continua
                zxingScanner = await codeReader.decodeFromVideoDevice(
                    null, // Auto-select camera
                    'camera-preview',
                    (result, err) => {
                        if (result) {
                            const now = Date.now();
                            const barcodeValue = result.text;
                            
                            // Controllo anti-cache avanzato
                            const isDuplicate = recentBarcodes.includes(barcodeValue);
                            const isTooFast = now - lastScanTime < MIN_SCAN_INTERVAL;
                            const isSameAsLast = lastBarcodeValue === barcodeValue && (now - lastBarcodeTime < 10000); // 10 secondi
                            
                            if (isTooFast || isSameAsLast) {
                                console.log(`🚫 Barcode ignorato: ${barcodeValue} (troppo veloce: ${isTooFast}, stesso: ${isSameAsLast})`);
                                return; // Ignora scansioni troppo frequenti o duplicate
                            }
                            
                            // Aggiorna cache anti-duplicati
                            lastScanTime = now;
                            lastBarcodeValue = barcodeValue;
                            lastBarcodeTime = now;
                            
                            // Mantieni solo gli ultimi 5 barcode in cache (sliding window)
                            recentBarcodes.push(barcodeValue);
                            if (recentBarcodes.length > 5) {
                                recentBarcodes.shift();
                            }
                            
                            // Barcode rilevato e validato!
                            console.log("🎯 ZXing - Barcode validato:", barcodeValue);
                            feedback.textContent = `✅ Barcode: ${barcodeValue}`;
                            feedback.style.color = "#28a745";
                            
                            // Processa il barcode SOLO se non c'è errore
                            try {
                                processBarcodeInput(result.text);
                                
                                // Vibrazione
                                if (navigator.vibrate) {
                                    navigator.vibrate([100, 50, 100]);
                                }
                                
                                // Mantieni messaggio successo per 2 secondi, poi countdown
                                setTimeout(() => {
                                    if (!isZXingActive) return;
                                    
                                    // Countdown visivo di 3 secondi
                                    let countdown = 3;
                                    const countdownInterval = setInterval(() => {
                                        if (isZXingActive) {
                                            feedback.textContent = `⏳ Attendi ${countdown}s prima del prossimo barcode`;
                                            feedback.style.color = "#ffc107";
                                            countdown--;
                                            
                                            if (countdown < 0) {
                                                clearInterval(countdownInterval);
                                                feedback.textContent = "📷 Scanner pronto - Inquadra prossimo barcode";
                                                feedback.style.color = "#17a2b8";
                                            }
                                        } else {
                                            clearInterval(countdownInterval);
                                        }
                                    }, 1000);
                                }, 2000); // Aspetta 2 secondi prima di iniziare countdown
                                
                            } catch (processError) {
                                // Errore nella processazione - gestione più robusta
                                console.warn("Errore processazione barcode:", processError);
                                feedback.textContent = `⚠️ Errore: ${processError.message || 'Problema processazione'}`;
                                feedback.style.color = "#dc3545";
                                
                                // Se l'errore è grave, ferma scanner
                                if (processError.toString().includes('fetch') || 
                                    processError.toString().includes('network') ||
                                    processError.toString().includes('TypeError')) {
                                    console.log("🚨 Errore grave rilevato, ferma scanner...");
                                    if (isZXingActive) {
                                        stopZXingScanner();
                                    }
                                } else {
                                    // Errore normale - countdown con reset soft
                                    let countdown = 3;
                                    const errorCountdownInterval = setInterval(() => {
                                        if (isZXingActive) {
                                            feedback.textContent = `🔄 Riprova tra ${countdown}s`;
                                            feedback.style.color = "#ffc107";
                                            countdown--;
                                            
                                            if (countdown < 0) {
                                                clearInterval(errorCountdownInterval);
                                                feedback.textContent = "📷 Scanner pronto - Riprova";
                                                feedback.style.color = "#17a2b8";
                                            }
                                        } else {
                                            clearInterval(errorCountdownInterval);
                                        }
                                    }, 1000);
                                }
                            }
                        }
                        
                        // Non loggare errori normali di scansione
                        if (err && !(err instanceof ZXing.NotFoundException)) {
                            console.warn("ZXing decode error:", err);
                        }
                    }
                );
                
                feedback.textContent = "✅ Scanner ZXing attivo! Inquadra barcode";
                feedback.style.color = "#28a745";
                button.textContent = "🛑 Ferma Scanner";
                button.style.background = "#dc3545";
                isZXingActive = true;
                
            } catch (error) {
                console.error("❌ Errore ZXing:", error);
                feedback.textContent = `❌ Errore: ${error.message}`;
                feedback.style.color = "#dc3545";
                
                // Reset UI ma NON chiudere
                button.textContent = "📷 Avvia Scanner";
                button.style.background = "#00D4F5";
                cameraArea.style.display = "none";
                isZXingActive = false;
                
                throw error; // Rilancia per gestione in toggleCameraScanner
            }
        }
        
        async function startCameraScanner() {
            // Verifica che html5-qrcode sia caricato
            if (typeof Html5Qrcode === 'undefined') {
                throw new Error("Libreria html5-qrcode non caricata. Ricarica la pagina.");
            }
            
            console.log("🔍 Avvio scanner con html5-qrcode...");
            
            // Inizializza il scanner
            html5QrCode = new Html5Qrcode("camera-preview");
            
            // Configurazione scanner ottimizzata
            const config = {
                fps: 10,
                qrbox: { width: 250, height: 250 },
                aspectRatio: 1.0
            };
            
            // Constraint per la fotocamera (priorità fotocamera posteriore)
            const cameraConfig = { facingMode: "environment" };
            
            try {
                await html5QrCode.start(
                    cameraConfig,
                    config,
                    onBarcodeSuccess,
                    onBarcodeError
                );
                
                console.log("✅ Scanner html5-qrcode avviato con successo!");
                
            } catch (error) {
                console.warn("⚠️ Fotocamera posteriore non disponibile, provo frontale...");
                
                // Fallback: prova fotocamera frontale
                try {
                    await html5QrCode.start(
                        { facingMode: "user" },
                        config,
                        onBarcodeSuccess,
                        onBarcodeError
                    );
                    
                    console.log("✅ Scanner avviato con fotocamera frontale!");
                    
                } catch (frontError) {
                    console.error("❌ Impossibile avviare scanner:", frontError);
                    
                    // Messaggio di errore dettagliato per debug
                    let errorMessage = "Impossibile avviare la fotocamera";
                    let errorDetails = `\nErrore tecnico: ${frontError.toString()}`;
                    
                    if (frontError.toString().includes('NotAllowedError')) {
                        errorMessage = "Permessi fotocamera negati. Consenti l'accesso alla fotocamera nelle impostazioni del browser.";
                    } else if (frontError.toString().includes('NotFoundError')) {
                        errorMessage = "Nessuna fotocamera trovata sul dispositivo.";
                    } else if (frontError.toString().includes('NotSupportedError')) {
                        errorMessage = "Fotocamera non supportata. Prova con Chrome, Firefox o Safari.";
                    } else if (frontError.toString().includes('OverconstrainedError')) {
                        errorMessage = "Configurazione fotocamera non supportata.";
                    } else if (frontError.toString().includes('SecurityError')) {
                        errorMessage = "Errore di sicurezza. Serve HTTPS per accedere alla fotocamera.";
                    }
                    
                    // Aggiungi dettagli tecnici in console
                    console.error("Dettagli errore completo:", {
                        name: frontError.name,
                        message: frontError.message,
                        toString: frontError.toString(),
                        stack: frontError.stack
                    });
                    
                    throw new Error(errorMessage + errorDetails);
                }
            }
        }
        
        // Callback per barcode rilevato con successo
        function onBarcodeSuccess(decodedText, decodedResult) {
            console.log("📷 Barcode rilevato dalla fotocamera:", decodedText);
            
            // Ferma lo scanner automaticamente dopo la rilevazione
            stopCameraScanner();
            
            // Processa il barcode rilevato
            processBarcodeInput(decodedText);
            
            // Fornisci feedback visivo
            showFeedback("📷 Barcode scansionato con successo!", "#28a745");
            
            // Vibrazione su mobile se supportata
            if (navigator.vibrate) {
                navigator.vibrate(200);
            }
        }
        
        // Callback per errori (normale durante la scansione)
        function onBarcodeError(error) {
            // Non loggare gli errori normali di scanning
            // Questi errori sono comuni quando non c'è un barcode nel frame
        }
        
        async function stopCameraScanner() {
            if (html5QrCode && html5QrCode.isScanning) {
                try {
                    await html5QrCode.stop();
                    console.log("✅ Scanner fermato con successo");
                } catch (error) {
                    console.error("⚠️ Errore durante stop scanner:", error);
                }
            }
            
            // Reset variabili
            html5QrCode = null;
        }
        
        // Pulizia quando si esce dal picking
        async function cleanupCameraOnExit() {
            if (isCameraActive) {
                await stopCameraScanner();
                isCameraActive = false;
                
                // Reset UI
                const button = document.getElementById("camera-scanner-button");
                const cameraArea = document.getElementById("camera-scanner-area");
                if (button) {
                    button.textContent = "📷 Avvia Scanner";
                    button.style.background = "#00D4F5";
                }
                if (cameraArea) {
                    cameraArea.style.display = "none";
                }
            }
        }
        
        
        
        
        
        
        
        // === SCANNER ZXING (ALTERNATIVO) ===
        let zxingScanner = null;
        let isZXingActive = false;
        let lastBarcodeValue = null;
        let lastBarcodeTime = 0;
        let recentBarcodes = []; // Cache degli ultimi barcode per evitare duplicati
        
        
        function stopZXingScanner() {
            console.log("🛑 Fermando ZXing scanner...");
            
            // Ferma ZXing scanner
            if (zxingScanner) {
                try {
                    zxingScanner.reset();
                    console.log("✅ ZXing scanner fermato");
                } catch (error) {
                    console.warn("Errore stop ZXing:", error);
                }
                zxingScanner = null;
            }
            
            // Ferma anche lo stream video
            const videoElement = document.getElementById('camera-preview');
            if (videoElement && videoElement.srcObject) {
                const tracks = videoElement.srcObject.getTracks();
                tracks.forEach(track => {
                    track.stop();
                    console.log(`🔹 Track fermato: ${track.kind}`);
                });
                videoElement.srcObject = null;
                console.log("✅ Stream video fermato");
            }
            
            // Reset flag
            isZXingActive = false;
        }
        
        
        // Funzione per aggiornare il contatore prodotti in uscita
        async function updateOutgoingStockCounter() {
            try {
                const response = await fetch('/analysis/outgoing-stock-total');
                if (response.ok) {
                    const data = await response.json();
                    document.getElementById('total-outgoing-stock').textContent = data.total;
                } else {
                    document.getElementById('total-outgoing-stock').textContent = 'Errore';
                }
            } catch (error) {
                console.error('Errore nel recupero giacenza in uscita:', error);
                document.getElementById('total-outgoing-stock').textContent = 'N/A';
            }
        }

        // === FUNZIONI GESTIONE EXCEL RECAP ===

        // Mostra il recap Excel
        function showExcelRecap(data) {
            currentExcelRecapData = data;
            
            // Aggiorna il titolo
            document.getElementById('excel-recap-title').textContent = 
                `📊 Recap Excel: ${data.file_name}`;
            
            // Aggiorna le statistiche
            const summary = data.summary;
            document.getElementById('excel-recap-total').textContent = summary.total_lines;
            document.getElementById('excel-recap-orders').textContent = summary.total_orders;
            document.getElementById('excel-recap-ok').textContent = summary.total_lines - summary.errors - summary.warnings;
            document.getElementById('excel-recap-warnings').textContent = summary.warnings;
            document.getElementById('excel-recap-errors').textContent = summary.errors;
            
            // Popola sezione errori se presenti
            const errorsSection = document.getElementById('excel-recap-errors-section');
            const errorsList = document.getElementById('excel-recap-errors-list');
            if (data.parse_errors && data.parse_errors.length > 0) {
                errorsSection.style.display = 'block';
                errorsList.innerHTML = data.parse_errors.map(error => 
                    `<div class="error-item">
                        <strong>Riga ${error.line}</strong>: ${error.message}
                        <br><small>Valore: ${error.value}</small>
                    </div>`
                ).join('');
            } else {
                errorsSection.style.display = 'none';
            }
            
            // Popola tabella operazioni
            const operationsTable = document.getElementById('excel-recap-operations-table');
            if (data.recap_items && data.recap_items.length > 0) {
                operationsTable.innerHTML = data.recap_items.map(item => {
                    const statusIcon = item.status === 'ok' ? '✅' : 
                                      item.status === 'warning' ? '⚠️' : '❌';
                    
                    const statusClass = item.status === 'ok' ? 'status-ok' : 
                                       item.status === 'warning' ? 'status-warning' : 'status-error';
                    
                    return `
                        <tr class="excel-recap-row ${statusClass}" data-line="${item.line}">
                            <td>${item.line}</td>
                            <td>
                                <input type="text" class="excel-recap-input" value="${item.order_number}" 
                                       data-line="${item.line}" data-field="order_number"
                                       style="width: 100%; border: 1px solid #ddd; padding: 2px;">
                            </td>
                            <td>
                                <input type="text" class="excel-recap-input" value="${item.customer_name}" 
                                       data-line="${item.line}" data-field="customer_name"
                                       style="width: 100%; border: 1px solid #ddd; padding: 2px;">
                            </td>
                            <td>
                                <input type="text" class="excel-recap-input" value="${item.sku}" 
                                       data-line="${item.line}" data-field="sku" list="product-skus"
                                       style="width: 100%; border: 1px solid #ddd; padding: 2px;">
                            </td>
                            <td title="${item.description}" style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">
                                ${item.description}
                            </td>
                            <td>
                                <input type="number" class="excel-recap-input" value="${item.quantity}" 
                                       data-line="${item.line}" data-field="quantity" min="1"
                                       style="width: 60px; border: 1px solid #ddd; padding: 2px;">
                            </td>
                            <td>
                                <span class="status-badge ${statusClass}">${statusIcon}</span>
                            </td>
                            <td>
                                <div class="recap-edit-controls">
                                    ${item.status !== 'ok' ? 
                                        `<button class="recap-edit-btn" onclick="validateExcelRow(${item.line})">Valida</button>
                                         <button class="recap-ignore-btn" onclick="removeExcelRow(${item.line})">Rimuovi</button>` : 
                                        '<span style="color: #28a745; font-size: 12px;">OK</span>'
                                    }
                                </div>
                            </td>
                        </tr>`;
                }).join('');
            } else {
                operationsTable.innerHTML = '<tr><td colspan="8">Nessuna operazione da eseguire</td></tr>';
            }
            
            // Mostra l'overlay
            document.getElementById('excel-recap-overlay').style.display = 'block';
            
            // Setup del pulsante execute
            const executeBtn = document.getElementById('excel-recap-execute-btn');
            executeBtn.onclick = function() {
                commitExcelRecap();
            };
            
            // Setup degli input listeners per validazione in tempo reale
            setupExcelInputListeners();
        }

        // Chiude il recap Excel
        window.closeExcelRecap = function() {
            document.getElementById('excel-recap-overlay').style.display = 'none';
            currentExcelRecapData = null;
            currentExcelFileName = null;
        };

        // Filtra gli item del recap Excel (mostra solo errori/avvisi)
        window.filterExcelRecapItems = function() {
            const showOnlyErrors = document.getElementById('excel-show-only-errors').checked;
            const rows = document.querySelectorAll('.excel-recap-row');
            
            rows.forEach(row => {
                if (showOnlyErrors) {
                    const hasError = row.classList.contains('status-error') || row.classList.contains('status-warning');
                    row.style.display = hasError ? '' : 'none';
                } else {
                    row.style.display = '';
                }
            });
        };

        // Valida una riga Excel dopo modifica
        window.validateExcelRow = function(line) {
            const row = document.querySelector(`tr[data-line="${line}"]`);
            if (!row) return;
            
            const inputs = row.querySelectorAll('.excel-recap-input');
            let isValid = true;
            let hasWarning = false;
            
            // Valida ogni input
            inputs.forEach(input => {
                const field = input.dataset.field;
                const value = input.value.trim();
                
                // Reset style
                input.style.borderColor = '#ddd';
                
                // Validazioni base
                if (!value) {
                    input.style.borderColor = 'red';
                    isValid = false;
                } else if (field === 'quantity' && (isNaN(value) || parseInt(value) <= 0)) {
                    input.style.borderColor = 'red';
                    isValid = false;
                } else if (field === 'sku') {
                    // Qui potresti aggiungere validazione SKU contro anagrafica
                    // Per ora solo controllo che non sia vuoto
                    if (!value) {
                        input.style.borderColor = 'red';
                        isValid = false;
                    }
                }
            });
            
            // Aggiorna lo stato della riga
            row.classList.remove('status-ok', 'status-warning', 'status-error');
            const statusBadge = row.querySelector('.status-badge');
            const editControls = row.querySelector('.recap-edit-controls');
            
            if (isValid && !hasWarning) {
                row.classList.add('status-ok');
                statusBadge.innerHTML = '✅';
                statusBadge.className = 'status-badge status-ok';
                editControls.innerHTML = '<span style="color: #28a745; font-size: 12px;">OK</span>';
            } else if (isValid && hasWarning) {
                row.classList.add('status-warning');
                statusBadge.innerHTML = '⚠️';
                statusBadge.className = 'status-badge status-warning';
            } else {
                row.classList.add('status-error');
                statusBadge.innerHTML = '❌';
                statusBadge.className = 'status-badge status-error';
            }
            
            // Aggiorna i contatori
            updateExcelRecapStats();
        };

        // Rimuove una riga Excel
        window.removeExcelRow = function(line) {
            const row = document.querySelector(`tr[data-line="${line}"]`);
            if (row && confirm('Rimuovere questa riga dal recap?')) {
                row.remove();
                updateExcelRecapStats();
            }
        };

        // Aggiorna le statistiche del recap Excel
        function updateExcelRecapStats() {
            const rows = document.querySelectorAll('.excel-recap-row');
            const stats = {
                total: rows.length,
                ok: document.querySelectorAll('.excel-recap-row.status-ok').length,
                warning: document.querySelectorAll('.excel-recap-row.status-warning').length,
                error: document.querySelectorAll('.excel-recap-row.status-error').length
            };
            
            document.getElementById('excel-recap-total').textContent = stats.total;
            document.getElementById('excel-recap-ok').textContent = stats.ok;
            document.getElementById('excel-recap-warnings').textContent = stats.warning;
            document.getElementById('excel-recap-errors').textContent = stats.error;
            
            // Calcola ordini unici
            const orderNumbers = new Set();
            rows.forEach(row => {
                const orderInput = row.querySelector('input[data-field="order_number"]');
                if (orderInput && orderInput.value.trim()) {
                    orderNumbers.add(orderInput.value.trim());
                }
            });
            document.getElementById('excel-recap-orders').textContent = orderNumbers.size;
        }

        // Setup listeners per input Excel
        function setupExcelInputListeners() {
            const inputs = document.querySelectorAll('.excel-recap-input');
            inputs.forEach(input => {
                input.addEventListener('input', function() {
                    const line = parseInt(this.dataset.line);
                    // Debounce validation
                    clearTimeout(this.validationTimeout);
                    this.validationTimeout = setTimeout(() => {
                        validateExcelRow(line);
                    }, 300);
                });
                
                input.addEventListener('blur', function() {
                    const line = parseInt(this.dataset.line);
                    validateExcelRow(line);
                });
            });
        }

        // Setup listeners per input Picking Recap
        function setupPickingInputListeners() {
            const inputs = document.querySelectorAll('.recap-order-input, .recap-location-input, .recap-sku-input, .recap-quantity-input');
            inputs.forEach(input => {
                input.addEventListener('input', function() {
                    const line = parseInt(this.dataset.line);
                    const type = this.dataset.type;
                    
                    // Aggiorna immediatamente il valore nell'oggetto dati
                    const item = currentPickingRecapData.recap_items.find(item => item.line === line);
                    if (item) {
                        if (type === 'order_number') {
                            item.order_number = this.value.trim();
                        } else if (type === 'location') {
                            item.location = this.value.trim().toUpperCase();
                        } else if (type === 'sku') {
                            item.sku = this.value.trim();
                        } else if (type === 'quantity') {
                            item.quantity = parseInt(this.value) || 1;
                        }
                    }
                });
                
                input.addEventListener('blur', function() {
                    const line = parseInt(this.dataset.line);
                    // Optional: trigger validation on blur if needed
                });
            });
        }

        // Commit del recap Excel (creazione ordini)
        async function commitExcelRecap() {
            if (!currentExcelRecapData) {
                alert('Nessun dato Excel da processare');
                return;
            }
            
            // Raccogli i dati aggiornati dal recap
            const rows = document.querySelectorAll('.excel-recap-row');
            const updatedRecapItems = [];
            
            rows.forEach(row => {
                const line = parseInt(row.dataset.line);
                const orderInput = row.querySelector('input[data-field="order_number"]');
                const customerInput = row.querySelector('input[data-field="customer_name"]');
                const skuInput = row.querySelector('input[data-field="sku"]');
                const quantityInput = row.querySelector('input[data-field="quantity"]');
                
                const status = row.classList.contains('status-ok') ? 'ok' : 
                              row.classList.contains('status-warning') ? 'warning' : 'error';
                
                updatedRecapItems.push({
                    line: line,
                    order_number: orderInput.value.trim(),
                    customer_name: customerInput.value.trim(),
                    sku: skuInput.value.trim(),
                    quantity: parseInt(quantityInput.value) || 0,
                    status: status
                });
            });
            
            const executeBtn = document.getElementById('excel-recap-execute-btn');
            const originalText = executeBtn.textContent;
            executeBtn.textContent = '⏳ Creazione in corso...';
            executeBtn.disabled = true;
            
            try {
                const response = await fetch('/orders/commit-excel-orders', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        recap_items: updatedRecapItems,
                        file_name: currentExcelRecapData ? currentExcelRecapData.file_name : 'excel_import.xlsx'
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    alert(`✅ ${result.message}`);
                    closeExcelRecap();
                    
                    // Ricarica la lista ordini
                    await fetchOrders();
                } else {
                    alert(`❌ Errore: ${result.message}`);
                }
            } catch (error) {
                console.error('Errore commit Excel:', error);
                alert('❌ Errore durante la creazione degli ordini');
            } finally {
                executeBtn.textContent = originalText;
                executeBtn.disabled = false;
            }
        }

        // === MODIFICA NOME CLIENTE ===
        
        // Funzione per aprire il popup di modifica cliente
        async function editCustomerName(orderNumber, currentCustomerName, orderId) {
            const overlay = document.createElement('div');
            overlay.id = 'edit-customer-overlay';
            overlay.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.7); z-index: 10000;
                display: flex; justify-content: center; align-items: center;
            `;
            
            // Controlla se esistono DDT collegati
            let ddtCheckbox = '';
            try {
                const ddtResponse = await fetch(`/ddt/check-order/${orderNumber}`);
                if (ddtResponse.ok) {
                    const ddtData = await ddtResponse.json();
                    if (ddtData.has_ddt) {
                        ddtCheckbox = `
                            <div style="margin: 15px 0; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                    <input type="checkbox" id="update-ddt-checkbox">
                                    <span>Aggiorna anche il DDT collegato (${ddtData.ddt_number})</span>
                                </label>
                            </div>
                        `;
                    }
                }
            } catch (error) {
                console.log('Nessun DDT collegato trovato');
            }
            
            overlay.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 8px; max-width: 500px; width: 90%;">
                    <h3 style="margin: 0 0 20px 0; color: #333;">Modifica Nome Cliente</h3>
                    <div style="margin-bottom: 15px;">
                        <strong>Ordine:</strong> ${orderNumber}
                    </div>
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: bold;">Nuovo Nome Cliente:</label>
                        <input type="text" id="new-customer-name" value="${currentCustomerName}" 
                               style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;">
                    </div>
                    ${ddtCheckbox}
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button onclick="closeEditCustomerOverlay()" 
                                style="padding: 10px 20px; border: 1px solid #ddd; background: #f8f9fa; border-radius: 4px; cursor: pointer;">
                            Annulla
                        </button>
                        <button onclick="saveCustomerName('${orderNumber}', ${orderId})" 
                                style="padding: 10px 20px; border: none; background: #007bff; color: white; border-radius: 4px; cursor: pointer;">
                            Salva
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(overlay);
            document.getElementById('new-customer-name').focus();
            document.getElementById('new-customer-name').select();
        }
        
        // Funzione per chiudere l'overlay di modifica cliente
        function closeEditCustomerOverlay() {
            const overlay = document.getElementById('edit-customer-overlay');
            if (overlay) {
                overlay.remove();
            }
        }
        
        // Funzione per salvare il nuovo nome cliente
        async function saveCustomerName(orderNumber, orderId) {
            const newCustomerName = document.getElementById('new-customer-name').value.trim();
            const updateDdt = document.getElementById('update-ddt-checkbox') ? 
                              document.getElementById('update-ddt-checkbox').checked : false;
            
            if (!newCustomerName) {
                alert('Il nome cliente non può essere vuoto');
                return;
            }
            
            try {
                const response = await fetch(`/orders/${orderNumber}/customer`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        customer_name: newCustomerName,
                        update_ddt: updateDdt
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    // Chiudi l'overlay immediatamente
                    closeEditCustomerOverlay();
                    
                    // Aggiorna la visualizzazione locale negli overlay
                    const displayElement = document.getElementById(`customer-display-${orderId}`);
                    if (displayElement) {
                        displayElement.textContent = newCustomerName;
                    }
                    
                    // Aggiorna anche l'elemento nell'overlay picking se presente
                    const displayPickingElement = document.getElementById(`customer-display-picking-${orderId}`);
                    if (displayPickingElement) {
                        displayPickingElement.textContent = newCustomerName;
                    }
                    
                    // Aggiorna anche la tabella principale se presente
                    if (window.originalOrdersData) {
                        const orderIndex = window.originalOrdersData.findIndex(o => o.id == orderId);
                        if (orderIndex !== -1) {
                            window.originalOrdersData[orderIndex].customer_name = newCustomerName;
                            // Aggiorna anche i dati filtrati se presenti
                            if (window.filteredOrdersData) {
                                const filteredIndex = window.filteredOrdersData.findIndex(o => o.id == orderId);
                                if (filteredIndex !== -1) {
                                    window.filteredOrdersData[filteredIndex].customer_name = newCustomerName;
                                }
                            }
                            // Ri-renderizza la tabella immediatamente
                            try {
                                renderOrdersTable();
                            } catch (renderError) {
                                console.warn('Errore nel render tabella:', renderError);
                            }
                        }
                    }
                    
                    // Mostra messaggio di successo
                    alert(`✅ Nome cliente aggiornato con successo${updateDdt ? ' (DDT incluso)' : ''}`);
                    
                    // Forza il refresh completo della pagina
                    window.location.reload();
                } else {
                    alert(`❌ Errore: ${result.message}`);
                }
            } catch (error) {
                console.error('Errore aggiornamento cliente:', error);
                alert('❌ Errore durante l\'aggiornamento del nome cliente');
            }
        }
        
        // Rendi le funzioni globali per i pulsanti inline
        window.skipCurrentPosition = skipCurrentPosition;
        window.exitRealTimePicking = exitRealTimePicking;
        window.toggleCameraScanner = toggleCameraScanner;
        window.updateOutgoingStockCounter = updateOutgoingStockCounter;
        window.editCustomerName = editCustomerName;
        window.closeEditCustomerOverlay = closeEditCustomerOverlay;
        window.saveCustomerName = saveCustomerName;
        
        // Aggiorna il contatore all'avvio
        updateOutgoingStockCounter();

        // Precompila date export al caricamento pagina
        initializeExportDates();

        // --- FUNZIONI EXPORT ORDINI ---

        function initializeExportDates() {
            const today = new Date();
            const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
            
            // Formatta le date in formato YYYY-MM-DD evitando problemi fuso orario
            const formatDate = (date) => {
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            };
            
            // Precompila i campi
            const fromDateField = document.getElementById('export-from-date');
            const toDateField = document.getElementById('export-to-date');
            
            if (fromDateField) {
                fromDateField.value = formatDate(firstDayOfMonth);
            }
            
            if (toDateField) {
                toDateField.value = formatDate(today);
            }
        }
        
        // Export Excel
        window.exportOrdersExcel = async function() {
            try {
                const fromDate = document.getElementById('export-from-date').value;
                const toDate = document.getElementById('export-to-date').value;
                
                // Costruisci URL con parametri date
                let url = '/orders/export-excel';
                const params = new URLSearchParams();
                if (fromDate) params.append('from_date', fromDate);
                if (toDate) params.append('to_date', toDate);
                if (params.toString()) url += '?' + params.toString();
                
                // Mostra loading
                const loadingMsg = document.createElement('div');
                loadingMsg.innerHTML = '⏳ Generazione file Excel in corso...';
                loadingMsg.style.cssText = 'position:fixed;top:20px;right:20px;background:#0066CC;color:white;padding:15px 20px;border-radius:8px;z-index:10000;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-weight:600;';
                document.body.appendChild(loadingMsg);
                
                const response = await fetch(url);
                
                // Rimuovi loading
                document.body.removeChild(loadingMsg);
                
                if (!response.ok) {
                    const error = await response.json();
                    alert(`Errore generazione Excel: ${error.detail || 'Errore sconosciuto'}`);
                    return;
                }
                
                // Download del file Excel
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                
                // Estrai nome file dalla response header se disponibile
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'export_ordini.xlsx';
                if (contentDisposition) {
                    const matches = /filename="?([^"]+)"?/.exec(contentDisposition);
                    if (matches && matches[1]) {
                        filename = matches[1];
                    }
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(downloadUrl);
                document.body.removeChild(a);
                
                // Feedback successo
                const successMsg = document.createElement('div');
                successMsg.innerHTML = '✅ File Excel scaricato con successo!';
                successMsg.style.cssText = 'position:fixed;top:20px;right:20px;background:#28a745;color:white;padding:12px 18px;border-radius:6px;z-index:10000;font-weight:500;';
                document.body.appendChild(successMsg);
                setTimeout(() => document.body.removeChild(successMsg), 3000);
                
            } catch (error) {
                console.error('Errore export Excel ordini:', error);
                alert('Errore di rete durante la generazione del file Excel.');
            }
        };
        
        // Export PDF  
        window.exportOrdersPdf = async function() {
            try {
                const fromDate = document.getElementById('export-from-date').value;
                const toDate = document.getElementById('export-to-date').value;
                
                // Costruisci URL con parametri date
                let url = '/orders/export-pdf';
                const params = new URLSearchParams();
                if (fromDate) params.append('from_date', fromDate);
                if (toDate) params.append('to_date', toDate);
                if (params.toString()) url += '?' + params.toString();
                
                // Mostra loading
                const loadingMsg = document.createElement('div');
                loadingMsg.innerHTML = '⏳ Generazione file PDF in corso...';
                loadingMsg.style.cssText = 'position:fixed;top:20px;right:20px;background:#dc3545;color:white;padding:15px 20px;border-radius:8px;z-index:10000;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-weight:600;';
                document.body.appendChild(loadingMsg);
                
                const response = await fetch(url);
                
                // Rimuovi loading
                document.body.removeChild(loadingMsg);
                
                if (!response.ok) {
                    const error = await response.json();
                    alert(`Errore generazione PDF: ${error.detail || 'Errore sconosciuto'}`);
                    return;
                }
                
                // Download del file PDF
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                
                // Estrai nome file dalla response header se disponibile
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'export_ordini.pdf';
                if (contentDisposition) {
                    const matches = /filename="?([^"]+)"?/.exec(contentDisposition);
                    if (matches && matches[1]) {
                        filename = matches[1];
                    }
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(downloadUrl);
                document.body.removeChild(a);
                
                // Feedback successo
                const successMsg = document.createElement('div');
                successMsg.innerHTML = '✅ File PDF scaricato con successo!';
                successMsg.style.cssText = 'position:fixed;top:20px;right:20px;background:#28a745;color:white;padding:12px 18px;border-radius:6px;z-index:10000;font-weight:500;';
                document.body.appendChild(successMsg);
                setTimeout(() => document.body.removeChild(successMsg), 3000);
                
            } catch (error) {
                console.error('Errore export PDF ordini:', error);
                alert('Errore di rete durante la generazione del file PDF.');
            }
        };
