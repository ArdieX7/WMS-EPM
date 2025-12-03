from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime


# Schemas per ArrivalLine
class ArrivalLineBase(BaseModel):
    product_sku: str
    expected_quantity: int

    @validator('expected_quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v


class ArrivalLineCreate(ArrivalLineBase):
    pass


class ArrivalLineUpdate(BaseModel):
    """Per modifiche da recap desktop"""
    product_sku: str
    expected_quantity: int


class ArrivalLine(ArrivalLineBase):
    id: int
    arrival_id: int
    received_quantity: int = 0

    class Config:
        from_attributes = True


# Schemas per Arrival
class ArrivalBase(BaseModel):
    arrival_number: str
    supplier_name: str
    arrival_date: Optional[datetime] = None
    notes: Optional[str] = None


class ArrivalCreate(ArrivalBase):
    """Creazione documento con righe da form desktop"""
    lines: List[ArrivalLineCreate]


class ArrivalUpdate(BaseModel):
    """Update documento (prima della conferma)"""
    supplier_name: Optional[str] = None
    arrival_date: Optional[datetime] = None
    notes: Optional[str] = None
    lines: Optional[List[ArrivalLineUpdate]] = None


class Arrival(ArrivalBase):
    id: int
    created_date: datetime
    is_draft: bool
    is_completed: bool
    completed_date: Optional[datetime] = None
    lines: List[ArrivalLine] = []

    class Config:
        from_attributes = True


# Schema per conferma documento
class ArrivalConfirmRequest(BaseModel):
    """Desktop: conferma documento con possibili modifiche"""
    arrival_id: int
    modified_lines: Optional[List[ArrivalLineUpdate]] = None


class ArrivalConfirmResponse(BaseModel):
    success: bool
    message: str
    operations_logged: int
    arrival: Arrival


# Schema per mobile scanner
class ArrivalScanValidation(BaseModel):
    """Validazione EAN scansionato da mobile"""
    arrival_id: int
    ean_code: str


class ArrivalScanValidationResponse(BaseModel):
    valid: bool
    product_sku: Optional[str] = None
    product_description: Optional[str] = None
    expected_quantity: int = 0
    received_quantity: int = 0
    progress_percentage: float = 0.0
    message: Optional[str] = None


class ArrivalScanConfirm(BaseModel):
    """Conferma quantità scansionata da mobile"""
    arrival_id: int
    product_sku: str
    quantity: int


class ArrivalScanConfirmResponse(BaseModel):
    success: bool
    message: str
    received_quantity: int
    expected_quantity: int
    progress_percentage: float
    all_completed: bool
