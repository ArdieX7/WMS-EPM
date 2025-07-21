from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func

from wms_app.database.database import Base

class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())