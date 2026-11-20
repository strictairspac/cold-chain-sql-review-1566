from pydantic import BaseModel,Field
from decimal import Decimal
class PaymentInput(BaseModel):
    payment_no:str=Field(min_length=4,max_length=40,pattern=r'^[A-Za-z0-9-]+$')
    customer:str=Field(min_length=2,max_length=120)
    received_amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
