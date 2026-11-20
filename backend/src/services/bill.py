from sqlalchemy import select
from fastapi import HTTPException
from ..models.bill import Bill
def serialize(x):
    return {'id':x.id,'bill_no':x.bill_no,'customer':x.customer,'amount':f'{x.amount:.2f}','outstanding':f'{x.outstanding:.2f}','status':x.status,'created_at':str(x.created_at)}
def list_bills(db,customer=None,status=None):
    q=select(Bill).order_by(Bill.id)
    if customer:q=q.where(Bill.customer==customer)
    if status:q=q.where(Bill.status==status)
    return [serialize(x) for x in db.scalars(q)]
def create_bill(db,data):
    if db.scalar(select(Bill).where(Bill.bill_no==data.bill_no)):raise HTTPException(409,'账单编号已存在')
    obj=Bill(bill_no=data.bill_no,customer=data.customer,amount=data.amount,outstanding=data.amount)
    db.add(obj);db.commit();return serialize(obj)
