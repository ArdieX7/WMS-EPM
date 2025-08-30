from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from wms_app.routers.auth import require_permission
from wms_app.middleware.auth_middleware import AuthMiddleware

from wms_app.database import database
from wms_app.models import products, inventory, orders, reservations, serials, ddt, settings, logs, auth
from wms_app.models.inventory import Location, Inventory  
from wms_app.models.orders import Order



# Crea le tabelle del database (solo se non esistono già)
products.Base.metadata.create_all(bind=database.engine)
inventory.Base.metadata.create_all(bind=database.engine)
orders.Base.metadata.create_all(bind=database.engine)
reservations.Base.metadata.create_all(bind=database.engine)
serials.Base.metadata.create_all(bind=database.engine)
ddt.Base.metadata.create_all(bind=database.engine)
settings.Base.metadata.create_all(bind=database.engine)
logs.Base.metadata.create_all(bind=database.engine)
auth.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="WMS EPM")

# Aggiungi middleware di autenticazione
auth_middleware = AuthMiddleware()
app.middleware("http")(auth_middleware)

# Monta le cartelle per i file statici (CSS, JS) e i template (HTML)
app.mount("/static", StaticFiles(directory="wms_app/static"), name="static")
templates = Jinja2Templates(directory="wms_app/templates")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active_page": "home"})

@app.get("/test-main")
async def test_main_endpoint():
    print("🔥 TEST MAIN ENDPOINT CHIAMATO - SERVER PRINCIPALE FUNZIONA!")
    return {"server": "main", "status": "OK", "message": "Endpoint principale funziona"}

# Qui aggiungeremo i router per le diverse sezioni dell'app
from wms_app.routers import products, inventory, orders, analysis, warehouse, reservations, serials, ddt, logs, auth, admin
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(analysis.router)
app.include_router(warehouse.router)
app.include_router(reservations.router)
app.include_router(serials.router)
app.include_router(ddt.router)
app.include_router(logs.router)

@app.get("/products-page", response_class=HTMLResponse)
async def get_products_page(request: Request):
    return templates.TemplateResponse("products.html", {"request": request, "active_page": "products"})

# API endpoints per statistiche dashboard
@app.get("/api/stats/inventory")
async def get_inventory_stats(db: Session = Depends(database.get_db)):
    """Totale pezzi in magazzino"""
    total_pieces = db.query(func.sum(Inventory.quantity)).scalar() or 0
    return {"count": total_pieces}

@app.get("/api/stats/ground")
async def get_ground_stats(db: Session = Depends(database.get_db)):
    """Pezzi a terra (ubicazioni temporanee)"""
    # Assumiamo che le ubicazioni "a terra" inizino con "TERRA" o simili
    ground_pieces = db.query(func.sum(Inventory.quantity)).filter(
        Inventory.location_name.like('TERRA%')
    ).scalar() or 0
    
    # Se non ci sono ubicazioni specifiche per terra, usa un valore di fallback
    if ground_pieces == 0:
        # Potremmo anche cercare ubicazioni che non seguono il pattern standard
        ground_pieces = db.query(func.sum(Inventory.quantity)).filter(
            func.length(Inventory.location_name) < 5  # Ubicazioni con nomi corti potrebbero essere temporanee
        ).scalar() or 0
    
    return {"count": ground_pieces}

@app.get("/api/stats/locations")
async def get_locations_stats(db: Session = Depends(database.get_db)):
    """Ubicazioni utilizzate vs totali"""
    # Ubicazioni con inventario (utilizzate)
    used_locations = db.query(func.count(func.distinct(Inventory.location_name))).scalar() or 0
    
    # Totale ubicazioni disponibili
    total_locations = db.query(func.count(Location.name)).filter(
        Location.available == True
    ).scalar() or 0
    
    # Calcola percentuale di utilizzo
    usage_percentage = round((used_locations / total_locations * 100), 1) if total_locations > 0 else 0
    free_percentage = round((100 - usage_percentage), 1)
    
    return {
        "used": used_locations, 
        "total": total_locations, 
        "count": used_locations,
        "usage_percentage": usage_percentage,
        "free_percentage": free_percentage,
        "free_locations": total_locations - used_locations
    }

@app.get("/api/stats/orders")
async def get_orders_stats(db: Session = Depends(database.get_db)):
    """Ordini da completare (non evasi)"""
    # Ordini non completati, non archiviati e non cancellati
    pending_orders = db.query(func.count(Order.id)).filter(
        and_(
            Order.is_completed == False,
            Order.is_archived == False,
            Order.is_cancelled == False
        )
    ).scalar() or 0
    
    return {"count": pending_orders}

@app.get("/api/stats/serials")
async def get_serials_stats(db: Session = Depends(database.get_db)):
    """Seriali mancanti per ordini non evasi"""
    # Stessa logica degli ordini pendenti - ordini che necessitano ancora di seriali
    incomplete_orders = db.query(func.count(Order.id)).filter(
        and_(
            Order.is_completed == False,
            Order.is_archived == False,
            Order.is_cancelled == False
        )
    ).scalar() or 0
    
    return {"count": incomplete_orders}