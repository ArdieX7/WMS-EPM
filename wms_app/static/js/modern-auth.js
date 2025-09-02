/**
 * Modern Authentication System - WMS EPM
 * Sistema di autenticazione unificato con JWT, refresh token e zero flash
 * Ottimizzato per desktop e mobile con gestione robusta degli errori
 */

class ModernAuth {
    constructor() {
        this.accessToken = localStorage.getItem('access_token');
        this.refreshToken = localStorage.getItem('refresh_token');
        this.currentUser = null;
        this.userPermissions = null;
        this.refreshPromise = null;
        this.initialized = false;
        this.pendingPermissionChecks = [];
        
        // Configurazione
        this.config = {
            apiBase: '/api/auth',
            refreshThreshold: 2 * 60 * 1000, // Refresh 2 minuti prima della scadenza
            maxRetries: 3,
            retryDelay: 1000,
            mobileTimeout: 10000, // Timeout maggiore per mobile
            desktopTimeout: 5000
        };
        
        // Binding metodi
        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
        this.handleOnline = this.handleOnline.bind(this);
        this.handleOffline = this.handleOffline.bind(this);
        
        // Setup event listeners
        this.setupEventListeners();
        
        console.log('🔐 ModernAuth inizializzato');
    }
    
    setupEventListeners() {
        // Gestione visibilità tab per refresh automatico
        document.addEventListener('visibilitychange', this.handleVisibilityChange);
        
        // Gestione connessione online/offline
        window.addEventListener('online', this.handleOnline);
        window.addEventListener('offline', this.handleOffline);
        
        // Cleanup su unload
        window.addEventListener('beforeunload', () => {
            if (this.refreshPromise) {
                this.refreshPromise = null;
            }
        });
    }
    
    // =================== GESTIONE TOKEN ===================
    
    isAuthenticated() {
        return !!(this.accessToken && this.refreshToken);
    }
    
    async getValidAccessToken() {
        if (!this.accessToken) return null;
        
        // Controlla se il token sta per scadere
        if (this.isTokenNearExpiry()) {
            return await this.refreshAccessToken();
        }
        
        return this.accessToken;
    }
    
    isTokenNearExpiry() {
        if (!this.accessToken) return true;
        
        try {
            // Decodifica JWT senza verificare signature (per leggere exp)
            const payload = JSON.parse(atob(this.accessToken.split('.')[1]));
            const exp = payload.exp * 1000; // Converti in millisecondi
            const now = Date.now();
            
            return (exp - now) < this.config.refreshThreshold;
        } catch (e) {
            console.warn('Errore decodifica token JWT:', e);
            return true;
        }
    }
    
    async refreshAccessToken() {
        // Evita chiamate multiple simultanee
        if (this.refreshPromise) {
            return await this.refreshPromise;
        }
        
        if (!this.refreshToken) {
            this.logout();
            return null;
        }
        
        this.refreshPromise = this.performRefresh();
        const result = await this.refreshPromise;
        this.refreshPromise = null;
        
        return result;
    }
    
    async performRefresh() {
        try {
            console.log('🔄 Refresh token in corso...');
            
            const response = await fetch(`${this.config.apiBase}/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ refresh_token: this.refreshToken })
            });
            
            if (response.ok) {
                const tokens = await response.json();
                this.setTokens(tokens.access_token, tokens.refresh_token);
                console.log('✅ Token refresh completato');
                return tokens.access_token;
            } else {
                console.warn('❌ Refresh token fallito:', response.status);
                this.logout();
                return null;
            }
        } catch (error) {
            console.error('❌ Errore refresh token:', error);
            this.logout();
            return null;
        }
    }
    
    setTokens(accessToken, refreshToken) {
        this.accessToken = accessToken;
        this.refreshToken = refreshToken;
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
    }
    
    clearTokens() {
        this.accessToken = null;
        this.refreshToken = null;
        this.currentUser = null;
        this.userPermissions = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    }
    
    // =================== UTENTE E PERMESSI ===================
    
    async getCurrentUser() {
        console.log('👤 getCurrentUser chiamato, currentUser cached:', !!this.currentUser);
        if (this.currentUser) return this.currentUser;
        
        const token = await this.getValidAccessToken();
        console.log('🔑 Token valido ottenuto:', !!token);
        if (!token) return null;
        
        try {
            console.log('🌐 Chiamata API /me...');
            const response = await this.authenticatedFetch(`${this.config.apiBase}/me`);
            console.log('📡 Risposta API /me:', response.status, response.statusText);
            
            if (response.ok) {
                this.currentUser = await response.json();
                this.userPermissions = this.currentUser.permissions;
                
                console.log('✅ Utente caricato con successo:', this.currentUser.username);
                console.log('🔐 Permessi caricati:', this.userPermissions?.length || 0);
                
                // Rendi disponibili globalmente
                window.currentUser = this.currentUser;
                window.userPermissions = this.userPermissions;
                
                return this.currentUser;
            } else if (response.status === 401) {
                console.log('🚫 Token non autorizzato, eseguo logout');
                this.logout();
                return null;
            } else {
                console.log('❌ Errore API /me:', response.status);
                return null;
            }
        } catch (error) {
            console.error('❌ Errore caricamento utente:', error);
            return null;
        }
    }
    
    hasPermission(permission) {
        return this.userPermissions?.includes(permission) || false;
    }
    
    hasRole(roleName) {
        return this.currentUser?.roles?.some(role => role.name === roleName) || false;
    }
    
    // =================== RICHIESTE AUTENTICATE ===================
    
    async authenticatedFetch(url, options = {}) {
        const token = await this.getValidAccessToken();
        if (!token) {
            throw new Error('Token non disponibile');
        }
        
        const authOptions = {
            ...options,
            headers: {
                ...options.headers,
                'Authorization': `Bearer ${token}`
            }
        };
        
        // Retry logic per richieste critiche
        let lastError;
        for (let attempt = 0; attempt < this.config.maxRetries; attempt++) {
            try {
                const response = await fetch(url, authOptions);
                
                if (response.status === 401 && attempt === 0) {
                    // Primo tentativo fallito - prova refresh
                    const newToken = await this.refreshAccessToken();
                    if (newToken) {
                        authOptions.headers.Authorization = `Bearer ${newToken}`;
                        continue; // Riprova con nuovo token
                    } else {
                        this.logout();
                        throw new Error('Autenticazione fallita');
                    }
                }
                
                return response;
            } catch (error) {
                lastError = error;
                if (attempt < this.config.maxRetries - 1) {
                    await this.delay(this.config.retryDelay * (attempt + 1));
                }
            }
        }
        
        throw lastError;
    }
    
    // =================== AUTENTICAZIONE PAGINE ===================
    
    async initializePageAuth() {
        // Pagine pubbliche che non richiedono autenticazione
        const publicPages = ['/login'];
        
        if (publicPages.includes(window.location.pathname)) {
            this.markPageAsAuthenticated();
            
            // Se è la home e l'utente è autenticato, carica comunque i dati
            if (window.location.pathname === '/' && this.isAuthenticated()) {
                try {
                    console.log('🔄 Caricamento dati utente per home...');
                    const user = await this.getCurrentUser();
                    console.log('👤 Utente caricato:', user);
                    if (user) {
                        this.applyPermissions();
                        this.updateUI(user);
                        console.log('✅ UI aggiornata con dati utente');
                    } else {
                        console.log('⚠️ Nessun utente restituito - token potrebbe essere scaduto');
                        // Pulisci i token se non validi
                        this.clearTokens();
                        this.updateUI(null);
                    }
                } catch (error) {
                    console.log('❌ Errore caricamento utente opzionale:', error);
                    // Pulisci i token se c'è un errore
                    this.clearTokens();
                    this.updateUI(null);
                }
            } else {
                // Per pagine pubbliche senza autenticazione, mostra login area
                this.updateUI(null);
            }
            
            return true;
        }
        
        // Per tutte le altre pagine, controlla autenticazione
        if (!this.isAuthenticated()) {
            this.redirectToLogin();
            return false;
        }
        
        try {
            // Carica dati utente
            const user = await this.getCurrentUser();
            if (!user) {
                this.redirectToLogin();
                return false;
            }
            
            // Applica permessi
            this.applyPermissions();
            
            // Aggiorna UI
            this.updateUI(user);
            
            // Marca pagina come autenticata
            this.markPageAsAuthenticated();
            
            this.initialized = true;
            
            // Esegui controlli permesso pendenti
            this.executePermissionChecks();
            
            return true;
        } catch (error) {
            console.error('Errore inizializzazione autenticazione:', error);
            this.showError('Errore di autenticazione. Riprova.');
            return false;
        }
    }
    
    requirePermission(permission) {
        console.log(`🔐 Controllo permesso: ${permission}`);
        console.log(`👤 Utente corrente:`, this.currentUser?.username);
        console.log(`🔑 Permessi utente:`, this.userPermissions);
        
        if (!this.hasPermission(permission)) {
            console.log(`❌ ACCESSO NEGATO - Permesso: ${permission}`);
            
            // SICUREZZA CRITICA: Nascondi immediatamente tutti i contenuti
            this.hideProtectedContent();
            
            // Mostra errore e redirect
            this.showError(`⛔ ACCESSO NEGATO - Permesso richiesto: ${permission}`);
            setTimeout(() => {
                this.redirectToLogin();
            }, 3000);
            return false;
        }
        
        console.log(`✅ Permesso concesso: ${permission}`);
        // Permessi OK - mostra il contenuto protetto
        this.showProtectedContent();
        return true;
    }
    
    applyPermissions() {
        if (!this.userPermissions) return;
        
        const elementsWithPermissions = document.querySelectorAll('[data-permission]');
        elementsWithPermissions.forEach(element => {
            const requiredPermission = element.getAttribute('data-permission');
            const hasPermission = this.hasPermission(requiredPermission);
            
            element.style.display = hasPermission ? '' : 'none';
        });
    }
    
    executePermissionChecks() {
        console.log('🔍 Esecuzione controlli permesso pendenti:', this.pendingPermissionChecks.length);
        console.log('📋 Lista permessi da controllare:', this.pendingPermissionChecks);
        
        if (this.pendingPermissionChecks.length === 0) {
            console.log('✅ Nessun permesso da controllare - pagina pubblica');
            this.showProtectedContent();
            return;
        }
        
        // Esegui tutti i controlli permesso in attesa
        let allPermissionsValid = true;
        this.pendingPermissionChecks.forEach(permission => {
            const hasPermission = this.requirePermission(permission);
            if (!hasPermission) {
                allPermissionsValid = false;
            }
        });
        
        // Pulisci la lista
        this.pendingPermissionChecks = [];
        
        console.log('🎯 Risultato controlli permessi:', allPermissionsValid);
    }
    
    // =================== UI E UX ===================
    
    showLoadingOverlay(message = 'Verifica autenticazione...') {
        const overlay = document.createElement('div');
        overlay.className = 'auth-loading-overlay active';
        overlay.innerHTML = `
            <div class="auth-loader">
                <div class="spinner"></div>
                <p class="message">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }
    
    hideLoadingOverlay(overlay) {
        if (overlay) {
            overlay.classList.add('fade-out');
            setTimeout(() => overlay.remove(), 300);
        }
    }
    
    showError(message) {
        const error = document.createElement('div');
        error.className = 'auth-error';
        error.textContent = message;
        document.body.appendChild(error);
        
        setTimeout(() => error.remove(), 5000);
    }
    
    markPageAsAuthenticated() {
        document.body.classList.add('auth-checked', 'page-entering');
    }
    
    hideProtectedContent() {
        document.body.classList.remove('permissions-checked');
        console.log('🚫 SICUREZZA: Contenuto protetto nascosto');
        
        // Sicurezza aggiuntiva: nascondi tutto manualmente
        const protectedElements = document.querySelectorAll('.protected-content');
        protectedElements.forEach(el => {
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.opacity = '0';
        });
    }
    
    showProtectedContent() {
        document.body.classList.add('permissions-checked');
        console.log('✅ AUTORIZZATO: Contenuto protetto mostrato');
        
        // Mostra contenuto autorizzato
        const protectedElements = document.querySelectorAll('.protected-content');
        protectedElements.forEach(el => {
            el.style.display = '';
            el.style.visibility = '';
            el.style.opacity = '';
        });
    }
    
    // NUOVO: Nascondi tutto immediatamente all'avvio (chiamata immediata)
    static securePageOnLoad() {
        // Eseguito IMMEDIATAMENTE quando script carica
        document.body.classList.remove('permissions-checked');
        
        const protectedElements = document.querySelectorAll('.protected-content');
        protectedElements.forEach(el => {
            el.style.display = 'none !important';
            el.style.visibility = 'hidden !important';
        });
        
        console.log('🔒 SICUREZZA: Pagina protetta all\'avvio');
    }
    
    updateUI(user) {
        // Aggiorna la navbar con le informazioni utente
        const userArea = document.getElementById('user-area');
        const loginArea = document.getElementById('login-area');
        const userNameDisplay = document.getElementById('user-name-display');
        const userRoleDisplay = document.getElementById('user-role-display');
        const logoutButton = document.getElementById('logout-button');
        
        if (user && userArea && loginArea) {
            // Mostra area utente, nascondi area login
            userArea.style.display = 'flex';
            loginArea.style.display = 'none';
            
            // Aggiorna informazioni utente
            if (userNameDisplay) userNameDisplay.textContent = user.username;
            if (userRoleDisplay) userRoleDisplay.textContent = user.roles.map(r => r.name).join(', ');
            
            // Configura pulsante logout
            if (logoutButton) {
                logoutButton.onclick = () => this.showLogoutConfirm();
            }
        } else {
            // Utente non autenticato - mostra area login
            if (userArea) userArea.style.display = 'none';
            if (loginArea) loginArea.style.display = 'block';
        }
    }
    
    // =================== LOGIN/LOGOUT ===================
    
    async login(username, password) {
        try {
            const response = await fetch(`${this.config.apiBase}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            if (response.ok) {
                const tokens = await response.json();
                this.setTokens(tokens.access_token, tokens.refresh_token);
                
                // Carica dati utente
                await this.getCurrentUser();
                
                return { success: true };
            } else {
                const error = await response.json();
                return { success: false, message: error.detail || 'Login fallito' };
            }
        } catch (error) {
            console.error('Errore login:', error);
            return { success: false, message: 'Errore di connessione' };
        }
    }
    
    async logout() {
        if (this.refreshToken) {
            try {
                await fetch(`${this.config.apiBase}/logout`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ refresh_token: this.refreshToken })
                });
            } catch (e) {
                // Ignore logout errors
            }
        }
        
        this.clearTokens();
        this.redirectToLogin();
    }
    
    showLogoutConfirm() {
        if (confirm('Sei sicuro di voler uscire dal sistema?')) {
            this.logout();
        }
    }
    
    redirectToLogin() {
        const currentPath = window.location.pathname;
        if (currentPath !== '/login') {
            window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
        }
    }
    
    // =================== EVENT HANDLERS ===================
    
    handleVisibilityChange() {
        if (!document.hidden && this.initialized) {
            // Tab è tornato visibile - verifica token
            this.getValidAccessToken().catch(() => this.logout());
        }
    }
    
    handleOnline() {
        console.log('🌐 Connessione ripristinata');
        if (this.initialized) {
            this.getValidAccessToken().catch(() => this.logout());
        }
    }
    
    handleOffline() {
        console.log('📴 Connessione persa');
    }
    
    // =================== UTILITIES ===================
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    isMobile() {
        return /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }
    
    getTimeout() {
        return this.isMobile() ? this.config.mobileTimeout : this.config.desktopTimeout;
    }
}

// =================== INIZIALIZZAZIONE GLOBALE ===================

// SICUREZZA IMMEDIATA: Nascondi contenuto appena lo script carica
ModernAuth.securePageOnLoad();

// Crea istanza globale
window.modernAuth = new ModernAuth();

// Funzioni di compatibilità globale
window.hasPermission = (permission) => window.modernAuth.hasPermission(permission);
window.requirePermission = (permission) => {
    if (window.modernAuth.initialized && window.modernAuth.userPermissions) {
        // Sistema inizializzato - controllo immediato
        return window.modernAuth.requirePermission(permission);
    } else {
        // Sistema non ancora inizializzato - aggiungi alla lista pendenti
        console.log(`⏳ Permesso ${permission} in attesa di inizializzazione`);
        
        // Evita duplicati
        if (!window.modernAuth.pendingPermissionChecks.includes(permission)) {
            window.modernAuth.pendingPermissionChecks.push(permission);
        }
        
        // Sistema di fallback per controlli che non partono
        setTimeout(() => {
            if (window.modernAuth.pendingPermissionChecks.includes(permission)) {
                console.log(`⚠️ FALLBACK: Controllo forzato per ${permission}`);
                if (window.modernAuth.initialized && window.modernAuth.userPermissions) {
                    window.modernAuth.executePermissionChecks();
                } else {
                    console.log(`❌ FALLBACK: Sistema ancora non inizializzato per ${permission}`);
                    // Se ancora non è inizializzato dopo 5 secondi, c'è un problema
                    window.modernAuth.showError(`Errore caricamento permessi: ${permission}`);
                    setTimeout(() => window.modernAuth.redirectToLogin(), 2000);
                }
            }
        }, 5000); // Fallback dopo 5 secondi
        
        return true; // Permetti temporaneamente, sarà controllato dopo
    }
};

// Funzione di debug per pulire l'autenticazione
window.clearAuth = () => {
    console.log('🧹 Pulizia autenticazione forzata...');
    window.modernAuth.clearTokens();
    window.location.reload();
};

// Auto-inizializzazione quando DOM è pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAuth);
} else {
    initializeAuth();
}

async function initializeAuth() {
    console.log('🚀 Inizializzazione autenticazione moderna...');
    console.log('📍 Percorso corrente:', window.location.pathname);
    console.log('🔐 Token presente:', !!window.modernAuth.accessToken);
    
    // Mostra loader solo se necessario
    let overlay = null;
    if (!document.body.classList.contains('auth-checked')) {
        overlay = window.modernAuth.showLoadingOverlay();
    }
    
    try {
        const success = await window.modernAuth.initializePageAuth();
        if (!success) {
            console.log('❌ Autenticazione fallita');
            return;
        }
        
        console.log('✅ Autenticazione completata');
        
        // Debug UI update
        const userArea = document.getElementById('user-area');
        const loginArea = document.getElementById('login-area');
        console.log('🎨 User area presente:', !!userArea);
        console.log('🎨 Login area presente:', !!loginArea);
        
    } catch (error) {
        console.error('❌ Errore critico autenticazione:', error);
        window.modernAuth.showError('Errore di sistema. Ricarica la pagina.');
    } finally {
        if (overlay) {
            window.modernAuth.hideLoadingOverlay(overlay);
        }
    }
}

// Export per uso in moduli
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModernAuth;
}