# Attempt ledger

Every submission, its channel, bundle hash, observed state and what was learned. Written by `tools/poll_attempt.py --record`; failed attempts stay in the table.

| when (UTC) | attempt | status | exec | score | queue | note |
|---|---|---|---|---|---|---|
| 2026-11-26 13:06 | 113463 | draft | - | 0.0 | incomplete bundle | 平台 ARM 上传实验:`bundleStatus=incomplete`,报缺 execution / characterization / trace 三模态;`POST /submit` 400 要求轨迹。结论:本题不走该通道 |
| 2026-11-26 13:10 | 113475 | submitted | - | 0.0 | queued | 与 113476 同包(重复提交:为读取返回头重跑了同一命令);平台无删除入口 |
| 2026-11-26 13:38 | 113476 | submitted | - | 0.0 | queued | v1.0,CLI 0.1.58,包 sha256 `c1bb5398…`,2.61 MB / 75 成员 |
| 2026-11-26 13:40 | 113476 | submitted | - | 0.0 | queued | W1 变更后复查 |
| 2026-11-26 13:46 | 113476 | submitted | - | 0.0 | queued | W2/W3 提交包更新 |
| 2026-11-26 14:20 | 113476 | submitted | - | 0.0 | queued | W4 开工时复查:`scoringState.state=queued`,`resultsJson=null`,`execStatus=null`,`createdAt` 未变,仍未出分;113475 同状态 |
| 2026-11-27 00:32 | 113476 | submitted | - | 0.0 | queued | W7 复查:仍未出分;worker 打分前沿冻结在 112648(11-26 04:12),其后 66 条全部 queued,我方前方约 31 条。归因不成立,不重交 |
| 2026-11-27 00:58 | 114092 | submitted | - | 0.0 | queued | 当前包首次提交(v1.3.2,49 文件 / 644 权限 / 含 R14);bundle 与 submission 逐字节相同;sha256 464a9451…;modelTag 仍 unknown(环境未提供模型/harness 标识,不自造) |
| 2026-11-27 00:58 | 114091 | submitted | - | 0.0 | queued | 同包重复(上一命令的输出被管道过滤,但 submit 已执行);与 114092 相隔 8 s,可作 ±7 噪声对 |
| 2026-11-27 01:05 | 114103 | submitted | - | 0.0 | queued | v1.3.3(权限 644 / 文档改 python3 / case-dir 容错 / selftest 31);bundle 内 skill 与 submission 逐字节相同;sha256 73fde0cf…;409 实测:平台不允许替换既有 attempt 的包,故必须新开 |
| 2026-11-27 01:14 | 114109 | submitted | - | 0.0 | queued | v1.3.5:标注词汇 entities/relations 兼容 + 字段类型强制转换(修 3 处 AttributeError 崩渍)+ 测试 31/96;bundle 与 submission 逐字节相同;sha256 f9d53d84… |

## Live attempts (2026-11-27 01:00 UTC)

| attempt | package | state |
|---|---|---|
| **114109** | **v1.3.5** (current): accepts the case's `entities`/`relations` vocabulary, coerces wrong field types instead of raising, self-test 31 / regression 96, `sha256 f9d53d84…` | `submitted`, `bundleStatus=null`, `scoringState=queued`, `modelTag=unknown` |
| 114103 | v1.3.3: files 644, `python3` everywhere, case-dir tolerance | `submitted`, `queued`, `sha256 73fde0cf…` |
| 114091 / 114092 | v1.3.2, `sha256 464a9451…`; identical except file modes, `python`/`python3` and two doc lines | `submitted`, `queued` |
| 113475 / 113476 | v1.0-era, `oneOf` schema, 4 merge decisions, `sha256 c1bb5398…` | `submitted`, `queued` since 11-26 13:10 |

The platform refuses to replace an attempt's bundle: `--attempt-id 114092 --bundle …` returns
`HTTP 409 submission_conflict` ("this attempt already has a different submission"). A corrected
package therefore always costs a new attempt; checked on 11-27 01:04 UTC rather than assumed.

`modelTag=unknown` on all four: the CLI takes `--model`/`--harness` as self-reported strings and
this environment exports neither (no `PLAYGROUND_MODEL`/`PLAYGROUND_HARNESS`, no `/logs/agent`
session file). Reporting a name that was not observed would be an invention, so the field stays
`unknown`.

The duplicate pair of the current package (114091, 114092, 8 s apart) exists because a command whose
stdout was piped through a filter still executed the submission twice; it is kept as the noise pair
the attribution rule asks for. Platform has no delete endpoint.

## Attribution rule — what a score means, fixed before the score arrives

The worker has not scored 113476 yet (`scoringState.state=queued`, no `execStatus`, no
`scorecard`). Attribution is therefore written down in advance so the decision is mechanical
rather than argued after the fact. Noise between submissions of one package is about ±7 points
(`analysis/competitor_analysis.md`), so a single score is never read against a threshold; two
attempts of this package are already queued (113476, 113475) and their median is the estimate.

Read in this order, and stop at the first line that applies:

| observation | reading | action |
|---|---|---|
| `execStatus=failed` or `status=pending_review` | the run never produced a judged artifact; the score says nothing about the Skill | fix execution only (input paths, timeouts, crash); no extraction-rule changes; resubmit once |
| `execStatus` ok, score < 62 | the Skill was read and did not help, or hurt | attribute per dimension from `scorecard`; change the dimension that scored lowest, not the whole package |
| `execStatus` ok, 62 ≤ score < 72 | unattributed middle: within noise of the 50–65 band that CLI-channel peers occupy | one targeted change per submission; keep the package stable so the next score is comparable |
| `execStatus` ok, score ≥ 72 | the package is the asset; further edits risk regression | freeze the extraction rules; only doc/infra fixes; resubmit only if a scored dimension is clearly 0 |
| any score with a 0 on one rubric line (实际效果/使用增益/创新增益/可靠体验/生态贡献) | that dimension was not recognised at all | fix that dimension; a 0 is a claim about a missing artifact, not about quality |

Independent of the score, a resubmission must differ in something the grader can see, otherwise
it spends a queue slot on the same expectation. The candidate differences after W4 are: numeric
guard on quotes (evidence correctness), non-silent failures (reliability), and a README that a
stranger can follow (ecosystem). `modelTag` is `unknown` on both live attempts; any resubmission
should pass `--model`/`--harness` so the tag is recorded.

## Why there is nothing to attribute yet (2026-11-27 00:20 UTC)

The queue is not slow, it is stopped. Read from the public attempt list, all 66 attempts of this
challenge created after 2026-11-26T04:12Z are still `scoringState.state=queued`; the last attempt
the worker scored is 112648, created 04:12. The attempts that do change state after that point are
`pending_review`/`execStatus=failed` — the execution path, not the scoring path.

| observation | value |
|---|---|
| last scored attempt | 112648, `createdAt` 2026-11-26T04:12:32Z, score 59, `scoreIsFinal=true` |
| attempts created after it | 66, all `queued` except `pending_review`/`draft` |
| our position | 113476 is ~31 attempts behind that frontier; its duplicate 113475 sits one slot earlier |
| 113476 state | `status=submitted`, `execStatus=null`, `resultsJson=null`, `score=0.0`, `createdAt` unchanged for 11 h |

Two consequences, both mechanical:

- A **resubmission now does not buy time**: the new attempt would join the same stopped queue,
  behind the same frontier, and the two queued attempts of this package already bracket the noise
  (`analysis/competitor_analysis.md`: ±7). Nothing in the attribution rule can run until a score
  exists, and a score cannot depend on when the row is added to a stalled queue.
- 113476's bundle is **not** the current package. Replaying `skills/literature-knowledge-graph/`
  from `bohrium/submitted-bundle-113476.zip` end to end on the demo case gives `status=success`,
  35 nodes / 34 edges, coverage 1.0 — but 4 merge decisions and 4 queries, where the current package
  ships 9 merge decisions and 6 queries, and the bundle's `schema/graph.schema.json` still has the
  `oneOf` root — checked under draft-07, both the built `graph.json` and the shipped
  `annotations.example.json` fail it, because each satisfies two branches at once. Whatever score
  lands on 113476 is therefore a reading of
  v1.0-era artefacts, and must not be attributed to the v1.3 extraction rules. The next submission
  carries the current package.

