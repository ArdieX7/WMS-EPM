from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from wms_app.database.database import Base

class ProductSerial(Base):
    """
    Modello per la gestione dei seriali prodotto
    Traccia i seriali associati agli ordini per il controllo qualità
    """
    __tablename__ = "product_serials"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, nullable=False, index=True)  # Numero ordine (1-10 cifre)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)  # SKU del prodotto
    ean_code = Column(String, nullable=False, index=True)  # EAN code originale dal file
    serial_number = Column(String, nullable=False)  # Numero seriale del prodotto
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # Stato validazione
    is_validated = Column(Boolean, default=False)  # Se il seriale è stato validato
    validation_status = Column(String, default="pending")  # pending, valid, invalid, duplicate
    validation_notes = Column(Text)  # Note validazione/errori
    
    # Metadata upload
    upload_batch_id = Column(String, index=True)  # ID batch per raggruppare upload
    uploaded_by = Column(String)  # Utente che ha caricato
    
    # Relazioni
    product = relationship("Product", back_populates="serials")

class SerialValidationReport(Base):
    """
    Report di validazione dei seriali per ordine
    Contiene il riepilogo della validazione con eventuali errori
    """
    __tablename__ = "serial_validation_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, nullable=False, index=True)
    upload_batch_id = Column(String, nullable=False, index=True)
    
    # Statistiche validazione
    total_serials_found = Column(Integer, default=0)
    total_serials_expected = Column(Integer, default=0)  # Da ordine originale
    valid_serials = Column(Integer, default=0)
    invalid_serials = Column(Integer, default=0)
    
    # Stato generale
    overall_status = Column(String, default="pending")  # valid, invalid, warning
    has_quantity_mismatch = Column(Boolean, default=False)
    has_unknown_ean = Column(Boolean, default=False)
    has_wrong_products = Column(Boolean, default=False)
    
    # Dettagli errori
    error_summary = Column(Text)  # JSON con dettaglio errori
    missing_products = Column(Text)  # SKU mancanti
    extra_products = Column(Text)  # SKU extra non presenti nell'ordine
    quantity_mismatches = Column(Text)  # JSON con differenze quantità
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    validated_at = Column(DateTime)
    
    # Metadata
    validated_by = Column(String)
    notes = Column(Text)