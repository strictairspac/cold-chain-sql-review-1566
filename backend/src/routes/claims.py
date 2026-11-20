from fastapi import APIRouter,Depends,Response
from ..config.database import get_db
from ..schemas.claim import ClaimInput
from ..services.auth import current_user,writer
from ..services.claim import list_claims,get_claim,get_receipt,create_claim,process_claim
router=APIRouter(prefix='/claims')
@router.get('')
def listing(status:str=None,customer:str=None,db=Depends(get_db),user=Depends(current_user)):return list_claims(db,status,customer)
@router.post('')
def create(data:ClaimInput,response:Response,db=Depends(get_db),user=Depends(writer)):
    body,replayed=create_claim(db,data,user)
    response.status_code=200 if replayed else 201
    if replayed:response.headers['X-Idempotent-Replay']='true'
    return body
@router.get('/{claim_id}')
def detail(claim_id:int,db=Depends(get_db),user=Depends(current_user)):return get_claim(db,claim_id)
@router.get('/{claim_id}/receipt')
def receipt(claim_id:int,db=Depends(get_db),user=Depends(current_user)):return get_receipt(db,claim_id)
@router.post('/{claim_id}/process')
def process(claim_id:int,db=Depends(get_db),user=Depends(writer)):return process_claim(db,claim_id)
