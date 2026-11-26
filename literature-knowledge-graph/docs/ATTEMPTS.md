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
