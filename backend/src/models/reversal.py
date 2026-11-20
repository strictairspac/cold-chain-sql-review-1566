from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,DateTime,ForeignKey,func
from datetime import datetime
from ..config.database import Base
class Reversal(Base):
    __tablename__='reversals'
    id:Mapped[int]=mapped_column(primary_key=True)
    payment_id:Mapped[int]=mapped_column(ForeignKey('payments.id'),unique=True)
    reason:Mapped[str]=mapped_column(String(200))
    actor:Mapped[str]=mapped_column(String(120))
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
