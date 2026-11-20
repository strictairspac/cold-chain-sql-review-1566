from fastapi import APIRouter,Depends
from ..config.database import get_db
from ..schemas.bill import BillInput
from ..services.auth import current_user,writer
from ..services.bill import list_bills,create_bill
router=APIRouter(prefix='/bills')
@router.get('')
def listing(customer:str=None,status:str=None,db=Depends(get_db),user=Depends(current_user)):return list_bills(db,customer,status)
@router.post('',status_code=201)
def create(data:BillInput,db=Depends(get_db),user=Depends(writer)):return create_bill(db,data)
