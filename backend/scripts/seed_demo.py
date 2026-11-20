from datetime import datetime
from sqlalchemy import select
from src.config.database import Base,engine,Session
from src.models.user import User
from src.models.payment import Payment
from src.models.bill import Bill
from src.models.claim import Claim
from src.models.allocation import Allocation
from src.models.reversal import Reversal
from src.models.receipt import Receipt
from src.models.audit import Audit
from src.utils.password import hash_password
def seed():
    Base.metadata.create_all(engine)
    with Session() as db:
        for role in ('admin','operator','viewer'):
            email=role+'@chenggang.test'
            if not db.scalar(select(User).where(User.email==email)):db.add(User(email=email,role=role,password_hash=hash_password('ColdChain!17')))
        db.commit()
        payments=[('PAY-2026-1101','海润食品','10000.00','5000.00','active'),('PAY-2026-1102','海润食品','6000.00','6000.00','active'),
            ('PAY-2026-1103','北屿水产','8000.00','3000.00','active'),('PAY-2026-1104','岚山乳业','12000.00','12000.00','active'),
            ('PAY-2026-1105','海润食品','3000.00','0.00','reversed')]
        pmap={}
        for no,customer,received,balance,status in payments:
            obj=db.scalar(select(Payment).where(Payment.payment_no==no))
            if not obj:obj=Payment(payment_no=no,customer=customer,received_amount=received,balance=balance,status=status);db.add(obj);db.flush()
            pmap[no]=obj
        bills=[('BILL-HR-01','海润食品','8000.00','5000.00','open'),('BILL-HR-02','海润食品','2000.00','0.00','settled'),
            ('BILL-HR-03','海润食品','3000.00','3000.00','open'),('BILL-HR-04','海润食品','4500.00','4500.00','open'),
            ('BILL-BY-01','北屿水产','9000.00','4000.00','open'),('BILL-BY-02','北屿水产','1500.00','1500.00','open'),
            ('BILL-LS-01','岚山乳业','12000.00','12000.00','open')]
        bmap={}
        for no,customer,amount,outstanding,status in bills:
            obj=db.scalar(select(Bill).where(Bill.bill_no==no))
            if not obj:obj=Bill(bill_no=no,customer=customer,amount=amount,outstanding=outstanding,status=status);db.add(obj);db.flush()
            bmap[no]=obj
        claims=[('seed-clm-0001','PAY-2026-1101','BILL-HR-01','3000.00','posted',None),
            ('seed-clm-0002','PAY-2026-1101','BILL-HR-02','2000.00','posted',None),
            ('seed-clm-0003','PAY-2026-1103','BILL-BY-01','5000.00','posted',None),
            ('seed-clm-0004','PAY-2026-1105','BILL-HR-03','3000.00','posted',None),
            ('seed-clm-0005','PAY-2026-1102','BILL-HR-04','1000.00','pending',None),
            ('seed-clm-0006','PAY-2026-1102','BILL-HR-04','9999.00','rejected','账单欠款不足')]
        for key,pno,bno,amount,status,reason in claims:
            if db.scalar(select(Claim).where(Claim.idempotency_key==key)):continue
            claim=Claim(idempotency_key=key,payment_id=pmap[pno].id,bill_id=bmap[bno].id,amount=amount,status=status,
                reject_reason=reason,created_by='operator@chenggang.test',posted_at=datetime.now() if status=='posted' else None)
            db.add(claim);db.flush()
            if status=='posted':
                reversed_alloc=key=='seed-clm-0004'
                db.add(Allocation(claim_id=claim.id,payment_id=claim.payment_id,bill_id=claim.bill_id,amount=amount,
                    status='reversed' if reversed_alloc else 'active',reversed_at=datetime.now() if reversed_alloc else None))
                payload={'receipt_no':f'RCPT-{claim.id:08d}','claim_id':claim.id,'payment_no':pno,'bill_no':bno,'customer':pmap[pno].customer,
                    'amount':amount,'payment_balance_after':str(pmap[pno].balance),'bill_outstanding_after':str(bmap[bno].outstanding),
                    'posted_at':str(claim.posted_at),'operator':'operator@chenggang.test'}
                db.add(Receipt(receipt_no=payload['receipt_no'],claim_id=claim.id,payload=payload))
        if not db.scalar(select(Reversal).where(Reversal.payment_id==pmap['PAY-2026-1105'].id)):
            db.add(Reversal(payment_id=pmap['PAY-2026-1105'].id,reason='银行退票：付款方账户止付',actor='admin@chenggang.test'))
        db.commit()
        from sqlalchemy import text
        return {t:db.execute(text('SELECT COUNT(*) FROM '+t)).scalar() for t in ('users','payments','bills','claims','allocations','receipts','reversals')}
if __name__=='__main__':print(seed())
