from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from typing import List
import io

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, KeepTogether, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import math

from wms_app.models.products import Product
from wms_app.models.inventory import Inventory, Location
from wms_app.models.orders import OutgoingStock
from wms_app.schemas import analysis as analysis_schemas
from wms_app.database import get_db
from wms_app.routers.auth import require_permission
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="wms_app/templates")

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
)


@router.get("/test-endpoint")
async def test_endpoint():
    print("🟢 TEST ENDPOINT CHIAMATO - IL SERVER FUNZIONA!")
    return {"status": "OK", "message": "Server funziona correttamente"}

@router.get("/dashboard", response_class=HTMLResponse)
async def get_analysis_dashboard(request: Request):
    print("🚨🚨🚨 DASHBOARD ANALYSIS CARICATO - LE MODIFICHE FUNZIONANO! 🚨🚨🚨")
    return templates.TemplateResponse("analysis.html", {"request": request, "active_page": "analysis"})

@router.get("/data", response_model=analysis_schemas.AnalysisPageData)
def get_analysis_data(db: Session = Depends(get_db)):
    """Endpoint per recuperare tutti i dati aggregati per la dashboard di analisi."""

    # 1. Calcolo dei KPI delle ubicazioni
    total_locations = db.query(func.count(Location.name)).scalar() or 0
    
    # CORRETTO: conta solo ubicazioni con quantity > 0 (coerente con pallet scaffali)
    occupied_locations_query = db.query(func.count(func.distinct(Inventory.location_name))).filter(
        Inventory.quantity > 0
    )
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
    # Prima calcoliamo gli SKU critici per il KPI
    critical_skus_count = 0
    
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
    
    # Calcoliamo gli SKU critici (giacenza <= 15)
    critical_skus_count = len([item for item in total_stock_list if item.total_quantity <= 15])
    
    # Aggiorniamo il KPI con il conteggio degli SKU critici
    kpis.critical_stock_skus = critical_skus_count

    return analysis_schemas.AnalysisPageData(kpis=kpis, total_stock_by_product=total_stock_list)

@router.get("/outgoing-stock-total")
def get_outgoing_stock_total(db: Session = Depends(get_db)):
    """Endpoint per ottenere il totale della giacenza in uscita"""
    total_pieces_outgoing = db.query(func.sum(OutgoingStock.quantity)).scalar() or 0
    return {"total": total_pieces_outgoing}

@router.get("/critical-stock-details")
def get_critical_stock_details(db: Session = Depends(get_db)):
    """Endpoint per ottenere la lista dettagliata degli SKU con giacenza critica (≤ 20 pezzi)"""
    # Calcoliamo la giacenza totale per ogni SKU (come nel main endpoint)
    
    # Giacenza in scaffali (esclusa TERRA)
    shelves_results = db.query(
        Inventory.product_sku,
        Product.description,
        func.sum(Inventory.quantity).label("quantity_in_shelves")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name != 'TERRA'
    ).group_by(Inventory.product_sku, Product.description).all()
    
    # Giacenza a TERRA
    ground_results = db.query(
        Inventory.product_sku,
        Product.description,
        func.sum(Inventory.quantity).label("quantity_on_ground")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name == 'TERRA'
    ).group_by(Inventory.product_sku, Product.description).all()
    
    # Giacenza in uscita
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
    
    critical_items = []
    for sku in all_relevant_skus:
        quantity_in_shelves = shelves_map.get(sku, 0)
        quantity_on_ground = ground_map.get(sku, 0)
        quantity_outgoing = outgoing_map.get(sku, 0)
        total_quantity = quantity_in_shelves + quantity_on_ground + quantity_outgoing
        
        # Filtra solo gli SKU con giacenza critica (≤ 15)
        if total_quantity <= 15:
            # Trova la prima ubicazione dove si trova il prodotto per il link
            first_location = None
            location_result = db.query(Inventory.location_name).filter(
                Inventory.product_sku == sku,
                Inventory.quantity > 0
            ).first()
            if location_result:
                first_location = location_result.location_name
            elif outgoing_map.get(sku, 0) > 0:
                first_location = "IN_USCITA"
            
            critical_items.append({
                "sku": sku,
                "description": all_products.get(sku, ""),
                "quantity_in_shelves": quantity_in_shelves,
                "quantity_on_ground": quantity_on_ground,
                "quantity_outgoing": quantity_outgoing,
                "total_quantity": total_quantity,
                "primary_location": first_location or "N/A"
            })
    
    # Ordiniamo per giacenza totale crescente (i più critici per primi)
    critical_items.sort(key=lambda x: x["total_quantity"])
    
    return {
        "critical_items": critical_items,
        "count": len(critical_items),
        "threshold": 15
    }


def _get_product_locations_data(sku: str, db: Session):
    """Funzione interna per ottenere i dati delle ubicazioni di un prodotto."""
    locations = db.query(Inventory).filter(
        Inventory.product_sku == sku,
        Inventory.quantity > 0
    ).order_by(Inventory.location_name).all()
    
    if not locations:
        raise HTTPException(status_code=404, detail="SKU non trovato in nessuna ubicazione o SKU inesistente.")

    return [analysis_schemas.ProductLocationItem(location_name=item.location_name, quantity=item.quantity) for item in locations]

@router.get("/product-locations/{sku:path}", response_model=List[analysis_schemas.ProductLocationItem])
def get_product_locations(sku: str, db: Session = Depends(get_db)):
    """Dato uno SKU, restituisce tutte le ubicazioni che lo contengono."""
    return _get_product_locations_data(sku, db)


@router.get("/export-product-locations/{sku:path}")
async def export_product_locations_csv(sku: str, db: Session = Depends(get_db)):
    """Esporta le ubicazioni di un prodotto in formato CSV."""
    locations = _get_product_locations_data(sku, db) # Riusiamo la logica dell'endpoint precedente

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

@router.get("/export-product-locations-pdf/{sku:path}")
async def export_product_locations_pdf(sku: str, db: Session = Depends(get_db)):
    """Esporta le ubicazioni di un prodotto in formato PDF."""
    try:
        # Ottieni direttamente i dati
        locations_query = db.query(Inventory).filter(
            Inventory.product_sku == sku,
            Inventory.quantity > 0
        ).order_by(Inventory.location_name).all()
        
        if not locations_query:
            raise HTTPException(status_code=404, detail=f"SKU '{sku}' non trovato in nessuna ubicazione con quantità > 0")

        # Converti i risultati nel formato necessario
        locations = [{"location_name": item.location_name, "quantity": item.quantity} for item in locations_query]

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Titolo
        story.append(Paragraph(f"Report Ubicazioni - Prodotto: {sku}", styles['h1']))
        story.append(Spacer(1, 0.2 * inch))

        # Calcola righe per pagina: circa 25 righe per tabella (50 totali in 2 colonne) per pagina A4
        max_rows_per_table = 25
        max_rows_per_page = max_rows_per_table * 2  # Due colonne per pagina
        
        # Se i dati sono pochi, usa una sola tabella
        if len(locations) <= max_rows_per_table:
            data = [["Ubicazione", "Qty", "Note"]]
            for item in locations:
                data.append([item["location_name"], str(item["quantity"]), ""])

            table = Table(data, colWidths=[1.5*inch, 0.5*inch, 1.2*inch])
            table.setStyle([
                ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
            ])
            story.append(table)
        else:
            # Dividi in pagine con gestione multi-pagina
            page_num = 1
            for i in range(0, len(locations), max_rows_per_page):
                page_data = locations[i:i + max_rows_per_page]
                
                # Se non è la prima pagina, aggiungi page break e titolo
                if i > 0:
                    story.append(PageBreak())
                    story.append(Paragraph(f"Report Ubicazioni - Prodotto: {sku} (Pag. {page_num})", styles['h2']))
                    story.append(Spacer(1, 0.1 * inch))
                
                # Dividi i dati della pagina in due colonne
                mid_point = len(page_data) // 2
                left_locations = page_data[:mid_point]
                right_locations = page_data[mid_point:]

                # Prima tabella (sinistra)
                data1 = [["Ubicazione", "Qty", "Note"]]
                for item in left_locations:
                    data1.append([item["location_name"], str(item["quantity"]), ""])

                table1 = Table(data1, colWidths=[1.2*inch, 0.4*inch, 1*inch])
                table1.setStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                    ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                ])

                # Seconda tabella (destra) - solo se ci sono dati
                if right_locations:
                    data2 = [["Ubicazione", "Qty", "Note"]]
                    for item in right_locations:
                        data2.append([item["location_name"], str(item["quantity"]), ""])

                    table2 = Table(data2, colWidths=[1.2*inch, 0.4*inch, 1*inch])
                    table2.setStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                        ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 3),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ('TOPPADDING', (0, 0), (-1, -1), 2),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ])

                    # Crea contenitore per affiancare le tabelle
                    container_data = [[table1, "", table2]]
                    container_table = Table(container_data, colWidths=[2.6*inch, 0.4*inch, 2.6*inch])
                else:
                    # Se non ci sono dati per la seconda colonna, usa solo la prima
                    container_data = [[table1, "", ""]]
                    container_table = Table(container_data, colWidths=[2.6*inch, 0.4*inch, 2.6*inch])
                
                container_table.setStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ])
                story.append(container_table)
                
                page_num += 1

        doc.build(story)
        buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(buffer.getvalue()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=ubicazioni_{sku.replace('/', '_')}.pdf"}
        )
    except Exception as e:
        print(f"Errore PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione PDF: {str(e)}")

@router.get("/products-by-row/{fila}", response_model=List[analysis_schemas.ProductInRowItem])
def get_products_by_row(fila: int, db: Session = Depends(get_db)):
    """Restituisce tutti i prodotti e le loro ubicazioni per una data fila."""
    # Filtra le ubicazioni che iniziano ESATTAMENTE con il numero della fila seguito da una lettera
    # Formato ubicazioni: {FILA}{LETTERA}{RESTO} (es. 2A1P1, 21A1P1)
    # Uso LIKE con controllo che il carattere dopo il numero sia una lettera
    
    products_query = db.query(
        Inventory.location_name,
        Inventory.product_sku,
        Product.description,
        Inventory.quantity
    ).join(Product, Inventory.product_sku == Product.sku)

    # Pattern per matchare esattamente la fila: inizia con il numero + almeno una lettera
    fila_pattern = f"{fila}A%"
    
    # Query che filtra ubicazioni che iniziano con {fila}A, {fila}B, {fila}C, etc.
    # ma NON {fila}1, {fila}2, etc. (che sarebbero altre file)
    from sqlalchemy import or_
    
    letter_patterns = [f"{fila}{letter}%" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    
    filtered_products = products_query.filter(
        or_(*[Inventory.location_name.like(pattern) for pattern in letter_patterns])
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

@router.get("/export-products-by-row/{fila}")
async def export_products_by_row_csv(fila: int, db: Session = Depends(get_db)):
    """Esporta i prodotti di una fila in formato CSV."""
    products_data = get_products_by_row(fila, db) # Riusiamo la logica dell'endpoint precedente
    
    output = io.StringIO()
    output.write("ubicazione,sku,quantita\n") # Intestazione del CSV
    for item in products_data:
        output.write(f"{item.location_name},{item.product_sku},{item.quantity}\n")
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=prodotti_fila_{fila}.csv"}
    )

@router.get("/export-products-by-row-pdf/{fila}")
async def export_products_by_row_pdf(fila: int, db: Session = Depends(get_db)):
    """Esporta i prodotti di una fila in formato PDF."""
    # Query diretta per evitare problemi di caching
    
    products_query = db.query(
        Inventory.location_name,
        Inventory.product_sku,
        Product.description,
        Inventory.quantity
    ).join(Product, Inventory.product_sku == Product.sku)

    letter_patterns = [f"{fila}{letter}%" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    
    filtered_products = products_query.filter(
        or_(*[Inventory.location_name.like(pattern) for pattern in letter_patterns])
    ).filter(Inventory.quantity > 0)
    
    products_in_row = filtered_products.order_by(Inventory.location_name, Inventory.product_sku).all()

    if not products_in_row:
        raise HTTPException(status_code=404, detail=f"Nessun prodotto trovato nella fila {fila} o fila inesistente.")

    # Converti in formato necessario per il PDF (senza descrizione)
    products_data = [{"location_name": item.location_name, "product_sku": item.product_sku, "quantity": item.quantity} for item in products_in_row]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Titolo
    story.append(Paragraph(f"Report Prodotti - Fila: {fila}", styles['h1']))
    story.append(Spacer(1, 0.2 * inch))

    # Calcola righe per pagina: circa 30 righe per tabella in layout 2-colonne
    max_rows_per_table = 30
    max_rows_per_page = max_rows_per_table * 2  # Due tabelle per pagina
    
    # Se i dati sono pochi, usa una sola tabella
    if len(products_data) <= max_rows_per_table:
        data = [["Ubicazione", "SKU", "Qty", "Note"]]
        for item in products_data:
            data.append([item["location_name"], item["product_sku"], str(item["quantity"]), ""])

        table = Table(data, colWidths=[0.8*inch, 2*inch, 0.4*inch, 1.4*inch])
        table.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
            ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ])
        story.append(table)
    else:
        # Dividi in pagine con 2 colonne per pagina
        page_num = 1
        for i in range(0, len(products_data), max_rows_per_page):
            page_data = products_data[i:i + max_rows_per_page]
            
            # Se non è la prima pagina, aggiungi page break e titolo
            if i > 0:
                story.append(PageBreak())
                story.append(Paragraph(f"Report Prodotti - Fila: {fila} (Pag. {page_num})", styles['h2']))
                story.append(Spacer(1, 0.1 * inch))
            
            # Dividi i dati della pagina in due colonne
            mid_point = len(page_data) // 2
            left_products = page_data[:mid_point]
            right_products = page_data[mid_point:]

            # Prima tabella (sinistra)
            data1 = [["Ubicazione", "SKU", "Qty", "Note"]]
            for item in left_products:
                data1.append([item["location_name"], item["product_sku"], str(item["quantity"]), ""])

            table1 = Table(data1, colWidths=[0.6*inch, 1.5*inch, 0.3*inch, 1.2*inch])
            table1.setStyle([
                ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ])

            # Seconda tabella (destra)
            data2 = [["Ubicazione", "SKU", "Qty", "Note"]]
            for item in right_products:
                data2.append([item["location_name"], item["product_sku"], str(item["quantity"]), ""])

            table2 = Table(data2, colWidths=[0.6*inch, 1.5*inch, 0.3*inch, 1.2*inch])
            table2.setStyle([
                ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ])

            # Crea contenitore per affiancare le tabelle con spazio tra loro
            container_data = [[table1, "", table2]]  # Colonna vuota per spaziatura
            container_table = Table(container_data, colWidths=[3.6*inch, 0.3*inch, 3.6*inch])
            container_table.setStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ])
            story.append(container_table)
            
            page_num += 1

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(buffer.getvalue()),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=prodotti_fila_{fila}.pdf"}
    )

@router.get("/pallet-summary", response_model=analysis_schemas.PalletSummary)
def get_pallet_summary(db: Session = Depends(get_db)):
    """Calcola il totale pallet nel magazzino. 
    Scaffali: 1 pallet per ubicazione occupata.
    Terra: CEIL(quantità / pallet_quantity)."""
    
    # 1. Conta ubicazioni occupate negli scaffali (ogni ubicazione = 1 pallet)
    shelves_locations_count = db.query(Inventory).filter(
        Inventory.location_name != 'TERRA',
        Inventory.quantity > 0
    ).count()
    
    # 2. Calcola pallet a terra (quantità / pallet_quantity, arrotondato per eccesso)
    ground_results = db.query(
        Inventory.product_sku,
        Product.pallet_quantity,
        func.sum(Inventory.quantity).label("total_quantity")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name == 'TERRA',
        Inventory.quantity > 0
    ).group_by(Inventory.product_sku, Product.pallet_quantity).all()
    
    pallets_on_ground = 0
    products_analyzed = len(set([item.product_sku for item in db.query(
        Inventory.product_sku
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.quantity > 0
    ).all()]))
    
    for item in ground_results:
        pallet_qty = item.pallet_quantity if item.pallet_quantity and item.pallet_quantity > 0 else 1
        # CEIL per arrotondare per eccesso (29.1 → 30)
        pallets_for_sku = math.ceil(item.total_quantity / pallet_qty)
        pallets_on_ground += pallets_for_sku
    
    total_pallets = shelves_locations_count + pallets_on_ground
    
    return analysis_schemas.PalletSummary(
        total_pallets=total_pallets,
        pallets_on_ground=pallets_on_ground,
        pallets_in_shelves=shelves_locations_count,
        products_analyzed=products_analyzed
    )

@router.get("/pallet-details", response_model=analysis_schemas.PalletDetails)
def get_pallet_details(db: Session = Depends(get_db)):
    """Ottiene il dettaglio completo dei pallet per prodotto.
    Scaffali: conta ubicazioni occupate per SKU.
    Terra: CEIL(quantità / pallet_quantity)."""
    
    # Query per giacenze in scaffali: conta ubicazioni per SKU
    shelves_results = db.query(
        Inventory.product_sku,
        Product.description,
        Product.pallet_quantity,
        func.count(Inventory.id).label("locations_count"),
        func.sum(Inventory.quantity).label("quantity_in_shelves")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name != 'TERRA',
        Inventory.quantity > 0
    ).group_by(
        Inventory.product_sku, Product.description, Product.pallet_quantity
    ).all()
    
    # Query per giacenze a TERRA
    ground_results = db.query(
        Inventory.product_sku,
        Product.description,
        Product.pallet_quantity,
        func.sum(Inventory.quantity).label("quantity_on_ground")
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name == 'TERRA',
        Inventory.quantity > 0
    ).group_by(
        Inventory.product_sku, Product.description, Product.pallet_quantity
    ).all()
    
    # Creiamo mappe per facilitare l'aggregazione
    shelves_map = {item.product_sku: {
        'quantity': item.quantity_in_shelves,
        'locations_count': item.locations_count,
        'description': item.description,
        'pallet_quantity': item.pallet_quantity
    } for item in shelves_results}
    
    ground_map = {item.product_sku: {
        'quantity': item.quantity_on_ground,
        'description': item.description,  
        'pallet_quantity': item.pallet_quantity
    } for item in ground_results}
    
    # Combiniamo tutti i prodotti che hanno giacenza
    all_relevant_skus = set(shelves_map.keys()) | set(ground_map.keys())
    
    product_details = []
    summary_pallets = 0
    summary_pallets_ground = 0
    summary_pallets_shelves = 0
    
    for sku in all_relevant_skus:
        # Dati scaffali
        shelves_data = shelves_map.get(sku, {'quantity': 0, 'locations_count': 0, 'description': '', 'pallet_quantity': 0})
        ground_data = ground_map.get(sku, {'quantity': 0, 'description': '', 'pallet_quantity': 0})
        
        # Prendi descrizione e pallet_quantity dal primo disponibile
        description = shelves_data['description'] or ground_data['description'] or ''
        pallet_qty = shelves_data['pallet_quantity'] or ground_data['pallet_quantity'] or 0
        
        # Calcola quantità
        quantity_in_shelves = shelves_data['quantity']
        quantity_on_ground = ground_data['quantity']
        
        # Calcola pallet CORRETTAMENTE
        pallets_in_shelves = shelves_data['locations_count']  # Ogni ubicazione = 1 pallet
        
        # Pallet a terra: CEIL(quantità / pallet_quantity)
        if quantity_on_ground > 0:
            effective_pallet_qty = pallet_qty if pallet_qty > 0 else 1
            pallets_on_ground = math.ceil(quantity_on_ground / effective_pallet_qty)
        else:
            pallets_on_ground = 0
            
        pallets_total = pallets_in_shelves + pallets_on_ground
        
        # Aggiungi ai totali
        summary_pallets += pallets_total
        summary_pallets_ground += pallets_on_ground
        summary_pallets_shelves += pallets_in_shelves
        
        product_details.append(analysis_schemas.ProductPalletDetail(
            sku=sku,
            description=description,
            pallet_quantity=pallet_qty,
            pallets_on_ground=pallets_on_ground,
            pallets_in_shelves=pallets_in_shelves,
            pallets_total=pallets_total,
            quantity_on_ground=quantity_on_ground,
            quantity_in_shelves=quantity_in_shelves
        ))
    
    # Ordina per pallet totali decrescenti
    product_details.sort(key=lambda x: x.pallets_total, reverse=True)
    
    summary = analysis_schemas.PalletSummary(
        total_pallets=summary_pallets,
        pallets_on_ground=summary_pallets_ground,
        pallets_in_shelves=summary_pallets_shelves,
        products_analyzed=len(product_details)
    )
    
    return analysis_schemas.PalletDetails(
        summary=summary,
        products=product_details
    )

@router.get("/debug-location-count")
def debug_location_count(db: Session = Depends(get_db)):
    """Debug endpoint per confrontare i due conteggi ubicazioni."""
    
    # Query 1: Dashboard KPI (distinct location_name)
    dashboard_count = db.query(func.count(func.distinct(Inventory.location_name))).scalar() or 0
    
    # Query 2: Pallet Scaffali (count records con quantity > 0)
    pallet_count = db.query(Inventory).filter(
        Inventory.location_name != 'TERRA',
        Inventory.quantity > 0
    ).count()
    
    # Query 3: Distinct location_name con quantity > 0 (per vedere se è questo il problema)
    dashboard_with_qty_filter = db.query(func.count(func.distinct(Inventory.location_name))).filter(
        Inventory.location_name != 'TERRA',
        Inventory.quantity > 0
    ).scalar() or 0
    
    # Query 4: Trova ubicazioni con quantity = 0
    zero_qty_locations = db.query(Inventory.location_name).filter(
        Inventory.location_name != 'TERRA',
        Inventory.quantity == 0
    ).distinct().all()
    
    return {
        "dashboard_count": dashboard_count,
        "pallet_count": pallet_count,
        "dashboard_with_qty_filter": dashboard_with_qty_filter,
        "zero_quantity_locations_count": len(zero_qty_locations),
        "zero_quantity_locations": [loc[0] for loc in zero_qty_locations],
        "explanation": {
            "dashboard_query": "COUNT(DISTINCT location_name)",
            "pallet_query": "COUNT(*) WHERE quantity > 0",
            "difference": dashboard_count - pallet_count
        }
    }

@router.get("/products-on-ground", response_model=List[analysis_schemas.ProductInRowItem])
def get_products_on_ground(db: Session = Depends(get_db)):
    """Restituisce tutti i prodotti a TERRA."""
    products_query = db.query(
        Inventory.location_name,
        Inventory.product_sku,
        Product.description,
        Inventory.quantity
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name == 'TERRA',
        Inventory.quantity > 0
    ).order_by(Inventory.product_sku)
    
    products_on_ground = products_query.all()

    if not products_on_ground:
        raise HTTPException(status_code=404, detail="Nessun prodotto trovato a TERRA.")

    return [analysis_schemas.ProductInRowItem(
        location_name=item.location_name,
        product_sku=item.product_sku,
        product_description=item.description,
        quantity=item.quantity
    ) for item in products_on_ground]

@router.get("/export-products-on-ground-csv")
async def export_products_on_ground_csv(db: Session = Depends(get_db)):
    """Esporta i prodotti a TERRA in formato CSV."""
    products_data = get_products_on_ground(db)
    
    output = io.StringIO()
    output.write("ubicazione,sku,descrizione,quantita\n")
    for item in products_data:
        description = item.product_description.replace('"', '""') if item.product_description else ""
        if "," in description:
            description = f'"{description}"'
        output.write(f"{item.location_name},{item.product_sku},{description},{item.quantity}\n")
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prodotti_terra.csv"}
    )

@router.get("/export-products-on-ground-pdf")
async def export_products_on_ground_pdf(db: Session = Depends(get_db)):
    """Esporta i prodotti a TERRA in formato PDF."""
    # Query diretta per prodotti a TERRA
    products_query = db.query(
        Inventory.location_name,
        Inventory.product_sku,
        Product.description,
        Inventory.quantity
    ).join(Product, Inventory.product_sku == Product.sku).filter(
        Inventory.location_name == 'TERRA',
        Inventory.quantity > 0
    ).order_by(Inventory.product_sku)
    
    products_on_ground = products_query.all()

    if not products_on_ground:
        raise HTTPException(status_code=404, detail="Nessun prodotto trovato a TERRA.")

    # Converti in formato per PDF
    products_data = [{
        "location_name": item.location_name, 
        "product_sku": item.product_sku, 
        "product_description": item.description or "",
        "quantity": item.quantity
    } for item in products_on_ground]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Titolo
    story.append(Paragraph("Report Prodotti a TERRA", styles['h1']))
    story.append(Spacer(1, 0.2 * inch))

    # Calcola righe per pagina: circa 30 righe per tabella in layout 2-colonne
    max_rows_per_table = 25
    max_rows_per_page = max_rows_per_table * 2  # Due tabelle per pagina
    
    # Se i dati sono pochi, usa una sola tabella
    if len(products_data) <= max_rows_per_table:
        data = [["SKU", "Qty", "Note"]]
        for item in products_data:
            data.append([item["product_sku"], str(item["quantity"]), ""])

        table = Table(data, colWidths=[2*inch, 0.8*inch, 2.7*inch])
        table.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
            ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ])
        story.append(table)
    else:
        # Dividi in pagine con 2 colonne per pagina
        page_num = 1
        for i in range(0, len(products_data), max_rows_per_page):
            page_data = products_data[i:i + max_rows_per_page]
            
            # Se non è la prima pagina, aggiungi page break e titolo
            if i > 0:
                story.append(PageBreak())
                story.append(Paragraph(f"Report Prodotti a TERRA (Pag. {page_num})", styles['h2']))
                story.append(Spacer(1, 0.1 * inch))
            
            # Dividi i dati della pagina in due colonne
            mid_point = len(page_data) // 2
            left_products = page_data[:mid_point]
            right_products = page_data[mid_point:]

            # Prima tabella (sinistra)
            data1 = [["SKU", "Qty", "Note"]]
            for item in left_products:
                data1.append([item["product_sku"], str(item["quantity"]), ""])

            table1 = Table(data1, colWidths=[1.5*inch, 0.4*inch, 1.5*inch])
            table1.setStyle([
                ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ])

            # Seconda tabella (destra) - solo se ci sono dati
            if right_products:
                data2 = [["SKU", "Qty", "Note"]]
                for item in right_products:
                    data2.append([item["product_sku"], str(item["quantity"]), ""])

                table2 = Table(data2, colWidths=[1.5*inch, 0.4*inch, 1.5*inch])
                table2.setStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), '#f2f2f2'),
                    ('GRID', (0, 0), (-1, -1), 1, '#ddd'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                ])

                # Crea contenitore per affiancare le tabelle
                container_data = [[table1, "", table2]]
                container_table = Table(container_data, colWidths=[3.4*inch, 0.3*inch, 3.4*inch])
            else:
                # Se non ci sono dati per la seconda colonna, usa solo la prima
                container_data = [[table1, "", ""]]
                container_table = Table(container_data, colWidths=[3.4*inch, 0.3*inch, 3.4*inch])
            
            container_table.setStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ])
            story.append(container_table)
            
            page_num += 1

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(buffer.getvalue()),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=prodotti_terra.pdf"}
    )

@router.get("/export-total-stock-csv")
async def export_total_stock_csv(db: Session = Depends(get_db)):
    """Esporta tutta la giacenza del magazzino in formato CSV."""
    from datetime import datetime
    
    # Riusa la logica dell'endpoint /data per ottenere i dati aggregati
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
    
    # Prepara il CSV
    output = io.StringIO()
    
    # Intestazione CSV
    output.write("sku,descrizione,giacenza_scaffalata,giacenza_terra,giacenza_uscita,giacenza_totale\n")
    
    # Dati ordinati per SKU
    for sku in sorted(all_relevant_skus):
        quantity_in_shelves = shelves_map.get(sku, 0)
        quantity_on_ground = ground_map.get(sku, 0)
        quantity_outgoing = outgoing_map.get(sku, 0)
        total_quantity = quantity_in_shelves + quantity_on_ground + quantity_outgoing
        
        description = all_products.get(sku, "").replace('"', '""')  # Escape virgolette per CSV
        
        # Gestisci descrizioni con virgole mettendole tra virgolette
        if "," in description:
            description = f'"{description}"'
            
        output.write(f'{sku},{description},{quantity_in_shelves},{quantity_on_ground},{quantity_outgoing},{total_quantity}\n')
    
    output.seek(0)
    
    # Timestamp per nome file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=giacenza_totale_{timestamp}.csv"}
    )