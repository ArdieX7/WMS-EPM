from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from wms_app.database.database import Base

class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    location_name = Column(String, ForeignKey("locations.name"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    reserved_quantity = Column(Integer, nullable=False)
    order_id = Column(String, nullable=False)  # Riferimento all'ordine
    reserved_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="active")  # 'active', 'completed', 'expired', 'cancelled'
    
    # Relazioni
    location = relationship("Location")
    product = relationship("Product")
    
    def __repr__(self):
        return f"<Reservation(order={self.order_id}, sku={self.product_sku}, loc={self.location_name}, qty={self.reserved_quantity})>"