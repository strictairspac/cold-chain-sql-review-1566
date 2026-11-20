# gb-4101 实测记录（2026-11-20）

环境：本机无 docker/root，PostgreSQL 17.5（zonkyio arm64 二进制，127.0.0.1:55432）+ Python 3.11 venv；应用栈 FastAPI + SQLAlchemy + psycopg2，uvicorn 真实起服务，pytest 多线程客户端打满 HTTP 全链路。

## 场景与结论

1. 两笔抢同一账单（test_two_payments_compete_for_one_bill）：欠款 100、两笔各认 80 并发办理 → 恰一笔 posted、一笔 rejected「账单欠款不足」；欠款 20.00 不为负；同场无关第三笔照常 posted。
2. 认领撞冲回（test_claim_collides_with_reversal）：5 轮并发碰撞，posted/rejected 两种合法先后序均覆盖；每轮断言欠款恢复 300.00、余额 0.00、无残留 active 抵扣、复核勾稽一致。
3. 丢回执重试（test_lost_receipt_retry）：同幂等键 6 线程并发登记仅 1 单；办理后 6 线程并发重试均返回同一回执号且 replayed=true；余额/欠款只扣一次，抵扣明细唯一，GET /claims/{id}/receipt 可补拉。
4. 复核同版快照（test_review_reads_same_snapshot）：3 线程写入风暴下 15 次复核全部 reconciled=true；单连接 REPEATABLE READ READ ONLY 事务内两次读取不受并发落账影响。
5. 只读与超额（test_viewer_readonly_and_overdraft）：viewer 全部写请求 403；超额/负数/跨客户 422，余额欠款不变。

完整输出见 pytest.log（6 passed，连续 4 轮全绿）。
