from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,DateTime,ForeignKey,JSON,func
from datetime import datetime
from ..config.database import Base
class Receipt(Base):
    __tablename__='receipts'
    id:Mapped[int]=mapped_column(primary_key=True)
    receipt_no:Mapped[str]=mapped_column(String(40),unique=True)
    claim_id:Mapped[int]=mapped_column(ForeignKey('claims.id'),unique=True)
    payload:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
