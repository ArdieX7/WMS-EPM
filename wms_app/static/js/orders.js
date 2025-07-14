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
                        row.innerHTML = `
                            <td>${order.id}</td>
                            <td>${order.order_number}</td>
                            <td>${order.customer_name}</td>
                            <td>${new Date(order.order_date).toLocaleDateString()}</td>
                            <td>${order.is_completed ? 'Completato' : 'In Corso'}</td>
                            <td>
                                <button class="view-order-button" data-order-id="${order.id}" data-completed="${order.is_completed}">
                                    ${order.is_completed ? 'Vedi Dettagli' : 'Dettagli/Picking'}
                                </button>
                                ${!order.is_completed ? `<button class="fulfill-order-button" data-order-id="${order.id}">Evadi Ordine</button>` : ''}
                            </td>
                        `;
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

            // Chiamate iniziali
            loadProductSkus();
            fetchOrders();
        });