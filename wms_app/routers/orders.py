from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict

from wms_app import models, schemas
from wms_app.database import database, get_db
from wms_app.main import templates

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)

# --- Viste HTML (devono essere definite prima delle rotte con parametri di percorso) ---

@router.get("/manage", response_class=HTMLResponse)
async def get_orders_management_page(request: Request, db: Session = Depends(get_db)):
    orders = db.query(models.Order).options(joinedload(models.Order.lines)).all()
    products = db.query(models.Product).all()
    return templates.TemplateResponse("orders.html", {
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
    orders = db.query(models.Order).options(joinedload(models.Order.lines)).offset(skip).limit(limit).all()
    return orders

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


@router.get("/{order_id}", response_model=schemas.Order)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# --- Logica di Picking ---

@router.get("/{order_id}/picking-suggestions", response_model=Dict[str, schemas.PickingSuggestion])
def get_picking_suggestions(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).options(joinedload(models.Order.lines)).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

    suggestions = {}
    for line in order.lines:
        if line.requested_quantity <= line.picked_quantity:
            continue # Quantità già prelevata

        remaining_to_pick = line.requested_quantity - line.picked_quantity
        product_sku = line.product_sku

        # Trova stock disponibile per il prodotto, ordinato per ubicazioni a terra (es. P1) prima
        # Questa è una logica semplificata per 'a terra'. Potrebbe essere più complessa.
        available_stock = db.query(models.Inventory).filter(
            models.Inventory.product_sku == product_sku,
            models.Inventory.quantity > 0
        ).order_by(
            models.Inventory.location_name # Ordine alfabetico
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
        
        if remaining_to_pick > 0:
            # Non c'è abbastanza stock per soddisfare l'intera riga
            suggestions[product_sku] = schemas.PickingSuggestion(
                status="partial_stock", 
                needed=line.requested_quantity, 
                available_in_locations=product_suggestions
            )
        else:
            suggestions[product_sku] = schemas.PickingSuggestion(
                status="full_stock", 
                needed=line.requested_quantity, 
                available_in_locations=product_suggestions
            )

    return suggestions

@router.post("/{order_id}/confirm-pick", response_model=schemas.Order)
def confirm_pick(order_id: int, pick_confirmation: schemas.PickConfirmation, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.is_completed:
        raise HTTPException(status_code=400, detail="Order is already completed")

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