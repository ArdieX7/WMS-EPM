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
    critical_stock_skus: int = 0  # SKU con giacenza <= 15 pezzi

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

class PalletSummary(BaseModel):
    """Rappresenta il riassunto totale dei pallet nel magazzino."""
    total_pallets: float
    pallets_on_ground: float
    pallets_in_shelves: float
    products_analyzed: int

class ProductPalletDetail(BaseModel):
    """Rappresenta il dettaglio pallet per un singolo prodotto."""
    sku: str
    description: Optional[str]
    pallet_quantity: int  # Quantità per pallet (configurata)
    pallets_on_ground: float
    pallets_in_shelves: float
    pallets_total: float
    quantity_on_ground: int  # Quantità effettiva a terra
    quantity_in_shelves: int  # Quantità effettiva in scaffali

class PalletDetails(BaseModel):
    """Dati completi per il modal dei dettagli pallet."""
    summary: PalletSummary
    products: List[ProductPalletDetail]
