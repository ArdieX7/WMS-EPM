from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from wms_app.models.carriers import Carrier
from wms_app.database import get_db

router = APIRouter()


class CarrierCreate(BaseModel):
    name: str


@router.get("/")
def get_carriers(db: Session = Depends(get_db)):
    """Lista tutti i vettori attivi."""
    carriers = db.query(Carrier).filter(Carrier.is_active == True).order_by(Carrier.name).all()
    return {"carriers": [{"id": c.id, "name": c.name} for c in carriers]}


@router.post("/")
def create_carrier(body: CarrierCreate, db: Session = Depends(get_db)):
    """Aggiunge un nuovo vettore all'anagrafica."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Il nome del vettore non può essere vuoto")

    existing = db.query(Carrier).filter(Carrier.name == name).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=409, detail=f"Vettore '{name}' già presente")
        else:
            # Riattiva se era stato disattivato
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            return {"id": existing.id, "name": existing.name}

    carrier = Carrier(name=name)
    db.add(carrier)
    db.commit()
    db.refresh(carrier)
    return {"id": carrier.id, "name": carrier.name}


@router.delete("/{carrier_id}")
def delete_carrier(carrier_id: int, db: Session = Depends(get_db)):
    """Elimina un vettore dall'anagrafica."""
    carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
    if not carrier:
        raise HTTPException(status_code=404, detail="Vettore non trovato")
    db.delete(carrier)
    db.commit()
    return {"success": True, "message": f"Vettore '{carrier.name}' eliminato"}
