from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
import re
import io

from sqlalchemy import func
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import barcode
from barcode.writer import ImageWriter

from wms_app import models
from wms_app.database import get_db
from wms_app.routers.auth import require_permission
from wms_app.main import templates

router = APIRouter(
    prefix="/warehouse",
    tags=["warehouse"],
)

# Pydantic models for request bodies
class LocationRange(BaseModel):
    row_start: int
    row_end: int
    bay_start: int
    bay_end: int
    level_start: int
    level_end: int
    position_start: int
    position_end: int

class LocationsToDelete(BaseModel):
    locations: List[str]

class LabelGenerationRequest(BaseModel):
    fila: int
    campata_start: int
    campata_end: int


@router.get("/manage", response_class=HTMLResponse)
async def get_warehouse_management_page(request: Request, db: Session = Depends(get_db)):
    all_locations = db.query(models.Location).order_by(models.Location.name).all()
    
    # Recupera l'inventario per tutte le ubicazioni che hanno una quantità > 0
    inventory_details_query = db.query(
        models.Inventory.location_name,
        models.Inventory.product_sku,
        models.Inventory.quantity
    ).filter(models.Inventory.quantity > 0).all()

    # Raggruppa i dettagli per ubicazione
    inventory_by_location = {}
    for loc_name, sku, qty in inventory_details_query:
        if loc_name not in inventory_by_location:
            inventory_by_location[loc_name] = []
        inventory_by_location[loc_name].append(f"SKU: {sku}, Qta: {qty}")

    locations_by_row = {}
    for location in all_locations:
        import re
        match = re.match(r'^(\d+)', location.name)
        if not match:
            continue
        
        row_number = int(match.group(1))
        
        if row_number not in locations_by_row:
            locations_by_row[row_number] = []
        
        tooltip_text = "\n".join(inventory_by_location.get(location.name, []))
        
        locations_by_row[row_number].append({
            "name": location.name,
            "is_occupied": location.name in inventory_by_location,
            "is_available": location.available,
            "tooltip": tooltip_text
        })

    sorted_locations_by_row = dict(sorted(locations_by_row.items()))

    return templates.TemplateResponse("warehouse.html", {
        "request": request,
        "locations_by_row": sorted_locations_by_row,
        "active_page": "warehouse"
    })

@router.post("/add-location")
async def add_location(location_name: str = Form(...), db: Session = Depends(get_db)):
    if not location_name.strip():
        raise HTTPException(status_code=400, detail="Il nome dell'ubicazione non può essere vuoto.")
    
    # Conversione automatica in maiuscolo
    location_name = location_name.upper().strip()
    
    existing_location = db.query(models.Location).filter(models.Location.name == location_name).first()
    if existing_location:
        raise HTTPException(status_code=400, detail=f"L'ubicazione '{location_name}' esiste già.")

    new_location = models.Location(name=location_name)
    db.add(new_location)
    db.commit()
    
    return RedirectResponse(url="/warehouse/manage", status_code=303)

@router.post("/generate-locations")
async def generate_locations(
    row_start: int = Form(...), 
    row_end: int = Form(...), 
    bay_start: int = Form(...), 
    bay_end: int = Form(...), 
    level_start: int = Form(...), 
    level_end: int = Form(...), 
    position_start: int = Form(...), 
    position_end: int = Form(...), 
    db: Session = Depends(get_db)
):
    if not all([row_start > 0, row_end > 0, bay_start > 0, bay_end > 0, level_start > 0, level_end > 0, position_start > 0, position_end > 0]):
        raise HTTPException(status_code=400, detail="Tutti i valori devono essere maggiori di zero.")
    if row_start > row_end or bay_start > bay_end or level_start > level_end or position_start > position_end:
        raise HTTPException(status_code=400, detail="Il valore 'Da' non può essere maggiore del valore 'A'.")

    generated_count = 0
    for r in range(row_start, row_end + 1):
        for b in range(bay_start, bay_end + 1):
            for l in range(level_start, level_end + 1):
                for p in range(position_start, position_end + 1):
                    bay_char = chr(ord('A') + b - 1)
                    location_name = f"{r}{bay_char}{l}P{p}"
                    
                    existing_location = db.query(models.Location).filter(models.Location.name == location_name).first()
                    if not existing_location:
                        new_location = models.Location(name=location_name)
                        db.add(new_location)
                        generated_count += 1
    
    db.commit()
    # TODO: Aggiungere un messaggio flash per notificare l'utente del risultato.
    return RedirectResponse(url="/warehouse/manage", status_code=303)

@router.post("/preview-delete-locations")
async def preview_delete_locations(range_data: LocationRange, db: Session = Depends(get_db)):
    locations_to_check = []
    for r in range(range_data.row_start, range_data.row_end + 1):
        for b in range(range_data.bay_start, range_data.bay_end + 1):
            for l in range(range_data.level_start, range_data.level_end + 1):
                for p in range(range_data.position_start, range_data.position_end + 1):
                    bay_char = chr(ord('A') + b - 1)
                    location_name = f"{r}{bay_char}{l}P{p}"
                    locations_to_check.append(location_name)

    # Ubicazioni che esistono nel DB in base al range fornito
    existing_locations_q = db.query(models.Location.name).filter(models.Location.name.in_(locations_to_check)).all()
    existing_locations = {loc[0] for loc in existing_locations_q}

    # Ubicazioni occupate in quell'intervallo
    occupied_locations_q = db.query(models.Inventory.location_name)\
        .filter(models.Inventory.location_name.in_(existing_locations))\
        .filter(models.Inventory.quantity > 0)\
        .distinct().all()
    occupied_locations = {loc[0] for loc in occupied_locations_q}

    locations_to_delete = sorted(list(existing_locations - occupied_locations))
    locations_not_empty = sorted(list(occupied_locations))

    return JSONResponse(content={
        "locations_to_delete": locations_to_delete,
        "locations_not_empty": locations_not_empty
    })

@router.post("/commit-delete-locations")
async def commit_delete_locations(data: LocationsToDelete, db: Session = Depends(get_db)):
    if not data.locations:
        raise HTTPException(status_code=400, detail="Nessuna ubicazione da cancellare.")

    # Controlliamo di nuovo per sicurezza che le ubicazioni siano vuote
    occupied_locations_q = db.query(models.Inventory.location_name)\
        .filter(models.Inventory.location_name.in_(data.locations))\
        .filter(models.Inventory.quantity > 0)\
        .distinct().all()
    
    if occupied_locations_q:
        occupied_list = [loc[0] for loc in occupied_locations_q]
        raise HTTPException(status_code=400, detail=f"Impossibile cancellare. Le seguenti ubicazioni non sono vuote: {', '.join(occupied_list)}")

    db.query(models.Location).filter(models.Location.name.in_(data.locations)).delete(synchronize_session=False)
    db.commit()

    return JSONResponse(content={"message": "Ubicazioni cancellate con successo"}, status_code=200)

@router.post("/set-locations-availability")
async def set_locations_availability(
    row_start: int = Form(...),
    row_end: int = Form(...),
    bay_start: int = Form(...),
    bay_end: int = Form(...),
    level_start: int = Form(...),
    level_end: int = Form(...),
    position_start: int = Form(...),
    position_end: int = Form(...),
    available: bool = Form(...),
    db: Session = Depends(get_db)
):
    """
    Imposta la disponibilità di un range di ubicazioni.
    available=True per renderle disponibili, False per non disponibili.
    """
    # Genera la lista delle ubicazioni nel range specificato
    locations_to_update = []
    
    for row in range(row_start, row_end + 1):
        for bay_num in range(bay_start, bay_end + 1):
            # Converti il numero della campata in lettera (1=A, 2=B, etc.)
            bay_letter = chr(ord('A') + bay_num - 1)
            for level in range(level_start, level_end + 1):
                for position in range(position_start, position_end + 1):
                    location_name = f"{row}{bay_letter}{level}P{position}"
                    locations_to_update.append(location_name)
    
    if not locations_to_update:
        raise HTTPException(status_code=400, detail="Nessuna ubicazione trovata nel range specificato.")
    
    # Aggiorna la disponibilità delle ubicazioni esistenti
    updated_count = db.query(models.Location).filter(
        models.Location.name.in_(locations_to_update)
    ).update(
        {"available": available}, 
        synchronize_session=False
    )
    
    db.commit()
    
    status_text = "disponibili" if available else "non disponibili"
    return JSONResponse(content={
        "message": f"{updated_count} ubicazioni rese {status_text}",
        "updated_count": updated_count,
        "total_specified": len(locations_to_update)
    })

@router.post("/preview-availability-change")
async def preview_availability_change(range_data: LocationRange, db: Session = Depends(get_db)):
    """
    Anteprima delle ubicazioni che verrebbero modificate nella disponibilità
    """
    # Genera la lista delle ubicazioni nel range specificato
    locations_in_range = []
    
    for row in range(range_data.row_start, range_data.row_end + 1):
        for bay_num in range(range_data.bay_start, range_data.bay_end + 1):
            # Converti il numero della campata in lettera (1=A, 2=B, etc.)
            bay_letter = chr(ord('A') + bay_num - 1)
            for level in range(range_data.level_start, range_data.level_end + 1):
                for position in range(range_data.position_start, range_data.position_end + 1):
                    location_name = f"{row}{bay_letter}{level}P{position}"
                    locations_in_range.append(location_name)
    
    # Verifica quali di queste ubicazioni esistono nel database
    existing_locations_q = db.query(models.Location.name, models.Location.available).filter(
        models.Location.name.in_(locations_in_range)
    ).all()
    
    existing_locations = {loc.name: loc.available for loc in existing_locations_q}
    
    # Separa per stato attuale
    available_locations = [name for name, avail in existing_locations.items() if avail]
    unavailable_locations = [name for name, avail in existing_locations.items() if not avail]
    non_existing_locations = [name for name in locations_in_range if name not in existing_locations]
    
    return JSONResponse(content={
        "total_in_range": len(locations_in_range),
        "existing_count": len(existing_locations),
        "available_locations": sorted(available_locations),
        "unavailable_locations": sorted(unavailable_locations),
        "non_existing_locations": sorted(non_existing_locations)
    })


# ==================== GENERAZIONE ETICHETTE ====================

def parse_location(location_name: str) -> Tuple[int, str, int, int]:
    """
    Parsa il nome ubicazione nel formato {FILA}{LETTERA}{PIANO}P{POSIZIONE}
    Es: "1A1P3" -> (1, 'A', 1, 3)
    Returns: (fila, lettera, piano, posizione)
    """
    match = re.match(r'^(\d+)([A-Z])(\d+)P(\d+)$', location_name)
    if not match:
        raise ValueError(f"Formato ubicazione non valido: {location_name}")

    fila = int(match.group(1))
    lettera = match.group(2)
    piano = int(match.group(3))
    posizione = int(match.group(4))

    return fila, lettera, piano, posizione


def group_locations_by_campata(locations: List[str]) -> Dict[Tuple[int, str], Dict[int, List[Tuple[int, str]]]]:
    """
    Raggruppa le ubicazioni per campata e poi per piano.
    Returns: {(fila, lettera): {piano: [(posizione, location_name), ...]}}
    Esempio: {(1, 'A'): {1: [(1, '1A1P1'), (2, '1A1P2')], 2: [(1, '1A2P1'), ...]}}
    """
    grouped = {}

    for loc_name in locations:
        try:
            fila, lettera, piano, posizione = parse_location(loc_name)
            campata_key = (fila, lettera)

            if campata_key not in grouped:
                grouped[campata_key] = {}

            if piano not in grouped[campata_key]:
                grouped[campata_key][piano] = []

            grouped[campata_key][piano].append((posizione, loc_name))
        except ValueError:
            continue

    # Ordina le posizioni in ogni piano
    for campata_key in grouped:
        for piano in grouped[campata_key]:
            grouped[campata_key][piano].sort()

    return grouped


def generate_barcode_image(location_name: str) -> io.BytesIO:
    """
    Genera un'immagine barcode Code128 per l'ubicazione.
    Returns: BytesIO con l'immagine PNG del barcode
    """
    code128 = barcode.get_barcode_class('code128')
    barcode_instance = code128(location_name, writer=ImageWriter())

    buffer = io.BytesIO()
    barcode_instance.write(buffer, options={
        'module_width': 0.3,
        'module_height': 12,
        'quiet_zone': 2,
        'font_size': 0,  # Nascondi il testo sotto il barcode
        'text_distance': 1,
        'write_text': False
    })
    buffer.seek(0)

    return buffer


def generate_labels_pdf(grouped_locations: Dict[Tuple[int, str], Dict[int, List[Tuple[int, str]]]]) -> io.BytesIO:
    """
    Genera un PDF con le etichette disposte in 2 colonne (2 piani per foglio).
    Layout: A4, 2 colonne, ogni colonna = 1 piano con posizioni verticali
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    # Margini e dimensioni
    margin = 1 * cm
    column_width = (page_width - 3 * margin) / 2  # 2 colonne con spazio centrale

    # Per ogni campata, crea fogli accoppiando i piani a 2 a 2
    sorted_campate = sorted(grouped_locations.items())

    first_page = True

    for campata_key, piani_dict in sorted_campate:
        fila, lettera = campata_key

        # Ordina i piani e crea coppie (1-2, 3-4, 5-6, ...)
        sorted_piani = sorted(piani_dict.items())
        piano_pairs = []

        for i in range(0, len(sorted_piani), 2):
            piano1 = sorted_piani[i]
            piano2 = sorted_piani[i + 1] if i + 1 < len(sorted_piani) else None
            piano_pairs.append((piano1, piano2))

        # Genera un foglio per ogni coppia di piani
        for piano1, piano2 in piano_pairs:
            if not first_page:
                c.showPage()
            first_page = False

            # Calcola il numero massimo di posizioni tra i due piani
            max_positions_1 = len(piano1[1]) if piano1 else 0
            max_positions_2 = len(piano2[1]) if piano2 else 0
            max_positions = max(max_positions_1, max_positions_2)

            # Calcola l'altezza di ogni cella (posizione)
            available_height = page_height - 2 * margin
            cell_height = available_height / max_positions if max_positions > 0 else available_height

            # Disegna le etichette per il piano 1 (colonna sinistra)
            if piano1:
                _draw_piano_labels(c, campata_key, piano1, margin, margin,
                                  column_width, cell_height, page_height, max_positions)

            # Disegna le etichette per il piano 2 (colonna destra)
            if piano2:
                _draw_piano_labels(c, campata_key, piano2, margin * 2 + column_width,
                                  margin, column_width, cell_height, page_height, max_positions)

    c.save()
    buffer.seek(0)
    return buffer


def _draw_piano_labels(c: canvas.Canvas, campata_key: Tuple[int, str], piano_data: Tuple[int, List],
                       x: float, y_base: float, width: float, cell_height: float,
                       page_height: float, max_positions: int):
    """
    Disegna le etichette per un singolo piano in una colonna.
    Disposizione: P1 in basso → P4 in alto (come nella realtà fisica)

    Args:
        campata_key: (fila, lettera)
        piano_data: (piano_num, [(posizione, location_name), ...])
        x: posizione X della colonna
        y_base: margine base
        width: larghezza colonna
        cell_height: altezza di ogni cella
        page_height: altezza pagina
        max_positions: numero massimo posizioni per allineamento
    """
    piano_num, positions = piano_data

    # Disegna bordo esterno della colonna
    total_height = cell_height * len(positions)
    y_column_bottom = y_base
    c.rect(x, y_column_bottom, width, total_height)

    # Ordina le posizioni: P1, P2, P3, P4 (dal basso verso l'alto)
    sorted_positions = sorted(positions, key=lambda p: p[0])  # Ordina per numero posizione

    # Disegna ogni posizione dal basso verso l'alto
    for idx, (pos_num, location_name) in enumerate(sorted_positions):
        # Calcola Y: primo elemento (P1) in basso, ultimo (P4) in alto
        y_bottom = y_column_bottom + (idx * cell_height)
        y_top = y_bottom + cell_height

        # Testo ubicazione (grande, centrato verticalmente)
        text_y = y_bottom + cell_height * 0.6
        c.setFont("Helvetica-Bold", 36)
        text_width = c.stringWidth(location_name, "Helvetica-Bold", 36)
        text_x = x + (width - text_width) / 2
        c.drawString(text_x, text_y, location_name)

        # Barcode (in basso, centrato orizzontalmente)
        try:
            barcode_buffer = generate_barcode_image(location_name)
            barcode_image = ImageReader(barcode_buffer)
            barcode_width = width * 0.8
            barcode_height = cell_height * 0.3
            barcode_x = x + (width - barcode_width) / 2
            barcode_y = y_bottom + cell_height * 0.05

            c.drawImage(barcode_image, barcode_x, barcode_y,
                       width=barcode_width, height=barcode_height,
                       preserveAspectRatio=True, mask='auto')
        except Exception as e:
            # Se il barcode fallisce, logga l'errore
            print(f"Errore generazione barcode per {location_name}: {e}")
            pass

        # Linea separatrice orizzontale (tra posizioni, tranne dopo l'ultima)
        if idx < len(sorted_positions) - 1:
            c.line(x, y_top, x + width, y_top)


@router.post("/generate-labels-pdf")
async def generate_labels_pdf_endpoint(
    request_data: LabelGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    Genera PDF con etichette per le campate specificate.
    Input: fila, campata_start (1=A, 2=B, ...), campata_end
    """
    # Validazione input
    if request_data.campata_start < 1 or request_data.campata_end < 1:
        raise HTTPException(status_code=400, detail="Le campate devono essere >= 1")
    if request_data.campata_start > request_data.campata_end:
        raise HTTPException(status_code=400, detail="Campata iniziale deve essere <= campata finale")
    if request_data.fila < 1:
        raise HTTPException(status_code=400, detail="La fila deve essere >= 1")

    # Converti i numeri delle campate in lettere
    campate_letters = []
    for campata_num in range(request_data.campata_start, request_data.campata_end + 1):
        letter = chr(ord('A') + campata_num - 1)
        campate_letters.append(letter)

    # Query per trovare tutte le ubicazioni che corrispondono al pattern
    # Pattern: {fila}{lettera}{piano}P{posizione}
    all_locations = db.query(models.Location.name).all()
    matching_locations = []

    for loc in all_locations:
        loc_name = loc[0]
        try:
            fila, lettera, piano, posizione = parse_location(loc_name)
            if fila == request_data.fila and lettera in campate_letters:
                matching_locations.append(loc_name)
        except ValueError:
            continue

    if not matching_locations:
        raise HTTPException(
            status_code=404,
            detail=f"Nessuna ubicazione trovata per Fila {request_data.fila}, Campate {campate_letters}"
        )

    # Raggruppa per campata
    grouped = group_locations_by_campata(matching_locations)

    # Genera PDF
    pdf_buffer = generate_labels_pdf(grouped)

    # Nome file
    campate_range = f"{campate_letters[0]}-{campate_letters[-1]}" if len(campate_letters) > 1 else campate_letters[0]
    filename = f"etichette_fila{request_data.fila}_campate{campate_range}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
