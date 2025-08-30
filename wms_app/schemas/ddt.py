from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DDTLineBase(BaseModel):
    product_sku: str
    product_description: str
    quantity: int
    unit_measure: str = "pz"

class DDTLineCreate(DDTLineBase):
    pass

class DDTLine(DDTLineBase):
    id: int
    ddt_id: int
    
    class Config:
        from_attributes = True

class DDTBase(BaseModel):
    order_number: str
    customer_name: str
    customer_address: Optional[str] = None
    customer_city: Optional[str] = None
    customer_cap: Optional[str] = None
    customer_province: Optional[str] = None
    transporter_name: Optional[str] = None
    transporter_notes: Optional[str] = None
    transport_reason: str = "Vendita"
    total_packages: int = 1
    total_weight: Optional[str] = None
    notes: Optional[str] = None

class DDTCreate(DDTBase):
    lines: List[DDTLineCreate]

class DDT(DDTBase):
    id: int
    ddt_number: str
    issue_date: datetime
    transport_date: Optional[datetime] = None
    is_printed: bool = False
    printed_date: Optional[datetime] = None
    lines: List[DDTLine] = []
    
    class Config:
        from_attributes = True

class DDTGenerateRequest(BaseModel):
    order_number: str
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    customer_city: Optional[str] = None
    customer_cap: Optional[str] = None
    customer_province: Optional[str] = None
    transporter_name: Optional[str] = None
    transporter_notes: Optional[str] = None
    transport_reason: str = "Vendita"
    total_packages: int = 1
    total_weight: Optional[str] = None
    notes: Optional[str] = None

class DDTResponse(BaseModel):
    ddt: DDT
    message: str