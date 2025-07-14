        document.addEventListener("DOMContentLoaded", function() {
            const productsTableBody = document.querySelector("#products-table tbody");
            const createProductForm = document.getElementById("create-product-form");

            // Funzione per caricare i prodotti
            async function fetchProducts() {
                const response = await fetch("/products/");
                const products = await response.json();
                
                productsTableBody.innerHTML = ''; // Pulisce la tabella

                products.forEach(product => {
                    const eanList = product.eans.map(ean => ean.ean).join(', ');
                    const formattedValue = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(product.estimated_value || 0);
                    const row = `<tr>
                        <td>${product.sku}</td>
                        <td>${product.description || ''}</td>
                        <td>${formattedValue}</td>
                        <td>${eanList}</td>
                        <td>
                            <button class="edit-product-button" data-sku="${product.sku}">Modifica</button>
                        </td>
                    </tr>`;
                    productsTableBody.innerHTML += row;
                });

                // Aggiungi listener per i bottoni Modifica
                document.querySelectorAll(".edit-product-button").forEach(button => {
                    button.addEventListener("click", async function() {
                        const skuToEdit = this.dataset.sku;
                        await showEditProductForm(skuToEdit);
                    });
                });
            }

            // Funzione per creare un prodotto
            createProductForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                
                const sku = document.getElementById("sku").value;
                const description = document.getElementById("description").value;
                const estimated_value = parseFloat(document.getElementById("estimated_value").value) || 0.0;
                const eans = document.getElementById("eans").value.split(',').map(e => e.trim()).filter(e => e);

                const response = await fetch("/products/", {
                    method: "POST",
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ sku, description, estimated_value, eans })
                });

                if (response.ok) {
                    createProductForm.reset();
                    alert("Prodotto aggiunto con successo!");
                    fetchProducts(); // Ricarica la lista
                } else {
                    const error = await response.json();
                    alert(`Errore: ${error.detail}`);
                }
            });

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
                document.getElementById("edit-eans").value = product.eans.map(ean => ean.ean).join(', ');
                document.getElementById("edit-product-section").style.display = "block";
            }

            // Gestione invio form Modifica Prodotto
            const editProductForm = document.getElementById("edit-product-form");
            editProductForm.addEventListener("submit", async function(event) {
                event.preventDefault();
                const sku = document.getElementById("edit-sku").value;
                const description = document.getElementById("edit-description").value;
                const estimated_value = parseFloat(document.getElementById("edit-estimated_value").value) || 0.0;
                const eans = document.getElementById("edit-eans").value.split(',').map(e => e.trim()).filter(e => e);

                const response = await fetch(`/products/${sku}`,
                    {
                        method: "PUT",
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ sku, description, estimated_value, eans })
                    });

                if (response.ok) {
                    alert("Prodotto aggiornato con successo!");
                    document.getElementById("edit-product-section").style.display = "none";
                    fetchProducts(); // Ricarica la lista
                } else {
                    const error = await response.json();
                    alert(`Errore nell'aggiornamento prodotto: ${error.detail}`);
                }
            });

            // Aggiungi un bottone per chiudere il form di modifica
            document.getElementById("cancel-edit-button").addEventListener("click", function() {
                document.getElementById("edit-product-section").style.display = "none";
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
                    alert("Seleziona un file TXT da importare.");
                    return;
                }

                const formData = new FormData();
                formData.append("file", file);

                try {
                    const response = await fetch("/products/import-ean-txt", {
                        method: "POST",
                        body: formData,
                    });

                    if (response.ok) {
                        const result = await response.json();
                        alert(`Importazione completata: ${result.message}`);
                        importProductsEanForm.reset();
                        fetchProducts(); // Ricarica la lista dei prodotti
                    } else {
                        const error = await response.json();
                        alert(`Errore nell'importazione: ${error.detail}`);
                    }
                } catch (error) {
                    console.error("Errore nell'importazione prodotti/EAN:", error);
                    alert("Errore nell'importazione prodotti/EAN.");
                }
            });
        });