from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import io

from wms_app import models
from wms_app.schemas import products as product_schemas # Aggiornato l'alias
from wms_app.database import database

router = APIRouter(
    prefix="/products",
    tags=["products"],
)

# Endpoint per creare un nuovo prodotto
@router.post("/", response_model=product_schemas.Product)
def create_product(product: product_schemas.ProductCreate, db: Session = Depends(database.get_db)):
    db_product = db.query(models.Product).filter(models.Product.sku == product.sku).first()
    if db_product:
        raise HTTPException(status_code=400, detail="SKU already registered")
    
    new_product = models.Product(
        sku=product.sku, 
        description=product.description,
        estimated_value=product.estimated_value
    )
    db.add(new_product)
    
    for ean_code in product.eans:
        new_ean = models.EanCode(ean=ean_code, product_sku=product.sku)
        db.add(new_ean)
        
    db.commit()
    db.refresh(new_product)
    return new_product

# Endpoint per ottenere una lista di tutti i prodotti
@router.get("/", response_model=List[product_schemas.Product])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products

# Endpoint per cercare prodotti per SKU
@router.get("/search", response_model=List[product_schemas.Product])
def search_products_by_sku(query: str, db: Session = Depends(database.get_db)):
    products = db.query(models.Product).filter(models.Product.sku.contains(query)).all()
    return products

# Endpoint per ottenere i dettagli di un singolo prodotto
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

    for line in text_content.splitlines():
        if not line.strip():
            continue
        parts = line.split(',')
        if not parts:
            continue

        sku = parts[0].strip()
        # Il secondo elemento è la descrizione, il terzo (opzionale) è il valore
        description = parts[1].strip() if len(parts) > 1 else None
        estimated_value_str = parts[2].strip() if len(parts) > 2 else None
        eans = [ean.strip() for ean in parts[3:] if ean.strip()]

        if not sku:
            continue # Ignora righe senza SKU

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

        for ean_code in eans:
            existing_ean = db.query(models.EanCode).filter(models.EanCode.ean == ean_code).first()
            if not existing_ean:
                new_ean = models.EanCode(ean=ean_code, product_sku=sku)
                db.add(new_ean)
        
        if sku not in processed_skus:
            imported_count += 1
            processed_skus.add(sku)

    db.commit()
    return {"message": f"Importati o aggiornati {imported_count} prodotti/EAN."}

@router.put("/{sku:path}", response_model=product_schemas.Product)
def update_product(sku: str, product: product_schemas.ProductCreate, db: Session = Depends(database.get_db)):
    db_product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    db_product.description = product.description
    db_product.estimated_value = product.estimated_value
    db.add(db_product)

    # Rimuovi tutti gli EAN esistenti per questo prodotto
    db.query(models.EanCode).filter(models.EanCode.product_sku == sku).delete()

    # Aggiungi i nuovi EAN
    for ean_code in product.eans:
        new_ean = models.EanCode(ean=ean_code, product_sku=sku)
        db.add(new_ean)

    db.commit()
    db.refresh(db_product)
    return db_product

