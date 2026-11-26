# Attempt ledger

Every submission, its channel, bundle hash, observed state and what was learned. Written by `tools/poll_attempt.py --record`; failed attempts stay in the table.

| when (UTC) | attempt | status | exec | score | queue | note |
|---|---|---|---|---|---|---|
| 2026-11-26 13:06 | 113463 | draft | - | 0.0 | incomplete bundle | 平台 ARM 上传实验:`bundleStatus=incomplete`,报缺 execution / characterization / trace 三模态;`POST /submit` 400 要求轨迹。结论:本题不走该通道 |
| 2026-11-26 13:10 | 113475 | submitted | - | 0.0 | queued | 与 113476 同包(重复提交:为读取返回头重跑了同一命令);平台无删除入口 |
| 2026-11-26 13:38 | 113476 | submitted | - | 0.0 | queued | v1.0,CLI 0.1.58,包 sha256 `c1bb5398…`,2.61 MB / 75 成员 |
| 2026-11-26 13:40 | 113476 | submitted | - | 0.0 | queued | W1 变更后复查 |
