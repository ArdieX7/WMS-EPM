from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from wms_app.database.database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True) # Numero ordine esterno
    customer_name = Column(String)
    order_date = Column(DateTime, default=func.now())
    is_completed = Column(Boolean, default=False)

    lines = relationship("OrderLine", back_populates="order")

class OrderLine(Base):
    __tablename__ = "order_lines"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_sku = Column(String, ForeignKey("products.sku"))
    requested_quantity = Column(Integer)
    picked_quantity = Column(Integer, default=0)

    order = relationship("Order", back_populates="lines")
    product = relationship("Product")

class OutgoingStock(Base):
    __tablename__ = "outgoing_stock"

    id = Column(Integer, primary_key=True, index=True)
    order_line_id = Column(Integer, ForeignKey("order_lines.id"))
    product_sku = Column(String, ForeignKey("products.sku"))
    quantity = Column(Integer)
    # Potremmo aggiungere qui l'ubicazione da cui è stato prelevato, se necessario per tracciabilità

    order_line = relationship("OrderLine")
    product = relationship("Product")
