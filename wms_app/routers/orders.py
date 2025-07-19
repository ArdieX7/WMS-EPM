from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from typing import List, Dict
from collections import defaultdict
from datetime import datetime

from wms_app import models, schemas
from wms_app.database import database, get_db

# Import templates in modo lazy per evitare import circolari
def get_templates():
    from wms_app.main import templates
    return templates

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

# --- Viste HTML (devono essere definite prima delle rotte con parametri di percorso) ---

@router.get("/manage", response_class=HTMLResponse)
async def get_orders_management_page(request: Request, db: Session = Depends(get_db)):
    # Escludi ordini archiviati dalla vista principale
    orders = db.query(models.Order).filter(models.Order.is_archived == 0).options(joinedload(models.Order.lines)).all()
    products = db.query(models.Product).all()
    return get_templates().TemplateResponse("orders.html", {
        "request": request,
        "orders": orders,
        "products": products,
        "active_page": "orders"
    })

# --- API Endpoints per la Gestione Ordini (generici, senza parametri di percorso) ---

@router.post("/", response_model=schemas.Order)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    db_order = db.query(models.Order).filter(models.Order.order_number == order.order_number).first()
    if db_order:
        raise HTTPException(status_code=400, detail="Order number already exists")

    new_order = models.Order(order_number=order.order_number, customer_name=order.customer_name)
    db.add(new_order)
    db.flush() # Per ottenere l'ID dell'ordine prima del commit

    for line_data in order.lines:
        product = db.query(models.Product).filter(models.Product.sku == line_data.product_sku).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product SKU {line_data.product_sku} not found for order line")
        
        new_line = models.OrderLine(
            order_id=new_order.id,
            product_sku=line_data.product_sku,
            requested_quantity=line_data.requested_quantity
        )
        db.add(new_line)
    
    db.commit()
    db.refresh(new_order)
    return new_order

@router.get("/", response_model=List[schemas.Order])
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Escludi ordini archiviati dalla lista principale
    orders = db.query(models.Order).filter(
        models.Order.is_archived == 0
    ).options(joinedload(models.Order.lines)).offset(skip).limit(limit).all()
    return orders

@router.get("/archived")
def get_archived_orders(db: Session = Depends(get_db)):
    """Recupera tutti gli ordini archiviati."""
    try:
        archived_orders = db.query(models.Order).filter(
            models.Order.is_archived == 1
        ).options(joinedload(models.Order.lines)).order_by(models.Order.id.desc()).all()
        
        orders_data = []
        for order in archived_orders:
            order_data = {
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "archived_date": order.archived_date.isoformat() if order.archived_date else None,
                "is_completed": bool(order.is_completed),
                "is_cancelled": bool(order.is_cancelled),
                "lines": [
                    {
                        "product_sku": line.product_sku,
                        "requested_quantity": line.requested_quantity,
                        "picked_quantity": line.picked_quantity
                    }
                    for line in order.lines
                ]
            }
            orders_data.append(order_data)
        
        return {"orders": orders_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching archived orders: {str(e)}")

# --- API Endpoints con parametri di percorso (devono essere definiti dopo le rotte generiche) ---


@router.post("/import-orders-txt")
async def import_orders_from_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")

    orders_in_file = {}
    line_number = 0
    for line in text_content.splitlines():
        line_number += 1
        if not line.strip():
            continue
        
        parts = line.strip().split(',')
        if len(parts) != 4:
            raise HTTPException(status_code=400, detail=f"Formato non valido alla riga {line_number}: la riga deve contenere NumeroOrdine,Cliente,SKU,Qty")

        order_number, customer_name, sku, qty_str = parts
        order_number = order_number.strip()
        customer_name = customer_name.strip()
        sku = sku.strip()

        try:
            quantity = int(qty_str.strip())
            if quantity <= 0:
                raise ValueError("La quantità deve essere positiva.")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Quantità non valida alla riga {line_number}: '{qty_str}'")

        if order_number not in orders_in_file:
            orders_in_file[order_number] = {
                "customer_name": customer_name,
                "lines": []
            }
        
        orders_in_file[order_number]["lines"].append({"sku": sku, "quantity": quantity})

    created_count = 0
    updated_count = 0

    for order_number, order_data in orders_in_file.items():
        db_order = db.query(models.Order).filter(models.Order.order_number == order_number).first()

        if not db_order:
            # Crea un nuovo ordine
            db_order = models.Order(
                order_number=order_number, 
                customer_name=order_data['customer_name']
            )
            db.add(db_order)
            db.flush() # Per ottenere l'ID dell'ordine
            created_count += 1
        else:
            # Ordine esistente, verifica se è già completato
            if db_order.is_completed:
                continue # Salta gli ordini già completati
            updated_count += 1

        # Aggiungi le righe d'ordine
        for line in order_data['lines']:
            # Controlla se il prodotto esiste
            product = db.query(models.Product).filter(models.Product.sku == line['sku']).first()
            if not product:
                db.rollback()
                raise HTTPException(status_code=404, detail=f"Prodotto con SKU '{line['sku']}' non trovato per l'ordine '{order_number}'. L'importazione è stata annullata.")

            # Controlla se una riga simile esiste già per evitare duplicati
            existing_line = db.query(models.OrderLine).filter(
                models.OrderLine.order_id == db_order.id,
                models.OrderLine.product_sku == line['sku']
            ).first()

            if existing_line:
                # Aggiorna la quantità della riga esistente
                existing_line.requested_quantity += line['quantity']
            else:
                # Crea una nuova riga d'ordine
                new_line = models.OrderLine(
                    order_id=db_order.id,
                    product_sku=line['sku'],
                    requested_quantity=line['quantity']
                )
                db.add(new_line)

    db.commit()
    return {"message": f"Importazione completata. Ordini creati: {created_count}. Ordini aggiornati: {updated_count}."}

# --- Nuovi Endpoint Picking (DEVONO essere prima di /{order_id}) ---

@router.post("/validate-picking-txt")
async def validate_picking_from_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Valida le operazioni di picking da file TXT scanner e restituisce un recap dettagliato.
    Formato pistola scanner: numero ordine, ubicazione, EAN/SKU ripetuti o EAN/SKU_quantità
    """
    try:
        picking_data = await _parse_picking_file_scanner(file, db)
    except HTTPException as e:
        raise e
    
    if not picking_data:
        raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi.")
    
    validation_results = {
        "valid_operations": [],
        "warnings": [],
        "errors": [],
        "order_summaries": {}
    }
    
    for order_number, locations_data in picking_data.items():
        # Trova l'ordine
        order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(
            models.Order.order_number == order_number
        ).first()
        
        order_summary = {
            "order_number": order_number,
            "customer_name": None,
            "exists": order is not None,
            "is_completed": False,
            "lines": {},
            "picking_operations": []
        }
        
        if not order:
            validation_results["errors"].append(f"Ordine '{order_number}' non trovato nel database")
            order_summary["customer_name"] = "ORDINE NON TROVATO"
        else:
            order_summary["customer_name"] = order.customer_name
            order_summary["is_completed"] = order.is_completed
            
            if order.is_completed:
                validation_results["errors"].append(f"Ordine '{order_number}' è già completato")
            
            # Costruisci mappa righe ordine
            for line in order.lines:
                order_summary["lines"][line.product_sku] = {
                    "requested": line.requested_quantity,
                    "picked": line.picked_quantity,
                    "remaining": line.requested_quantity - line.picked_quantity
                }
        
        # Valida ogni operazione di picking
        for location, skus_data in locations_data.items():
            for sku, quantity in skus_data.items():
                operation = {
                    "order_number": order_number,
                    "location": location,
                    "sku": sku,
                    "quantity": quantity,
                    "status": "valid",
                    "issues": []
                }
                
                # Verifica ordine esistente
                if not order:
                    operation["status"] = "error"
                    operation["issues"].append("Ordine non trovato")
                elif order.is_completed:
                    operation["status"] = "error"
                    operation["issues"].append("Ordine già completato")
                else:
                    # Trova la riga ordine
                    order_line = db.query(models.OrderLine).filter(
                        models.OrderLine.order_id == order.id,
                        models.OrderLine.product_sku == sku
                    ).first()
                    
                    if not order_line:
                        operation["status"] = "error"
                        operation["issues"].append(f"Prodotto '{sku}' non presente nell'ordine")
                    else:
                        # Verifica giacenza disponibile
                        inventory_item = db.query(models.Inventory).filter(
                            models.Inventory.location_name == location,
                            models.Inventory.product_sku == sku
                        ).first()
                        
                        if not inventory_item:
                            operation["status"] = "error"
                            operation["issues"].append(f"Prodotto non presente in ubicazione '{location}'")
                        elif inventory_item.quantity < quantity:
                            operation["status"] = "error"
                            operation["issues"].append(f"Giacenza insufficiente: disponibili {inventory_item.quantity}, richiesti {quantity}")
                        
                        # Verifica quantità ordine
                        remaining_to_pick = order_line.requested_quantity - order_line.picked_quantity
                        if quantity > remaining_to_pick:
                            if remaining_to_pick == 0:
                                operation["status"] = "warning"
                                operation["issues"].append(f"Prodotto già completamente prelevato per questo ordine")
                            else:
                                operation["status"] = "warning"
                                operation["issues"].append(f"Quantità eccessiva: rimanenti da prelevare {remaining_to_pick}, tentativo prelievo {quantity}")
                
                order_summary["picking_operations"].append(operation)
                
                if operation["status"] == "valid":
                    validation_results["valid_operations"].append(operation)
                elif operation["status"] == "warning":
                    validation_results["warnings"].append(operation)
                elif operation["status"] == "error":
                    validation_results["errors"].append(operation)
        
        validation_results["order_summaries"][order_number] = order_summary
    
    # Aggiungi statistiche finali
    validation_results["stats"] = {
        "total_operations": len(validation_results["valid_operations"]) + len(validation_results["warnings"]) + len(validation_results["errors"]),
        "valid_count": len(validation_results["valid_operations"]),
        "warning_count": len(validation_results["warnings"]),
        "error_count": len(validation_results["errors"]),
        "orders_count": len(validation_results["order_summaries"])
    }
    
    return validation_results

@router.post("/commit-picking-txt")
async def commit_picking_from_txt(file: UploadFile = File(...), force: bool = False, db: Session = Depends(get_db)):
    """
    Commit delle operazioni di picking dopo validazione.
    Se force=True, esegue solo le operazioni valide ignorando quelle con warning/errori.
    """
    try:
        picking_data = await _parse_picking_file_scanner(file, db)
    except HTTPException as e:
        raise e
    
    if not picking_data:
        raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi.")
    
    successful_operations = []
    skipped_operations = []
    
    for order_number, locations_data in picking_data.items():
        # Trova l'ordine
        order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
        if not order or order.is_completed:
            skipped_operations.append(f"Ordine '{order_number}' saltato (non trovato o completato)")
            continue
        
        for location, skus_data in locations_data.items():
            for sku, quantity in skus_data.items():
                # Trova la riga ordine
                order_line = db.query(models.OrderLine).filter(
                    models.OrderLine.order_id == order.id,
                    models.OrderLine.product_sku == sku
                ).first()
                
                if not order_line:
                    skipped_operations.append(f"Prodotto '{sku}' non trovato nell'ordine '{order_number}'")
                    continue
                
                # Verifica giacenza disponibile
                inventory_item = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku == sku
                ).first()
                
                if not inventory_item or inventory_item.quantity < quantity:
                    skipped_operations.append(f"Giacenza insufficiente per {sku} in {location}")
                    continue
                
                # Verifica quantità ordine (con tolleranza se force=True)
                remaining_to_pick = order_line.requested_quantity - order_line.picked_quantity
                actual_quantity = quantity
                
                if quantity > remaining_to_pick:
                    if force and remaining_to_pick > 0:
                        actual_quantity = remaining_to_pick  # Preleva solo quello che serve
                        skipped_operations.append(f"Ridotta quantità per {sku} da {quantity} a {actual_quantity}")
                    elif remaining_to_pick == 0:
                        skipped_operations.append(f"Saltato {sku}: già completamente prelevato")
                        continue
                    else:
                        skipped_operations.append(f"Saltato {sku}: quantità eccessiva")
                        continue
                
                # Esegui l'operazione di picking
                inventory_item.quantity -= actual_quantity
                order_line.picked_quantity += actual_quantity
                
                # Aggiungi a OutgoingStock
                outgoing_item = db.query(models.OutgoingStock).filter(
                    models.OutgoingStock.order_line_id == order_line.id,
                    models.OutgoingStock.product_sku == sku
                ).first()
                
                if outgoing_item:
                    outgoing_item.quantity += actual_quantity
                else:
                    new_outgoing_item = models.OutgoingStock(
                        order_line_id=order_line.id,
                        product_sku=sku,
                        quantity=actual_quantity
                    )
                    db.add(new_outgoing_item)
                
                successful_operations.append(f"Prelevato {actual_quantity}x {sku} da {location} per ordine {order_number}")
    
    if not successful_operations and not force:
        db.rollback()
        raise HTTPException(status_code=400, detail="Nessuna operazione valida da eseguire")
    
    db.commit()
    
    return {
        "message": f"Picking completato: {len(successful_operations)} operazioni eseguite",
        "successful_operations": successful_operations,
        "skipped_operations": skipped_operations,
        "force_mode": force
    }

@router.post("/debug-picking-txt")
async def debug_picking_from_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Endpoint di debug per verificare il parsing del file scanner.
    """
    try:
        content = await file.read()
        text_content = content.decode("utf-8")
        lines = text_content.splitlines()
        
        # Check database contents
        all_locations = {loc.name for loc in db.query(models.Location).all()}
        all_products = {p.sku for p in db.query(models.Product).all()}
        all_eans = {e.ean: e.product_sku for e in db.query(models.EanCode).all()}
        
        return {
            "file_name": file.filename,
            "total_lines": len(lines),
            "first_10_lines": lines[:10],
            "parser_used": "debug_scanner",
            "database_info": {
                "locations": list(all_locations)[:10],
                "products": list(all_products)[:10], 
                "eans": list(all_eans.keys())[:10]
            }
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@router.post("/import-picking-txt")
async def import_picking_from_txt_legacy(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Endpoint legacy che usa il nuovo parser scanner ma mantiene il comportamento originale.
    """
    try:
        # Parsing con il nuovo formato scanner
        picking_data = await _parse_picking_file_scanner(file, db)
        
        if not picking_data:
            raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi.")
        
        return {"message": f"Parser chiamato correttamente. Ordini trovati: {list(picking_data.keys())}"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore interno: {str(e)}")

# --- API Endpoints con parametri di percorso (devono essere definiti dopo le rotte generiche) ---

@router.get("/{order_id}", response_model=schemas.Order)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# --- Logica di Picking ---

@router.get("/{order_id}/picking-suggestions", response_model=Dict[str, schemas.PickingSuggestion])
def get_picking_suggestions(order_id: int, db: Session = Depends(get_db)):
    from wms_app.services.reservation_service import ReservationService
    
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

    # Inizializza il servizio di prenotazioni
    reservation_service = ReservationService(db)
    
    # Pulisce automaticamente le prenotazioni scadute
    reservation_service.cleanup_expired_reservations()
    
    # Prepara lista prodotti necessari per l'ordine
    products_needed = []
    for line in order.lines:
        if line.requested_quantity > line.picked_quantity:
            remaining_to_pick = line.requested_quantity - line.picked_quantity
            products_needed.append({
                'sku': line.product_sku,
                'quantity': remaining_to_pick,
                'line_id': line.id
            })
    
    if not products_needed:
        return {}  # Ordine già completamente prelevato
    
    # Usa il Round-Robin Reservation System per allocare ubicazioni
    try:
        allocations = reservation_service.allocate_picking_locations(
            order_id=str(order.order_number), 
            products_needed=products_needed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore allocazione picking: {str(e)}")
    
    # Converte il risultato nel formato atteso dal frontend
    suggestions = {}
    for allocation in allocations:
        sku = allocation['sku']
        
        product_suggestions = []
        for loc_allocation in allocation['allocations']:
            product_suggestions.append({
                "location_name": loc_allocation['location_name'],
                "quantity": loc_allocation['quantity'],
                "reservation_id": loc_allocation['reservation_id']  # Nuovo campo per tracking
            })
        
        if allocation['fully_allocated']:
            suggestions[sku] = schemas.PickingSuggestion(
                status="full_stock",
                needed=allocation['requested_quantity'],
                available_in_locations=product_suggestions
            )
        else:
            suggestions[sku] = schemas.PickingSuggestion(
                status="partial_stock",
                needed=allocation['requested_quantity'],
                available_in_locations=product_suggestions
            )
    
    return suggestions

@router.post("/{order_id}/confirm-pick", response_model=schemas.Order)
def confirm_pick(order_id: int, pick_confirmation: schemas.PickConfirmation, db: Session = Depends(get_db)):
    from wms_app.services.reservation_service import ReservationService
    
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

    reservation_service = ReservationService(db)

    for picked_item in pick_confirmation.picked_items:
        order_line = db.query(models.OrderLine).filter(
            models.OrderLine.id == picked_item.order_line_id,
            models.OrderLine.order_id == order_id
        ).first()
        if not order_line:
            raise HTTPException(status_code=404, detail=f"Order line {picked_item.order_line_id} not found for this order")

        inventory_item = db.query(models.Inventory).filter(
            models.Inventory.product_sku == picked_item.product_sku,
            models.Inventory.location_name == picked_item.location_name
        ).first()

        if not inventory_item or inventory_item.quantity < picked_item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock of {picked_item.product_sku} in {picked_item.location_name} to pick {picked_item.quantity}")

        # Scala dalla giacenza
        inventory_item.quantity -= picked_item.quantity
        order_line.picked_quantity += picked_item.quantity

        # Sposta in OutgoingStock
        outgoing_item = db.query(models.OutgoingStock).filter(
            models.OutgoingStock.order_line_id == picked_item.order_line_id,
            models.OutgoingStock.product_sku == picked_item.product_sku
        ).first()

        if outgoing_item:
            outgoing_item.quantity += picked_item.quantity
        else:
            new_outgoing_item = models.OutgoingStock(
                order_line_id=picked_item.order_line_id,
                product_sku=picked_item.product_sku,
                quantity=picked_item.quantity
            )
            db.add(new_outgoing_item)
        
        # NUOVO: Completa la prenotazione se present
        # Cerca prenotazioni attive per questo ordine/prodotto/ubicazione
        if hasattr(picked_item, 'reservation_id') and picked_item.reservation_id:
            reservation_service.complete_reservation(picked_item.reservation_id, picked_item.quantity)
        else:
            # Fallback: cerca prenotazione per order_number/sku/location
            from wms_app.models.reservations import InventoryReservation
            reservation = db.query(InventoryReservation).filter(
                InventoryReservation.order_id == str(order.order_number),
                InventoryReservation.product_sku == picked_item.product_sku,
                InventoryReservation.location_name == picked_item.location_name,
                InventoryReservation.status == 'active'
            ).first()
            
            if reservation:
                reservation_service.complete_reservation(reservation.id, picked_item.quantity)
    
    db.commit()
    db.refresh(order)
    return order

@router.post("/{order_id}/fulfill", response_model=schemas.Order)
def fulfill_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

    # Scala da OutgoingStock e completa l'ordine
    for line in order.lines:
        outgoing_item = db.query(models.OutgoingStock).filter(
            models.OutgoingStock.order_line_id == line.id,
            models.OutgoingStock.product_sku == line.product_sku
        ).first()

        if outgoing_item:
            if outgoing_item.quantity != line.picked_quantity: # Dovrebbe essere uguale se tutto è stato prelevato
                raise HTTPException(status_code=400, detail=f"Mismatch in outgoing stock for line {line.id}")
            db.delete(outgoing_item) # Rimuovi da outgoing stock
        
        if line.requested_quantity != line.picked_quantity:
            raise HTTPException(status_code=400, detail=f"Order line {line.id} not fully picked. Requested: {line.requested_quantity}, Picked: {line.picked_quantity}")

    order.is_completed = True
    db.commit()
    db.refresh(order)
    return order

# --- Nuova Funzionalità: Picking da File TXT ---

async def _parse_picking_file_scanner(file: UploadFile, db: Session) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Parsing del file di picking da pistola scanner con formato:
    - Riga 1: Numero Ordine
    - Riga 2: Ubicazione
    - Righe 3+: EAN/SKU ripetuti (quantità = numero ripetizioni) oppure EAN/SKU_quantità
    - Il pattern si ripete per più ordini
    
    Ritorna: {order_number: {location: {sku: quantity}}}
    """
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Il file non è in formato UTF-8 valido.")
    
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    parsed_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    errors = []
    
    # Parsing migliorato per il formato scanner
    current_order = None
    current_location = None
    
    # Ottieni le ubicazioni esistenti dal database per confronto
    all_locations = {loc.name for loc in db.query(models.Location).all()}
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Verifica se è un numero ordine (numerico o alfanumerico corto)
        if line.replace('-', '').replace('_', '').isalnum() and len(line) <= 10:
            # Verifica che non sia una ubicazione esistente
            if line not in all_locations:
                current_order = line
                current_location = None
                continue
        
        # Verifica se è una ubicazione esistente nel database
        if line in all_locations:
            current_location = line
            continue
        
        # Altrimenti è un prodotto
        if current_order and current_location:
            ean_or_sku = line
            quantity = 1
            
            # Parsing quantità da formato SKU_quantità
            if '_' in ean_or_sku:
                parts = ean_or_sku.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    ean_or_sku = parts[0]
                    quantity = int(parts[1])
            
            # Trova SKU nel database
            sku_found = None
            try:
                # Prova come EAN
                ean_code = db.query(models.EanCode).filter(models.EanCode.ean == ean_or_sku).first()
                if ean_code:
                    sku_found = ean_code.product_sku
                else:
                    # Prova come SKU diretto
                    product = db.query(models.Product).filter(models.Product.sku == ean_or_sku).first()
                    if product:
                        sku_found = product.sku
            except Exception:
                # Ignora errori di database per evitare hang
                pass
            
            if sku_found:
                parsed_data[current_order][current_location][sku_found] += quantity
            else:
                errors.append(f"Riga {i+1}: EAN/SKU '{ean_or_sku}' non trovato nel database")
        else:
            errors.append(f"Riga {i+1}: Prodotto '{line}' senza ordine o ubicazione validi")
    
    if errors:
        raise HTTPException(status_code=400, detail=f"Errori nel parsing: {'; '.join(errors)}")
        
    return parsed_data

@router.post("/commit-picking-txt")
async def commit_picking_from_txt(file: UploadFile = File(...), force: bool = False, db: Session = Depends(get_db)):
    """
    Commit delle operazioni di picking dopo validazione.
    Se force=True, esegue solo le operazioni valide ignorando quelle con warning/errori.
    """
    try:
        picking_data = await _parse_picking_file_scanner(file, db)
    except HTTPException as e:
        raise e
    
    if not picking_data:
        raise HTTPException(status_code=400, detail="Il file è vuoto o non contiene dati validi.")
    
    successful_operations = []
    skipped_operations = []
    
    for order_number, locations_data in picking_data.items():
        # Trova l'ordine
        order = db.query(models.Order).filter(models.Order.order_number == order_number).first()
        if not order or order.is_completed:
            skipped_operations.append(f"Ordine '{order_number}' saltato (non trovato o completato)")
            continue
        
        for location, skus_data in locations_data.items():
            for sku, quantity in skus_data.items():
                # Trova la riga ordine
                order_line = db.query(models.OrderLine).filter(
                    models.OrderLine.order_id == order.id,
                    models.OrderLine.product_sku == sku
                ).first()
                
                if not order_line:
                    skipped_operations.append(f"Prodotto '{sku}' non trovato nell'ordine '{order_number}'")
                    continue
                
                # Verifica giacenza disponibile
                inventory_item = db.query(models.Inventory).filter(
                    models.Inventory.location_name == location,
                    models.Inventory.product_sku == sku
                ).first()
                
                if not inventory_item or inventory_item.quantity < quantity:
                    skipped_operations.append(f"Giacenza insufficiente per {sku} in {location}")
                    continue
                
                # Verifica quantità ordine (con tolleranza se force=True)
                remaining_to_pick = order_line.requested_quantity - order_line.picked_quantity
                actual_quantity = quantity
                
                if quantity > remaining_to_pick:
                    if force and remaining_to_pick > 0:
                        actual_quantity = remaining_to_pick  # Preleva solo quello che serve
                        skipped_operations.append(f"Ridotta quantità per {sku} da {quantity} a {actual_quantity}")
                    elif remaining_to_pick == 0:
                        skipped_operations.append(f"Saltato {sku}: già completamente prelevato")
                        continue
                    else:
                        skipped_operations.append(f"Saltato {sku}: quantità eccessiva")
                        continue
                
                # Esegui l'operazione di picking
                inventory_item.quantity -= actual_quantity
                order_line.picked_quantity += actual_quantity
                
                # Aggiungi a OutgoingStock
                outgoing_item = db.query(models.OutgoingStock).filter(
                    models.OutgoingStock.order_line_id == order_line.id,
                    models.OutgoingStock.product_sku == sku
                ).first()
                
                if outgoing_item:
                    outgoing_item.quantity += actual_quantity
                else:
                    new_outgoing_item = models.OutgoingStock(
                        order_line_id=order_line.id,
                        product_sku=sku,
                        quantity=actual_quantity
                    )
                    db.add(new_outgoing_item)
                
                successful_operations.append(f"Prelevato {actual_quantity}x {sku} da {location} per ordine {order_number}")
    
    if not successful_operations and not force:
        db.rollback()
        raise HTTPException(status_code=400, detail="Nessuna operazione valida da eseguire")
    
    db.commit()
    
    return {
        "message": f"Picking completato: {len(successful_operations)} operazioni eseguite",
        "successful_operations": successful_operations,
        "skipped_operations": skipped_operations,
        "force_mode": force
    }

@router.get("/{order_id}/picking-list-print")
async def get_picking_list_print(order_id: int, db: Session = Depends(get_db)):
    """
    Genera una versione stampabile della picking list per un ordine.
    """
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Ottieni i suggerimenti di picking
    suggestions = {}
    for line in order.lines:
        if line.requested_quantity <= line.picked_quantity:
            continue
            
        remaining_to_pick = line.requested_quantity - line.picked_quantity
        product_sku = line.product_sku
        
        available_stock = db.query(models.Inventory).filter(
            models.Inventory.product_sku == product_sku,
            models.Inventory.quantity > 0
        ).order_by(
            models.Inventory.location_name
        ).all()
        
        product_suggestions = []
        for item in available_stock:
            if remaining_to_pick <= 0:
                break
            
            qty_from_location = min(remaining_to_pick, item.quantity)
            product_suggestions.append({
                "location_name": item.location_name,
                "quantity": qty_from_location
            })
            remaining_to_pick -= qty_from_location
        
        suggestions[product_sku] = {
            "needed": line.requested_quantity - line.picked_quantity,
            "locations": product_suggestions
        }
    
    # Genera HTML stampabile
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Picking List - Ordine {order.order_number}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
            .order-info {{ margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
            th {{ background-color: #f0f0f0; }}
            .location {{ font-weight: bold; }}
            @media print {{ 
                body {{ margin: 0; }}
                .no-print {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>PICKING LIST</h1>
        </div>
        <div class="order-info">
            <p><strong>Numero Ordine:</strong> {order.order_number}</p>
            <p><strong>Cliente:</strong> {order.customer_name}</p>
            <p><strong>Data:</strong> {order.order_date.strftime('%d/%m/%Y %H:%M') if order.order_date else 'N/A'}</p>
        </div>
        <table>
            <thead>
                <tr>
                    <th>SKU</th>
                    <th>Ubicazione</th>
                    <th>Quantità da Prelevare</th>
                    <th>☐ Prelevato</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for sku, suggestion in suggestions.items():
        for location in suggestion["locations"]:
            html_content += f"""
                <tr>
                    <td>{sku}</td>
                    <td class="location">{location['location_name']}</td>
                    <td>{location['quantity']}</td>
                    <td style="text-align: center; width: 50px;">☐</td>
                </tr>
            """
    
    html_content += """
            </tbody>
        </table>
        <div class="no-print">
            <button onclick="window.print()">Stampa</button>
            <button onclick="window.close()">Chiudi</button>
        </div>
        <script>
            // Auto-print quando la pagina è caricata
            window.onload = function() {
                setTimeout(function() {
                    window.print();
                }, 500);
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

# --- Nuovi Endpoint per Gestione Archiviazione e Annullamento ---

@router.post("/{order_id}/archive")
def archive_order(order_id: int, db: Session = Depends(get_db)):
    """Archivia un ordine completato."""
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Validazione stato ordine
        
        if not order.is_completed:
            raise HTTPException(status_code=400, detail="Can only archive completed orders")
        
        if order.is_archived:
            raise HTTPException(status_code=400, detail="Order is already archived")
        
        if order.is_cancelled:
            raise HTTPException(status_code=400, detail="Cannot archive a cancelled order")
        
        # Archivia l'ordine
        order.is_archived = True
        order.archived_date = datetime.utcnow()
        
        db.commit()
        return {"message": f"Order {order.order_number} archived successfully"}
        
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error archiving order: {str(e)}")

@router.post("/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    """Annulla un ordine e rilascia la giacenza in uscita."""
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Validazione stato ordine
        
        if order.is_completed:
            raise HTTPException(status_code=400, detail="Cannot cancel a completed order")
        
        if order.is_cancelled:
            raise HTTPException(status_code=400, detail="Order is already cancelled")
        
        if order.is_archived:
            raise HTTPException(status_code=400, detail="Cannot cancel an archived order")
        
        # Recupera tutte le giacenze in uscita per questo ordine
        outgoing_stocks = db.query(models.OutgoingStock).join(models.OrderLine).filter(
            models.OrderLine.order_id == order_id
        ).all()
        
        released_items = []
        for stock in outgoing_stocks:
            released_items.append({
                "product_sku": stock.product_sku,
                "quantity": stock.quantity
            })
            # Rimuovi dalla giacenza in uscita
            db.delete(stock)
        
        # Annulla l'ordine
        order.is_cancelled = True
        order.cancelled_date = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": f"Order {order.order_number} cancelled successfully",
            "released_items": released_items,
            "note": "Released items should be repositioned in warehouse by operators"
        }
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error cancelling order: {str(e)}")

@router.delete("/{order_id}/unarchive")
def unarchive_order(order_id: int, db: Session = Depends(get_db)):
    """Rimuove un ordine dall'archivio (riporta nella lista normale)."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if not order.is_archived:
        raise HTTPException(status_code=400, detail="Order is not archived")
    
    # Rimuovi dall'archivio
    order.is_archived = False
    order.archived_date = None
    
    try:
        db.commit()
        return {"message": f"Order {order.order_number} removed from archive successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error unarchiving order: {str(e)}")