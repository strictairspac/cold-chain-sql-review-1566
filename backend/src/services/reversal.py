from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from fastapi import HTTPException
from ..models.payment import Payment
from ..models.bill import Bill
from ..models.allocation import Allocation
from ..models.reversal import Reversal
from .claim import LOCK_TIMEOUT_SQL,_busy
def _summary(payment,reversal,restored,replayed):
    return {'payment_id':payment.id,'payment_no':payment.payment_no,'customer':payment.customer,'status':payment.status,
        'balance':f'{payment.balance:.2f}','reversal_id':reversal.id,'reason':reversal.reason,'actor':reversal.actor,
        'reversed_at':str(reversal.created_at),'restored':restored,'replayed':replayed}
def reverse_payment(db,payment_id,data,user):
    db.execute(LOCK_TIMEOUT_SQL)
    try:
        payment=db.scalar(select(Payment).where(Payment.id==payment_id).with_for_update())
        if not payment:raise HTTPException(404,'到账款不存在')
        if payment.status=='reversed':
            reversal=db.scalar(select(Reversal).where(Reversal.payment_id==payment.id))
            restored=[{'bill_no':db.get(Bill,a.bill_id).bill_no,'amount':f'{a.amount:.2f}'}
                for a in db.scalars(select(Allocation).where(Allocation.payment_id==payment.id,Allocation.status=='reversed').order_by(Allocation.bill_id))]
            return _summary(payment,reversal,restored,True)
        allocations=db.scalars(select(Allocation).where(Allocation.payment_id==payment.id,Allocation.status=='active').order_by(Allocation.bill_id)).all()
        restored=[]
        for a in allocations:
            bill=db.scalar(select(Bill).where(Bill.id==a.bill_id).with_for_update())
            bill.outstanding+=a.amount
            if bill.status=='settled':bill.status='open'
            a.status='reversed';a.reversed_at=datetime.now()
            restored.append({'bill_no':bill.bill_no,'amount':f'{a.amount:.2f}'})
        payment.balance=0;payment.status='reversed'
        reversal=Reversal(payment_id=payment.id,reason=data.reason,actor=user.email)
        db.add(reversal);db.commit()
        return _summary(payment,reversal,restored,False)
    except OperationalError as exc:
        db.rollback()
        if _busy(exc):raise HTTPException(409,'该到账或账单正被其他操作占用，请稍后重试')
        raise
