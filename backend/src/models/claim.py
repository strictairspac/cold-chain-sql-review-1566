from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,Numeric,DateTime,ForeignKey,func
from datetime import datetime
from decimal import Decimal
from typing import Optional
from ..config.database import Base
class Claim(Base):
    __tablename__='claims'
    id:Mapped[int]=mapped_column(primary_key=True)
    idempotency_key:Mapped[str]=mapped_column(String(80),unique=True)
    payment_id:Mapped[int]=mapped_column(ForeignKey('payments.id'))
    bill_id:Mapped[int]=mapped_column(ForeignKey('bills.id'))
    amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    status:Mapped[str]=mapped_column(String(20),default='pending')
    reject_reason:Mapped[Optional[str]]=mapped_column(String(200))
    created_by:Mapped[str]=mapped_column(String(120))
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
    posted_at:Mapped[Optional[datetime]]=mapped_column(DateTime)
