from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class OperationLog(Base):
    __tablename__ = "operation_logs"
    
    # Identificativi primari
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    operation_id = Column(String(36), default=lambda: str(uuid.uuid4()), nullable=False, index=True)
    
    # Classificazione operazione
    operation_type = Column(String(50), nullable=False, index=True)  # CARICO_MANUALE, SCARICO_FILE, etc.
    operation_category = Column(String(20), nullable=False, index=True)  # MANUAL, FILE, PICKING, SYSTEM
    
    # Utente e contesto
    user_id = Column(String(50), default="system", index=True)  # Futuro sistema utenti
    session_id = Column(String(100))  # Per tracciare sessioni utente
    
    # Dettagli operazione principale
    product_sku = Column(String(100), index=True)
    location_from = Column(String(50), index=True)
    location_to = Column(String(50), index=True)
    quantity = Column(Integer)
    
    # Metadati file e batch
    file_name = Column(String(255))  # Nome file se upload
    file_line_number = Column(Integer)  # Riga del file per debug
    batch_size = Column(Integer)  # Dimensione batch per operazioni multiple
    
    # Status e messaggi
    status = Column(String(20), default="SUCCESS", nullable=False, index=True)  # SUCCESS, ERROR, WARNING
    error_message = Column(Text)
    warning_message = Column(Text)
    
    # Dettagli aggiuntivi flessibili
    details = Column(JSON)  # Dati specifici per tipo operazione
    
    # Snapshot per audit (opzionale)
    inventory_before = Column(JSON)  # Stato precedente ubicazione
    inventory_after = Column(JSON)   # Stato successivo ubicazione
    
    # Tracking performance
    execution_time_ms = Column(Integer)  # Tempo esecuzione in millisecondi
    
    # Metadati sistema
    server_instance = Column(String(100))  # Per sistemi multi-server
    api_endpoint = Column(String(200))  # Endpoint API che ha generato l'operazione

# Indici compositi per query ottimizzate
Index('idx_logs_timestamp_type', OperationLog.timestamp, OperationLog.operation_type)
Index('idx_logs_sku_timestamp', OperationLog.product_sku, OperationLog.timestamp)
Index('idx_logs_location_timestamp', OperationLog.location_from, OperationLog.location_to, OperationLog.timestamp)
Index('idx_logs_status_timestamp', OperationLog.status, OperationLog.timestamp)
Index('idx_logs_operation_id', OperationLog.operation_id)  # Per operazioni batch

# Costanti per standardizzare i tipi di operazione
class OperationType:
    # Operazioni Inventario Manuali
    CARICO_MANUALE = "CARICO_MANUALE"
    SCARICO_MANUALE = "SCARICO_MANUALE"
    SPOSTAMENTO_MANUALE = "SPOSTAMENTO_MANUALE"
    RIALLINEAMENTO_MANUALE = "RIALLINEAMENTO_MANUALE"
    
    # Operazioni Inventario da File
    CARICO_FILE = "CARICO_FILE"
    SCARICO_FILE = "SCARICO_FILE"
    SPOSTAMENTO_FILE = "SPOSTAMENTO_FILE"
    RIALLINEAMENTO_FILE = "RIALLINEAMENTO_FILE"
    
    # Operazioni Container/Terra
    SCARICO_CONTAINER_MANUALE = "SCARICO_CONTAINER_MANUALE"
    SCARICO_CONTAINER_FILE = "SCARICO_CONTAINER_FILE"
    UBICAZIONE_DA_TERRA_MANUALE = "UBICAZIONE_DA_TERRA_MANUALE"
    UBICAZIONE_DA_TERRA_FILE = "UBICAZIONE_DA_TERRA_FILE"
    CONSOLIDAMENTO_TERRA = "CONSOLIDAMENTO_TERRA"
    
    # Operazioni Picking e Prenotazioni
    PICKING_GENERATO = "PICKING_GENERATO"
    PICKING_CONFERMATO = "PICKING_CONFERMATO"
    PRELIEVO_FILE = "PRELIEVO_FILE"
    PRELIEVO_MANUALE = "PRELIEVO_MANUALE"
    PRELIEVO_TEMPO_REALE = "PRELIEVO_TEMPO_REALE"
    PRENOTAZIONE_CREATA = "PRENOTAZIONE_CREATA"
    PRENOTAZIONE_SCADUTA = "PRENOTAZIONE_SCADUTA"
    PRENOTAZIONE_COMPLETATA = "PRENOTAZIONE_COMPLETATA"
    PRENOTAZIONE_CANCELLATA = "PRENOTAZIONE_CANCELLATA"
    
    # Operazioni Prodotti
    PRODOTTO_CREATO = "PRODOTTO_CREATO"
    PRODOTTO_MODIFICATO = "PRODOTTO_MODIFICATO"
    PRODOTTO_ELIMINATO = "PRODOTTO_ELIMINATO"
    
    # Operazioni Magazzino
    UBICAZIONE_CREATA = "UBICAZIONE_CREATA"
    UBICAZIONE_MODIFICATA = "UBICAZIONE_MODIFICATA"
    UBICAZIONE_ELIMINATA = "UBICAZIONE_ELIMINATA"
    
    # Operazioni Ordini
    ORDINE_CREATO = "ORDINE_CREATO"
    ORDINE_MODIFICATO = "ORDINE_MODIFICATO"
    ORDINE_ELIMINATO = "ORDINE_ELIMINATO"
    ORDINE_COMPLETATO = "ORDINE_COMPLETATO"
    ORDINE_EVASO = "ORDINE_EVASO"
    ORDINE_ANNULLATO = "ORDINE_ANNULLATO"
    
    # Operazioni Seriali
    SERIALI_ASSEGNATI = "SERIALI_ASSEGNATI"
    SERIALI_RIMOSSI = "SERIALI_RIMOSSI"
    
    # Operazioni DDT
    DDT_CREATO = "DDT_CREATO"
    DDT_MODIFICATO = "DDT_MODIFICATO"
    DDT_FINALIZZATO = "DDT_FINALIZZATO"
    
    # Operazioni Sistema
    SISTEMA_AVVIATO = "SISTEMA_AVVIATO"
    BACKUP_CREATO = "BACKUP_CREATO"
    PULIZIA_DATABASE = "PULIZIA_DATABASE"

class OperationCategory:
    MANUAL = "MANUAL"      # Operazioni manuali utente
    FILE = "FILE"          # Operazioni da upload file
    PICKING = "PICKING"    # Operazioni di picking
    SYSTEM = "SYSTEM"      # Operazioni automatiche sistema
    API = "API"            # Chiamate API esterne

class OperationStatus:
    SUCCESS = "SUCCESS"    # Operazione completata con successo
    ERROR = "ERROR"        # Errore che ha bloccato l'operazione
    WARNING = "WARNING"    # Operazione completata ma con avvisi
    PARTIAL = "PARTIAL"    # Operazione parzialmente completata
    CANCELLED = "CANCELLED"  # Operazione cancellata dall'utente