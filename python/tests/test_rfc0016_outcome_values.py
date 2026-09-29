"""RFC 0016 Examples and Conformance cases, plus prototype boundary checks.

Case IDs track the RFC's prose lists. The unsupported-consumer error rows
intentionally assert the preserved Core admission error; see decision 28.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from jps_evaluator import (
    EvaluationInputError,
    PackNotConformantError,
    ResourceLimitError,
    UnsupportedExtensionError,
    canonicalize_disposition,
    evaluate,
    strict_loads,
)
from tests.pack_fixtures import base_pack


EXTENSION = "org.judgmentpack.outcome-values"
PYTHON_ROOT = Path(__file__).parents[1]
PASS_THROUGH_BYTES = (
    b'{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"approve-refund",'
    b'"reasons":[],"value":{"currency":"CAD","refundAmount":"149.50"}}'
)
UNKNOWN_BYTES = b'{"handoff":{"state":"none"},"kind":"unresolved","reasons":["unknown"]}'


def value_pack(declaration):
    pack = base_pack()
    pack["specVersion"] = "0.2.0-draft"
    pack["metadata"] = {"requiredExtensions": [EXTENSION]}
    pack["outcomes"][0]["extensions"] = {EXTENSION: deepcopy(declaration)}
    pack["rules"][0]["when"] = {"op": "literal", "value": True}
    return pack


def fact_condition(path, operator, value):
    return {"op": "fact", "path": path, "operator": operator, "value": value}


def outcome(values=None, outcome_id="outcome-a"):
    result = {
        "kind": "outcome", "outcomeId": outcome_id,
        "reasons": [], "handoff": {"state": "none"},
    }
    if values is not None:
        result["value"] = values
    return result


def select_route(pack, route):
    pack["fallbackOutcome"] = "outcome-b"
    if route == "forced-outcome":
        pack["exceptions"] = [{
            "id": "force-a", "description": "Force the declared outcome.",
            "when": {"op": "literal", "value": True},
            "effect": "force-outcome", "outcome": "outcome-a", "onUnknown": "ignore",
        }]
        # A forced outcome must still bypass this otherwise blocking rule.
        pack["rules"][0]["when"] = fact_condition("/missing", "equals", True)
        pack["rules"][0]["onUnknown"] = "escalate"
    elif route == "fallbackOutcome":
        pack["rules"][0]["when"] = {"op": "literal", "value": False}
        pack["fallbackOutcome"] = "outcome-a"


def pass_through_pack():
    pack = value_pack({
        "refundAmount": {"type": "decimal", "fromFact": "/proposed/refundAmount"},
        "currency": {"type": "string", "constant": "CAD"},
    })
    pack["outcomes"][0]["id"] = "approve-refund"
    pack["outcomes"][0]["label"] = "Approve the proposed refund"
    pack["rules"][0]["outcome"] = "approve-refund"
    pack["rules"][0]["when"] = fact_condition("/customer/goodStanding", "equals", True)
    return pack


def run_cli(tmp_path, pack, facts="{}", *, enabled=True, evidence=None):
    pack_path = tmp_path / "pack.json"
    facts_path = tmp_path / "facts.json"
    pack_path.write_text(pack if isinstance(pack, str) else json.dumps(pack), encoding="utf-8")
    facts_path.write_text(facts, encoding="utf-8")
    command = [sys.executable, "-m", "jps_evaluator", "--pack", str(pack_path),
               "--facts", str(facts_path)]
    if enabled:
        command.append("--enable-rfc0016")
    if evidence is not None:
        evidence_path = tmp_path / "evidence.json"
        evidence_path.write_text(evidence, encoding="utf-8")
        command.extend(["--evidence", str(evidence_path)])
    return subprocess.run(command, cwd=PYTHON_ROOT, capture_output=True, check=False)


def assert_pack_error(pack, **kwargs):
    with pytest.raises(PackNotConformantError) as error:
        evaluate(pack, {}, enable_rfc0016=True, **kwargs)
    assert error.value.error_class == "pack-not-conformant"
    assert error.value.phase == "preflight"


# Examples: Tiers, Pass-through, and A calculated quantity.
@pytest.mark.parametrize("score,chosen,values", [
    ("720", "limit-high", {"creditLimit": "10000"}),
    ("650", "limit-standard", {"creditLimit": "5000"}),
    ("719", "limit-standard", {"creditLimit": "5000"}),
    ("649", "decline", None),
], ids=["high", "standard", "standard-upper-bound", "decline-no-value"])
def test_example_tiers(score, chosen, values):
    pack = value_pack({"creditLimit": {"type": "decimal", "constant": "10000"}})
    pack["outcomes"] = [
        {"id": "limit-high", "label": "Approve, high limit", "extensions": {
            EXTENSION: {"creditLimit": {"type": "decimal", "constant": "10000"}}}},
        {"id": "limit-standard", "label": "Approve, standard limit", "extensions": {
            EXTENSION: {"creditLimit": {"type": "decimal", "constant": "5000"}}}},
        {"id": "decline", "label": "Decline"},
    ]
    pack["rules"][0].update(outcome="limit-high", when=fact_condition(
        "/score", "greater-than-or-equal", "720"))
    standard = deepcopy(pack["rules"][0])
    standard.update(id="standard", outcome="limit-standard", when={
        "op": "all", "conditions": [
            fact_condition("/score", "greater-than-or-equal", "650"),
            fact_condition("/score", "less-than", "720"),
        ],
    })
    pack["rules"].append(standard)
    pack["fallbackOutcome"] = "decline"
    assert evaluate(pack, {"score": score}, enable_rfc0016=True) == outcome(values, chosen)


def test_example_pass_through_disposition_bytes():
    facts = {"customer": {"goodStanding": True}, "proposed": {"refundAmount": "149.50"}}
    assert canonicalize_disposition(evaluate(
        pass_through_pack(), facts, enable_rfc0016=True
    )) == PASS_THROUGH_BYTES


@pytest.mark.parametrize("proposed", [{}, {"refundAmount": 149.5}], ids=["absent", "json-number"])
def test_example_pass_through_unresolved_and_core_contrast_bytes(proposed):
    facts = {"customer": {"goodStanding": True}, "proposed": proposed}
    pack = pass_through_pack()
    assert canonicalize_disposition(evaluate(pack, facts, enable_rfc0016=True)) == UNKNOWN_BYTES
    del pack["outcomes"][0]["extensions"]
    del pack["metadata"]["requiredExtensions"]
    assert evaluate(pack, facts) == outcome(outcome_id="approve-refund")


@pytest.mark.parametrize("amount,supervisor", [("125.00", False), ("500", False), ("500.01", True)],
                         ids=["prepared-fact", "threshold", "above-threshold"])
def test_example_calculated_quantity_is_prepared_before_evaluation(amount, supervisor):
    pack = value_pack({"refundAmount": {"type": "decimal", "fromFact": "/refund/amount"}})
    pack["rules"][0]["when"] = fact_condition("/refund/amount", "less-than-or-equal", "500")
    pack["exceptions"] = [{
        "id": "supervisor", "description": "Request supervision above 500.",
        "when": fact_condition("/refund/amount", "greater-than", "500"),
        "effect": "escalate", "onUnknown": "escalate",
    }]
    pack["escalation"] = {"triggers": ["unknown"],
                          "target": {"kind": "human-role", "name": "Supervisor"}}
    result = evaluate(pack, {"refund": {"amount": amount}}, enable_rfc0016=True)
    if supervisor:
        assert result == {"kind": "unresolved", "reasons": ["exception-escalation"],
                          "handoff": {"state": "requested", "triggeredBy": ["exception-escalation"]}}
    else:
        assert result == outcome({"refundAmount": amount})


# Conformance: document-level positive cases.
@pytest.mark.parametrize("declaration,facts,expected", [
    ({"text": {"type": "string", "constant": "CAD"},
      "amount": {"type": "decimal", "constant": "10000"},
      "flag": {"type": "boolean", "constant": True}},
     {}, {"text": "CAD", "amount": "10000", "flag": True}),
    ({"text": {"type": "string", "constant": "CAD"}}, {}, {"text": "CAD"}),
    ({"amount": {"type": "decimal", "constant": "10000"}}, {}, {"amount": "10000"}),
    ({"flag": {"type": "boolean", "constant": True}}, {}, {"flag": True}),
    ({"amount": {"type": "decimal", "fromFact": "/amount"}}, {"amount": "2.50"}, {"amount": "2.50"}),
    ({"text": {"type": "string", "constant": "CAD"},
      "amount": {"type": "decimal", "fromFact": "/amount"}},
     {"amount": "2.50"}, {"text": "CAD", "amount": "2.50"}),
    ({"text": {"type": "string", "constant": strict_loads(r'"\ud83d\ude80"')}}, {}, {"text": "🚀"}),
], ids=["constants-of-each-type", "constant-string", "constant-decimal", "constant-boolean",
        "fromFact", "mixed", "surrogate-pair"])
def test_document_positive(declaration, facts, expected):
    # json.dumps writes non-BMP characters as surrogate-pair escapes.
    pack = strict_loads(json.dumps(value_pack(declaration)))
    result = evaluate(pack, facts, enable_rfc0016=True)
    assert result == outcome(expected)
    assert canonicalize_disposition(result) == canonicalize_disposition(outcome(expected))


# Conformance: document-level negative cases; extra rows exercise the same grammar.
@pytest.mark.parametrize("declaration", [
    pytest.param({"a": {"type": "decimal", "constant": "1", "fromFact": "/a"}}, id="both-sources"),
    pytest.param({"a": {"type": "decimal"}}, id="neither-source"),
    pytest.param({"a": {"type": "number", "constant": "1"}}, id="unknown-type"),
    pytest.param({"a": {"type": "decimal", "constant": "1", "tool": "pay"}}, id="undefined-source-member"),
    pytest.param({"a": {"type": "decimal", "constant": "1e2"}}, id="invalid-decimal-constant"),
    pytest.param({"a": {"type": "boolean", "constant": "true"}}, id="boolean-string-constant"),
    pytest.param({"a": {"type": "string", "constant": "\ud800"}}, id="unpaired-surrogate-constant"),
    pytest.param({}, id="empty-declaration"),
    pytest.param({"Amount": {"type": "decimal", "constant": "1"}}, id="capital-initial-name"),
    pytest.param({"1amount": {"type": "decimal", "constant": "1"}}, id="digit-initial-name"),
    pytest.param({"amount\n": {"type": "decimal", "constant": "1"}}, id="line-feed-ending-name"),
    pytest.param({"a": {"constant": "1"}}, id="missing-type"),
    pytest.param({"a": {"type": [], "constant": "1"}}, id="non-string-type"),
    pytest.param({"a": {"type": "decimal", "constant": 1}}, id="numeric-constant"),
    pytest.param({"a": {"type": "boolean", "constant": 1}}, id="boolean-numeric-constant"),
    pytest.param({"a": {"type": "string", "constant": None}}, id="null-constant"),
    pytest.param({"a": {"type": "string", "fromFact": "a"}}, id="relative-pointer"),
    pytest.param({"a": {"type": "string", "fromFact": "/~2"}}, id="invalid-pointer-escape"),
    pytest.param({"a": {"type": "string", "fromFact": 0}}, id="non-string-pointer"),
    pytest.param({"a": []}, id="non-object-source"),
    pytest.param([], id="non-object-declaration"),
    pytest.param({"": {"type": "string", "constant": ""}}, id="empty-name"),
    pytest.param({"amóunt": {"type": "string", "constant": ""}}, id="non-ascii-name"),
    pytest.param({"credit-limit": {"type": "string", "constant": ""}}, id="hyphen-name"),
    pytest.param({"a": {"type": "string", "fromFact": ["/a", "/b"]}}, id="no-choice-among-facts"),
    pytest.param({"a": {"type": "decimal", "constant": "1", "add": "2"}}, id="no-arithmetic"),
],)
def test_document_negative(declaration):
    assert_pack_error(value_pack(declaration))


def test_document_negative_missing_required_extension():
    pack = value_pack({"a": {"type": "string", "constant": "text"}})
    del pack["metadata"]
    assert_pack_error(pack)


def test_document_negative_extension_on_root_alone():
    pack = value_pack({"a": {"type": "string", "constant": "text"}})
    pack["extensions"] = pack["outcomes"][0].pop("extensions")
    assert_pack_error(pack)


@pytest.mark.parametrize("location", ["root", "decision", "rule", "evidence-requirement", "source",
                                     "exception", "escalation", "metadata"])
def test_document_negative_extension_on_outcome_and_other_core_object(location):
    pack = value_pack({"a": {"type": "string", "constant": "text"}})
    if location == "root":
        target = pack
    elif location == "rule":
        target = pack["rules"][0]
    elif location == "evidence-requirement":
        target = {"id": "proof", "description": "Proof", "required": False}
        pack["evidenceRequirements"] = [target]
    elif location == "source":
        target = {"id": "policy", "title": "Policy", "locator": {"kind": "other", "value": "Here"}}
        pack["sources"] = [target]
    elif location == "exception":
        select_route(pack, "forced-outcome")
        target = pack["exceptions"][0]
    elif location == "escalation":
        target = {"triggers": ["unknown"], "target": {"kind": "queue", "name": "Review"}}
        pack["escalation"] = target
    else:
        target = pack[location]
    target["extensions"] = deepcopy(pack["outcomes"][0]["extensions"])
    assert_pack_error(pack)


# Conformance: evaluation positive/negative cases across all three outcome routes.
@pytest.mark.parametrize("route", ["true-rule", "forced-outcome", "fallbackOutcome"])
def test_evaluation_positive_constant_by_each_outcome_route(route):
    pack = value_pack({"amount": {"type": "decimal", "constant": "10000"}})
    select_route(pack, route)
    assert evaluate(pack, {}, enable_rfc0016=True) == outcome({"amount": "10000"})


@pytest.mark.parametrize("value_type,value", [("string", "CAD"), ("decimal", "149.50"), ("boolean", True)],
                         ids=["string", "decimal", "boolean"])
def test_evaluation_positive_fromFact_each_type(value_type, value):
    pack = value_pack({"a": {"type": value_type, "fromFact": "/fact"}})
    assert evaluate(pack, {"fact": value}, enable_rfc0016=True) == outcome({"a": value})


@pytest.mark.parametrize("route", ["true-rule", "forced-outcome", "fallbackOutcome"])
def test_evaluation_negative_missing_fromFact_by_each_outcome_route(route):
    pack = value_pack({"amount": {"type": "decimal", "fromFact": "/missing"}})
    select_route(pack, route)
    assert canonicalize_disposition(evaluate(pack, {}, enable_rfc0016=True)) == UNKNOWN_BYTES


def test_evaluation_negative_two_values_one_missing_has_no_partial_value():
    pack = value_pack({"currency": {"type": "string", "constant": "CAD"},
                       "amount": {"type": "decimal", "fromFact": "/missing"}})
    assert canonicalize_disposition(evaluate(pack, {}, enable_rfc0016=True)) == UNKNOWN_BYTES


@pytest.mark.parametrize("kind", ["not-applicable", "unresolved"])
def test_evaluation_negative_non_outcome_never_resolves_or_carries_values(kind):
    pack = value_pack({"a": {"type": "string", "constant": "x" * 1000}})
    pack["applicability"] = ({"op": "literal", "value": False} if kind == "not-applicable"
                             else fact_condition("/absent", "equals", True))
    # Resolving the declaration would exceed this budget.
    result = evaluate(pack, {}, enable_rfc0016=True, evaluation_work_limit=50)
    assert result == {"kind": kind, "reasons": ["not-applicable" if kind == "not-applicable" else "unknown"],
                      "handoff": {"state": "none"}}


@pytest.mark.parametrize("triggers", [["unknown", "no-match"], ["no-match"], None],
                         ids=["unknown-trigger", "other-trigger", "no-escalation"])
def test_evaluation_handoff_for_unresolved_value(triggers):
    pack = value_pack({"a": {"type": "string", "fromFact": "/missing"}})
    if triggers is not None:
        pack["escalation"] = {"triggers": triggers, "target": {"kind": "queue", "name": "Review"}}
    handoff = ({"state": "requested", "triggeredBy": ["unknown"]} if triggers and "unknown" in triggers
               else {"state": "none"})
    assert evaluate(pack, {}, enable_rfc0016=True) == {
        "kind": "unresolved", "reasons": ["unknown"], "handoff": handoff,
    }


@pytest.mark.parametrize("value_type,value", [("decimal", "0.10"), ("string", ""), ("boolean", False)],
                         ids=["trailing-zeroes", "empty-string", "false"])
def test_evaluation_boundary_exact_copy(value_type, value):
    pack = value_pack({"a": {"type": value_type, "fromFact": "/fact"}})
    result = evaluate(pack, {"fact": value}, enable_rfc0016=True)
    assert result == outcome({"a": value})
    expected_value = json.dumps(value, separators=(",", ":")).encode("utf-8")
    assert canonicalize_disposition(result) == (
        b'{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"outcome-a",'
        b'"reasons":[],"value":{"a":' + expected_value + b'}}'
    )


def test_evaluation_boundary_two_true_rules_same_outcome_resolve_values_once():
    pack = value_pack({"a": {"type": "boolean", "constant": False}})
    second = deepcopy(pack["rules"][0])
    second["id"] = "second"
    pack["rules"].append(second)
    # Two literal rules cost 2; one value source costs 1+len('a')+1 = 3.
    assert evaluate(pack, {}, enable_rfc0016=True, evaluation_work_limit=5) == outcome({"a": False})


def test_evaluation_boundary_declaration_member_order_does_not_change_canonical_bytes():
    pack = pass_through_pack()
    facts = {"customer": {"goodStanding": True}, "proposed": {"refundAmount": "149.50"}}
    before = canonicalize_disposition(evaluate(pack, facts, enable_rfc0016=True))
    declaration = pack["outcomes"][0]["extensions"][EXTENSION]
    pack["outcomes"][0]["extensions"][EXTENSION] = dict(reversed(list(declaration.items())))
    after = canonicalize_disposition(evaluate(pack, facts, enable_rfc0016=True))
    assert before == after == PASS_THROUGH_BYTES


@pytest.mark.parametrize("value_type,value,resolves", [
    ("decimal", 149.5, False), ("decimal", None, False), ("decimal", {}, False),
    ("decimal", " 149.50 ", False), ("string", " CAD \n", True),
    ("string", "\ud800", False), ("decimal", [], False), ("decimal", True, False),
    ("string", False, False), ("string", [], False), ("string", {}, False),
    ("string", None, False), ("boolean", "false", False), ("boolean", 0, False),
    ("string", "\udfff", False), ("decimal", "1e2", False),
], ids=["decimal-json-number", "decimal-null", "decimal-object", "decimal-whitespace",
        "string-whitespace", "string-unpaired-surrogate", "decimal-array", "decimal-boolean",
        "string-boolean", "string-array", "string-object", "string-null", "boolean-string",
        "boolean-number", "string-unpaired-low-surrogate", "decimal-exponent"])
def test_evaluation_adversarial_selected_type(value_type, value, resolves):
    pack = value_pack({"a": {"type": value_type, "fromFact": "/fact"}})
    result = evaluate(pack, {"fact": value}, enable_rfc0016=True)
    if resolves:
        assert result == outcome({"a": value})
    else:
        assert canonicalize_disposition(result) == UNKNOWN_BYTES


def test_evaluation_adversarial_pointer_array_out_of_range():
    pack = value_pack({"a": {"type": "string", "fromFact": "/items/1"}})
    assert canonicalize_disposition(evaluate(pack, {"items": ["only"]}, enable_rfc0016=True)) == UNKNOWN_BYTES


def test_evaluation_adversarial_only_produced_outcome_is_inspected():
    pack = value_pack({"a": {"type": "string", "constant": "yes"}})
    pack["outcomes"][1]["extensions"] = {
        EXTENSION: {"missing": {"type": "decimal", "fromFact": "/absent"}},
    }
    assert evaluate(pack, {}, enable_rfc0016=True) == outcome({"a": "yes"})


# Conformance: error rows, including the documented unsupported-consumer limitation.
def test_error_malformed_unselected_declaration_precedes_false_applicability():
    pack = value_pack({"a": {"type": "string", "constant": "yes"}})
    pack["outcomes"][1]["extensions"] = {EXTENSION: {}}
    pack["applicability"] = {"op": "literal", "value": False}
    assert_pack_error(pack)


def test_error_malformed_declaration_precedes_undeclared_evidence_member():
    assert_pack_error(value_pack({}), evidence={"undeclared": "present"})


@pytest.mark.parametrize("declaration", [
    {"a": {"type": "string", "constant": "yes"}}, {}, {"a": {"type": "unknown", "constant": "yes"}},
], ids=["well-formed", "empty-declaration", "unknown-type"])
def test_error_unsupported_consumer_reserved_name_precedence_decision_28(declaration):
    # RFC expects unsupported-required-extension after hypothetical schema admission.
    # With the opt-in off, this implementation must retain current Core rejection.
    with pytest.raises(PackNotConformantError) as error:
        evaluate(value_pack(declaration), {})
    assert error.value.error_class == "pack-not-conformant"
    assert error.value.phase == "preflight"


@pytest.mark.parametrize("enabled", [False, True], ids=["unsupported-consumer", "supporting-consumer"])
def test_error_duplicate_member_inside_declaration_is_core_pack_fault(tmp_path, enabled):
    pack_text = json.dumps(value_pack({"a": {"type": "decimal", "constant": "2"}}))
    pack_text = pack_text.replace('"a":', '"a": {"type":"decimal","constant":"1"}, "a":', 1)
    completed = run_cli(tmp_path, pack_text, enabled=enabled, evidence='{"undeclared":"present"}')
    assert completed.returncode == 2
    assert completed.stdout == b""
    result = json.loads(completed.stderr)
    assert result["error"]["class"] == "pack-not-conformant"
    assert result["error"]["phase"] == "preflight"
    assert "duplicate" in result["error"]["message"]
    assert "disposition" not in result
    assert result["experimental"] is True
    assert result["conformanceClaim"] == "none"


# Integration and decisions: CLI bytes, admission boundaries, Unicode, and limits.
def test_cli_pass_through_exact_disposition_bytes_and_existing_markers(tmp_path):
    completed = run_cli(tmp_path, pass_through_pack(),
                        '{"customer":{"goodStanding":true},"proposed":{"refundAmount":"149.50"}}')
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == b""
    assert completed.stdout == (b'{"conformanceClaim":"none","disposition":'
                                + PASS_THROUGH_BYTES + b',"experimental":true}\n')


def test_cli_off_by_default_and_opt_in_required(tmp_path):
    completed = run_cli(tmp_path, pass_through_pack(), enabled=False)
    assert completed.returncode == 2
    assert completed.stdout == b""
    assert json.loads(completed.stderr)["error"]["class"] == "pack-not-conformant"


def test_cli_extension_pack_preflight_precedes_malformed_facts(tmp_path):
    completed = run_cli(tmp_path, value_pack({}), facts="{")
    assert completed.returncode == 2
    assert completed.stdout == b""
    assert json.loads(completed.stderr)["error"]["class"] == "pack-not-conformant"


def test_cli_boolean_and_unicode_values_have_canonical_bytes(tmp_path):
    pack = value_pack({"a": {"type": "boolean", "constant": False},
                       "b": {"type": "string", "constant": "🚀\n\"\\"}})
    completed = run_cli(tmp_path, pack)
    assert completed.returncode == 0, completed.stderr
    expected = ('{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"outcome-a",'
                '"reasons":[],"value":{"a":false,"b":"🚀\\n\\\"\\\\"}}').encode("utf-8")
    assert completed.stdout == b'{"conformanceClaim":"none","disposition":' + expected + b',"experimental":true}\n'


@pytest.mark.parametrize("enabled", [False, True])
def test_core_pack_without_values_is_byte_identical(enabled):
    pack = base_pack()
    pack["fallbackOutcome"] = "outcome-a"
    assert canonicalize_disposition(evaluate(pack, {}, enable_rfc0016=enabled)) == (
        b'{"handoff":{"state":"none"},"kind":"outcome","outcomeId":"outcome-a","reasons":[]}'
    )


def test_supported_extension_list_alone_cannot_enable_rfc0016():
    with pytest.raises(PackNotConformantError):
        evaluate(value_pack({"a": {"type": "boolean", "constant": True}}), {},
                 supported_extensions=[EXTENSION])


@pytest.mark.parametrize("version", ["0.1.0-draft", "0.2.0-draft"])
def test_opt_in_applies_to_both_existing_spec_versions(version):
    pack = value_pack({"a": {"type": "boolean", "constant": True}})
    pack["specVersion"] = version
    assert evaluate(pack, {}, enable_rfc0016=True) == outcome({"a": True})


@pytest.mark.parametrize("invalid", [None, 1, "true"])
def test_opt_in_must_be_boolean(invalid):
    with pytest.raises(EvaluationInputError, match="enable_rfc0016"):
        evaluate(base_pack(), {}, enable_rfc0016=invalid)


@pytest.mark.parametrize("location", ["requiredExtensions", "extensions"])
def test_other_reserved_extension_names_remain_rejected(location):
    pack = value_pack({"a": {"type": "boolean", "constant": True}})
    other = "org.judgmentpack.other"
    if location == "requiredExtensions":
        pack["metadata"][location].append(other)
    else:
        pack["outcomes"][0][location][other] = {}
    assert_pack_error(pack)


def test_required_name_without_declaration_remains_a_core_error():
    pack = value_pack({"a": {"type": "boolean", "constant": True}})
    del pack["outcomes"][0]["extensions"]
    assert_pack_error(pack)


def test_other_required_extension_still_needs_explicit_support():
    pack = value_pack({"a": {"type": "boolean", "constant": True}})
    pack["extensions"] = {"com.example.other": {}}
    pack["metadata"]["requiredExtensions"].append("com.example.other")
    with pytest.raises(UnsupportedExtensionError):
        evaluate(pack, {}, enable_rfc0016=True)
    assert evaluate(pack, {}, enable_rfc0016=True,
                    supported_extensions=["com.example.other"]) == outcome({"a": True})


@pytest.mark.parametrize("fault", ["unknown-root-member", "bad-outcome-reference", "single-outcome",
                                  "duplicate-required-extension", "invalid-uri"])
def test_opt_in_preserves_other_core_pack_checks(fault):
    pack = value_pack({"a": {"type": "boolean", "constant": True}})
    if fault == "unknown-root-member":
        pack["extra"] = True
    elif fault == "bad-outcome-reference":
        pack["rules"][0]["outcome"] = "undeclared"
    elif fault == "single-outcome":
        pack["outcomes"] = pack["outcomes"][:1]
    elif fault == "duplicate-required-extension":
        pack["metadata"]["requiredExtensions"].append(EXTENSION)
    else:
        pack["id"] = "relative"
    assert_pack_error(pack)


def test_extensions_shaped_literal_data_remains_inert_decision_29():
    pack = value_pack({"a": {"type": "boolean", "constant": True}})
    payload = {"extensions": {EXTENSION: {}}}
    pack["extensions"] = {"com.example.inert": payload}
    pack["rules"][0]["when"] = fact_condition("", "equals", payload)
    assert evaluate(pack, payload, enable_rfc0016=True) == outcome({"a": True})


@pytest.mark.parametrize("pointer,facts,expected", [
    ("", "root", "root"), ("/a~1b/~0key", {"a/b": {"~key": "escaped"}}, "escaped"),
    ("/items/0", {"items": ["first"]}, "first"), ("/items/01", {"items": ["a", "b"]}, None),
    ("/items/-", {"items": ["a"]}, None), ("/a/b", {"a": "scalar"}, None),
    ("/01", {"01": "object-member"}, "object-member"),
], ids=["root", "escaped-tokens", "array-index", "array-leading-zero", "array-dash", "scalar-traversal", "object-leading-zero"])
def test_fromFact_uses_core_pointer_rules(pointer, facts, expected):
    pack = value_pack({"a": {"type": "string", "fromFact": pointer}})
    result = evaluate(pack, facts, enable_rfc0016=True)
    if expected is None:
        assert canonicalize_disposition(result) == UNKNOWN_BYTES
    else:
        assert result == outcome({"a": expected})


@pytest.mark.parametrize("decimal", ["+1", "01", "1.", ".1", "NaN", "Infinity", "1\n", "١"])
def test_decimal_grammar_rejects_constant_and_fact(decimal):
    assert_pack_error(value_pack({"a": {"type": "decimal", "constant": decimal}}))
    pack = value_pack({"a": {"type": "decimal", "fromFact": "/a"}})
    assert canonicalize_disposition(evaluate(pack, {"a": decimal}, enable_rfc0016=True)) == UNKNOWN_BYTES


@pytest.mark.parametrize("decimal", ["-0", "-0.00", "-999999999999999999999999999999.000", "999999999999999999999999999999"])
def test_values_are_not_range_checked_or_normalized(decimal):
    pack = value_pack({"a": {"type": "decimal", "fromFact": "/a"}})
    assert evaluate(pack, {"a": decimal}, enable_rfc0016=True) == outcome({"a": decimal})


def test_unicode_scalar_strings_are_copied_without_normalization():
    text = "e\u0301\x00🚀"
    pack = value_pack({"a": {"type": "string", "fromFact": ""}})
    assert evaluate(pack, strict_loads(json.dumps(text)), enable_rfc0016=True) == outcome({"a": text})
    assert_pack_error(value_pack({"a": {"type": "string", "constant": "\ud83d\ude80"}}))


def test_independent_rfc0008_and_rfc0016_opt_ins():
    pack = value_pack({"a": {"type": "string", "fromFact": "/a"}})
    pack["rules"][0]["when"] = {"op": "exists", "path": "/items", "where": {"op": "literal", "value": True}}
    assert_pack_error(pack)
    assert evaluate(pack, {"a": "root-value", "items": [{}]}, enable_rfc0008=True,
                    enable_rfc0016=True) == outcome({"a": "root-value"})


@pytest.mark.parametrize("source,facts,limit", [
    ({"type": "string", "constant": "xx"}, {}, 6),
    ({"type": "string", "fromFact": "/x"}, {"x": "xx"}, 9),
    ({"type": "string", "fromFact": "/x"}, {}, 6),
], ids=["constant", "resolved-pointer", "unresolved-pointer"])
def test_value_resolution_shares_work_budget_with_conditions(source, facts, limit):
    pack = value_pack({"a": source})
    with pytest.raises(ResourceLimitError) as error:
        evaluate(pack, facts, enable_rfc0016=True, evaluation_work_limit=limit - 1)
    assert error.value.error_class == "resource-exhaustion"
    assert error.value.phase == "evaluation"
    result = evaluate(pack, facts, enable_rfc0016=True, evaluation_work_limit=limit)
    assert result == (outcome({"a": "xx"}) if "constant" in source or facts else json.loads(UNKNOWN_BYTES))


@pytest.mark.parametrize("reverse", [False, True])
def test_value_work_is_order_independent_even_when_a_value_is_missing(reverse):
    sources = [("a", {"type": "string", "fromFact": "/missing"}),
               ("b", {"type": "string", "constant": "x" * 100})]
    if reverse:
        sources.reverse()
    pack = value_pack(dict(sources))
    with pytest.raises(ResourceLimitError):
        evaluate(pack, {}, enable_rfc0016=True, evaluation_work_limit=50)
    assert canonicalize_disposition(evaluate(pack, {}, enable_rfc0016=True)) == UNKNOWN_BYTES


def test_value_names_count_toward_collection_limit_even_on_unselected_outcomes():
    # Three outcomes + one rule + 9,996 value sources is exactly the existing limit.
    declaration = {f"v{i}": {"type": "boolean", "constant": True} for i in range(9996)}
    pack = value_pack(declaration)
    pack["applicability"] = {"op": "literal", "value": False}
    assert evaluate(pack, {}, enable_rfc0016=True)["kind"] == "not-applicable"
    pack["outcomes"][0]["extensions"][EXTENSION]["overLimit"] = {"type": "boolean", "constant": True}
    with pytest.raises(ResourceLimitError):
        evaluate(pack, {}, enable_rfc0016=True)


@pytest.mark.parametrize("location", ["constant", "fact"])
def test_string_admission_limits_keep_preflight_error_classes(location):
    text = "x" * (1024 * 1024 + 1)
    if location == "constant":
        assert_pack_error(value_pack({"a": {"type": "string", "constant": text}}))
    else:
        pack = value_pack({"a": {"type": "string", "fromFact": ""}})
        with pytest.raises(EvaluationInputError) as error:
            evaluate(pack, text, enable_rfc0016=True)
        assert error.value.error_class == "malformed-input"
        assert error.value.phase == "preflight"
