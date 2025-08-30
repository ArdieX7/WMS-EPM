# WMS Deployment Quick Start

## 🚀 Guida Rapida Deployment VPS Hetzner

Questa è una guida rapida per deployare il WMS su VPS Hetzner. Per la guida completa vedi `deploy_guide_vps.md`.

## 📋 Prerequisiti

1. **Account Hetzner** con carta di credito
2. **Dominio** (opzionale ma consigliato)
3. **PC Windows** con PowerShell

## ⚡ Quick Setup (15 minuti)

### Step 1: SSH Keys (2 min)

```bash
# Su Windows PowerShell
ssh-keygen -t ed25519 -C "wms@tuodominio.com"
type C:\Users\TuoNome\.ssh\id_ed25519.pub
```

### Step 2: Crea VPS Hetzner (5 min)

**Configurazione raccomandata:**
- **Type**: CPX21 (€7.50/mese)
- **Image**: Ubuntu 22.04 LTS
- **Volume**: 40GB EXT4 
- **IPv4**: ✅ Sì (necessario)
- **SSH Key**: Incolla la tua chiave pubblica

**Nel campo Cloud Config copia/incolla:**
```yaml
#cloud-config
package_upgrade: true
packages: [docker.io, docker-compose-plugin, git, nginx, certbot, python3-certbot-nginx, ufw, htop]
users:
  - name: wms
    groups: [sudo, docker]
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh_authorized_keys:
      - TUA_CHIAVE_SSH_QUI
runcmd:
  - systemctl enable docker && systemctl start docker
  - ufw --force enable && ufw allow ssh && ufw allow 80/tcp && ufw allow 443/tcp
  - mkdir -p /opt/projects && chown wms:wms /opt/projects
```

### Step 3: Primo Accesso (3 min)

```bash
# Connetti al server
ssh wms@TUO_IP_SERVER

# Verifica installazione
docker --version
nginx -v

# Clone progetto
cd /opt/projects
git clone https://github.com/TUO_ACCOUNT/WMS_EPM.git
cd WMS_EPM
```

### Step 4: Deploy WMS (5 min)

```bash
# Setup ambiente
cp .env.production .env
nano .env  # Modifica password e domini

# Genera password sicure
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"

# Avvia applicazione
docker compose -f docker-compose.production.yml up -d

# Verifica status
docker compose ps
```

## 🔧 File Creati per Te

### Script Utili in `/scripts/`
- **`setup-server.sh`** - Setup automatico server completo
- **`backup-wms.sh`** - Backup automatico database e file
- **`monitor-wms.sh`** - Monitoraggio sistema WMS

### Configurazioni
- **`nginx-production.conf`** - Nginx ottimizzato per produzione
- **`docker-compose.production.yml`** - Docker Compose per produzione
- **`.env.production`** - Template environment sicuro

## 🏃‍♂️ Setup Automatico Completo

Se preferisci il setup automatico:

```bash
# Carica e esegui script setup
cd /opt/projects/WMS_EPM
chmod +x scripts/setup-server.sh
./scripts/setup-server.sh
```

## 🔒 SSL con Let's Encrypt (se hai dominio)

```bash
# Configura nginx per il dominio
sudo cp nginx-production.conf /etc/nginx/sites-available/wms
sudo ln -s /etc/nginx/sites-available/wms /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Modifica configurazione per il tuo dominio
sudo nano /etc/nginx/sites-available/wms  # Sostituisci TUO_DOMINIO.com

# Test e riavvio
sudo nginx -t
sudo systemctl restart nginx

# Ottieni certificato SSL
sudo certbot --nginx -d tuodominio.com -d www.tuodominio.com
```

## 📊 Monitoraggio

```bash
# Controllo rapido
./scripts/monitor-wms.sh --full

# Controllo interattivo
./scripts/monitor-wms.sh

# Verifica singoli servizi
docker compose ps
docker compose logs web
sudo systemctl status nginx
```

## 🗄️ Backup Automatico

```bash
# Test backup manuale
./scripts/backup-wms.sh

# Setup backup automatico (ogni notte alle 2:00)
crontab -e
# Aggiungi: 0 2 * * * /opt/projects/WMS_EPM/scripts/backup-wms.sh
```

## 🚨 Troubleshooting Rapido

### WMS non raggiungibile
```bash
# Verifica servizi
docker compose ps
sudo systemctl status nginx

# Controlla log
docker compose logs web
sudo tail -f /var/log/nginx/error.log
```

### Database non connette
```bash
# Riavvia database
docker compose restart db

# Verifica connessione
docker compose exec db pg_isready -U wms_user
```

### Spazio disco esaurito
```bash
# Pulizia Docker
docker system prune -a

# Controlla spazio
df -h
./scripts/monitor-wms.sh --disk
```

## 📞 Support Rapido

### Comandi Diagnostici Essenziali
```bash
# Status generale sistema
./scripts/monitor-wms.sh --full

# Log applicazione
docker compose logs -f web

# Risorse sistema
htop
docker stats

# Connettività
curl -I http://localhost:8000/
curl -I http://TUO_IP/
```

### File di Log Importanti
- **WMS**: `docker compose logs web`
- **Nginx**: `/var/log/nginx/error.log`
- **Sistema**: `/var/log/syslog`
- **Backup**: `/var/log/wms-backup.log`
- **Monitor**: `/var/log/wms-monitor.log`

## 💰 Costi Stimati

### Setup Base (CPX21)
- Server: €4.90/mese
- IPv4: €1.00/mese
- Volume 40GB: €1.60/mese
- **Totale: ~€7.50/mese**

### Setup Performante (CPX31)
- Server: €9.90/mese  
- IPv4: €1.00/mese
- Volume 80GB: €3.20/mese
- **Totale: ~€14.10/mese**

## ✅ Checklist Deployment

- [ ] VPS creato con cloud-config
- [ ] SSH keys configurate
- [ ] WMS deployato con Docker
- [ ] Nginx configurato
- [ ] SSL attivo (se dominio)
- [ ] Backup automatico setup
- [ ] Monitoraggio funzionante
- [ ] Test completo applicazione

## 🎯 Prossimi Passi Suggeriti

1. **Dominio personalizzato** + SSL
2. **Backup su cloud** (AWS S3, Google Drive)
3. **Monitoraggio avanzato** (Grafana, Prometheus)
4. **CI/CD** per deploy automatici
5. **Load balancer** per alta disponibilità

---

**Per maggiori dettagli vedi:**
- `deploy_guide_vps.md` - Guida completa
- `scripts/` - Script di automazione
- `docker-compose.production.yml` - Configurazione produzione

**Ultima modifica**: 2024-08-29