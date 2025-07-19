# 🚀 Guida al Deploy del WMS EPM

## Opzioni di Deployment

### 1. **VPS con Docker (Consigliato)**

#### Setup iniziale su Ubuntu/Debian:
```bash
# 1. Installa Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 2. Installa Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. Clone il repository
git clone <your-repo-url>
cd WMS_EPM

# 4. Configura environment
cp .env.example .env
nano .env  # Modifica configurazioni

# 5. Avvia con Docker
docker-compose up -d
```

#### Configurazione dominio:
```bash
# In nginx.conf, cambia:
server_name your-domain.com;
# Con il tuo dominio reale

# Per SSL con Let's Encrypt:
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 2. **Railway (Più Semplice)**

1. **Vai su [railway.app](https://railway.app)**
2. **Connetti il tuo repository GitHub**
3. **Aggiungi PostgreSQL database**
4. **Configura variabili ambiente:**
   ```
   DATABASE_URL=<postgresql-url-da-railway>
   HOST=0.0.0.0
   PORT=8000
   DEBUG=False
   ```

### 3. **DigitalOcean App Platform**

1. **Crea file `app.yaml`:**
```yaml
name: wms-epm
services:
- name: web
  source_dir: /
  github:
    repo: your-username/WMS_EPM
    branch: main
  run_command: python start_server.py
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: DEBUG
    value: "False"
databases:
- name: wms-db
  engine: PG
  version: "15"
```

### 4. **Heroku**

```bash
# Installa Heroku CLI
# Crea Procfile:
echo "web: python start_server.py" > Procfile

# Deploy:
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku config:set DEBUG=False
git push heroku main
```

## 📋 Checklist Pre-Deploy

- [ ] **Database**: Migra dati da SQLite a PostgreSQL
- [ ] **Environment**: Configura variabili `.env`
- [ ] **SSL**: Configura certificato per HTTPS
- [ ] **Dominio**: Punta DNS al server
- [ ] **Backup**: Configura backup automatici database
- [ ] **Monitoring**: Setup logging e monitoraggio
- [ ] **Security**: Firewall e security headers

## 🔧 Migrazione Database

```python
# Script per migrare da SQLite a PostgreSQL
import sqlite3
import psycopg2
from sqlalchemy import create_engine

# Esporta da SQLite
sqlite_conn = sqlite3.connect('wms.db')
# Importa in PostgreSQL
postgres_engine = create_engine('postgresql://user:pass@host:5432/db')
```

## 💰 Costi Stimati

| Provider | Piano | Costo/mese | Caratteristiche |
|----------|-------|------------|-----------------|
| Railway | Hobby | $5 | 512MB RAM, 1GB storage |
| DigitalOcean | Basic | $12 | 1GB RAM, 25GB storage |
| Heroku | Basic | $7+$9 | Dyno + PostgreSQL |
| VPS Vultr | Regular | $6 | 1GB RAM, 25GB SSD |

## 🛠️ Troubleshooting

### Errori comuni:
- **Port già in uso**: Cambia PORT in `.env`
- **Database connection**: Verifica DATABASE_URL
- **Static files**: Configura Nginx per servire `/static/`
- **Memory issues**: Aumenta RAM server o ottimizza query

## 📞 Supporto

Per problemi specifici del deploy, controlla:
1. **Logs applicazione**: `docker-compose logs web`
2. **Database logs**: `docker-compose logs db`
3. **Nginx logs**: `docker-compose logs nginx`