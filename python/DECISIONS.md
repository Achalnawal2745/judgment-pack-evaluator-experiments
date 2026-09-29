# Interpretation decisions

This log records choices made from the supplied clean-room reference texts. Quotations below are the
exact text relied on. The implementation was not compared with another evaluator.

1. **An omitted evidence-availability input is an empty object, so every declared requirement is
   initially `unknown`.**

   Text relied on: RFC 0006 says, “one JSON object keyed by declared
   `evidenceRequirements[].id`, each value `present`, `absent`, or `unknown`; an omitted key means
   `unknown`.” The brief calls the whole object “optional.”

   Alternatives considered: reject an omitted document, or treat omission as a complete manifest
   in which every item is absent. I chose an empty object because it applies the RFC’s omitted-key
   rule without inventing completeness.

2. **The JSON serialization of the reason set is a deterministically ordered array.**

   Text relied on: RFC 0006 defines “`reasons` an unordered, deduplicated set (set equality; empty
   iff `kind` = `outcome`)”; Core §8 says, “Reasons are a de-duplicated set; their order carries no
   priority.”

   JSON has no set value. Alternatives were an object keyed by reason or a nondeterministically
   ordered array. I chose an array, ordered by the vocabulary’s specification order solely for
   reproducible bytes. Consumers and tests compare it as a set; the order has no semantics.

   **0.2.0-draft alignment:** Core §8.3 now closes the ordering question: the array is sorted
   ascending by Unicode code point. The current implementation uses that required order; the
   historical choice above is retained only as lineage.

3. **`handoff` is serialized as the string `none` or `requested`, with no additional portable
   target member.**

   Text relied on: RFC 0006 says, “`handoff` ∈ {`none`, `requested`} echoing the declared target
   when requested,” while the brief enumerates the output as “(`kind`, `outcomeId`, `reasons` as a
   deduplicated set, `handoff`)”.

   The phrase “echoing the declared target” suggests target data, but the same sentence constrains
   `handoff` to two string values and specifies no target member or object shape. I chose the
   explicit enum and did not invent an extra field. This leaves the target-echo phrase
   under-specified.

   **0.2.0-draft alignment:** Core §8.3 now closes this shape: `handoff` is an object with always
   present `state` and conditionally present `triggeredBy`. The current implementation uses that
   required object; the historical choice above is retained only as lineage.

4. **A direct exception escalation requests handoff even when the pack has no `escalation`
   object.**

   Text relied on: Core §8.1 says, “A direct exception escalation without an `escalation` object
   remains an unresolved direct request with no Core-defined destination.” RFC 0006’s
   implementation-experience text likewise describes “a requested handoff with no target.”

   The alternative was `handoff: none` because there is no target. I chose `requested` because
   request state and destination availability are explicitly distinct.

5. **Required-evidence `absent` dominates required-evidence `unknown`, but does not erase
   `unknown` independently discovered from exceptions.**

   Text relied on: RFC 0006 says, “record `missing-required-evidence` iff any required
   requirement’s presence is **false**; record `unknown` iff any required requirement’s presence
   is **unknown** and none is false.”

   I apply “none is false” to the required-evidence step. If another stage independently records
   `unknown` (for example, an unknown exception with `onUnknown: escalate`), Core §8’s requirement
   to “Retain every reason discovered at this stage” keeps it.

6. **Unknown applicability stops evaluation before evidence, exceptions, or rules.**

   Text relied on: Core §8 step 1 says, “If it is unknown, produce an `unresolved` result with
   reason `unknown` and stop.”

   RFC 0006 says evidence blocking yields unresolved “after exception inspection,” but that text
   restates step 2 and does not repeal step 1’s explicit stop. I therefore do not inspect
   exceptions for false or unknown applicability.

7. **Ordered decimal comparison is mathematical: scale and negative zero do not affect the
   result.**

   Text relied on: RFC 0006 says decimal strings are “compared by mathematical value.” Core §2.2
   supplies the lexical grammar.

   Alternatives included lexical comparison and scale-sensitive comparison. Both contradict
   “mathematical value”; therefore `"1.0"` equals `"1.00"` for ordering purposes and `"-0"` is
   equal to `"0"`.

8. **Only two decimal strings participate in ordered comparisons.**

   Text relied on: RFC 0006 says, “an ordered comparison is defined iff both values are JSON
   strings conforming to the §2.2 decimal grammar ... any other value — including a JSON number —
   yields `unknown`.”

   I apply “both values” to the selected fact and condition operand. No string-to-number or
   JSON-number-to-decimal coercion is performed.

9. **JSON numbers loaded by the CLI retain exact base-ten mathematical identity.**

   Text relied on: Core §7.4 says, “JSON numbers compare by their mathematical value without lossy
   conversion.” RFC 0006 identifies representability as an unresolved question and says malformed
   input or resource exhaustion is an error.

   Alternatives were binary floating-point conversion or mapping large but valid numbers to
   `unknown`. I chose a small symbolic decimal-number representation, bounded by documented input
   limits, so equality is exact within those limits. Exceeding a limit is an explicit error rather
   than a disposition.

10. **Failure to resolve a valid pointer is `unknown`; syntactically malformed pointers in a pack
    are rejected during the pack sanity check.**

    Text relied on: Core §7.4 says, “A syntactically valid pointer that does not resolve, including
    an invalid array traversal at runtime, produces `unknown`.” The RFC says a malformed input is
    an evaluation error, and the schema constrains pointer syntax.

    The low-level pointer helper distinguishes syntax failure from traversal failure. During
    condition evaluation either inability yields `unknown`, but the top-level evaluator first
    rejects malformed pack conditions because a conforming pack is an input precondition.

11. **The evaluator performs evaluation-focused pack sanity checks, not full document
    conformance.**

    Text relied on: the brief says, “precondition: full document conformance, established
    externally — you may sanity-check the shape ... but need not reimplement document validation.”

    I check the root and every field that can affect evaluation, including condition shapes,
    identifiers used by evaluation, references, exception effect fields, fallback, escalation,
    and required extensions. I do not implement unrelated URI, timestamp, citation, or metadata
    format validation.

    **0.2.0-draft alignment:** §8.2 and §8.4 now make a non-semantically-conforming pack the
    `pack-not-conformant` error. The current implementation therefore validates the complete Core
    structure, asserted URI/date/date-time formats, and semantic references. The historical
    narrower choice above no longer describes the implementation.

12. **Supported extension names are exact, case-sensitive capabilities; duplicate names in the
    caller’s supported list are harmless.**

    Text relied on: Core §9 says, “A consumer that does not support every required extension ...
    MUST NOT silently ignore a required extension.” Extension names are JSON object keys, for
    which no case folding is specified.

    I use exact string set membership. A list describes capabilities rather than document
    members, so repeated declarations do not change its meaning.

13. **Optional extension values are validated only as bounded JSON and are otherwise inert.**

    Text relied on: Core §9 says, “An optional extension MUST NOT change Core semantics” and
    consumers “may otherwise ignore them.” RFC 0006 calls for hostile optional-extension content
    that “must stay inert during evaluation.”

    I neither interpret nor execute extension values. General JSON/resource checks still apply
    because all runtime input is untrusted.

14. **All exception and unsuppressed rule conditions are evaluated within their respective
    stages, regardless of the first blocking result.**

    Text relied on: Core §8 says, “Evaluate every exception condition and collect its effects,”
    “after all exception effects have been inspected,” and later “evaluate all remaining rules.”
    It also requires retaining both unknown and conflict when both occur.

    Early exit could miss a second reason or conflicting outcome. I collect the whole stage before
    resolving it.

15. **A compatible forced outcome bypasses normal rules but cannot bypass evidence or
    exception-stage blockers.**

    Text relied on: Core §8 step 5 makes missing required evidence, escalating unknown exceptions,
    conflicting exception effects, and direct escalation blocking; step 6 then says, “If one
    compatible forced outcome remains and no blocking state from step 5 exists, produce that
    outcome without evaluating normal rules.”

    This order rules out allowing a forced outcome to cure missing evidence or an escalation
    request.

16. **The appendix is exercised as ten input rows, while retaining its own description of nine
    logical instances.**

    Text relied on: the brief asks for “the nine walked instances,” RFC 0006 says “The nine
    appendix instances,” but the appendix table contains rows 1, 2, 3, 4, 5, 6, 7a, 7b, 8, and 9
    and says “instance 7’s two variants pin the semantics.”

    Alternatives were to omit either 7a or 7b to make nine executions, or to run every stated
    input/expected pair. I chose all ten table rows because the brief also says “the appendix rows
    are inputs *and* expected dispositions.” I treat 7a and 7b as variants of one logical
    instance.

17. **The appendix tests use a minimal pack reconstructed from the behavior stated in the
    appendix, because the named example pack is not among the supplied reference files.**

    Text relied on: the appendix says facts abbreviate `/request/*`, identifies the outcome and
    evidence ids, states that instance 8 is forced and normal rules are skipped, states that
    instance 9 has “decline and clarify rules both true,” and states “the `no-match` fallback path
    is unreachable for this pack while `fallbackOutcome` is declared.”

    The available reference directory contains only the RFC, Core text, and schema; the linked
    example is not supplied. I use the least additional structure that produces the walked
    branches: applicability requires `type=data-access`; `appropriateness=hard-fail` declines;
    either `completeness=incomplete` or `appropriateness=pending` clarifies;
    `complete` plus `pass` proceeds; embargo `true` forces decline; both evidence requirements are
    required; and `clarify-return` is the declared fallback. This reconstructed fixture tests the
    specified evaluator behavior but is not represented as a copy of the unavailable example.

18. **Errors are raised by the library and serialized by the CLI on stderr with a nonzero exit;
    their envelope still carries the brief’s experimental/no-claim markers.**

    Text relied on: RFC 0006 says, “Errors are not dispositions” and an error is produced
    “never a disposition.” The brief says to “refuse bad inputs explicitly” and separately says,
    “Every output payload must carry `"experimental": true` and `"conformanceClaim": "none"`.”

    Returning an error-shaped value from `evaluate()` could be mistaken for another disposition.
    Exceptions make the API boundary explicit; the CLI catches them, emits a separate JSON error
    envelope to stderr, and exits with status 2. The two required markers label that payload but do
    not turn it into a disposition: it has an `error` member and no disposition `kind`.

19. **The implementation has explicit, deterministic resource limits.**

    Text relied on: Core §2.1 requires implementations to reject “data exceeding their documented
    resource limits rather than process only a silent prefix”; Core §10 says implementations
    “SHOULD define limits for document bytes, nesting depth, collection sizes, string sizes, and
    evaluation work”; RFC 0006 says resource exhaustion is an explicit evaluation error.

    I chose limits large enough for the corpus: 16 MiB per CLI JSON text, nesting depth 128,
    200,000 JSON values/members, 1 MiB per string or member name, 4,096 characters per JSON-number
    token, (as refined by decision 25) 10,000 authored evaluation collection items, and (as refined
    by decision 22) 200,000 evaluation-work units. These are implementation limits, not semantics,
    and are documented in the README. Under Core 0.2.0-draft, document/carrier admission limits are
    classified during preflight and collection/work limits as evaluation-phase
    `resource-exhaustion`.

20. **Duplicate evidence keys are rejected at the JSON-text boundary; an already parsed Python
    dictionary cannot express a duplicate.**

    Text relied on: RFC 0006 says, “a duplicate or undeclared key is an input error,” and Core
    §2.1 says “object member names MUST be unique.”

    The CLI’s strict JSON loader receives member pairs and rejects every duplicate before building
    a dictionary. The Python API accepts an already materialized JSON value, where duplicate
    members have no representation; callers needing carrier-level duplicate detection must use
    `strict_loads()` or the CLI. Silently choosing the first or last duplicate at the text
    boundary was rejected.

21. **RFC 6901 array tokens use canonical unsigned indexes; `-` and leading-zero multi-digit
    tokens do not resolve.**

    Text relied on: Core §7.4 says, “A `fact.path` is interpreted as RFC 6901 JSON Pointer syntax,”
    “The empty string selects the document root,” and “an invalid array traversal at runtime,
    produces `unknown`.” The schema’s pointer pattern admits only ordinary characters and the
    escapes `~0` and `~1`.

    For object traversal, decoded tokens are exact member names. For arrays I chose RFC 6901’s
    canonical index interpretation: `0` or a nonzero digit followed by digits. The alternatives
    were accepting `01` as index 1 or treating `-` as an append/index value; neither identifies an
    existing array element in pointer resolution. `~0` decodes to `~` and `~1` to `/`; any other
    tilde escape is malformed.

22. **RFC 0008 work is an order-independent, runtime-expanded preflight measure with a default
    shared limit of 200,000 units.**

    Text relied on: RFC 0008 requires a work unit and a preflight function; charging before any
    element evaluates and independently of element order; ragged child work as `Σᵢ |Bᵢ|`; all
    Boolean branches and sibling aggregates; deep equality by runtime value size; `uniform`; and a
    stated treatment of successful, unresolved, and non-array pointer paths. It explicitly leaves
    the model and portable limit undefined. Core §10 asks implementations to define evaluation-work
    limits, and RFC 0006 makes exhaustion an error rather than a disposition.

    I chose the following candidate model. One evaluation owns a shared integer budget. Immediately
    before a condition reached by §8 is evaluated, a pure preflight function expands and measures
    that whole condition against its current runtime root; the complete charge is applied
    atomically, and no predicate in that condition runs if it does not fit. Conditions in §8 stages
    that are never reached (for example, rules after false applicability) are not charged.

    The unit formulas are:

    - every condition node costs 1;
    - a pointer attempt costs 1 plus `1 + len(decoded-token)` for every token attempted, including
      the token on which resolution fails; the empty pointer therefore costs 1;
    - JSON runtime size is 1 for `null` or a Boolean, `1 + character-count` for a string or number
      token, `1 + Σ child-size` for an array, and
      `1 + Σ(1 + key-character-count + member-value-size)` for an object;
    - `all`, `any`, and `not` add every child charge, including branches runtime evaluation could
      short-circuit; `evidence-present` adds `1 + id-character-count` for its lookup;
    - a resolved `fact` equality or ordered comparison adds the sizes of both compared values;
      `in` adds that same pair charge for every authored candidate, including candidates after a
      match; an unresolved `fact.path` stops after its charged pointer attempt;
    - `exists` and `every` add their charged `path` attempt and, only when it resolves to an array,
      `Σ preflight(where, element)` over the actual members. Thus nested ragged arrays are summed,
      never replaced by a rectangular product. Unresolved and non-array aggregate paths stop after
      the pointer charge;
    - `uniform` adds its `path` attempt, every member-relative `at` attempt (including failures), and
      `size(left) + size(right)` for every unordered pair of resolved `at` values. Algebraically the
      pair charge is `(resolved-count - 1) × Σ resolved-value-size`, computed without a quadratic
      preflight loop.

    This model deliberately charges comparison work that semantic short-circuiting may avoid. That
    makes dominant-first and dominant-last permutations consume the same budget. Sibling costs add
    by recursion, and the same formula covers aggregates below Boolean wrappers. The Python API’s
    `evaluation_work_limit` and the CLI’s `--evaluation-work-limit` configure the positive-integer
    limit; the default is 200,000. Alternatives considered were dynamic charging (rejected because
    element order could decide whether the limit trips), a rectangular nested-array product
    (rejected by the RFC), and charging only authored condition nodes (rejected because it prices
    composite equality and `uniform` as constants).

23. **The RFC 0008 prototype is a local evaluator opt-in, not a claim that its pack is valid under
    `0.1.0-draft`.**

    Text relied on: the clean-room brief requires an explicit opt-in defaulting off and says a pack
    using these operators remains invalid under JPS `0.1.0-draft`. RFC 0008 says the operators need
    a later exact `specVersion`; a `0.1.0-draft` reader rejects them structurally; and no
    evaluator-conformance claim is available.

    By default, encountering `exists`, `every`, or `uniform` is an explicit pack error.
    `enable_rfc0008=True` (or CLI `--enable-rfc0008`) locally admits the three draft shapes and
    applies the prototype semantics; it does not reinterpret the document as structurally
    conforming, register an extension, alter the Core disposition, or create a claim. The Core
    evaluator accepts both the historical `0.1.0-draft` inputs and the newly re-declared
    `0.2.0-draft` inputs as the alignment brief expressly requires. The alternatives were silently
    enabling the operators, treating them as an optional extension, or inventing a future
    `specVersion`; each would contradict the stated prototype boundary or claim a specification
    artifact the supplied texts do not define.

24. **The CLI uses an outer diagnostic envelope and places the exact §8.3 object in its
    `disposition` member.**

    Text relied on: Core §8.3 says, “Nothing else belongs in the disposition object” and permits
    diagnostics only “outside the disposition.” Core §8.4 says the error transport and wire format
    are not defined. The alignment brief says, “The CLI's JSON output carries this canonical form
    as the disposition member,” while the prior clean-room surface requires its
    experimental/no-claim labels on every output payload.

    A raw disposition would have nowhere to put those payload labels without violating §8.3; putting
    them inside the disposition is now expressly forbidden. I chose a success envelope with
    `disposition`, `experimental`, and `conformanceClaim`, and a distinct error envelope with
    `error`, the same two labels, and no `disposition`. The bytes of the nested disposition are the
    RFC 8785 bytes. This transport choice is not part of the portable disposition.

25. **The evaluation collection-size limit is 10,000 authored evaluation collection items.**

    Text relied on: Core §10 requires an evaluator to define collection-size and evaluation-work
    limits, but defines neither a portable size nor which collections share one counter. It says
    reaching the collection limit during evaluation is `resource-exhaustion`.

    I count the combined lengths of `evidenceRequirements`, `outcomes`, `rules`, and `exceptions`
    and cap that sum at 10,000. Sources and extension payloads are not consulted by ordinary
    evaluation; condition-tree expansion is bounded by the separate 200,000-unit work limit; and
    all JSON input is independently bounded by the 200,000-value/member carrier limit. Alternatives
    included one limit per array and counting every optional/non-evaluated collection. A shared
    evaluator-relevant counter is deterministic and makes the phase split explicit.

26. **A manifest `packs/<name>.json` reference is also tried as `<manifest-dir>/<name>.json` in
    this clean-room snapshot.**

    Text relied on: the alignment brief says the corpus “pack path resolves to the fixture in the
    same directory.” The supplied manifest spells its paths under `packs/`, but the one supplied
    pack fixture is beside the manifest and no `packs/` directory exists.

    The corpus test first honors the declared path, then tries only the named basename beside the
    manifest. It does not search elsewhere, synthesize a pack, or edit `reference/`. This resolves
    the thirteen rows using `data-request-intake-triage.json`. The other three declared fixture
    basenames are absent, so their seven rows remain explicitly blocked rather than being made to
    agree with reconstructed inputs.

27. **RFC 0016 opt-in admits one reserved name and supplies its capability.**

    Text relied on: the current brief requires “An opt-in, off by default” and leaves admission
    “yours to decide and to record.” RFC 0016, *What this needs from Core*, says both schema
    restrictions “would admit this one name” while “refusing every other reserved name.” Its
    *Declaration* requires the name in `metadata.requiredExtensions`.

    I chose `enable_rfc0016=True` and CLI `--enable-rfc0016`, independently of RFC 0008, following
    the existing opt-in spelling. The flag admits exactly `org.judgmentpack.outcome-values` on
    outcomes and in `metadata.requiredExtensions`, validates every declaration during pack
    preflight, and adds that one capability to the implementation's supported set. Supplying the
    name in `supported_extensions` alone cannot enable it. All other Core checks remain in force:
    bounded/unique-member JSON, closed object shapes, identifiers, formats, references, at least
    two outcomes, declaration of required capabilities, and values for every required extension.
    The reference schema is untouched. Other required capabilities still need explicit support.

    Alternatives were stripping extension content before validation, relaxing the entire reserved
    namespace, or requiring both the flag and a supported-extension argument. The first two weaken
    admission; the third permits an internally implemented capability to be accidentally omitted.
    The existing evaluator accepts `0.1.0-draft` and `0.2.0-draft`; I apply the local prototype to
    both rather than invent a version or silently narrow the historical API. The reference schema
    remains unchanged and no conformance claim is made. With the flag off, admission is unchanged.

28. **Unsupported-consumer RFC rows retain the current reserved-name pack error.**

    Text relied on: the brief requires that with opt-in off the package behave “as it does now,
    for every input.” RFC 0016, *Compatibility*, says “Under the current schema a pack using the
    reserved name is not structurally conforming” and conditions the unsupported-extension error
    on “Once the schema admits the name”. Its *Conformance*, third error bullet, asks an
    unsupported implementation to report `unsupported-required-extension` for a well-formed
    declaration, an empty declaration, and an unknown type.

    Those three cases cannot get that expected class with this prototype's flag off: current
    admission rejects the reserved name as `pack-not-conformant` before capability checks. With
    the flag on the implementation supports it and validates its declarations. I preserve the
    off-mode contract and explicitly test `pack-not-conformant` for all three variants in
    `test_error_unsupported_consumer_reserved_name_precedence_decision_28`. They are reported
    limitations, not silently omitted or claimed to match the RFC's expected error. The duplicate
    member variant of the same bullet does match: CLI JSON loading rejects it as
    `pack-not-conformant` with either flag setting, before malformed evidence is inspected.

    Alternatives were changing off-mode admission or introducing an additional schema-only mode
    to simulate an unsupported implementation. The former contradicts the brief and the latter
    adds a public mode with no requested use. I do not disagree with the RFC's expected class for
    a future reader whose schema already admits the name; that is not the current off-mode
    reader. No other listed RFC case is unmet or has a disputed expected answer.

29. **Extension placement means Core extension slots, not arbitrary JSON data.**

    Text relied on: RFC 0016, *Declaration*, says “As a member name of an `extensions` object,
    the name appears on an outcome and nowhere else” and refers to the places “The schema admits”.
    Core §4 distinguishes recognized Core members from “arbitrary JSON values inside an
    `extensions` object”; §9 says an optional extension “MUST NOT change Core semantics”.

    I check all schema-defined slots: root, decision, evidence requirement, source, rule,
    exception, escalation, metadata, and outcome. Only outcome admits this name. Objects in
    condition operands and inside another extension's payload are data, even if they contain
    members spelled `extensions` and `org.judgmentpack.outcome-values`. They neither declare
    values nor satisfy a required-extension entry. A recursive search for those spellings anywhere
    in the pack was the alternative; it would interpret literal data as Core structure and make
    otherwise inert payloads change admission. The new test file pins this scope explicitly.

30. **Unicode checks operate on decoded scalar values without repairing Python strings.**

    Text relied on: RFC 0016, *Declaration*, requires a string to be “a sequence of Unicode
    scalar values”; its positive document cases include a character outside the BMP “written
    as a surrogate pair”. *Resolution* says “Nothing is coerced, trimmed or normalized”.

    JSON text containing an escaped high/low surrogate pair is decoded by the existing loader
    into one scalar and accepted. A Python API string containing surrogate code points is
    rejected as a constant, or fails resolution as a selected fact, even if it contains two
    adjacent code points that could be repaired into a pair. The alternative was to join those
    Python code points or replace lone surrogates; that changes the caller's value. Existing
    general JSON admission remains unchanged: unselected strings with lone surrogates do not
    become input errors merely because this prototype is enabled. Only declared `string`
    constants and selected `string` values receive the scalar check. The pointer syntax remains
    Core's; a pointer is not itself an outcome string value. Value names use whole-string ASCII
    matching, including capitals after the first letter; decimals reuse Core's whole-string
    grammar. Empty strings, control characters, and non-normalized Unicode scalar sequences
    remain valid and are copied exactly. The canonicalizer gains Boolean serialization while
    continuing to reject numbers and nulls; its existing scalar checks and UTF-16 member ordering
    apply to the new member too.

31. **Outcome values share the existing collection and evaluation-work limits.**

    Text relied on: RFC 0016, *Resources*, says “A declaration or a selected value past a
    documented limit is handled as §10 handles any other.” Its open question 8 leaves bounds
    undefined. Core §10 requires documented collection-size and evaluation-work limits and
    distinguishes preflight admission limits from evaluation `resource-exhaustion`.

    I extend decision 25's shared 10,000-item count by the number of value sources declared
    across all outcomes. As before, this count is checked after input preflight and before
    applicability; exceeding it is an evaluation-phase `resource-exhaustion`. Only the produced
    outcome incurs resolution work. Each declared value costs `1 + len(value-name)` units; a
    `fromFact` additionally costs the pointer attempt defined in decision 22 (including a failing
    token); each resolved selection or constant costs one type inspection, plus its character
    count if it is a string. Rejected numbers, nulls, arrays, and objects cost one inspection and
    their contents are not traversed. All lengths count decoded Python string characters.

    The entire selected declaration is measured and charged once against the same budget as the
    conditions, before any type failure can return `unknown`. This makes declaration order
    irrelevant even when one source is missing. No value-resolution work is charged for a
    non-outcome or an outcome without a declaration. Alternatives were no additional accounting,
    a separate budget, or short-circuit charging; these respectively leave the new work unbounded,
    conceal its combined cost, or make authoring order affect exhaustion. Existing JSON string,
    item, depth, number-token, and document-byte limits still apply at admission, with existing
    preflight error classes. No new dependency or output truncation is introduced.

32. **Examples use minimal Core packs completed from the RFC's stated behavior.**

    Text relied on: RFC 0016's *Examples* give an outcomes fragment for tiers, describe a pack
    “whose one rule produces `approve-refund`” for pass-through, and say the calculated quantity
    “is supplied as the fact `/refund/amount`”. Core §4 requires at least two outcomes and one
    rule. The RFC supplies no complete pack for these examples.

    I complete the fragments with the existing local base fixture's metadata and required Core
    fields. The pass-through example has the exact stated condition and declaration, no
    escalation, and additional unused outcomes to meet Core's minimum. For tiers, the problem
    statement supplies thresholds 720 and 650: decimal-string score facts select high at >=720,
    standard at >=650 and <720, and decline by fallback. The alternative of only testing a
    literal rule would not exercise those described tiers.

    For the calculated example, a <=500 rule approves the already supplied amount, and a >500
    exception requests escalation to a human-role Supervisor. The alternative of an outcome
    named `supervisor` would label a category without making the described handoff request.
    Calculation, origin verification, tool execution, and external action are absent. Values
    themselves impose no range bound: the tests also copy unbounded positive and negative
    decimal strings when no rule limits them. These are reconstructed examples, not copies of
    any unavailable pack or other implementation.

33. **CLI byte comparison applies to the disposition inside the existing envelope.**

    Text relied on: the brief says the command line “prints the disposition as it does now” and
    “Keep the markers the package already writes.” RFC 0016 extends §8.3's byte-identity
    requirement to `value` and supplies canonical bytes for the pass-through disposition.

    I retain decision 24's outer `experimental: true` / `conformanceClaim: "none"` envelope
    and its final newline. The embedded disposition bytes exactly match the RFC sample. A raw
    sample as the entire stdout was the alternative, but would remove the required markers and
    change the existing CLI transport. The new CLI test compares the entire stdout byte string,
    built around the RFC's literal sample, so both requirements are exercised together.

## Appendix comparison

After implementing the semantics above, all ten table rows (the nine logical instances, including
both 7a and 7b) produced the appendix’s stated disposition. No implementation reading disagreed
with an appendix expected disposition.
