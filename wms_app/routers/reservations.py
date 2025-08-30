from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import datetime

from wms_app.database import get_db
from wms_app.routers.auth import require_permission
from wms_app.services.reservation_service import ReservationService
from wms_app.models.reservations import InventoryReservation
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="wms_app/templates")

router = APIRouter(
    prefix="/reservations",
    tags=["reservations"],
)

@router.get("/dashboard", response_class=HTMLResponse)
async def get_reservations_dashboard(request: Request, db: Session = Depends(get_db)): 
    """Dashboard per gestire le prenotazioni di inventario"""
    
    # Ottieni statistiche prenotazioni
    active_count = db.query(InventoryReservation).filter(
        InventoryReservation.status == 'active'
    ).count()
    
    expired_count = db.query(InventoryReservation).filter(
        InventoryReservation.status == 'expired'
    ).count()
    
    completed_count = db.query(InventoryReservation).filter(
        InventoryReservation.status == 'completed'
    ).count()
    
    # Ottieni prenotazioni attive
    active_reservations = db.query(InventoryReservation).filter(
        InventoryReservation.status == 'active'
    ).order_by(InventoryReservation.reserved_at.desc()).limit(50).all()
    
    return templates.TemplateResponse("reservations.html", {
        "request": request,
        "active_page": "reservations",
        "stats": {
            "active": active_count,
            "expired": expired_count,
            "completed": completed_count
        },
        "active_reservations": active_reservations
    })

@router.get("/status")
def get_reservations_status(db: Session = Depends(get_db)):
    """Ottieni stato generale delle prenotazioni"""
    
    reservation_service = ReservationService(db)
    
    # Cleanup automatico
    expired_cleaned = reservation_service.cleanup_expired_reservations()
    
    # Statistiche
    stats = db.query(
        InventoryReservation.status,
        db.func.count(InventoryReservation.id).label('count')
    ).group_by(InventoryReservation.status).all()
    
    stats_dict = {stat.status: stat.count for stat in stats}
    
    return {
        "statistics": stats_dict,
        "expired_cleaned": expired_cleaned,
        "last_cleanup": datetime.utcnow().isoformat()
    }

@router.get("/active")
def get_active_reservations(db: Session = Depends(get_db)):
    """Ottieni tutte le prenotazioni attive"""
    
    reservations = db.query(InventoryReservation).filter(
        InventoryReservation.status == 'active'
    ).order_by(InventoryReservation.reserved_at.desc()).all()
    
    return [{
        "id": r.id,
        "order_id": r.order_id,
        "product_sku": r.product_sku,
        "location_name": r.location_name,
        "reserved_quantity": r.reserved_quantity,
        "reserved_at": r.reserved_at.isoformat(),
        "expires_at": r.expires_at.isoformat(),
        "status": r.status
    } for r in reservations]

@router.get("/order/{order_id}")
def get_reservations_by_order(order_id: str, db: Session = Depends(get_db)):
    """Ottieni prenotazioni per un ordine specifico"""
    
    reservation_service = ReservationService(db)
    return reservation_service.get_reservation_status(order_id)

@router.post("/cleanup/expired")
def cleanup_expired_reservations(db: Session = Depends(get_db)):
    """Cleanup manuale delle prenotazioni scadute"""
    
    reservation_service = ReservationService(db)
    cleaned_count = reservation_service.cleanup_expired_reservations()
    
    return {
        "message": f"Pulite {cleaned_count} prenotazioni scadute",
        "cleaned_count": cleaned_count,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/cleanup/all")
def cleanup_all_reservations(db: Session = Depends(get_db)):
    """
    CLEANUP MANUALE DI EMERGENZA - Cancella TUTTE le prenotazioni attive
    ATTENZIONE: Usare solo in caso di problemi gravi
    """
    
    reservation_service = ReservationService(db)
    cancelled_count = reservation_service.manual_cleanup_all_reservations()
    
    return {
        "message": f"RESET EMERGENZA: Cancellate {cancelled_count} prenotazioni attive",
        "cancelled_count": cancelled_count,
        "timestamp": datetime.utcnow().isoformat(),
        "warning": "Tutte le prenotazioni attive sono state cancellate"
    }

@router.delete("/{reservation_id}")
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """Cancella una prenotazione specifica"""
    
    reservation = db.query(InventoryReservation).filter(
        InventoryReservation.id == reservation_id
    ).first()
    
    if not reservation:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")
    
    if reservation.status != 'active':
        raise HTTPException(status_code=400, detail=f"Prenotazione già {reservation.status}")
    
    reservation.status = 'cancelled'
    db.commit()
    
    return {
        "message": f"Prenotazione {reservation_id} cancellata",
        "reservation_id": reservation_id,
        "order_id": reservation.order_id,
        "product_sku": reservation.product_sku,
        "location_name": reservation.location_name
    }

@router.get("/availability/{product_sku}")
def get_product_availability(product_sku: str, db: Session = Depends(get_db)):
    """Ottieni disponibilità di un prodotto considerando le prenotazioni"""
    
    reservation_service = ReservationService(db)
    locations = reservation_service.get_locations_with_availability(product_sku)
    
    return {
        "product_sku": product_sku,
        "locations": locations,
        "total_available": sum(loc['available_quantity'] for loc in locations)
    }