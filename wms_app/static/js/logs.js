/**
 * LOG OPERAZIONI - JAVASCRIPT MODULE
 * Sistema completo per visualizzazione, filtri e gestione logs WMS
 */

class LogsManager {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 50;
        this.totalPages = 0;
        this.totalCount = 0;
        this.currentFilters = {};
        this.currentSort = { column: 'timestamp', direction: 'desc' };
        this.isLoading = false;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.initializeFilters();
        this.loadStatistics();
        this.loadLogs();
    }
    
    bindEvents() {
        // Filtri
        document.getElementById('apply-filters-btn').addEventListener('click', () => this.applyFilters());
        document.getElementById('reset-filters-btn').addEventListener('click', () => this.resetFilters());
        
        // Azioni header
        document.getElementById('refresh-logs-btn').addEventListener('click', () => this.refreshData());
        document.getElementById('export-logs-btn').addEventListener('click', () => this.openExportOverlay());
        document.getElementById('cleanup-logs-btn').addEventListener('click', () => this.openCleanupOverlay());
        
        // Controlli tabella
        document.getElementById('page-size-select').addEventListener('change', (e) => {
            this.pageSize = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadLogs();
        });
        
        // Ordinamento tabella
        document.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                this.toggleSort(column);
            });
        });
        
        // Forms overlay
        document.getElementById('export-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.executeExport();
        });
        
        document.getElementById('cleanup-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.executeCleanup();
        });
        
        // Enter key sui filtri
        document.querySelectorAll('.filter-input').forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.applyFilters();
                }
            });
        });
    }
    
    initializeFilters() {
        // Imposta date default (ultimi 7 giorni)
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 7);
        
        document.getElementById('start-date').value = this.formatDateTimeLocal(startDate);
        document.getElementById('end-date').value = this.formatDateTimeLocal(endDate);
        
        // Per export, imposta stesso range
        document.getElementById('export-start-date').value = this.formatDateTimeLocal(startDate);
        document.getElementById('export-end-date').value = this.formatDateTimeLocal(endDate);
    }
    
    formatDateTimeLocal(date) {
        // Formato per datetime-local input
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }
    
    async loadStatistics() {
        try {
            const response = await fetch('/logs/statistics?days=7');
            if (!response.ok) throw new Error('Errore caricamento statistiche');
            
            const stats = await response.json();
            
            document.getElementById('total-operations').textContent = stats.total_operations;
            document.getElementById('error-operations').textContent = stats.error_operations;
            document.getElementById('warning-operations').textContent = stats.warning_operations;
            document.getElementById('success-rate').textContent = `${stats.success_rate.toFixed(1)}%`;
            
        } catch (error) {
            console.error('Errore caricamento statistiche:', error);
            this.showError('Errore nel caricamento delle statistiche');
        }
    }
    
    async loadLogs() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading(true);
        
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                page_size: this.pageSize,
                order_by: this.currentSort.column,
                order_direction: this.currentSort.direction,
                ...this.currentFilters
            });
            
            const response = await fetch(`/logs/data?${params}`);
            if (!response.ok) throw new Error('Errore caricamento logs');
            
            const data = await response.json();
            
            this.displayLogs(data.logs);
            this.updatePagination(data.pagination);
            this.updateResultsInfo(data.pagination);
            
        } catch (error) {
            console.error('Errore caricamento logs:', error);
            this.showError('Errore nel caricamento dei logs');
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }
    
    displayLogs(logs) {
        const tbody = document.getElementById('logs-table-body');
        tbody.innerHTML = '';
        
        if (logs.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; padding: 2rem; color: #666;">
                        Nessun log trovato con i filtri applicati
                    </td>
                </tr>
            `;
            return;
        }
        
        logs.forEach(log => {
            const row = document.createElement('tr');
            row.className = 'clickable';
            row.addEventListener('click', () => this.showLogDetails(log));
            
            row.innerHTML = `
                <td>${this.formatTimestamp(log.timestamp)}</td>
                <td>
                    <div class="operation-type">${this.formatOperationType(log.operation_type)}</div>
                    <small style="color: #666;">${log.operation_category}</small>
                </td>
                <td>${this.formatStatus(log.status)}</td>
                <td class="location-display">${log.product_sku || '-'}</td>
                <td class="location-display">${this.formatLocations(log.location_from, log.location_to)}</td>
                <td>${log.quantity || '-'}</td>
                <td>${log.user_id || '-'}</td>
                <td>
                    ${this.formatDetailsPreview(log)}
                </td>
            `;
            
            tbody.appendChild(row);
        });
    }
    
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString('it-IT', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    formatOperationType(type) {
        // Converte CARICO_MANUALE in "Carico Manuale"
        return type.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
        ).join(' ');
    }
    
    formatStatus(status) {
        const badges = {
            'SUCCESS': '<span class="status-badge success">✓ Successo</span>',
            'ERROR': '<span class="status-badge error">✗ Errore</span>',
            'WARNING': '<span class="status-badge warning">⚠ Warning</span>',
            'PARTIAL': '<span class="status-badge partial">◐ Parziale</span>',
            'CANCELLED': '<span class="status-badge cancelled">✕ Cancellato</span>'
        };
        
        return badges[status] || `<span class="status-badge">${status}</span>`;
    }
    
    formatLocations(locationFrom, locationTo) {
        if (!locationFrom && !locationTo) return '-';
        if (!locationFrom) return `→ ${locationTo}`;
        if (!locationTo) return locationFrom;
        return `${locationFrom} <span class="location-arrow">→</span> ${locationTo}`;
    }
    
    formatDetailsPreview(log) {
        let preview = [];
        
        // Per operazioni seriali, mostra il numero ordine invece del nome file
        if (log.operation_type === 'SERIALI_ASSEGNATI' || log.operation_type === 'SERIALI_RIMOSSI') {
            if (log.details && log.details.order_number) {
                preview.push(`📋 Ordine ${log.details.order_number}`);
            }
        } else if (log.file_name) {
            preview.push(`📁 ${log.file_name}`);
        }
        
        if (log.file_line_number) {
            preview.push(`#${log.file_line_number}`);
        }
        
        if (log.execution_time_ms) {
            preview.push(`⏱️ ${log.execution_time_ms}ms`);
        }
        
        if (log.error_message) {
            preview.push('❌ Errore');
        }
        
        if (log.warning_message) {
            preview.push('⚠️ Warning');
        }
        
        return preview.length > 0 ? `<small>${preview.join(' • ')}</small>` : '-';
    }
    
    showLogDetails(log) {
        const content = document.getElementById('log-details-content');
        
        content.innerHTML = `
            <div class="log-detail-section">
                <h4>📋 Informazioni Generali</h4>
                <div class="detail-grid">
                    <div class="detail-label">ID Operazione:</div>
                    <div class="detail-value monospace">${log.operation_id}</div>
                    
                    <div class="detail-label">Timestamp:</div>
                    <div class="detail-value">${this.formatTimestamp(log.timestamp)}</div>
                    
                    <div class="detail-label">Tipo Operazione:</div>
                    <div class="detail-value">${this.formatOperationType(log.operation_type)}</div>
                    
                    <div class="detail-label">Categoria:</div>
                    <div class="detail-value">${log.operation_category}</div>
                    
                    <div class="detail-label">Status:</div>
                    <div class="detail-value">${this.formatStatus(log.status)}</div>
                    
                    <div class="detail-label">Utente:</div>
                    <div class="detail-value">${log.user_id || '-'}</div>
                </div>
            </div>
            
            ${log.product_sku || log.location_from || log.location_to || log.quantity ? `
            <div class="log-detail-section">
                <h4>📦 Dettagli Prodotto/Ubicazione</h4>
                <div class="detail-grid">
                    ${log.product_sku ? `
                        <div class="detail-label">SKU Prodotto:</div>
                        <div class="detail-value monospace">${log.product_sku}</div>
                    ` : ''}
                    
                    ${log.location_from ? `
                        <div class="detail-label">Da Ubicazione:</div>
                        <div class="detail-value monospace">${log.location_from}</div>
                    ` : ''}
                    
                    ${log.location_to ? `
                        <div class="detail-label">A Ubicazione:</div>
                        <div class="detail-value monospace">${log.location_to}</div>
                    ` : ''}
                    
                    ${log.quantity ? `
                        <div class="detail-label">Quantità:</div>
                        <div class="detail-value">${log.quantity}</div>
                    ` : ''}
                </div>
            </div>
            ` : ''}
            
            ${log.file_name || log.file_line_number || log.execution_time_ms ? `
            <div class="log-detail-section">
                <h4>⚙️ Dettagli Tecnici</h4>
                <div class="detail-grid">
                    ${log.file_name ? `
                        <div class="detail-label">Nome File:</div>
                        <div class="detail-value">${log.file_name}</div>
                    ` : ''}
                    
                    ${log.file_line_number ? `
                        <div class="detail-label">Riga File:</div>
                        <div class="detail-value">${log.file_line_number}</div>
                    ` : ''}
                    
                    ${log.execution_time_ms ? `
                        <div class="detail-label">Tempo Esecuzione:</div>
                        <div class="detail-value">${log.execution_time_ms} ms</div>
                    ` : ''}
                </div>
            </div>
            ` : ''}
            
            ${log.error_message ? `
            <div class="log-detail-section">
                <h4>❌ Messaggio di Errore</h4>
                <div class="json-display">${log.error_message}</div>
            </div>
            ` : ''}
            
            ${log.warning_message ? `
            <div class="log-detail-section">
                <h4>⚠️ Messaggio di Warning</h4>
                <div class="json-display">${log.warning_message}</div>
            </div>
            ` : ''}
            
            ${log.details ? `
            <div class="log-detail-section">
                <h4>📄 Dettagli Aggiuntivi</h4>
                <div class="json-display">${JSON.stringify(log.details, null, 2)}</div>
            </div>
            ` : ''}
        `;
        
        document.getElementById('log-details-overlay').style.display = 'flex';
    }
    
    updatePagination(pagination) {
        this.currentPage = pagination.current_page;
        this.totalPages = pagination.total_pages;
        this.totalCount = pagination.total_count;
        
        const container = document.getElementById('pagination-container');
        container.innerHTML = '';
        
        if (this.totalPages <= 1) return;
        
        // Pulsante Previous
        const prevBtn = document.createElement('button');
        prevBtn.className = 'pagination-btn';
        prevBtn.textContent = '« Precedente';
        prevBtn.disabled = this.currentPage === 1;
        prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        container.appendChild(prevBtn);
        
        // Numeri pagina (con ellipsis se necessario)
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(this.totalPages, this.currentPage + 2);
        
        if (startPage > 1) {
            this.addPageButton(container, 1);
            if (startPage > 2) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.className = 'pagination-ellipsis';
                container.appendChild(ellipsis);
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            this.addPageButton(container, i);
        }
        
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.className = 'pagination-ellipsis';
                container.appendChild(ellipsis);
            }
            this.addPageButton(container, this.totalPages);
        }
        
        // Pulsante Next
        const nextBtn = document.createElement('button');
        nextBtn.className = 'pagination-btn';
        nextBtn.textContent = 'Successiva »';
        nextBtn.disabled = this.currentPage === this.totalPages;
        nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        container.appendChild(nextBtn);
        
        // Info paginazione
        const info = document.createElement('div');
        info.className = 'pagination-info';
        info.textContent = `Pagina ${this.currentPage} di ${this.totalPages}`;
        container.appendChild(info);
    }
    
    addPageButton(container, pageNum) {
        const btn = document.createElement('button');
        btn.className = `pagination-btn ${pageNum === this.currentPage ? 'active' : ''}`;
        btn.textContent = pageNum;
        btn.addEventListener('click', () => this.goToPage(pageNum));
        container.appendChild(btn);
    }
    
    goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.loadLogs();
    }
    
    updateResultsInfo(pagination) {
        const start = (pagination.current_page - 1) * pagination.page_size + 1;
        const end = Math.min(start + pagination.page_size - 1, pagination.total_count);
        
        document.getElementById('results-info').textContent = 
            `Visualizzati ${start}-${end} di ${pagination.total_count} logs`;
    }
    
    toggleSort(column) {
        if (this.currentSort.column === column) {
            this.currentSort.direction = this.currentSort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.currentSort.column = column;
            this.currentSort.direction = 'desc';
        }
        
        this.updateSortIndicators();
        this.currentPage = 1;
        this.loadLogs();
    }
    
    updateSortIndicators() {
        document.querySelectorAll('.sort-indicator').forEach(indicator => {
            indicator.className = 'sort-indicator';
        });
        
        const activeHeader = document.querySelector(`[data-column="${this.currentSort.column}"] .sort-indicator`);
        if (activeHeader) {
            activeHeader.className = `sort-indicator ${this.currentSort.direction}`;
        }
    }
    
    applyFilters() {
        this.currentFilters = {};
        
        // Date
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;
        
        if (startDate) this.currentFilters.start_date = startDate;
        if (endDate) this.currentFilters.end_date = endDate;
        
        // Multi-select
        const operationTypes = Array.from(document.getElementById('operation-type-filter').selectedOptions)
            .map(option => option.value).filter(v => v);
        const categories = Array.from(document.getElementById('category-filter').selectedOptions)
            .map(option => option.value).filter(v => v);
        const statuses = Array.from(document.getElementById('status-filter').selectedOptions)
            .map(option => option.value).filter(v => v);
        
        if (operationTypes.length > 0) this.currentFilters.operation_types = operationTypes.join(',');
        if (categories.length > 0) this.currentFilters.operation_categories = categories.join(',');
        if (statuses.length > 0) this.currentFilters.statuses = statuses.join(',');
        
        // Campi di ricerca
        const searchSku = document.getElementById('search-sku').value.trim();
        const searchLocation = document.getElementById('search-location').value.trim();
        const searchUser = document.getElementById('search-user').value.trim();
        const searchText = document.getElementById('search-text').value.trim();
        
        if (searchSku) this.currentFilters.product_sku = searchSku;
        if (searchLocation) this.currentFilters.location = searchLocation;
        if (searchUser) this.currentFilters.user_id = searchUser;
        if (searchText) this.currentFilters.search_text = searchText;
        
        this.currentPage = 1;
        this.loadLogs();
    }
    
    resetFilters() {
        // Reset form
        document.getElementById('start-date').value = '';
        document.getElementById('end-date').value = '';
        document.getElementById('operation-type-filter').selectedIndex = 0;
        document.getElementById('category-filter').selectedIndex = 0;
        document.getElementById('status-filter').selectedIndex = 0;
        document.getElementById('search-sku').value = '';
        document.getElementById('search-location').value = '';
        document.getElementById('search-user').value = '';
        document.getElementById('search-text').value = '';
        
        // Reset filtri interni
        this.currentFilters = {};
        this.currentPage = 1;
        
        // Reimposta filtri di default
        this.initializeFilters();
        this.loadLogs();
    }
    
    refreshData() {
        this.loadStatistics();
        this.loadLogs();
    }
    
    openExportOverlay() {
        document.getElementById('export-overlay').style.display = 'flex';
    }
    
    closeExportOverlay() {
        document.getElementById('export-overlay').style.display = 'none';
    }
    
    async executeExport() {
        const startDate = document.getElementById('export-start-date').value;
        const endDate = document.getElementById('export-end-date').value;
        const limit = document.getElementById('export-limit').value;
        
        try {
            const params = new URLSearchParams({
                start_date: startDate,
                end_date: endDate,
                limit: limit,
                ...this.currentFilters
            });
            
            const response = await fetch(`/logs/export?${params}`);
            if (!response.ok) throw new Error('Errore durante export');
            
            const data = await response.json();
            
            // Crea download
            const blob = new Blob([data.csv_data], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showSuccess(`Export completato: ${data.total_records} record esportati`);
            this.closeExportOverlay();
            
        } catch (error) {
            console.error('Errore export:', error);
            this.showError('Errore durante l\'export dei logs');
        }
    }
    
    openCleanupOverlay() {
        document.getElementById('cleanup-overlay').style.display = 'flex';
    }
    
    closeCleanupOverlay() {
        document.getElementById('cleanup-overlay').style.display = 'none';
    }
    
    async executeCleanup() {
        const daysToKeep = document.getElementById('cleanup-days').value;
        
        if (!confirm(`Sei sicuro di voler eliminare tutti i logs più vecchi di ${daysToKeep} giorni?`)) {
            return;
        }
        
        try {
            const response = await fetch(`/logs/cleanup?days_to_keep=${daysToKeep}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Errore durante pulizia');
            
            const data = await response.json();
            
            this.showSuccess(`Pulizia completata: ${data.deleted_count} logs rimossi`);
            this.closeCleanupOverlay();
            this.refreshData();
            
        } catch (error) {
            console.error('Errore pulizia:', error);
            this.showError('Errore durante la pulizia dei logs');
        }
    }
    
    showLoading(show) {
        document.getElementById('loading-indicator').style.display = show ? 'block' : 'none';
    }
    
    showError(message) {
        alert(`❌ ${message}`);
    }
    
    showSuccess(message) {
        alert(`✅ ${message}`);
    }
}

// Funzioni globali per overlay
function closeLogDetails() {
    document.getElementById('log-details-overlay').style.display = 'none';
}

function closeExportOverlay() {
    if (window.logsManager) {
        window.logsManager.closeExportOverlay();
    }
}

function closeCleanupOverlay() {
    if (window.logsManager) {
        window.logsManager.closeCleanupOverlay();
    }
}

// Inizializzazione quando il DOM è pronto
document.addEventListener('DOMContentLoaded', function() {
    window.logsManager = new LogsManager();
});