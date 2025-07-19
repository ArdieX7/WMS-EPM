from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List
import io

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from wms_app.models.products import Product
from wms_app.models.inventory import Inventory, Location
from wms_app.models.orders import OutgoingStock
from wms_app.schemas import analysis as analysis_schemas
from wms_app.database import get_db
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="wms_app/templates")

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
)

@router.get("/dashboard", response_class=HTMLResponse)
async def get_analysis_dashboard(request: Request):
    return templates.TemplateResponse("analysis.html", {"request": request, "active_page": "analysis"})

@router.get("/data", response_model=analysis_schemas.AnalysisPageData)
def get_analysis_data(db: Session = Depends(get_db)):
    """Endpoint per recuperare tutti i dati aggregati per la dashboard di analisi."""

    # 1. Calcolo dei KPI delle ubicazioni
    total_locations = db.query(func.count(Location.name)).scalar() or 0
    occupied_locations_query = db.query(func.count(func.distinct(Inventory.location_name)))
    occupied_locations = occupied_locations_query.scalar() or 0
    
    ground_floor_locations = db.query(func.count(Location.name)).filter(Location.name.like('%1P%')).scalar() or 0
    occupied_ground_floor_locations = occupied_locations_query.filter(Inventory.location_name.like('%1P%')).scalar() or 0
    free_ground_floor_locations = ground_floor_locations - occupied_ground_floor_locations

    # 2. Calcolo dei KPI di inventario
    total_pieces_in_shelves = db.query(func.sum(Inventory.quantity)).filter(Inventory.location_name != 'TERRA').scalar() or 0
    total_pieces_on_ground = db.query(func.sum(Inventory.quantity)).filter(Inventory.location_name == 'TERRA').scalar() or 0
    total_pieces_outgoing = db.query(func.sum(OutgoingStock.quantity)).scalar() or 0
    unique_skus_in_stock = db.query(func.count(func.distinct(Inventory.product_sku))).scalar() or 0

    # 3. Calcolo della valorizzazione totale
    inventory_value_query = db.query(func.sum(Inventory.quantity * Product.estimated_value)).join(Product, Inventory.product_sku == Product.sku)
    total_inventory_value = inventory_value_query.scalar() or 0.0

    kpis = analysis_schemas.AnalysisKPIs(
        total_locations=total_locations,
        occupied_locations=occupied_locations,
        free_locations=total_locations - occupied_locations,
        ground_floor_locations=ground_floor_locations,
        free_ground_floor_locations=free_ground_floor_locations,
        total_pieces_in_shelves=total_pieces_in_shelves,
        total_pieces_on_ground=total_pieces_on_ground,
        total_pieces_outgoing=total_pieces_outgoing,
        unique_skus_in_stock=unique_skus_in_stock,
        total_inventory_value=round(total_inventory_value, 2)
    )

    # 4. Calcolo della giacenza per prodotto (scaffalata + terra + in uscita)
    # Giacenza in scaffali (esclusa TERRA)
    shelves_results = db.query(
        Inventory.product_sku,
        Product.description,
        func.sum(Inventory.quantity).label("quantity_in_shelves")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name != 'TERRA'
    ).group_by(
        Inventory.product_sku, Product.description
    ).all()
    
    # Giacenza a terra (solo TERRA)
    ground_results = db.query(
        Inventory.product_sku,
        Product.description,
        func.sum(Inventory.quantity).label("quantity_on_ground")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name == 'TERRA'
    ).group_by(
        Inventory.product_sku, Product.description
    ).all()
    
    # Giacenza in uscita con descrizione prodotto
    outgoing_results = db.query(
        OutgoingStock.product_sku,
        Product.description,
        func.sum(OutgoingStock.quantity).label("quantity_outgoing")
    ).join(Product, OutgoingStock.product_sku == Product.sku).group_by(
        OutgoingStock.product_sku, Product.description
    ).all()
    
    # Recuperiamo tutti i prodotti per le descrizioni
    all_products = {p.sku: p.description for p in db.query(Product.sku, Product.description).all()}
    
    # Creiamo mappe per facilitare l'aggregazione
    shelves_map = {item.product_sku: item.quantity_in_shelves for item in shelves_results}
    ground_map = {item.product_sku: item.quantity_on_ground for item in ground_results}
    outgoing_map = {item.product_sku: item.quantity_outgoing for item in outgoing_results}
    
    # Combiniamo tutti i prodotti che hanno giacenza in almeno una categoria
    all_relevant_skus = set(shelves_map.keys()) | set(ground_map.keys()) | set(outgoing_map.keys())
    
    total_stock_list = []
    for sku in all_relevant_skus:
        quantity_in_shelves = shelves_map.get(sku, 0)
        quantity_on_ground = ground_map.get(sku, 0)
        quantity_outgoing = outgoing_map.get(sku, 0)
        
        total_stock_list.append(analysis_schemas.ProductTotalStock(
            sku=sku,
            description=all_products.get(sku, ""),
            quantity_in_shelves=quantity_in_shelves,
            quantity_on_ground=quantity_on_ground,
            quantity_outgoing=quantity_outgoing,
            total_quantity=quantity_in_shelves + quantity_on_ground + quantity_outgoing
        ))
    
    # Ordiniamo per SKU
    total_stock_list.sort(key=lambda x: x.sku)

    return analysis_schemas.AnalysisPageData(kpis=kpis, total_stock_by_product=total_stock_list)


@router.get("/product-locations/{sku:path}", response_model=List[analysis_schemas.ProductLocationItem])
def get_product_locations(sku: str, db: Session = Depends(get_db)):
    """Dato uno SKU, restituisce tutte le ubicazioni che lo contengono."""
    locations = db.query(Inventory).filter(
        Inventory.product_sku == sku,
        Inventory.quantity > 0
    ).order_by(Inventory.location_name).all()
    
    if not locations:
        raise HTTPException(status_code=404, detail="SKU non trovato in nessuna ubicazione o SKU inesistente.")

    return [analysis_schemas.ProductLocationItem(location_name=item.location_name, quantity=item.quantity) for item in locations]


@router.get("/export-product-locations/{sku:path}")
async def export_product_locations_csv(sku: str, db: Session = Depends(get_db)):
    """Esporta le ubicazioni di un prodotto in formato CSV."""
    locations = await get_product_locations(sku, db) # Riusiamo la logica dell'endpoint precedente

    output = io.StringIO()
    output.write("ubicazione,quantita\n") # Intestazione del CSV
    for item in locations:
        output.write(f"{item.location_name},{item.quantity}\n")
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ubicazioni_{sku.replace('/', '_')}.csv"}
    )

@router.get("/products-by-row/{fila}", response_model=List[analysis_schemas.ProductInRowItem])
def get_products_by_row(fila: int, db: Session = Depends(get_db)):
    """Restituisce tutti i prodotti e le loro ubicazioni per una data fila."""
    # Filtra le ubicazioni che iniziano con il numero della fila e contengono 'P' (per posizione)
    # Assumiamo che il formato sia FILA_CAMPATA_PIANO_POSIZIONE (es. 1A1P1)
    search_pattern = f"{fila}%%P%"
    
    products_query = db.query(
        Inventory.location_name,
        Inventory.product_sku,
        Product.description,
        Inventory.quantity
    ).join(Product, Inventory.product_sku == Product.sku)

    filtered_products = products_query.filter(
        Inventory.location_name.like(search_pattern)
    ).filter(Inventory.quantity > 0)
    
    products_in_row = filtered_products.order_by(Inventory.location_name, Inventory.product_sku).all()

    if not products_in_row:
        raise HTTPException(status_code=404, detail=f"Nessun prodotto trovato nella fila {fila} o fila inesistente.")

    return [analysis_schemas.ProductInRowItem(
        location_name=item.location_name,
        product_sku=item.product_sku,
        product_description=item.description,
        quantity=item.quantity
    ) for item in products_in_row]

@router.get("/export-products-by-row-pdf/{fila}")
async def export_products_by_row_pdf(fila: int, db: Session = Depends(get_db)):
    """Esporta i prodotti di una fila in formato PDF."""
    products_data = get_products_by_row(fila, db) # Riusiamo la logica dell'endpoint precedente

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Titolo
    story.append(Paragraph(f"Report Prodotti Fila {fila}", styles['h1']))
    story.append(Spacer(1, 0.2 * inch))

    # Dati della tabella
    data = [["Ubicazione", "SKU", "Descrizione", "Quantità"]]
    for item in products_data:
        data.append([item.location_name, item.product_sku, item.product_description or '', str(item.quantity)])

    table = Table(data)
    table.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
        ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ])
    story.append(table)

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=prodotti_fila_{fila}.pdf"}
    )