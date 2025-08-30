/**
 * Enhanced Upload Component - Drag & Drop + Scanner Input
 * WMS EPM - Componente riutilizzabile per upload avanzati
 */

class EnhancedUpload {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        
        if (!this.container) {
            console.error(`Enhanced Upload: Container ${containerId} not found`);
            return;
        }

        // Configurazione default
        this.options = {
            acceptedTypes: ['.txt'],
            maxFileSize: 10 * 1024 * 1024, // 10MB
            enableDragDrop: true,
            enableScanner: true,
            onFileSelect: null,
            onScannerProcess: null,
            scannerPlaceholder: 'Incolla qui i dati dalla pistola scanner...\n\nEsempio:\nUB001_SKU123\nUB002_SKU456\n...',
            ...options
        };

        this.currentFile = null;
        this.currentMode = 'file';
        
        this.init();
    }

    init() {
        this.createUploadInterface();
        this.bindEvents();
        console.log(`✅ Enhanced Upload initialized for ${this.containerId}`);
    }

    createUploadInterface() {
        let uploadHTML = '';
        
        // Se scanner è disabilitato, mostra interfaccia semplificata
        if (!this.options.enableScanner) {
            uploadHTML = `
                <div class="enhanced-upload-header">
                    <h4 class="enhanced-upload-title">
                        📤 Caricamento File
                    </h4>
                </div>

                <!-- Area Drag & Drop -->
                ${this.options.enableDragDrop ? this.createDragDropZone() : ''}
                ${this.createFileInput()}

                <!-- Status e Preview -->
                <div class="upload-status" id="${this.containerId}-status"></div>
                <div class="file-preview" id="${this.containerId}-preview"></div>
            `;
        } else {
            // Interfaccia completa con toggle
            uploadHTML = `
                <div class="enhanced-upload-header">
                    <h4 class="enhanced-upload-title">
                        📤 Caricamento File
                    </h4>
                    <div class="upload-mode-toggle">
                        <button class="mode-button active" data-mode="file">
                            📁 File
                        </button>
                        <button class="mode-button" data-mode="scanner">
                            🔫 Scanner
                        </button>
                    </div>
                </div>

                <!-- Modalità File Upload -->
                <div class="upload-mode active" data-mode="file">
                    ${this.options.enableDragDrop ? this.createDragDropZone() : ''}
                    ${this.createFileInput()}
                </div>

                <!-- Modalità Scanner Input -->
                ${this.createScannerInput()}

                <!-- Status e Preview -->
                <div class="upload-status" id="${this.containerId}-status"></div>
                <div class="file-preview" id="${this.containerId}-preview"></div>
            `;
        }

        this.container.innerHTML = uploadHTML;
    }

    createDragDropZone() {
        return `
            <div class="drag-drop-zone" id="${this.containerId}-dropzone">
                <div class="drag-drop-content">
                    <div class="drag-drop-icon">📁</div>
                    <div class="drag-drop-text">Trascina qui il file</div>
                    <div class="drag-drop-hint">Oppure clicca per selezionare</div>
                    <div class="drag-drop-or"><span>oppure</span></div>
                    <button type="button" class="file-input-button" id="${this.containerId}-browse">
                        📂 Sfoglia File
                    </button>
                </div>
            </div>
        `;
    }

    createFileInput() {
        const acceptTypes = Array.isArray(this.options.acceptedTypes) ? 
            this.options.acceptedTypes.join(',') : this.options.acceptedTypes;
            
        return `
            <input type="file" 
                   id="${this.containerId}-file-input" 
                   class="file-input-hidden"
                   accept="${acceptTypes}" />
        `;
    }

    createScannerInput() {
        return `
            <div class="upload-mode" data-mode="scanner">
                <div class="scanner-input-zone">
                    <textarea 
                        class="scanner-textarea" 
                        id="${this.containerId}-scanner-input"
                        placeholder="${this.options.scannerPlaceholder}"></textarea>
                    
                    <div class="scanner-controls">
                        <div class="scanner-info">
                            <span>💡</span>
                            <span>Incolla i dati dalla pistola scanner</span>
                        </div>
                        <div class="scanner-buttons">
                            <button type="button" class="scanner-button" id="${this.containerId}-clear-scanner">
                                🗑️ Pulisci
                            </button>
                            <button type="button" class="scanner-button primary" id="${this.containerId}-process-scanner">
                                ⚡ Elabora
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    bindEvents() {
        // Mode Toggle
        const modeButtons = this.container.querySelectorAll('.mode-button');
        modeButtons.forEach(button => {
            button.addEventListener('click', (e) => this.switchMode(e.target.dataset.mode));
        });

        // File Input
        const fileInput = this.container.querySelector(`#${this.containerId}-file-input`);
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }

        // Browse Button
        const browseButton = this.container.querySelector(`#${this.containerId}-browse`);
        if (browseButton && fileInput) {
            browseButton.addEventListener('click', () => fileInput.click());
        }

        // Drag & Drop
        if (this.options.enableDragDrop) {
            this.bindDragDropEvents();
        }

        // Scanner
        if (this.options.enableScanner) {
            this.bindScannerEvents();
        }
    }

    bindDragDropEvents() {
        const dropZone = this.container.querySelector(`#${this.containerId}-dropzone`);
        if (!dropZone) return;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => this.highlight(dropZone), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => this.unhighlight(dropZone), false);
        });

        // Handle dropped files
        dropZone.addEventListener('drop', (e) => this.handleDrop(e), false);
        
        // Click to browse
        dropZone.addEventListener('click', () => {
            const fileInput = this.container.querySelector(`#${this.containerId}-file-input`);
            if (fileInput) fileInput.click();
        });
    }

    bindScannerEvents() {
        const processButton = this.container.querySelector(`#${this.containerId}-process-scanner`);
        const clearButton = this.container.querySelector(`#${this.containerId}-clear-scanner`);
        const scannerInput = this.container.querySelector(`#${this.containerId}-scanner-input`);
        
        if (processButton && scannerInput) {
            processButton.addEventListener('click', () => this.processScanner());
            
            // Auto-resize textarea
            scannerInput.addEventListener('input', (e) => {
                e.target.style.height = 'auto';
                e.target.style.height = e.target.scrollHeight + 'px';
            });

            // Keyboard shortcuts
            scannerInput.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    this.processScanner();
                }
            });
        }

        if (clearButton) {
            clearButton.addEventListener('click', () => this.clearScanner());
        }
    }

    switchMode(mode) {
        this.currentMode = mode;
        
        // Update buttons
        const buttons = this.container.querySelectorAll('.mode-button');
        buttons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Update content
        const contents = this.container.querySelectorAll('.upload-mode');
        contents.forEach(content => {
            content.classList.toggle('active', content.dataset.mode === mode);
        });

        this.clearStatus();
        this.clearPreview();
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight(element) {
        element.classList.add('drag-over');
    }

    unhighlight(element) {
        element.classList.remove('drag-over');
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            this.handleFiles(files);
        }
    }

    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.handleFiles(files);
        }
    }

    handleFiles(files) {
        const file = files[0];
        
        if (!this.validateFile(file)) {
            return;
        }

        this.currentFile = file;
        this.showFilePreview(file);
        this.showStatus('success', `✅ File "${file.name}" pronto per l'upload`);

        // Callback
        if (this.options.onFileSelect && typeof this.options.onFileSelect === 'function') {
            this.options.onFileSelect(file);
        }
    }

    validateFile(file) {
        // Check file type
        if (this.options.acceptedTypes && this.options.acceptedTypes.length > 0) {
            const fileExt = '.' + file.name.split('.').pop().toLowerCase();
            if (!this.options.acceptedTypes.includes(fileExt)) {
                this.showStatus('error', `❌ Tipo file non supportato. Accettati: ${this.options.acceptedTypes.join(', ')}`);
                return false;
            }
        }

        // Check file size
        if (file.size > this.options.maxFileSize) {
            const maxSizeMB = (this.options.maxFileSize / (1024 * 1024)).toFixed(1);
            this.showStatus('error', `❌ File troppo grande. Massimo ${maxSizeMB}MB`);
            return false;
        }

        return true;
    }

    processScanner() {
        const scannerInput = this.container.querySelector(`#${this.containerId}-scanner-input`);
        if (!scannerInput) return;

        const content = scannerInput.value.trim();
        if (!content) {
            this.showStatus('error', '❌ Inserisci i dati dalla pistola scanner');
            return;
        }

        this.showStatus('processing', '⏳ Elaborazione dati scanner...');

        // Convert textarea content to virtual file
        const blob = new Blob([content], { type: 'text/plain' });
        const virtualFile = new File([blob], 'scanner_input.txt', { type: 'text/plain' });
        
        this.currentFile = virtualFile;
        this.showFilePreview(virtualFile, true);
        this.showStatus('success', `✅ Dati scanner elaborati (${content.split('\\n').filter(l => l.trim()).length} righe)`);

        // Callback
        if (this.options.onScannerProcess && typeof this.options.onScannerProcess === 'function') {
            this.options.onScannerProcess(virtualFile, content);
        }
    }

    clearScanner() {
        const scannerInput = this.container.querySelector(`#${this.containerId}-scanner-input`);
        if (scannerInput) {
            scannerInput.value = '';
            scannerInput.style.height = 'auto';
        }
        this.clearStatus();
        this.clearPreview();
    }

    showFilePreview(file, isScanner = false) {
        const preview = this.container.querySelector(`#${this.containerId}-preview`);
        if (!preview) return;

        const sizeText = isScanner ? 
            `${file.size} bytes (da scanner)` : 
            `${(file.size / 1024).toFixed(1)} KB`;

        preview.innerHTML = `
            <div class="file-preview-header">
                <span class="file-preview-name">
                    ${isScanner ? '🔫' : '📁'} ${file.name}
                </span>
                <span class="file-preview-size">${sizeText}</span>
                <button class="file-preview-remove" onclick="window.enhancedUploads['${this.containerId}'].clearFile()" title="Rimuovi file">
                    ✕
                </button>
            </div>
        `;
        
        preview.classList.add('show');
    }

    clearFile() {
        this.currentFile = null;
        this.clearPreview();
        this.clearStatus();
        
        // Reset file input
        const fileInput = this.container.querySelector(`#${this.containerId}-file-input`);
        if (fileInput) {
            fileInput.value = '';
        }
    }

    clearPreview() {
        const preview = this.container.querySelector(`#${this.containerId}-preview`);
        if (preview) {
            preview.classList.remove('show');
            preview.innerHTML = '';
        }
    }

    showStatus(type, message) {
        const status = this.container.querySelector(`#${this.containerId}-status`);
        if (!status) return;

        status.className = `upload-status ${type}`;
        status.textContent = message;
        
        if (type === 'error') {
            this.container.classList.add('pulse');
            setTimeout(() => this.container.classList.remove('pulse'), 300);
        }
    }

    clearStatus() {
        const status = this.container.querySelector(`#${this.containerId}-status`);
        if (status) {
            status.className = 'upload-status';
            status.textContent = '';
        }
    }

    // Public methods
    getFile() {
        return this.currentFile;
    }

    getCurrentMode() {
        return this.currentMode;
    }

    reset() {
        this.clearFile();
        this.switchMode('file');
        
        if (this.options.enableScanner) {
            this.clearScanner();
        }
    }

    setStatus(type, message) {
        this.showStatus(type, message);
    }
}

// Global registry for enhanced uploads
window.enhancedUploads = window.enhancedUploads || {};

// Utility function to create enhanced upload
window.createEnhancedUpload = function(containerId, options) {
    const upload = new EnhancedUpload(containerId, options);
    window.enhancedUploads[containerId] = upload;
    return upload;
};