from sqlalchemy import Column, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from wms_app.database.database import Base

class Product(Base):
    __tablename__ = "products"

    sku = Column(String, primary_key=True, index=True)
    description = Column(String, index=True)
    estimated_value = Column(Float, default=0.0)

    eans = relationship("EanCode", back_populates="product")

class EanCode(Base):
    __tablename__ = "ean_codes"

    ean = Column(String, primary_key=True, index=True)
    product_sku = Column(String, ForeignKey("products.sku"))

    product = relationship("Product", back_populates="eans")
