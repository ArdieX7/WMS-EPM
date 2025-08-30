from sqlalchemy import Column, String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from wms_app.database.database import Base

class Location(Base):
    __tablename__ = "locations"

    name = Column(String, primary_key=True, index=True)
    available = Column(Boolean, default=True, nullable=False)  # True = disponibile, False = non disponibile
    # In futuro potremmo aggiungere dettagli come tipo_ubicazione (scaffale, terra), capacità, etc.

    inventory_items = relationship("Inventory", back_populates="location")

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    location_name = Column(String, ForeignKey("locations.name"))
    product_sku = Column(String, ForeignKey("products.sku"))
    quantity = Column(Integer, default=0)

    location = relationship("Location", back_populates="inventory_items")
    product = relationship("Product")
