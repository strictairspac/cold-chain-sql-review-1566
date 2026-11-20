from fastapi import APIRouter,Depends
from ..config.database import get_db
from ..schemas.payment import PaymentInput
from ..schemas.reversal import ReversalInput
from ..services.auth import current_user,writer
from ..services.payment import list_payments,create_payment,list_customers
from ..services.reversal import reverse_payment
router=APIRouter(prefix='/payments')
@router.get('')
def listing(customer:str=None,status:str=None,db=Depends(get_db),user=Depends(current_user)):return list_payments(db,customer,status)
@router.post('',status_code=201)
def create(data:PaymentInput,db=Depends(get_db),user=Depends(writer)):return create_payment(db,data)
@router.post('/{payment_id}/reverse')
def reverse(payment_id:int,data:ReversalInput,db=Depends(get_db),user=Depends(writer)):return reverse_payment(db,payment_id,data,user)
@router.get('/meta/customers')
def customers(db=Depends(get_db),user=Depends(current_user)):return list_customers(db)
