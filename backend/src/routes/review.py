from fastapi import APIRouter,Depends
from ..services.auth import current_user
from ..services.review import customer_review
router=APIRouter(prefix='/review')
@router.get('/customers/{customer}')
def review(customer:str,user=Depends(current_user)):return customer_review(customer)
