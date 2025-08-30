from pydantic import BaseModel
from typing import Optional, List

# Schema per una singola ubicazione
class LocationBase(BaseModel):
    name: str

class LocationCreate(LocationBase):
    pass

class Location(LocationBase):
    class Config:
        from_attributes = True

# Schema per una voce di inventario
class InventoryBase(BaseModel):
    location_name: str
    product_sku: str
    quantity: int

class InventoryUpdate(BaseModel):
    location_name: str
    product_sku: str
    quantity: int # La quantità da aggiungere (positiva) o rimuovere (negativa)

class Inventory(InventoryBase):
    id: int
    product: Optional["Product"] # Per visualizzare i dettagli del prodotto

    class Config:
        from_attributes = True

# --- Nuovo Schema per la Generazione Massiva Ubicazioni ---
class LocationGenerate(BaseModel):
    start_fila: int
    end_fila: int
    start_campata: str # Es: 'A'
    end_campata: str   # Es: 'H'
    start_piano: int
    end_piano: int
    start_posizione: int
    end_posizione: int

# --- Nuovo Schema per la Movimentazione Interna ---
class InternalMove(BaseModel):
    product_sku: str
    from_location_name: str
    to_location_name: str
    quantity: int # Quantità da spostare. Se 0 o -1, indica spostamento totale.

# --- Schemi per Importazione/Controllo Giacenze da File ---
class InventoryComparisonItem(BaseModel):
    location_name: str
    product_sku: str
    current_quantity: int
    new_quantity: int
    status: str # Es: 'new', 'update', 'no_change', 'delete_implicit'

class StockParseError(BaseModel):
    line_number: int
    line_content: str
    error: str

class StockParseResult(BaseModel):
    items_to_commit: List[InventoryComparisonItem]
    errors: List[StockParseError]

class StockCommitRequest(BaseModel):
    items: List[InventoryComparisonItem] # Ora inviamo l'intero oggetto di confronto

# --- Schema per Consigli di Consolidamento ---
class ConsolidationSuggestion(BaseModel):
    sku: str
    description: str
    pallet_quantity: int
    from_location: str
    from_quantity: int
    to_location: str
    to_quantity: int
    combined_quantity: int
    efficiency_gain: str

class ConsolidationSuggestionsResponse(BaseModel):
    suggestions: List[ConsolidationSuggestion]
    total_suggestions: int
    locations_saveable: int
    products_analyzed: int
    products_with_palletization: int


# Importazione posticipata per evitare dipendenze circolari
from .products import Product
Inventory.update_forward_refs()
