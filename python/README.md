# JPS evaluator (Python, experimental)

This standard-library-only Python package evaluates Judgment Pack Core inputs under the
`0.2.0-draft` semantics in `reference/`. It also retains a separately enabled experimental
prototype of RFC 0008's `exists`, `every`, and `uniform` conditions, and an independently enabled
prototype of draft RFC 0016's outcome values.

This package makes **no evaluator-conformance claim**. Corpus results are reported as test results
only; they do not establish a claim or anything about the truth, authority, safety, or fitness of a
pack or disposition.

## Python API

```python
from jps_evaluator import canonicalize_disposition, evaluate

disposition = evaluate(
    pack,
    facts,
    evidence={
        "intake-form": "present",
        "sponsor-endorsement": "unknown",
    },
    supported_extensions=[],
    evaluation_work_limit=200_000,
)

canonical_bytes = canonicalize_disposition(disposition)
```

`evidence` is optional. Omitting it supplies the implicit empty object; an omitted requirement key
is `"unknown"`. A supplied evidence document must be an object keyed only by declared evidence
requirement ids, with values `"present"`, `"absent"`, or `"unknown"`.

`evaluate()` returns only the §8.3 disposition:

```json
{
  "kind": "outcome",
  "outcomeId": "proceed",
  "reasons": [],
  "handoff": {
    "state": "none"
  }
}
```

`outcomeId` is present exactly for an outcome. `reasons` and `handoff.triggeredBy` are
duplicate-free arrays sorted by Unicode code point. `canonicalize_disposition()` implements the
strings/Booleans/arrays/objects subset of RFC 8785 and returns UTF-8 bytes. Booleans occur in
RFC 0016 values; numbers and nulls remain excluded.

Failures raise an `EvaluationError` subclass. Every error has an `error_class` and `phase`:

| Class | Phase |
| --- | --- |
| `pack-not-conformant` | `preflight` |
| `malformed-input` | `preflight` |
| `unsupported-required-extension` | `preflight` |
| `resource-exhaustion` | `evaluation` |

Preflight is ordered pack, facts, evidence, then supported extensions, and completes before
resolution starts. Errors never return a disposition.

Both `0.1.0-draft` and `0.2.0-draft` packs are accepted. RFC 0008 remains disabled by default;
`enable_rfc0008=True` only enables the local prototype and does not change a pack's status or create
a claim.

## Draft RFC 0016 outcome values

Outcome values are **off by default**. Enable this local prototype with
`evaluate(pack, facts, enable_rfc0016=True)` or the CLI's `--enable-rfc0016` flag. This implements
a draft proposal, not an adopted Core feature, and makes no conformance claim. The flag admits
and supports exactly `org.judgmentpack.outcome-values` on outcomes; it works with either existing
accepted `specVersion`. It is independent of `enable_rfc0008`.

A pack using it must list `org.judgmentpack.outcome-values` in `metadata.requiredExtensions`.
An outcome can then declare, for example:

```json
"extensions": {
  "org.judgmentpack.outcome-values": {
    "refundAmount": {"type": "decimal", "fromFact": "/proposed/refundAmount"},
    "currency": {"type": "string", "constant": "CAD"}
  }
}
```

Each source has exactly one `constant` or `fromFact`, and type `string`, `decimal`, or `boolean`.
Declarations are checked during pack preflight, including on outcomes that will not be selected.
Other Core validation remains in place. No additional `supported_extensions` argument is needed;
listing this capability there alone does not enable the prototype.

After a rule, forced outcome, or fallback selects an outcome, its values are copied exactly into
the disposition's `value` object. Strings must contain Unicode scalar values; decimals must be
strings satisfying Core's decimal grammar; Booleans must be JSON Booleans. An absent pointer or
wrong type yields `unresolved` with only `unknown`, no `outcomeId`, and no partial `value`.
Fallback is not retried. Handoff follows the pack's `unknown` trigger. Other dispositions have
no `value` member. Values perform no calculation, range check, origin verification, or action,
and do not authorize external action.

With the flag off, reserved-name admission still fails as `pack-not-conformant`, including when
the capability is supplied in `supported_extensions`. Thus the RFC's three unsupported-consumer
error variants do not produce its proposed `unsupported-required-extension` class here. This
preserves the existing off-mode contract; see decision 28. Decisions 27–33 record admission,
placement, Unicode, limits, example reconstruction, and CLI transport choices.

## CLI

```console
python -m jps_evaluator \
  --pack pack.json \
  --facts facts.json \
  --evidence evidence.json \
  --supported-extension com.example.capability \
  --evaluation-work-limit 200000
```

For a pack carrying outcome values:

```console
python -m jps_evaluator --pack pack.json --facts facts.json --enable-rfc0016
```

On success, stdout contains a compact JSON envelope whose `disposition` member is emitted from its
RFC 8785 canonical bytes:

```json
{"conformanceClaim":"none","disposition":{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"proceed","reasons":[]},"experimental":true}
```

On error, stdout is empty, stderr contains an envelope with separate `class`, `phase`, and `message`
members, and the process exits with status 2. Error envelopes contain no `disposition`.

## Tests

From the repository root:

```console
python3 -m pytest python/tests -q
```

The suite covers Core §§7–8, strict JSON input, full pack structure and semantic references,
preflight precedence, every Core error class and phase, portable disposition invariants, JCS bytes,
the CLI, and the supplied evaluation corpus manifest.

`tests/test_rfc0016_outcome_values.py` covers every example and each document, evaluation, and
error case listed in RFC 0016, with named rows. It compares the RFC's stated disposition bytes
and the full CLI envelope, and explicitly tests the preserved errors described in decision 28.

The current clean-room corpus snapshot supplies all four fixtures for the twenty manifest cases.
Decision 26 records the earlier snapshot's missing fixtures; its basename path resolution still
applies to the supplied layout.

## Resource limits

These are implementation limits, not portable Core semantics:

- 16 MiB per JSON text;
- nesting depth 128;
- 200,000 JSON values and object members per input;
- 1 MiB per string or object member name;
- 4,096 characters per JSON-number token;
- 10,000 combined authored evaluation collection items across evidence requirements, outcomes,
  rules, and exceptions, plus all declared outcome value sources when RFC 0016 is enabled; and
- 200,000 evaluation-work units by default, configurable through the Python API and CLI.

A pack that reaches a document/carrier admission limit is `pack-not-conformant`. A facts or evidence
document that reaches one is `malformed-input`. Reaching the collection or work limit after admission
is `resource-exhaustion`. No limit produces a partial disposition.

RFC 0016 resolution shares the conditions' work budget. For the produced outcome, each source
costs `1 + len(value-name)`; a `fromFact` adds the existing pointer cost (one plus
`1 + len(decoded-token)` for each attempted token); a constant or resolved selection adds one
type inspection plus its character count if it is a string. Composite selections fail the type
check without traversing their contents. The whole declaration is charged once before any
unresolved value can stop resolution, so member order cannot affect the budget. See decision 31.

See `DECISIONS.md` for underdetermined choices and their source text.
