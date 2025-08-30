#!/bin/bash

# Script Monitoraggio WMS
# Versione: 1.0
# Data: 2024-08-29
# Descrizione: Monitoraggio completo dello stato del sistema WMS

set -u  # Exit on undefined variable

# Configurazione
PROJECT_NAME="WMS_EPM"
PROJECT_DIR="/opt/projects/${PROJECT_NAME}"
LOG_FILE="/var/log/wms-monitor.log"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85
ALERT_THRESHOLD_DISK=90
ALERT_THRESHOLD_LOAD=4.0

# Notification settings
SEND_ALERTS=false
ALERT_EMAIL=""
WEBHOOK_URL=""

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Funzioni helper
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

print_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN} $1 ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
}

print_status() {
    local status="$1"
    local message="$2"
    case $status in
        "OK")
            echo -e "${GREEN}✓ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠ $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}✗ $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ $message${NC}"
            ;;
    esac
}

# Funzione per inviare alert
send_alert() {
    local priority="$1"
    local message="$2"
    
    if [[ "$SEND_ALERTS" != "true" ]]; then
        return 0
    fi
    
    # Log alert
    log "[ALERT-$priority] $message"
    
    # Email alert
    if [[ -n "$ALERT_EMAIL" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "WMS Alert [$priority]" "$ALERT_EMAIL"
    fi
    
    # Webhook alert (Slack/Discord)
    if [[ -n "$WEBHOOK_URL" ]]; then
        local color="warning"
        [[ "$priority" == "CRITICAL" ]] && color="danger"
        [[ "$priority" == "OK" ]] && color="good"
        
        curl -X POST "$WEBHOOK_URL" \
            -H 'Content-type: application/json' \
            --data "{\"color\":\"$color\",\"text\":\"WMS Monitor [$priority]: $message\"}" \
            &>/dev/null || true
    fi
}

# Controlla se script è già in esecuzione
check_lock() {
    local lockfile="/tmp/wms-monitor.lock"
    
    if [[ -f "$lockfile" ]]; then
        local pid=$(cat "$lockfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Script già in esecuzione (PID: $pid)"
            exit 1
        else
            rm -f "$lockfile"
        fi
    fi
    
    echo $$ > "$lockfile"
    trap "rm -f $lockfile" EXIT
}

# Controlla stato sistema generale
check_system_health() {
    print_header "STATO SISTEMA"
    
    local alerts=()
    
    # Uptime
    local uptime_info=$(uptime | awk -F',' '{print $1}')
    print_status "INFO" "Sistema: $uptime_info"
    
    # Load average
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    if (( $(echo "$load_avg > $ALERT_THRESHOLD_LOAD" | bc -l) )); then
        print_status "WARNING" "Load Average: $load_avg (soglia: $ALERT_THRESHOLD_LOAD)"
        alerts+=("High Load Average: $load_avg")
    else
        print_status "OK" "Load Average: $load_avg"
    fi
    
    # CPU Usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    cpu_usage=${cpu_usage%.*}  # Remove decimal part
    if [[ $cpu_usage -gt $ALERT_THRESHOLD_CPU ]]; then
        print_status "WARNING" "CPU Usage: ${cpu_usage}% (soglia: $ALERT_THRESHOLD_CPU%)"
        alerts+=("High CPU Usage: ${cpu_usage}%")
    else
        print_status "OK" "CPU Usage: ${cpu_usage}%"
    fi
    
    # Memory Usage
    local mem_info=$(free | grep Mem)
    local mem_total=$(echo $mem_info | awk '{print $2}')
    local mem_used=$(echo $mem_info | awk '{print $3}')
    local mem_percent=$(( (mem_used * 100) / mem_total ))
    
    if [[ $mem_percent -gt $ALERT_THRESHOLD_MEMORY ]]; then
        print_status "WARNING" "Memory Usage: ${mem_percent}% (soglia: $ALERT_THRESHOLD_MEMORY%)"
        alerts+=("High Memory Usage: ${mem_percent}%")
    else
        print_status "OK" "Memory Usage: ${mem_percent}%"
    fi
    
    # Disk Usage
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt $ALERT_THRESHOLD_DISK ]]; then
        print_status "ERROR" "Disk Usage: ${disk_usage}% (soglia: $ALERT_THRESHOLD_DISK%)"
        alerts+=("Critical Disk Usage: ${disk_usage}%")
    else
        print_status "OK" "Disk Usage: ${disk_usage}%"
    fi
    
    # Invia alert se necessario
    if [[ ${#alerts[@]} -gt 0 ]]; then
        local alert_message="Sistema WMS - Alert: ${alerts[*]}"
        send_alert "WARNING" "$alert_message"
    fi
}

# Controlla stato Docker
check_docker_status() {
    print_header "STATO DOCKER"
    
    # Docker daemon
    if systemctl is-active --quiet docker; then
        print_status "OK" "Docker daemon: Running"
    else
        print_status "ERROR" "Docker daemon: Not running"
        send_alert "CRITICAL" "Docker daemon non attivo"
        return 1
    fi
    
    # Docker containers
    if [[ -d "$PROJECT_DIR" ]]; then
        cd "$PROJECT_DIR"
        
        # Container status
        local containers=$(docker compose ps -q 2>/dev/null)
        if [[ -z "$containers" ]]; then
            print_status "ERROR" "Nessun container WMS trovato"
            send_alert "CRITICAL" "Container WMS non trovati"
            return 1
        fi
        
        # Check each container
        while read -r container_id; do
            if [[ -n "$container_id" ]]; then
                local container_name=$(docker inspect --format='{{.Name}}' "$container_id" | sed 's/\///')
                local container_status=$(docker inspect --format='{{.State.Status}}' "$container_id")
                local container_health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container_id")
                
                if [[ "$container_status" == "running" ]]; then
                    if [[ "$container_health" == "healthy" ]] || [[ "$container_health" == "no-healthcheck" ]]; then
                        print_status "OK" "Container $container_name: $container_status ($container_health)"
                    else
                        print_status "WARNING" "Container $container_name: $container_status ($container_health)"
                        send_alert "WARNING" "Container $container_name unhealthy"
                    fi
                else
                    print_status "ERROR" "Container $container_name: $container_status"
                    send_alert "CRITICAL" "Container $container_name not running"
                fi
            fi
        done <<< "$containers"
        
        # Docker resource usage
        local docker_stats=$(docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null)
        if [[ -n "$docker_stats" ]]; then
            echo -e "\n${BLUE}Resource Usage:${NC}"
            echo "$docker_stats"
        fi
    else
        print_status "ERROR" "Directory progetto non trovata: $PROJECT_DIR"
        return 1
    fi
}

# Controlla connettività database
check_database() {
    print_header "STATO DATABASE"
    
    if [[ -d "$PROJECT_DIR" ]]; then
        cd "$PROJECT_DIR"
        
        # Test connessione PostgreSQL
        local db_container=$(docker compose ps -q db 2>/dev/null)
        if [[ -n "$db_container" ]]; then
            if docker exec "$db_container" pg_isready -U wms_user -d wms_db &>/dev/null; then
                print_status "OK" "Database PostgreSQL: Connesso"
                
                # Statistiche database
                local db_size=$(docker exec "$db_container" psql -U wms_user -d wms_db -t -c "SELECT pg_size_pretty(pg_database_size('wms_db'));" 2>/dev/null | xargs)
                print_status "INFO" "Dimensione database: $db_size"
                
                # Numero connessioni attive
                local active_connections=$(docker exec "$db_container" psql -U wms_user -d wms_db -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | xargs)
                print_status "INFO" "Connessioni attive: $active_connections"
                
            else
                print_status "ERROR" "Database PostgreSQL: Non raggiungibile"
                send_alert "CRITICAL" "Database PostgreSQL non raggiungibile"
            fi
        else
            print_status "ERROR" "Container database non trovato"
            send_alert "CRITICAL" "Container database non trovato"
        fi
    fi
}

# Controlla stato Nginx
check_nginx() {
    print_header "STATO NGINX"
    
    if systemctl is-active --quiet nginx; then
        print_status "OK" "Nginx: Running"
        
        # Test configurazione
        if nginx -t &>/dev/null; then
            print_status "OK" "Nginx configurazione: Valid"
        else
            print_status "ERROR" "Nginx configurazione: Invalid"
            send_alert "WARNING" "Nginx configurazione non valida"
        fi
        
        # Controlla porte in ascolto
        local nginx_ports=$(ss -tlnp | grep nginx | awk '{print $4}' | cut -d: -f2 | sort -u | tr '\n' ' ')
        print_status "INFO" "Nginx porte: $nginx_ports"
        
    else
        print_status "ERROR" "Nginx: Not running"
        send_alert "CRITICAL" "Nginx non attivo"
    fi
}

# Controlla connettività WMS
check_wms_connectivity() {
    print_header "CONNETTIVITÀ WMS"
    
    local wms_endpoints=(
        "http://localhost:8000/health"
        "http://localhost:8000/"
    )
    
    for endpoint in "${wms_endpoints[@]}"; do
        if curl -f -s --max-time 10 "$endpoint" >/dev/null; then
            print_status "OK" "Endpoint $endpoint: Raggiungibile"
        else
            print_status "ERROR" "Endpoint $endpoint: Non raggiungibile"
            send_alert "WARNING" "Endpoint WMS $endpoint non raggiungibile"
        fi
    done
    
    # Test risposta nginx (se configurato)
    if systemctl is-active --quiet nginx; then
        if curl -f -s --max-time 10 "http://localhost/health" >/dev/null; then
            print_status "OK" "Nginx proxy: Funzionante"
        else
            print_status "WARNING" "Nginx proxy: Non raggiungibile"
        fi
    fi
}

# Controlla spazio disco dettagliato
check_disk_space() {
    print_header "UTILIZZO DISCO"
    
    # Spazio generale
    df -h | while read filesystem size used avail percent mountpoint; do
        if [[ "$filesystem" != "Filesystem" ]] && [[ "$mountpoint" =~ ^/|^/opt|^/var ]]; then
            local usage_num=$(echo $percent | sed 's/%//')
            if [[ $usage_num -gt $ALERT_THRESHOLD_DISK ]]; then
                print_status "ERROR" "$mountpoint: $percent utilizzato ($used/$size)"
            elif [[ $usage_num -gt 75 ]]; then
                print_status "WARNING" "$mountpoint: $percent utilizzato ($used/$size)"
            else
                print_status "OK" "$mountpoint: $percent utilizzato ($used/$size)"
            fi
        fi
    done
    
    # Spazio directory progetto
    if [[ -d "$PROJECT_DIR" ]]; then
        local project_size=$(du -sh "$PROJECT_DIR" 2>/dev/null | cut -f1)
        print_status "INFO" "Dimensione progetto WMS: $project_size"
    fi
    
    # Spazio Docker
    local docker_size=$(docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>/dev/null)
    if [[ -n "$docker_size" ]]; then
        echo -e "\n${BLUE}Docker Space Usage:${NC}"
        echo "$docker_size"
    fi
}

# Controlla log per errori
check_logs() {
    print_header "ANALISI LOG"
    
    local error_count=0
    local warning_count=0
    
    # Log applicazione WMS
    if [[ -d "$PROJECT_DIR" ]]; then
        cd "$PROJECT_DIR"
        
        # Docker logs
        local recent_errors=$(docker compose logs --tail=100 web 2>/dev/null | grep -i "error\|exception\|traceback" | wc -l)
        local recent_warnings=$(docker compose logs --tail=100 web 2>/dev/null | grep -i "warning\|warn" | wc -l)
        
        if [[ $recent_errors -gt 0 ]]; then
            print_status "WARNING" "Errori recenti applicazione: $recent_errors"
            error_count=$((error_count + recent_errors))
        else
            print_status "OK" "Nessun errore recente applicazione"
        fi
        
        if [[ $recent_warnings -gt 0 ]]; then
            print_status "INFO" "Warning recenti applicazione: $recent_warnings"
            warning_count=$((warning_count + recent_warnings))
        fi
    fi
    
    # Log Nginx
    if [[ -f "/var/log/nginx/error.log" ]]; then
        local nginx_errors=$(tail -100 /var/log/nginx/error.log | grep "$(date +'%Y/%m/%d')" | wc -l)
        if [[ $nginx_errors -gt 0 ]]; then
            print_status "WARNING" "Errori Nginx oggi: $nginx_errors"
            error_count=$((error_count + nginx_errors))
        else
            print_status "OK" "Nessun errore Nginx oggi"
        fi
    fi
    
    # Alert se troppi errori
    if [[ $error_count -gt 10 ]]; then
        send_alert "WARNING" "Molti errori rilevati nei log: $error_count"
    fi
}

# Controlla sicurezza base
check_security() {
    print_header "CONTROLLI SICUREZZA"
    
    # Firewall status
    if ufw status | grep -q "Status: active"; then
        print_status "OK" "UFW Firewall: Attivo"
    else
        print_status "WARNING" "UFW Firewall: Inattivo"
        send_alert "WARNING" "Firewall UFW non attivo"
    fi
    
    # SSH configuration
    if [[ -f "/etc/ssh/sshd_config" ]]; then
        local root_login=$(grep "^PermitRootLogin" /etc/ssh/sshd_config | awk '{print $2}')
        if [[ "$root_login" == "no" ]]; then
            print_status "OK" "SSH Root Login: Disabilitato"
        else
            print_status "WARNING" "SSH Root Login: Abilitato"
        fi
        
        local password_auth=$(grep "^PasswordAuthentication" /etc/ssh/sshd_config | awk '{print $2}')
        if [[ "$password_auth" == "no" ]]; then
            print_status "OK" "SSH Password Auth: Disabilitato"
        else
            print_status "WARNING" "SSH Password Auth: Abilitato"
        fi
    fi
    
    # Check per tentativi di accesso
    local failed_ssh=$(journalctl --since "24 hours ago" | grep "Failed password" | wc -l)
    if [[ $failed_ssh -gt 20 ]]; then
        print_status "WARNING" "Tentativi SSH falliti (24h): $failed_ssh"
        send_alert "WARNING" "Molti tentativi SSH falliti: $failed_ssh"
    else
        print_status "OK" "Tentativi SSH falliti (24h): $failed_ssh"
    fi
}

# Report riassuntivo
generate_summary() {
    print_header "RIASSUNTO MONITORAGGIO"
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}Report generato: $timestamp${NC}"
    
    # Status generale
    local overall_status="OK"
    local issues=()
    
    # Controlla se ci sono problemi critici
    if ! systemctl is-active --quiet docker; then
        overall_status="CRITICAL"
        issues+=("Docker non attivo")
    fi
    
    if ! systemctl is-active --quiet nginx; then
        overall_status="WARNING"
        issues+=("Nginx non attivo")
    fi
    
    # Spazio disco critico
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt $ALERT_THRESHOLD_DISK ]]; then
        overall_status="CRITICAL"
        issues+=("Spazio disco critico: ${disk_usage}%")
    fi
    
    # Mostra status finale
    case $overall_status in
        "OK")
            print_status "OK" "Sistema WMS: Tutto funzionante"
            ;;
        "WARNING")
            print_status "WARNING" "Sistema WMS: Problemi minori rilevati"
            send_alert "WARNING" "Monitoraggio WMS - Problemi: ${issues[*]}"
            ;;
        "CRITICAL")
            print_status "ERROR" "Sistema WMS: Problemi critici rilevati"
            send_alert "CRITICAL" "Monitoraggio WMS - Problemi critici: ${issues[*]}"
            ;;
    esac
    
    # Suggerimenti
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo -e "\n${YELLOW}Azioni consigliate:${NC}"
        for issue in "${issues[@]}"; do
            echo -e "${YELLOW}- Risolvi: $issue${NC}"
        done
    fi
    
    echo -e "\n${CYAN}Per dettagli completi: tail -f $LOG_FILE${NC}"
}

# Menu interattivo
show_menu() {
    clear
    echo -e "${PURPLE}WMS Monitoring System${NC}"
    echo -e "${PURPLE}=====================${NC}"
    echo
    echo "1) Status Completo"
    echo "2) Solo Sistema"
    echo "3) Solo Docker"
    echo "4) Solo Database"  
    echo "5) Solo Nginx"
    echo "6) Solo Connettività"
    echo "7) Solo Spazio Disco"
    echo "8) Solo Log"
    echo "9) Solo Sicurezza"
    echo "q) Quit"
    echo
    read -p "Scegli opzione: " choice
    
    case $choice in
        1) run_full_check ;;
        2) check_system_health ;;
        3) check_docker_status ;;
        4) check_database ;;
        5) check_nginx ;;
        6) check_wms_connectivity ;;
        7) check_disk_space ;;
        8) check_logs ;;
        9) check_security ;;
        q|Q) exit 0 ;;
        *) echo "Opzione non valida"; sleep 1; show_menu ;;
    esac
}

# Controllo completo
run_full_check() {
    echo -e "${PURPLE}WMS MONITORING REPORT${NC}"
    echo -e "${PURPLE}$(date)${NC}"
    
    check_system_health
    check_docker_status
    check_database
    check_nginx
    check_wms_connectivity
    check_disk_space
    check_logs
    check_security
    generate_summary
}

# Main function
main() {
    # Crea log file se non esiste
    sudo touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/tmp/wms-monitor.log"
    
    check_lock
    
    case "${1:-}" in
        "--full"|"-f")
            run_full_check
            ;;
        "--system"|"-s")
            check_system_health
            ;;
        "--docker"|"-d")
            check_docker_status
            ;;
        "--database"|"--db")
            check_database
            ;;
        "--nginx"|"-n")
            check_nginx
            ;;
        "--connectivity"|"-c")
            check_wms_connectivity
            ;;
        "--disk")
            check_disk_space
            ;;
        "--logs"|"-l")
            check_logs
            ;;
        "--security")
            check_security
            ;;
        "--help"|"-h")
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -f, --full          Controllo completo"
            echo "  -s, --system        Solo sistema"
            echo "  -d, --docker        Solo Docker"
            echo "      --db            Solo database"
            echo "  -n, --nginx         Solo Nginx"
            echo "  -c, --connectivity  Solo connettività"
            echo "      --disk          Solo spazio disco"
            echo "  -l, --logs          Solo analisi log"
            echo "      --security      Solo sicurezza"
            echo "  -h, --help          Mostra questo help"
            echo
            echo "Senza parametri: Menu interattivo"
            ;;
        "")
            show_menu
            ;;
        *)
            echo "Opzione non valida: $1"
            echo "Usa --help per vedere le opzioni disponibili"
            exit 1
            ;;
    esac
}

# Esegui main
main "$@"