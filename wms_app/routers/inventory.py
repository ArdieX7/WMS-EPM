from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import Dict
from collections import defaultdict

from wms_app import models
from wms_app.schemas import inventory as inventory_schemas
from wms_app.database import get_db
from wms_app.routers.auth import require_permission
from wms_app.services.logging_service import LoggingService
from wms_app.models.logs import OperationType, OperationCategory, OperationStatus
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

# Nuovo endpoint per parsing carico con recap e validazioni
@router.post("/parse-add-stock-file")
async def parse_add_stock_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Analizza un file di carico e restituisce un recap delle operazioni da effettuare con validazioni.
    """
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    lines = text_content.splitlines()
    recap_items = []
    errors = []
    warnings = []
    current_location = None
    locations_with_content = set()  # Traccia ubicazioni che hanno EAN/SKU
    all_locations = {loc.name for loc in db.query(models.Location).all()}
    found_locations = []  # Traccia tutte le ubicazioni trovate nel file
    
    # CORREZIONE BUG: Dizionario per consolidare quantità per (ubicazione, sku)
    consolidated_operations = {}  # {(location, sku): {'quantity': total, 'lines': [line_numbers], 'input_codes': [codes]}}

    for i, line_content in enumerate(lines):
        line = line_content.strip()
        if not line:
            continue

        # Controlla se è una ubicazione
        if line in all_locations:
            current_location = line
            found_locations.append({"location": line, "line": i+1})
            continue
        
        if not current_location:
            errors.append({
                "line": i+1,
                "type": "missing_location",
                "message": f"Riga {i+1}: Trovato EAN/SKU '{line}' senza un'ubicazione valida che lo preceda.",
                "ean_sku": line,
                "location": "",
                "quantity": 1
            })
            continue

        # Marca che questa ubicazione ha contenuto
        locations_with_content.add(current_location)

        # Parse EAN/SKU e quantità
        ean_or_sku = line
        quantity = 1

        if '_' in ean_or_sku:
            parts = ean_or_sku.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                ean_or_sku = parts[0]
                quantity = int(parts[1])
            else:
                errors.append({
                    "line": i+1,
                    "type": "invalid_format",
                    "message": f"Riga {i+1}: Formato EAN/SKU_Quantità non valido: '{line}'",
                    "ean_sku": ean_or_sku,
                    "location": current_location,
                    "quantity": quantity
                })
                continue

        # Trova SKU dal database
        sku_found = None
        product_description = ""

        ean_code = db.query(models.EanCode).filter(models.EanCode.ean == ean_or_sku).first()
        if ean_code:
            sku_found = ean_code.product_sku
            product = db.query(models.Product).filter(models.Product.sku == sku_found).first()
            product_description = product.description if product else ""
        else:
            product = db.query(models.Product).filter(models.Product.sku == ean_or_sku).first()
            if product:
                sku_found = product.sku
                product_description = product.description

        if not sku_found:
            errors.append({
                "line": i+1,
                "type": "product_not_found",
                "message": f"Riga {i+1}: EAN/SKU '{ean_or_sku}' non trovato nel database.",
                "ean_sku": ean_or_sku,
                "location": current_location,
                "quantity": quantity
            })
            continue

        # Controlla unicità SKU per ubicazione (ECCEZIONE: TERRA può contenere SKU multipli)
        existing_inventory = None
        if current_location != "TERRA":
            existing_inventory = db.query(models.Inventory).filter(
                models.Inventory.location_name == current_location,
                models.Inventory.product_sku != sku_found,
                models.Inventory.quantity > 0
            ).first()

        current_inventory = db.query(models.Inventory).filter(
            models.Inventory.location_name == current_location,
            models.Inventory.product_sku == sku_found
        ).first()

        current_qty = current_inventory.quantity if current_inventory else 0
        new_qty = current_qty + quantity

        # CORREZIONE BUG: Consolida quantità invece di creare entry duplicate
        operation_key = (current_location, sku_found)
        
        if operation_key in consolidated_operations:
            # Aggiungi alla quantità esistente
            consolidated_operations[operation_key]['quantity'] += quantity
            consolidated_operations[operation_key]['lines'].append(i+1)
            consolidated_operations[operation_key]['input_codes'].append(ean_or_sku)
        else:
            # Crea nuova entry consolidata
            consolidated_operations[operation_key] = {
                'quantity': quantity,
                'lines': [i+1],
                'input_codes': [ean_or_sku],
                'location': current_location,
                'sku': sku_found,
                'description': product_description,
                'existing_inventory': existing_inventory
            }

    # CORREZIONE BUG: Converti operazioni consolidate in recap_items
    for (location, sku), operation_data in consolidated_operations.items():
        # Ricalcola giacenze con quantità consolidata
        current_inventory = db.query(models.Inventory).filter(
            models.Inventory.location_name == location,
            models.Inventory.product_sku == sku
        ).first()
        
        current_qty = current_inventory.quantity if current_inventory else 0
        consolidated_quantity = operation_data['quantity']
        new_qty = current_qty + consolidated_quantity
        
        # Controlla conflitti per l'operazione consolidata
        existing_inventory = operation_data['existing_inventory']
        if existing_inventory:
            warnings.append({
                "line": operation_data['lines'][0],  # Prima riga che ha causato il conflitto
                "type": "location_conflict", 
                "message": f"CONFLITTO: Ubicazione '{location}' contiene già '{existing_inventory.product_sku}'. Una ubicazione può contenere solo un tipo di prodotto.",
                "ean_sku": operation_data['input_codes'][0],
                "location": location,
                "quantity": consolidated_quantity,
                "conflicting_sku": existing_inventory.product_sku
            })
        
        # Crea recap item consolidato
        recap_items.append({
            "line": operation_data['lines'][0],  # Prima riga per riferimento
            "location": location,
            "sku": sku,
            "description": operation_data['description'],
            "input_code": ", ".join(operation_data['input_codes']),  # Mostra tutti i codici usati
            "quantity_to_add": consolidated_quantity,
            "current_quantity": current_qty,
            "new_quantity": new_qty,
            "status": "warning" if existing_inventory else "ok",
            "consolidated_from_lines": operation_data['lines'],  # Per debug
            "consolidated_quantity": consolidated_quantity  # Per evidenziare il consolidamento
        })

    # Aggiungi ubicazioni senza EAN/SKU come operazioni manuali
    for loc_info in found_locations:
        location = loc_info["location"]
        if location not in locations_with_content:
            warnings.append({
                "line": loc_info["line"],
                "type": "empty_location",
                "message": f"Ubicazione '{location}' trovata senza EAN/SKU. Inserisci manualmente i dati nel recap.",
                "ean_sku": "",
                "location": location,
                "quantity": 0
            })
            
            # Aggiungi entry nel recap per inserimento manuale
            recap_items.append({
                "line": loc_info["line"],
                "location": location,
                "sku": "",  # Vuoto per inserimento manuale
                "description": "",
                "input_code": "",
                "quantity_to_add": 0,  # Sarà inserito manualmente
                "current_quantity": 0,
                "new_quantity": 0,
                "status": "manual_input",  # Nuovo stato per inserimento manuale
                "needs_input": True  # Flag per identificare righe che necessitano input
            })

    return {
        "recap_items": recap_items,
        "errors": errors,
        "warnings": warnings,
        "total_operations": len(recap_items)
    }

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
        # AUTO-DISPONIBILITÀ: Rendi disponibile l'ubicazione se stiamo aggiungendo stock
        location_obj = db.query(models.Location).filter(models.Location.name == location).first()
        if location_obj and not location_obj.available:
            location_obj.available = True
        
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

# Nuovo endpoint per parsing scarico con recap e validazioni
@router.post("/parse-subtract-stock-file")
async def parse_subtract_stock_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Analizza un file di scarico e restituisce un recap delle operazioni da effettuare con validazioni.
    """
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    lines = text_content.splitlines()
    recap_items = []
    errors = []
    warnings = []
    current_location = None
    locations_with_content = set()  # Traccia ubicazioni che hanno EAN/SKU
    all_locations = {loc.name for loc in db.query(models.Location).all()}
    found_locations = []  # Traccia tutte le ubicazioni trovate nel file
    
    # CORREZIONE BUG: Dizionario per consolidare quantità per (ubicazione, sku)
    consolidated_operations = {}  # {(location, sku): {'quantity': total, 'lines': [line_numbers], 'input_codes': [codes]}}

    for i, line_content in enumerate(lines):
        line = line_content.strip()
        if not line:
            continue

        # Controlla se è una ubicazione
        if line in all_locations:
            current_location = line
            found_locations.append({"location": line, "line": i+1})
            continue
        
        if not current_location:
            errors.append({
                "line": i+1,
                "type": "missing_location",
                "message": f"Riga {i+1}: Trovato EAN/SKU '{line}' senza un'ubicazione valida che lo preceda.",
                "ean_sku": line,
                "location": "",
                "quantity": 1
            })
            continue

        # Marca che questa ubicazione ha contenuto
        locations_with_content.add(current_location)

        # Parse EAN/SKU e quantità
        ean_or_sku = line
        quantity = 1

        if '_' in ean_or_sku:
            parts = ean_or_sku.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                ean_or_sku = parts[0]
                quantity = int(parts[1])
            else:
                errors.append({
                    "line": i+1,
                    "type": "invalid_format",
                    "message": f"Riga {i+1}: Formato EAN/SKU_Quantità non valido: '{line}'",
                    "ean_sku": ean_or_sku,
                    "location": current_location,
                    "quantity": quantity
                })
                continue

        # Trova SKU dal database
        sku_found = None
        product_description = ""

        ean_code = db.query(models.EanCode).filter(models.EanCode.ean == ean_or_sku).first()
        if ean_code:
            sku_found = ean_code.product_sku
            product = db.query(models.Product).filter(models.Product.sku == sku_found).first()
            product_description = product.description if product else ""
        else:
            product = db.query(models.Product).filter(models.Product.sku == ean_or_sku).first()
            if product:
                sku_found = product.sku
                product_description = product.description

        if not sku_found:
            errors.append({
                "line": i+1,
                "type": "product_not_found",
                "message": f"Riga {i+1}: EAN/SKU '{ean_or_sku}' non trovato nel database.",
                "ean_sku": ean_or_sku,
                "location": current_location,
                "quantity": quantity
            })
            continue

        # Controlla giacenza disponibile
        current_inventory = db.query(models.Inventory).filter(
            models.Inventory.location_name == current_location,
            models.Inventory.product_sku == sku_found
        ).first()

        current_qty = current_inventory.quantity if current_inventory else 0
        new_qty = current_qty - quantity

        status = "ok"
        if current_qty < quantity:
            warnings.append({
                "line": i+1,
                "type": "insufficient_stock",
                "message": f"GIACENZA INSUFFICIENTE: Tentativo di scaricare {quantity} pz di '{sku_found}' da '{current_location}'. Disponibile: {current_qty}",
                "ean_sku": ean_or_sku,
                "location": current_location,
                "quantity": quantity,
                "available": current_qty
            })
            status = "error"

        # CORREZIONE BUG: Consolida quantità invece di creare entry duplicate per scarico
        operation_key = (current_location, sku_found)
        
        if operation_key in consolidated_operations:
            # Aggiungi alla quantità esistente
            consolidated_operations[operation_key]['quantity'] += quantity
            consolidated_operations[operation_key]['lines'].append(i+1)
            consolidated_operations[operation_key]['input_codes'].append(ean_or_sku)
            # Aggiorna status se c'è un errore
            if status == "error":
                consolidated_operations[operation_key]['status'] = status
        else:
            # Crea nuova entry consolidata
            consolidated_operations[operation_key] = {
                'quantity': quantity,
                'lines': [i+1],
                'input_codes': [ean_or_sku],
                'location': current_location,
                'sku': sku_found,
                'description': product_description,
                'status': status
            }

    # CORREZIONE BUG: Converti operazioni consolidate in recap_items per scarico
    for (location, sku), operation_data in consolidated_operations.items():
        # Ricalcola giacenze con quantità consolidata
        current_inventory = db.query(models.Inventory).filter(
            models.Inventory.location_name == location,
            models.Inventory.product_sku == sku
        ).first()
        
        current_qty = current_inventory.quantity if current_inventory else 0
        consolidated_quantity = operation_data['quantity']
        new_qty = max(0, current_qty - consolidated_quantity)
        
        # Verifica se la quantità consolidata supera la giacenza disponibile
        status = operation_data['status']
        if current_qty < consolidated_quantity:
            errors.append({
                "line": operation_data['lines'][0],  # Prima riga che ha causato l'errore
                "type": "insufficient_stock",
                "message": f"GIACENZA INSUFFICIENTE: Tentativo di scaricare {consolidated_quantity} pz di '{sku}' da '{location}'. Disponibile: {current_qty}",
                "ean_sku": operation_data['input_codes'][0],
                "location": location,
                "quantity": consolidated_quantity,
                "available": current_qty
            })
            status = "error"
        
        # Crea recap item consolidato per scarico
        recap_items.append({
            "line": operation_data['lines'][0],  # Prima riga per riferimento
            "location": location,
            "sku": sku,
            "description": operation_data['description'],
            "input_code": ", ".join(operation_data['input_codes']),  # Mostra tutti i codici usati
            "quantity_to_subtract": consolidated_quantity,
            "current_quantity": current_qty,
            "new_quantity": new_qty,
            "status": status,
            "consolidated_from_lines": operation_data['lines'],  # Per debug
            "consolidated_quantity": consolidated_quantity  # Per evidenziare il consolidamento
        })

    # Aggiungi ubicazioni senza EAN/SKU come operazioni manuali
    for loc_info in found_locations:
        location = loc_info["location"]
        if location not in locations_with_content:
            warnings.append({
                "line": loc_info["line"],
                "type": "empty_location",
                "message": f"Ubicazione '{location}' trovata senza EAN/SKU. Inserisci manualmente i dati nel recap.",
                "ean_sku": "",
                "location": location,
                "quantity": 0
            })
            
            # Aggiungi entry nel recap per inserimento manuale
            recap_items.append({
                "line": loc_info["line"],
                "location": location,
                "sku": "",  # Vuoto per inserimento manuale
                "description": "",
                "input_code": "",
                "quantity_to_subtract": 0,  # Sarà inserito manualmente
                "current_quantity": 0,
                "new_quantity": 0,
                "status": "manual_input",  # Nuovo stato per inserimento manuale
                "needs_input": True  # Flag per identificare righe che necessitano input
            })

    return {
        "recap_items": recap_items,
        "errors": errors,
        "warnings": warnings,
        "total_operations": len(recap_items)
    }

# Endpoint di commit per operazioni validate
@router.post("/commit-file-operations")
async def commit_file_operations(operations_data: dict, db: Session = Depends(get_db)):
    """
    Esegue le operazioni validate dal recap con controlli finali di sicurezza.
    """
    operations = operations_data.get("operations", [])
    operation_type = operations_data.get("type")  # "add" o "subtract"
    
    if not operations:
        raise HTTPException(status_code=400, detail="Nessuna operazione da eseguire.")
    
    # VALIDAZIONE FINALE: Controlla conflitti di ubicazione prima del commit
    location_conflicts = {}
    for op in operations:
        location = op.get("location")
        sku = op.get("sku")
        
        if not location_conflicts.get(location):
            location_conflicts[location] = set()
        location_conflicts[location].add(sku)
    
    # Trova ubicazioni con più SKU (ECCEZIONE: TERRA può contenere SKU multipli)
    conflicts = []
    for location, skus in location_conflicts.items():
        if len(skus) > 1 and location != "TERRA":
            conflicts.append(f"Ubicazione '{location}' contiene più SKU: {', '.join(skus)}")
    
    if conflicts:
        raise HTTPException(
            status_code=400, 
            detail="❌ OPERAZIONE BLOCCATA - Conflitti di ubicazione rilevati:\n\n" + "\n".join(conflicts) + 
                   "\n\nUna ubicazione può contenere solo un tipo di prodotto. Correggi i conflitti e riprova."
        )
    
    # VALIDAZIONE FINALE: Controlla anche conflitti con giacenze esistenti per il carico
    if operation_type == "add":
        for op in operations:
            location = op.get("location")
            sku = op.get("sku")
            
            # Controlla se l'ubicazione contiene già un SKU diverso (ECCEZIONE: TERRA può contenere SKU multipli)
            if location != "TERRA":
                existing_inventory = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku != sku,
                    models.Inventory.quantity > 0
                ).first()
                
                if existing_inventory:
                    raise HTTPException(
                        status_code=400,
                        detail=f"❌ CONFLITTO RILEVATO: Ubicazione '{location}' contiene già il prodotto '{existing_inventory.product_sku}'. "
                               f"Non è possibile aggiungere '{sku}' nella stessa ubicazione."
                    )
        
    processed_items = 0
    errors = []
    
    try:
        for op in operations:
            if op.get("status") == "error":
                continue  # Salta operazioni con errori
                
            location = op.get("location")
            sku = op.get("sku")
            quantity = op.get("quantity_to_add" if operation_type == "add" else "quantity_to_subtract")
            
            if operation_type == "add":
                # AUTO-DISPONIBILITÀ per carico
                location_obj = db.query(models.Location).filter(models.Location.name == location).first()
                if location_obj and not location_obj.available:
                    location_obj.available = True
                
                inventory_item = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku == sku
                ).first()

                if inventory_item:
                    inventory_item.quantity += quantity
                else:
                    new_item = models.Inventory(location_name=location, product_sku=sku, quantity=quantity)
                    db.add(new_item)
                    
            elif operation_type == "subtract":
                inventory_item = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku == sku
                ).first()

                if inventory_item and inventory_item.quantity >= quantity:
                    inventory_item.quantity -= quantity
                    if inventory_item.quantity == 0:
                        db.delete(inventory_item)
                else:
                    current_qty = inventory_item.quantity if inventory_item else 0
                    errors.append(f"Impossibile scaricare {quantity} pz di {sku} da {location}. Giacenza attuale: {current_qty}.")
                    continue
                    
            processed_items += 1
    
        if errors:
            db.rollback()
            raise HTTPException(status_code=400, detail="Operazione parzialmente fallita:\n" + "\n".join(errors))
        
        # LOGGING: Registra le operazioni da file come batch
        logger = LoggingService(db)
        
        # Determina tipo operazione per logging
        log_operation_type = OperationType.CARICO_FILE if operation_type == "add" else OperationType.SCARICO_FILE
        
        # Prepara operazioni per batch logging
        batch_operations = []
        for op in operations:
            if op.get("status") != "error":  # Solo operazioni riuscite
                batch_operations.append({
                    'product_sku': op.get("sku"),
                    'location_from': op.get("location") if operation_type == "subtract" else None,
                    'location_to': op.get("location") if operation_type == "add" else None,
                    'quantity': op.get("quantity_to_add" if operation_type == "add" else "quantity_to_subtract"),
                    'status': OperationStatus.SUCCESS,
                    'line_number': op.get("line", 0),
                    'details': {
                        'input_code': op.get("input_code", ""),
                        'previous_quantity': op.get("current_quantity", 0),
                        'new_quantity': op.get("new_quantity", 0),
                        'operation_type': operation_type,
                        'consolidated_quantity': op.get("consolidated_quantity")
                    }
                })
        
        # Registra operazioni file senza log batch start/end
        if batch_operations:
            # Ottieni nome file dalla prima operazione o usa default più descrittivo
            file_name = operations_data.get('file_name')
            if not file_name or file_name == 'uploaded_file.txt':
                # Genera nome descrittivo basato sul tipo operazione e timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_name = f"{operation_type}_operations_{timestamp}.txt"
            
            logger.log_file_operations(
                operation_type=log_operation_type,
                operation_category=OperationCategory.FILE,
                operations=batch_operations,
                file_name=file_name,
                user_id="file_user"  # TODO: Sostituire con sistema auth reale
            )
        
        db.commit()
        operation_name = "Carico" if operation_type == "add" else "Scarico"
        return {"message": f"{operation_name} completato con successo. Elaborate {processed_items} operazioni."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'operazione: {str(e)}")

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
    if location_name:
        location_name = location_name.upper()  # Conversione automatica in maiuscolo
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
    
    # CONTROLLO UNICITÀ: Una ubicazione può contenere solo un SKU (ECCEZIONE: TERRA può contenere SKU multipli)
    if location_name != "TERRA":
        existing_inventory_in_location = db.query(models.Inventory).filter(
            models.Inventory.location_name == location_name,
            models.Inventory.product_sku != product_sku,
            models.Inventory.quantity > 0
        ).first()
        
        if existing_inventory_in_location:
            if quantity_change > 0:
                # Errore per carico in ubicazione occupata da altro prodotto
                raise HTTPException(
                    status_code=400, 
                    detail=f"Ubicazione '{location_name}' contiene già il prodotto '{existing_inventory_in_location.product_sku}' (quantità: {existing_inventory_in_location.quantity}). Una ubicazione può contenere solo un tipo di prodotto."
                )
            elif quantity_change < 0:
                # Errore per scarico quando si cerca un prodotto diverso da quello presente
                raise HTTPException(
                    status_code=400,
                detail=f"Impossibile scaricare '{product_sku}' dall'ubicazione '{location_name}'. L'ubicazione contiene '{existing_inventory_in_location.product_sku}' (quantità: {existing_inventory_in_location.quantity})."
            )
    
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
    
    # AUTO-DISPONIBILITÀ: Se stiamo aggiungendo stock (quantity_change > 0) in un'ubicazione
    # non disponibile, rendila automaticamente disponibile
    if quantity_change > 0 and not location.available:
        location.available = True
        action += " - ubicazione resa automaticamente disponibile"
    
    # LOGGING: Registra l'operazione prima del commit
    logger = LoggingService(db)
    operation_type = OperationType.CARICO_MANUALE if quantity_change > 0 else OperationType.SCARICO_MANUALE
    
    # Cattura stato precedente per logging
    previous_quantity = inventory_item.quantity - quantity_change if inventory_item and hasattr(inventory_item, 'quantity') else 0
    new_quantity = previous_quantity + quantity_change if previous_quantity + quantity_change >= 0 else 0
    
    logger.log_operation(
        operation_type=operation_type,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        product_sku=product_sku,
        location_to=location_name if quantity_change > 0 else None,
        location_from=location_name if quantity_change < 0 else None,
        quantity=abs(quantity_change),
        user_id="manual_user",  # TODO: Sostituire con sistema auth reale
        details={
            "operation": "manual_stock_update",
            "quantity_change": quantity_change,
            "previous_quantity": previous_quantity,
            "new_quantity": new_quantity,
            "action_performed": action,
            "location_made_available": quantity_change > 0 and not location.available
        },
        api_endpoint="/inventory/update-stock"
    )
    
    db.commit()
    return {"message": f"Inventario {action} per {product_sku} in {location_name}."}

@router.post("/move-stock")
async def move_stock(move_data: dict, db: Session = Depends(get_db)):
    """Sposta giacenza da una ubicazione a un'altra."""
    product_sku = move_data.get("product_sku")
    from_location = move_data.get("from_location")
    if from_location:
        from_location = from_location.upper()  # Conversione automatica in maiuscolo
    to_location = move_data.get("to_location")
    if to_location:
        to_location = to_location.upper()  # Conversione automatica in maiuscolo
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
    
    # CONTROLLO UNICITÀ: Verifica se l'ubicazione di destinazione contiene già un altro SKU (ECCEZIONE: TERRA può contenere SKU multipli)
    if to_location != "TERRA":
        existing_inventory_in_destination = db.query(models.Inventory).filter(
            models.Inventory.location_name == to_location,
            models.Inventory.product_sku != product_sku,
            models.Inventory.quantity > 0
        ).first()
        
        if existing_inventory_in_destination:
            # Rollback della modifica all'origine prima di lanciare l'errore
            from_inventory.quantity += quantity_to_move
            raise HTTPException(
                status_code=400, 
                detail=f"Ubicazione di destinazione '{to_location}' contiene già il prodotto '{existing_inventory_in_destination.product_sku}'. Una ubicazione può contenere solo un tipo di prodotto."
            )
    
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
    
    # LOGGING: Registra l'operazione di spostamento
    logger = LoggingService(db)
    
    # Calcola quantità precedenti per logging
    from_previous_quantity = from_inventory.quantity + quantity_to_move  # Quantità prima dello spostamento
    to_previous_quantity = to_inventory.quantity - quantity_to_move if to_inventory and hasattr(to_inventory, 'quantity') else 0
    
    logger.log_operation(
        operation_type=OperationType.SPOSTAMENTO_MANUALE,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        product_sku=product_sku,
        location_from=from_location,
        location_to=to_location,
        quantity=quantity_to_move,
        user_id="manual_user",  # TODO: Sostituire con sistema auth reale
        details={
            "operation": "manual_stock_movement",
            "from_previous_quantity": from_previous_quantity,
            "from_new_quantity": from_inventory.quantity if from_inventory in db else 0,
            "to_previous_quantity": to_previous_quantity,
            "to_new_quantity": to_inventory.quantity,
            "from_location_cleared": from_inventory.quantity == 0,
            "to_location_created": to_previous_quantity == 0
        },
        api_endpoint="/inventory/move-stock"
    )
    
    db.commit()
    return {"message": f"Spostati {quantity_to_move} pz di {product_sku} da {from_location} a {to_location}."}

@router.post("/parse-movements-file")
async def parse_movements_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Analizza un file di spostamenti e restituisce un recap delle operazioni da effettuare con validazioni.
    Il file contiene ubicazioni alternate: origine, destinazione, origine, destinazione...
    """
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    recap_items = []
    errors = []
    warnings = []
    all_locations = {loc.name for loc in db.query(models.Location).all()}
    
    # Simula l'inventario progressivo per validare l'ordine degli spostamenti
    simulated_inventory = {}
    original_inventory = {}  # Mantiene lo stato originale per controlli
    
    # Carica l'inventario attuale nei simulatori
    current_inventory = db.query(models.Inventory).filter(models.Inventory.quantity > 0).all()
    for item in current_inventory:
        inventory_data = {
            'sku': item.product_sku,
            'quantity': item.quantity
        }
        simulated_inventory[item.location_name] = inventory_data.copy()
        original_inventory[item.location_name] = inventory_data.copy()
    
    # Verifica che il numero di righe sia pari
    if len(lines) % 2 != 0:
        errors.append({
            "line": len(lines),
            "type": "odd_lines",
            "message": f"Il file deve contenere un numero pari di righe (coppie origine-destinazione). Trovate {len(lines)} righe.",
            "from_location": "",
            "to_location": "",
        })
        return {
            "recap_items": recap_items,
            "errors": errors,
            "warnings": warnings,
            "total_operations": 0
        }
    
    # Processa le coppie di ubicazioni
    for i in range(0, len(lines), 2):
        move_number = (i // 2) + 1
        from_location = lines[i]
        to_location = lines[i + 1]
        
        # Verifica che entrambe le ubicazioni esistano
        if from_location not in all_locations:
            errors.append({
                "line": i + 1,
                "type": "invalid_location",
                "message": f"Spostamento {move_number}: Ubicazione di origine '{from_location}' non trovata.",
                "from_location": from_location,
                "to_location": to_location,
            })
            continue
            
        if to_location not in all_locations:
            errors.append({
                "line": i + 2,
                "type": "invalid_location", 
                "message": f"Spostamento {move_number}: Ubicazione di destinazione '{to_location}' non trovata.",
                "from_location": from_location,
                "to_location": to_location,
            })
            continue
        
        # Controlla se l'ubicazione di origine ha giacenza nell'inventario ORIGINALE
        # Questo è importante per capire cosa c'era realmente in quella posizione all'inizio
        origin_inventory = original_inventory.get(from_location)
        if not origin_inventory or origin_inventory['quantity'] <= 0:
            errors.append({
                "line": i + 1,
                "type": "no_stock",
                "message": f"Spostamento {move_number}: Nessuna giacenza trovata nell'ubicazione di origine '{from_location}' nell'inventario iniziale.",
                "from_location": from_location,
                "to_location": to_location,
            })
            continue
        
        # Controlla conflitti nell'ubicazione di destinazione
        destination_inventory = simulated_inventory.get(to_location)
        has_conflict = (destination_inventory and 
                       destination_inventory['quantity'] > 0 and 
                       destination_inventory['sku'] != origin_inventory['sku'])
        
        if has_conflict:
            warnings.append({
                "line": i + 2,
                "type": "destination_conflict",
                "message": f"CONFLITTO Spostamento {move_number}: Destinazione '{to_location}' contiene già '{destination_inventory['sku']}', si vuole spostare '{origin_inventory['sku']}'.",
                "from_location": from_location,
                "to_location": to_location,
                "existing_sku": destination_inventory['sku'],
                "moving_sku": origin_inventory['sku']
            })
        
        # Crea l'item del recap
        recap_items.append({
            "move_number": move_number,
            "line_from": i + 1,
            "line_to": i + 2,
            "from_location": from_location,
            "to_location": to_location,
            "sku": origin_inventory['sku'],
            "quantity": origin_inventory['quantity'],
            "status": "warning" if has_conflict else "ok"
        })
        
        # Aggiorna i simulatori per il prossimo spostamento
        # Rimuovi dall'origine in entrambi gli inventari (è stata spostata)
        if from_location in simulated_inventory:
            del simulated_inventory[from_location]
        if from_location in original_inventory:
            del original_inventory[from_location]
        
        # Per la destinazione nel simulatore: se c'è conflitto, il prodotto esistente verrà sovrascritto
        # Ma se non c'è conflitto (stesso SKU), aggiungi la quantità
        if to_location in simulated_inventory and simulated_inventory[to_location]['sku'] == origin_inventory['sku']:
            # Stesso SKU: somma le quantità
            simulated_inventory[to_location]['quantity'] += origin_inventory['quantity']
        else:
            # SKU diverso o ubicazione vuota: sostituisci completamente
            simulated_inventory[to_location] = {
                'sku': origin_inventory['sku'],
                'quantity': origin_inventory['quantity']
            }
            
        # NON aggiorniamo original_inventory per la destinazione - mantiene lo stato iniziale

    return {
        "recap_items": recap_items,
        "errors": errors,
        "warnings": warnings,
        "total_operations": len(recap_items)
    }

@router.post("/commit-movements")
async def commit_movements(movements_data: dict, db: Session = Depends(get_db)):
    """
    Esegue gli spostamenti validati dal recap in ordine sequenziale.
    """
    movements = movements_data.get("movements", [])
    
    if not movements:
        raise HTTPException(status_code=400, detail="Nessuno spostamento da eseguire.")
    
    processed_movements = 0
    errors = []
    batch_operations = []  # Per logging
    
    try:
        # Processa i movimenti in ordine
        for movement in movements:
            if movement.get("status") == "error":
                continue  # Salta movimenti con errori
                
            from_location = movement.get("from_location")
            to_location = movement.get("to_location")
            
            # Trova l'inventario di origine
            from_inventory = db.query(models.Inventory).filter(
                models.Inventory.location_name == from_location,
                models.Inventory.quantity > 0
            ).first()
            
            if not from_inventory:
                errors.append(f"Spostamento {movement.get('move_number')}: Nessuna giacenza trovata in '{from_location}'")
                continue
            
            product_sku = from_inventory.product_sku
            quantity_to_move = from_inventory.quantity
            
            # Raccogli dati per logging PRIMA di modificare l'inventario
            batch_operations.append({
                'product_sku': product_sku,
                'location_from': from_location,
                'location_to': to_location,
                'quantity': quantity_to_move,
                'status': OperationStatus.SUCCESS,
                'line_number': movement.get("move_number", 0),
                'details': {
                    'move_number': movement.get("move_number"),
                    'movement_type': 'file_movement',
                    'operation_description': f"Spostamento #{movement.get('move_number')}: {product_sku} da {from_location} a {to_location}"
                }
            })
            
            # Verifica conflitti nella destinazione (controllo finale)
            existing_in_destination = db.query(models.Inventory).filter(
                models.Inventory.location_name == to_location,
                models.Inventory.product_sku != product_sku,
                models.Inventory.quantity > 0
            ).first()
            
            if existing_in_destination:
                # Se c'è un conflitto ma l'utente ha confermato, sovrascriviamo
                # Elimina il contenuto esistente nella destinazione
                db.delete(existing_in_destination)
            
            # Rimuovi dall'origine
            db.delete(from_inventory)
            
            # Trova o crea nella destinazione
            to_inventory = db.query(models.Inventory).filter(
                models.Inventory.location_name == to_location,
                models.Inventory.product_sku == product_sku
            ).first()
            
            if to_inventory:
                to_inventory.quantity += quantity_to_move
            else:
                to_inventory = models.Inventory(
                    location_name=to_location,
                    product_sku=product_sku,
                    quantity=quantity_to_move
                )
                db.add(to_inventory)
            
            processed_movements += 1
        
        if errors:
            db.rollback()
            raise HTTPException(status_code=400, detail="Operazione fallita:\\n" + "\\n".join(errors))
        
        # LOGGING: Registra le operazioni di spostamento
        logger = LoggingService(db)
        
        # Registra spostamenti file senza log batch start/end
        if batch_operations:
            file_name = movements_data.get('file_name', 'movements_file.txt')
            logger.log_file_operations(
                operation_type=OperationType.SPOSTAMENTO_FILE,
                operation_category=OperationCategory.FILE,
                operations=batch_operations,
                file_name=file_name,
                user_id="file_user"
            )
        
        db.commit()
        return {"message": f"Spostamenti completati con successo. Elaborati {processed_movements} movimenti."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante gli spostamenti: {str(e)}")

@router.get("/get-current-quantity/{sku}/{location}")
async def get_current_quantity(sku: str, location: str, db: Session = Depends(get_db)):
    """Recupera la giacenza attuale per un SKU in una specifica ubicazione."""
    inventory_item = db.query(models.Inventory).filter(
        models.Inventory.product_sku == sku,
        models.Inventory.location_name == location
    ).first()
    
    current_quantity = inventory_item.quantity if inventory_item else 0
    
    return {
        "sku": sku,
        "location": location,
        "current_quantity": current_quantity
    }

@router.get("/manage", response_class=HTMLResponse)
async def get_inventory_management_page(request: Request, db: Session = Depends(get_db)):
    inventory = db.query(models.Inventory).filter(models.Inventory.quantity > 0).options(joinedload(models.Inventory.product)).order_by(models.Inventory.location_name).all()
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "inventory": inventory,
        "active_page": "inventory"
    })

@router.post("/unload-container-manual")
async def unload_container_manual(unload_data: dict, db: Session = Depends(get_db)):
    """
    Scarica un prodotto dal container posizionandolo a TERRA.
    """
    sku = unload_data.get("sku")
    quantity = unload_data.get("quantity", 0)
    
    if not sku or quantity <= 0:
        raise HTTPException(status_code=400, detail="SKU e quantità sono richiesti e validi")
    
    # Verifica che il prodotto esista
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Prodotto con SKU '{sku}' non trovato")
    
    # Trova o crea l'inventario a TERRA (auto-consolida se esistono record multipli)
    existing_ground_records = db.query(models.Inventory).filter(
        models.Inventory.product_sku == sku,
        models.Inventory.location_name == "TERRA"
    ).all()
    
    if existing_ground_records:
        # Se esistono record, consolida tutto nel primo e rimuovi gli altri
        primary_record = existing_ground_records[0]
        total_existing = sum(record.quantity for record in existing_ground_records)
        
        # Aggiorna il primo record con la quantità totale + nuova quantità
        primary_record.quantity = total_existing + quantity
        
        # Rimuovi tutti gli altri record duplicati
        for record in existing_ground_records[1:]:
            db.delete(record)
    else:
        # Crea nuovo record
        ground_inventory = models.Inventory(
            product_sku=sku,
            location_name="TERRA",
            quantity=quantity
        )
        db.add(ground_inventory)
    
    # LOGGING: Registra l'operazione di scarico container
    logger = LoggingService(db)
    
    # Calcola quantità precedente
    previous_quantity = sum(record.quantity for record in existing_ground_records) if existing_ground_records else 0
    new_quantity = previous_quantity + quantity
    
    logger.log_operation(
        operation_type=OperationType.SCARICO_CONTAINER_MANUALE,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        product_sku=sku,
        location_to="TERRA",
        quantity=quantity,
        user_id="manual_user",  # TODO: Sostituire con sistema auth reale
        details={
            "operation": "manual_container_unload",
            "previous_quantity_at_terra": previous_quantity,
            "new_quantity_at_terra": new_quantity,
            "records_consolidated": len(existing_ground_records) if existing_ground_records else 0,
            "auto_consolidation_performed": len(existing_ground_records) > 1
        },
        api_endpoint="/inventory/unload-container-manual"
    )
    
    db.commit()
    return {"message": f"Scaricati {quantity} pz di '{sku}' a TERRA dal container."}

@router.post("/parse-unload-container-file")
async def parse_unload_container_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Analizza il file di scarico container e restituisce un recap per conferma utente.
    Formato: SKU (1 pezzo) o SKU_QTY (QTY pezzi)
    """
    try:
        content = await file.read()
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")
    except Exception as e:
        print(f"DEBUG: Error reading file: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Errore lettura file: {str(e)}")

    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    
    if not lines:
        raise HTTPException(status_code=400, detail="Il file è vuoto.")
    
    # ANALISI FILE: Consolida le quantità per SKU
    sku_quantities = {}
    sku_original_codes = {}  # Mappa SKU -> primo codice originale trovato
    errors = []
    warnings = []
    recap_items = []
    
    for line_num, line in enumerate(lines, 1):
        # Parse SKU e quantità
        if '_' in line:
            parts = line.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                sku = parts[0]
                quantity = int(parts[1])
            else:
                sku = line
                quantity = 1
        else:
            sku = line
            quantity = 1
        
        if quantity <= 0:
            errors.append({
                'line': line_num,
                'input': line,
                'error': f"Quantità non valida per '{line}'"
            })
            continue
        
        # Verifica che il prodotto esista - supporta sia EAN code che SKU
        sku_found = None
        product = None
        input_code = sku  # Conserva il codice originale dal file per il logging
        
        # Prima prova a cercare come EAN code
        ean_code = db.query(models.EanCode).filter(models.EanCode.ean == sku).first()
        if ean_code:
            sku_found = ean_code.product_sku
            product = db.query(models.Product).filter(models.Product.sku == sku_found).first()
        else:
            # Altrimenti prova a cercare come SKU diretto
            product = db.query(models.Product).filter(models.Product.sku == sku).first()
            if product:
                sku_found = product.sku
        
        if not product or not sku_found:
            errors.append({
                'line': line_num,
                'input': line,
                'error': f"Prodotto con codice '{sku}' non trovato (né come EAN né come SKU)"
            })
            continue
            
        # Usa lo SKU risolto per il resto della logica
        sku = sku_found
        
        # Traccia il primo codice originale per questo SKU (per il recap)
        if sku not in sku_original_codes:
            sku_original_codes[sku] = input_code
            
        # Accumula quantità per SKU
        sku_quantities[sku] = sku_quantities.get(sku, 0) + quantity

    # Crea recap items per ogni SKU consolidato
    for sku, total_quantity in sku_quantities.items():
        # Trova descrizione prodotto
        product = db.query(models.Product).filter(models.Product.sku == sku).first()
        description = product.description if product else "Descrizione non disponibile"
        
        # Trova giacenza attuale a TERRA
        existing_ground_records = db.query(models.Inventory).filter(
            models.Inventory.product_sku == sku,
            models.Inventory.location_name == "TERRA"
        ).all()
        
        current_quantity = sum(record.quantity for record in existing_ground_records)
        new_quantity = current_quantity + total_quantity
        
        recap_items.append({
            'line': f"Consolidato da {len([k for k in sku_quantities.keys() if k == sku])} righe",
            'input_code': sku_original_codes.get(sku, sku),  # Mostra il codice originale (EAN o SKU)
            'sku': sku,
            'location': 'TERRA',
            'description': description,
            'quantity_to_add': total_quantity,
            'current_quantity': current_quantity,
            'new_quantity': new_quantity,
            'status': 'ok',
            'consolidated_quantity': total_quantity
        })
        
        # Aggiungi warning se ci sono record duplicati esistenti
        if len(existing_ground_records) > 1:
            warnings.append({
                'message': f"TERRA contiene {len(existing_ground_records)} record duplicati per '{sku}' (verranno consolidati automaticamente)",
                'sku': sku,
                'location': 'TERRA'
            })

    result = {
        'recap_items': recap_items,
        'errors': errors,
        'warnings': warnings,
        'total_items': len(recap_items),
        'total_pieces': sum(sku_quantities.values()) if sku_quantities else 0,
        'file_analysis': {
            'total_lines': len(lines),
            'valid_lines': len(lines) - len(errors),
            'unique_skus': len(sku_quantities),
            'consolidated_items': len(recap_items)
        }
    }
    
    return result

@router.post("/commit-unload-container-operations")
async def commit_unload_container_operations(operations_data: dict, db: Session = Depends(get_db)):
    """
    Esegue le operazioni di scarico container validate dal recap.
    """
    operations = operations_data.get("operations", [])
    
    if not operations:
        raise HTTPException(status_code=400, detail="Nessuna operazione da eseguire.")
    
    processed_items = 0
    errors = []
    
    try:
        for op in operations:
            if op.get("status") == "error":
                continue  # Salta operazioni con errori
                
            sku = op.get("sku")
            quantity_to_add = op.get("quantity_to_add")
            
            # Trova tutti i record esistenti a TERRA per questo SKU
            existing_ground_records = db.query(models.Inventory).filter(
                models.Inventory.product_sku == sku,
                models.Inventory.location_name == "TERRA"
            ).all()
            
            if existing_ground_records:
                # Consolida tutti i record esistenti + nuova quantità nel primo record
                primary_record = existing_ground_records[0]
                total_existing = sum(record.quantity for record in existing_ground_records)
                
                # Aggiorna il primo record con la quantità totale esistente + nuova quantità
                primary_record.quantity = total_existing + quantity_to_add
                
                # Rimuovi tutti gli altri record duplicati
                for record in existing_ground_records[1:]:
                    db.delete(record)
            else:
                # Crea nuovo record con quantità consolidata
                ground_inventory = models.Inventory(
                    product_sku=sku,
                    location_name="TERRA",
                    quantity=quantity_to_add
                )
                db.add(ground_inventory)
            
            processed_items += 1
        
        if errors:
            db.rollback()
            raise HTTPException(status_code=400, detail="Operazione parzialmente fallita:\\n" + "\\n".join(errors))
        
        # LOGGING: Registra le operazioni di scarico container da file
        logger = LoggingService(db)
        
        # Crea operazioni di log consolidate
        batch_operations = []
        for op in operations:
            if op.get("status") != "error":
                batch_operations.append({
                    'product_sku': op.get("sku"),
                    'location_from': None,  # Dal container
                    'location_to': 'TERRA',
                    'quantity': op.get("quantity_to_add"),
                    'status': OperationStatus.SUCCESS,
                    'details': {
                        'operation_description': f"Scarico container: {op.get('sku')} ({op.get('quantity_to_add')} pz) a TERRA",
                        'source': 'container_unload_file',
                        'consolidated_quantity': op.get("consolidated_quantity")
                    }
                })
        
        # Registra operazioni senza log batch start/end
        if batch_operations:
            file_name = operations_data.get('file_name', 'container_unload.txt')
            logger.log_file_operations(
                operation_type=OperationType.SCARICO_FILE,
                operation_category=OperationCategory.FILE,
                operations=batch_operations,
                file_name=file_name,
                user_id="file_user"
            )
        
        db.commit()
        total_pieces = sum(op.get("quantity_to_add", 0) for op in operations if op.get("status") != "error")
        return {"message": f"Scarico container completato. Processati {processed_items} SKU per un totale di {total_pieces} pezzi a TERRA."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'operazione: {str(e)}")

@router.post("/relocate-from-ground-manual")
async def relocate_from_ground_manual(relocate_data: dict, db: Session = Depends(get_db)):
    """
    Sposta un prodotto dalla TERRA a una ubicazione specifica.
    """
    sku = relocate_data.get("sku")
    quantity = relocate_data.get("quantity", 0)
    location = relocate_data.get("location")
    
    if not sku or quantity <= 0 or not location:
        raise HTTPException(status_code=400, detail="SKU, quantità e ubicazione sono richiesti e validi")
    
    location = location.upper()
    
    # Verifica che l'ubicazione esista
    location_exists = db.query(models.Location).filter(models.Location.name == location).first()
    if not location_exists:
        raise HTTPException(status_code=404, detail=f"Ubicazione '{location}' non trovata")
    
    
    # Trova TUTTI i record dello stesso SKU a TERRA e calcola il totale
    ground_inventory_records = db.query(models.Inventory).filter(
        models.Inventory.product_sku == sku,
        models.Inventory.location_name == "TERRA"
    ).all()
    
    total_available = sum(record.quantity for record in ground_inventory_records)
    
    if total_available < quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Giacenza insufficiente a TERRA per '{sku}'. Richiesti: {quantity}, Disponibili: {total_available}"
        )
    
    # Verifica che l'ubicazione di destinazione non contenga già un altro prodotto (ECCEZIONE: TERRA può contenere SKU multipli)
    if location != "TERRA":
        existing_inventory = db.query(models.Inventory).filter(
            models.Inventory.location_name == location,
            models.Inventory.product_sku != sku,
            models.Inventory.quantity > 0
        ).first()
        
        if existing_inventory:
            raise HTTPException(
                status_code=400,
                detail=f"L'ubicazione '{location}' contiene già il prodotto '{existing_inventory.product_sku}'. Una ubicazione può contenere solo un tipo di prodotto."
            )
    
    # Rimuovi dalla TERRA - gestisce record multipli dello stesso SKU
    remaining_to_remove = quantity
    for record in ground_inventory_records:
        if remaining_to_remove <= 0:
            break
        
        if record.quantity <= remaining_to_remove:
            # Rimuovi tutto il record
            remaining_to_remove -= record.quantity
            db.delete(record)
        else:
            # Rimuovi parzialmente
            record.quantity -= remaining_to_remove
            remaining_to_remove = 0
    
    # Trova o crea nell'ubicazione di destinazione
    destination_inventory = db.query(models.Inventory).filter(
        models.Inventory.product_sku == sku,
        models.Inventory.location_name == location
    ).first()
    
    if destination_inventory:
        destination_inventory.quantity += quantity
    else:
        destination_inventory = models.Inventory(
            product_sku=sku,
            location_name=location,
            quantity=quantity
        )
        db.add(destination_inventory)
    
    # LOGGING: Registra lo spostamento da TERRA
    logger = LoggingService(db)
    logger.log_operation(
        operation_type=OperationType.SPOSTAMENTO_MANUALE,
        operation_category=OperationCategory.MANUAL,
        status=OperationStatus.SUCCESS,
        product_sku=sku,
        location_from="TERRA",
        location_to=location,
        quantity=quantity,
        user_id="manual_user",
        details={
            'operation_description': f"Ubicazione da TERRA: {sku} ({quantity} pz) da TERRA a {location}",
            'total_available': total_available,
            'movement_type': 'ground_to_location'
        }
    )
    
    db.commit()
    return {"message": f"Spostati {quantity} pz di '{sku}' da TERRA a '{location}'."}

@router.post("/parse-relocate-from-ground-file")
async def parse_relocate_from_ground_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Analizza il file di ubicazione da terra e restituisce un recap per conferma utente.
    Formato: Ubicazione, SKU o SKU_QTY
    """
    try:
        movements = await _parse_movement_file(file, db)
    except HTTPException as e:
        raise e

    if not movements:
        raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi da elaborare.")

    # ANALISI MOVIMENTI: Verifica e prepara recap
    recap_items = []
    errors = []
    warnings = []
    total_operations = 0
    
    for location, skus in movements.items():
        # Verifica che l'ubicazione esista
        location_exists = db.query(models.Location).filter(models.Location.name == location).first()
        if not location_exists:
            for sku in skus.keys():
                errors.append({
                    'line': total_operations + 1,
                    'input': f"{location} -> {sku}",
                    'error': f"Ubicazione '{location}' non trovata"
                })
            total_operations += len(skus)
            continue
            
        # Verifica conflitti ubicazione (non può contenere SKU diversi)
        if location != "TERRA":
            existing_inventory = db.query(models.Inventory).filter(
                models.Inventory.location_name == location,
                models.Inventory.quantity > 0
            ).all()
            
            if existing_inventory:
                existing_skus = [inv.product_sku for inv in existing_inventory]
                new_skus = list(skus.keys())
                
                # Se l'ubicazione contiene già prodotti diversi da quelli che vogliamo inserire
                conflicting_skus = [sku for sku in existing_skus if sku not in new_skus]
                if conflicting_skus:
                    for sku in new_skus:
                        errors.append({
                            'line': total_operations + 1,
                            'input': f"{location} -> {sku}",
                            'error': f"Ubicazione '{location}' contiene già altri prodotti: {', '.join(conflicting_skus)}"
                        })
                        total_operations += 1
                    continue
        
        for sku, quantity in skus.items():
            total_operations += 1
            
            # Verifica che il prodotto esista
            product = db.query(models.Product).filter(models.Product.sku == sku).first()
            if not product:
                errors.append({
                    'line': total_operations,
                    'input': f"{location} -> {sku}",
                    'error': f"Prodotto '{sku}' non trovato"
                })
                continue
            
            # Verifica giacenza a TERRA
            ground_inventory_records = db.query(models.Inventory).filter(
                models.Inventory.product_sku == sku,
                models.Inventory.location_name == "TERRA"
            ).all()
            
            ground_quantity = sum(record.quantity for record in ground_inventory_records)
            
            if ground_quantity < quantity:
                errors.append({
                    'line': total_operations,
                    'input': f"{location} -> {sku}_{quantity}",
                    'error': f"Giacenza insufficiente a TERRA per '{sku}'. Richiesti: {quantity}, Disponibili: {ground_quantity}"
                })
                continue
            
            # Verifica giacenza destinazione
            destination_inventory = db.query(models.Inventory).filter(
                models.Inventory.product_sku == sku,
                models.Inventory.location_name == location
            ).first()
            
            current_destination_qty = destination_inventory.quantity if destination_inventory else 0
            new_destination_qty = current_destination_qty + quantity
            new_ground_qty = ground_quantity - quantity
            
            # Warning se ci sono record TERRA duplicati
            if len(ground_inventory_records) > 1:
                warnings.append({
                    'message': f"TERRA contiene {len(ground_inventory_records)} record duplicati per '{sku}' (verranno consolidati automaticamente)",
                    'sku': sku,
                    'location': 'TERRA'
                })
            
            recap_items.append({
                'line': total_operations,
                'input_code': f"{location} -> {sku}{'_' + str(quantity) if quantity > 1 else ''}",
                'sku': sku,
                'location_from': 'TERRA',
                'location_to': location,
                'description': product.description,
                'quantity_to_move': quantity,
                'current_ground_quantity': ground_quantity,
                'new_ground_quantity': new_ground_qty,
                'current_destination_quantity': current_destination_qty,
                'new_destination_quantity': new_destination_qty,
                'status': 'ok'
            })

    return {
        'recap_items': recap_items,
        'errors': errors,
        'warnings': warnings,
        'total_items': len(recap_items),
        'total_operations': total_operations,
        'file_analysis': {
            'total_movements': total_operations,
            'valid_movements': len(recap_items),
            'unique_destinations': len(movements),
            'error_movements': len(errors)
        }
    }

@router.post("/commit-relocate-from-ground-operations")
async def commit_relocate_from_ground_operations(operations_data: dict, db: Session = Depends(get_db)):
    """
    Esegue le operazioni di ubicazione da terra validate dal recap.
    """
    operations = operations_data.get("operations", [])
    
    if not operations:
        raise HTTPException(status_code=400, detail="Nessuna operazione da eseguire.")
    
    processed_items = 0
    errors = []
    
    try:
        for op in operations:
            if op.get("status") == "error":
                continue  # Salta operazioni con errori
                
            sku = op.get("sku")
            location_to = op.get("location_to")
            quantity_to_move = op.get("quantity_to_move")
            
            # Trova e consolida TUTTI i record dello stesso SKU a TERRA
            ground_inventory_records = db.query(models.Inventory).filter(
                models.Inventory.product_sku == sku,
                models.Inventory.location_name == "TERRA"
            ).all()
            
            total_ground_quantity = sum(record.quantity for record in ground_inventory_records)
            
            if total_ground_quantity < quantity_to_move:
                errors.append(f"Giacenza insufficiente a TERRA per '{sku}'. Richiesti: {quantity_to_move}, Disponibili: {total_ground_quantity}")
                continue
            
            # Rimuovi dalla TERRA - gestisce record multipli dello stesso SKU
            remaining_to_remove = quantity_to_move
            for record in ground_inventory_records:
                if remaining_to_remove <= 0:
                    break
                
                if record.quantity <= remaining_to_remove:
                    # Rimuovi tutto il record
                    remaining_to_remove -= record.quantity
                    db.delete(record)
                else:
                    # Rimuovi parzialmente
                    record.quantity -= remaining_to_remove
                    remaining_to_remove = 0
            
            # Trova o crea nell'ubicazione di destinazione
            destination_inventory = db.query(models.Inventory).filter(
                models.Inventory.product_sku == sku,
                models.Inventory.location_name == location_to
            ).first()
            
            if destination_inventory:
                destination_inventory.quantity += quantity_to_move
            else:
                destination_inventory = models.Inventory(
                    product_sku=sku,
                    location_name=location_to,
                    quantity=quantity_to_move
                )
                db.add(destination_inventory)
            
            processed_items += 1
        
        if errors:
            db.rollback()
            raise HTTPException(status_code=400, detail="Operazione parzialmente fallita:\\n" + "\\n".join(errors))
        
        # LOGGING: Registra le operazioni di ubicazione da terra da file
        logger = LoggingService(db)
        
        # Prepara operazioni per logging
        batch_operations = []
        for op in operations:
            if op.get("status") != "error":
                batch_operations.append({
                    'product_sku': op.get("sku"),
                    'location_from': 'TERRA',
                    'location_to': op.get("location_to"),
                    'quantity': op.get("quantity_to_move"),
                    'status': OperationStatus.SUCCESS,
                    'details': {
                        'operation_description': f"Ubicazione da TERRA: {op.get('sku')} ({op.get('quantity_to_move')} pz) da TERRA a {op.get('location_to')}",
                        'source': 'relocate_ground_file',
                        'movement_type': 'ground_to_location_file'
                    }
                })
        
        # Registra operazioni senza log batch start/end
        if batch_operations:
            file_name = operations_data.get('file_name', 'relocate_ground.txt')
            logger.log_file_operations(
                operation_type=OperationType.SPOSTAMENTO_FILE,
                operation_category=OperationCategory.FILE,
                operations=batch_operations,
                file_name=file_name,
                user_id="file_user"
            )
        
        db.commit()
        return {"message": f"Ubicazione da terra completata. Processati {processed_items} movimenti."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'operazione: {str(e)}")

@router.post("/consolidate-ground-inventory")
async def consolidate_ground_inventory(db: Session = Depends(get_db)):
    """
    Consolida i record duplicati dello stesso SKU in TERRA.
    """
    try:
        # Trova tutti i record a TERRA
        ground_records = db.query(models.Inventory).filter(
            models.Inventory.location_name == "TERRA"
        ).all()
        
        # Raggruppa per SKU
        sku_groups = {}
        for record in ground_records:
            if record.product_sku not in sku_groups:
                sku_groups[record.product_sku] = []
            sku_groups[record.product_sku].append(record)
        
        consolidated_count = 0
        
        # Consolida ogni gruppo
        for sku, records in sku_groups.items():
            if len(records) > 1:
                # Calcola la quantità totale
                total_quantity = sum(record.quantity for record in records)
                
                # Mantieni il primo record e aggiorna la quantità
                primary_record = records[0]
                primary_record.quantity = total_quantity
                
                # Elimina gli altri record
                for record in records[1:]:
                    db.delete(record)
                
                consolidated_count += len(records) - 1
        
        db.commit()
        return {"message": f"Consolidamento completato. Uniti {consolidated_count} record duplicati in TERRA."}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante il consolidamento: {str(e)}")


@router.get("/consolidation-suggestions", response_model=inventory_schemas.ConsolidationSuggestionsResponse)
async def get_consolidation_suggestions(db: Session = Depends(get_db)):
    """
    Analizza l'inventario e suggerisce consolidamenti ottimali tra ubicazioni.
    
    Criteri:
    - Solo prodotti con pallettizzazione definita (pallet_quantity > 0)
    - Esclude ubicazioni TERRA
    - Combina ubicazioni con stesso SKU se totale <= pallet_quantity
    - Suggerisce spostamento da ubicazione più piccola a più grande
    """
    try:
        suggestions = []
        
        # 1. Ottieni prodotti con pallettizzazione definita
        products_with_pallet = db.query(models.Product).filter(
            models.Product.pallet_quantity > 0
        ).all()
        
        products_analyzed = 0
        products_with_palletization = len(products_with_pallet)
        
        for product in products_with_pallet:
            products_analyzed += 1
            
            # 2. Trova tutte le ubicazioni per questo SKU (esclusa TERRA)
            locations = db.query(models.Inventory).filter(
                models.Inventory.product_sku == product.sku,
                models.Inventory.quantity > 0,
                models.Inventory.location_name != "TERRA"
            ).order_by(models.Inventory.quantity.desc()).all()  # Ordina per quantità decrescente
            
            # 3. Se ci sono almeno 2 ubicazioni, calcola il consolidamento ottimale
            if len(locations) < 2:
                continue
            
            # 4. Algoritmo di consolidamento ottimale
            optimal_consolidation = _find_optimal_consolidation(locations, product.pallet_quantity)
            
            if optimal_consolidation:
                # Crea un unico suggerimento per questo SKU
                from_locations = []
                total_from_quantity = 0
                
                for loc in optimal_consolidation['from_locations']:
                    from_locations.append(f"{loc['location']} ({loc['quantity']}pz)")
                    total_from_quantity += loc['quantity']
                
                target_location = optimal_consolidation['to_location']
                target_quantity = optimal_consolidation['to_quantity']
                final_quantity = total_from_quantity + target_quantity
                
                locations_freed = len(optimal_consolidation['from_locations'])
                efficiency_gain = f"Libera {locations_freed} ubicazione{'i' if locations_freed > 1 else ''} ({final_quantity}/{product.pallet_quantity})"
                
                suggestions.append(inventory_schemas.ConsolidationSuggestion(
                    sku=product.sku,
                    description="",  # Rimuovo la descrizione superflua come richiesto
                    pallet_quantity=product.pallet_quantity,
                    from_location=" + ".join(from_locations),  # Mostra tutte le ubicazioni di origine
                    from_quantity=total_from_quantity,
                    to_location=f"{target_location['location']} ({target_location['quantity']}pz)",
                    to_quantity=target_quantity,
                    combined_quantity=final_quantity,
                    efficiency_gain=efficiency_gain
                ))
        
        # 7. Calcola statistiche
        total_suggestions = len(suggestions)
        locations_saveable = sum([
            len(suggestion.from_location.split(" + ")) 
            for suggestion in suggestions
        ])  # Conta tutte le ubicazioni che verranno liberate
        
        return inventory_schemas.ConsolidationSuggestionsResponse(
            suggestions=suggestions,
            total_suggestions=total_suggestions,
            locations_saveable=locations_saveable,
            products_analyzed=products_analyzed,
            products_with_palletization=products_with_palletization
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi consolidamenti: {str(e)}")


def _find_optimal_consolidation(locations, pallet_quantity):
    """
    Trova il consolidamento ottimale per un SKU.
    
    Strategia migliorata:
    1. Prova diverse combinazioni per trovare quella che libera più ubicazioni
    2. Considera qualsiasi ubicazione come potenziale target
    3. Verifica che il totale non superi pallet_quantity
    
    Args:
        locations: Lista di record Inventory ordinata per quantità decrescente
        pallet_quantity: Capacità massima del pallet
        
    Returns:
        Dict con from_locations, to_location, to_quantity oppure None
    """
    if len(locations) < 2:
        return None
    
    best_consolidation = None
    max_locations_freed = 0
    
    # Prova ogni ubicazione come potenziale target
    for i, target in enumerate(locations):
        remaining_locations = locations[:i] + locations[i+1:]
        
        # Calcola spazio disponibile nel target
        available_space = pallet_quantity - target.quantity
        
        if available_space <= 0:
            continue  # Target già pieno, prova il prossimo
        
        # Algoritmo greedy: seleziona ubicazioni da consolidare
        selected_locations = []
        total_to_move = 0
        
        # Ordina per quantità crescente per ottimizzare lo spazio
        remaining_sorted = sorted(remaining_locations, key=lambda x: x.quantity)
        
        for location in remaining_sorted:
            if total_to_move + location.quantity <= available_space:
                selected_locations.append(location)
                total_to_move += location.quantity
        
        # Verifica se questa combinazione è migliore
        locations_freed = len(selected_locations)
        if locations_freed > max_locations_freed and locations_freed > 0:
            max_locations_freed = locations_freed
            best_consolidation = {
                'from_locations': [
                    {'location': loc.location_name, 'quantity': loc.quantity} 
                    for loc in selected_locations
                ],
                'to_location': {
                    'location': target.location_name,
                    'quantity': target.quantity
                },
                'to_quantity': target.quantity,
                'total_moved': total_to_move,
                'locations_freed': locations_freed
            }
    
    return best_consolidation


@router.get("/consolidation-suggestions/pdf")
async def export_consolidation_suggestions_pdf(db: Session = Depends(get_db)):
    """
    Genera PDF con i consigli di consolidamento per l'operatore
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io
        from datetime import datetime
    except ImportError:
        raise HTTPException(status_code=500, detail="Librerie PDF non disponibili")
    
    # Ottieni i dati dei consolidamenti (riusa la logica esistente)
    suggestions_response = await get_consolidation_suggestions(db)
    suggestions = suggestions_response.suggestions
    
    if not suggestions:
        raise HTTPException(status_code=404, detail="Nessun consolidamento disponibile")
    
    # Crea PDF in orientamento orizzontale
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch,
                          leftMargin=0.5*inch, rightMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Stile semplice per intestazione
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    story = []
    
    # Header semplice
    now = datetime.now()
    story.append(Paragraph(f"CONSOLIDAMENTI - {now.strftime('%d/%m/%Y %H:%M')}", title_style))
    story.append(Spacer(1, 20))
    
    # Tabella consolidamenti
    table_data = [
        ['N°', 'SKU', 'DA UBICAZIONE', 'QTÀ', 'A UBICAZIONE', 'QTÀ', 'TOTALE', 'FATTO ✓']
    ]
    
    for i, suggestion in enumerate(suggestions, 1):
        table_data.append([
            str(i),
            suggestion.sku,
            suggestion.from_location.replace(' + ', '\n+ '),  # Multiriga per ubicazioni multiple
            str(suggestion.from_quantity),
            suggestion.to_location,
            str(suggestion.to_quantity),
            f"{suggestion.combined_quantity}/{suggestion.pallet_quantity}",
            "☐"  # Checkbox vuota
        ])
    
    # Crea tabella ottimizzata per orientamento orizzontale
    table = Table(table_data, colWidths=[0.4*inch, 2.2*inch, 2.5*inch, 0.6*inch, 1.8*inch, 0.6*inch, 1.0*inch, 0.6*inch])
    table.setStyle(TableStyle([
        # Header bianco e nero
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        
        # Dati in bianco e nero
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        
        # Bordi
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Colonna SKU in grassetto
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 1), (1, -1), 9),  # SKU più piccoli per entrare meglio
        
        # Allineamento testo per colonne lunghe
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # SKU allineati a sinistra
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),  # Da ubicazione a sinistra
        ('ALIGN', (4, 1), (4, -1), 'LEFT'),  # A ubicazione a sinistra
        
        # Checkbox più grande
        ('FONTSIZE', (7, 1), (7, -1), 14),
    ]))
    
    story.append(table)
    
    # Build PDF
    doc.build(story)
    
    # Prepara response
    buffer.seek(0)
    response = Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=consolidamenti-{now.strftime('%Y%m%d-%H%M')}.pdf"}
    )
    buffer.close()
    
    return response