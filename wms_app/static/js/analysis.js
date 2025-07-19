        document.addEventListener("DOMContentLoaded", function() {
            const kpiContainer = document.getElementById("kpi-container");
            const totalStockTableBody = document.querySelector("#total-stock-table tbody");
            const productSkusDatalist = document.getElementById("product-skus");

            // Caricamento dati iniziali della dashboard
            async function loadDashboardData() {
                try {
                    const response = await fetch("/analysis/data");
                    if (!response.ok) throw new Error("Errore nel caricamento dei dati di analisi.");
                    const data = await response.json();

                    // Popola i KPI
                    const kpis = data.kpis;
                    const formattedInventoryValue = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(kpis.total_inventory_value);

                    kpiContainer.innerHTML = `
                        <div class="kpi-box"><h3>Ubicazioni Totali</h3><div class="value">${kpis.total_locations}</div></div>
                        <div class="kpi-box"><h3>Ubicazioni Occupate</h3><div class="value">${kpis.occupied_locations}</div></div>
                        <div class="kpi-box"><h3>Ubicazioni Libere</h3><div class="value">${kpis.free_locations}</div></div>
                        <div class="kpi-box"><h3>Ubicazioni a Terra</h3><div class="value">${kpis.ground_floor_locations}</div></div>
                        <div class="kpi-box"><h3>Ubicazioni a Terra Libere</h3><div class="value">${kpis.free_ground_floor_locations}</div></div>
                        <div class="kpi-box"><h3>Pezzi in Scaffali</h3><div class="value">${kpis.total_pieces_in_shelves}</div></div>
                        <div class="kpi-box"><h3>Pezzi a Terra</h3><div class="value">${kpis.total_pieces_on_ground}</div></div>
                        <div class="kpi-box"><h3>Pezzi in Uscita</h3><div class="value">${kpis.total_pieces_outgoing}</div></div>
                        <div class="kpi-box"><h3>SKU Univoci a Magazzino</h3><div class="value">${kpis.unique_skus_in_stock}</div></div>
                        <div class="kpi-box"><h3>Valore Totale Inventario</h3><div class="value">${formattedInventoryValue}</div></div>
                    `;

                    // Popola la tabella delle giacenze totali
                    totalStockTableBody.innerHTML = '';
                    data.total_stock_by_product.forEach(item => {
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

                } catch (error) {
                    console.error(error);
                    kpiContainer.innerHTML = `<p>Impossibile caricare i dati della dashboard.</p>`;
                }
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
            const productLocationCloseButton = productLocationModal.querySelector(".close-button");
            let currentSkuForExport = '';

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

            productLocationCloseButton.onclick = () => { productLocationModal.style.display = "none"; }
            
            // Gestione esportazione CSV
            document.getElementById("export-csv-button").addEventListener("click", function() {
                if (currentSkuForExport) {
                    const encodedSku = encodeURIComponent(currentSkuForExport);
                    window.location.href = `/analysis/export-product-locations/${encodedSku}`;
                }
            });

            // Gestione ricerca prodotti per fila
            const productsByRowForm = document.getElementById("products-by-row-form");
            const productsByRowModal = document.getElementById("products-by-row-modal");
            const productsByRowCloseButton = productsByRowModal.querySelector(".close-button");
            let currentRowForExport = '';

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

            productsByRowCloseButton.onclick = () => { productsByRowModal.style.display = "none"; }

            // Gestione chiusura modali cliccando fuori
            window.onclick = (event) => {
                if (event.target == productLocationModal) productLocationModal.style.display = "none";
                if (event.target == productsByRowModal) productsByRowModal.style.display = "none";
            }

            // Gestione esportazione PDF
            document.getElementById("export-pdf-button").addEventListener("click", function() {
                if (currentRowForExport) {
                    window.location.href = `/analysis/export-products-by-row-pdf/${currentRowForExport}`;
                }
            });

            // Chiamate iniziali
            loadDashboardData();
            loadProductSkus();
        });