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

# Schema per la Modifica Data Archiviazione
class UpdateArchivedDateRequest(BaseModel):
    new_archived_date: datetime

    @validator('new_archived_date')
    def validate_date_not_future(cls, v):
        # Rimuovi timezone info per confronto
        v_naive = v.replace(tzinfo=None) if v.tzinfo else v
        now_naive = datetime.now()

        if v_naive > now_naive:
            raise ValueError('La data di archiviazione non può essere nel futuro')
        return v

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

# --- Schema for Order Editing ---
class OrderLineEdit(BaseModel):
    """Single line in an order edit request"""
    product_sku: str
    requested_quantity: int

    @validator('requested_quantity')
    def validate_positive_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

class OrderEditRequest(BaseModel):
    """Request body for editing an order"""
    lines: List[OrderLineEdit]

    @validator('lines')
    def validate_lines_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Order must have at least one line')
        return v

class OrderEditWarning(BaseModel):
    """Warning message about TERRA transfers or constraints"""
    type: str  # 'terra_transfer', 'picked_constraint', 'ddt_exists'
    product_sku: Optional[str] = None
    message: str
    quantity: Optional[int] = None

class OrderEditResponse(BaseModel):
    """Response from order edit operation"""
    success: bool
    message: str
    warnings: List[OrderEditWarning] = []
    order: "Order"  # Forward reference


# --- Schemi per Prelievi Real-Time ---

class PickingOpenOrderLine(BaseModel):
    order_line_id: int
    product_sku: str
    product_name: Optional[str] = None
    requested_quantity: int
    picked_quantity: int
    remaining: int

class PickingOpenOrder(BaseModel):
    order_id: int
    order_number: str
    customer_name: str
    lines: List[PickingOpenOrderLine]
    total_items: int
    total_picked: int
    is_fully_picked: bool

class PickingOpenOrdersResponse(BaseModel):
    orders: List[PickingOpenOrder]

class PickingPlanLocation(BaseModel):
    location_name: str
    available_quantity: int
    reservation_id: Optional[int] = None
    to_pick: int

class PickingPlanLine(BaseModel):
    order_line_id: int
    product_sku: str
    product_name: Optional[str] = None
    ean_codes: List[str] = []
    requested_quantity: int
    picked_quantity: int
    remaining: int
    suggested_locations: List[PickingPlanLocation] = []
    status: str  # full_stock, partial_stock, out_of_stock, completed

class ActivatePickingSessionResponse(BaseModel):
    session_id: str
    order_id: int
    order_number: str
    customer_name: str
    picking_plan: List[PickingPlanLine]

class ValidateScanLocationRequest(BaseModel):
    location_name: str
    session_id: str

    @validator('location_name')
    def location_name_to_uppercase(cls, v):
        return v.upper() if v else v

class ProductAtLocation(BaseModel):
    product_sku: str
    product_name: Optional[str] = None
    order_line_id: int
    available_quantity: int
    needed: int
    ean_codes: List[str] = []

class ValidateScanLocationResponse(BaseModel):
    valid: bool
    location_name: str
    products_available: List[ProductAtLocation] = []
    error: Optional[str] = None
    status: Optional[str] = None

class ValidateScanEanRequest(BaseModel):
    ean_code: str
    location_name: str
    session_id: str

    @validator('location_name')
    def location_name_to_uppercase(cls, v):
        return v.upper() if v else v

class ValidateScanEanResponse(BaseModel):
    valid: bool
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    order_line_id: Optional[int] = None
    available_at_location: Optional[int] = None
    remaining_to_pick: Optional[int] = None
    max_pickable: Optional[int] = None
    error: Optional[str] = None
    status: Optional[str] = None

class RealtimeCommitPickRequest(BaseModel):
    order_line_id: int
    product_sku: str
    location_name: str
    quantity: int
    session_id: str
    reservation_id: Optional[int] = None

    @validator('location_name')
    def location_name_to_uppercase(cls, v):
        return v.upper() if v else v

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('La quantità deve essere positiva')
        return v

class RealtimeCommitPickResponse(BaseModel):
    success: bool
    product_sku: Optional[str] = None
    location_name: Optional[str] = None
    quantity_picked: Optional[int] = None
    new_picked_quantity: Optional[int] = None
    new_remaining: Optional[int] = None
    product_completed: Optional[bool] = None
    order_fully_picked: Optional[bool] = None
    progress: Optional[str] = None
    error: Optional[str] = None
    status: Optional[str] = None

class RealtimeUndoPickRequest(BaseModel):
    order_line_id: int
    location_name: str
    product_sku: str
    quantity: int

    @validator('location_name')
    def location_name_to_uppercase(cls, v):
        return v.upper() if v else v

class RealtimeUndoPickResponse(BaseModel):
    success: bool
    quantity_restored: Optional[int] = None
    new_picked_quantity: Optional[int] = None
    new_remaining: Optional[int] = None
    error: Optional[str] = None
    status: Optional[str] = None
