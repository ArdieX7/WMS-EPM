from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from wms_app.database.database import Base


class Arrival(Base):
    """Documento di arrivo merce da fornitore"""
    __tablename__ = "arrivals"

    id = Column(Integer, primary_key=True, index=True)
    arrival_number = Column(String, unique=True, index=True, nullable=False)
    supplier_name = Column(String, nullable=False)
    arrival_date = Column(DateTime, default=func.now())
    created_date = Column(DateTime, default=func.now())

    # Stati documento
    is_draft = Column(Boolean, default=True)  # True = bozza editabile, False = confermato
    is_completed = Column(Boolean, default=False)  # True = caricato a TERRA
    completed_date = Column(DateTime, nullable=True)

    # Metadati
    notes = Column(Text, nullable=True)

    # Relazioni
    lines = relationship("ArrivalLine", back_populates="arrival", cascade="all, delete-orphan")


class ArrivalLine(Base):
    """Righe prodotto per documento arrivo"""
    __tablename__ = "arrival_lines"

    id = Column(Integer, primary_key=True, index=True)
    arrival_id = Column(Integer, ForeignKey("arrivals.id"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    expected_quantity = Column(Integer, nullable=False)
    received_quantity = Column(Integer, default=0)

    # Relazioni
    arrival = relationship("Arrival", back_populates="lines")
    product = relationship("Product")
