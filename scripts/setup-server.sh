#!/bin/bash

# Setup Server Script per WMS Deployment su VPS Ubuntu
# Versione: 1.0
# Data: 2024-08-29

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzioni helper
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verifica se è root/sudo
check_privileges() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Non eseguire questo script come root. Usa un utente normale con sudo."
        exit 1
    fi
    
    if ! sudo -n true 2>/dev/null; then
        log_error "Questo script richiede privilegi sudo."
        exit 1
    fi
}

# Verifica sistema operativo
check_system() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "Sistema operativo non supportato"
        exit 1
    fi
    
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]] || [[ "${VERSION_ID}" != "22.04" ]]; then
        log_warning "Script testato su Ubuntu 22.04. Il tuo sistema: $ID $VERSION_ID"
        read -p "Continuare comunque? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Aggiorna sistema
update_system() {
    log_info "Aggiornamento sistema..."
    sudo apt update
    sudo apt upgrade -y
    log_success "Sistema aggiornato"
}

# Installa pacchetti base
install_base_packages() {
    log_info "Installazione pacchetti base..."
    
    local packages=(
        "curl"
        "wget"
        "git"
        "unzip"
        "tree"
        "htop"
        "ncdu"
        "ufw"
        "nginx"
        "certbot"
        "python3-certbot-nginx"
        "software-properties-common"
        "apt-transport-https"
        "ca-certificates"
        "gnupg"
        "lsb-release"
    )
    
    sudo apt install -y "${packages[@]}"
    log_success "Pacchetti base installati"
}

# Installa Docker
install_docker() {
    log_info "Installazione Docker..."
    
    # Rimuovi versioni precedenti
    sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Aggiungi repository Docker
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Installa Docker
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Aggiungi utente al gruppo docker
    sudo usermod -aG docker $USER
    
    # Abilita Docker
    sudo systemctl enable docker
    sudo systemctl start docker
    
    log_success "Docker installato"
}

# Configura firewall
setup_firewall() {
    log_info "Configurazione firewall (UFW)..."
    
    # Reset UFW
    sudo ufw --force reset
    
    # Policy di default
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Regole base
    sudo ufw allow ssh
    sudo ufw allow 80/tcp   # HTTP
    sudo ufw allow 443/tcp  # HTTPS
    sudo ufw allow 8000/tcp # App development
    
    # Abilita UFW
    sudo ufw --force enable
    
    log_success "Firewall configurato"
}

# Ottimizza sistema per applicazioni web
optimize_system() {
    log_info "Ottimizzazione sistema per applicazioni web..."
    
    # Ottimizzazioni sysctl
    sudo tee /etc/sysctl.d/99-wms-optimizations.conf > /dev/null <<EOF
# Ottimizzazioni WMS
vm.max_map_count=262144
net.core.somaxconn=65535
vm.swappiness=10
net.ipv4.tcp_keepalive_time=600
net.ipv4.tcp_keepalive_intvl=60
net.ipv4.tcp_keepalive_probes=3

# Ottimizzazioni network
net.ipv4.tcp_fin_timeout=15
net.ipv4.tcp_tw_reuse=1
net.core.rmem_max=134217728
net.core.wmem_max=134217728
net.ipv4.tcp_rmem=4096 65536 134217728
net.ipv4.tcp_wmem=4096 65536 134217728
EOF
    
    # Applica ottimizzazioni
    sudo sysctl -p /etc/sysctl.d/99-wms-optimizations.conf
    
    # Ottimizzazioni limits
    sudo tee /etc/security/limits.d/99-wms.conf > /dev/null <<EOF
# Ottimizzazioni file limits per WMS
* soft nofile 65536
* hard nofile 65536
root soft nofile 65536
root hard nofile 65536
EOF
    
    log_success "Sistema ottimizzato"
}

# Configura nginx base
setup_nginx() {
    log_info "Configurazione Nginx base..."
    
    # Backup configurazione originale
    sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
    
    # Rimuovi sito default
    sudo rm -f /etc/nginx/sites-enabled/default
    
    # Configura nginx.conf ottimizzato
    sudo tee /etc/nginx/nginx.conf > /dev/null <<'EOF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    # Basic Settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;
    
    # Hide nginx version
    server_tokens off;
    
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # SSL Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    
    # Logging Settings
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                   '$status $body_bytes_sent "$http_referer" '
                   '"$http_user_agent" "$http_x_forwarded_for"';
                   
    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log;
    
    # Gzip Settings
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Virtual Host Configs
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
EOF
    
    # Test configurazione
    sudo nginx -t
    
    # Abilita nginx
    sudo systemctl enable nginx
    sudo systemctl restart nginx
    
    log_success "Nginx configurato"
}

# Crea struttura directory
create_directories() {
    log_info "Creazione struttura directory..."
    
    # Directory principali
    sudo mkdir -p /opt/projects
    sudo mkdir -p /opt/ssl
    sudo mkdir -p /opt/backups
    sudo mkdir -p /opt/scripts
    
    # Cambia ownership
    sudo chown -R $USER:$USER /opt/projects
    sudo chown -R $USER:$USER /opt/backups
    sudo chown -R $USER:$USER /opt/scripts
    
    log_success "Directory create"
}

# Setup log rotation
setup_log_rotation() {
    log_info "Configurazione log rotation..."
    
    sudo tee /etc/logrotate.d/wms > /dev/null <<EOF
/opt/projects/*/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        docker compose restart web 2>/dev/null || true
    endscript
}

/var/log/nginx/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data adm
    prerotate
        if [ -d /etc/logrotate.d/httpd-prerotate ]; then \
            run-parts /etc/logrotate.d/httpd-prerotate; \
        fi
    endscript
    postrotate
        invoke-rc.d nginx rotate >/dev/null 2>&1
    endscript
}
EOF
    
    log_success "Log rotation configurato"
}

# Hardening SSH
harden_ssh() {
    log_info "Hardening SSH..."
    
    # Backup configurazione SSH
    sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
    
    # Applica configurazioni di sicurezza
    sudo sed -i 's/#Port 22/Port 22/' /etc/ssh/sshd_config
    sudo sed -i 's/#Protocol 2/Protocol 2/' /etc/ssh/sshd_config
    sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
    sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
    sudo sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
    sudo sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
    
    # Aggiungi configurazioni aggiuntive
    echo "ClientAliveInterval 300" | sudo tee -a /etc/ssh/sshd_config
    echo "ClientAliveCountMax 2" | sudo tee -a /etc/ssh/sshd_config
    echo "AllowUsers $USER" | sudo tee -a /etc/ssh/sshd_config
    
    # Test configurazione
    sudo sshd -t
    
    log_success "SSH configurato (NON disconnetterti prima di testare una nuova connessione!)"
}

# Installa strumenti di monitoraggio
install_monitoring_tools() {
    log_info "Installazione strumenti di monitoraggio..."
    
    # Installa htop, iotop, etc.
    sudo apt install -y htop iotop nethogs iftop dstat
    
    log_success "Strumenti di monitoraggio installati"
}

# Setup timezone
setup_timezone() {
    log_info "Configurazione timezone..."
    
    sudo timedatectl set-timezone Europe/Rome
    
    log_success "Timezone configurato: Europe/Rome"
}

# Crea script utili
create_utility_scripts() {
    log_info "Creazione script utili..."
    
    # Script per controllo sistema
    tee /opt/scripts/system-status.sh > /dev/null <<'EOF'
#!/bin/bash

echo "=== STATUS SISTEMA WMS ==="
echo "Data: $(date)"
echo

echo "--- SISTEMA ---"
uptime
df -h
free -h

echo
echo "--- DOCKER ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo
echo "--- SERVIZI ---"
systemctl status nginx --no-pager -l
systemctl status docker --no-pager -l

echo
echo "--- CONNESSIONI RETE ---"
ss -tuln | grep LISTEN

echo
echo "--- SPAZIO DISCO ---"
du -sh /opt/projects/*
EOF
    
    chmod +x /opt/scripts/system-status.sh
    
    log_success "Script utili creati"
}

# Main execution
main() {
    echo "=== SETUP SERVER WMS ==="
    echo "Iniziando setup automatico server per WMS deployment..."
    echo
    
    check_privileges
    check_system
    
    log_info "Setup in corso... Questo potrebbe richiedere alcuni minuti."
    
    update_system
    install_base_packages
    install_docker
    setup_firewall
    optimize_system
    setup_nginx
    create_directories
    setup_log_rotation
    setup_timezone
    install_monitoring_tools
    create_utility_scripts
    
    # Harden SSH per ultimo (potrebbe interrompere connessione)
    read -p "Vuoi applicare l'hardening SSH? ATTENZIONE: Configura prima le SSH keys! (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        harden_ssh
    else
        log_warning "Hardening SSH saltato. Configuralo manualmente per sicurezza!"
    fi
    
    echo
    echo "=== SETUP COMPLETATO ==="
    log_success "Server configurato con successo!"
    echo
    echo "Prossimi passi:"
    echo "1. Riavvia il server: sudo reboot"
    echo "2. Riconnettiti dopo il riboot"
    echo "3. Verifica Docker: docker --version"
    echo "4. Clona il progetto WMS in /opt/projects/"
    echo "5. Configura il progetto con docker compose"
    echo
    echo "Script utili creati in /opt/scripts/"
    echo "- system-status.sh: Controllo stato sistema"
    echo
    log_warning "IMPORTANTE: Se hai abilitato SSH hardening, testa la connessione SSH da un'altra finestra prima di disconnetterti!"
}

# Trap per cleanup in caso di errore
trap 'log_error "Setup interrotto. Controlla i log per dettagli."' ERR

# Esegui main
main "$@"