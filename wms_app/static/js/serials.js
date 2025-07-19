// JavaScript per la gestione seriali prodotto

document.addEventListener('DOMContentLoaded', function() {
    // Inizializzazione
    setupEventListeners();
});

function setupEventListeners() {
    // Form upload
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleFileUpload);
    }
}

// --- Gestione Upload File ---

async function handleFileUpload(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const resultDiv = document.getElementById('uploadResult');
    
    // Show loading
    showLoading(form);
    resultDiv.style.display = 'none';
    
    try {
        const response = await fetch('/serials/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        hideLoading(form);
        
        console.log('Upload response:', result); // Debug
        
        if (response.ok && result.success) {
            showUploadResult(result, 'success');
            // Refresh orders list after successful upload
            setTimeout(() => {
                refreshOrdersList();
            }, 1000);
        } else {
            showUploadResult(result, 'error');
        }
        
    } catch (error) {
        hideLoading(form);
        showUploadResult({
            success: false,
            message: 'Errore di rete durante il caricamento',
            errors: [error.message]
        }, 'error');
    }
}

function showUploadResult(result, type) {
    const resultDiv = document.getElementById('uploadResult');
    resultDiv.className = `result-container ${type}`;
    
    let html = `<h4>${result.success ? '✅ Upload Completato' : '❌ Errore Upload'}</h4>`;
    html += `<p><strong>Messaggio:</strong> ${result.message || 'Errore sconosciuto'}</p>`;
    
    if (result.success) {
        html += `<div class="upload-stats">`;
        html += `<p><strong>Righe processate:</strong> ${result.total_lines_processed}</p>`;
        html += `<p><strong>Seriali trovati:</strong> ${result.total_serials_found}</p>`;
        html += `<p><strong>Ordini trovati:</strong> ${result.total_orders_found}</p>`;
        if (result.upload_batch_id) {
            html += `<p><strong>Batch ID:</strong> <code>${result.upload_batch_id}</code></p>`;
        }
        html += `</div>`;
    }
    
    if (result.errors && result.errors.length > 0) {
        html += `<div class="upload-errors">`;
        html += `<h5>Errori trovati:</h5>`;
        html += `<ul>`;
        result.errors.forEach(error => {
            html += `<li>${error}</li>`;
        });
        html += `</ul>`;
        html += `</div>`;
    }
    
    if (result.warnings && result.warnings.length > 0) {
        html += `<div class="upload-warnings">`;
        html += `<h5>Avvisi:</h5>`;
        html += `<ul>`;
        result.warnings.forEach(warning => {
            html += `<li>${warning}</li>`;
        });
        html += `</ul>`;
        html += `</div>`;
    }
    
    resultDiv.innerHTML = html;
    resultDiv.style.display = 'block';
    
    // Scroll to result
    resultDiv.scrollIntoView({ behavior: 'smooth' });
}

// --- Gestione Lista Ordini ---

async function refreshOrdersList() {
    const tableBody = document.getElementById('ordersTableBody');
    
    try {
        showLoading(tableBody);
        
        const response = await fetch('/serials/orders');
        const orders = await response.json();
        
        hideLoading(tableBody);
        
        if (!response.ok) {
            throw new Error('Errore nel caricamento ordini');
        }
        
        renderOrdersTable(orders);
        
    } catch (error) {
        hideLoading(tableBody);
        console.error('Errore refresh ordini:', error);
        alert('Errore nel caricamento ordini: ' + error.message);
    }
}

function renderOrdersTable(orders) {
    const tableBody = document.getElementById('ordersTableBody');
    
    if (orders.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 20px;">
                    Nessun ordine con seriali trovato
                </td>
            </tr>
        `;
        return;
    }
    
    tableBody.innerHTML = orders.map(order => {
        const totalSerials = Object.values(order.found_serials).reduce((sum, serials) => sum + serials.length, 0);
        
        return `
            <tr>
                <td><strong>${order.order_number}</strong></td>
                <td>
                    ${order.order_exists ? 
                        `<span class="status-badge status-${order.order_status}">${order.order_status}</span>` :
                        `<span class="status-badge status-not-found">Non Trovato</span>`
                    }
                </td>
                <td>${Object.keys(order.expected_products).length}</td>
                <td>${totalSerials}</td>
                <td>
                    ${order.validation_summary ? 
                        `<span class="status-badge status-${order.validation_summary.overall_status}">${order.validation_summary.overall_status}</span>` :
                        `<span class="status-badge status-pending">Non Validato</span>`
                    }
                </td>
                <td>
                    ${order.last_upload_date ? 
                        new Date(order.last_upload_date).toLocaleString('it-IT') : 
                        'N/A'
                    }
                </td>
                <td class="actions">
                    <button onclick="viewOrderDetails('${order.order_number}')" 
                            class="btn btn-small btn-info" title="Visualizza Dettagli">
                        👁️ Dettagli
                    </button>
                    <button onclick="validateOrder('${order.order_number}')" 
                            class="btn btn-small btn-warning" title="Valida Seriali">
                        ✅ Valida
                    </button>
                    <button onclick="generateOrderPDF('${order.order_number}')" 
                            class="btn btn-small btn-success" title="Genera PDF">
                        📄 PDF
                    </button>
                    <button onclick="generateOrderExcel('${order.order_number}')" 
                            class="btn btn-small btn-success" title="Genera Excel">
                        📊 Excel
                    </button>
                    <button onclick="deleteOrderSerials('${order.order_number}')" 
                            class="btn btn-small btn-danger" title="Elimina Seriali">
                        🗑️ Elimina
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// --- Visualizzazione Dettagli Ordine ---

async function viewOrderDetails(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}`);
        const orderData = await response.json();
        
        if (!response.ok) {
            throw new Error('Errore nel caricamento dettagli ordine');
        }
        
        showOrderDetailsModal(orderData);
        
    } catch (error) {
        console.error('Errore dettagli ordine:', error);
        alert('Errore nel caricamento dettagli: ' + error.message);
    }
}

function showOrderDetailsModal(orderData) {
    const modal = document.getElementById('orderDetailsModal');
    const title = document.getElementById('modalOrderTitle');
    const content = document.getElementById('orderDetailsContent');
    
    title.textContent = `Dettagli Seriali Ordine ${orderData.order_number}`;
    
    let html = `
        <div class="order-info">
            <h4>📋 Informazioni Ordine</h4>
            <p><strong>Numero Ordine:</strong> ${orderData.order_number}</p>
            <p><strong>Ordine Esistente:</strong> ${orderData.order_exists ? 'Sì' : 'No'}</p>
            <p><strong>Stato:</strong> ${orderData.order_status || 'N/A'}</p>
            <p><strong>Ultima Modifica:</strong> ${orderData.last_upload_date ? 
                new Date(orderData.last_upload_date).toLocaleString('it-IT') : 'N/A'}</p>
        </div>
    `;
    
    // Confronto prodotti attesi vs trovati
    html += `<div class="products-comparison">`;
    html += `<h4>📦 Confronto Prodotti</h4>`;
    
    const allSkus = new Set([
        ...Object.keys(orderData.expected_products),
        ...Object.keys(orderData.found_serials)
    ]);
    
    if (allSkus.size === 0) {
        html += `<p>Nessun prodotto trovato.</p>`;
    } else {
        html += `<table style="width: 100%; border-collapse: collapse;">`;
        html += `<thead>
            <tr style="background: #f8f9fa;">
                <th style="padding: 8px; border: 1px solid #dee2e6;">SKU</th>
                <th style="padding: 8px; border: 1px solid #dee2e6;">Quantità Attesa</th>
                <th style="padding: 8px; border: 1px solid #dee2e6;">Seriali Trovati</th>
                <th style="padding: 8px; border: 1px solid #dee2e6;">Stato</th>
            </tr>
        </thead><tbody>`;
        
        Array.from(allSkus).sort().forEach(sku => {
            const expected = orderData.expected_products[sku] || 0;
            const found = orderData.found_serials[sku] ? orderData.found_serials[sku].length : 0;
            
            let status = 'OK';
            let statusClass = 'status-valid';
            
            if (expected === 0 && found > 0) {
                status = 'EXTRA';
                statusClass = 'status-warning';
            } else if (expected > 0 && found === 0) {
                status = 'MANCANTE';
                statusClass = 'status-invalid';
            } else if (expected !== found) {
                status = 'QUANTITÀ ERRATA';
                statusClass = 'status-warning';
            }
            
            html += `<tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>${sku}</strong></td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">${expected}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">${found}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">
                    <span class="status-badge ${statusClass}">${status}</span>
                </td>
            </tr>`;
        });
        
        html += `</tbody></table>`;
    }
    
    html += `</div>`;
    
    // Dettaglio seriali per prodotto
    if (Object.keys(orderData.found_serials).length > 0) {
        html += `<div class="serials-detail">`;
        html += `<h4>🏷️ Dettaglio Seriali</h4>`;
        
        Object.keys(orderData.found_serials).sort().forEach(sku => {
            const serials = orderData.found_serials[sku];
            html += `<div class="product-serials">`;
            html += `<h5>SKU: ${sku} (${serials.length} seriali)</h5>`;
            html += `<div class="serials-list">`;
            serials.forEach(serial => {
                html += `<div class="serial-item">${serial}</div>`;
            });
            html += `</div>`;
            html += `</div>`;
        });
        
        html += `</div>`;
    }
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function closeOrderDetailsModal() {
    document.getElementById('orderDetailsModal').style.display = 'none';
}

// --- Validazione Ordine ---

async function validateOrder(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/validate`);
        const validationData = await response.json();
        
        if (!response.ok) {
            throw new Error('Errore nella validazione ordine');
        }
        
        showValidationModal(validationData);
        
    } catch (error) {
        console.error('Errore validazione:', error);
        alert('Errore nella validazione: ' + error.message);
    }
}

function showValidationModal(validationData) {
    const modal = document.getElementById('validationModal');
    const title = document.getElementById('validationModalTitle');
    const content = document.getElementById('validationContent');
    
    title.textContent = `Validazione Ordine ${validationData.order_number}`;
    
    let html = `
        <div class="validation-summary">
            <h4>📊 Riepilogo Validazione</h4>
            <p><strong>Stato Generale:</strong> 
                <span class="status-badge status-${validationData.overall_status}">
                    ${validationData.overall_status.toUpperCase()}
                </span>
            </p>
            <p><strong>Seriali Trovati:</strong> ${validationData.total_serials_found}</p>
            <p><strong>Seriali Attesi:</strong> ${validationData.total_serials_expected}</p>
            <p><strong>Seriali Validi:</strong> ${validationData.valid_serials}</p>
            <p><strong>Seriali Invalidi:</strong> ${validationData.invalid_serials}</p>
        </div>
    `;
    
    // Flags di controllo
    html += `<div class="validation-flags">`;
    html += `<h4>🚩 Controlli Effettuati</h4>`;
    html += `<p><strong>Incongruenza Quantità:</strong> ${validationData.has_quantity_mismatch ? '❌ Sì' : '✅ No'}</p>`;
    html += `<p><strong>EAN Sconosciuti:</strong> ${validationData.has_unknown_ean ? '❌ Sì' : '✅ No'}</p>`;
    html += `<p><strong>Prodotti Errati:</strong> ${validationData.has_wrong_products ? '❌ Sì' : '✅ No'}</p>`;
    html += `<p><strong>Seriali Duplicati:</strong> ${validationData.has_duplicate_serials ? '❌ Sì' : '✅ No'}</p>`;
    html += `</div>`;
    
    // Prodotti mancanti
    if (validationData.missing_products.length > 0) {
        html += `<div class="missing-products">`;
        html += `<h4>❌ Prodotti Mancanti</h4>`;
        html += `<ul>`;
        validationData.missing_products.forEach(sku => {
            html += `<li>${sku}</li>`;
        });
        html += `</ul>`;
        html += `</div>`;
    }
    
    // Prodotti extra
    if (validationData.extra_products.length > 0) {
        html += `<div class="extra-products">`;
        html += `<h4>⚠️ Prodotti Extra (non nell'ordine)</h4>`;
        html += `<ul>`;
        validationData.extra_products.forEach(sku => {
            html += `<li>${sku}</li>`;
        });
        html += `</ul>`;
        html += `</div>`;
    }
    
    // Incongruenze quantità
    if (Object.keys(validationData.quantity_mismatches).length > 0) {
        html += `<div class="quantity-mismatches">`;
        html += `<h4>⚠️ Incongruenze Quantità</h4>`;
        html += `<table style="width: 100%; border-collapse: collapse;">`;
        html += `<thead>
            <tr style="background: #f8f9fa;">
                <th style="padding: 8px; border: 1px solid #dee2e6;">SKU</th>
                <th style="padding: 8px; border: 1px solid #dee2e6;">Attesa</th>
                <th style="padding: 8px; border: 1px solid #dee2e6;">Trovata</th>
                <th style="padding: 8px; border: 1px solid #dee2e6;">Differenza</th>
            </tr>
        </thead><tbody>`;
        
        Object.entries(validationData.quantity_mismatches).forEach(([sku, quantities]) => {
            const diff = quantities.found - quantities.expected;
            html += `<tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;">${sku}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">${quantities.expected}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">${quantities.found}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6; color: ${diff > 0 ? 'green' : 'red'};">
                    ${diff > 0 ? '+' : ''}${diff}
                </td>
            </tr>`;
        });
        
        html += `</tbody></table>`;
        html += `</div>`;
    }
    
    // Errori dettagliati
    if (validationData.errors.length > 0) {
        html += `<div class="validation-errors">`;
        html += `<h4>❌ Errori Dettagliati</h4>`;
        validationData.errors.forEach(error => {
            html += `<div class="error-item">`;
            html += `<div class="error-type">${error.error_type}</div>`;
            html += `<div>${error.message}</div>`;
            html += `</div>`;
        });
        html += `</div>`;
    }
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function closeValidationModal() {
    document.getElementById('validationModal').style.display = 'none';
}

// --- Generazione PDF ---

async function generateOrderPDF(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/pdf`);
        
        if (!response.ok) {
            throw new Error('Errore nella generazione PDF');
        }
        
        // Download del PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seriali_ordine_${orderNumber}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('Errore PDF:', error);
        alert('Errore nella generazione PDF: ' + error.message);
    }
}

// --- Generazione Excel ---

async function generateOrderExcel(orderNumber) {
    try {
        const response = await fetch(`/serials/orders/${orderNumber}/excel`);
        
        if (!response.ok) {
            throw new Error('Errore nella generazione Excel');
        }
        
        // Download dell'Excel
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seriali_ordine_${orderNumber}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('Errore Excel:', error);
        alert('Errore nella generazione Excel: ' + error.message);
    }
}

// --- Eliminazione Seriali ---

async function deleteOrderSerials(orderNumber) {
    if (!confirm(`Sei sicuro di voler eliminare tutti i seriali dell'ordine ${orderNumber}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/serials/orders/${orderNumber}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Errore nell\'eliminazione');
        }
        
        alert(result.message);
        refreshOrdersList();
        
    } catch (error) {
        console.error('Errore eliminazione:', error);
        alert('Errore nell\'eliminazione: ' + error.message);
    }
}

// --- Utility Functions ---

function showLoading(element) {
    element.classList.add('loading');
}

function hideLoading(element) {
    element.classList.remove('loading');
}

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const isHidden = section.style.display === 'none';
    section.style.display = isHidden ? 'block' : 'none';
    
    // Update toggle icon
    const toggleIcon = section.previousElementSibling.querySelector('.toggle-icon');
    if (toggleIcon) {
        toggleIcon.textContent = isHidden ? '▼' : '▶';
    }
}

function toggleFormatInfo() {
    const formatInfo = document.getElementById('format-info');
    const toggleIcon = document.getElementById('format-toggle-icon');
    
    if (formatInfo.style.display === 'none') {
        formatInfo.style.display = 'block';
        toggleIcon.textContent = '▼';
    } else {
        formatInfo.style.display = 'none';
        toggleIcon.textContent = '▶';
    }
}

// Close modals when clicking outside
window.onclick = function(event) {
    const orderModal = document.getElementById('orderDetailsModal');
    const validationModal = document.getElementById('validationModal');
    
    if (event.target === orderModal) {
        closeOrderDetailsModal();
    }
    if (event.target === validationModal) {
        closeValidationModal();
    }
}