from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from sqlalchemy import func

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
