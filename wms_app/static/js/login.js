// Login JavaScript - WMS EPM
document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const loginButton = document.getElementById('loginButton');
    const buttonText = document.querySelector('.button-text');
    const buttonLoader = document.querySelector('.button-loader');
    const errorMessage = document.getElementById('errorMessage');
    const errorText = document.querySelector('.error-text');

    // Controllo se l'utente è già loggato
    checkAuthStatus();

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        if (!username || !password) {
            showError('Per favore inserisci username e password');
            return;
        }

        // Avvia loading
        setLoading(true);
        hideError();

        try {
            // Usa il sistema ModernAuth per il login
            const result = await window.modernAuth.login(username, password);

            if (result.success) {
                // Login riuscito
                showSuccess('Accesso effettuato con successo!');
                
                // Gestisci redirect se presente nell'URL
                const urlParams = new URLSearchParams(window.location.search);
                const redirectUrl = urlParams.get('redirect');
                
                setTimeout(() => {
                    if (redirectUrl) {
                        window.location.href = decodeURIComponent(redirectUrl);
                    } else {
                        window.location.href = '/';
                    }
                }, 1000);
            } else {
                // Login fallito
                showError(result.message || 'Credenziali non valide');
            }
        } catch (error) {
            console.error('Errore durante il login:', error);
            showError('Errore di connessione. Riprova più tardi.');
        } finally {
            setLoading(false);
        }
    });

    function setLoading(loading) {
        loginButton.disabled = loading;
        buttonText.style.display = loading ? 'none' : 'inline';
        buttonLoader.style.display = loading ? 'inline-flex' : 'none';
    }

    function showError(message) {
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        errorMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function hideError() {
        errorMessage.style.display = 'none';
    }

    function showSuccess(message) {
        // Mostra messaggio di successo temporaneo
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.innerHTML = `
            <span class="success-icon">✓</span>
            <span class="success-text">${message}</span>
        `;
        successDiv.style.cssText = `
            background: rgba(40, 167, 69, 0.1);
            border: 1px solid #28a745;
            border-radius: 10px;
            padding: 1rem 1.5rem;
            color: #28a745;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-top: 1rem;
            animation: slideInUp 0.3s ease-out;
        `;
        
        document.querySelector('.login-container').appendChild(successDiv);
        
        setTimeout(() => {
            successDiv.remove();
        }, 2000);
    }

    async function checkAuthStatus() {
        // Usa il sistema ModernAuth per verificare l'autenticazione
        if (window.modernAuth && window.modernAuth.isAuthenticated()) {
            try {
                const user = await window.modernAuth.getCurrentUser();
                if (user) {
                    // Utente già autenticato, gestisci redirect
                    const urlParams = new URLSearchParams(window.location.search);
                    const redirectUrl = urlParams.get('redirect');
                    
                    if (redirectUrl) {
                        window.location.href = decodeURIComponent(redirectUrl);
                    } else {
                        window.location.href = '/';
                    }
                    return;
                }
            } catch (error) {
                console.log('Token non valido, pulizia automatica...');
                window.modernAuth.clearTokens();
            }
        }
    }

    // Gestione del tasto Invio nei campi input
    document.getElementById('username').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('password').focus();
        }
    });

    document.getElementById('password').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            loginForm.dispatchEvent(new Event('submit'));
        }
    });

    // Auto-focus sul campo username
    document.getElementById('username').focus();
});