#!/usr/bin/env python3
"""Writes rfc0016_cases.json: the cases the Conformance section of draft RFC 0016
(outcome values) lists, one row each, with the answer the RFC's text gives.

Every row carries its own pack, because the rows differ in the declaration under
test. A pack or a facts document is carried as JSON text, not as a value, so
that a row can hold what a value cannot: a member given twice, an escape, an
order of members. The expected answer is written from the RFC, never read off
an implementation.

Usage: make_rfc0016_cases.py > rfc0016_cases.json
"""
import json
import sys

NAME = "org.judgmentpack.outcome-values"
BS = chr(92)


def text(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def declaring(outcome_id, declaration_text):
    return '{"id": %s, "label": "An outcome", "extensions": {"%s": %s}}' % (
        json.dumps(outcome_id), NAME, declaration_text)


def plain(outcome_id):
    return '{"id": %s, "label": "An outcome"}' % json.dumps(outcome_id)


RULE = ('{"id": "the-rule", "description": "The one rule.", "when": {"op": "fact", "path": "/go", '
        '"operator": "equals", "value": true}, "outcome": %s, "onUnknown": "ignore"}')


def pack(outcomes, rules=None, more="", required=None, name="row"):
    """One minimal pack. `required` is the text of the items of
    metadata.requiredExtensions; None lists the extension once and "-" leaves
    metadata out."""
    if rules is None:
        rules = "[" + RULE % '"approve"' + "]"
    if required is None:
        metadata = '"metadata": {"requiredExtensions": ["%s"]},' % NAME
    elif required == "-":
        metadata = ""
    else:
        metadata = '"metadata": {"requiredExtensions": [%s]},' % required
    return ('{"specVersion": "0.2.0-draft", '
            '"id": "https://example.invalid/judgment-packs/rfc0016-%s", '
            '"version": "0.1.0", '
            '"title": "Synthetic draft RFC 0016 row", '
            '"description": "Invented content for specification testing; it authorizes nothing.", '
            '"decision": {"intent": "Exercise one draft RFC 0016 declaration against one facts document.", '
            '"question": "Is the outcome produced, and with which values?"}, '
            '%s %s "outcomes": %s, "rules": %s}') % (name, metadata, more, outcomes, rules)


def two(declaration_text):
    return "[" + declaring("approve", declaration_text) + ", " + plain("decline") + "]"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def outcome(outcome_id, value=None):
    disposition = {"handoff": {"state": "none"}, "kind": "outcome", "outcomeId": outcome_id, "reasons": []}
    if value is not None:
        disposition["value"] = value
    return {"disposition": canonical(disposition)}


UNRESOLVED = {"disposition": '{"handoff":{"state":"none"},"kind":"unresolved","reasons":["unknown"]}'}
REQUESTED = {"disposition": '{"handoff":{"state":"requested","triggeredBy":["unknown"]},"kind":"unresolved","reasons":["unknown"]}'}
NOT_CONFORMANT = {"errorClass": "pack-not-conformant"}
UNSUPPORTED = {"errorClass": "unsupported-required-extension"}

EXAMPLE = ('{"refundAmount": {"type": "decimal", "fromFact": "/proposed/refundAmount"}, '
           '"currency": {"type": "string", "constant": "CAD"}}')
NEVER = "[" + RULE % '"decline"' + "]"
FORCING = ('"exceptions": [{"id": "the-exception", "description": "Forces the outcome.", "when": {"op": "fact", '
           '"path": "/force", "operator": "equals", "value": true}, "effect": "force-outcome", '
           '"outcome": "approve", "onUnknown": "ignore"}],')
FALLBACK = '"fallbackOutcome": "approve",'
ESCALATE = '"escalation": {"triggers": ["unknown"], "target": {"kind": "queue", "name": "refund-review"}},'
ESCALATE_OTHER = '"escalation": {"triggers": ["conflict", "no-match"], "target": {"kind": "queue", "name": "refund-review"}},'

rows = []


def row(case_id, origin, pack_text, facts_text, expected, evidence=None, opt_in=True, note=None):
    assert case_id not in [r["id"] for r in rows], case_id
    rows.append({"id": case_id, "origin": origin, "optIn": opt_in, "pack": pack_text, "facts": facts_text,
                 "evidenceAvailability": evidence, "expected": expected, "note": note})


GO = '{"go": true}'

# --- Document cases, positive -------------------------------------------------
D = "Conformance, document cases, positive: "
row("document-constant-string", D + "a constant of type string",
    pack(two('{"currency": {"type": "string", "constant": "CAD"}}')), GO, outcome("approve", {"currency": "CAD"}))
row("document-constant-decimal", D + "a constant of type decimal",
    pack(two('{"creditLimit": {"type": "decimal", "constant": "10000"}}')), GO, outcome("approve", {"creditLimit": "10000"}))
row("document-constant-boolean", D + "a constant of type boolean",
    pack(two('{"needsReceipt": {"type": "boolean", "constant": true}}')), GO, outcome("approve", {"needsReceipt": True}))
row("document-from-fact", D + "one with fromFact",
    pack(two('{"refundAmount": {"type": "decimal", "fromFact": "/amount"}}')), '{"go": true, "amount": "149.50"}',
    outcome("approve", {"refundAmount": "149.50"}))
row("document-mixed", D + "one mixing both",
    pack(two(EXAMPLE)), '{"go": true, "proposed": {"refundAmount": "149.50"}}',
    outcome("approve", {"currency": "CAD", "refundAmount": "149.50"}))
row("document-constant-surrogate-pair", D + "a string constant outside the Basic Multilingual Plane, written as a surrogate pair",
    pack(two('{"mark": {"type": "string", "constant": "' + BS + "ud83d" + BS + 'ude00"}}')), GO,
    outcome("approve", {"mark": chr(0x1F600)}),
    note="The pack holds the escape and the expected disposition the character, as RFC 8785 writes it.")

# --- Document cases, negative -------------------------------------------------
D = "Conformance, document cases, negative: "
for case_id, what, declaration in [
    ("both-sources", "a value source with both constant and fromFact", '{"v": {"type": "string", "constant": "a", "fromFact": "/a"}}'),
    ("no-source", "a value source with neither", '{"v": {"type": "string"}}'),
    ("unknown-type", "a value source with an unknown type", '{"v": {"type": "number", "constant": "1"}}'),
    ("undefined-member", "a value source with a member this section does not define", '{"v": {"type": "string", "constant": "a", "unit": "CAD"}}'),
    ("decimal-constant-fails-grammar", "a decimal constant that fails §2.2", '{"v": {"type": "decimal", "constant": "1e3"}}'),
    ("boolean-constant-as-string", "a boolean constant given as the string \"true\"", '{"v": {"type": "boolean", "constant": "true"}}'),
    ("string-constant-unpaired-surrogate", "a string constant holding an unpaired surrogate", '{"v": {"type": "string", "constant": "' + BS + 'ud800"}}'),
    ("empty-declaration", "an empty declaration", "{}"),
    ("name-begins-with-capital", "a value name that begins with a capital", '{"Amount": {"type": "string", "constant": "a"}}'),
    ("name-begins-with-digit", "a value name that begins with a digit", '{"1st": {"type": "string", "constant": "a"}}'),
    ("name-ends-in-line-feed", "a value name that ends in a line feed", '{"amount' + BS + 'n": {"type": "string", "constant": "a"}}'),
]:
    row("document-" + case_id, D + what, pack(two(declaration)), GO, NOT_CONFORMANT)
row("document-not-listed-as-required", D + "a declaration in a pack that does not list the extension as required",
    pack(two(EXAMPLE), required="-"), '{"go": true, "proposed": {"refundAmount": "149.50"}}', NOT_CONFORMANT)
ALSO = '"extensions": {"%s": %s}' % (NAME, EXAMPLE)
row("document-name-on-root-alone", D + "the extension name on the root object alone",
    pack("[" + plain("approve") + ", " + plain("decline") + "]", more=ALSO + ","), GO, NOT_CONFORMANT)
row("document-name-on-outcome-and-rule", D + "the name on an outcome and on a rule as well",
    pack(two(EXAMPLE), rules="[" + (RULE % '"approve"')[:-1] + ", " + ALSO + "}]"),
    '{"go": true, "proposed": {"refundAmount": "149.50"}}', NOT_CONFORMANT)

# --- Evaluation rows, positive and negative, by each way §8 produces an outcome
WAYS = [
    ("true-rule", "a true rule", None, "", '{"go": true, "amount": "149.50"}'),
    ("forced-outcome", "a forced outcome", NEVER, FORCING, '{"go": true, "force": true, "amount": "149.50"}'),
    ("fallback", "fallbackOutcome", NEVER, FALLBACK, '{"go": false, "amount": "149.50"}'),
]
for way, words, rules, more, facts in WAYS:
    row("evaluation-constant-by-" + way, "Conformance, evaluation rows, positive: a constant carried on an outcome produced by " + words,
        pack(two('{"creditLimit": {"type": "decimal", "constant": "5000"}}'), rules=rules, more=more), facts,
        outcome("approve", {"creditLimit": "5000"}))
for declared, fact, carried in [("string", '"CAD"', "CAD"), ("decimal", '"149.50"', "149.50"), ("boolean", "true", True)]:
    row("evaluation-from-fact-" + declared, "Conformance, evaluation rows, positive: a fromFact that resolves, of type " + declared,
        pack(two('{"v": {"type": "%s", "fromFact": "/selected"}}' % declared)), '{"go": true, "selected": %s}' % fact,
        outcome("approve", {"v": carried}))
for way, words, rules, more, facts in WAYS:
    row("evaluation-unresolved-by-" + way,
        "Conformance, evaluation rows, negative: a fromFact whose pointer does not resolve, on an outcome produced by " + words,
        pack(two('{"refundAmount": {"type": "decimal", "fromFact": "/missing"}}'), rules=rules, more=more), facts, UNRESOLVED)
row("evaluation-two-values-one-unresolved",
    "Conformance, evaluation rows, negative: two values of which one does not resolve, where the disposition carries no value member at all",
    pack(two(EXAMPLE)), GO, UNRESOLVED)
row("evaluation-not-applicable", "Conformance, evaluation rows, negative: a not-applicable result, carrying no value",
    pack(two(EXAMPLE), more='"applicability": {"op": "fact", "path": "/inScope", "operator": "equals", "value": true},'),
    '{"go": true, "inScope": false, "proposed": {"refundAmount": "1"}}',
    {"disposition": '{"handoff":{"state":"none"},"kind":"not-applicable","reasons":["not-applicable"]}'})
row("evaluation-unresolved-result", "Conformance, evaluation rows, negative: an unresolved result, carrying no value",
    pack(two(EXAMPLE)), '{"go": false, "proposed": {"refundAmount": "1"}}',
    {"disposition": '{"handoff":{"state":"none"},"kind":"unresolved","reasons":["no-match"]}'})

# --- Handoff -------------------------------------------------------------------
H = "Conformance, evaluation rows, handoff: a value that does not resolve in a pack "
MISSING = two('{"refundAmount": {"type": "decimal", "fromFact": "/missing"}}')
row("handoff-triggers-name-unknown", H + "whose escalation.triggers name unknown", pack(MISSING, more=ESCALATE), GO, REQUESTED)
row("handoff-triggers-do-not-name-unknown", H + "whose triggers do not name it", pack(MISSING, more=ESCALATE_OTHER), GO, UNRESOLVED)
row("handoff-no-escalation-object", H + "with no escalation object", pack(MISSING), GO, UNRESOLVED)

# --- Boundary --------------------------------------------------------------------
B = "Conformance, evaluation rows, boundary: "
row("boundary-trailing-zeroes", B + "a decimal with trailing zeroes copied unchanged",
    pack(two('{"v": {"type": "decimal", "fromFact": "/selected"}}')), '{"go": true, "selected": "0.10"}', outcome("approve", {"v": "0.10"}))
row("boundary-empty-string", B + "the empty string as a string value",
    pack(two('{"v": {"type": "string", "fromFact": "/selected"}}')), '{"go": true, "selected": ""}', outcome("approve", {"v": ""}))
row("boundary-false", B + "the Boolean false",
    pack(two('{"v": {"type": "boolean", "fromFact": "/selected"}}')), '{"go": true, "selected": false}', outcome("approve", {"v": False}))
ALWAYS = ('{"id": "the-other", "description": "Another rule.", "when": {"op": "literal", "value": true}, '
          '"outcome": "approve", "onUnknown": "ignore"}')
BOTH = '{"go": true, "proposed": {"refundAmount": "149.50"}}'
row("boundary-two-true-rules", B + "two true rules naming the same outcome, which carries its values once",
    pack(two(EXAMPLE), rules="[" + RULE % '"approve"' + ", " + ALWAYS + "]"), BOTH,
    outcome("approve", {"currency": "CAD", "refundAmount": "149.50"}))
row("boundary-members-in-another-order", B + "the same declaration with its members authored in another order",
    pack(two('{"currency": {"constant": "CAD", "type": "string"}, "refundAmount": {"fromFact": "/proposed/refundAmount", "type": "decimal"}}')),
    BOTH, outcome("approve", {"currency": "CAD", "refundAmount": "149.50"}),
    note="The expected bytes are those of document-mixed, to the byte.")

# --- Adversarial -------------------------------------------------------------------
A = "Conformance, evaluation rows, adversarial: "
DEC = pack(two('{"v": {"type": "decimal", "fromFact": "/selected"}}'))
STR = pack(two('{"v": {"type": "string", "fromFact": "/selected"}}'))
for case_id, what, fact in [
    ("decimal-fact-json-number", "where decimal is declared, a fact given as a JSON number", "149.5"),
    ("decimal-fact-null", "where decimal is declared, a fact given as null", "null"),
    ("decimal-fact-object", "where decimal is declared, a fact given as an object", '{"amount": "1"}'),
    ("decimal-fact-whitespace", "where decimal is declared, a fact given as a string with surrounding whitespace", '" 149.50 "'),
]:
    row("adversarial-" + case_id, A + what, DEC, '{"go": true, "selected": %s}' % fact, UNRESOLVED)
row("adversarial-string-fact-whitespace", A + "where string is declared, a fact string with surrounding whitespace, which resolves and is copied unchanged",
    STR, '{"go": true, "selected": "  CAD \\t"}', outcome("approve", {"v": "  CAD \t"}))
row("adversarial-string-fact-unpaired-surrogate", A + "where string is declared, a fact string holding an unpaired surrogate, which does not resolve",
    STR, '{"go": true, "selected": "' + BS + 'udc00"}', UNRESOLVED,
    note="An implementation whose carrier refuses the facts document answers malformed-input and never reaches resolution.")
row("adversarial-array-out-of-range", A + "a pointer that traverses an array out of range",
    pack(two('{"v": {"type": "decimal", "fromFact": "/lines/2/amount"}}')),
    '{"go": true, "lines": [{"amount": "1"}, {"amount": "2"}]}', UNRESOLVED)
row("adversarial-another-outcome-unresolvable",
    A + "a produced outcome whose own values resolve while another outcome declares a fromFact the facts cannot supply",
    pack("[" + declaring("approve", EXAMPLE) + ", " + declaring("decline", '{"reason": {"type": "string", "fromFact": "/missing"}}') + "]"),
    BOTH, outcome("approve", {"currency": "CAD", "refundAmount": "149.50"}))

# --- The RFC's own examples -----------------------------------------------------------
PASS_THROUGH = pack("[" + declaring("approve-refund", EXAMPLE) + ", " + plain("decline") + "]",
                    rules='[{"id": "good-standing", "description": "A customer in good standing is refunded.", "when": {"op": "fact", '
                          '"path": "/customer/goodStanding", "operator": "equals", "value": true}, "outcome": "approve-refund", '
                          '"onUnknown": "ignore"}]', required=None)
row("example-pass-through", "Examples, pass-through: the facts supply the amount",
    PASS_THROUGH, '{"customer": {"goodStanding": true}, "proposed": {"refundAmount": "149.50"}}',
    {"disposition": '{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"approve-refund","reasons":[],"value":{"currency":"CAD","refundAmount":"149.50"}}'},
    note="The expected bytes are the ones the RFC prints under The disposition.")
row("example-pass-through-amount-absent", "Examples, pass-through: /proposed/refundAmount absent",
    PASS_THROUGH, '{"customer": {"goodStanding": true}}', UNRESOLVED)
row("example-pass-through-amount-a-number", "Examples, pass-through: /proposed/refundAmount given as the JSON number 149.5",
    PASS_THROUGH, '{"customer": {"goodStanding": true}, "proposed": {"refundAmount": 149.5}}', UNRESOLVED)
TIERS = ("[" + declaring("limit-high", '{"creditLimit": {"type": "decimal", "constant": "10000"}}') + ", "
         + declaring("limit-standard", '{"creditLimit": {"type": "decimal", "constant": "5000"}}') + ", " + plain("decline") + "]")
TIER_RULES = ('[{"id": "high", "description": "A score of 720 or more.", "when": {"op": "fact", "path": "/score", '
              '"operator": "greater-than-or-equal", "value": "720"}, "outcome": "limit-high", "onUnknown": "escalate"}, '
              '{"id": "standard", "description": "A score of 650 to 719.", "when": {"op": "all", "conditions": ['
              '{"op": "fact", "path": "/score", "operator": "greater-than-or-equal", "value": "650"}, '
              '{"op": "fact", "path": "/score", "operator": "less-than", "value": "720"}]}, "outcome": "limit-standard", '
              '"onUnknown": "escalate"}]')
row("example-tiers-standard", "Examples, tiers: the rules produce limit-standard",
    pack(TIERS, rules=TIER_RULES, more='"fallbackOutcome": "decline",'), '{"score": "700"}', outcome("limit-standard", {"creditLimit": "5000"}))
row("example-tiers-decline", "Examples, tiers: the rules produce decline, which carries no value member",
    pack(TIERS, rules=TIER_RULES, more='"fallbackOutcome": "decline",'), '{"score": "600"}', outcome("decline"))

# --- Error rows ---------------------------------------------------------------------------
X = "Conformance, error rows: "
MALFORMED = "[" + plain("approve") + ", " + declaring("decline", '{"v": {"type": "decimal", "constant": "1e3"}}') + "]"
row("error-malformed-declaration-applicability-false",
    X + "a malformed declaration on an outcome the evaluation would not have produced, in a pack whose applicability is false",
    pack(MALFORMED, more='"applicability": {"op": "literal", "value": false},'), GO, NOT_CONFORMANT)
row("error-malformed-declaration-and-undeclared-evidence",
    X + "a malformed declaration together with an evidence-availability document carrying an undeclared member name",
    pack(MALFORMED), GO, NOT_CONFORMANT, evidence='{"undeclared": "present"}')
U = X + "for an implementation that does not support the extension, "
row("error-unsupported-well-formed", U + "a well-formed pack that requires it",
    pack(two(EXAMPLE)), BOTH, UNSUPPORTED, opt_in=False,
    note="The row needs a schema that admits the name. Under the schema of 0.2.0-draft the pack is not structurally conforming, as the RFC's Compatibility section says.")
row("error-unsupported-empty-declaration", U + "the same class where its declaration is empty",
    pack(two("{}")), GO, UNSUPPORTED, opt_in=False, note="As error-unsupported-well-formed.")
row("error-unsupported-unknown-type", U + "the same class where its declaration has an unknown type",
    pack(two('{"v": {"type": "number", "constant": "1"}}')), GO, UNSUPPORTED, opt_in=False, note="As error-unsupported-well-formed.")
DUPLICATE = '{"v": {"type": "string", "constant": "a"}, "v": {"type": "string", "constant": "b"}}'
row("error-duplicate-member-unsupported", X + "a duplicate member name inside the declaration, for an implementation that does not support the extension",
    pack(two(DUPLICATE)), GO, NOT_CONFORMANT, opt_in=False)
row("error-duplicate-member-supported", X + "a duplicate member name inside the declaration, for an implementation that supports it",
    pack(two(DUPLICATE)), GO, NOT_CONFORMANT)

# --- Rows known not to match the RFC's answer, each with its reason ---------------------
SCHEMA = ("The row needs a schema that admits the name. Without the opt-in both implementations hold "
          "a pack to the schema of 0.2.0-draft, under which the name is reserved and the pack is not "
          "structurally conforming. The RFC's Compatibility section says as much. Recorded by the Go "
          "runtime in ADR-0039, finding 2, and by the Python evaluator in DECISIONS.md, entry 28.")
known = {
    "adversarial-string-fact-unpaired-surrogate": {
        "verdict": "DIVERGENT",
        "reason": ("The Go runtime's carrier refuses any input that holds an unpaired surrogate escape, "
                   "so the facts document is a malformed input before a value is selected (ADR-0039, "
                   "finding 1). The Python evaluator admits the document and the value does not "
                   "resolve, which is the RFC's answer (DECISIONS.md, entry 30). Core §2.1 does not "
                   "say which carrier is right."),
    },
    "error-unsupported-well-formed": {"verdict": "AGREE-OFF-RFC", "reason": SCHEMA},
    "error-unsupported-empty-declaration": {"verdict": "AGREE-OFF-RFC", "reason": SCHEMA},
    "error-unsupported-unknown-type": {"verdict": "AGREE-OFF-RFC", "reason": SCHEMA},
}
assert set(known) <= {r["id"] for r in rows}

json.dump({"rfc": "0016", "specCommit": "7c7abbb3124f1b58da21b1d2f9744b1124d4cb89", "known": known,
           "cases": rows}, sys.stdout, indent=1, ensure_ascii=True)
sys.stdout.write("\n")
