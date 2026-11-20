# 到账款认领台

为澄港冷链结算组登记银行到款、分次认领抵减同客户账单欠款、办理银行冲回，并提供同事务快照的复核视图。原生 HTML/CSS/JS 前端，Python 后端以行级锁保证并发落账正确，幂等键保证重试不重复落账。

## 真实工作场景

澄港冷链结算组共 18 人。客户付款常一笔到款分多次认领给同客户的几张账单：每次认领要同时扣减到账余额与账单欠款，两边都不能扣成负数。银行冲回一笔到款时，只恢复该笔抵掉的欠款，其他到账的抵扣照旧。操作员并发办理会争用同一到账或账单，系统排队或拒绝但不影响无关款项；落账后回执可能丢失，重试绝不能重复落账。复核人只读，且在同事务快照里读到账侧与账单侧的同一版欠款。

## 业务模块

1. 到账款：登记到款（编号防重），查看余额与状态；对到款办理银行冲回并记录原因与经办人。
2. 账单：登记应收账单，跟踪剩余欠款与 open/settled 状态。
3. 认领办理：登记认领（幂等键防重）→ 待处理列表办理落账 → 已入账（回执）或已拒绝（原因）。
4. 复核视图：按客户在 REPEATABLE READ 只读事务内读到账侧、账单侧与抵扣明细，逐账单勾稽。
5. 管理员操作审计：记录写请求、执行账号和 HTTP 结果，包括被拒绝的请求。

| 角色 | 主要页面 | 权限与典型动作 |
|---|---|---|
| admin 管理员 | 全部页面、审计 | 登记到款/账单、认领办理、冲回、查看写操作审计 |
| operator 操作员 | 四个业务页面 | 登记到款/账单、登记并办理认领、办理冲回；不可查看管理员审计 |
| viewer 观察员 | 四个业务页面 | 只读与复核；API 层拒绝所有业务写请求（403） |

## 快速启动

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
# 启动自动 seed；手动重跑不新增且不覆盖用户修改
docker compose exec -T backend python -m scripts.seed_demo
```

访问 [前端](http://localhost:18240)、[后端 OpenAPI](http://localhost:19240/docs)。数据库映射端口 17740。项目的日志、截图、测试脚本在批次根目录 `test-artifacts/gb-4101/`，不放入源码。

演示账号邮箱为 `admin@chenggang.test`、`operator@chenggang.test`、`viewer@chenggang.test`，统一密码 `ColdChain!17`。这些是本地固定演示凭据，上线前应修改 `.env` 和账号密码。

```bash
# 仅清理本项目及其演示数据
docker compose down -v --remove-orphans
```

## 核心规则与实现

- **同时扣减、不为负**：办理认领在同一事务内 `SELECT ... FOR UPDATE` 锁定到款行与账单行，校验 `余额 ≥ 认领额` 且 `欠款 ≥ 认领额` 后同时扣减；任一不满足则认领单置为已拒绝并记录原因（到账已冲回 / 账单已结清 / 到账余额不足 / 账单欠款不足），两侧都不可能出现负数。
- **冲回只恢复本笔**：抵扣明细（allocations）记录每笔到款抵掉的账单欠款。冲回按到款锁定其全部有效抵扣，逐张恢复账单欠款并置抵扣为已恢复，到款余额归零、状态置为已冲回；其他到款的抵扣不受影响。冲回按到款幂等，重复冲回返回原结果。
- **并发可等或拒绝**：行级锁按「到款 → 账单（按 id 升序）」固定顺序获取，避免死锁；争用同一行的请求排队等待，`lock_timeout` 3 秒超时返回 409 请稍后重试；无关到款/账单的办理走不同行锁，照常并行。
- **重试不重复落账**：认领登记携带唯一幂等键（唯一约束，冲突时返回原单并标记 `X-Idempotent-Replay`）；办理按认领单行锁 + 状态机，已入账的重复办理返回原回执（`replayed: true`），回执可经 `GET /claims/{id}/receipt` 补拉。
- **复核同版快照**：复核接口在 `REPEATABLE READ READ ONLY` 单事务内读到账侧与账单侧，两侧为同一版欠款并逐账单勾稽（有效抵扣合计 = 账单金额 − 剩余欠款）；观察员只读限制照旧，所有写请求 403。

## 实测（并发与幂等）

`backend/tests/` 使用真实 PostgreSQL 与完整 HTTP 栈（uvicorn + 多线程客户端）验证：

1. **两笔抢同一账单**：欠款 100，两笔各认 80 并发办理，恰一笔入账、一笔以「账单欠款不足」拒绝；欠款 20 不为负；同场第三笔无关款项照常入账。
2. **认领撞冲回**：认领办理与银行冲回并发碰撞 5 轮，两种合法先后序均被覆盖；每轮断言欠款恢复 300、余额归零、无残留有效抵扣、无负数。
3. **丢回执重试**：同一幂等键 6 线程并发登记只落一单；办理后 6 线程并发重试均返回同一回执号，余额与欠款只扣一次，抵扣明细唯一。
4. **复核快照**：写入风暴下复核接口始终勾稽一致；另以单连接 REPEATABLE READ 证明事务内读到旧版快照、事务外看到新版。
5. **只读与超额**：观察员全部写请求 403；超额/负数/跨客户认领 422，余额与欠款不变。

```bash
# 需要可访问的 PostgreSQL（本地开发见下节）
cd backend && TEST_DATABASE_URL=postgresql+psycopg2://app@127.0.0.1:55432/payment_claims_test \
  python -m pytest tests/ -q
```

## 技术栈、结构与本地开发

| 部分 | 实现 |
|---|---|
| frontend | 原生 ES modules、CSS、Nginx 1.27，olive paper 风格 |
| backend | Python 3.11、FastAPI、SQLAlchemy、PyJWT |
| db | PostgreSQL 16（行级锁、唯一约束、REPEATABLE READ） |
| auth | JWT 8 小时有效，PBKDF2 SHA-256 加盐密码 |

`backend/src/` 按 config/models/schemas/services/controllers/routes/middlewares/utils/constants 分工；`backend/scripts/seed_demo.py` 管理幂等初始化；`backend/migrations/README.md` 说明 schema v2。实体链为 payment、bill、claim、allocation、receipt、reversal，各自有模型与服务，路由按资源聚合。`frontend/src/` 按 api/stores/types/components/common/hooks/pages/router/utils/constants 分工。

后端本地：创建虚拟环境并安装 `backend/requirements.txt`（跑测试再装 `requirements-dev.txt`），先用 Compose 启动 db，设置本地可达的 DATABASE_URL/JWT_SECRET，进入 backend 执行 `uvicorn src.main:app --reload`。最省事的开发方式是修改源码后 `docker compose up -d --build`。前端通过 Nginx 的 `/api/` 去前缀代理访问后端，禁止双重 `/api/api`。

环境变量：COMPOSE_PROJECT_NAME（容器命名）、FRONTEND_PORT/BACKEND_PORT/DB_PORT（宿主端口）、POSTGRES_PASSWORD（演示库密码）、JWT_SECRET（签名密钥）、SEED_DEMO（默认 true）。后端容器另接收 DATABASE_URL。3 个服务均有 healthcheck；数据库使用命名卷。

共享枚举位置：角色与状态在 `backend/src/constants/enums.py` 和 `frontend/src/constants/enums.js`；模型/鉴权服务消费后端值，状态标签与前端权限消费前端值。

## 已知边界

- 认领办理为同步落账，没有异步队列；高并发以行级锁排队，lock_timeout 3 秒。
- 冲回针对整笔到款，不支持部分冲回；被拒绝的认领单为终态，需要新金额请重新登记。
- 复核视图为单客户粒度；勾稽口径为「有效抵扣合计 = 账单金额 − 剩余欠款」。
- 金额使用 NUMERIC(14,2)，接口以两位小数字符串返回；不支持多币种。
- 单实例后端；不对接生产银行回单通道，不部署生产高可用。
- Web 字体来自 Google Fonts，离线会使用 serif/monospace 回退；不影响功能。

License: MIT，见 LICENSE。
