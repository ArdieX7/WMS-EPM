// Admin Page JavaScript - WMS EPM
document.addEventListener('DOMContentLoaded', function() {
    // Controlla che l'utente sia admin
    checkAdminAccess();
    
    // Carica i dati iniziali
    loadUsers();
    loadRoles();
    loadStats();
});

let currentUsers = [];
let availableRoles = [];
let editingUserId = null;
let currentRoles = [];
let availablePermissions = [];
let editingRoleId = null;

async function checkAdminAccess() {
    try {
        // USA IL NUOVO SISTEMA MODERNAUTH
        if (!window.modernAuth) {
            console.error('❌ ModernAuth non disponibile');
            window.location.href = '/login';
            return;
        }
        
        const user = await window.modernAuth.getCurrentUser();
        if (!user || !user.roles.some(role => role.name === 'admin')) {
            console.error('❌ Accesso negato: privilegi amministratore richiesti');
            alert('Accesso negato: sono richiesti privilegi di amministratore');
            window.location.href = '/';
            return;
        }
        
        console.log('✅ Accesso admin verificato per:', user.username);
    } catch (error) {
        console.error('❌ Errore nel controllo accesso admin:', error);
        window.location.href = '/login';
    }
}

async function loadUsers() {
    try {
        // USA MODERNAUTH CON JWT HEADERS
        const token = await window.modernAuth.getValidAccessToken();
        if (!token) {
            window.location.href = '/login';
            return;
        }
        
        const response = await fetch('/admin/api/users', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            currentUsers = await response.json();
            renderUsersTable();
            updateStats();
            console.log('✅ Utenti caricati:', currentUsers.length);
        } else {
            console.error('❌ Errore API utenti:', response.status);
            showError('Errore nel caricamento degli utenti');
        }
    } catch (error) {
        console.error('❌ Errore nel caricamento utenti:', error);
        showError('Errore di connessione');
    }
}

async function loadRoles() {
    try {
        // USA MODERNAUTH CON JWT HEADERS
        const token = await window.modernAuth.getValidAccessToken();
        if (!token) {
            window.location.href = '/login';
            return;
        }
        
        const response = await fetch('/admin/api/roles', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            availableRoles = await response.json();
            currentRoles = availableRoles; // Sincronizza entrambe le variabili
            renderRolesDropdown();
            renderRolesTable(); // AGGIUNGI: Renderizza anche la tabella ruoli
            console.log('✅ Ruoli caricati:', availableRoles.length);
        } else {
            console.error('❌ Errore API ruoli:', response.status);
            // Non è critico, continua senza ruoli
        }
    } catch (error) {
        console.error('❌ Errore nel caricamento ruoli:', error);
        // Non è critico, continua senza ruoli
    }
}

function renderUsersTable() {
    const tbody = document.getElementById('usersTableBody');
    
    if (currentUsers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">Nessun utente trovato</td></tr>';
        return;
    }
    
    tbody.innerHTML = currentUsers.map(user => `
        <tr>
            <td>${user.id}</td>
            <td><strong>${user.username}</strong></td>
            <td>${user.email}</td>
            <td>
                <div class="role-tags">
                    ${user.roles.map(role => `
                        <span class="role-tag ${role.name}">${role.name}</span>
                    `).join('')}
                </div>
            </td>
            <td>
                <span class="status-badge ${user.is_active ? 'status-active' : 'status-inactive'}">
                    ${user.is_active ? 'Attivo' : 'Inattivo'}
                </span>
            </td>
            <td>${formatDate(user.created_at)}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-sm btn-edit" onclick="editUser(${user.id})" title="Modifica">
                        ✏️
                    </button>
                    <button class="btn-sm btn-delete" onclick="deleteUser(${user.id}, '${user.username}')" title="Elimina">
                        🗑️
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function renderRolesDropdown() {
    const dropdown = document.getElementById('modalRoles');
    dropdown.innerHTML = '<option value="">Seleziona un ruolo...</option>' + 
        availableRoles.map(role => `
            <option value="${role.name}">${role.name}</option>
        `).join('');
}

function updateStats() {
    const totalUsers = currentUsers.length;
    const activeUsers = currentUsers.filter(u => u.is_active).length;
    const adminUsers = currentUsers.filter(u => u.roles.some(r => r.name === 'admin')).length;
    
    document.getElementById('total-users').textContent = totalUsers;
    document.getElementById('active-users').textContent = activeUsers;
    document.getElementById('admin-users').textContent = adminUsers;
}

function loadStats() {
    // Le statistiche vengono calcolate dai dati utenti caricati
    updateStats();
}

async function showCreateUserModal() {
    // Assicurati che i ruoli siano caricati
    if (availableRoles.length === 0) {
        await loadRoles();
    }
    
    editingUserId = null;
    document.getElementById('modalTitle').textContent = 'Nuovo Utente';
    document.getElementById('userForm').reset();
    document.getElementById('passwordGroup').style.display = 'block';
    document.getElementById('modalPassword').required = true;
    document.getElementById('modalIsActive').checked = true;
    
    // Aggiorna il dropdown ruoli e reset selezione
    renderRolesDropdown();
    document.getElementById('modalRoles').value = '';
    
    document.getElementById('userModal').style.display = 'flex';
}

async function editUser(userId) {
    const user = currentUsers.find(u => u.id === userId);
    if (!user) return;
    
    // Assicurati che i ruoli siano caricati
    if (availableRoles.length === 0) {
        await loadRoles();
    }
    
    editingUserId = userId;
    document.getElementById('modalTitle').textContent = 'Modifica Utente';
    document.getElementById('modalUsername').value = user.username;
    document.getElementById('modalEmail').value = user.email;
    document.getElementById('modalIsActive').checked = user.is_active;
    
    // Nascondi il campo password per la modifica
    document.getElementById('passwordGroup').style.display = 'none';
    document.getElementById('modalPassword').required = false;
    
    // Aggiorna il dropdown ruoli e seleziona il ruolo dell'utente
    renderRolesDropdown();
    const userRole = user.roles.length > 0 ? user.roles[0].name : '';
    document.getElementById('modalRoles').value = userRole;
    
    document.getElementById('userModal').style.display = 'flex';
}

function closeUserModal() {
    document.getElementById('userModal').style.display = 'none';
    editingUserId = null;
}

let userToDelete = null;

function deleteUser(userId, username) {
    userToDelete = userId;
    document.getElementById('deleteUsername').textContent = username;
    document.getElementById('deleteModal').style.display = 'flex';
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    userToDelete = null;
}

async function confirmDeleteUser() {
    if (!userToDelete) return;
    
    try {
        const token = await window.modernAuth.getValidAccessToken();
        const response = await fetch(`/admin/api/users/${userToDelete}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showSuccess('Utente eliminato con successo');
            closeDeleteModal();
            loadUsers(); // Ricarica la lista
        } else {
            const error = await response.json();
            showError(error.detail || 'Errore nell\'eliminazione');
        }
    } catch (error) {
        console.error('Errore nell\'eliminazione:', error);
        showError('Errore di connessione');
    }
}

// Gestione form utente
document.getElementById('userForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const selectedRole = document.getElementById('modalRoles').value;
    
    const userData = {
        username: formData.get('username'),
        email: formData.get('email'),
        is_active: formData.get('is_active') === 'on',
        role_names: selectedRole ? [selectedRole] : []
    };
    
    // Aggiungi password solo per nuovi utenti
    if (!editingUserId) {
        userData.password = formData.get('password');
    }
    
    setFormLoading(true);
    
    try {
        const url = editingUserId ? `/admin/api/users/${editingUserId}` : '/admin/api/users';
        const method = editingUserId ? 'PUT' : 'POST';
        
        const token = await window.modernAuth.getValidAccessToken();
        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        if (response.ok) {
            const message = editingUserId ? 'Utente aggiornato con successo' : 'Utente creato con successo';
            showSuccess(message);
            closeUserModal();
            loadUsers(); // Ricarica la lista
        } else {
            const error = await response.json();
            showError(error.detail || 'Errore nel salvataggio');
        }
    } catch (error) {
        console.error('Errore nel salvataggio:', error);
        showError('Errore di connessione');
    } finally {
        setFormLoading(false);
    }
});

function setFormLoading(loading) {
    const button = document.getElementById('submitButton');
    const buttonText = button.querySelector('.button-text');
    const buttonLoader = button.querySelector('.button-loader');
    
    button.disabled = loading;
    buttonText.style.display = loading ? 'none' : 'inline';
    buttonLoader.style.display = loading ? 'inline-flex' : 'none';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('it-IT', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showError(message) {
    // Sistema di notifiche semplice
    const notification = document.createElement('div');
    notification.className = 'notification error';
    notification.innerHTML = `
        <span class="notification-icon">⚠️</span>
        <span>${message}</span>
    `;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #fff5f5;
        color: #c53030;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #c53030;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1001;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        animation: slideInRight 0.3s ease-out;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function showSuccess(message) {
    const notification = document.createElement('div');
    notification.className = 'notification success';
    notification.innerHTML = `
        <span class="notification-icon">✅</span>
        <span>${message}</span>
    `;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #f0fff4;
        color: #2d5016;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #38a169;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1001;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        animation: slideInRight 0.3s ease-out;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// ========== GESTIONE TAB ==========
function showTab(tabName) {
    // Nasconde tutti i tab content
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
        tab.style.display = 'none';
    });
    
    // Rimuove active da tutti i tab button
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Mostra il tab selezionato
    const selectedTab = document.getElementById(`${tabName}-tab`);
    const selectedButton = document.querySelector(`[onclick="showTab('${tabName}')"]`);
    
    if (selectedTab && selectedButton) {
        selectedTab.classList.add('active');
        selectedTab.style.display = 'block';
        selectedButton.classList.add('active');
        
        // NUOVO: Carica dati specifici per tab
        if (tabName === 'roles') {
            loadRolesManagement(); // Carica i ruoli per la tabella
            console.log('🔄 Caricamento ruoli per tab roles...');
        } else if (tabName === 'users') {
            // Ricarica utenti se necessario
            if (currentUsers.length === 0) {
                loadUsers();
            }
        }
    }
}

// ========== GESTIONE RUOLI ==========
async function loadRolesManagement() {
    try {
        // USA MODERNAUTH CON JWT HEADERS
        const token = await window.modernAuth.getValidAccessToken();
        if (!token) {
            window.location.href = '/login';
            return;
        }
        
        const response = await fetch('/admin/api/roles', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            currentRoles = await response.json();
            renderRolesTable();
            console.log('✅ Ruoli management caricati:', currentRoles.length);
        } else {
            console.error('❌ Errore API ruoli management:', response.status);
            showError('Errore nel caricamento dei ruoli');
        }
    } catch (error) {
        console.error('❌ Errore nel caricamento ruoli:', error);
        showError('Errore di connessione');
    }
}

async function loadPermissions() {
    try {
        const token = await window.modernAuth.getValidAccessToken();
        const response = await fetch('/admin/api/permissions', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        if (response.ok) {
            availablePermissions = await response.json();
            renderPermissionsCheckboxes();
        }
    } catch (error) {
        console.error('Errore nel caricamento permessi:', error);
    }
}

function renderRolesTable() {
    const tbody = document.getElementById('rolesTableBody');
    
    if (currentRoles.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">Nessun ruolo trovato</td></tr>';
        return;
    }
    
    tbody.innerHTML = currentRoles.map(role => {
        const usersCount = currentUsers.filter(user => 
            user.roles.some(userRole => userRole.name === role.name)
        ).length;
        
        const isSystemRole = ['admin', 'operatore', 'cliente'].includes(role.name);
        
        return `
            <tr>
                <td>${role.id}</td>
                <td>
                    <strong>${role.name}</strong>
                    ${isSystemRole ? '<span class="system-badge">Sistema</span>' : ''}
                </td>
                <td>${role.description || '-'}</td>
                <td>
                    <div class="permission-tags">
                        ${(role.permissions && role.permissions.length > 0) ? 
                            role.permissions.slice(0, 5).map(perm => `
                                <span class="permission-tag ${perm.includes('_view') ? 'view' : 'manage'}">
                                    ${perm.replace('_', ' ')}
                                </span>
                            `).join('') : '<span class="no-permissions">Nessun permesso</span>'
                        }
                        ${(role.permissions && role.permissions.length > 5) ? `<span class="permission-tag">+${role.permissions.length - 5}</span>` : ''}
                    </div>
                </td>
                <td>
                    <span class="users-count">${usersCount} utenti</span>
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-sm btn-edit" onclick="editRole(${role.id})" title="Modifica">
                            ✏️
                        </button>
                        ${!isSystemRole ? `
                            <button class="btn-sm btn-delete" onclick="deleteRole(${role.id}, '${role.name}')" title="Elimina">
                                🗑️
                            </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function renderPermissionsCheckboxes() {
    const container = document.getElementById('permissionsContainer');
    
    container.innerHTML = availablePermissions.map(section => {
        // Separa i permessi base dai granulari
        const basePermissions = section.permissions.filter(p => 
            !p.action.includes('view_') || p.action === 'view'
        );
        const granularPermissions = section.permissions.filter(p => 
            p.action.includes('view_') && p.action !== 'view'
        );
        
        return `
            <div class="permission-section">
                <div class="permission-section-header">
                    <h4 class="section-title">${section.section.charAt(0).toUpperCase() + section.section.slice(1)}</h4>
                    <div class="section-controls">
                        <button type="button" class="btn-link" onclick="selectAllPermissions('${section.section}')">
                            Seleziona Tutti
                        </button>
                        <button type="button" class="btn-link" onclick="selectNoPermissions('${section.section}')">
                            Deseleziona
                        </button>
                    </div>
                </div>
                
                ${basePermissions.length > 0 ? `
                <div class="permissions-subsection">
                    <div class="subsection-header">Accesso Pagina</div>
                    <div class="permissions-grid">
                        ${basePermissions.map(perm => `
                            <div class="permission-item">
                                <input type="checkbox" name="permissions" value="${perm.name}" id="perm_${perm.id}" data-section="${section.section}">
                                <label for="perm_${perm.id}" class="permission-label">
                                    ${perm.description}
                                    <div class="permission-description">${perm.name}</div>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${granularPermissions.length > 0 ? `
                <div class="permissions-subsection">
                    <div class="subsection-header">Controllo Sezioni</div>
                    <div class="permissions-grid">
                        ${granularPermissions.map(perm => `
                            <div class="permission-item granular">
                                <input type="checkbox" name="permissions" value="${perm.name}" id="perm_${perm.id}" data-section="${section.section}">
                                <label for="perm_${perm.id}" class="permission-label">
                                    ${perm.description}
                                    <div class="permission-description">${perm.name}</div>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

function selectAllPermissions(section) {
    const checkboxes = document.querySelectorAll(`input[data-section="${section}"]`);
    checkboxes.forEach(cb => cb.checked = true);
}

function selectNoPermissions(section) {
    const checkboxes = document.querySelectorAll(`input[data-section="${section}"]`);
    checkboxes.forEach(cb => cb.checked = false);
}

async function showCreateRoleModal() {
    // Carica i permessi se non sono ancora stati caricati
    if (availablePermissions.length === 0) {
        await loadPermissions();
    }
    
    editingRoleId = null;
    document.getElementById('roleModalTitle').textContent = 'Nuovo Ruolo';
    document.getElementById('roleForm').reset();
    
    // Deseleziona tutti i permessi
    const checkboxes = document.querySelectorAll('#permissionsContainer input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
    
    document.getElementById('roleModal').style.display = 'flex';
}

async function editRole(roleId) {
    const role = currentRoles.find(r => r.id === roleId);
    if (!role) return;
    
    // Carica i permessi se non sono ancora stati caricati
    if (availablePermissions.length === 0) {
        await loadPermissions();
    }
    
    editingRoleId = roleId;
    document.getElementById('roleModalTitle').textContent = 'Modifica Ruolo';
    document.getElementById('roleName').value = role.name;
    document.getElementById('roleDescription').value = role.description || '';
    
    // Seleziona i permessi del ruolo
    const checkboxes = document.querySelectorAll('#permissionsContainer input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = role.permissions.includes(cb.value);
    });
    
    document.getElementById('roleModal').style.display = 'flex';
}

function closeRoleModal() {
    document.getElementById('roleModal').style.display = 'none';
    editingRoleId = null;
}

let roleToDelete = null;

function deleteRole(roleId, roleName) {
    roleToDelete = roleId;
    document.getElementById('deleteRoleName').textContent = roleName;
    document.getElementById('deleteRoleModal').style.display = 'flex';
}

function closeDeleteRoleModal() {
    document.getElementById('deleteRoleModal').style.display = 'none';
    roleToDelete = null;
}

async function confirmDeleteRole() {
    if (!roleToDelete) return;
    
    try {
        const token = await window.modernAuth.getValidAccessToken();
        const response = await fetch(`/admin/api/roles/${roleToDelete}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showSuccess('Ruolo eliminato con successo');
            closeDeleteRoleModal();
            loadRolesManagement();
        } else {
            const error = await response.json();
            showError(error.detail || 'Errore nell\'eliminazione');
        }
    } catch (error) {
        console.error('Errore nell\'eliminazione:', error);
        showError('Errore di connessione');
    }
}

// Gestione form ruolo
document.getElementById('roleForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const selectedPermissions = Array.from(document.querySelectorAll('#permissionsContainer input:checked'))
        .map(cb => cb.value);
    
    const roleData = {
        name: formData.get('name'),
        description: formData.get('description'),
        permissions: selectedPermissions
    };
    
    setRoleFormLoading(true);
    
    try {
        const url = editingRoleId ? `/admin/api/roles/${editingRoleId}` : '/admin/api/roles';
        const method = editingRoleId ? 'PUT' : 'POST';
        
        const token = await window.modernAuth.getValidAccessToken();
        const response = await fetch(url, {
            method: method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(roleData)
        });
        
        if (response.ok) {
            const message = editingRoleId ? 'Ruolo aggiornato con successo' : 'Ruolo creato con successo';
            showSuccess(message);
            closeRoleModal();
            loadRolesManagement();
            loadRoles(); // Ricarica ruoli per dropdown utenti
            loadUsers(); // Ricarica utenti per aggiornare dropdown ruoli
        } else {
            const error = await response.json();
            showError(error.detail || 'Errore nel salvataggio');
        }
    } catch (error) {
        console.error('Errore nel salvataggio:', error);
        showError('Errore di connessione');
    } finally {
        setRoleFormLoading(false);
    }
});

function setRoleFormLoading(loading) {
    const button = document.getElementById('roleSubmitButton');
    const buttonText = button.querySelector('.button-text');
    const buttonLoader = button.querySelector('.button-loader');
    
    button.disabled = loading;
    buttonText.style.display = loading ? 'none' : 'inline';
    buttonLoader.style.display = loading ? 'inline-flex' : 'none';
}