from sqlalchemy import text
from ..config.database import engine
SNAPSHOT_SQL=text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
def customer_review(customer):
    """同一 REPEATABLE READ 只读快照内读到账侧与账单侧，两侧看到的是同一版欠款。"""
    with engine.connect() as conn:
        conn.execute(SNAPSHOT_SQL)
        payments=[dict(r) for r in conn.execute(text(
            "SELECT id,payment_no,customer,received_amount::text,balance::text,status FROM payments WHERE customer=:c ORDER BY id"),{'c':customer}).mappings()]
        bills=[dict(r) for r in conn.execute(text(
            "SELECT id,bill_no,customer,amount::text,outstanding::text,status FROM bills WHERE customer=:c ORDER BY id"),{'c':customer}).mappings()]
        allocations=[dict(r) for r in conn.execute(text(
            "SELECT a.id,a.claim_id,p.payment_no,b.bill_no,a.amount::text AS amount,a.status "
            "FROM allocations a JOIN payments p ON p.id=a.payment_id JOIN bills b ON b.id=a.bill_id "
            "WHERE p.customer=:c ORDER BY a.id"),{'c':customer}).mappings()]
    active={}
    for a in allocations:
        if a['status']=='active':active[a['bill_no']]=active.get(a['bill_no'],0)+float(a['amount'])
    checks=[{'bill_no':b['bill_no'],'allocated':f"{active.get(b['bill_no'],0):.2f}",
        'reduced':f"{float(b['amount'])-float(b['outstanding']):.2f}",
        'match':abs(active.get(b['bill_no'],0)-(float(b['amount'])-float(b['outstanding'])))<0.005} for b in bills]
    totals={'received':f"{sum(float(p['received_amount']) for p in payments):.2f}",
        'balance':f"{sum(float(p['balance']) for p in payments):.2f}",
        'billed':f"{sum(float(b['amount']) for b in bills):.2f}",
        'outstanding':f"{sum(float(b['outstanding']) for b in bills):.2f}"}
    return {'customer':customer,'payments':payments,'bills':bills,'allocations':allocations,
        'checks':checks,'totals':totals,'reconciled':all(c['match'] for c in checks),
        'snapshot':'REPEATABLE READ / READ ONLY 单事务快照'}
