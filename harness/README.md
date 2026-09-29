# Post-hoc agreement harness

NOT part of the clean-room deliverable: this referee tooling knows both
implementations' output shapes and was added after the clean-room session
ended. It runs identical (pack, facts, evidence, supported-extensions)
inputs through the Go reference runtime and an implementation here (pass
its directory, e.g. `python/`, as the implementation argument) and diffs the
dispositions' semantic content (kind, outcomeId, reasons set, handoff
state).

`rfc0008_harness.py` is the same idea for draft RFC 0008's collection
quantifiers, with two differences the RFC forces: every case in
`rfc0008_cases.json` carries its own pack (the rows differ in the condition
under test, not only in the facts), and both implementations must be opted in
to the draft grammar. It also runs the equivalence check RFC 0008's
Conformance section asks for, over the assets in `rfc0008_equivalence/`.
Findings: `RFC0008-AGREEMENT.md`.

`rfc0016_harness.py` does the same for draft RFC 0016's outcome values. Its rows are the cases
that RFC lists under Conformance and Examples, written by `make_rfc0016_cases.py` from the RFC's
text, each with the answer the text gives. It compares three things for each row: the Go answer,
the Python answer and the RFC's. A disposition is compared byte for byte as each implementation
wrote it, and an error by its §8.4 class. Rows known not to match the RFC's answer are named in
the cases file with their reason, and the run fails if a row gets a verdict the file does not name
for it. Its verdicts and the rows' expected answers are tested in `test_rfc0016_harness.py`, which
needs neither evaluator. Findings: `RFC0016-AGREEMENT.md`.

Result on 2026-07-27 against judgment-pack v0.2.0 and the
data-request-intake-triage example: 13/13 agreement (the nine RFC 0006
appendix instances plus three probes). One shape divergence recorded, not
counted as semantic: the disposition's handoff serialization
(object-with-target-echo vs bare string enum) is underdetermined by the
RFC -- see python/DECISIONS.md entry 3.

`error_class_agreement.py` covers what `class_agreement.py` cannot. That driver compares
dispositions and treats any error as a non-result, and the frozen corpus has no error row, so
nothing compared WHICH Core §8.4 class the two implementations report. This one runs the
specification's **staged** rows (`reference/conformance-evaluation-staged/`, in no corpus) through
both and compares three classes — Go's, Python's, and the row's — since a staged row may itself be
what is wrong. §8.4 leaves an error's transport undefined and the two differ on it (the Go runtime
writes `evaluationError` to stdout, the Python evaluator writes `error` to stderr), so the driver is
told where each puts a result and an error and compares the class identifier alone. Its verdict
logic and the vendored rows' digests are tested in `test_error_class_agreement.py`, which needs
neither evaluator. Findings: `ERROR-CLASS-AGREEMENT.md`.

## The runtime pin, and when to move it

`class_agreement.py` takes a Go binary, so CI builds one from a **pinned, immutable
runtime commit** rather than a branch. A moving ref would let a change in another
repository decide, silently, whether this repository's cross-implementation evidence
still holds — and the whole point of the comparison is that a divergence is
adjudicated against the specification text, never by preferring whichever
implementation moved last.

To advance the pin: change the `ref` in the `evaluator-agreement` job to another
reviewed runtime commit, run the harness locally against it, and say in the pull
request what that commit changed about evaluation.

**The shape to refuse is a pin advanced together with a row's expectation in one
commit.** That is indistinguishable from making the evidence agree by moving the
thing it was evidence about.
