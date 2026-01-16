-- Script SQL per inserimento permessi feature "Arrivi"
-- Esegui questo script dopo aver avviato il server per la prima volta
-- per creare i permessi necessari nel database

-- Inserimento permessi per feature Arrivi
INSERT INTO permissions (name, description, section, action) VALUES
('arrivals_view', 'Visualizzare documenti arrivo', 'arrivals', 'view'),
('arrivals_create', 'Creare documenti arrivo', 'arrivals', 'create'),
('arrivals_manage', 'Modificare/eliminare documenti arrivo', 'arrivals', 'manage'),
('arrivals_confirm', 'Confermare documenti arrivo (carico a TERRA)', 'arrivals', 'confirm'),
('arrivals_scan', 'Scansionare prodotti da mobile', 'arrivals', 'scan');

-- Assegna tutti i permessi arrivals al ruolo admin (assumendo role_id=1 per admin)
-- NOTA: Modifica il role_id se il tuo admin ha un ID diverso
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions WHERE section = 'arrivals';

-- Verifica permessi inseriti
SELECT * FROM permissions WHERE section = 'arrivals';

-- Verifica assegnazione a role admin
SELECT rp.*, p.name, p.description
FROM role_permissions rp
JOIN permissions p ON rp.permission_id = p.id
WHERE p.section = 'arrivals';
