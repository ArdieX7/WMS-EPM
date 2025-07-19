        document.addEventListener("DOMContentLoaded", function() {
            const createOrderForm = document.getElementById("create-order-form");
            const orderLinesContainer = document.getElementById("order-lines-container");
            const addLineButton = document.getElementById("add-line-button");
            const ordersTableBody = document.querySelector("#orders-table tbody");
            const productSkusDatalist = document.getElementById("product-skus");
            const orderDetailsContainer = document.getElementById("order-details-container");

            const importOrdersForm = document.getElementById("import-orders-form");
            const importOrdersResult = document.getElementById("import-orders-result");

            let lineCounter = 0;
            let currentOrderData = null; // Per memorizzare i dati dell'ordine corrente

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
                        <label for="line-product-sku-${lineCounter}">SKU Prodotto:</label>
                        <input type="text" id="line-product-sku-${lineCounter}" list="product-skus" required>
                        <label for="line-quantity-${lineCounter}">Quantità Richiesta:</label>
                        <input type="number" id="line-quantity-${lineCounter}" required><br><br>
                    </div>
                `;
                orderLinesContainer.insertAdjacentHTML('beforeend', newLineHtml);
            });

            // Funzione per caricare e visualizzare gli ordini
            async function fetchOrders() {
                try {
                    const response = await fetch("/orders/");
                    const orders = await response.json();
                    ordersTableBody.innerHTML = '';

                    for (const order of orders) {
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
                        
                        const progressColor = order.is_cancelled ? '#6c757d' :
                                            order.is_completed ? '#28a745' :
                                            pickingProgress === 0 ? '#dc3545' :
                                            pickingProgress === 100 ? '#17a2b8' :
                                            '#ffc107';
                        
                        // Genera pulsanti azioni basati sullo stato
                        let actionButtons = '';
                        
                        if (order.is_cancelled) {
                            // Ordine annullato: solo visualizzazione dettagli
                            actionButtons = `
                                <button class="view-order-button" data-order-id="${order.id}" data-completed="${order.is_completed}">
                                    Vedi Dettagli
                                </button>
                                <span style="color: #dc3545; font-weight: bold; margin-left: 10px;">Nessuna azione disponibile</span>
                            `;
                        } else {
                            actionButtons = `
                                <button class="view-order-button" data-order-id="${order.id}" data-completed="${order.is_completed}">
                                    ${order.is_completed ? 'Vedi Dettagli' : 'Dettagli/Picking'}
                                </button>
                            `;

                            if (order.is_completed) {
                                // Ordine completato: può essere archiviato
                                actionButtons += `
                                    <button class="archive-order-button" data-order-id="${order.id}" style="background-color: #17a2b8; margin-left: 5px;">
                                        Archivia
                                    </button>
                                `;
                            } else {
                                // Ordine in corso: può essere evaso o annullato
                                actionButtons += `
                                    <button class="fulfill-order-button" data-order-id="${order.id}">
                                        Evadi Ordine
                                    </button>
                                    <button class="cancel-order-button" data-order-id="${order.id}" style="background-color: #dc3545; margin-left: 5px;">
                                        Annulla
                                    </button>
                                `;
                            }
                        }
                        
                        row.innerHTML = `
                            <td>${order.id}</td>
                            <td>${order.order_number}</td>
                            <td>${order.customer_name}</td>
                            <td>${new Date(order.order_date).toLocaleDateString()}</td>
                            <td>${orderStatus}</td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <div style="background-color: #f1f1f1; border-radius: 10px; height: 20px; flex: 1; position: relative;">
                                        <div style="background-color: ${progressColor}; height: 100%; width: ${pickingProgress}%; border-radius: 10px; transition: width 0.3s;"></div>
                                        <span style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 12px; font-weight: bold; color: #333;">${pickingProgress}%</span>
                                    </div>
                                    <small style="color: ${progressColor}; font-weight: bold; min-width: 120px;">${pickingStatus}</small>
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

                } catch (error) {
                    console.error("Errore nel caricamento degli ordini:", error);
                    orderDetailsContainer.innerHTML = `<p class="error-message">Errore nel caricamento degli ordini.</p>`;
                }
            }

            // Funzione per mostrare i dettagli dell'ordine e i suggerimenti di picking
            async function showOrderDetails(orderId, isCompleted) {
                try {
                    // 1. Recupera sempre i dati base dell'ordine
                    const orderResponse = await fetch(`/orders/${orderId}`);
                    if (!orderResponse.ok) {
                        throw new Error("Errore nel recupero dei dati base dell'ordine.");
                    }
                    const order = await orderResponse.json();
                    currentOrderData = order;

                    // 2. Recupera i suggerimenti di picking SOLO se l'ordine non è completato
                    let suggestions = {};
                    if (!isCompleted) {
                        const suggestionsResponse = await fetch(`/orders/${orderId}/picking-suggestions`);
                        if (!suggestionsResponse.ok) {
                            // Se fallisce il fetch dei suggerimenti, lo segnaliamo ma andiamo avanti a mostrare i dettagli base
                            console.error("Errore nel recupero dei suggerimenti di picking.");
                            suggestions = { error: true };
                        } else {
                            suggestions = await suggestionsResponse.json();
                        }
                    }

                    // 3. Costruisci l'HTML
                    let detailsHtml = `
                        <div class="order-details">
                            <button id="close-details-button" style="float: right;">Chiudi</button>
                            ${!isCompleted ? `<button id="print-picking-list-button" style="float: right; margin-right: 10px;" data-order-id="${order.id}">Stampa Picking List</button>` : ''}
                            <h4>Dettagli Ordine #${order.order_number} (${order.customer_name})</h4>
                            <p>Stato: ${order.is_completed ? 'Completato' : 'In Corso'}</p>
                            <h5>Righe Ordine:</h5>
                            <ul>
                    `;
                    order.lines.forEach(line => {
                        detailsHtml += `<li>${line.product_sku}: Richiesto ${line.requested_quantity}, Prelevato ${line.picked_quantity}</li>`;
                    });
                    detailsHtml += `</ul>`;

                    // 4. Mostra la sezione di picking solo se l'ordine non è completato
                    if (!isCompleted) {
                        detailsHtml += `<h5>Suggerimenti Picking:</h5>`;
                        if (suggestions.error) {
                            detailsHtml += `<p class="error-message">Impossibile caricare i suggerimenti di picking.</p>`;
                        } else if (Object.keys(suggestions).length === 0) {
                            detailsHtml += `<p>Nessun suggerimento di picking disponibile (ordine già completamente prelevato o senza righe aperte).</p>`;
                        } else {
                            detailsHtml += `<div class="picking-suggestions">`;
                            for (const sku in suggestions) {
                                const suggestion = suggestions[sku];
                                detailsHtml += `<p><strong>${sku}</strong> (Richiesto: ${suggestion.needed}):</p><ul>`;
                                if (suggestion.status === "partial_stock") {
                                    detailsHtml += `<li class="error-message">ATTENZIONE: Stock parziale disponibile!</li>`;
                                }
                                suggestion.available_in_locations.forEach(item => {
                                    detailsHtml += `<li>Da ${item.location_name}: ${item.quantity}</li>`;
                                });
                                detailsHtml += `</ul>`;
                            }
                            detailsHtml += `</div>`;

                            detailsHtml += `
                                <h4>Conferma Prelievo</h4>
                                <form id="confirm-pick-form" data-order-id="${order.id}">
                                    <p>Inserisci i dettagli dei prodotti effettivamente prelevati:</p>
                                    <div id="picked-items-container"></div>
                                    <button type="button" id="add-picked-item-button">Aggiungi Articolo Prelevato</button><br><br>
                                    <button type="submit">Conferma Prelievo</button>
                                </form>
                            `;
                        }
                    } else {
                         detailsHtml += `<p><strong>Questo ordine è completato. Non sono possibili ulteriori azioni di picking.</strong></p>`;
                    }
                    detailsHtml += `</div>`;

                    // 5. Inserisci l'HTML nel contenitore e aggiungi i listener
                    orderDetailsContainer.innerHTML = detailsHtml;
                    orderDetailsContainer.style.display = 'block';

                    document.getElementById("close-details-button").addEventListener("click", () => {
                        orderDetailsContainer.style.display = 'none';
                        currentOrderData = null;
                    });

                    if (!isCompleted) {
                        const addButton = document.getElementById("add-picked-item-button");
                        if (addButton) addButton.addEventListener("click", addPickedItemField);
                        
                        const pickForm = document.getElementById("confirm-pick-form");
                        if (pickForm) pickForm.addEventListener("submit", async (event) => {
                            event.preventDefault();
                            await confirmPicking(order.id);
                        });
                        
                        const printButton = document.getElementById("print-picking-list-button");
                        if (printButton) printButton.addEventListener("click", () => {
                            const orderId = printButton.dataset.orderId;
                            window.open(`/orders/${orderId}/picking-list-print`, '_blank');
                        });
                    }

                } catch (error) {
                    console.error("Errore in showOrderDetails:", error);
                    orderDetailsContainer.innerHTML = `<p class="error-message">${error.message}</p>`;
                    orderDetailsContainer.style.display = 'block';
                }
            }

            // Funzione per aggiungere un campo per un articolo prelevato
            function addPickedItemField() {
                const container = document.getElementById("picked-items-container");
                const fieldId = `picked-item-${Date.now()}`;
                const fieldHtml = `
                    <div class="picked-item-entry">
                        <label for="${fieldId}-sku">SKU:</label>
                        <input type="text" name="sku" list="product-skus" required>
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
                        orderDetailsContainer.style.display = 'none';
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
                    const response = await fetch(`/orders/${orderId}/fulfill`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ order_id: parseInt(orderId) }),
                    });

                    if (response.ok) {
                        alert("Ordine evaso con successo!");
                        fetchOrders();
                    } else {
                        const error = await response.json();
                        alert(`Errore nell'evasione ordine: ${error.detail}`);
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
                                <label for="line-product-sku-0">SKU Prodotto:</label>
                                <input type="text" id="line-product-sku-0" list="product-skus" required>
                                <label for="line-quantity-0">Quantità Richiesta:</label>
                                <input type="number" id="line-quantity-0" required><br><br>
                            </div>
                        `;
                        lineCounter = 0;
                        alert("Ordine creato con successo!");
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
                    alert("Seleziona un file.");
                    return;
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
                        importOrdersResult.style.color = 'green';
                        importOrdersResult.textContent = result.message;
                        fetchOrders(); // Ricarica la lista degli ordini
                    } else {
                        importOrdersResult.style.color = 'red';
                        importOrdersResult.textContent = `Errore: ${result.detail}`;
                    }
                } catch (error) {
                    console.error("Errore nell'importazione degli ordini:", error);
                    importOrdersResult.style.color = 'red';
                    importOrdersResult.textContent = "Errore di rete durante l'importazione.";
                }
            });

            // Gestione prelievo da file TXT (nuovo flusso con validazione)
            const importPickingForm = document.getElementById("import-picking-form");
            const importPickingResult = document.getElementById("import-picking-result");
            let currentPickingFile = null;

            importPickingForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const fileInput = document.getElementById("picking-file");
                if (fileInput.files.length === 0) {
                    alert("Seleziona un file.");
                    return;
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
                        importPickingResult.style.color = 'green';
                        importPickingResult.textContent = "Validazione completata. Controlla il riepilogo.";
                        showValidationModal(result);
                    } else {
                        importPickingResult.style.color = 'red';
                        importPickingResult.textContent = `Errore: ${result.detail}`;
                    }
                } catch (error) {
                    console.error("Errore nella validazione:", error);
                    importPickingResult.style.color = 'red';
                    importPickingResult.textContent = "Errore di rete durante la validazione.";
                }
            });

            // Funzioni per gestire il modale di validazione
            window.showValidationModal = function(validationData) {
                const modal = document.getElementById("picking-validation-modal");
                const modalBody = document.getElementById("validation-modal-body");
                
                let html = '<div class="summary-stats">';
                html += `<div class="stat-item"><span class="stat-number" style="color: #28a745;">${validationData.stats.valid_count}</span>Operazioni Valide</div>`;
                html += `<div class="stat-item"><span class="stat-number" style="color: #ffc107;">${validationData.stats.warning_count}</span>Avvertimenti</div>`;
                html += `<div class="stat-item"><span class="stat-number" style="color: #dc3545;">${validationData.stats.error_count}</span>Errori</div>`;
                html += `<div class="stat-item"><span class="stat-number">${validationData.stats.orders_count}</span>Ordini Coinvolti</div>`;
                html += '</div>';

                // Raggruppa per ordine
                for (const orderNumber in validationData.order_summaries) {
                    const orderSummary = validationData.order_summaries[orderNumber];
                    html += `<div class="order-summary">`;
                    html += `<div class="order-header">`;
                    html += `Ordine: ${orderNumber} - ${orderSummary.customer_name}`;
                    if (!orderSummary.exists) {
                        html += ` <span class="status-error">(NON TROVATO)</span>`;
                    } else if (orderSummary.is_completed) {
                        html += ` <span class="status-error">(COMPLETATO)</span>`;
                    }
                    html += `</div>`;
                    
                    html += `<div class="order-content">`;
                    
                    // Mostra stato righe ordine
                    if (orderSummary.exists && Object.keys(orderSummary.lines).length > 0) {
                        html += `<h4>Stato Righe Ordine:</h4>`;
                        html += `<table style="margin-bottom: 15px;"><thead><tr><th>SKU</th><th>Richiesto</th><th>Prelevato</th><th>Rimanente</th></tr></thead><tbody>`;
                        for (const sku in orderSummary.lines) {
                            const line = orderSummary.lines[sku];
                            html += `<tr><td>${sku}</td><td>${line.requested}</td><td>${line.picked}</td><td>${line.remaining}</td></tr>`;
                        }
                        html += `</tbody></table>`;
                    }
                    
                    // Mostra operazioni di picking
                    html += `<h4>Operazioni di Picking:</h4>`;
                    orderSummary.picking_operations.forEach(op => {
                        html += `<div class="operation-item ${op.status}">`;
                        html += `<strong>${op.sku}</strong> da ${op.location} (Qty: ${op.quantity}) `;
                        html += `<span class="status-${op.status}">${op.status.toUpperCase()}</span>`;
                        if (op.issues.length > 0) {
                            html += `<br><small>${op.issues.join('; ')}</small>`;
                        }
                        html += `</div>`;
                    });
                    
                    html += `</div></div>`;
                }

                modalBody.innerHTML = html;
                modal.style.display = "block";
                
                // Abilita/disabilita bottoni in base ai risultati
                const commitAllButton = document.getElementById("commit-all-button");
                const commitForceButton = document.getElementById("commit-force-button");
                
                commitAllButton.disabled = validationData.stats.valid_count === 0;
                commitForceButton.disabled = validationData.stats.total_operations === validationData.stats.error_count;
            }

            window.closeValidationModal = function() {
                document.getElementById("picking-validation-modal").style.display = "none";
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

                    closeValidationModal();

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
                    closeValidationModal();
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
                    if (confirm("Sei sicuro di voler annullare questo ordine? I prodotti in uscita verranno rilasciati.")) {
                        await cancelOrder(orderId);
                    }
                }
            });

            // Gestione apertura sezione ordini archiviati
            document.getElementById("archived-orders-section").addEventListener("toggle", function(e) {
                if (e.target.open) {
                    fetchArchivedOrders();
                }
            });

            // Funzione per archiviare un ordine
            async function archiveOrder(orderId) {
                try {
                    const response = await fetch(`/orders/${orderId}/archive`, {
                        method: "POST"
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
                        if (result.released_items && result.released_items.length > 0) {
                            message += "\n\nProdotti rilasciati dalla giacenza in uscita:\n";
                            result.released_items.forEach(item => {
                                message += `- ${item.product_sku}: ${item.quantity} pz\n`;
                            });
                            message += "\nRicordati di riposizionare questi prodotti nel magazzino!";
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
                    const archivedOrdersTableBody = document.querySelector("#archived-orders-table tbody");
                    
                    archivedOrdersTableBody.innerHTML = '';

                    if (data.orders && data.orders.length > 0) {
                        for (const order of data.orders) {
                            const row = document.createElement("tr");
                            row.innerHTML = `
                                <td>${order.id}</td>
                                <td>${order.order_number}</td>
                                <td>${order.customer_name}</td>
                                <td>${new Date(order.order_date).toLocaleDateString()}</td>
                                <td>${order.archived_date ? new Date(order.archived_date).toLocaleDateString() : 'N/A'}</td>
                                <td>${order.is_cancelled ? 'Annullato' : 'Completato'}</td>
                                <td>
                                    <button class="view-archived-order-button" data-order-id="${order.id}">
                                        Vedi Dettagli
                                    </button>
                                    <button class="unarchive-order-button" data-order-id="${order.id}" style="background-color: #ffc107; margin-left: 5px;">
                                        Ripristina
                                    </button>
                                </td>
                            `;
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
                                // Trova l'ordine nei dati e visualizza i dettagli
                                const order = data.orders.find(o => o.id == orderId);
                                if (order) {
                                    showOrderDetails(order);
                                }
                            });
                        });
                    } else {
                        archivedOrdersTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #666;">Nessun ordine archiviato</td></tr>';
                    }
                } catch (error) {
                    console.error("Errore nel caricamento degli ordini archiviati:", error);
                    const archivedOrdersTableBody = document.querySelector("#archived-orders-table tbody");
                    archivedOrdersTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: red;">Errore nel caricamento</td></tr>';
                }
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

            // Chiamate iniziali
            loadProductSkus();
            fetchOrders();
        });