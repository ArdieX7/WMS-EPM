#!/bin/bash

# Script Backup Automatico WMS
# Versione: 1.0
# Data: 2024-08-29
# Descrizione: Backup completo database e file di progetto WMS

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configurazione
PROJECT_NAME="WMS_EPM"
PROJECT_DIR="/opt/projects/${PROJECT_NAME}"
BACKUP_DIR="/opt/backups"
LOG_FILE="/var/log/wms-backup.log"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Database configuration
DB_CONTAINER="${PROJECT_NAME}_db_1"  # Adjust if needed
DB_NAME="wms_db"
DB_USER="wms_user"
DB_PASSWORD=""  # Will be extracted from env

# Notification settings (optional)
SEND_NOTIFICATIONS=false
NOTIFICATION_EMAIL=""
WEBHOOK_URL=""  # Slack/Discord webhook

# Colori per log
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzioni helper
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_info() {
    log "[INFO] $1"
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    log "[SUCCESS] $1"
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    log "[WARNING] $1"
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    log "[ERROR] $1"
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verifica prerequisiti
check_prerequisites() {
    log_info "Verifica prerequisiti..."
    
    # Verifica directory progetto
    if [[ ! -d "$PROJECT_DIR" ]]; then
        log_error "Directory progetto non trovata: $PROJECT_DIR"
        exit 1
    fi
    
    # Verifica Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker non installato"
        exit 1
    fi
    
    # Verifica Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose non disponibile"
        exit 1
    fi
    
    # Crea directory backup se non esiste
    mkdir -p "$BACKUP_DIR"/{database,files,logs}
    
    log_success "Prerequisiti verificati"
}

# Estrai password database dal file .env
get_db_password() {
    local env_file="${PROJECT_DIR}/.env"
    if [[ -f "$env_file" ]]; then
        DB_PASSWORD=$(grep "DATABASE_URL" "$env_file" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    fi
    
    if [[ -z "$DB_PASSWORD" ]]; then
        log_warning "Password database non trovata in .env, uso variabili d'ambiente Docker"
    fi
}

# Backup database PostgreSQL
backup_database() {
    log_info "Avvio backup database..."
    
    local backup_file="${BACKUP_DIR}/database/wms_db_${TIMESTAMP}.sql"
    local container_name=""
    
    # Trova il nome del container database
    cd "$PROJECT_DIR"
    container_name=$(docker compose ps -q db 2>/dev/null)
    
    if [[ -z "$container_name" ]]; then
        log_error "Container database non trovato o non in esecuzione"
        return 1
    fi
    
    # Esegui backup
    if docker exec "$container_name" pg_dump -U "$DB_USER" -d "$DB_NAME" > "$backup_file"; then
        # Comprimi backup
        gzip "$backup_file"
        
        local size=$(du -h "${backup_file}.gz" | cut -f1)
        log_success "Backup database completato: ${backup_file}.gz (${size})"
        
        # Verifica integrità backup
        if zcat "${backup_file}.gz" | head -20 | grep -q "PostgreSQL database dump"; then
            log_success "Backup database verificato"
        else
            log_error "Backup database corrotto!"
            return 1
        fi
    else
        log_error "Errore durante backup database"
        return 1
    fi
}

# Backup file di progetto
backup_project_files() {
    log_info "Avvio backup file progetto..."
    
    local backup_file="${BACKUP_DIR}/files/wms_project_${TIMESTAMP}.tar.gz"
    
    # Lista directory/file da includere nel backup
    local include_paths=(
        "wms_app/"
        "scripts/"
        "requirements.txt"
        "docker-compose.yml"
        "Dockerfile"
        ".env"
        "nginx.conf"
        "nginx-production.conf"
        "deploy_guide_vps.md"
    )
    
    # Lista directory/file da escludere
    local exclude_patterns=(
        "--exclude=__pycache__"
        "--exclude=*.pyc"
        "--exclude=*.pyo"
        "--exclude=.git"
        "--exclude=venv"
        "--exclude=venv_new"
        "--exclude=*.log"
        "--exclude=wms.db"  # Database SQLite se presente
        "--exclude=*.swp"
        "--exclude=*.tmp"
        "--exclude=node_modules"
    )
    
    cd "$PROJECT_DIR"
    
    # Crea archivio tar.gz
    if tar -czf "$backup_file" "${exclude_patterns[@]}" "${include_paths[@]}" 2>/dev/null; then
        local size=$(du -h "$backup_file" | cut -f1)
        log_success "Backup file progetto completato: ${backup_file} (${size})"
    else
        log_error "Errore durante backup file progetto"
        return 1
    fi
}

# Backup configurazioni sistema
backup_system_configs() {
    log_info "Backup configurazioni sistema..."
    
    local backup_file="${BACKUP_DIR}/files/system_configs_${TIMESTAMP}.tar.gz"
    local config_paths=()
    
    # Aggiungi percorsi se esistono
    [[ -f "/etc/nginx/sites-available/wms" ]] && config_paths+=("/etc/nginx/sites-available/wms")
    [[ -f "/etc/nginx/sites-available/wms-production" ]] && config_paths+=("/etc/nginx/sites-available/wms-production")
    [[ -d "/etc/letsencrypt/live" ]] && config_paths+=("/etc/letsencrypt/live")
    [[ -f "/etc/crontab" ]] && config_paths+=("/etc/crontab")
    
    if [[ ${#config_paths[@]} -gt 0 ]]; then
        if sudo tar -czf "$backup_file" "${config_paths[@]}" 2>/dev/null; then
            local size=$(du -h "$backup_file" | cut -f1)
            log_success "Backup configurazioni sistema: ${backup_file} (${size})"
        else
            log_warning "Errore backup configurazioni sistema"
        fi
    else
        log_info "Nessuna configurazione sistema da salvare"
    fi
}

# Backup logs applicazione
backup_logs() {
    log_info "Backup logs applicazione..."
    
    local backup_file="${BACKUP_DIR}/logs/wms_logs_${TIMESTAMP}.tar.gz"
    local log_paths=()
    
    # Aggiungi percorsi log se esistono
    [[ -f "/var/log/nginx/wms_access.log" ]] && log_paths+=("/var/log/nginx/wms_access.log")
    [[ -f "/var/log/nginx/wms_error.log" ]] && log_paths+=("/var/log/nginx/wms_error.log")
    [[ -f "${PROJECT_DIR}/server.log" ]] && log_paths+=("${PROJECT_DIR}/server.log")
    [[ -f "$LOG_FILE" ]] && log_paths+=("$LOG_FILE")
    
    # Logs Docker
    cd "$PROJECT_DIR"
    docker compose logs --no-color > "${BACKUP_DIR}/logs/docker_logs_${TIMESTAMP}.log" 2>/dev/null || true
    log_paths+=("${BACKUP_DIR}/logs/docker_logs_${TIMESTAMP}.log")
    
    if [[ ${#log_paths[@]} -gt 0 ]]; then
        if tar -czf "$backup_file" "${log_paths[@]}" 2>/dev/null; then
            local size=$(du -h "$backup_file" | cut -f1)
            log_success "Backup logs: ${backup_file} (${size})"
            
            # Rimuovi log temporaneo
            rm -f "${BACKUP_DIR}/logs/docker_logs_${TIMESTAMP}.log"
        else
            log_warning "Errore backup logs"
        fi
    fi
}

# Pulizia backup vecchi
cleanup_old_backups() {
    log_info "Pulizia backup vecchi (>$RETENTION_DAYS giorni)..."
    
    local deleted_count=0
    
    # Pulizia per ogni directory
    for dir in database files logs; do
        local backup_path="${BACKUP_DIR}/${dir}"
        if [[ -d "$backup_path" ]]; then
            while IFS= read -r -d '' file; do
                rm -f "$file"
                ((deleted_count++))
            done < <(find "$backup_path" -name "*" -type f -mtime +$RETENTION_DAYS -print0)
        fi
    done
    
    if [[ $deleted_count -gt 0 ]]; then
        log_success "Rimossi $deleted_count backup vecchi"
    else
        log_info "Nessun backup vecchio da rimuovere"
    fi
}

# Verifica spazio disco
check_disk_space() {
    log_info "Verifica spazio disco..."
    
    local backup_disk_usage=$(df "$BACKUP_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    local root_disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [[ $backup_disk_usage -gt 85 ]]; then
        log_warning "Spazio backup quasi esaurito: ${backup_disk_usage}%"
    fi
    
    if [[ $root_disk_usage -gt 90 ]]; then
        log_error "Spazio disco critico: ${root_disk_usage}%"
        return 1
    fi
    
    log_info "Spazio disco OK - Root: ${root_disk_usage}%, Backup: ${backup_disk_usage}%"
}

# Invia notifiche (opzionale)
send_notifications() {
    local status="$1"
    local message="$2"
    
    if [[ "$SEND_NOTIFICATIONS" != "true" ]]; then
        return 0
    fi
    
    # Email notification
    if [[ -n "$NOTIFICATION_EMAIL" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "WMS Backup $status" "$NOTIFICATION_EMAIL"
    fi
    
    # Webhook notification (Slack/Discord)
    if [[ -n "$WEBHOOK_URL" ]]; then
        local color="good"
        [[ "$status" == "FAILED" ]] && color="danger"
        
        curl -X POST "$WEBHOOK_URL" \
            -H 'Content-type: application/json' \
            --data "{\"color\":\"$color\",\"text\":\"WMS Backup $status: $message\"}" \
            &>/dev/null || true
    fi
}

# Report finale backup
generate_backup_report() {
    log_info "Generazione report backup..."
    
    local report_file="${BACKUP_DIR}/backup_report_${TIMESTAMP}.txt"
    
    cat > "$report_file" <<EOF
WMS BACKUP REPORT
================
Data: $(date)
Timestamp: $TIMESTAMP

BACKUP EFFETTUATI:
EOF
    
    # Aggiungi dettagli backup database
    local db_backup="${BACKUP_DIR}/database/wms_db_${TIMESTAMP}.sql.gz"
    if [[ -f "$db_backup" ]]; then
        echo "- Database: $(basename "$db_backup") ($(du -h "$db_backup" | cut -f1))" >> "$report_file"
    fi
    
    # Aggiungi dettagli backup file
    local files_backup="${BACKUP_DIR}/files/wms_project_${TIMESTAMP}.tar.gz"
    if [[ -f "$files_backup" ]]; then
        echo "- File progetto: $(basename "$files_backup") ($(du -h "$files_backup" | cut -f1))" >> "$report_file"
    fi
    
    # Aggiungi utilizzo spazio
    echo "" >> "$report_file"
    echo "UTILIZZO SPAZIO:" >> "$report_file"
    du -sh "${BACKUP_DIR}/"* >> "$report_file"
    
    echo "" >> "$report_file"
    echo "SPAZIO DISCO:" >> "$report_file"
    df -h / >> "$report_file"
    
    log_success "Report generato: $report_file"
}

# Funzione main
main() {
    log_info "=== AVVIO BACKUP WMS ==="
    log_info "Timestamp: $TIMESTAMP"
    
    local backup_success=true
    local error_messages=()
    
    # Esegui backup step by step
    check_prerequisites || { backup_success=false; error_messages+=("Prerequisiti falliti"); }
    
    if [[ "$backup_success" == "true" ]]; then
        get_db_password
        
        backup_database || { backup_success=false; error_messages+=("Backup database fallito"); }
        backup_project_files || { backup_success=false; error_messages+=("Backup file fallito"); }
        backup_system_configs || true  # Non bloccante
        backup_logs || true  # Non bloccante
        
        if [[ "$backup_success" == "true" ]]; then
            cleanup_old_backups || true  # Non bloccante
            check_disk_space || { backup_success=false; error_messages+=("Spazio disco critico"); }
            generate_backup_report || true  # Non bloccante
        fi
    fi
    
    # Report finale
    if [[ "$backup_success" == "true" ]]; then
        log_success "=== BACKUP COMPLETATO CON SUCCESSO ==="
        send_notifications "SUCCESS" "Backup WMS completato con successo - $TIMESTAMP"
        exit 0
    else
        local error_msg="Errori: ${error_messages[*]}"
        log_error "=== BACKUP FALLITO ==="
        log_error "$error_msg"
        send_notifications "FAILED" "$error_msg"
        exit 1
    fi
}

# Trap per cleanup in caso di interruzione
trap 'log_error "Backup interrotto!"; exit 1' INT TERM

# Esegui main se script chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Crea log file se non esiste
    sudo touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/tmp/wms-backup.log"
    
    main "$@"
fi