from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from wms_app.database.database import Base

class DDT(Base):
    __tablename__ = "ddt"

    id = Column(Integer, primary_key=True, index=True)
    ddt_number = Column(String, unique=True, index=True)
    order_number = Column(String, ForeignKey("orders.order_number"))
    customer_name = Column(String)
    customer_address = Column(Text, nullable=True)
    customer_city = Column(String, nullable=True)
    customer_cap = Column(String, nullable=True)
    customer_province = Column(String, nullable=True)
    
    # Informazioni trasportatore
    transporter_name = Column(String, nullable=True)
    transporter_notes = Column(Text, nullable=True)
    
    # Date
    issue_date = Column(DateTime, default=func.now())
    transport_date = Column(DateTime, nullable=True)
    
    # Causale trasporto
    transport_reason = Column(String, default="Vendita")
    
    # Numero colli e peso
    total_packages = Column(Integer, default=1)
    total_weight = Column(String, nullable=True)  # Es. "25.5 kg"
    
    # Note aggiuntive
    notes = Column(Text, nullable=True)
    
    # Stato
    is_printed = Column(Boolean, default=False)
    printed_date = Column(DateTime, nullable=True)
    
    # Relazioni
    order = relationship("Order")
    lines = relationship("DDTLine", back_populates="ddt")

class DDTLine(Base):
    __tablename__ = "ddt_lines"

    id = Column(Integer, primary_key=True, index=True)
    ddt_id = Column(Integer, ForeignKey("ddt.id"))
    product_sku = Column(String, ForeignKey("products.sku"))
    product_description = Column(String)
    quantity = Column(Integer)
    unit_measure = Column(String, default="pz")
    
    # Relazioni
    ddt = relationship("DDT", back_populates="lines")
    product = relationship("Product")