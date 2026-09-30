# Study 014 — decision-to-execution binding under an external receipt protocol

**Status: FROZEN by the squash-merge of PR #49, and the registered primary attempt has run:
`R1 holds`, and the reviewer holdout is concordant, 8 of 8** ([`ANALYSIS.md`](ANALYSIS.md),
`results/primary-attempt-001`).
Six pre-freeze cross-vendor review rounds closed with `freezable as written`
(`PREREG-REVIEW.md`). Everything executed before the freeze is harness validation under
`pilots/`, labeled as such, and supports no claim beyond "the machinery works". The
first registered attempt is primary and is defined in the preregistration's freeze
section.

## What it is

An interoperability falsification study between two independently designed layers:

- **JPS** owns the judgment: given this exact pack and these exact inputs, what
  disposition follows (deterministic, byte-portable under Core §8.3).
- **OpenWorkProof** (an independently developed execution-verification protocol —
  Ed25519-signed work orders, capability grants, action receipts, causal replay, an
  offline acceptance-bundle verifier) owns authorization, execution receipts, and chain
  verification.
- A **thin adapter** (`adapter/SPEC.md`) owns exactly one thing: a *judgment commitment* —
  the digest tuple `{pack bytes, input bytes, canonical disposition, replay tuple,
  authorized action}` — bound into the OWP chain at two signed points, and a verification
  ceremony that recomputes it from retained artifacts. The two points are **defense in
  depth**, not a demonstrated necessity: OWP already associates every receipt with its
  signed work order cryptographically, and no arm here establishes what the second point
  adds over that.

The study then tries to break the composition: 33 registered one-at-a-time mutations
(judgment-artifact, facts, disposition, action, replay/drift, causal-chain) plus 5 controls
and 1 disclosed demonstration, each adjudicated per layer — did OWP's unchanged verifier
catch it, did the adapter's binding check catch it, did deterministic JPS replay catch it,
or did nothing? An undetected-by-all cell is a primary result, preserved, never patched:
alternative-work-order remint is registered as such up front, and decision currency is
registered as an analytic limitation because no fixture distinct from the baseline can
observe it at all.

What a green ceremony means, stated narrowly: **the retained artifacts and the receipted
lineage are internally consistent, and the executed call the chain records is the one the
recorded judgment authorized.** It is not a claim that the action physically happened (a
receipt is an attestation by the signing system), not a claim that the judgment is correct,
and not a claim that a JPS disposition authorizes anything — an approve disposition is
eligibility under a study-defined map, never an OWP capability grant. An insider holding
every fixture key can remint a whole alternative chain that this composition does not
distinguish; catching that needs an anchor outside the chain.

Neither protocol is modified. OWP is consumed as an installed package at a pinned commit;
jpack as a pinned release binary. The commitment rides in slots OWP signs but never
reads (`WorkOrder.objective`, `AgentRequest.context_source_digest`) — the study measures
precisely the difference between *carried under signature* and *semantically checked*.

## How it relates to what came before

- **Study 013** asked whether the surrounding application *behaves* consistently with the
  judgment, live, under an external regression harness. 014 asks whether a third party
  can later *prove*, offline, from retained artifacts and pinned keys alone, exactly which
  judgment authorized exactly which executed action. Same boundary, different question:
  behavior vs provenance. The disposition→action map here is study-defined, as 013's
  execution mapper was — JPS Core binds no caller.
- **The gateway** proves byte-lineage of *inputs* under its own signing identity and
  refuses, by policy, to let a receipt assert truth or authorization. Its mechanisms
  (record signing, chaining, the external-anchor lesson, the §5a consumer ceremony) are
  prior art here; its subject matter is disjoint. The registered boundary rows are the
  gateway's registry lesson resurfacing one layer up.
- **ADR-0002's ceiling** governs both layers of this composition: binding/lineage, not
  truth.

## Reproduce (once frozen)

```
export JPACK_BIN=/path/to/jpack           # pinned v0.16.0 release binary
export OWP_SOURCE=/path/to/OpenWorkProof  # the pinned clone, read-only, build path only

harness/build_fixtures.py --force   # one-time fixture construction (entropy pinned; output frozen by manifest)
harness/make_manifest.py            # regenerate harness/STUDY-MANIFEST.sha256 (--check to verify)
harness/run_verify.py --cell fixtures/baseline
harness/score.py --attempt-root pilots/<new-directory>
python -m pytest harness/tests -q
```

Both environment variables are required: the tests fail rather than skip without them.
`OWP_SOURCE` is checked, not just used — the clone's HEAD, its tracked-file cleanliness and
every helper file the builder imports are pinned in `harness/PINS.json`, and a mismatch
refuses the build. So does an untracked path carrying any importable suffix under the roots
the builder prepends to `sys.path`, an `openworkproof` that, once imported, is not the
installed package the pins cover, or any other module the import brought in from outside
that package, the pre-existing search path and the pinned helper files. Toolchain pins (OWP commit + venv, jpack release digests, interpreter,
dependency freeze) live in the same registry and are enforced by the scorer before it
adjudicates anything; upstream identity in `upstream/`.

The freeze anchor is linear: `harness/STUDY-MANIFEST.sha256` covers the code, the protocol
documents and the locked stratum's fixture manifests; `harness/PINS.json` pins that
manifest's digest; the freeze commit anchors `harness/PINS.json`. The manifest covers
neither itself nor the registry that pins it.

The registry is stratified: `harness/MATRIX.json` is the locked-replication stratum,
`harness/MATRIX-HOLDOUT.json` is the reviewer-authored holdout stratum, and
`--include-holdout` is refused mechanically until the preregistration freezes. It is the
only route into that stratum, and the builder's library routes enforce that rather than
assume it: they require an attempt context the scorer mints after its freeze gates pass.
After the freeze the flag makes the attempt construct the holdout stratum itself — inside
its own `holdout-fixtures/` subtree, with every per-cell manifest digest stamped into the
attempt record, re-hashed after adjudication and compared against those stamps — and record
every cell's construction outcome, so a refusal is a finding and a crash is a recorded
pipeline event.

Nothing in this repository claims any JPS conformance.
