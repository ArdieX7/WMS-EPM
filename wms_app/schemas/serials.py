from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ProductSerialBase(BaseModel):
    order_number: str
    product_sku: str
    ean_code: str
    serial_number: str

class ProductSerialCreate(ProductSerialBase):
    upload_batch_id: Optional[str] = None
    uploaded_by: Optional[str] = None

class ProductSerial(ProductSerialBase):
    id: int
    is_validated: bool
    validation_status: str
    validation_notes: Optional[str] = None
    upload_batch_id: Optional[str] = None
    created_at: datetime
    uploaded_at: datetime

    class Config:
        from_attributes = True

class SerialUploadResult(BaseModel):
    """Risultato dell'upload e parsing del file seriali"""
    success: bool
    message: str
    upload_batch_id: Optional[str] = None
    total_lines_processed: int
    total_serials_found: int
    total_orders_found: int
    errors: List[str] = []
    warnings: List[str] = []

class SerialValidationError(BaseModel):
    """Dettaglio errore di validazione"""
    error_type: str  # unknown_ean, quantity_mismatch, wrong_product, duplicate_serial, duplicate_in_file
    order_number: str
    ean_code: Optional[str] = None
    sku: Optional[str] = None
    expected_quantity: Optional[int] = None
    found_quantity: Optional[int] = None
    message: str

class SerialValidationSummary(BaseModel):
    """Riepilogo validazione seriali per ordine"""
    order_number: str
    total_serials_found: int
    total_serials_expected: int
    valid_serials: int
    invalid_serials: int
    overall_status: str  # valid, invalid, warning
    has_quantity_mismatch: bool
    has_unknown_ean: bool
    has_wrong_products: bool
    has_duplicate_serials: bool
    errors: List[SerialValidationError] = []
    missing_products: List[str] = []  # SKU mancanti
    extra_products: List[str] = []    # SKU extra non nell'ordine
    quantity_mismatches: Dict[str, Dict[str, int]] = {}  # sku: {expected: X, found: Y}

class SerialValidationReport(BaseModel):
    """Report completo validazione batch"""
    id: int
    upload_batch_id: str
    overall_status: str
    total_orders: int
    valid_orders: int
    invalid_orders: int
    created_at: datetime
    validated_at: Optional[datetime] = None
    order_summaries: List[SerialValidationSummary] = []

    class Config:
        from_attributes = True

class OrderSerialsView(BaseModel):
    """Vista seriali per un ordine specifico"""
    order_number: str
    order_exists: bool
    order_status: Optional[str] = None
    expected_products: Dict[str, int] = {}  # sku: quantity
    found_serials: Dict[str, List[str]] = {}  # sku: [serial1, serial2, ...]
    validation_summary: Optional[SerialValidationSummary] = None
    last_upload_date: Optional[datetime] = None

class SerialFileFormat(BaseModel):
    """Formato atteso per il file seriali da pistola scanner"""
    description: str = "Formato: Ogni elemento su una riga separata"
    example: str = """1234
9788838668001
SN001
9788838668001
SN002
5678
9788838668002
SN100"""
    rules: List[str] = [
        "Numero ordine: 1-10 cifre numeriche (una riga)",
        "EAN code: deve esistere in anagrafica prodotti (una riga)", 
        "Seriale: qualsiasi stringa alfanumerica (una riga)",
        "Ogni elemento è su una riga separata (a capo)",
        "I seriali sono associati all'ultimo EAN sparato",
        "Tutti gli EAN e seriali sono associati all'ultimo numero ordine sparato"
    ]

class SerialRecapItem(BaseModel):
    """Item del recap per verifica seriali"""
    line: int
    order_number: str
    ean_code: str
    serial_number: str
    sku: str
    status: str  # 'ok', 'warning', 'error'

class SerialParseResult(BaseModel):
    """Risultato del parsing con recap modificabile"""
    success: bool
    message: str
    file_name: Optional[str] = None
    total_lines_processed: int
    recap_items: List[SerialRecapItem] = []
    errors: List[str] = []
    warnings: List[str] = []
    stats: Dict[str, int] = {}  # total, ok, warnings, errors
    orders_summary: Dict[str, Dict] = {}  # order_number: {customer, serials_count, etc}

class SerialCommitRequest(BaseModel):
    """Richiesta per commit delle operazioni seriali"""
    file_name: str
    recap_items: List[SerialRecapItem]
    uploaded_by: Optional[str] = "file_user"