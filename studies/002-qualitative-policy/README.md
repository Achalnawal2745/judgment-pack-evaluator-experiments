# Study 002 — does the determination boundary reproduce on a *qualitative* policy?

Study 001 encoded 461 lines of arithmetic-dense regulation and found that a substantial part of the
decision could not live in the pack: **124 prepared facts, 13 of them prepared *determinations***
rather than data. [RFC 0007](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0007-determination-boundary.md)
generalised that into a claim about the format, and then named its own sharpest weakness:

> *Study 001 is one domain, chosen for measurement properties rather than representativeness, and it
> is the hardest case for a format that declines to compute. A qualitative-policy domain might show
> none of this — and that result would be as informative as the original finding.*

This study answers that question. **It replicates, dramatically weakened, and via a different
mechanism.**

## Method

The same measurement as Study 001, on a policy chosen to be its opposite: qualitative, deontic,
essentially arithmetic-free.

- **Substrate:** the airline agent policy from [τ-bench](https://github.com/sierra-research/tau2-bench)
  (MIT, pinned `1d244f5d`), `data/tau2/domains/airline/policy.md` — 166 lines of real
  customer-service policy. Not vendored; see [`tau2bench/`](tau2bench/).
- **Slice:** the "Cancel flight" decision — *given a cancellation request, may it be cancelled?*
- **Author:** OpenAI Codex, clean-room from the policy text and the specification only, under the
  [protocol](../../CLEAN-ROOM-PROTOCOL.md). **Deliberately a different model family from Study 001's
  pack author**, so a shared bias cannot produce a shared finding.
- **The brief explicitly licensed a null result** — "everything fit cleanly" was named in advance as
  an acceptable and useful outcome.

## Result

| Measure | Study 001 (CBA, arithmetic-dense) | Study 002 (airline, qualitative) |
| --- | ---: | ---: |
| Policy encoded | 461 lines | 166 lines |
| Rules in the pack | 61 | **1** |
| **M1 — prepared facts** | **124** | **5** |
| **M2 — prepared *determinations*** | **13** | **1** |
| M3 — things the format cannot say | (arithmetic) | 2 |
| M4 — architectural constraints hit | 1 | 1 |
| M5 — fit cleanly | — | 7 |

The pack is 2 outcomes, 1 rule, 1 escalate exception, 4 evidence requirements. It validates at
`exit 0` and evaluates a real request to `outcome: may-cancel`.

**The format fits qualitative policy far better** — the migration is roughly a twenty-fifth of
Study 001's, and seven policy devices mapped with no friction at all. That is a genuine scoping
result for RFC 0007, and it argues against over-generalising the original finding.

**But it is not zero, and the residue is the interesting part.**

## The three findings

### 1. The escape reproduces — through a *logical* gap, not a numeric one

Study 001's determinations escaped because the format cannot calculate. Study 002's single
determination escapes for an unrelated reason:

> *"If any portion of the flight has already been flown, the agent cannot help and transfer is needed."*

**Core has no quantifier over runtime collections.** Its `any` combines a fixed, authored list of
conditions; it cannot ask whether *some element* of a variable-length array satisfies a predicate. So
the pack cannot decide "any portion already flown" — something upstream must inspect the segments and
hand the pack a conclusion.

This matters more than its count of 1. It shows the determination boundary is **not a property of
arithmetic**: it appears wherever the format lacks the device a policy sentence needs, and what is
lost is a *judgment*, not a value.

### 2. A concrete, small, previously unnamed expressiveness gap

RFC 0007 listed candidate areas for future encodings to probe — obligations, ordinal assessment,
precedence — all explicitly unevidenced. **Collection quantification was not among them, and it is
now the best-evidenced gap of the three studies**: one sentence of ordinary policy prose, in the
format's own design centre, that cannot be expressed.

The second M3 entry is the one predicted in advance: no date/time subtraction, so
*"the booking was made within the last 24 hrs"* must arrive pre-computed as `bookingAgeHours`.

### 3. The architectural constraint reproduces, and its root cause is now clear

Study 001: §8's conflict rule forced 61 violation detectors with the benign outcome only as
`fallbackOutcome`. Study 002, independently and in a different shape: the flown-portion clause became
an `escalate` exception, all four positive grounds were folded into a single `any` rule, and denial
became the fallback.

Two different authors, two different domains, the same underlying cause — **§8 has no rule
precedence**, so a policy's "if … otherwise" ordering has to be re-encoded as structure. That was an
unevidenced guess in RFC 0007; it now has two independent observations.

## Exposure disclosure

The clean-room barrier held — the session log contains no read outside the room and no reference to
the prior study's artifacts. But the barrier was not total, and the gap is ours, not the author's:

**The brief told the author what Study 001 found.** Its opening paragraph states that a prior study
encoded arithmetic-dense regulation and "found that a substantial part of the *decision* could not
live in the pack and migrated into a preparation layer." An author primed that migration is the
phenomenon under study may be more inclined to find some.

Mitigations, such as they are: the brief named a null result as acceptable in the same breath
("a result of 'everything fit' is a completely acceptable and useful outcome"); the measurement is
itemised with the policy sentence quoted for every entry, so each count can be checked against the
text rather than taken on trust; and the headline result is a **twenty-five-fold reduction** against
Study 001 — the direction a primed author would be least likely to produce. A cleaner replication
would withhold the prior finding entirely, and the next one should.

## Honest limits

- **One decision, not the whole policy.** Only "Cancel flight" was encoded. The booking, modification,
  and refund sections are untouched, and the policy's agent-behaviour rules (confirmation, one tool
  call at a time) are not decisions a pack represents at all.
- **n = 1 for the determination finding.** A single M2 entry supports "the boundary is not
  arithmetic-specific"; it does not measure how common the phenomenon is in qualitative policy.
- **No efficacy claim.** No comparison arm was run in this study and none is implied. Study 001's
  comparison arms have run since this was written; its
  [`RESULTS-FIRST-PROMPT-ARMS.md`](../001-policy-representation/RESULTS-FIRST-PROMPT-ARMS.md)
  reports them.
- **The counting boundary is the author's.** `MIGRATION.md` states it explicitly and lists what was
  excluded and why, so the count can be audited or disputed.

## Artifacts

[`pack/airline-cancellation.json`](pack/airline-cancellation.json) (validates, exit 0) ·
[`MIGRATION.md`](MIGRATION.md) (the measurement, every entry quoting its policy sentence) ·
[`DECISIONS.md`](DECISIONS.md) (interpretation calls) ·
[`CLEAN-ROOM-BRIEF.md`](CLEAN-ROOM-BRIEF.md) (what the author was and was not allowed to see).

```bash
judgment-pack spec validate pack/airline-cancellation.json
judgment-pack experimental evaluate pack/airline-cancellation.json \
  --facts pack/facts.example.json --evidence pack/evidence.example.json --format json
```
