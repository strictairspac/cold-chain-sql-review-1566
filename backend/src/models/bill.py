from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,Numeric,DateTime,func
from datetime import datetime
from decimal import Decimal
from ..config.database import Base
class Bill(Base):
    __tablename__='bills'
    id:Mapped[int]=mapped_column(primary_key=True)
    bill_no:Mapped[str]=mapped_column(String(40),unique=True)
    customer:Mapped[str]=mapped_column(String(120))
    amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    outstanding:Mapped[Decimal]=mapped_column(Numeric(14,2))
    status:Mapped[str]=mapped_column(String(20),default='open')
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
