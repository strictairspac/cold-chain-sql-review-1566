from pydantic import BaseModel,Field
from decimal import Decimal
class ClaimInput(BaseModel):
    payment_id:int=Field(gt=0)
    bill_id:int=Field(gt=0)
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
    idempotency_key:str=Field(min_length=8,max_length=80)
