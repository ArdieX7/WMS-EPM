from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from wms_app.database.database import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
