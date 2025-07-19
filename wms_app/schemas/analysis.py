from pydantic import BaseModel
from typing import List, Optional

# --- Schemi per la pagina di Analisi ---

class ProductTotalStock(BaseModel):
    """Rappresenta la giacenza totale di un singolo prodotto."""
    sku: str
    description: Optional[str]
    quantity_in_shelves: int = 0
    quantity_on_ground: int = 0
    quantity_outgoing: int = 0
    total_quantity: int

class AnalysisKPIs(BaseModel):
    """Rappresenta gli indicatori chiave di performance (KPI) del magazzino."""
    total_locations: int
    occupied_locations: int
    free_locations: int
    ground_floor_locations: int
    free_ground_floor_locations: int
    total_pieces_in_shelves: int
    total_pieces_on_ground: int
    total_pieces_outgoing: int
    unique_skus_in_stock: int
    total_inventory_value: float

class AnalysisPageData(BaseModel):
    """Dati completi per la pagina di analisi."""
    kpis: AnalysisKPIs
    total_stock_by_product: List[ProductTotalStock]

class ProductLocationItem(BaseModel):
    """Rappresenta la giacenza di un prodotto in una specifica ubicazione."""
    location_name: str
    quantity: int

class ProductInRowItem(BaseModel):
    """Rappresenta un prodotto trovato in una specifica ubicazione all'interno di una fila."""
    location_name: str
    product_sku: str
    product_description: Optional[str]
    quantity: int
