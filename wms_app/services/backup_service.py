import os
import shutil
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import uuid
import hashlib

from wms_app.services.logging_service import LoggingService
from wms_app.models.logs import OperationType, OperationCategory


class BackupService:
    """
    Servizio per la gestione completa dei backup del database WMS.
    Fornisce funzionalità per backup automatici, manuali, ripristini e gestione.
    """
    
    def __init__(self, db_session=None):
        """
        Inizializza il servizio backup.
        
        Args:
            db_session: Sessione database per logging (opzionale)
        """
        self.db_session = db_session
        self.logger = LoggingService(db_session) if db_session else None
        
        # Path configurabili
        self.base_dir = Path(".")
        self.db_path = self.base_dir / "wms.db"
        self.backup_root = self.base_dir / "backups"
        
        # Directory specifiche
        self.daily_dir = self.backup_root / "daily"
        self.weekly_dir = self.backup_root / "weekly"
        self.manual_dir = self.backup_root / "manual"
        self.metadata_dir = self.backup_root / "metadata"
        
        # Configurazione retention
        self.daily_retention_days = 7
        self.weekly_retention_weeks = 4
        self.manual_retention_days = 30
        
        # Assicura che le directory esistano
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Crea le directory di backup se non esistono."""
        for directory in [self.daily_dir, self.weekly_dir, self.manual_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _generate_backup_filename(self, backup_type: str) -> str:
        """
        Genera nome file per backup con timestamp.
        
        Args:
            backup_type: Tipo backup (daily, weekly, manual)
            
        Returns:
            str: Nome file backup
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"wms_{backup_type}_{timestamp}.db"
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calcola hash MD5 del file per verifica integrità.
        
        Args:
            file_path: Path al file
            
        Returns:
            str: Hash MD5 del file
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_HASH_CALCULATION_FAILED",
                    error=e,
                    operation_category=OperationCategory.SYSTEM,
                    details={"file_path": str(file_path)}
                )
            raise
    
    def _validate_database_integrity(self, db_path: Path) -> bool:
        """
        Valida l'integrità del database SQLite.
        
        Args:
            db_path: Path al database
            
        Returns:
            bool: True se database integro
        """
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                return result[0] == "ok"
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_INTEGRITY_CHECK_FAILED",
                    error=e,
                    operation_category=OperationCategory.SYSTEM,
                    details={"db_path": str(db_path)}
                )
            return False
    
    def _create_backup_metadata(self, backup_path: Path, backup_type: str, file_hash: str) -> Dict[str, Any]:
        """
        Crea metadata per il backup.
        
        Args:
            backup_path: Path al file backup
            backup_type: Tipo di backup
            file_hash: Hash del file
            
        Returns:
            dict: Metadata del backup
        """
        file_size = backup_path.stat().st_size
        
        metadata = {
            "backup_id": str(uuid.uuid4()),
            "backup_type": backup_type,
            "filename": backup_path.name,
            "filepath": str(backup_path),
            "created_at": datetime.now().isoformat(),
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "file_hash": file_hash,
            "source_db": str(self.db_path),
            "is_valid": True
        }
        
        # Salva metadata in file separato
        metadata_file = self.metadata_dir / f"{backup_path.stem}.json"
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            if self.logger:
                self.logger.log_warning(
                    operation_type="BACKUP_METADATA_SAVE_WARNING",
                    warning_message=f"Impossibile salvare metadata: {str(e)}",
                    operation_category=OperationCategory.SYSTEM
                )
        
        return metadata
    
    def create_manual_backup(self, user_id: str = "manual") -> Dict[str, Any]:
        """
        Crea un backup manuale del database.
        
        Args:
            user_id: ID utente che richiede il backup
            
        Returns:
            dict: Informazioni sul backup creato
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database non trovato: {self.db_path}")
        
        # Genera nome file e path
        filename = self._generate_backup_filename("manual")
        backup_path = self.manual_dir / filename
        
        try:
            # Copia database
            shutil.copy2(str(self.db_path), str(backup_path))
            
            # Verifica integrità
            if not self._validate_database_integrity(backup_path):
                backup_path.unlink()  # Elimina backup corrotto
                raise Exception("Backup corrotto - fallita verifica integrità")
            
            # Calcola hash e crea metadata
            file_hash = self._calculate_file_hash(backup_path)
            metadata = self._create_backup_metadata(backup_path, "manual", file_hash)
            
            # Log operazione
            if self.logger:
                self.logger.log_operation(
                    operation_type="BACKUP_MANUAL_CREATED",
                    operation_category=OperationCategory.MANUAL,
                    user_id=user_id,
                    details={
                        "backup_id": metadata["backup_id"],
                        "filename": filename,
                        "file_size_mb": metadata["file_size_mb"],
                        "file_hash": file_hash
                    }
                )
            
            return {
                "success": True,
                "backup_id": metadata["backup_id"],
                "filename": filename,
                "file_size_mb": metadata["file_size_mb"],
                "created_at": metadata["created_at"],
                "backup_path": str(backup_path)
            }
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_MANUAL_FAILED",
                    error=e,
                    operation_category=OperationCategory.MANUAL,
                    user_id=user_id
                )
            raise
    
    def create_daily_backup(self) -> Dict[str, Any]:
        """
        Crea backup giornaliero automatico.
        
        Returns:
            dict: Informazioni sul backup creato
        """
        if not self.db_path.exists():
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_DAILY_FAILED",
                    error="Database file not found",
                    operation_category=OperationCategory.SYSTEM
                )
            return {"success": False, "error": "Database non trovato"}
        
        filename = self._generate_backup_filename("daily")
        backup_path = self.daily_dir / filename
        
        try:
            shutil.copy2(str(self.db_path), str(backup_path))
            
            if not self._validate_database_integrity(backup_path):
                backup_path.unlink()
                raise Exception("Backup corrotto")
            
            file_hash = self._calculate_file_hash(backup_path)
            metadata = self._create_backup_metadata(backup_path, "daily", file_hash)
            
            if self.logger:
                self.logger.log_operation(
                    operation_type="BACKUP_DAILY_CREATED",
                    operation_category=OperationCategory.SYSTEM,
                    details={
                        "backup_id": metadata["backup_id"],
                        "filename": filename,
                        "file_size_mb": metadata["file_size_mb"]
                    }
                )
            
            return {
                "success": True,
                "backup_id": metadata["backup_id"],
                "filename": filename,
                "file_size_mb": metadata["file_size_mb"],
                "created_at": metadata["created_at"]
            }
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_DAILY_FAILED",
                    error=e,
                    operation_category=OperationCategory.SYSTEM
                )
            return {"success": False, "error": str(e)}
    
    def create_weekly_backup(self) -> Dict[str, Any]:
        """
        Crea backup settimanale automatico.
        
        Returns:
            dict: Informazioni sul backup creato
        """
        if not self.db_path.exists():
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_WEEKLY_FAILED",
                    error="Database file not found",
                    operation_category=OperationCategory.SYSTEM
                )
            return {"success": False, "error": "Database non trovato"}
        
        filename = self._generate_backup_filename("weekly")
        backup_path = self.weekly_dir / filename
        
        try:
            shutil.copy2(str(self.db_path), str(backup_path))
            
            if not self._validate_database_integrity(backup_path):
                backup_path.unlink()
                raise Exception("Backup corrotto")
            
            file_hash = self._calculate_file_hash(backup_path)
            metadata = self._create_backup_metadata(backup_path, "weekly", file_hash)
            
            if self.logger:
                self.logger.log_operation(
                    operation_type="BACKUP_WEEKLY_CREATED",
                    operation_category=OperationCategory.SYSTEM,
                    details={
                        "backup_id": metadata["backup_id"],
                        "filename": filename,
                        "file_size_mb": metadata["file_size_mb"]
                    }
                )
            
            return {
                "success": True,
                "backup_id": metadata["backup_id"],
                "filename": filename,
                "file_size_mb": metadata["file_size_mb"],
                "created_at": metadata["created_at"]
            }
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_WEEKLY_FAILED",
                    error=e,
                    operation_category=OperationCategory.SYSTEM
                )
            return {"success": False, "error": str(e)}
    
    def list_backups(self, backup_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista tutti i backup disponibili.
        
        Args:
            backup_type: Filtra per tipo (daily, weekly, manual) o None per tutti
            
        Returns:
            list: Lista backup con metadata
        """
        backups = []
        
        # Directory da scansionare
        dirs_to_scan = []
        if backup_type is None:
            dirs_to_scan = [
                (self.daily_dir, "daily"),
                (self.weekly_dir, "weekly"), 
                (self.manual_dir, "manual")
            ]
        elif backup_type == "daily":
            dirs_to_scan = [(self.daily_dir, "daily")]
        elif backup_type == "weekly":
            dirs_to_scan = [(self.weekly_dir, "weekly")]
        elif backup_type == "manual":
            dirs_to_scan = [(self.manual_dir, "manual")]
        
        for backup_dir, dir_type in dirs_to_scan:
            if not backup_dir.exists():
                continue
                
            for backup_file in backup_dir.glob("*.db"):
                # Cerca metadata corrispondente
                metadata_file = self.metadata_dir / f"{backup_file.stem}.json"
                
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        backups.append(metadata)
                    except Exception:
                        # Crea metadata base se file corrotto
                        backups.append(self._create_fallback_metadata(backup_file, dir_type))
                else:
                    # Crea metadata base se non esiste
                    backups.append(self._create_fallback_metadata(backup_file, dir_type))
        
        # Ordina per data di creazione (più recente prima)
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return backups
    
    def _create_fallback_metadata(self, backup_file: Path, backup_type: str) -> Dict[str, Any]:
        """
        Crea metadata di fallback per backup senza metadata.
        
        Args:
            backup_file: Path al file backup
            backup_type: Tipo di backup
            
        Returns:
            dict: Metadata di base
        """
        try:
            stat = backup_file.stat()
            file_size = stat.st_size
            
            return {
                "backup_id": str(uuid.uuid4()),
                "backup_type": backup_type,
                "filename": backup_file.name,
                "filepath": str(backup_file),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "file_size": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "file_hash": "unknown",
                "source_db": str(self.db_path),
                "is_valid": None  # Non verificato
            }
        except Exception:
            return {
                "backup_id": str(uuid.uuid4()),
                "backup_type": backup_type,
                "filename": backup_file.name,
                "filepath": str(backup_file),
                "created_at": datetime.now().isoformat(),
                "file_size": 0,
                "file_size_mb": 0,
                "file_hash": "error",
                "source_db": str(self.db_path),
                "is_valid": False
            }
    
    def restore_backup(self, backup_id: str, user_id: str = "restore") -> Dict[str, Any]:
        """
        Ripristina un backup specifico.
        ATTENZIONE: Questa operazione sovrascrive il database corrente!
        
        Args:
            backup_id: ID del backup da ripristinare
            user_id: ID utente che richiede il ripristino
            
        Returns:
            dict: Risultato dell'operazione
        """
        # Trova il backup
        backup_info = None
        backup_path = None
        
        for backup in self.list_backups():
            if backup["backup_id"] == backup_id:
                backup_info = backup
                backup_path = Path(backup["filepath"])
                break
        
        if not backup_info:
            raise FileNotFoundError(f"Backup {backup_id} non trovato")
        
        if not backup_path.exists():
            raise FileNotFoundError(f"File backup non trovato: {backup_path}")
        
        try:
            # Crea backup di sicurezza del database corrente
            safety_backup_name = f"wms_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            safety_backup_path = self.manual_dir / safety_backup_name
            
            if self.db_path.exists():
                shutil.copy2(str(self.db_path), str(safety_backup_path))
            
            # Verifica integrità backup da ripristinare
            if not self._validate_database_integrity(backup_path):
                raise Exception("Il backup selezionato è corrotto")
            
            # Ripristina il database
            shutil.copy2(str(backup_path), str(self.db_path))
            
            # Verifica che il ripristino sia andato a buon fine
            if not self._validate_database_integrity(self.db_path):
                # Ripristina backup di sicurezza se qualcosa è andato storto
                if safety_backup_path.exists():
                    shutil.copy2(str(safety_backup_path), str(self.db_path))
                raise Exception("Errore durante ripristino - database principale ripristinato")
            
            if self.logger:
                self.logger.log_operation(
                    operation_type="BACKUP_RESTORE_SUCCESS",
                    operation_category=OperationCategory.MANUAL,
                    user_id=user_id,
                    details={
                        "restored_backup_id": backup_id,
                        "restored_filename": backup_info["filename"],
                        "safety_backup": safety_backup_name
                    }
                )
            
            return {
                "success": True,
                "restored_backup": backup_info["filename"],
                "safety_backup": safety_backup_name,
                "restored_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_RESTORE_FAILED",
                    error=e,
                    operation_category=OperationCategory.MANUAL,
                    user_id=user_id,
                    details={"backup_id": backup_id}
                )
            raise
    
    def delete_backup(self, backup_id: str, user_id: str = "delete") -> Dict[str, Any]:
        """
        Elimina un backup specifico.
        
        Args:
            backup_id: ID del backup da eliminare
            user_id: ID utente che richiede l'eliminazione
            
        Returns:
            dict: Risultato dell'operazione
        """
        # Trova il backup
        backup_info = None
        for backup in self.list_backups():
            if backup["backup_id"] == backup_id:
                backup_info = backup
                break
        
        if not backup_info:
            raise FileNotFoundError(f"Backup {backup_id} non trovato")
        
        backup_path = Path(backup_info["filepath"])
        metadata_file = self.metadata_dir / f"{backup_path.stem}.json"
        
        try:
            # Elimina file backup
            if backup_path.exists():
                backup_path.unlink()
            
            # Elimina metadata
            if metadata_file.exists():
                metadata_file.unlink()
            
            if self.logger:
                self.logger.log_operation(
                    operation_type="BACKUP_DELETE_SUCCESS",
                    operation_category=OperationCategory.MANUAL,
                    user_id=user_id,
                    details={
                        "deleted_backup_id": backup_id,
                        "deleted_filename": backup_info["filename"]
                    }
                )
            
            return {
                "success": True,
                "deleted_backup": backup_info["filename"],
                "deleted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_DELETE_FAILED",
                    error=e,
                    operation_category=OperationCategory.MANUAL,
                    user_id=user_id,
                    details={"backup_id": backup_id}
                )
            raise
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """
        Rimuove backup vecchi secondo le policy di retention.
        
        Returns:
            dict: Statistiche pulizia
        """
        now = datetime.now()
        deleted_count = {"daily": 0, "weekly": 0, "manual": 0}
        
        # Pulizia backup giornalieri
        cutoff_daily = now - timedelta(days=self.daily_retention_days)
        for backup in self.list_backups("daily"):
            backup_date = datetime.fromisoformat(backup["created_at"].replace('Z', '+00:00').replace('+00:00', ''))
            if backup_date < cutoff_daily:
                try:
                    self.delete_backup(backup["backup_id"], "system_cleanup")
                    deleted_count["daily"] += 1
                except Exception as e:
                    if self.logger:
                        self.logger.log_warning(
                            operation_type="BACKUP_CLEANUP_WARNING",
                            warning_message=f"Impossibile eliminare backup {backup['backup_id']}: {str(e)}",
                            operation_category=OperationCategory.SYSTEM
                        )
        
        # Pulizia backup settimanali
        cutoff_weekly = now - timedelta(weeks=self.weekly_retention_weeks)
        for backup in self.list_backups("weekly"):
            backup_date = datetime.fromisoformat(backup["created_at"].replace('Z', '+00:00').replace('+00:00', ''))
            if backup_date < cutoff_weekly:
                try:
                    self.delete_backup(backup["backup_id"], "system_cleanup")
                    deleted_count["weekly"] += 1
                except Exception as e:
                    if self.logger:
                        self.logger.log_warning(
                            operation_type="BACKUP_CLEANUP_WARNING",
                            warning_message=f"Impossibile eliminare backup {backup['backup_id']}: {str(e)}",
                            operation_category=OperationCategory.SYSTEM
                        )
        
        # Pulizia backup manuali
        cutoff_manual = now - timedelta(days=self.manual_retention_days)
        for backup in self.list_backups("manual"):
            backup_date = datetime.fromisoformat(backup["created_at"].replace('Z', '+00:00').replace('+00:00', ''))
            if backup_date < cutoff_manual:
                try:
                    self.delete_backup(backup["backup_id"], "system_cleanup")
                    deleted_count["manual"] += 1
                except Exception as e:
                    if self.logger:
                        self.logger.log_warning(
                            operation_type="BACKUP_CLEANUP_WARNING",
                            warning_message=f"Impossibile eliminare backup {backup['backup_id']}: {str(e)}",
                            operation_category=OperationCategory.SYSTEM
                        )
        
        total_deleted = sum(deleted_count.values())
        
        if self.logger:
            self.logger.log_operation(
                operation_type="BACKUP_CLEANUP_COMPLETED",
                operation_category=OperationCategory.SYSTEM,
                details={
                    "total_deleted": total_deleted,
                    "daily_deleted": deleted_count["daily"],
                    "weekly_deleted": deleted_count["weekly"],
                    "manual_deleted": deleted_count["manual"],
                    "retention_policy": {
                        "daily_days": self.daily_retention_days,
                        "weekly_weeks": self.weekly_retention_weeks,
                        "manual_days": self.manual_retention_days
                    }
                }
            )
        
        return {
            "success": True,
            "total_deleted": total_deleted,
            "deleted_by_type": deleted_count,
            "cleanup_date": now.isoformat()
        }
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """
        Ottiene statistiche sui backup.
        
        Returns:
            dict: Statistiche backup
        """
        all_backups = self.list_backups()
        
        # Statistiche per tipo
        type_stats = {"daily": [], "weekly": [], "manual": []}
        for backup in all_backups:
            backup_type = backup.get("backup_type", "unknown")
            if backup_type in type_stats:
                type_stats[backup_type].append(backup)
        
        # Calcola dimensioni totali
        total_size = sum(backup.get("file_size", 0) for backup in all_backups)
        total_size_mb = round(total_size / (1024 * 1024), 2)
        
        # Backup più recente
        latest_backup = all_backups[0] if all_backups else None
        
        # Spazio occupato per directory
        space_by_type = {}
        for backup_type, backups in type_stats.items():
            space_by_type[backup_type] = {
                "count": len(backups),
                "total_mb": round(sum(b.get("file_size", 0) for b in backups) / (1024 * 1024), 2)
            }
        
        return {
            "total_backups": len(all_backups),
            "total_size_mb": total_size_mb,
            "latest_backup": latest_backup,
            "by_type": space_by_type,
            "retention_policy": {
                "daily_retention_days": self.daily_retention_days,
                "weekly_retention_weeks": self.weekly_retention_weeks,
                "manual_retention_days": self.manual_retention_days
            }
        }
    
    def validate_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Valida l'integrità di un backup specifico.
        
        Args:
            backup_id: ID del backup da validare
            
        Returns:
            dict: Risultato della validazione
        """
        # Trova il backup
        backup_info = None
        for backup in self.list_backups():
            if backup["backup_id"] == backup_id:
                backup_info = backup
                break
        
        if not backup_info:
            raise FileNotFoundError(f"Backup {backup_id} non trovato")
        
        backup_path = Path(backup_info["filepath"])
        
        if not backup_path.exists():
            return {
                "is_valid": False,
                "error": "File backup non trovato",
                "backup_id": backup_id
            }
        
        try:
            # Verifica integrità SQLite
            is_valid = self._validate_database_integrity(backup_path)
            
            # Verifica hash se disponibile
            hash_valid = True
            current_hash = None
            if backup_info.get("file_hash") and backup_info["file_hash"] != "unknown":
                current_hash = self._calculate_file_hash(backup_path)
                hash_valid = current_hash == backup_info["file_hash"]
            
            result = {
                "is_valid": is_valid and hash_valid,
                "sqlite_integrity": is_valid,
                "hash_integrity": hash_valid,
                "backup_id": backup_id,
                "filename": backup_info["filename"],
                "file_size_mb": backup_info["file_size_mb"],
                "validated_at": datetime.now().isoformat()
            }
            
            if current_hash:
                result["current_hash"] = current_hash
                result["expected_hash"] = backup_info.get("file_hash")
            
            if self.logger:
                self.logger.log_operation(
                    operation_type="BACKUP_VALIDATION_COMPLETED",
                    operation_category=OperationCategory.SYSTEM,
                    details=result
                )
            
            return result
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    operation_type="BACKUP_VALIDATION_FAILED",
                    error=e,
                    operation_category=OperationCategory.SYSTEM,
                    details={"backup_id": backup_id}
                )
            
            return {
                "is_valid": False,
                "error": str(e),
                "backup_id": backup_id
            }