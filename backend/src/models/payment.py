from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,Numeric,DateTime,func
from datetime import datetime
from decimal import Decimal
from ..config.database import Base
class Payment(Base):
    __tablename__='payments'
    id:Mapped[int]=mapped_column(primary_key=True)
    payment_no:Mapped[str]=mapped_column(String(40),unique=True)
    customer:Mapped[str]=mapped_column(String(120))
    received_amount:Mapped[Decimal]=mapped_column(Numeric(14,2))
    balance:Mapped[Decimal]=mapped_column(Numeric(14,2))
    status:Mapped[str]=mapped_column(String(20),default='active')
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
