from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wms_app.database import database
from wms_app.models import products, inventory, orders

# --- ATTENZIONE: Ricrea il database ad ogni avvio ---
# Questa riga elimina tutte le tabelle esistenti e le ricrea. 
# Utile per lo sviluppo, da rimuovere in produzione.
products.Base.metadata.drop_all(bind=database.engine)
# --------------------------------------------------

# Crea le tabelle del database (solo se non esistono già)
products.Base.metadata.create_all(bind=database.engine)
inventory.Base.metadata.create_all(bind=database.engine)
orders.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="WMS EPM")

# Monta le cartelle per i file statici (CSS, JS) e i template (HTML)
app.mount("/static", StaticFiles(directory="wms_app/static"), name="static")
templates = Jinja2Templates(directory="wms_app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active_page": "home"})

# Qui aggiungeremo i router per le diverse sezioni dell'app
from wms_app.routers import products, inventory, orders, analysis, warehouse
app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(orders.router)
app.include_router(analysis.router)
app.include_router(warehouse.router)

@app.get("/products-page", response_class=HTMLResponse)
async def get_products_page(request: Request):
    return templates.TemplateResponse("products.html", {"request": request, "active_page": "products"})