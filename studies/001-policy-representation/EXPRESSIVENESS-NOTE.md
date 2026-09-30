# What 461 lines of regulatory text look like as a judgment pack

**An expressiveness report from Study 001.** Not an efficacy claim: nothing here says whether
judgment packs help anyone. This reports only what happened when the format was pointed at real
regulatory text and asked to carry it. *(Update 2026-09-30: when this note was written no
comparison arm had been run. All three arms have since run, and on the preregistered endpoint the
pack arm loses; see [`RESULTS-FIRST-PROMPT-ARMS.md`](RESULTS-FIRST-PROMPT-ARMS.md). The sentence
that previously stood here said "no comparison arm has been run" and is superseded.)*

Everything below is reproducible from the pinned artifacts in this directory. The subject is the JPS
`0.1.0-draft` format and the reference runtime's experimental evaluator (`judgment-pack` v0.2.0),
which claims no conformance.

---

## What was encoded

461 lines of the NBA Collective Bargaining Agreement, as published in
[RuleArena](https://github.com/skyriver-2000/RuleArena) (ACL 2025, MIT, commit `3b9e2256`) — real
regulatory prose, not a synthesized policy. The decision: *is this set of roster operations legal?*

The pack was authored clean-room by a coding agent from the CBA text and the benchmark's rule-name
vocabulary alone; no instance, gold answer, or answer distribution was read. It validates at
`exit 0` and its 61 rules cover **61 / 61** of the vocabulary the benchmark uses to annotate which
provisions govern each instance.

## What the format carried well

- **The rules themselves.** 61 provisions encoded as conditions over facts, each citing the CBA
  article and section it came from. Citation is native, not bolted on.
- **Uncertainty as a first-class result.** Every rule carries `onUnknown: escalate`. When a fact an
  applicable rule needs is absent, the evaluation resolves to `unresolved` with a reason and a
  handoff request rather than guessing. Across 432 evaluations there were **zero engine refusals** —
  every input produced a disposition or an explicit escalation.
- **Multiple simultaneous violations.** Three independent violations produce one `illegal` outcome
  citing three rules, with no conflict.

## What the format could not carry — four findings

### 1. No arithmetic, so 124 facts had to be computed elsewhere

JPS compares facts; it has no arithmetic. Every quantity the CBA reasons about — post-transaction
team salary, apron comparisons, maximum-salary tiers, year-over-year escalation — must be supplied
to the pack rather than derived by it. The pack requires **124 `/facts/derived/*` fields**: 39
always-present booleans, 18 conditional booleans, 67 conditional decimal strings.

The pack holds the constants (25/30/35 %, 105 %, 175 %, 120 %, 130 %, 5 %, 8 %, …) and the
preprocessor holds the division. That division is a defensible split — but it means a reader of the
pack alone cannot see the whole decision.

### 2. Part of the *reasoning* migrated out, not just the arithmetic

This is the sharper version of finding 1. **13 of the 39 always-present booleans name which Salary
Cap Exception a transaction invokes.** The source prose never states one; working it out is the
legal reasoning the benchmark exists to test. Selecting "the lowest tier whose limb covers the
amount" requires comparing against a computed limb, which the format cannot express — so the
selection lives in the preprocessor.

The consequence for any evaluation: a score for the pack is partly a score for the preprocessor.
We report it, but we do not claim it measures the format.

### 3. The format can say *unknown*, but not *immaterial*

**The pack cannot decide 28 % of instances** (60 of 216). Almost all trace to one cause: the Minimum
Player Salary schedule appears in *neither* the CBA excerpt *nor* the benchmark's stipulations — it
is nowhere in the corpus. 77 of 216 instances contain a contract stated at "minimum applicable player
salary". A preprocessor that refuses to invent the figure cannot compute those teams' salaries, the
fields are omitted, the rules go `unknown`, and the instance escalates.

A language model reading the same text handles this by treating minimum contracts as *immaterial* —
too small to change the answer — and proceeds. **The pack cannot, because JPS has no "immaterial".**
Its three-valued logic distinguishes true, false, and unknown; it has no way to say "this input is
missing but too small to matter."

This is arguably the most interesting boundary the exercise found. It is not a bug in the pack, and
we deliberately did not fix it by inventing a number.

### 4. Conflict semantics force a single-outcome architecture

§8 treats two *distinct* candidate outcomes as `conflict` → `unresolved`. A pack containing both
affirmative "this is legal" rules and "this is illegal" rules therefore goes unresolved whenever one
of each fires — which, in a domain of independent provisions, is common.

The pack is consequently built as **61 violation detectors that all resolve to `illegal`, with
`legal` reachable only as `fallbackOutcome`.** That works, and it makes every fired rule an
independently reportable citation. But it is a workaround discovered by the author, not a documented
pattern, and it means the format nudges hard toward "detect violations, default to the good outcome"
rather than "weigh the considerations."

## What this suggests

For a decision of this shape — dense, arithmetic-heavy regulatory computation — **JPS expressed the
*policy* faithfully and a substantial part of the *determination* migrated into a preprocessor the
format cannot describe.** The pack is an honest, citable, machine-checkable statement of the rules.
It is not, on its own, the decision procedure.

Whether that is a limitation or a correct separation of concerns depends on a question the
specification has not answered: **is the fact-preparation layer inside the format's remit or outside
it?** Today it is outside, invisible, and unattributable — the disposition cannot say "this answer
depended on a derived value someone else computed under this definition."

Two questions go to the specification from this exercise, and are the subject of a companion RFC:
derived values and their attribution, and materiality.

## Honest limits of this note

- **One domain, and an adversarial one.** NBA transaction legality is arithmetic-dense by design.
  A format that declines to compute is playing away from home here. Nothing in this note transfers
  to qualitative policy without repeating the exercise there.
- **One pack, authored by one coding agent** in a clean room, in roughly a day. A domain expert with
  more time might encode more, though not the arithmetic — that boundary is structural.
- **The 28 % undecidable figure is partly a corpus property**, not purely a format property: the
  missing salary schedule is absent from the benchmark, not from the CBA in the world.
- **No efficacy claim in this note.** When it was written, arms A and A′ had not been run, and
  [PIPELINE-STATUS.md](PIPELINE-STATUS.md) listed the gaps, including two that would bias any
  future comparison. *(Update 2026-09-30: both arms have since run; the comparison is reported in
  [`RESULTS-FIRST-PROMPT-ARMS.md`](RESULTS-FIRST-PROMPT-ARMS.md).)*

## Reproducing

```bash
rulearena/fetch.sh
judgment-pack spec validate packs/nba-transaction-legality.json          # exit 0
python pipeline/parse_nba.py --checkout rulearena/checkout --out pipeline/out/facts --strict
python pipeline/derive.py   --facts pipeline/out/facts --out pipeline/out/facts --strict
python pipeline/derive.py   --readings                                    # the 15 numbered readings
```

Detail: [`packs/COVERAGE.md`](packs/COVERAGE.md) (what the pack covers, the 124-field contract, 15
numbered interpretation readings), [`pipeline/DERIVED.md`](pipeline/DERIVED.md) (the preprocessor and
what it refuses to invent), [`pipeline/PARSE-COVERAGE.md`](pipeline/PARSE-COVERAGE.md).
