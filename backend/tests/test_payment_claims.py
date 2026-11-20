import threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
import httpx,psycopg2,pytest
from sqlalchemy.engine.url import make_url
from conftest import TEST_DB
def req(method,path,headers=None,json=None):
    return httpx.request(method,path,headers=headers or {},json=json,timeout=20)
def uid():return uuid.uuid4().hex[:8].upper()
def make_payment(base,tokens,customer,amount,no=None):
    r=req('POST',base+'/payments',tokens['operator'],{'payment_no':no or 'PAY-T-'+uid(),'customer':customer,'received_amount':amount})
    assert r.status_code==201,r.text
    return r.json()
def make_bill(base,tokens,customer,amount,no=None):
    r=req('POST',base+'/bills',tokens['operator'],{'bill_no':no or 'BILL-T-'+uid(),'customer':customer,'amount':amount})
    assert r.status_code==201,r.text
    return r.json()
def make_claim(base,tokens,payment_id,bill_id,amount,key=None):
    return req('POST',base+'/claims',tokens['operator'],{'payment_id':payment_id,'bill_id':bill_id,'amount':amount,'idempotency_key':key or 'key-'+uid()})
def process(base,tokens,claim_id):return req('POST',f"{base}/claims/{claim_id}/process",tokens['operator'])
def reverse(base,tokens,payment_id,reason='银行退票'):return req('POST',f"{base}/payments/{payment_id}/reverse",tokens['operator'],{'reason':reason})
def run_raced(base,tasks):
    """tasks: list of zero-arg callables; all released by one barrier to force contention."""
    barrier=threading.Barrier(len(tasks))
    def wrapped(fn):
        barrier.wait(timeout=15)
        return fn()
    with ThreadPoolExecutor(max_workers=len(tasks)) as ex:return list(ex.map(wrapped,tasks))
def get_payment(base,tokens,payment_id):
    return next(p for p in req('GET',base+'/payments',headers=tokens['viewer']).json() if p['id']==payment_id)
def get_bill(base,tokens,bill_id):
    return next(b for b in req('GET',base+'/bills',headers=tokens['viewer']).json() if b['id']==bill_id)
def review(base,tokens,customer):return req('GET',f'{base}/review/customers/{customer}',headers=tokens['viewer']).json()

def test_installments_split_and_settle(server,tokens):
    """分次认领：一笔到账分三次抵给同客户两张账单，两侧同步扣减、账单结清。"""
    c='分次客户-'+uid()
    p=make_payment(server,tokens,c,'1000.00')
    b1=make_bill(server,tokens,c,'600.00');b2=make_bill(server,tokens,c,'400.00')
    receipts=[]
    for bill,amount in ((b1,'300.00'),(b1,'300.00'),(b2,'400.00')):
        claim=make_claim(server,tokens,p['id'],bill['id'],amount)
        assert claim.status_code==201,claim.text
        done=process(server,tokens,claim.json()['id'])
        assert done.status_code==200 and done.json()['claim']['status']=='posted',done.text
        receipts.append(done.json()['receipt']['receipt_no'])
    assert len(set(receipts))==3
    assert get_payment(server,tokens,p['id'])['balance']=='0.00'
    assert get_bill(server,tokens,b1['id'])['status']=='settled'
    assert get_bill(server,tokens,b2['id'])['outstanding']=='0.00'

def test_two_payments_compete_for_one_bill(server,tokens):
    """实测一：两笔到账抢同一账单。欠款 100、各认 80，必有一笔被拒，且无关款项照办。"""
    c='抢单客户-'+uid()
    bill=make_bill(server,tokens,c,'100.00')
    p1=make_payment(server,tokens,c,'100.00');p2=make_payment(server,tokens,c,'100.00')
    other=make_payment(server,tokens,c,'100.00');other_bill=make_bill(server,tokens,c,'50.00')
    c1=make_claim(server,tokens,p1['id'],bill['id'],'80.00').json()
    c2=make_claim(server,tokens,p2['id'],bill['id'],'80.00').json()
    c3=make_claim(server,tokens,other['id'],other_bill['id'],'30.00').json()
    r1,r2,r3=run_raced(server,[lambda:process(server,tokens,c1['id']),lambda:process(server,tokens,c2['id']),lambda:process(server,tokens,c3['id'])])
    for r in (r1,r2,r3):assert r.status_code==200,r.text
    outcomes=[r1.json()['claim']['status'],r2.json()['claim']['status']]
    assert sorted(outcomes)==['posted','rejected'],outcomes
    loser=r1.json()['claim'] if outcomes[0]=='rejected' else r2.json()['claim']
    assert loser['reject_reason']=='账单欠款不足'
    assert r3.json()['claim']['status']=='posted','无关款项应照常入账'
    assert get_bill(server,tokens,bill['id'])['outstanding']=='20.00'
    balances=sorted((get_payment(server,tokens,p1['id'])['balance'],get_payment(server,tokens,p2['id'])['balance']))
    assert balances==['100.00','20.00'],balances
    snap=review(server,tokens,c)
    assert snap['reconciled'] and all(float(b['outstanding'])>=0 for b in snap['bills'])
    assert all(float(p['balance'])>=0 for p in snap['payments'])

def test_claim_collides_with_reversal(server,tokens):
    """实测二：认领撞冲回。无论谁先落账，最终欠款恢复、余额归零、不出现负数。"""
    seen=set()
    for round_no in range(5):
        c='冲回客户-'+uid()
        p=make_payment(server,tokens,c,'500.00');bill=make_bill(server,tokens,c,'300.00')
        claim=make_claim(server,tokens,p['id'],bill['id'],'200.00').json()
        r_claim,r_reverse=run_raced(server,[lambda:process(server,tokens,claim['id']),lambda:reverse(server,tokens,p['id'])])
        assert r_claim.status_code==200 and r_reverse.status_code==200,(r_claim.text,r_reverse.text)
        outcome=r_claim.json()['claim']['status'];seen.add(outcome)
        pay=get_payment(server,tokens,p['id']);bl=get_bill(server,tokens,bill['id'])
        assert pay['status']=='reversed' and pay['balance']=='0.00',pay
        assert bl['outstanding']=='300.00',bl
        if outcome=='posted':
            assert r_claim.json()['receipt']['receipt_no']
        else:
            assert outcome=='rejected' and r_claim.json()['claim']['reject_reason']=='到账已被银行冲回'
        snap=review(server,tokens,c)
        assert snap['reconciled']
        assert not [a for a in snap['allocations'] if a['status']=='active'],'冲回后不应残留有效抵扣'
    print('\n撞冲回覆盖到的结果分支:',sorted(seen))

def test_lost_receipt_retry(server,tokens):
    """实测三：落账后丢回执。重试登记与重试办理都不能重复落账。"""
    c='回执客户-'+uid()
    p=make_payment(server,tokens,c,'800.00');bill=make_bill(server,tokens,c,'800.00')
    key='lost-receipt-'+uid()
    first=make_claim(server,tokens,p['id'],bill['id'],'500.00',key)
    assert first.status_code==201,first.text
    claim_id=first.json()['id']
    replays=run_raced(server,[lambda:make_claim(server,tokens,p['id'],bill['id'],'500.00',key) for _ in range(6)])
    assert all(r.status_code==200 and r.json()['id']==claim_id for r in replays)
    keys=[x for x in req('GET',server+'/claims',headers=tokens['viewer']).json() if x['idempotency_key']==key]
    assert len(keys)==1,'同一幂等键只能落一条认领单'
    posted=process(server,tokens,claim_id)
    assert posted.status_code==200 and posted.json()['receipt'],posted.text
    receipt_no=posted.json()['receipt']['receipt_no']
    retries=run_raced(server,[lambda:process(server,tokens,claim_id) for _ in range(6)])
    assert all(r.status_code==200 and r.json()['receipt'] and r.json()['receipt']['receipt_no']==receipt_no for r in retries)
    assert all(r.json()['replayed'] for r in retries)
    assert get_payment(server,tokens,p['id'])['balance']=='300.00','重试不得重复扣减到账余额'
    assert get_bill(server,tokens,bill['id'])['outstanding']=='300.00','重试不得重复扣减账单欠款'
    snap=review(server,tokens,c)
    mine=[a for a in snap['allocations'] if a['claim_id']==claim_id]
    assert len(mine)==1,'同一认领只能产生一条抵扣明细'
    refetch=req('GET',f"{server}/claims/{claim_id}/receipt",headers=tokens['viewer'])
    assert refetch.status_code==200 and refetch.json()['receipt_no']==receipt_no

def test_review_reads_same_snapshot(server,tokens):
    """复核：接口在写入风暴下始终勾稽一致；单事务内两侧读到同一版欠款。"""
    c='复核客户-'+uid()
    p=make_payment(server,tokens,c,'5000.00')
    bills=[make_bill(server,tokens,c,'900.00') for _ in range(3)]
    stop=threading.Event()
    def writer():
        while not stop.is_set():
            bill=bills[int(time.time()*1000)%3]
            claim=make_claim(server,tokens,p['id'],bill['id'],'1.00')
            if claim.status_code==201:process(server,tokens,claim.json()['id'])
    threads=[threading.Thread(target=writer,daemon=True) for _ in range(3)]
    for t in threads:t.start()
    try:
        for _ in range(15):
            snap=review(server,tokens,c)
            assert snap['reconciled'],snap['checks']
            assert all(x['match'] for x in snap['checks'])
            time.sleep(0.05)
    finally:
        stop.set()
        for t in threads:t.join()
    u=make_url(TEST_DB)
    conn=psycopg2.connect(host=u.host,port=u.port or 5432,user=u.username,password=u.password,dbname=u.database)
    conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
    cur=conn.cursor()
    cur.execute("SELECT COALESCE(SUM(balance),0) FROM payments WHERE customer=%s",(c,))
    before_balance=cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(outstanding),0) FROM bills WHERE customer=%s",(c,))
    before_outstanding=cur.fetchone()[0]
    claim=make_claim(server,tokens,p['id'],bills[0]['id'],'7.00')
    if claim.status_code==201:process(server,tokens,claim.json()['id'])
    cur.execute("SELECT COALESCE(SUM(balance),0) FROM payments WHERE customer=%s",(c,))
    after_balance=cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(outstanding),0) FROM bills WHERE customer=%s",(c,))
    after_outstanding=cur.fetchone()[0]
    assert after_balance==before_balance and after_outstanding==before_outstanding,'REPEATABLE READ 事务内必须读到同一版欠款'
    conn.close()
    snap=review(server,tokens,c)
    assert snap['reconciled']

def test_viewer_readonly_and_overdraft(server,tokens):
    """只读限制照旧：观察员可复核查看，所有写操作被 403 拒绝；超额认领被拒绝且不为负。"""
    c='只读客户-'+uid()
    p=make_payment(server,tokens,c,'100.00');bill=make_bill(server,tokens,c,'100.00')
    claim=make_claim(server,tokens,p['id'],bill['id'],'50.00').json()
    for method,path,body in (('POST','/payments',{'payment_no':'PAY-V-'+uid(),'customer':c,'received_amount':'1.00'}),
        ('POST','/bills',{'bill_no':'BILL-V-'+uid(),'customer':c,'amount':'1.00'}),
        ('POST','/claims',{'payment_id':p['id'],'bill_id':bill['id'],'amount':'1.00','idempotency_key':'viewer-'+uid()}),
        ('POST',f"/claims/{claim['id']}/process",None),('POST',f"/payments/{p['id']}/reverse",{'reason':'测试'})):
        r=req(method,server+path,tokens['viewer'],body)
        assert r.status_code==403,(method,path,r.status_code,r.text)
    for path in ('/payments','/bills','/claims',f'/review/customers/{c}'):
        assert req('GET',server+path,headers=tokens['viewer']).status_code==200
    too_much=make_claim(server,tokens,p['id'],bill['id'],'150.00')
    assert too_much.status_code==422,too_much.text
    negative=make_claim(server,tokens,p['id'],bill['id'],'-5.00')
    assert negative.status_code==422
    mismatch=make_bill(server,tokens,'其他客户-'+uid(),'10.00')
    cross=make_claim(server,tokens,p['id'],mismatch['id'],'10.00')
    assert cross.status_code==422 and '同一客户' in cross.text
    assert get_payment(server,tokens,p['id'])['balance']=='100.00'
    assert get_bill(server,tokens,bill['id'])['outstanding']=='100.00'
