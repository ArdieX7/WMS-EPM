document.addEventListener('DOMContentLoaded', function() {
    const productSkusDatalist = document.getElementById('product-skus');
    let commitData = null; // Variabile globale per i dati da committare

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
    const skuInputs = ['product-sku', 'move-product-sku'];
    skuInputs.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('input', function() {
                fetchAndPopulateDatalist(this.value);
            });
        }
    });

    // --- Gestione Form di Movimentazione (Carico/Scarico Manuale, Spostamento) ---
    const updateStockForm = document.getElementById('update-stock-form');
    if (updateStockForm) {
        updateStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per update-stock-form');
            const sku = document.getElementById('product-sku').value;
            const location = document.getElementById('location').value;
            const quantity = document.getElementById('quantity').value;

            console.log(`Invio richiesta a /inventory/update-stock per SKU: ${sku}, Ubicazione: ${location}, Quantità: ${quantity}`);
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
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Errore nella fetch per update-stock:', error);
                alert('Si è verificato un errore durante l\'aggiornamento manuale.');
            });
        });
    }

    const internalMoveForm = document.getElementById('internal-move-form');
    if (internalMoveForm) {
        internalMoveForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per internal-move-form');
            const sku = document.getElementById('move-product-sku').value;
            const fromLocation = document.getElementById('from-location').value;
            const toLocation = document.getElementById('to-location').value;
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
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Errore nella fetch per move-stock:', error);
                alert('Si è verificato un errore durante la movimentazione interna.');
            });
        });
    }

    // --- Gestione Form per Carico da File ---
    const addStockForm = document.getElementById('add-stock-form');
    if (addStockForm) {
        addStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per add-stock-form');
            const fileInput = document.getElementById('add-stock-file');
            const file = fileInput.files[0];
            if (!file) {
                alert('Per favore, seleziona un file.');
                console.log('Nessun file selezionato.');
                return;
            }
            console.log('File selezionato:', file.name);

            const formData = new FormData();
            formData.append('file', file);

            console.log('Invio richiesta a /inventory/add-stock-from-file');
            fetch('/inventory/add-stock-from-file', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Risposta dal server:', data);
                if (data.detail) {
                    alert('Errore: ' + data.detail);
                } else {
                    alert(data.message);
                    window.location.reload();
                }
            })
            .catch(error => {
                console.error('Errore nella fetch:', error);
                alert('Si è verificato un errore durante il caricamento.');
            });
        });
    }

    // --- Gestione Form per Scarico da File ---
    const subtractStockForm = document.getElementById('subtract-stock-form');
    if (subtractStockForm) {
        subtractStockForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Evento submit catturato per subtract-stock-form');
            const fileInput = document.getElementById('subtract-stock-file');
            const file = fileInput.files[0];
            if (!file) {
                alert('Per favore, seleziona un file.');
                console.log('Nessun file selezionato.');
                return;
            }
            console.log('File selezionato:', file.name);

            const formData = new FormData();
            formData.append('file', file);

            console.log('Invio richiesta a /inventory/subtract-stock-from-file');
            fetch('/inventory/subtract-stock-from-file', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail); });
                }
                return response.json();
            })
            .then(data => {
                console.log('Risposta dal server:', data);
                alert(data.message);
                window.location.reload();
            })
            .catch(error => {
                console.error('Errore nella fetch:', error);
                alert('Errore durante lo scarico: ' + error.message);
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
                alert('Per favore, seleziona un file.');
                console.log('Nessun file selezionato.');
                return;
            }
            console.log('File selezionato:', file.name);

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
});