from sqlalchemy import select
from fastapi import HTTPException
from ..models.payment import Payment
from ..models.bill import Bill
def serialize(x):
    return {'id':x.id,'payment_no':x.payment_no,'customer':x.customer,'received_amount':f'{x.received_amount:.2f}','balance':f'{x.balance:.2f}','status':x.status,'created_at':str(x.created_at)}
def list_payments(db,customer=None,status=None):
    q=select(Payment).order_by(Payment.id)
    if customer:q=q.where(Payment.customer==customer)
    if status:q=q.where(Payment.status==status)
    return [serialize(x) for x in db.scalars(q)]
def create_payment(db,data):
    if db.scalar(select(Payment).where(Payment.payment_no==data.payment_no)):raise HTTPException(409,'到款编号已存在')
    obj=Payment(payment_no=data.payment_no,customer=data.customer,received_amount=data.received_amount,balance=data.received_amount)
    db.add(obj);db.commit();return serialize(obj)
def list_customers(db):
    q=select(Payment.customer).union(select(Bill.customer)).order_by(1)
    return [r[0] for r in db.execute(q)]
