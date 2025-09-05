from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import io

from wms_app import models
from wms_app.schemas import products as product_schemas # Aggiornato l'alias
from wms_app.database import database, get_db
from wms_app.routers.auth import require_permission
from wms_app.services.logging_service import LoggingService

router = APIRouter(
    prefix="/products",
    tags=["products"],
)

# Endpoint per creare un nuovo prodotto
@router.post("/", response_model=product_schemas.Product)
def create_product(product: product_schemas.ProductCreate, db: Session = Depends(database.get_db), current_user = Depends(require_permission("products_manage"))):
    # Verifica se l'SKU esiste già
    db_product = db.query(models.Product).filter(models.Product.sku == product.sku).first()
    if db_product:
        raise HTTPException(status_code=400, detail="SKU already registered")
    
    # Verifica se ci sono codici EAN duplicati
    duplicate_eans = []
    for ean_code in product.eans:
        if ean_code:  # Ignora EAN vuoti
            existing_ean = db.query(models.EanCode).filter(models.EanCode.ean == ean_code).first()
            if existing_ean:
                duplicate_eans.append(f"EAN '{ean_code}' già associato al prodotto '{existing_ean.product_sku}'")
    
    if duplicate_eans:
        error_message = "Codici EAN duplicati trovati: " + "; ".join(duplicate_eans)
        raise HTTPException(status_code=400, detail=error_message)
    
    try:
        new_product = models.Product(
            sku=product.sku, 
            description=product.description,
            estimated_value=product.estimated_value,
            weight=product.weight,
            pallet_quantity=product.pallet_quantity
        )
        db.add(new_product)
        
        # Aggiungi i codici EAN solo se non sono vuoti
        for ean_code in product.eans:
            if ean_code.strip():  # Verifica che l'EAN non sia vuoto o solo spazi
                new_ean = models.EanCode(ean=ean_code.strip(), product_sku=product.sku)
                db.add(new_ean)
                
        db.commit()
        db.refresh(new_product)
        return new_product
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante la creazione del prodotto: {str(e)}")

# Endpoint per ottenere una lista di tutti i prodotti
@router.get("/", response_model=List[product_schemas.Product])
def read_products(skip: int = 0, limit: int = 1000, db: Session = Depends(database.get_db)):
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products

# Endpoint per cercare prodotti per SKU
@router.get("/search", response_model=List[product_schemas.Product])
def search_products_by_sku(query: str, db: Session = Depends(database.get_db)):
    products = db.query(models.Product).filter(models.Product.sku.contains(query)).all()
    return products

@router.get("/verify-sku/{sku}")
def verify_sku_exists(sku: str, db: Session = Depends(database.get_db)):
    """Verifica se un SKU esiste nel database e restituisce informazioni base."""
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    return {
        "exists": product is not None,
        "sku": sku,
        "description": product.description if product else None
    }

# ENDPOINT SPECIFICI DEVONO ESSERE PRIMA DI QUELLO GENERICO {sku:path}
@router.get("/{sku:path}/validate-deletion")
def validate_product_deletion(sku: str, db: Session = Depends(database.get_db)):
    # Verifica che il prodotto esista
    db_product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    
    # VALIDAZIONI DI SICUREZZA: Controlla tutte le dipendenze (SOLO CONTROLLO)
    dependencies = []
    
    # 1. Controlla giacenze inventario
    inventory_count = db.query(models.Inventory).filter(models.Inventory.product_sku == sku).count()
    if inventory_count > 0:
        dependencies.append(f"Il prodotto ha {inventory_count} record di inventario in magazzino")
    
    # 2. Controlla righe ordine
    order_lines_count = db.query(models.OrderLine).filter(models.OrderLine.product_sku == sku).count()
    if order_lines_count > 0:
        dependencies.append(f"Il prodotto è presente in {order_lines_count} righe d'ordine")
    
    # 3. Controlla movimenti in uscita
    outgoing_stock_count = db.query(models.OutgoingStock).filter(models.OutgoingStock.product_sku == sku).count()
    if outgoing_stock_count > 0:
        dependencies.append(f"Il prodotto ha {outgoing_stock_count} movimenti di uscita registrati")
    
    # 4. Controlla seriali associati
    serials_count = db.query(models.ProductSerial).filter(models.ProductSerial.product_sku == sku).count()
    if serials_count > 0:
        dependencies.append(f"Il prodotto ha {serials_count} numeri seriali associati")
    
    # 5. Controlla righe DDT
    ddt_lines_count = db.query(models.DDTLine).filter(models.DDTLine.product_sku == sku).count()
    if ddt_lines_count > 0:
        dependencies.append(f"Il prodotto è presente in {ddt_lines_count} righe di documenti di trasporto")
    
    # 6. Controlla prenotazioni inventario
    reservations_count = db.query(models.InventoryReservation).filter(models.InventoryReservation.product_sku == sku).count()
    if reservations_count > 0:
        dependencies.append(f"Il prodotto ha {reservations_count} prenotazioni attive")
    
    # Restituisci il risultato della validazione
    return {
        "product_sku": sku,
        "can_delete": len(dependencies) == 0,
        "dependencies": dependencies,
        "total_dependencies": len(dependencies)
    }

# Endpoint per ottenere lo storico delle movimentazioni di un prodotto
@router.get("/{sku}/history")
def get_product_history(
    sku: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("products_view")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    operation_types: Optional[str] = Query(None),
    order_by: str = Query("timestamp"),
    order_direction: str = Query("desc")
):
    """
    Recupera lo storico delle movimentazioni per un prodotto specifico.
    """
    # Verifica che il prodotto esista
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Prodotto '{sku}' non trovato")
    
    logger = LoggingService(db)
    
    try:
        # Parsing date se fornite
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            # Default: ultimi 30 giorni se non specificato
            if not start_date:
                start_datetime = datetime.utcnow() - timedelta(days=30)
        
        # Parsing operation types
        operation_types_list = None
        if operation_types:
            operation_types_list = [t.strip() for t in operation_types.split(',') if t.strip()]
        
        # Calcola offset per paginazione
        offset = (page - 1) * page_size
        
        # Recupera logs per il prodotto specifico
        result = logger.get_logs(
            limit=page_size,
            offset=offset,
            start_date=start_datetime,
            end_date=end_datetime,
            operation_types=operation_types_list,
            product_sku=sku,  # Filtro per SKU specifico
            order_by=order_by,
            order_direction=order_direction
        )
        
        # Converti logs in formato JSON-serializable
        history_data = []
        for log in result['logs']:
            # Estrai numero ordine usando la funzione helper
            order_number_extracted = LoggingService.extract_order_number(log.operation_type, log.details)
            
            log_dict = {
                'id': log.id,
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'operation_type': log.operation_type,
                'operation_category': log.operation_category,
                'status': log.status,
                'location_from': log.location_from,
                'location_to': log.location_to,
                'quantity': log.quantity,
                'user_id': log.user_id,
                'order_number': order_number_extracted,
                'file_name': log.file_name,
                'file_line_number': log.file_line_number,
                'error_message': log.error_message,
                'warning_message': log.warning_message,
                'details': log.details,
                'execution_time_ms': log.execution_time_ms,
                'operation_id': log.operation_id
            }
            history_data.append(log_dict)
        
        # Aggiungi info prodotto
        product_info = {
            'sku': product.sku,
            'description': product.description,
            'estimated_value': float(product.estimated_value or 0),
            'weight': float(product.weight or 0),
            'pallet_quantity': product.pallet_quantity or 0
        }
        
        return {
            "product": product_info,
            "history": history_data,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_pages": result['total_pages'],
                "total_count": result['total_count']
            },
            "period_info": {
                "start_date": start_datetime.strftime('%Y-%m-%d %H:%M:%S') if start_datetime else None,
                "end_date": end_datetime.strftime('%Y-%m-%d %H:%M:%S') if end_datetime else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel recupero storico prodotto: {str(e)}")

# Endpoint per ottenere i dettagli di un singolo prodotto (DEVE ESSERE DOPO QUELLI SPECIFICI)
@router.get("/{sku:path}", response_model=product_schemas.Product)
def get_product(sku: str, db: Session = Depends(database.get_db)):
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("/import-ean-txt")
async def import_products_ean_from_txt(file: UploadFile = File(...), db: Session = Depends(database.get_db)):
    content = await file.read()
    text_content = content.decode("utf-8")
    
    imported_count = 0
    processed_skus = set()
    processed_eans = set()  # Traccia EAN già processati in questo import
    duplicate_eans = []     # Lista EAN duplicati per report
    error_count = 0

    for line_num, line in enumerate(text_content.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(',')
        if not parts:
            continue

        sku = parts[0].strip()
        # Il formato è: SKU, Descrizione, Valore, Peso, Qty_Pallet, EAN...
        description = parts[1].strip() if len(parts) > 1 else None
        estimated_value_str = parts[2].strip() if len(parts) > 2 else None
        weight_str = parts[3].strip() if len(parts) > 3 else None
        pallet_quantity_str = parts[4].strip() if len(parts) > 4 else None
        eans = [ean.strip() for ean in parts[5:] if ean.strip()]

        if not sku:
            continue # Ignora righe senza SKU

        try:
            db_product = db.query(models.Product).filter(models.Product.sku == sku).first()
            if not db_product:
                db_product = models.Product(sku=sku, description=description)
                db.add(db_product)
                db.flush() # Assicura che il prodotto sia nel DB prima di aggiungere EAN
            else:
                # Aggiorna la descrizione se fornita
                if description:
                    db_product.description = description

            # Aggiorna il valore stimato se fornito e valido
            if estimated_value_str:
                try:
                    db_product.estimated_value = float(estimated_value_str.replace(",", "."))
                except (ValueError, TypeError):
                    pass # Ignora valori non validi

            # Aggiorna il peso se fornito e valido
            if weight_str:
                try:
                    db_product.weight = float(weight_str.replace(",", "."))
                except (ValueError, TypeError):
                    pass # Ignora valori non validi

            # Aggiorna la quantità per pallet se fornita e valida
            if pallet_quantity_str:
                try:
                    db_product.pallet_quantity = int(pallet_quantity_str)
                except (ValueError, TypeError):
                    pass # Ignora valori non validi

            for ean_code in eans:
                # Controlla se l'EAN è già stato processato in questo import
                if ean_code in processed_eans:
                    duplicate_eans.append(f"Riga {line_num}: EAN '{ean_code}' duplicato nel file")
                    continue
                
                # Controlla se l'EAN esiste già nel database
                existing_ean = db.query(models.EanCode).filter(models.EanCode.ean == ean_code).first()
                if existing_ean:
                    if existing_ean.product_sku != sku:
                        duplicate_eans.append(f"Riga {line_num}: EAN '{ean_code}' già associato al prodotto '{existing_ean.product_sku}'")
                    continue
                
                # Aggiunge il nuovo EAN
                new_ean = models.EanCode(ean=ean_code, product_sku=sku)
                db.add(new_ean)
                processed_eans.add(ean_code)
            
            if sku not in processed_skus:
                imported_count += 1
                processed_skus.add(sku)
                
        except Exception as e:
            error_count += 1
            print(f"Errore processando riga {line_num}: {e}")
            continue

    db.commit()
    
    # Prepara messaggio di risposta
    message = f"Importati o aggiornati {imported_count} prodotti/EAN."
    if duplicate_eans:
        message += f" {len(duplicate_eans)} EAN duplicati ignorati."
    if error_count:
        message += f" {error_count} errori durante l'import."
    
    return {
        "message": message,
        "imported_count": imported_count,
        "duplicate_eans": duplicate_eans[:10],  # Mostra solo i primi 10 per non sovraccaricare la risposta
        "total_duplicates": len(duplicate_eans),
        "error_count": error_count
    }

@router.put("/{sku:path}", response_model=product_schemas.Product)
def update_product(sku: str, product: product_schemas.ProductCreate, db: Session = Depends(database.get_db)):
    db_product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Verifica se ci sono codici EAN duplicati (escludendo quelli già associati a questo prodotto)
    duplicate_eans = []
    for ean_code in product.eans:
        if ean_code and ean_code.strip():  # Ignora EAN vuoti
            existing_ean = db.query(models.EanCode).filter(
                models.EanCode.ean == ean_code.strip(),
                models.EanCode.product_sku != sku  # Escludi gli EAN già associati a questo prodotto
            ).first()
            if existing_ean:
                duplicate_eans.append(f"EAN '{ean_code}' già associato al prodotto '{existing_ean.product_sku}'")
    
    if duplicate_eans:
        error_message = "Codici EAN duplicati trovati: " + "; ".join(duplicate_eans)
        raise HTTPException(status_code=400, detail=error_message)

    try:
        db_product.description = product.description
        db_product.estimated_value = product.estimated_value
        db_product.weight = product.weight
        db_product.pallet_quantity = product.pallet_quantity
        db.add(db_product)

        # Rimuovi tutti gli EAN esistenti per questo prodotto
        db.query(models.EanCode).filter(models.EanCode.product_sku == sku).delete()

        # Aggiungi i nuovi EAN solo se non sono vuoti
        for ean_code in product.eans:
            if ean_code and ean_code.strip():  # Verifica che l'EAN non sia vuoto o solo spazi
                new_ean = models.EanCode(ean=ean_code.strip(), product_sku=sku)
                db.add(new_ean)

        db.commit()
        db.refresh(db_product)
        return db_product
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Errore durante l'aggiornamento del prodotto: {str(e)}")

@router.delete("/{sku:path}")
def delete_product(sku: str, db: Session = Depends(database.get_db)):
    # Verifica che il prodotto esista
    db_product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    
    # VALIDAZIONI DI SICUREZZA: Controlla tutte le dipendenze
    dependencies = []
    
    # 1. Controlla giacenze inventario
    inventory_count = db.query(models.Inventory).filter(models.Inventory.product_sku == sku).count()
    if inventory_count > 0:
        dependencies.append(f"Il prodotto ha {inventory_count} record di inventario in magazzino")
    
    # 2. Controlla righe ordine
    order_lines_count = db.query(models.OrderLine).filter(models.OrderLine.product_sku == sku).count()
    if order_lines_count > 0:
        dependencies.append(f"Il prodotto è presente in {order_lines_count} righe d'ordine")
    
    # 3. Controlla movimenti in uscita
    outgoing_stock_count = db.query(models.OutgoingStock).filter(models.OutgoingStock.product_sku == sku).count()
    if outgoing_stock_count > 0:
        dependencies.append(f"Il prodotto ha {outgoing_stock_count} movimenti di uscita registrati")
    
    # 4. Controlla seriali associati
    serials_count = db.query(models.ProductSerial).filter(models.ProductSerial.product_sku == sku).count()
    if serials_count > 0:
        dependencies.append(f"Il prodotto ha {serials_count} numeri seriali associati")
    
    # 5. Controlla righe DDT
    ddt_lines_count = db.query(models.DDTLine).filter(models.DDTLine.product_sku == sku).count()
    if ddt_lines_count > 0:
        dependencies.append(f"Il prodotto è presente in {ddt_lines_count} righe di documenti di trasporto")
    
    # 6. Controlla prenotazioni inventario
    reservations_count = db.query(models.InventoryReservation).filter(models.InventoryReservation.product_sku == sku).count()
    if reservations_count > 0:
        dependencies.append(f"Il prodotto ha {reservations_count} prenotazioni attive")
    
    # Se ci sono dipendenze, blocca l'eliminazione
    if dependencies:
        error_message = f"Impossibile eliminare il prodotto '{sku}'. Dipendenze trovate:\n" + "\n".join([f"• {dep}" for dep in dependencies])
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "Eliminazione bloccata per dipendenze esistenti",
                "dependencies": dependencies,
                "product_sku": sku
            }
        )
    
    # ELIMINAZIONE SICURA: Se arriviamo qui, il prodotto è "pulito"
    try:
        # 1. Elimina prima tutti i codici EAN associati
        db.query(models.EanCode).filter(models.EanCode.product_sku == sku).delete()
        
        # 2. Elimina il prodotto
        db.delete(db_product)
        
        # 3. Commit delle modifiche
        db.commit()
        
        return {
            "message": f"Prodotto '{sku}' eliminato con successo",
            "deleted_sku": sku,
            "deleted_ean_codes": True
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Errore durante l'eliminazione del prodotto: {str(e)}"
        )



