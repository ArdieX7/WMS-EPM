from pydantic import BaseModel
from typing import List, Optional

# Schema per un singolo codice EAN
class EanCodeBase(BaseModel):
    ean: str

class EanCodeCreate(EanCodeBase):
    pass

class EanCode(EanCodeBase):
    product_sku: str

    class Config:
        from_attributes = True

# Schema per un prodotto
class ProductBase(BaseModel):
    sku: str
    description: Optional[str] = None
    estimated_value: Optional[float] = 0.0

class ProductCreate(ProductBase):
    eans: List[str] = []

class Product(ProductBase):
    eans: List[EanCode] = []

    class Config:
        from_attributes = True

# --- Nuovo Schema per l'Importazione Prodotti/EAN da TXT ---
class ProductEanImportLine(BaseModel):
    sku: str
    eans: List[str]