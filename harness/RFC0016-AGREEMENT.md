# RFC 0016 cross-implementation agreement

Run date 2026-09-29, over 66 rows. The first 60 were run on 2026-09-28 and give now what they
gave then. Two prototypes of draft
[RFC 0016](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0016-outcome-values.md)
(outcome values) are driven over the same inputs, and what each answers is compared with the other
and with the answer the RFC's text gives.

- **Implementation A, Go.** The reference runtime's experimental evaluator, built from
  judgment-pack-runtime at commit `f98d4c9` of its main branch, which is
  [pull request 172](https://github.com/Judgment-Pack/judgment-pack-runtime/pull/172) as it was
  merged. The run was first made against that pull request's branch at `dacceff`, before the
  merge, and gave the same answer on every row. It is invoked as
  `jpack experimental evaluate <pack> --facts <f> [--evidence <e>] --rfc0016-outcome-values --format json`.
  Its decisions are in that pull request's ADR-0039.
- **Implementation B, Python.** The clean-room `jps_evaluator` in this repository's `python/`,
  invoked as `python -m jps_evaluator --pack <p> --facts <f> [--evidence <e>] --enable-rfc0016`.
  Its decisions are `python/DECISIONS.md`, entries 27 to 33.

**This file is the output of referee tooling, not a conformance claim.** RFC 0016 is a Draft. A
pack that uses it carries a reserved name and is not a valid document under any published version
of the specification. The RFC's own Implementation section states the standing limit: the two
implementations "are not independent evidence", because both trace to one maintainer's direction.
Agreement here corroborates the text. It does not confirm it independently.

## Reproducing

```console
$ python3 harness/rfc0016_harness.py <go-binary> python
```

The rows are [`rfc0016_cases.json`](rfc0016_cases.json), written by
[`make_rfc0016_cases.py`](make_rfc0016_cases.py). Each row carries its own pack and facts as JSON
text, so that a row can hold what a decoded value cannot: a member given twice, an escape, an
order of members. Each row names the case of the RFC it runs, in the RFC's words, and carries the
answer the RFC's text gives: a disposition in its canonical bytes, or a Core §8.4 error class. The
expected answers were written from the RFC and not read off either implementation.

A disposition is compared byte for byte, as each implementation wrote it. The bytes are cut out of
each implementation's output and are not decoded and written again. An error is compared by its
class alone, since §8.4 leaves an error's transport undefined and the two differ on it.

## Result

| | |
| --- | ---: |
| Rows | **66** |
| Both implementations give the RFC's answer | **62** |
| Both agree with each other and not with the RFC | **3** |
| The two implementations differ | **1** |

The 66 rows are the RFC's 6 positive and 14 negative document cases, its 28 evaluation rows, 7
error rows, and 11 rows from its Examples. Of the 45 rows whose answer is a disposition, 44 are
byte-identical between the two implementations and identical to the RFC's bytes, among them the
disposition the RFC prints under *The disposition*.

## The rows of the Examples

Five of the eleven were among the first 60. Six were added on 2026-09-29, for the cases of the
RFC's Examples that had no row
([issue 118](https://github.com/Judgment-Pack/judgment-pack-evaluator-experiments/issues/118)).
Both implementations give the RFC's answer on each of the six.

| Rows | What they run | The answer |
| --- | --- | --- |
| `example-tiers-high` | The tiers pack, with a score that makes its rules produce `limit-high` | That outcome, with `creditLimit` of `"10000"` |
| `example-pass-through-undeclared-amount-absent`, `…-amount-a-number` | The pass-through pack without its declaration and without its entry in `metadata.requiredExtensions`, with the amount absent and with the amount given as the JSON number `149.5` | `approve-refund`, and no `value` |
| `example-calculated-approved`, `…-at-the-bound`, `…-above` | A pack written for the RFC's calculated quantity | `approve-refund` with the amount as the fact gives it, or `refer-to-supervisor` with no `value` |

**The pack without the declaration is a pack of Core's**, and its two rows are run with neither
opt-in. They are the other half of two rows that were there already: with the declaration the
same facts give `unresolved`, and without it they give the outcome. That is the RFC's point in
that example, and both halves of it are now run.

**The RFC gives no pack for the calculated quantity.** It gives the sentence the pack is written
from, the fact, the operand and the declaration. The pack of these rows is one reading of it, and
each row carries what was chosen in writing it:

- the value is named `refundAmount`;
- a refund above 500 is sent to a supervisor by an outcome of its own, `refer-to-supervisor`,
  which declares nothing, and not by an escalation;
- a refund of exactly 500 is not above 500, and is approved;
- both rules ignore an unknown.

Another reading would give other rows. The row at the bound runs an amount of `"500.00"`: the
comparison reads it by its mathematical value (Core §7.4), so the refund is approved, and the
value is copied as it was found, so the disposition carries `"500.00"` and not `"500"`.

**What the Examples' rows still do not run** is what the RFC's open questions leave undecided:
a reader whose schema admits the name, an input at either implementation's limits, and a pack
that uses this draft together with RFC 0008.

## The one divergence

**A fact string that holds an unpaired surrogate** (`adversarial-string-fact-unpaired-surrogate`).
The RFC says such a value does not resolve, which gives `unresolved` with reason `unknown`.

| | Answer |
| --- | --- |
| The RFC | `unresolved`, reason `unknown` |
| Python | `unresolved`, reason `unknown` |
| Go | the `malformed-input` error, and no disposition |

The two differ before RFC 0016 is reached. The Go runtime's carrier refuses any input document
that holds an unpaired surrogate escape, under any flag, because RFC 8785 cannot serialize such a
string. The Python evaluator admits the document and refuses the value where it is selected. Core
§2.1 requires an implementation to reject "malformed" input and does not say whether a JSON text
with an unpaired surrogate escape is malformed.

This is a finding about the specification. The RFC's row assumes a carrier that admits the
document. Either Core says what a carrier does with such a text, or the RFC's row says that it
applies where the carrier admits it. It is not settled here, and neither implementation was
changed to match the other.

## The three rows where both differ from the RFC

The RFC lists three rows for an implementation that does not support the extension: given a pack
with a well-formed declaration, an empty one, or one of an unknown type, it answers
`unsupported-required-extension`. Both implementations, run without their opt-in, answer
`pack-not-conformant`.

The reason is the same in both. Without the opt-in each holds a pack to the schema of
`0.2.0-draft`, which refuses every name that begins `org.judgmentpack.`. The pack is refused as a
document before the supported extensions are compared. The RFC's Compatibility section says this
of the current schema, and its row describes a reader whose schema already admits the name. No
such schema is published. The rows cannot be run as written until one is.

The fourth row of that group, a member given twice inside the declaration, is `pack-not-conformant`
for every implementation, and both give it.

## What the two implementations decided differently and the rows do not show

These are read from the two decision logs. No row of the RFC separates them.

| | Go | Python |
| --- | --- | --- |
| How the name is admitted | The name is removed from outcomes and from the required list, and the published validator judges what is left | The name is admitted in those two places and the rest of Core's checks run as they were |
| Together with the RFC 0008 prototype | Refused: one draft to an evaluation | Allowed: the two opt-ins are independent |
| Pack versions | `0.2.0-draft` only | `0.1.0-draft` and `0.2.0-draft` |
| What the work of resolution is charged | Every outcome produced is charged the search for it, and the whole declaration is charged with its names and constants | An outcome with no declaration is charged nothing, and each value is charged its name and its value |
| Where a limit on the number of values is | None of its own | Counted with the other authored items against a limit of 10,000 |

The RFC leaves bounds open (its unresolved question 8), so the last two rows are differences the
RFC permits. An input near either implementation's limit is not portable between them.

## What this run is not

- It is not a corpus result. It runs in this repository's CI, against the Go runtime at the
  commit CI pins, `f98d4c9`, after `test_rfc0016_harness.py` has held the driver's verdicts and
  the rows' expected answers. The pin was moved to that commit in a change of its own, after the
  rows were merged: this repository does not move the pin in the commit that adds rows.
- It is not independent evidence, for the reason given at the top.
- It says nothing about whether outcome values should be an extension or a member of Core. The
  semantics are the same in both forms, and both implementations built the extension form.
