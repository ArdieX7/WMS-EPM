# Guida Deployment WMS su VPS Hetzner

## Panoramica
Guida completa per deployare il WMS su server VPS Hetzner con configurazione sicura e professionale.

## FASE 1: Configurazione VPS Hetzner

### 1.1 Specifiche Raccomandate

**Server Base (fino a 3 progetti):**
- **Location**: Falkenstein, Germania  
- **Image**: Ubuntu 22.04 LTS
- **Type**: CPX21 (2 vCPU, 4GB RAM, 40GB SSD) - €4.90/mese
- **Networking**: 
  - ✅ Public IPv4 (necessario) - €1/mese
  - ✅ Public IPv6 (gratuito)
- **Volume**: 40GB EXT4 - €1.60/mese
- **Server Name**: `wms-production-01`

**Server Scalabile (5+ progetti):**
- **Type**: CPX31 (4 vCPU, 8GB RAM, 80GB SSD) - €9.90/mese

### 1.2 Setup SSH Keys

**Sul tuo PC Windows (PowerShell Administrator):**

```bash
# Genera chiave SSH
ssh-keygen -t ed25519 -C "wms-deploy@tuodominio.com"

# Posizione: C:\Users\TuoNome\.ssh\id_ed25519
# Password: [IMPOSTA UNA PASSWORD SICURA]

# Copia chiave pubblica
type C:\Users\TuoNome\.ssh\id_ed25519.pub
```

**Nell'interfaccia Hetzner:**
1. Vai su "SSH Keys" nel pannello
2. Clicca "Add SSH Key"  
3. Incolla contenuto file `.pub`
4. Nome: "WMS-Deploy-Key"

### 1.3 Cloud Config (Automazione Setup Iniziale)

Nel campo "Cloud Config" durante creazione VPS:

```yaml
#cloud-config
package_upgrade: true
packages:
  - docker.io
  - docker-compose-plugin
  - git
  - nginx
  - certbot
  - python3-certbot-nginx
  - ufw
  - htop
  - curl
  - wget
  - unzip
  - tree
  - ncdu

groups:
  - docker

users:
  - name: wms
    groups: [sudo, docker]
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... # TUA CHIAVE QUI

runcmd:
  # Configura Docker
  - systemctl enable docker
  - systemctl start docker
  
  # Configura firewall base
  - ufw --force enable
  - ufw allow ssh
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw allow 8000/tcp
  
  # Ottimizza sistema per applicazioni web
  - sysctl -w vm.max_map_count=262144
  - sysctl -w net.core.somaxconn=65535
  - sysctl -w vm.swappiness=10
  
  # Crea directory struttura progetti
  - mkdir -p /opt/projects
  - chown wms:wms /opt/projects
  
  # Setup log rotation
  - echo "*/5 * * * * root /usr/sbin/logrotate /etc/logrotate.conf" >> /etc/crontab

write_files:
  - path: /etc/sysctl.d/99-wms-optimizations.conf
    content: |
      vm.max_map_count=262144
      net.core.somaxconn=65535
      vm.swappiness=10
      net.ipv4.tcp_keepalive_time=600
      net.ipv4.tcp_keepalive_intvl=60
      net.ipv4.tcp_keepalive_probes=3

  - path: /etc/security/limits.d/99-wms.conf
    content: |
      * soft nofile 65536
      * hard nofile 65536
      root soft nofile 65536
      root hard nofile 65536
```

## FASE 2: Prima Connessione e Setup Sicurezza

### 2.1 Connessione SSH

```bash
# Dal tuo PC
ssh wms@TUO_IP_SERVER

# Se hai problemi, usa root temporaneamente
ssh root@TUO_IP_SERVER
```

### 2.2 Setup Sicurezza Base

```bash
# Cambia password utenti
sudo passwd wms
sudo passwd root

# Configura timezone
sudo timedatectl set-timezone Europe/Rome

# Aggiorna sistema
sudo apt update && sudo apt upgrade -y

# Verifica installazioni
docker --version
docker compose version
nginx -v
```

### 2.3 Hardening SSH

```bash
# Backup configurazione SSH
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Modifica configurazione SSH
sudo nano /etc/ssh/sshd_config
```

**Configurazione SSH sicura:**
```
Port 22
Protocol 2
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers wms
```

```bash
# Riavvia SSH
sudo systemctl restart sshd

# Testa connessione da altra finestra PRIMA di chiudere
ssh wms@TUO_IP_SERVER
```

## FASE 3: Deploy WMS

### 3.1 Clone Repository

```bash
# Crea directory progetti
mkdir -p /opt/projects
cd /opt/projects

# Clone repository (configura accesso Git se privato)
git clone https://github.com/TUO_ACCOUNT/WMS_EPM.git
cd WMS_EPM

# Controlla files
ls -la
```

### 3.2 Configurazione Environment

```bash
# Crea configurazione produzione
cp .env.example .env.production

# Modifica per produzione
nano .env.production
```

**File .env.production:**
```env
# Database Configuration (GENERA PASSWORD SICURE!)
DATABASE_URL=postgresql://wms_user:TUA_PASSWORD_DB_SICURA@db:5432/wms_db

# Application Settings
DEBUG=False
SECRET_KEY=TUA_CHIAVE_SEGRETA_LUNGA_E_COMPLESSA_QUI

# Server Settings
HOST=0.0.0.0
PORT=8000
HTTPS_PORT=8443

# Production Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_WORKERS=4

# SSL Configuration
SSL_CERT_FILE=/opt/ssl/fullchain.pem
SSL_KEY_FILE=/opt/ssl/privkey.pem

# Backup Settings
BACKUP_ENABLED=True
BACKUP_RETENTION_DAYS=30
```

### 3.3 Genera Chiavi Sicure

```bash
# Genera SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Genera password database
openssl rand -base64 32
```

### 3.4 Build e Start Applicazione

```bash
# Copia configurazione
cp .env.production .env

# Start con Docker Compose
docker compose up -d

# Verifica status
docker compose ps
docker compose logs -f web
```

## FASE 4: Configurazione Nginx e SSL

### 4.1 Configurazione Nginx Base

```bash
# Rimuovi configurazione default
sudo rm /etc/nginx/sites-enabled/default

# Crea configurazione WMS
sudo nano /etc/nginx/sites-available/wms
```

**Configurazione Nginx (senza SSL inizialmente):**
```nginx
server {
    listen 80;
    server_name TUO_DOMINIO.com www.TUO_DOMINIO.com;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # Client settings
    client_max_body_size 50M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Static files (se necessario)
    location /static/ {
        alias /opt/projects/WMS_EPM/wms_app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }
}
```

```bash
# Abilita sito
sudo ln -s /etc/nginx/sites-available/wms /etc/nginx/sites-enabled/

# Testa configurazione
sudo nginx -t

# Riavvia nginx
sudo systemctl restart nginx
```

### 4.2 SSL con Let's Encrypt (se hai dominio)

```bash
# Ottieni certificato SSL
sudo certbot --nginx -d TUO_DOMINIO.com -d www.TUO_DOMINIO.com

# Rinnovo automatico (già configurato)
sudo systemctl status certbot.timer
```

### 4.3 Accesso via IP (senza dominio)

Se non hai dominio, configura nginx per IP:

```nginx
server {
    listen 80;
    server_name TUO_IP_SERVER;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## FASE 5: Monitoraggio e Backup

### 5.1 Setup Backup Automatico

Script di backup verrà creato separatamente (`backup-wms.sh`).

```bash
# Rendi eseguibile script backup
chmod +x /opt/projects/WMS_EPM/scripts/backup-wms.sh

# Setup cron per backup giornaliero alle 2:00
crontab -e
# Aggiungi: 0 2 * * * /opt/projects/WMS_EPM/scripts/backup-wms.sh
```

### 5.2 Monitoraggio

```bash
# Controlla status servizi
sudo systemctl status docker nginx

# Controlla logs applicazione
docker compose logs -f --tail=50 web

# Controlla risorse
htop
docker stats

# Spazio disco
df -h
ncdu /opt
```

### 5.3 Aggiornamenti

```bash
# Aggiornare applicazione
cd /opt/projects/WMS_EPM
git pull origin main
docker compose build
docker compose up -d

# Aggiornare sistema
sudo apt update && sudo apt upgrade -y
sudo reboot  # se necessario
```

## FASE 6: Multi-Progetto Setup

### 6.1 Struttura Directory

```
/opt/projects/
├── WMS_EPM/           (porta 8000)
├── progetto2/         (porta 8001) 
├── progetto3/         (porta 8002)
└── shared/
    ├── nginx/
    ├── ssl/
    └── backups/
```

### 6.2 Configurazione Nginx Multi-Progetti

```nginx
# /etc/nginx/sites-available/multi-projects
server {
    listen 80;
    server_name wms.tuodominio.com;
    location / {
        proxy_pass http://localhost:8000;
        # ... proxy headers
    }
}

server {
    listen 80;
    server_name app2.tuodominio.com;
    location / {
        proxy_pass http://localhost:8001;
        # ... proxy headers  
    }
}
```

## FASE 7: Troubleshooting

### 7.1 Problemi Comuni

**Applicazione non si avvia:**
```bash
docker compose logs web
docker compose restart web
```

**Nginx errore:**
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

**Database non connette:**
```bash
docker compose logs db
docker compose restart db
```

**Spazio disco pieno:**
```bash
# Pulizia Docker
docker system prune -a
docker volume prune

# Pulizia logs
sudo journalctl --vacuum-time=7d
```

### 7.2 Recovery Database

```bash
# Backup
docker compose exec db pg_dump -U wms_user wms_db > backup.sql

# Restore  
docker compose exec -T db psql -U wms_user -d wms_db < backup.sql
```

## FASE 8: Ottimizzazioni Prestazioni

### 8.1 Tuning Sistema

```bash
# Ottimizza swappiness
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf

# Aumenta limiti file
echo '* soft nofile 65536' | sudo tee -a /etc/security/limits.conf
echo '* hard nofile 65536' | sudo tee -a /etc/security/limits.conf
```

### 8.2 Monitoring con htop

```bash
# Installa htop se non presente
sudo apt install htop

# Monitora in tempo reale
htop

# Controlla connessioni
ss -tuln
netstat -tlnp
```

## Stima Costi

### Setup Base (CPX21)
- Server CPX21: €4.90/mese
- IPv4 pubblico: €1.00/mese  
- Volume 40GB: €1.60/mese
- **Totale: €7.50/mese**

### Setup Scalabile (CPX31)  
- Server CPX31: €9.90/mese
- IPv4 pubblico: €1.00/mese
- Volume 80GB: €3.20/mese  
- **Totale: €14.10/mese**

## Checklist Finale

- [ ] VPS creato con cloud-config
- [ ] SSH keys configurate
- [ ] Firewall attivo (UFW)
- [ ] WMS deployato con Docker
- [ ] Nginx configurato
- [ ] SSL attivo (se dominio disponibile)
- [ ] Backup automatico configurato
- [ ] Monitoraggio setup
- [ ] DNS puntato al server (se dominio)
- [ ] Test funzionalità complete

## Support

Per problemi o domande:
1. Controlla logs: `docker compose logs web`
2. Verifica status: `docker compose ps`  
3. Controlla risorse: `htop`
4. Test connessione DB: `docker compose exec db psql -U wms_user -d wms_db`

---
**Guida aggiornata**: 2024-08-29  
**Versione**: 1.0