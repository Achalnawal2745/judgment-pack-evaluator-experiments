# Study 001 — Does representing a policy as a judgment pack change how reliably a model applies it?

A preregistered, three-arm experiment on a third-party benchmark.

> **Results exist, and on the preregistered endpoint the pack arm loses.** All three arms have
> run over the full 432-twin corpus at k = 5. On the registered answerable population (216
> shared instances) accuracy was **A 0.781**, **A′ 0.778**, **B 0.579** — the judgment-pack arm
> lowest of the three. An earlier draft reported the opposite by scoring the wrong population;
> the post-run adversarial review caught it (five blockers) and the error is recorded in
> [`DEVIATIONS.md`](DEVIATIONS.md) §2 rather than silently fixed.
>
> A constant answer of `illegal` would score **0.829** on that population, above each arm's
> accuracy: 179 of its 216 gold labels are `illegal`. That baseline and a per-class table are
> secondary and descriptive: they were added after the run, are not registered, and test no arm
> against it ([`RESULTS-FIRST-PROMPT-ARMS.md`](RESULTS-FIRST-PROMPT-ARMS.md),
> [`DEVIATIONS.md`](DEVIATIONS.md) §9).
>
> H2 is **not estimable** on that set: it contains no redacted twin, so one row of the 2×2 is
> empty. Arm B's shortfall is diagnosed as a missing constant rather than a missing rule — it
> reaches 0.801 on the subset it can decide ([`G3-DIAGNOSIS.md`](G3-DIAGNOSIS.md),
> [`PIPELINE-STATUS.md`](PIPELINE-STATUS.md) §7).
>
> Read [`RESULTS-FIRST-PROMPT-ARMS.md`](RESULTS-FIRST-PROMPT-ARMS.md) for the verdict and its
> correction history, and [`results/k5-report-answerable.md`](results/k5-report-answerable.md)
> for the scored tables.

| | |
| --- | --- |
| Rationale | [ADR-0001](../../docs/adr/0001-evaluate-on-rulearena-first.md) — why RuleArena, what comes next, why run this at all |
| Preregistration | [PREREGISTRATION.md](PREREGISTRATION.md) — frozen at merge; hypotheses, primary endpoint, falsification conditions |
| Deviations | [DEVIATIONS.md](DEVIATIONS.md) |
| Substrate | [rulearena/](rulearena/) — third-party, MIT, pinned, fetched not vendored; attribution and upstream-contribution policy |
| Status | [PIPELINE-STATUS.md](PIPELINE-STATUS.md) — what runs today, what is stubbed, how to reproduce |

## The design in one table

| Arm | Policy representation | Facts |
| --- | --- | --- |
| A | The Collective Bargaining Agreement text verbatim in the prompt | identical |
| A′ | The pack's semantic content as prose in the prompt | identical |
| B | A judgment pack via `judgment-pack experimental evaluate` | identical |

Two model families (Claude, OpenAI Codex), k=5 trials, paired instances, judge-free scoring against
RuleArena's gold answers and its `relevant_rules` citation ground truth.

**A′ is the arm that matters.** Without it, a win for B confounds "structured representation" with
"a human spent hours disambiguating this policy."

## Three things stated up front, not in an appendix

1. **The abstention labels are ours by construction.** RuleArena has no "cannot decide" condition; we
   manufacture one by mechanically deleting a load-bearing fact ([pipeline/REDACTION.md](pipeline/REDACTION.md)).
2. **The format cannot compute.** Derived quantities come from a published deterministic preprocessor
   and go identically to every arm. This measures policy *representation*, not fact derivation.
3. **The evaluator is experimental and claims no conformance.** JPS 0.1.0-draft §3.4 forbids
   evaluator-conformance claims.

## Reproducing

```bash
rulearena/fetch.sh                 # clone the benchmark at the pinned commit
python pipeline/parse_nba.py --checkout rulearena/checkout --out pipeline/out/facts
python pipeline/derive.py   --facts pipeline/out/facts
python pipeline/redact.py   --facts pipeline/out/facts --out pipeline/out/twins --seed 20260727
python harness/run.py --arm B --backend mock --instances pipeline/out/twins --trials 1 --seed 1 --out results/smoke.jsonl
python harness/score.py results/*.jsonl
```
