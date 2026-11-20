import os,time,threading
import pytest
TEST_DB=os.getenv('TEST_DATABASE_URL','postgresql+psycopg2://app@127.0.0.1:55432/payment_claims_test')
os.environ['DATABASE_URL']=TEST_DB
os.environ['JWT_SECRET']='test-secret-payment-claims-0123456789abcdef'
os.environ['SEED_DEMO']='false'
BASE_URL='http://127.0.0.1:18123'
def _ensure_database():
    import psycopg2
    from sqlalchemy.engine.url import make_url
    u=make_url(TEST_DB)
    adm=psycopg2.connect(host=u.host,port=u.port or 5432,user=u.username,password=u.password,dbname='postgres')
    adm.autocommit=True
    cur=adm.cursor()
    cur.execute('SELECT 1 FROM pg_database WHERE datname=%s',(u.database,))
    if not cur.fetchone():cur.execute(f'CREATE DATABASE "{u.database}"')
    adm.close()
@pytest.fixture(scope='session',autouse=True)
def server():
    _ensure_database()
    from src.config.database import Base,engine,Session
    from src.models import user as _u,payment as _p,bill as _b,claim as _c,allocation as _a,receipt as _r,reversal as _v,audit as _au
    from sqlalchemy import text,select
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text('TRUNCATE receipts,allocations,claims,reversals,payments,bills,audit,users RESTART IDENTITY CASCADE'))
    from src.models.user import User
    from src.utils.password import hash_password
    with Session() as db:
        for role in ('admin','operator','viewer'):
            db.add(User(email=role+'@chenggang.test',role=role,password_hash=hash_password('ColdChain!17')))
        db.commit()
    import uvicorn
    from src.main import app
    srv=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=18123,log_level='warning'))
    t=threading.Thread(target=srv.run,daemon=True);t.start()
    import httpx
    for _ in range(100):
        try:
            if httpx.get(BASE_URL+'/health',timeout=1).status_code==200:break
        except Exception:time.sleep(0.1)
    else:raise RuntimeError('server did not start')
    yield BASE_URL
    srv.should_exit=True
@pytest.fixture(scope='session')
def tokens(server):
    import httpx
    out={}
    for role in ('admin','operator','viewer'):
        r=httpx.post(server+'/auth/login',json={'email':role+'@chenggang.test','password':'ColdChain!17'},timeout=5)
        assert r.status_code==200,r.text
        out[role]={'Authorization':'Bearer '+r.json()['token']}
    return out
