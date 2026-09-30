# Studies index

Preregistered experiments about the Judgment Pack evaluator. Each study answers one
question, pins its inputs by digest, and reports its result whichever way it lands —
negative and undetected results are kept, not dropped. Nothing here is normative: a study
is empirical evidence *about* the specification, authored deliberately outside the
specification repository. See the [repository README](../README.md) for how the efficacy
and agreement tracks are kept separate and why.

## The studies

| № | Question | Theme | External source | Status |
| --- | --- | --- | --- | --- |
| [001](001-policy-representation/) | Does representing a policy as a judgment pack change how reliably a model applies it? | Expressiveness / efficacy | RuleArena | Run — **H1 not supported: the pack arm scored lowest on the registered endpoint**; expressiveness result |
| [002](002-qualitative-policy/) | Does the determination boundary reproduce on a *qualitative* policy? | Expressiveness | τ²-bench | Run — expressiveness result |
| [003](003-escape-census/) | The escape census: across twelve real decisions, how often does judgment escape the pack? | Expressiveness | τ²-bench | Run — 12/12 decisions |
| [004](004-composition-closure/) | Does declared composition close the census's cross-decision escape? | Composition | — | Run — negative: 0 of 5 closed |
| [005](005-semantic-source-discovery/) | Semantic source discovery. | Trustworthy input | — | Run |
| [006](006-evidence-lineage-gate/) | The evidence-lineage gate: can a fabricated fact reach evaluation? | Trustworthy input | — | Run |
| [007](007-evidence-lineage-model-replication/) | Evidence-lineage model replication. | Trustworthy input | — | Run (frozen) |
| [008](008-portable-derivation-admission/) | Portable-derivation admission. | Trustworthy input | — | Run (frozen) |
| [009](009-transcribed-oracle-matrix/) | The transcribed-oracle matrix — a constructed existence witness. | Blinded authorship | codex-cli (author) | Run (frozen) |
| [010](010-blinded-oracle/) | The blinded oracle. | Blinded authorship | codex-cli (author) | Run (frozen) |
| [011](011-authorship-coverage-rates/) | Coverage rates for blinded record authorship. | Blinded authorship | codex-cli (author) | Run (frozen) |
| [012](012-policy-perturbation/) | Is a blinded author's test surface anchored to the policy's *surface form*, or to what the policy means? | Blinded authorship | codex-cli (author) | Frozen + run — **R1 unsupported; retracts a published claim** |
| [013](013-agent-eval-forge-integration/) | Can an independently developed agent-regression harness see the judgment/integration boundary? | Interoperability | Agent Eval Forge | Frozen + run — R1 holds (both strata) |
| [014](014-openworkproof-binding/) | Can an independently developed receipt protocol bind an executed action to the exact judgment that authorized it? | Interoperability | OpenWorkProof | Frozen + run — R1 holds (both strata) |
| [015](015-cloudflare-os-boundary/) | Can a third party prove offline which judgment authorized which staged action on a governed-agent platform — and what can neither system see? | Interoperability | Cloudflare OS | Frozen + run — R1 holds (27 cells); reviewer holdout diverged on 7 of 8 cells |
| [016](016-policy-currency-anchor/) | Can a signed pack-version currency registry detect a retired-version decision offline — and where must it fail? | Interoperability | OpenWorkProof | Frozen + run — R1 holds (both strata) |
| [017](017-witnessed-currency/) | What does a minimal witness/cross-view comparison step buy against the registry split view — and which contract clause does each remaining silence isolate? | Currency governance | — | Frozen + run — R1 holds (both strata) |
| [018](018-transition-rules/) | What does a cited registry head buy a stated transition rule — and where does the evidence stop? | Currency governance | — | Frozen + run — R1 holds; reviewer holdout diverged on three preregistered cells |
| [019](019-authorship-across-representations/) | Does a constrained judgment representation change how reliably a model authors an executable policy, compared with a general policy language? | Blinded authorship | Open Policy Agent; codex-cli (author) | **Frozen + run — R1 inconclusive (control gate failed: E1 floor)** |
| [021](021-history-replay-catch/) | Does replaying a ledger of decisions made under a pack catch a mechanical defect planted in it — and can the runtime's history profile tell a moved line from any other defect? | History replay | R1 holds: 131/131 registered cells (holdout 8/8) under the published v0.21.0 runtime; the catch curves and the signature table in `ANALYSIS.md` | Run (eight review rounds; frozen at #105) |
| [022](022-outside-format-binding/) | Can a gateway receipt be bound into an in-toto attestation so that a consumer of either format reads the other — and what does each of three verifiers (the gateway's own, a consumer ceremony over the unmodified in-toto reference implementation, the binding's rules) see of a tampered store or attestation, and what does none? | Outside-format binding | R1 holds: 19/19 locked cells, holdout 6/6; the ownership map in `ANALYSIS.md` — re-digest sees the bytes the binding names, nothing the gateway's key covers, and what makes an attestation about its receipt is the binding's rule | Run (nine review rounds; frozen at #106) |


Studies 001 and 012 each record a registered prediction that **failed**. In Study 001 the
primary hypothesis is not supported, and the sign is the opposite of the one registered: on
the registered answerable population the pack arm scored lowest of the three, in a run of
one of the two registered model families. Its `RESULTS-FIRST-PROMPT-ARMS.md` gives the
figures, the cause it diagnoses, and the earlier draft that reported the opposite by
scoring the wrong population. In Study 012, no longer
printing the thresholds changed nothing: the same six semantic classes were covered, and
records still landed exactly on values the policy never spelled out. That kills the
anchoring explanation Study 011 offered, which is retracted in 012's `CORRECTION.md` and
in a banner on Study 011's `DIVERSITY.md`. The pattern Study 011 reported is still there,
in the baseline as much as anywhere; only our account of its cause does not survive. That
retraction was itself corrected the same day — the head of 012's `CORRECTION.md` lists
what it got wrong, and why the largest error was claiming a universal our own published
census already contradicted. Study 015 is frozen and has run. Ten cross-vendor review
rounds returned DO-NOT-FREEZE and the eleventh returned freezable after listed fixes; the
freeze was taken on that verdict, and a twelfth round ran after it, which the study's
`DEVIATIONS.md` records. R1 holds on all 27 locked cells, and the reviewer's holdout
diverged on 7 of 8, classified cell by cell in the attempt's `ANALYSIS.md`.
The README banners of Studies 016, 017 and 018 still say that nothing has run under the
freeze. Each is pinned by its study's own freeze and cannot be edited
([ADR 0004](../docs/adr/0004-keep-appendable-files-out-of-the-freeze-set.md)); the status
column above and each study's `ANALYSIS.md` are current.
"Frozen + run" marks the studies that passed a preregistration through
cross-vendor adversarial review, froze it, and executed the registered primary attempt;
each study's own `PREREGISTRATION.md`, `PREREG-REVIEW.md`, and results carry the detail
the status column compresses.

## Independent open-source projects these studies build on

Third-party projects the studies pin and test against, credited with their exact pinned
state and license. Every study also records these in its own `PINS.json` / `upstream/`;
this table is a rollup, not the source of truth. None of these projects is affiliated
with Judgment Pack — that independence is the point of the studies that use them.

| Project | Used by | Repository | Pinned commit | License |
| --- | --- | --- | --- | --- |
| RuleArena | [001](001-policy-representation/) | [SkyRiver-2000/RuleArena](https://github.com/SkyRiver-2000/RuleArena) | `3b9e2256` | MIT |
| τ²-bench | [002](002-qualitative-policy/), [003](003-escape-census/) | [sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench) | `1d244f5d` | MIT |
| Agent Eval Forge | [013](013-agent-eval-forge-integration/) | [deghosal-2026/agent-eval-forge](https://github.com/deghosal-2026/agent-eval-forge) | `8925cacc` | MIT © Debashish Ghosal |
| OpenWorkProof | [014](014-openworkproof-binding/), [016](016-policy-currency-anchor/) | [dengyier/OpenWorkProof](https://github.com/dengyier/OpenWorkProof) | `8eeca6ff` | Apache-2.0 (per `LICENSE`) |
| Open Policy Agent | [019](019-authorship-across-representations/) | [open-policy-agent/opa](https://github.com/open-policy-agent/opa) | v1.19.0 release, `opa_linux_amd64_static` `1dd5c559…` *(pinned and enforced in 019's `harness/PINS.json` since the freeze)* | Apache-2.0 (per `LICENSE` at v1.19.0) |
| Cloudflare OS | [015](015-cloudflare-os-boundary/) | [cloudflare/cloudflare-os](https://github.com/cloudflare/cloudflare-os) | `b2a51b54` | Apache-2.0 (per `LICENSE`) |

The evaluator under test is the [judgment-pack-runtime](https://github.com/Judgment-Pack/judgment-pack-runtime)
release binary, pinned by release tag and executable digest per study. The blinded-authorship
and interoperability studies use [codex-cli](https://github.com/openai/codex) as an
independent-vendor author or adversarial reviewer, pinned by version; that
cross-vendor separation is what makes those studies evidence rather than self-report.

## Reading a study

Every study directory carries, at minimum: a `README.md` (what it is), a
`PREREGISTRATION.md` (the registered protocol, frozen before results), a `DEVIATIONS.md`
(corrections after the freeze, never by editing the preregistration), and its results.
Interoperability and blinded-authorship studies additionally carry a `PREREG-REVIEW.md`
with the verbatim cross-vendor review rounds and their dispositions. The invariant across
all of them: preregistration and public harness first, results second, and the ceiling
stated plainly — these studies establish binding, lineage, and expressiveness, never that
a policy or a fact is true.
