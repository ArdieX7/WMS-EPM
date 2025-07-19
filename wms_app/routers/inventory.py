from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import Dict
from collections import defaultdict

from wms_app import models
from wms_app.schemas import inventory as inventory_schemas
from wms_app.database import get_db
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="wms_app/templates")

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
)

async def _parse_movement_file(file: UploadFile, db: Session) -> Dict[str, Dict[str, int]]:
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    lines = text_content.splitlines()
    parsed_data = defaultdict(lambda: defaultdict(int))
    current_location = None
    errors = []
    all_locations = {loc.name for loc in db.query(models.Location).all()}

    for i, line_content in enumerate(lines):
        line = line_content.strip()
        if not line:
            continue

        if line in all_locations:
            current_location = line
            continue
        
        if not current_location:
            errors.append(f"Riga {i+1}: Trovato EAN/SKU '{line}' senza un'ubicazione valida che lo preceda.")
            continue

        ean_or_sku = line
        quantity = 1

        if '_' in ean_or_sku:
            parts = ean_or_sku.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                ean_or_sku = parts[0]
                quantity = int(parts[1])
            else:
                errors.append(f"Riga {i+1}: Formato EAN/SKU_Quantità non valido: '{line}'")
                continue

        sku_found = None

        ean_code = db.query(models.EanCode).filter(models.EanCode.ean == ean_or_sku).first()
        if ean_code:
            sku_found = ean_code.product_sku
        else:
            product = db.query(models.Product).filter(models.Product.sku == ean_or_sku).first()
            if product:
                sku_found = product.sku

        if sku_found:
            parsed_data[current_location][sku_found] += quantity
        else:
            errors.append(f"Riga {i+1}: EAN/SKU '{ean_or_sku}' non trovato nel database.")

    if errors:
        raise HTTPException(status_code=400, detail="\n".join(errors))
        
    return parsed_data

@router.post("/add-stock-from-file")
async def add_stock_from_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        movements = await _parse_movement_file(file, db)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    if not movements:
        return JSONResponse(status_code=400, content={"detail": "Il file è vuoto o non contiene dati validi da elaborare."})

    processed_items = 0
    for location, skus in movements.items():
        for sku, qty_to_add in skus.items():
            inventory_item = db.query(models.Inventory).filter(
                models.Inventory.location_name == location,
                models.Inventory.product_sku == sku
            ).first()

            if inventory_item:
                inventory_item.quantity += qty_to_add
            else:
                new_item = models.Inventory(location_name=location, product_sku=sku, quantity=qty_to_add)
                db.add(new_item)
            processed_items += 1
    
    db.commit()
    return {"message": f"Carico completato con successo. Elaborati {processed_items} movimenti."}

@router.post("/subtract-stock-from-file")
async def subtract_stock_from_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        movements = await _parse_movement_file(file, db)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    if not movements:
        return JSONResponse(status_code=400, content={"detail": "Il file è vuoto o non contiene dati validi da elaborare."})

    processed_items = 0
    errors = []
    for location, skus in movements.items():
        for sku, qty_to_subtract in skus.items():
            inventory_item = db.query(models.Inventory).filter(
                models.Inventory.location_name == location,
                models.Inventory.product_sku == sku
            ).first()

            if not inventory_item or inventory_item.quantity < qty_to_subtract:
                current_qty = inventory_item.quantity if inventory_item else 0
                errors.append(f"Impossibile scaricare {qty_to_subtract} pz di {sku} da {location}. Giacenza attuale: {current_qty}.")
                continue

            inventory_item.quantity -= qty_to_subtract
            processed_items += 1
    
    if errors:
        db.rollback()
        raise HTTPException(status_code=400, detail="Operazione annullata. Errori di giacenza:\n" + "\n".join(errors))

    db.commit()
    return {"message": f"Scarico completato con successo. Elaborati {processed_items} movimenti."}

@router.post("/parse-realignment-file", response_model=inventory_schemas.StockParseResult)
async def parse_realignment_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    lines = text_content.splitlines()
    new_quantities = defaultdict(lambda: defaultdict(int))
    errors = []
    current_location = None

    for i, line_content in enumerate(lines):
        line_number = i + 1
        line = line_content.strip()
        if not line: continue

        db_location = db.query(models.Location).filter(models.Location.name == line).first()
        if db_location:
            current_location = line
            continue
        
        if not current_location:
            errors.append(inventory_schemas.StockParseError(line_number=line_number, line_content=line, error="EAN/SKU trovato senza un'ubicazione precedente valida."))
            continue

        ean_or_sku = line
        product = db.query(models.Product).join(models.EanCode, models.Product.sku == models.EanCode.product_sku, isouter=True).filter(
            (models.Product.sku == ean_or_sku) | (models.EanCode.ean == ean_or_sku)
        ).first()

        if product:
            new_quantities[current_location][product.sku] += 1
        else:
            errors.append(inventory_schemas.StockParseError(line_number=line_number, line_content=line, error=f"EAN/SKU '{ean_or_sku}' non trovato."))

    if errors and not new_quantities:
         raise HTTPException(status_code=400, detail=[e.dict() for e in errors])

    comparison_results = []
    all_locations_in_file = list(new_quantities.keys())
    existing_inventory = db.query(models.Inventory).filter(models.Inventory.location_name.in_(all_locations_in_file)).all()
    existing_map = {(item.location_name, item.product_sku): item.quantity for item in existing_inventory}

    for location, skus in new_quantities.items():
        for sku, new_qty in skus.items():
            current_qty = existing_map.get((location, sku), 0)
            status = "no_change"
            if current_qty < new_qty: status = "update"
            elif current_qty > new_qty: status = "update"
            if current_qty == 0 and new_qty > 0: status = "new"
            
            comparison_results.append(inventory_schemas.InventoryComparisonItem(location_name=location, product_sku=sku, current_quantity=current_qty, new_quantity=new_qty, status=status))
            existing_map.pop((location, sku), None)

    for (location, sku), current_qty in existing_map.items():
        comparison_results.append(inventory_schemas.InventoryComparisonItem(location_name=location, product_sku=sku, current_quantity=current_qty, new_quantity=0, status="delete_implicit"))

    return inventory_schemas.StockParseResult(items_to_commit=comparison_results, errors=errors)

@router.post("/commit-realignment")
async def commit_realignment(commit_data: inventory_schemas.StockCommitRequest, db: Session = Depends(get_db)):
    updated_count = 0
    for item in commit_data.items:
        if item.status == 'no_change':
            continue

        inventory_item = db.query(models.Inventory).filter(
            models.Inventory.product_sku == item.product_sku,
            models.Inventory.location_name == item.location_name
        ).first()

        if inventory_item:
            if item.new_quantity > 0:
                inventory_item.quantity = item.new_quantity
            else:
                db.delete(inventory_item)
        elif item.new_quantity > 0:
            inventory_item = models.Inventory(product_sku=item.product_sku, location_name=item.location_name, quantity=item.new_quantity)
            db.add(inventory_item)
        
        updated_count += 1

    db.commit()
    return {"message": f"Riallineamento giacenze completato per {updated_count} record."}

from fastapi.responses import StreamingResponse
import io

@router.get("/backup-stock")
async def backup_stock(db: Session = Depends(get_db)):
    """
    Crea un backup di tutte le giacenze di magazzino in un file di testo.
    Il formato è: ubicazione,sku,quantità
    """
    inventory_items = db.query(models.Inventory).filter(models.Inventory.quantity > 0).all()
    
    output = io.StringIO()
    for item in inventory_items:
        output.write(f"{item.location_name},{item.product_sku},{item.quantity}\n")
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=backup_giacenze.txt"}
    )

@router.post("/restore-stock")
async def restore_stock(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Ripristina la giacenza da un file di backup, sovrascrivendo tutti i dati esistenti.
    """
    try:
        # Svuota l'inventario attuale
        db.query(models.Inventory).delete()
        
        content = await file.read()
        lines = content.decode("utf-8").splitlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) != 3:
                continue # Ignora le righe malformattate
            
            location, sku, quantity = parts
            
            new_item = models.Inventory(
                location_name=location,
                product_sku=sku,
                quantity=int(quantity)
            )
            db.add(new_item)
            
        db.commit()
        return {"message": "Giacenza ripristinata con successo dal backup."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante il ripristino: {str(e)}")


@router.delete("/delete-all-stock", status_code=200)
async def delete_all_stock(db: Session = Depends(get_db)):
    """
    Elimina tutte le giacenze di magazzino.
    """
    try:
        num_rows_deleted = db.query(models.Inventory).delete()
        db.commit()
        return {"message": f"Tutte le {num_rows_deleted} giacenze sono state eliminate con successo."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'eliminazione delle giacenze: {str(e)}")


@router.delete("/delete-stock-by-row", status_code=200)
async def delete_stock_by_row(row_prefix: str, db: Session = Depends(get_db)):
    """
    Elimina le giacenze per un range di file specifico (es. 'A01').
    """
    if not row_prefix:
        raise HTTPException(status_code=400, detail="Il prefisso della fila non può essere vuoto.")
        
    try:
        # Trova le ubicazioni che iniziano con il prefisso della fila
        locations_to_delete = db.query(models.Location.name).filter(models.Location.name.like(f"{row_prefix}%")).all()
        location_names = [loc.name for loc in locations_to_delete]
        
        if not location_names:
            return {"message": f"Nessuna ubicazione trovata con prefisso '{row_prefix}'."}

        # Elimina le giacenze in quelle ubicazioni
        num_rows_deleted = db.query(models.Inventory).filter(models.Inventory.location_name.in_(location_names)).delete(synchronize_session=False)
        db.commit()
        
        return {"message": f"{num_rows_deleted} giacenze eliminate per la fila '{row_prefix}'."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'eliminazione delle giacenze per fila: {str(e)}")


@router.post("/update-stock")
async def update_stock(update_data: dict, db: Session = Depends(get_db)):
    """Aggiorna la giacenza di un prodotto in una specifica ubicazione (carico/scarico manuale)."""
    product_sku = update_data.get("product_sku")
    location_name = update_data.get("location_name")
    quantity_change = update_data.get("quantity")
    
    if not product_sku or not location_name or quantity_change is None:
        raise HTTPException(status_code=400, detail="SKU prodotto, ubicazione e quantità sono obbligatori.")
    
    # Verifica che il prodotto esista
    product = db.query(models.Product).filter(models.Product.sku == product_sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Prodotto con SKU '{product_sku}' non trovato.")
    
    # Verifica che l'ubicazione esista
    location = db.query(models.Location).filter(models.Location.name == location_name).first()
    if not location:
        raise HTTPException(status_code=404, detail=f"Ubicazione '{location_name}' non trovata.")
    
    # Trova o crea l'elemento di inventario
    inventory_item = db.query(models.Inventory).filter(
        models.Inventory.product_sku == product_sku,
        models.Inventory.location_name == location_name
    ).first()
    
    if inventory_item:
        new_quantity = inventory_item.quantity + quantity_change
        if new_quantity < 0:
            raise HTTPException(status_code=400, detail=f"Giacenza insufficiente. Attuale: {inventory_item.quantity}, richiesto: {abs(quantity_change)}")
        
        if new_quantity == 0:
            db.delete(inventory_item)
            action = "eliminato (giacenza zero)"
        else:
            inventory_item.quantity = new_quantity
            action = f"aggiornato a {new_quantity}"
    else:
        if quantity_change <= 0:
            raise HTTPException(status_code=400, detail="Impossibile scaricare da una giacenza inesistente.")
        
        inventory_item = models.Inventory(
            product_sku=product_sku,
            location_name=location_name,
            quantity=quantity_change
        )
        db.add(inventory_item)
        action = f"creato con giacenza {quantity_change}"
    
    db.commit()
    return {"message": f"Inventario {action} per {product_sku} in {location_name}."}

@router.post("/move-stock")
async def move_stock(move_data: dict, db: Session = Depends(get_db)):
    """Sposta giacenza da una ubicazione a un'altra."""
    product_sku = move_data.get("product_sku")
    from_location = move_data.get("from_location")
    to_location = move_data.get("to_location")
    quantity_to_move = move_data.get("quantity", 0)
    
    if not product_sku or not from_location or not to_location:
        raise HTTPException(status_code=400, detail="SKU prodotto, ubicazione di origine e destinazione sono obbligatori.")
    
    if from_location == to_location:
        raise HTTPException(status_code=400, detail="L'ubicazione di origine e destinazione non possono essere uguali.")
    
    # Verifica che il prodotto esista
    product = db.query(models.Product).filter(models.Product.sku == product_sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Prodotto con SKU '{product_sku}' non trovato.")
    
    # Verifica che entrambe le ubicazioni esistano
    from_loc = db.query(models.Location).filter(models.Location.name == from_location).first()
    to_loc = db.query(models.Location).filter(models.Location.name == to_location).first()
    if not from_loc:
        raise HTTPException(status_code=404, detail=f"Ubicazione di origine '{from_location}' non trovata.")
    if not to_loc:
        raise HTTPException(status_code=404, detail=f"Ubicazione di destinazione '{to_location}' non trovata.")
    
    # Trova l'elemento di inventario di origine
    from_inventory = db.query(models.Inventory).filter(
        models.Inventory.product_sku == product_sku,
        models.Inventory.location_name == from_location
    ).first()
    
    if not from_inventory or from_inventory.quantity <= 0:
        raise HTTPException(status_code=400, detail=f"Nessuna giacenza trovata per {product_sku} in {from_location}.")
    
    # Determina la quantità da spostare
    if quantity_to_move <= 0:
        quantity_to_move = from_inventory.quantity
    
    if quantity_to_move > from_inventory.quantity:
        raise HTTPException(status_code=400, detail=f"Quantità richiesta ({quantity_to_move}) supera la giacenza disponibile ({from_inventory.quantity}).")
    
    # Aggiorna l'origine
    from_inventory.quantity -= quantity_to_move
    if from_inventory.quantity == 0:
        db.delete(from_inventory)
    
    # Trova o crea l'elemento di inventario di destinazione
    to_inventory = db.query(models.Inventory).filter(
        models.Inventory.product_sku == product_sku,
        models.Inventory.location_name == to_location
    ).first()
    
    if to_inventory:
        to_inventory.quantity += quantity_to_move
    else:
        to_inventory = models.Inventory(
            product_sku=product_sku,
            location_name=to_location,
            quantity=quantity_to_move
        )
        db.add(to_inventory)
    
    db.commit()
    return {"message": f"Spostati {quantity_to_move} pz di {product_sku} da {from_location} a {to_location}."}

@router.get("/manage", response_class=HTMLResponse)
async def get_inventory_management_page(request: Request, db: Session = Depends(get_db)):
    inventory = db.query(models.Inventory).filter(models.Inventory.quantity > 0).options(joinedload(models.Inventory.product)).order_by(models.Inventory.location_name).all()
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "inventory": inventory,
        "active_page": "inventory"
    })