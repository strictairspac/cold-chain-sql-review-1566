import time
from datetime import datetime
from sqlalchemy import select,text
from sqlalchemy.exc import IntegrityError,OperationalError
from fastapi import HTTPException
from ..models.claim import Claim
from ..models.payment import Payment
from ..models.bill import Bill
from ..models.allocation import Allocation
from ..models.receipt import Receipt
LOCK_TIMEOUT_SQL=text("SET LOCAL lock_timeout = '3s'")
def _busy(exc):
    code=getattr(getattr(exc,'orig',None),'pgcode',None) or getattr(getattr(exc,'orig',None),'sqlstate',None)
    return code in ('55P03','40P01')
def serialize(x,receipt=None):
    payment=getattr(x,'payment',None);bill=getattr(x,'bill',None)
    return {'id':x.id,'idempotency_key':x.idempotency_key,'payment_id':x.payment_id,'bill_id':x.bill_id,
        'payment_no':payment.payment_no if payment else None,'bill_no':bill.bill_no if bill else None,
        'customer':payment.customer if payment else None,'amount':f'{x.amount:.2f}','status':x.status,
        'reject_reason':x.reject_reason,'receipt_no':receipt.receipt_no if receipt else None,
        'created_by':x.created_by,'created_at':str(x.created_at),'posted_at':str(x.posted_at) if x.posted_at else None}
def _load(db,claim_id):
    claim=db.get(Claim,claim_id)
    if claim:claim.payment=db.get(Payment,claim.payment_id);claim.bill=db.get(Bill,claim.bill_id)
    return claim
def list_claims(db,status=None,customer=None):
    q=select(Claim).order_by(Claim.id.desc())
    if status:q=q.where(Claim.status==status)
    rows=db.scalars(q).all()
    receipts={r.claim_id:r for r in db.scalars(select(Receipt).where(Receipt.claim_id.in_([c.id for c in rows]))).all()} if rows else {}
    out=[]
    for c in rows:
        c.payment=db.get(Payment,c.payment_id);c.bill=db.get(Bill,c.bill_id)
        if customer and c.payment.customer!=customer:continue
        out.append(serialize(c,receipts.get(c.id)))
    return out
def get_claim(db,claim_id):
    claim=_load(db,claim_id)
    if not claim:raise HTTPException(404,'认领单不存在')
    receipt=db.scalar(select(Receipt).where(Receipt.claim_id==claim.id))
    return serialize(claim,receipt)
def get_receipt(db,claim_id):
    claim=_load(db,claim_id)
    if not claim:raise HTTPException(404,'认领单不存在')
    receipt=db.scalar(select(Receipt).where(Receipt.claim_id==claim.id))
    if not receipt:raise HTTPException(404,'该认领尚未入账，没有回执')
    return receipt.payload
def create_claim(db,data,user):
    existing=db.scalar(select(Claim).where(Claim.idempotency_key==data.idempotency_key))
    if existing:return serialize(_load(db,existing.id)),True
    payment=db.get(Payment,data.payment_id)
    if not payment:raise HTTPException(404,'到账款不存在')
    bill=db.get(Bill,data.bill_id)
    if not bill:raise HTTPException(404,'账单不存在')
    if payment.customer!=bill.customer:raise HTTPException(422,'到账与账单不属于同一客户，不能认领')
    if payment.status=='reversed':raise HTTPException(422,'到账已被银行冲回')
    if bill.status=='settled':raise HTTPException(422,'账单已结清')
    if data.amount>payment.balance:raise HTTPException(422,'申请金额超过到账余额')
    if data.amount>bill.outstanding:raise HTTPException(422,'申请金额超过账单欠款')
    claim=Claim(idempotency_key=data.idempotency_key,payment_id=payment.id,bill_id=bill.id,amount=data.amount,created_by=user.email)
    db.add(claim)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        for _ in range(20):
            existing=db.scalar(select(Claim).where(Claim.idempotency_key==data.idempotency_key))
            if existing:return serialize(_load(db,existing.id)),True
            time.sleep(0.05)
        raise HTTPException(409,'相同幂等键的认领正在登记，请稍后查询结果')
    return serialize(_load(db,claim.id)),False
def process_claim(db,claim_id):
    db.execute(LOCK_TIMEOUT_SQL)
    try:
        claim=db.scalar(select(Claim).where(Claim.id==claim_id).with_for_update())
        if not claim:raise HTTPException(404,'认领单不存在')
        if claim.status=='posted':
            receipt=db.scalar(select(Receipt).where(Receipt.claim_id==claim.id))
            return {'claim':serialize(_load(db,claim.id),receipt),'receipt':receipt.payload if receipt else None,'replayed':True}
        if claim.status=='rejected':
            return {'claim':serialize(_load(db,claim.id)),'receipt':None,'replayed':True}
        payment=db.scalar(select(Payment).where(Payment.id==claim.payment_id).with_for_update())
        bill=db.scalar(select(Bill).where(Bill.id==claim.bill_id).with_for_update())
        reason=None
        if payment.status=='reversed':reason='到账已被银行冲回'
        elif bill.status=='settled':reason='账单已结清'
        elif payment.balance<claim.amount:reason='到账余额不足'
        elif bill.outstanding<claim.amount:reason='账单欠款不足'
        if reason:
            claim.status='rejected';claim.reject_reason=reason;db.commit()
            return {'claim':serialize(_load(db,claim.id)),'receipt':None,'replayed':False}
        payment.balance-=claim.amount
        bill.outstanding-=claim.amount
        if bill.outstanding==0:bill.status='settled'
        claim.status='posted';claim.posted_at=datetime.now()
        db.add(Allocation(claim_id=claim.id,payment_id=payment.id,bill_id=bill.id,amount=claim.amount))
        payload={'receipt_no':f'RCPT-{claim.id:08d}','claim_id':claim.id,'payment_no':payment.payment_no,'bill_no':bill.bill_no,
            'customer':payment.customer,'amount':f'{claim.amount:.2f}','payment_balance_after':f'{payment.balance:.2f}',
            'bill_outstanding_after':f'{bill.outstanding:.2f}','posted_at':str(claim.posted_at),'operator':claim.created_by}
        receipt=Receipt(receipt_no=payload['receipt_no'],claim_id=claim.id,payload=payload)
        db.add(receipt);db.commit()
        return {'claim':serialize(_load(db,claim.id),receipt),'receipt':payload,'replayed':False}
    except OperationalError as exc:
        db.rollback()
        if _busy(exc):raise HTTPException(409,'该到账或账单正被其他操作占用，请稍后重试')
        raise
