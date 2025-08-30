from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime

# Schemi per OrderLine
class OrderLineBase(BaseModel):
    product_sku: str
    requested_quantity: int

class OrderLineCreate(OrderLineBase):
    pass

class OrderLine(OrderLineBase):
    id: int
    order_id: int
    picked_quantity: int = 0

    class Config:
        from_attributes = True

# Schemi per Order
class OrderBase(BaseModel):
    order_number: str
    customer_name: str

class OrderCreate(OrderBase):
    lines: List[OrderLineCreate]

class Order(OrderBase):
    id: int
    order_date: datetime
    is_completed: bool
    is_archived: bool = False
    is_cancelled: bool = False
    archived_date: Optional[datetime] = None
    cancelled_date: Optional[datetime] = None
    ddt_number: Optional[str] = None
    lines: List[OrderLine] = []
    total_weight: Optional[float] = 0.0  # Peso totale calcolato

    class Config:
        from_attributes = True

# Schema per il Picking
class PickingRequest(BaseModel):
    order_id: int

class PickedItem(BaseModel):
    order_line_id: int
    location_name: str
    product_sku: str
    quantity: int
    
    @validator('location_name')
    def location_name_to_uppercase(cls, v):
        return v.upper() if v else v

class PickConfirmation(BaseModel):
    order_id: int
    picked_items: List[PickedItem]

# Schema per l'Evasione
class FulfillmentRequest(BaseModel):
    order_id: int
    ddt_number: Optional[str] = None

# --- Nuovi Schemi per i Suggerimenti di Picking ---
class PickingSuggestionItem(BaseModel):
    location_name: str
    quantity: int

class PickingSuggestion(BaseModel):
    status: str # "full_stock" or "partial_stock"
    needed: int
    available_in_locations: List[PickingSuggestionItem]

# --- Nuovo Schema per l'Importazione Ordini da TXT ---
class OrderImportLine(BaseModel):
    order_number: str
    product_sku: str
    quantity: int
