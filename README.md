# Judgment Pack evaluator experiments

Empirical evidence about the evaluator proposed by the Judgment Pack Specification's
[RFC 0006](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0006-evaluator-conformance.md)
(Draft), in two tracks that answer two different questions and are judged by different standards:

- **Agreement — *do independent implementations produce the same result?*** Clean-room evaluators
  derived from the specification text alone. Their agreement tests whether the prose actually pins
  the semantics; their divergences locate the places it does not. Deterministic, offline, CI-verified.
- **Efficacy — *does representing a policy this way actually help?*** Preregistered experiments on
  third-party benchmarks. API-dependent, costly, non-deterministic, and run manually — never in CI.

The two are kept visibly separate on purpose. Conformance evidence is something a specification
project is the right author of; efficacy evidence is something it is the *wrong* author of, and the
only remedy is method: preregistration, public harness and data, and reported negative results.

**Nothing in this repository claims any JPS conformance.** JPS `0.1.0-draft` defines no evaluator
conformance class and forbids evaluator-conformance claims outright (Core §3.4). Every
implementation here is experimental, may change or be removed without compatibility promise, and
evaluates nothing normatively: a disposition is data, not an authorization, a decision, or an
executed action.

## Layout

| Path | What it is |
| --- | --- |
| [`CLEAN-ROOM-PROTOCOL.md`](CLEAN-ROOM-PROTOCOL.md) | The reusable recipe every implementation must follow to count as evidence |
| [`reference/`](reference/) | Pinned snapshots of the specification texts the rooms are built from |
| [`harness/`](harness/) | The post-hoc referee: runs identical inputs through implementations and diffs dispositions |
| [`python/`](python/) | **Agreement track.** Implementation #2 (the first lives in [`judgment-pack-runtime`](https://github.com/Judgment-Pack/judgment-pack-runtime)): stdlib-only Python, written clean-room by a coding agent from the reference texts, with its interpretation log in [`python/DECISIONS.md`](python/DECISIONS.md) |
| [`studies/`](studies/) | **Efficacy, expressiveness, and interoperability track.** Preregistered experiments on third-party benchmarks and independently developed systems, from policy expressiveness ([`001`](studies/001-policy-representation/)–[`003`](studies/003-escape-census/)) through trustworthy-input lineage ([`005`](studies/005-semantic-source-discovery/)–[`008`](studies/008-portable-derivation-admission/)) to receipt-protocol interoperability ([`013`](studies/013-agent-eval-forge-integration/), [`014`](studies/014-openworkproof-binding/)). See the [studies index](studies/README.md) for the full matrix and the open-source projects each one builds on. |
| [`docs/adr/`](docs/adr/) | Decision records for this repository — why a given study is being run, and what comes next |

Future implementations (TypeScript, Rust, …) get sibling directories — but the clean room itself
never happens inside this repository: an implementer working here could read the existing
implementations. See the protocol.

### Studies at a glance

Navigation and status only — every finding, and every qualification that finding carries, lives
in the study's own directory. Statuses below are the ones the [studies index](studies/README.md)
records; it remains the canonical matrix, with the external source each study builds on.

| Study | Track | Status | Evidence |
| --- | --- | --- | --- |
| [001](studies/001-policy-representation/) | Expressiveness / efficacy | Run — **H1 not supported: the pack arm scored lowest on the registered endpoint** (one of the two registered model families ran); expressiveness result | [`RESULTS-FIRST-PROMPT-ARMS.md`](studies/001-policy-representation/RESULTS-FIRST-PROMPT-ARMS.md), [`DEVIATIONS.md`](studies/001-policy-representation/DEVIATIONS.md), [Results](#results-so-far) |
| [002](studies/002-qualitative-policy/) | Expressiveness | Completed expressiveness result | [Results](#results-so-far), [study](studies/002-qualitative-policy/) |
| [003](studies/003-escape-census/) | Expressiveness | Completed escape census | [Results](#results-so-far), [study](studies/003-escape-census/) |
| [004](studies/004-composition-closure/) | Composition | Completed composition-closure study; no efficacy claim | [`RESULTS.md`](studies/004-composition-closure/RESULTS.md), [`run-log.md`](studies/004-composition-closure/run-log.md) |
| [005](studies/005-semantic-source-discovery/) | Trustworthy input | Completed semantic-source-discovery study | [`README.md`](studies/005-semantic-source-discovery/README.md), [`RESULTS.md`](studies/005-semantic-source-discovery/RESULTS.md), [`ANALYSIS.md`](studies/005-semantic-source-discovery/ANALYSIS.md) |
| [006](studies/006-evidence-lineage-gate/) | Trustworthy input | Deterministic phase completed; model-authoring phase terminated before inference because of infrastructure, so model usability is **not estimable** | [`README.md`](studies/006-evidence-lineage-gate/README.md), [`RESULTS.md`](studies/006-evidence-lineage-gate/RESULTS.md) |
| [007](studies/007-evidence-lineage-model-replication/) | Trustworthy input | Completed evidence-lineage model replication | [`README.md`](studies/007-evidence-lineage-model-replication/README.md), [`RESULTS.md`](studies/007-evidence-lineage-model-replication/RESULTS.md), [`ANALYSIS.md`](studies/007-evidence-lineage-model-replication/ANALYSIS.md) |
| [008](studies/008-portable-derivation-admission/) | Trustworthy input | Completed offline replay and probe with no model runs; read with the study's stated qualifications | [`README.md`](studies/008-portable-derivation-admission/README.md), [`RESULTS.md`](studies/008-portable-derivation-admission/RESULTS.md), [`ANALYSIS.md`](studies/008-portable-derivation-admission/ANALYSIS.md) |
| [009](studies/009-transcribed-oracle-matrix/) | Blinded authorship | Completed corrected retained attempt as a **constructed existence witness** — not discovery evidence, not general pipeline validation | [`README.md`](studies/009-transcribed-oracle-matrix/README.md), [`RESULTS.json`](studies/009-transcribed-oracle-matrix/RESULTS.json), [`ANALYSIS.md`](studies/009-transcribed-oracle-matrix/ANALYSIS.md) |
| [010](studies/010-blinded-oracle/) | Blinded authorship | Run (frozen) | [`ANALYSIS.md`](studies/010-blinded-oracle/ANALYSIS.md), [`RESULTS.json`](studies/010-blinded-oracle/RESULTS.json) |
| [011](studies/011-authorship-coverage-rates/) | Blinded authorship | Run (frozen) | [`ANALYSIS.md`](studies/011-authorship-coverage-rates/ANALYSIS.md), [`RESULTS.json`](studies/011-authorship-coverage-rates/RESULTS.json) |
| [012](studies/012-policy-perturbation/) | Blinded authorship | Frozen + run — **R1 unsupported; retracts a published claim** | [`ANALYSIS.md`](studies/012-policy-perturbation/ANALYSIS.md), [`CORRECTION.md`](studies/012-policy-perturbation/CORRECTION.md) |
| [013](studies/013-agent-eval-forge-integration/) | Interoperability | Frozen + run — R1 holds (both strata) | [`ANALYSIS.md`](studies/013-agent-eval-forge-integration/ANALYSIS.md), [`results/`](studies/013-agent-eval-forge-integration/results/) |
| [014](studies/014-openworkproof-binding/) | Interoperability | Frozen + run — R1 holds (both strata) | [`ANALYSIS.md`](studies/014-openworkproof-binding/ANALYSIS.md), [`results/`](studies/014-openworkproof-binding/results/) |
| [015](studies/015-cloudflare-os-boundary/) | Interoperability | Frozen + run — R1 holds (27 cells); reviewer holdout diverged on 7 of 8 cells | [`README.md`](studies/015-cloudflare-os-boundary/README.md), [`ANALYSIS.md`](studies/015-cloudflare-os-boundary/results/primary-attempt-001/ANALYSIS.md), [`results/`](studies/015-cloudflare-os-boundary/results/) |
| [016](studies/016-policy-currency-anchor/) | Interoperability | Frozen + run — R1 holds (both strata) | [`ANALYSIS.md`](studies/016-policy-currency-anchor/ANALYSIS.md), [`results/`](studies/016-policy-currency-anchor/results/) |
| [017](studies/017-witnessed-currency/) | Currency governance | Frozen + run — R1 holds (both strata) | [`ANALYSIS.md`](studies/017-witnessed-currency/ANALYSIS.md), [`results/`](studies/017-witnessed-currency/results/) |
| [018](studies/018-transition-rules/) | Currency governance | Frozen + run — R1 holds; reviewer holdout diverged on three preregistered cells | [`ANALYSIS.md`](studies/018-transition-rules/ANALYSIS.md), [`results/`](studies/018-transition-rules/results/) |
| [019](studies/019-authorship-across-representations/) | Blinded authorship | **Frozen + run — R1 inconclusive (control gate failed: E1 floor)** | [`ANALYSIS.md`](studies/019-authorship-across-representations/ANALYSIS.md), [`results/`](studies/019-authorship-across-representations/results/) |
| [021](studies/021-history-replay-catch/) | History replay | Run — R1 holds (131/131, holdout 8/8) | [`PREREGISTRATION.md`](studies/021-history-replay-catch/PREREGISTRATION.md), [`PREREG-REVIEW.md`](studies/021-history-replay-catch/PREREG-REVIEW.md) |
| [022](studies/022-outside-format-binding/) | Outside-format binding | Run — R1 holds (19/19, holdout 6/6) | [`PREREGISTRATION.md`](studies/022-outside-format-binding/PREREGISTRATION.md), [`PREREG-REVIEW.md`](studies/022-outside-format-binding/PREREG-REVIEW.md) |

This repository claims **no JPS conformance** for anything in it, and the table above adds no
aggregate headline: each study answers a different preregistered question and must be read with
its own qualifications.

## Results so far

### Agreement track

- **13/13 semantic agreement** between the Go reference runtime's experimental evaluator
  (v0.2.0) and `python/` on RFC 0006's nine appendix instances plus three probes — identical
  kind, outcome, reason set, and handoff state ([`harness/README.md`](harness/README.md)).
- **Draft RFC 0016 (outcome values): 66 rows, 62 where both implementations give the RFC's
  answer**, a disposition byte for byte or an error class. Three more agree with each other and
  not with the RFC, for a reason the RFC's own Compatibility section gives. One differs: what a
  carrier does with an unpaired surrogate, which Core does not say
  ([`harness/RFC0016-AGREEMENT.md`](harness/RFC0016-AGREEMENT.md)). CI runs the comparison
  against the pinned runtime.
- **Two specification gaps found** and recorded as RFC 0006 unresolved questions: number
  representability, and the disposition's concrete JSON serialization (the two implementations
  agreed on all semantics while serializing `handoff` incompatibly — see
  [`python/DECISIONS.md`](python/DECISIONS.md) entry 3).

### Efficacy track

**Study 001's comparison has run, and on the preregistered endpoint the pack arm loses.** All
three arms ran over the full corpus at k = 5, with one of the two registered model families. On
the registered answerable population (216 instances) pass^5 was A 0.727, A′ 0.778 and B 0.579:
B − A = −0.148, 95% CI [−0.213, −0.088], the opposite sign to H1. H5 (B against A′) and H4
(accuracy) are not supported either, and H3 (citation) fails. H2 (escalation) meets its registered
rule over all 432 twins, with false escalations on 27.8% of answerable trials against arm A's 1.1%.
The study traces the endpoint loss to 60 answerable instances the pack cannot decide, because the
benchmark omits a schedule the policy needs. An earlier draft reported the opposite by scoring the
wrong population.
[`RESULTS-FIRST-PROMPT-ARMS.md`](studies/001-policy-representation/RESULTS-FIRST-PROMPT-ARMS.md)
has the tables and [`DEVIATIONS.md`](studies/001-policy-representation/DEVIATIONS.md) the
corrections.

Later studies have retained results; each answers a different preregistered question and must be read with its study-level qualifications. Study 002 ran no comparison arm. The **expressiveness**
results below are on deliberately opposite policy types and by different model families:

| | Study 001 — CBA, arithmetic-dense | Study 002 — airline, qualitative | Study 003 — census, 12 decisions |
| --- | ---: | ---: | ---: |
| Prepared facts | 124 | 5 | 58 |
| Prepared *determinations* | 13 | 1 | 40 |
| Decisions with ≥1 determination | 1/1 | 1/1 | **12/12** |

The escape is universal in the census frame because real request inputs are collections — and one
device dominates: **quantification over collections forced 25 of 40 determinations** (arithmetic:
6). Encoders were hypothesis-blind; classification was two-way independent with **zero** fact-class
disagreements. See [Study 003](studies/003-escape-census/), [Study 002](studies/002-qualitative-policy/) and
[RFC 0007](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0007-determination-boundary.md).

## License

Apache-2.0. This repository is maintained alongside, but is not part of, the normative
specification; the specification repository owns the standard and its conformance corpus.
