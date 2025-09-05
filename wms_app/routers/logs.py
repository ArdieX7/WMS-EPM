from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import csv
import io

from wms_app.database import get_db
from wms_app.routers.auth import require_permission
from wms_app.services.logging_service import LoggingService
from wms_app.models.logs import OperationType, OperationCategory, OperationStatus
from fastapi.templating import Jinja2Templates

# Helper function per generare tutti i tipi di operazione
def get_all_operation_types():
    """Genera automaticamente tutti i tipi di operazione disponibili."""
    types = []
    
    # Usa reflection per ottenere tutti i tipi da OperationType
    for attr_name in dir(OperationType):
        if not attr_name.startswith('_'):
            value = getattr(OperationType, attr_name)
            if isinstance(value, str):
                # Crea label leggibile dal nome della costante
                label = attr_name.replace('_', ' ').title()
                types.append({"value": value, "label": label})
    
    # Ordina per label per una migliore UX
    types.sort(key=lambda x: x["label"])
    return types

def get_grouped_operation_types():
    """Genera tipi di operazione raggruppati in macro-categorie gerarchiche."""
    return {
        "carico": {
            "label": "📦 Carico",
            "operations": [
                {"value": OperationType.CARICO_MANUALE, "label": "Carico Manuale"},
                {"value": OperationType.CARICO_FILE, "label": "Carico File"},
                {"value": OperationType.SCARICO_CONTAINER_MANUALE, "label": "Scarico Container Manuale"},
                {"value": OperationType.SCARICO_CONTAINER_FILE, "label": "Scarico Container File"}
            ]
        },
        "scarico": {
            "label": "📤 Scarico", 
            "operations": [
                {"value": OperationType.SCARICO_MANUALE, "label": "Scarico Manuale"},
                {"value": OperationType.SCARICO_FILE, "label": "Scarico File"}
            ]
        },
        "movimenti": {
            "label": "🔄 Movimenti",
            "operations": [
                {"value": OperationType.SPOSTAMENTO_MANUALE, "label": "Spostamento Manuale"},
                {"value": OperationType.SPOSTAMENTO_FILE, "label": "Spostamento File"},
                {"value": OperationType.UBICAZIONE_DA_TERRA_MANUALE, "label": "Ubicazione Da Terra Manuale"},
                {"value": OperationType.UBICAZIONE_DA_TERRA_FILE, "label": "Ubicazione Da Terra File"},
                {"value": OperationType.RIALLINEAMENTO_MANUALE, "label": "Riallineamento Manuale"},
                {"value": OperationType.RIALLINEAMENTO_FILE, "label": "Riallineamento File"},
                {"value": OperationType.CONSOLIDAMENTO_TERRA, "label": "Consolidamento Terra"}
            ]
        },
        "prelievo": {
            "label": "🛒 Prelievo",
            "operations": [
                {"value": OperationType.PRELIEVO_FILE, "label": "Prelievo File"},
                {"value": OperationType.PRELIEVO_MANUALE, "label": "Prelievo Manuale"},
                {"value": OperationType.PRELIEVO_TEMPO_REALE, "label": "Prelievo Tempo Reale"},
                {"value": OperationType.PICKING_GENERATO, "label": "Picking Generato"},
                {"value": OperationType.PICKING_CONFERMATO, "label": "Picking Confermato"}
            ]
        },
        "ordini": {
            "label": "📋 Ordini",
            "operations": [
                {"value": OperationType.ORDINE_CREATO, "label": "Ordine Creato"},
                {"value": OperationType.ORDINE_MODIFICATO, "label": "Ordine Modificato"},
                {"value": OperationType.ORDINE_ELIMINATO, "label": "Ordine Eliminato"},
                {"value": OperationType.ORDINE_COMPLETATO, "label": "Ordine Completato"},
                {"value": OperationType.ORDINE_EVASO, "label": "Ordine Evaso"},
                {"value": OperationType.ORDINE_ANNULLATO, "label": "Ordine Annullato"}
            ]
        },
        "seriali": {
            "label": "🏷️ Seriali",
            "operations": [
                {"value": OperationType.SERIALI_ASSEGNATI, "label": "Seriali Assegnati"},
                {"value": OperationType.SERIALI_RIMOSSI, "label": "Seriali Rimossi"}
            ]
        },
        "ddt": {
            "label": "📄 DDT",
            "operations": [
                {"value": OperationType.DDT_CREATO, "label": "DDT Creato"},
                {"value": OperationType.DDT_MODIFICATO, "label": "DDT Modificato"},
                {"value": OperationType.DDT_FINALIZZATO, "label": "DDT Finalizzato"}
            ]
        },
        "prodotti": {
            "label": "📦 Prodotti",
            "operations": [
                {"value": OperationType.PRODOTTO_CREATO, "label": "Prodotto Creato"},
                {"value": OperationType.PRODOTTO_MODIFICATO, "label": "Prodotto Modificato"},
                {"value": OperationType.PRODOTTO_ELIMINATO, "label": "Prodotto Eliminato"}
            ]
        },
        "magazzino": {
            "label": "🏢 Magazzino",
            "operations": [
                {"value": OperationType.UBICAZIONE_CREATA, "label": "Ubicazione Creata"},
                {"value": OperationType.UBICAZIONE_MODIFICATA, "label": "Ubicazione Modificata"},
                {"value": OperationType.UBICAZIONE_ELIMINATA, "label": "Ubicazione Eliminata"}
            ]
        },
        "sistema": {
            "label": "⚙️ Sistema",
            "operations": [
                {"value": OperationType.SISTEMA_AVVIATO, "label": "Sistema Avviato"},
                {"value": OperationType.BACKUP_CREATO, "label": "Backup Creato"},
                {"value": OperationType.PULIZIA_DATABASE, "label": "Pulizia Database"}
            ]
        },
        "prenotazioni": {
            "label": "🔒 Prenotazioni",
            "operations": [
                {"value": OperationType.PRENOTAZIONE_CREATA, "label": "Prenotazione Creata"},
                {"value": OperationType.PRENOTAZIONE_SCADUTA, "label": "Prenotazione Scaduta"},
                {"value": OperationType.PRENOTAZIONE_COMPLETATA, "label": "Prenotazione Completata"},
                {"value": OperationType.PRENOTAZIONE_CANCELLATA, "label": "Prenotazione Cancellata"}
            ]
        }
    }

templates = Jinja2Templates(directory="wms_app/templates")

router = APIRouter(
    prefix="/logs",
    tags=["logs"],
)


@router.get("/dashboard", response_class=HTMLResponse)
async def logs_dashboard(request: Request): 
    """Pagina principale dashboard logs."""
    return templates.TemplateResponse(
        "logs.html", 
        {
            "request": request, 
            "active_page": "logs",
            "operation_types": get_all_operation_types(),
            "grouped_operation_types": get_grouped_operation_types(),
            "operation_categories": [
                {"value": OperationCategory.MANUAL, "label": "Manuale"},
                {"value": OperationCategory.FILE, "label": "Da File"},
                {"value": OperationCategory.PICKING, "label": "Picking"},
                {"value": OperationCategory.SYSTEM, "label": "Sistema"},
                {"value": OperationCategory.API, "label": "API"},
            ],
            "operation_statuses": [
                {"value": OperationStatus.SUCCESS, "label": "Successo"},
                {"value": OperationStatus.ERROR, "label": "Errore"},
                {"value": OperationStatus.WARNING, "label": "Warning"},
                {"value": OperationStatus.PARTIAL, "label": "Parziale"},
                {"value": OperationStatus.CANCELLED, "label": "Cancellato"},
            ]
        }
    )


@router.get("/data")
async def get_logs_data(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    operation_types: Optional[str] = Query(None),
    operation_categories: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    product_sku: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    search_text: Optional[str] = Query(None),
    order_number: Optional[str] = Query(None),
    order_by: str = Query("timestamp"),
    order_direction: str = Query("desc")
):
    """
    API per recuperare dati logs con filtri e paginazione.
    """
    logger = LoggingService(db)
    
    try:
        # Parsing date
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Parsing liste (arrivano come stringhe separate da virgola)
        operation_types_list = None
        if operation_types:
            operation_types_list = [t.strip() for t in operation_types.split(',') if t.strip()]
        
        operation_categories_list = None
        if operation_categories:
            operation_categories_list = [c.strip() for c in operation_categories.split(',') if c.strip()]
        
        statuses_list = None
        if statuses:
            statuses_list = [s.strip() for s in statuses.split(',') if s.strip()]
        
        # Calcola offset per paginazione
        offset = (page - 1) * page_size
        
        # Recupera logs
        result = logger.get_logs(
            limit=page_size,
            offset=offset,
            start_date=start_datetime,
            end_date=end_datetime,
            operation_types=operation_types_list,
            operation_categories=operation_categories_list,
            statuses=statuses_list,
            product_sku=product_sku,
            location=location,
            user_id=user_id,
            search_text=search_text,
            order_number=order_number,
            order_by=order_by,
            order_direction=order_direction
        )
        
        # Converti logs in formato JSON-serializable
        logs_data = []
        for log in result['logs']:
            # Estrai numero ordine usando la funzione helper
            order_number_extracted = LoggingService.extract_order_number(log.operation_type, log.details)
            
            log_dict = {
                'id': log.id,
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'operation_type': log.operation_type,
                'operation_category': log.operation_category,
                'status': log.status,
                'product_sku': log.product_sku,
                'location_from': log.location_from,
                'location_to': log.location_to,
                'quantity': log.quantity,
                'user_id': log.user_id,
                'order_number': order_number_extracted,
                'file_name': log.file_name,
                'file_line_number': log.file_line_number,
                'error_message': log.error_message,
                'warning_message': log.warning_message,
                'details': log.details,
                'execution_time_ms': log.execution_time_ms,
                'operation_id': log.operation_id
            }
            logs_data.append(log_dict)
        
        return {
            "logs": logs_data,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_pages": result['total_pages'],
                "total_count": result['total_count']
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero logs: {str(e)}")


@router.get("/statistics")
async def get_logs_statistics(
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=365)
):
    """
    API per statistiche logs dashboard.
    """
    logger = LoggingService(db)
    
    try:
        stats = logger.get_log_statistics(days=days)
        
        # Aggiunge informazioni addizionali
        stats['period_label'] = f"Ultimi {days} giorni"
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel calcolo statistiche: {str(e)}")


@router.get("/export")
async def export_logs_csv(
    db: Session = Depends(get_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    operation_types: Optional[str] = Query(None),
    operation_categories: Optional[str] = Query(None),
    statuses: Optional[str] = Query(None),
    product_sku: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    search_text: Optional[str] = Query(None),
    order_number: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=10000)
):
    """
    Esporta logs in formato CSV.
    """
    logger = LoggingService(db)
    
    try:
        # Parsing parametri (stesso logic dell'endpoint data)
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        operation_types_list = None
        if operation_types:
            operation_types_list = [t.strip() for t in operation_types.split(',') if t.strip()]
        
        operation_categories_list = None
        if operation_categories:
            operation_categories_list = [c.strip() for c in operation_categories.split(',') if c.strip()]
        
        statuses_list = None
        if statuses:
            statuses_list = [s.strip() for s in statuses.split(',') if s.strip()]
        
        # Recupera logs (senza paginazione per export)
        result = logger.get_logs(
            limit=limit,
            offset=0,
            start_date=start_datetime,
            end_date=end_datetime,
            operation_types=operation_types_list,
            operation_categories=operation_categories_list,
            statuses=statuses_list,
            product_sku=product_sku,
            location=location,
            user_id=user_id,
            search_text=search_text,
            order_number=order_number,
            order_by="timestamp",
            order_direction="desc"
        )
        
        # Crea CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow([
            'Timestamp',
            'Tipo Operazione', 
            'Categoria',
            'Status',
            'SKU Prodotto',
            'Da Ubicazione',
            'A Ubicazione', 
            'Quantità',
            'Utente',
            'Numero Ordine',
            'Nome File',
            'Riga File',
            'Messaggio Errore',
            'Messaggio Warning',
            'Tempo Esecuzione (ms)',
            'ID Operazione'
        ])
        
        # Dati CSV
        for log in result['logs']:
            # Estrai numero ordine usando la funzione helper
            order_number_extracted = LoggingService.extract_order_number(log.operation_type, log.details)
            
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.operation_type,
                log.operation_category,
                log.status,
                log.product_sku or '',
                log.location_from or '',
                log.location_to or '',
                log.quantity or '',
                log.user_id or '',
                order_number_extracted or '',
                log.file_name or '',
                log.file_line_number or '',
                log.error_message or '',
                log.warning_message or '',
                log.execution_time_ms or '',
                log.operation_id or ''
            ])
        
        # Prepara response
        csv_content = output.getvalue()
        output.close()
        
        # Nome file con timestamp
        export_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"wms_logs_export_{export_timestamp}.csv"
        
        return JSONResponse(
            content={
                "success": True,
                "filename": filename,
                "csv_data": csv_content,
                "total_records": len(result['logs']),
                "export_timestamp": export_timestamp
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nell'export CSV: {str(e)}")


@router.delete("/cleanup")
async def cleanup_old_logs(
    db: Session = Depends(get_db),
    days_to_keep: int = Query(90, ge=1, le=365)
):
    """
    Pulisce logs più vecchi del periodo specificato.
    """
    logger = LoggingService(db)
    
    try:
        deleted_count = logger.cleanup_old_logs(days_to_keep=days_to_keep)
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
            "cutoff_date": (datetime.utcnow() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nella pulizia logs: {str(e)}")


@router.get("/operation-types")
async def get_operation_types():
    """
    Ritorna lista di tutti i tipi di operazione disponibili.
    """
    types = []
    
    # Usa reflection per ottenere tutti i tipi da OperationType
    for attr_name in dir(OperationType):
        if not attr_name.startswith('_'):
            value = getattr(OperationType, attr_name)
            if isinstance(value, str):
                # Crea label leggibile dal nome della costante
                label = attr_name.replace('_', ' ').title()
                types.append({"value": value, "label": label})
    
    return {"operation_types": types}


@router.get("/recent")
async def get_recent_logs(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Recupera gli ultimi logs per dashboard widgets.
    """
    logger = LoggingService(db)
    
    try:
        result = logger.get_logs(
            limit=limit,
            offset=0,
            order_by="timestamp",
            order_direction="desc"
        )
        
        # Formatta per widget dashboard
        recent_logs = []
        for log in result['logs']:
            recent_logs.append({
                'timestamp': log.timestamp.strftime('%H:%M:%S'),
                'operation_type': log.operation_type,
                'status': log.status,
                'product_sku': log.product_sku,
                'location_display': f"{log.location_from or ''} → {log.location_to or ''}".strip(' →'),
                'user_id': log.user_id
            })
        
        return {"recent_logs": recent_logs}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero logs recenti: {str(e)}")


@router.get("/health")
async def logs_health_check(db: Session = Depends(get_db)):
    """
    Health check per il sistema di logging.
    """
    logger = LoggingService(db)
    
    try:
        # Test basic query
        result = logger.get_logs(limit=1)
        
        # Test statistics
        stats = logger.get_log_statistics(days=1)
        
        return {
            "status": "healthy",
            "total_logs": result['total_count'],
            "logs_today": stats['total_operations'],
            "service_version": "1.0.0"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "service_version": "1.0.0"
        }