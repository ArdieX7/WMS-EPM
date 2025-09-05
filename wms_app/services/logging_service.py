from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import time
import json
import traceback
import uuid

from wms_app.models.logs import OperationLog, OperationType, OperationCategory, OperationStatus
from wms_app.models import inventory as inventory_models


class LoggingService:
    def __init__(self, db: Session):
        self.db = db
        self.current_batch_id = None
        self.batch_operations = []
    
    def log_operation(
        self,
        operation_type: str,
        operation_category: str,
        status: str = OperationStatus.SUCCESS,
        product_sku: Optional[str] = None,
        location_from: Optional[str] = None,
        location_to: Optional[str] = None,
        quantity: Optional[int] = None,
        user_id: str = "system",
        session_id: Optional[str] = None,
        file_name: Optional[str] = None,
        file_line_number: Optional[int] = None,
        error_message: Optional[str] = None,
        warning_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        capture_inventory_snapshot: bool = False,
        execution_time_ms: Optional[int] = None,
        api_endpoint: Optional[str] = None,
        operation_id: Optional[str] = None
    ) -> str:
        """
        Registra una singola operazione nel log.
        
        Returns:
            str: L'operation_id dell'operazione registrata
        """
        try:
            # Genera operation_id se non fornito
            if not operation_id:
                operation_id = str(uuid.uuid4())
            
            # Cattura snapshot inventario se richiesto
            inventory_before = None
            inventory_after = None
            
            if capture_inventory_snapshot and (location_from or location_to):
                inventory_before = self._capture_inventory_snapshot(location_from, location_to, product_sku)
            
            # Crea entry log
            log_entry = OperationLog(
                operation_id=operation_id,
                operation_type=operation_type,
                operation_category=operation_category,
                status=status,
                product_sku=product_sku,
                location_from=location_from,
                location_to=location_to,
                quantity=quantity,
                user_id=user_id,
                session_id=session_id,
                file_name=file_name,
                file_line_number=file_line_number,
                error_message=error_message,
                warning_message=warning_message,
                details=details,
                inventory_before=inventory_before,
                inventory_after=inventory_after,
                execution_time_ms=execution_time_ms,
                api_endpoint=api_endpoint
            )
            
            self.db.add(log_entry)
            # Rimosso db.flush() che causava inconsistenze transazionali
            # L'operation_id è generato come UUID e non richiede flush
            
            return operation_id
            
        except Exception as e:
            # Logging failure non deve mai bloccare l'operazione principale
            print(f"ERRORE LOGGING: {str(e)}")
            return str(uuid.uuid4())  # Ritorna comunque un ID
    
    def start_batch_operation(self, batch_type: str, batch_size: int = 0) -> str:
        """
        Inizia una operazione batch e ritorna l'operation_id condiviso.
        """
        self.current_batch_id = str(uuid.uuid4())
        self.batch_operations = []
        
        # Log inizio batch
        self.log_operation(
            operation_type=f"{batch_type}_BATCH_START",
            operation_category=OperationCategory.SYSTEM,
            status=OperationStatus.SUCCESS,
            details={"batch_size": batch_size, "batch_type": batch_type},
            operation_id=self.current_batch_id
        )
        
        return self.current_batch_id
    
    def log_batch_operation(
        self,
        operation_type: str,
        operation_category: str,
        operations: List[Dict[str, Any]],
        file_name: Optional[str] = None,
        user_id: str = "system"
    ) -> str:
        """
        Registra multiple operazioni con lo stesso operation_id batch.
        """
        if not self.current_batch_id:
            self.current_batch_id = self.start_batch_operation("GENERIC", len(operations))
        
        try:
            for i, op in enumerate(operations):
                self.log_operation(
                    operation_type=operation_type,
                    operation_category=operation_category,
                    status=op.get('status', OperationStatus.SUCCESS),
                    product_sku=op.get('product_sku'),
                    location_from=op.get('location_from'),
                    location_to=op.get('location_to'),
                    quantity=op.get('quantity'),
                    user_id=user_id,
                    file_name=file_name,
                    file_line_number=op.get('line_number', i + 1),
                    error_message=op.get('error_message'),
                    warning_message=op.get('warning_message'),
                    details=op.get('details'),
                    operation_id=self.current_batch_id
                )
            
            # Log fine batch
            self.log_operation(
                operation_type=f"{operation_type}_BATCH_END",
                operation_category=OperationCategory.SYSTEM,
                status=OperationStatus.SUCCESS,
                details={"processed_operations": len(operations)},
                operation_id=self.current_batch_id
            )
            
            return self.current_batch_id
            
        except Exception as e:
            self.log_error(
                operation_type=f"{operation_type}_BATCH_FAILED",
                error=e,
                operation_category=operation_category,
                details={"attempted_operations": len(operations)},
                operation_id=self.current_batch_id
            )
            return self.current_batch_id
    
    def log_file_operations(
        self,
        operation_type: str,
        operation_category: OperationCategory,
        operations: List[Dict[str, Any]],
        file_name: Optional[str] = None,
        user_id: str = "file_user"
    ) -> str:
        """
        Registra multiple operazioni da file SENZA log di batch start/end.
        Usa un operation_id condiviso per raggruppare le operazioni.
        """
        # Genera un operation_id condiviso per tutte le operazioni del file
        shared_operation_id = str(uuid.uuid4())
        
        try:
            for i, op in enumerate(operations):
                self.log_operation(
                    operation_type=operation_type,
                    operation_category=operation_category,
                    status=op.get('status', OperationStatus.SUCCESS),
                    product_sku=op.get('product_sku'),
                    location_from=op.get('location_from'),
                    location_to=op.get('location_to'),
                    quantity=op.get('quantity'),
                    user_id=user_id,
                    file_name=file_name,
                    file_line_number=op.get('line_number', i + 1),
                    error_message=op.get('error_message'),
                    warning_message=op.get('warning_message'),
                    details=op.get('details'),
                    operation_id=shared_operation_id
                )
            
            return shared_operation_id
            
        except Exception as e:
            self.log_error(
                operation_type=f"{operation_type}_FAILED",
                error=e,
                operation_category=operation_category,
                details={"attempted_operations": len(operations), "file_name": file_name},
                operation_id=shared_operation_id
            )
            return shared_operation_id
    
    def log_error(
        self,
        operation_type: str,
        error: Union[Exception, str],
        operation_category: str = OperationCategory.SYSTEM,
        product_sku: Optional[str] = None,
        location_from: Optional[str] = None,
        location_to: Optional[str] = None,
        quantity: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        operation_id: Optional[str] = None,
        api_endpoint: Optional[str] = None
    ) -> str:
        """
        Registra un errore con stack trace completo.
        """
        error_message = str(error)
        error_details = details or {}
        
        # Aggiungi stack trace se è una Exception
        if isinstance(error, Exception):
            error_details['stack_trace'] = traceback.format_exc()
            error_details['error_type'] = type(error).__name__
        
        return self.log_operation(
            operation_type=operation_type,
            operation_category=operation_category,
            status=OperationStatus.ERROR,
            product_sku=product_sku,
            location_from=location_from,
            location_to=location_to,
            quantity=quantity,
            error_message=error_message,
            details=error_details,
            operation_id=operation_id,
            api_endpoint=api_endpoint
        )
    
    def log_warning(
        self,
        operation_type: str,
        warning_message: str,
        operation_category: str = OperationCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Registra un warning per operazioni che completano ma con problemi.
        """
        return self.log_operation(
            operation_type=operation_type,
            operation_category=operation_category,
            status=OperationStatus.WARNING,
            warning_message=warning_message,
            details=details,
            **kwargs
        )
    
    def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        operation_types: Optional[List[str]] = None,
        operation_categories: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        product_sku: Optional[str] = None,
        location: Optional[str] = None,
        user_id: Optional[str] = None,
        search_text: Optional[str] = None,
        order_number: Optional[str] = None,
        order_by: str = "timestamp",
        order_direction: str = "desc"
    ) -> Dict[str, Any]:
        """
        Recupera logs con filtri avanzati e paginazione.
        """
        query = self.db.query(OperationLog)
        
        # Filtri temporali
        if start_date:
            query = query.filter(OperationLog.timestamp >= start_date)
        if end_date:
            query = query.filter(OperationLog.timestamp <= end_date)
        
        # Filtri categoria e tipo
        if operation_types:
            query = query.filter(OperationLog.operation_type.in_(operation_types))
        if operation_categories:
            query = query.filter(OperationLog.operation_category.in_(operation_categories))
        if statuses:
            query = query.filter(OperationLog.status.in_(statuses))
        
        # Filtri prodotto e ubicazione
        if product_sku:
            query = query.filter(OperationLog.product_sku.ilike(f"%{product_sku}%"))
        if location:
            query = query.filter(
                or_(
                    OperationLog.location_from.ilike(f"%{location}%"),
                    OperationLog.location_to.ilike(f"%{location}%")
                )
            )
        if user_id:
            query = query.filter(OperationLog.user_id.ilike(f"%{user_id}%"))
        
        # Filtro numero ordine (cerca nel campo details JSON)
        if order_number:
            order_pattern = f"%{order_number}%"
            query = query.filter(OperationLog.details.ilike(order_pattern))
        
        # Ricerca testuale
        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.filter(
                or_(
                    OperationLog.product_sku.ilike(search_pattern),
                    OperationLog.location_from.ilike(search_pattern),
                    OperationLog.location_to.ilike(search_pattern),
                    OperationLog.error_message.ilike(search_pattern),
                    OperationLog.warning_message.ilike(search_pattern),
                    OperationLog.file_name.ilike(search_pattern)
                )
            )
        
        # Conteggio totale per paginazione
        total_count = query.count()
        
        # Ordinamento
        if hasattr(OperationLog, order_by):
            order_column = getattr(OperationLog, order_by)
            if order_direction.lower() == "desc":
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        
        # Paginazione
        logs = query.offset(offset).limit(limit).all()
        
        return {
            "logs": logs,
            "total_count": total_count,
            "page": (offset // limit) + 1,
            "page_size": limit,
            "total_pages": (total_count + limit - 1) // limit
        }
    
    @staticmethod
    def extract_order_number(operation_type: str, details: Optional[Union[str, Dict[str, Any]]]) -> Optional[str]:
        """
        Estrae il numero ordine dal campo details JSON per operazioni specifiche.
        
        Args:
            operation_type: Tipo di operazione
            details: JSON string contenente i dettagli dell'operazione
            
        Returns:
            str: Numero ordine se trovato, None altrimenti
        """
        # Lista delle operazioni che contengono numeri ordine
        order_related_operations = {
            OperationType.PRELIEVO_FILE,
            OperationType.PRELIEVO_MANUALE, 
            OperationType.PRELIEVO_TEMPO_REALE,
            OperationType.SERIALI_ASSEGNATI,
            OperationType.SERIALI_RIMOSSI,
            OperationType.ORDINE_EVASO,
            OperationType.ORDINE_ANNULLATO,
            OperationType.ORDINE_COMPLETATO,
            OperationType.ORDINE_CREATO
        }
        
        # Se non è un'operazione correlata agli ordini, ritorna None
        if operation_type not in order_related_operations:
            return None
            
        # Se details è vuoto, ritorna None
        if not details:
            return None
            
        try:
            # Se details è già un dict, usalo direttamente
            if isinstance(details, dict):
                details_json = details
            else:
                # Altrimenti prova a parsarlo come JSON string
                details_json = json.loads(details)
                
            order_number = details_json.get('order_number')
            
            if order_number is not None:
                return str(order_number)
                
        except (json.JSONDecodeError, AttributeError, TypeError):
            # Se il JSON non è valido o altri errori, ignora silenziosamente
            pass
            
        return None
    
    def get_log_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Calcola statistiche dei log per dashboard.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Totali per periodo
        total_operations = self.db.query(OperationLog).filter(
            OperationLog.timestamp >= start_date
        ).count()
        
        error_operations = self.db.query(OperationLog).filter(
            and_(
                OperationLog.timestamp >= start_date,
                OperationLog.status == OperationStatus.ERROR
            )
        ).count()
        
        warning_operations = self.db.query(OperationLog).filter(
            and_(
                OperationLog.timestamp >= start_date,
                OperationLog.status == OperationStatus.WARNING
            )
        ).count()
        
        # Operazioni per categoria
        category_stats = {}
        for category in [OperationCategory.MANUAL, OperationCategory.FILE, OperationCategory.PICKING, OperationCategory.SYSTEM]:
            count = self.db.query(OperationLog).filter(
                and_(
                    OperationLog.timestamp >= start_date,
                    OperationLog.operation_category == category
                )
            ).count()
            category_stats[category] = count
        
        # Ultime operazioni significative
        recent_operations = self.db.query(OperationLog).filter(
            OperationLog.timestamp >= start_date
        ).order_by(desc(OperationLog.timestamp)).limit(5).all()
        
        return {
            "period_days": days,
            "total_operations": total_operations,
            "error_operations": error_operations,
            "warning_operations": warning_operations,
            "success_rate": ((total_operations - error_operations) / total_operations * 100) if total_operations > 0 else 100,
            "category_stats": category_stats,
            "recent_operations": recent_operations
        }
    
    def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """
        Rimuove logs più vecchi del periodo specificato.
        
        Returns:
            int: Numero di logs rimossi
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = self.db.query(OperationLog).filter(
            OperationLog.timestamp < cutoff_date
        ).delete()
        
        self.db.commit()
        
        # Log dell'operazione di pulizia
        self.log_operation(
            operation_type=OperationType.PULIZIA_DATABASE,
            operation_category=OperationCategory.SYSTEM,
            status=OperationStatus.SUCCESS,
            details={
                "logs_removed": deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
                "days_kept": days_to_keep
            }
        )
        
        return deleted_count
    
    def _capture_inventory_snapshot(
        self, 
        location_from: Optional[str], 
        location_to: Optional[str], 
        product_sku: Optional[str]
    ) -> Dict[str, Any]:
        """
        Cattura snapshot dell'inventario per le ubicazioni coinvolte.
        """
        snapshot = {}
        
        locations_to_capture = [loc for loc in [location_from, location_to] if loc]
        
        for location in locations_to_capture:
            query = self.db.query(inventory_models.Inventory).filter(
                inventory_models.Inventory.location_name == location
            )
            
            if product_sku:
                query = query.filter(inventory_models.Inventory.product_sku == product_sku)
            
            inventory_items = query.all()
            
            snapshot[location] = [
                {
                    "product_sku": item.product_sku,
                    "quantity": item.quantity,
                    "timestamp": datetime.utcnow().isoformat()
                }
                for item in inventory_items
            ]
        
        return snapshot
    
    def commit_logs(self):
        """
        Commit esplicito dei logs. Da usare dopo operazioni batch.
        """
        try:
            self.db.commit()
        except Exception as e:
            print(f"ERRORE COMMIT LOGS: {str(e)}")
            self.db.rollback()


# Decoratore per logging automatico
def log_operation_decorator(
    operation_type: str,
    operation_category: str = OperationCategory.MANUAL,
    capture_snapshot: bool = False
):
    """
    Decoratore per logging automatico delle funzioni.
    
    Usage:
        @log_operation_decorator(OperationType.CARICO_MANUALE, OperationCategory.MANUAL)
        def add_inventory(db, product_sku, location, quantity):
            # ... logica funzione
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Estrai database session (assume sia il primo argomento o in kwargs)
            db = None
            if args and hasattr(args[0], 'query'):
                db = args[0]
            elif 'db' in kwargs:
                db = kwargs['db']
            
            if not db:
                # Se non trova DB, esegue senza logging
                return func(*args, **kwargs)
            
            logger = LoggingService(db)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                execution_time = int((time.time() - start_time) * 1000)
                
                # Estrai parametri comuni da kwargs per logging
                logger.log_operation(
                    operation_type=operation_type,
                    operation_category=operation_category,
                    status=OperationStatus.SUCCESS,
                    product_sku=kwargs.get('product_sku'),
                    location_from=kwargs.get('location_from'),
                    location_to=kwargs.get('location_to'),
                    quantity=kwargs.get('quantity'),
                    execution_time_ms=execution_time,
                    capture_inventory_snapshot=capture_snapshot
                )
                
                return result
                
            except Exception as e:
                execution_time = int((time.time() - start_time) * 1000)
                
                logger.log_error(
                    operation_type=f"{operation_type}_FAILED",
                    error=e,
                    operation_category=operation_category,
                    product_sku=kwargs.get('product_sku'),
                    location_from=kwargs.get('location_from'),
                    location_to=kwargs.get('location_to'),
                    quantity=kwargs.get('quantity'),
                    details={"execution_time_ms": execution_time}
                )
                
                raise  # Re-raise l'eccezione originale
        
        return wrapper
    return decorator