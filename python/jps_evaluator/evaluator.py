"""Core 0.2.0-draft evaluation with opt-in RFC 0008 and RFC 0016 prototypes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from .conditions import (
    DEFAULT_EVALUATION_WORK_LIMIT,
    EvaluationBudget,
    TriValue,
    _pointer_tokens,
    evaluate_condition,
    is_decimal_string,
)
from .errors import (
    EvaluationInputError,
    PackNotConformantError,
    PointerSyntaxError,
    ResourceLimitError,
    UnsupportedExtensionError,
)
from .json_input import normalize_json
from .outcome_values import (
    OUTCOME_VALUES_EXTENSION,
    resolve_values,
    validate_value_declaration,
)


_LOCAL_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
_EXTENSION_RE = re.compile(
    r"^(?!org\.judgmentpack\.)[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$"
)
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_URI_CHAR_RE = re.compile(r"^[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+$")
_BAD_PERCENT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_DATE_RE = re.compile(r"^(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})$")
_DATETIME_RE = re.compile(
    r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[Tt]"
    r"(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.[0-9]+)?(?:[Zz]|(?P<offset_sign>[+-])"
    r"(?P<offset_hour>[0-9]{2}):(?P<offset_minute>[0-9]{2}))$"
)
_ACCEPTED_SPEC_VERSIONS = {"0.1.0-draft", "0.2.0-draft"}
MAX_EVALUATION_COLLECTION_ITEMS = 10_000
_CORE_CONDITION_OPS = {"literal", "all", "any", "not", "fact", "evidence-present"}
_RFC0008_AGGREGATE_OPS = {"exists", "every", "uniform"}
_FACT_OPERATORS = {
    "equals",
    "not-equals",
    "greater-than",
    "greater-than-or-equal",
    "less-than",
    "less-than-or-equal",
    "in",
}
_ORDERED_OPERATORS = {
    "greater-than",
    "greater-than-or-equal",
    "less-than",
    "less-than-or-equal",
}
_TRIGGERS = {
    "not-applicable",
    "missing-required-evidence",
    "unknown",
    "conflict",
    "no-match",
}
_ROOT_MEMBERS = {
    "specVersion",
    "id",
    "version",
    "title",
    "description",
    "decision",
    "applicability",
    "evidenceRequirements",
    "sources",
    "outcomes",
    "rules",
    "exceptions",
    "fallbackOutcome",
    "escalation",
    "metadata",
    "extensions",
}


@dataclass(frozen=True)
class _PackView:
    applicability: dict[str, Any] | None
    requirements: tuple[dict[str, Any], ...]
    requirement_ids: frozenset[str]
    outcomes: frozenset[str]
    outcome_values: dict[str, dict[str, Any]]
    rules: tuple[dict[str, Any], ...]
    exceptions: tuple[dict[str, Any], ...]
    fallback: str | None
    escalation: dict[str, Any] | None
    required_extensions: frozenset[str]
    evaluation_collection_items: int


def evaluate(
    pack: Any,
    facts: Any,
    evidence: Any = None,
    supported_extensions: Iterable[str] = (),
    *,
    enable_rfc0008: bool = False,
    enable_rfc0016: bool = False,
    evaluation_work_limit: int = DEFAULT_EVALUATION_WORK_LIMIT,
) -> dict[str, Any]:
    """Evaluate one admitted input set and return only its portable disposition.

    RFC 0008 aggregate operators are accepted only when ``enable_rfc0008`` is
    explicitly true. Every failure raises an EvaluationError carrying exactly
    one Core class and a preflight/evaluation phase; errors are never returned
    as dispositions.

    ``enable_rfc0016=True`` admits and supports the draft outcome-values
    extension. It is disabled by default and makes no conformance claim.
    """

    if not isinstance(enable_rfc0008, bool):
        raise EvaluationInputError("enable_rfc0008 must be a Boolean")
    if not isinstance(enable_rfc0016, bool):
        raise EvaluationInputError("enable_rfc0016 must be a Boolean")

    # Core §8.2 fixes this admission order. Pack normalization and semantic
    # validation are deliberately completed before touching the facts input.
    normalized_pack, view = _admit_pack(
        pack, enable_rfc0008=enable_rfc0008, enable_rfc0016=enable_rfc0016
    )

    normalized_facts = normalize_json(facts, source="facts")
    normalized_evidence = (
        {} if evidence is None else normalize_json(evidence, source="evidence availability")
    )
    evidence_states = _prepare_evidence(normalized_evidence, view.requirement_ids)
    supported = _normalize_supported_extensions(supported_extensions)
    if enable_rfc0016:
        supported = supported | {OUTCOME_VALUES_EXTENSION}
    unsupported = view.required_extensions - supported
    if unsupported:
        raise UnsupportedExtensionError(
            "unsupported required extension(s): " + ", ".join(sorted(unsupported))
        )

    budget = EvaluationBudget(evaluation_work_limit)
    if view.evaluation_collection_items > MAX_EVALUATION_COLLECTION_ITEMS:
        raise ResourceLimitError(
            "evaluation collections exceed configured limit of "
            f"{MAX_EVALUATION_COLLECTION_ITEMS} items"
        )

    if view.applicability is None:
        applicability = TriValue.TRUE
    else:
        applicability = evaluate_condition(
            view.applicability,
            normalized_facts,
            evidence_states,
            budget=budget,
            enable_rfc0008=enable_rfc0008,
        )
    if applicability is TriValue.FALSE:
        return _make_disposition(
            "not-applicable",
            reasons={"not-applicable"},
            escalation=view.escalation,
        )
    if applicability is TriValue.UNKNOWN:
        return _make_disposition(
            "unresolved", reasons={"unknown"}, escalation=view.escalation
        )

    reasons: set[str] = set()
    absent_required = False
    unknown_required = False
    for requirement in view.requirements:
        if not requirement["required"]:
            continue
        state = evidence_states.get(requirement["id"], "unknown")
        absent_required = absent_required or state == "absent"
        unknown_required = unknown_required or state == "unknown"
    if absent_required:
        reasons.add("missing-required-evidence")
    elif unknown_required:
        reasons.add("unknown")

    suppressed_rules: set[str] = set()
    forced_outcomes: set[str] = set()
    direct_escalation = False
    for exception in view.exceptions:
        result = evaluate_condition(
            exception["when"],
            normalized_facts,
            evidence_states,
            budget=budget,
            enable_rfc0008=enable_rfc0008,
        )
        if result is TriValue.UNKNOWN:
            if exception["onUnknown"] == "escalate":
                reasons.add("unknown")
            continue
        if result is TriValue.FALSE:
            continue
        effect = exception["effect"]
        if effect == "suppress-rule":
            suppressed_rules.add(exception["targetRule"])
        elif effect == "force-outcome":
            forced_outcomes.add(exception["outcome"])
        else:
            direct_escalation = True

    if direct_escalation:
        reasons.add("exception-escalation")
    if len(forced_outcomes) > 1:
        reasons.add("conflict")
    if reasons:
        return _make_disposition(
            "unresolved",
            reasons=reasons,
            escalation=view.escalation,
            direct_escalation=direct_escalation,
        )
    if len(forced_outcomes) == 1:
        return _resolve_outcome(next(iter(forced_outcomes)), view, normalized_facts, budget)

    candidate_outcomes: set[str] = set()
    rule_reasons: set[str] = set()
    for rule in view.rules:
        if rule["id"] in suppressed_rules:
            continue
        result = evaluate_condition(
            rule["when"],
            normalized_facts,
            evidence_states,
            budget=budget,
            enable_rfc0008=enable_rfc0008,
        )
        if result is TriValue.TRUE:
            candidate_outcomes.add(rule["outcome"])
        elif result is TriValue.UNKNOWN and rule["onUnknown"] == "escalate":
            rule_reasons.add("unknown")

    if len(candidate_outcomes) > 1:
        rule_reasons.add("conflict")
    if rule_reasons:
        return _make_disposition(
            "unresolved", reasons=rule_reasons, escalation=view.escalation
        )
    if len(candidate_outcomes) == 1:
        return _resolve_outcome(next(iter(candidate_outcomes)), view, normalized_facts, budget)
    if view.fallback is not None:
        return _resolve_outcome(view.fallback, view, normalized_facts, budget)
    return _make_disposition(
        "unresolved", reasons={"no-match"}, escalation=view.escalation
    )


def _resolve_outcome(
    outcome_id: str, view: _PackView, facts: Any, budget: EvaluationBudget
) -> dict[str, Any]:
    disposition = _make_disposition("outcome", outcome_id=outcome_id)
    if outcome_id in view.outcome_values:
        values = resolve_values(view.outcome_values[outcome_id], facts, budget)
        if values is None:
            return _make_disposition(
                "unresolved", reasons={"unknown"}, escalation=view.escalation
            )
        disposition["value"] = values
    return disposition


def _admit_pack(
    pack: Any, *, enable_rfc0008: bool, enable_rfc0016: bool = False
) -> tuple[Any, _PackView]:
    """Normalize and validate only the pack stage of §8.2 preflight."""

    try:
        normalized_pack = normalize_json(pack, source="pack")
        return normalized_pack, _prepare_pack(
            normalized_pack,
            enable_rfc0008=enable_rfc0008,
            enable_rfc0016=enable_rfc0016,
        )
    except PackNotConformantError:
        raise
    except EvaluationInputError as exc:
        raise PackNotConformantError(str(exc)) from exc


def _prepare_pack(
    pack: Any,
    *,
    enable_rfc0008: bool,
    enable_rfc0016: bool = False,
) -> _PackView:
    _validate_object(
        pack,
        "pack",
        required={"specVersion", "id", "version", "title", "decision", "outcomes", "rules"},
        allowed=_ROOT_MEMBERS,
    )
    if (
        not isinstance(pack["specVersion"], str)
        or pack["specVersion"] not in _ACCEPTED_SPEC_VERSIONS
    ):
        raise EvaluationInputError(
            "pack specVersion must be '0.1.0-draft' or '0.2.0-draft'"
        )
    _validate_absolute_uri(pack["id"], "pack id")
    if not isinstance(pack["version"], str) or _VERSION_RE.fullmatch(pack["version"]) is None:
        raise EvaluationInputError("pack version must be a three-component version string")
    _require_non_empty_string(pack["title"], "pack title")
    if "description" in pack:
        _require_non_empty_string(pack["description"], "pack description")

    extension_values: set[str] = set()
    if "extensions" in pack:
        _validate_extensions(pack["extensions"], "pack extensions", extension_values)
    _validate_decision(pack["decision"], extension_values)

    outcomes_raw = pack["outcomes"]
    if not isinstance(outcomes_raw, list) or len(outcomes_raw) < 2:
        raise EvaluationInputError("pack outcomes must be an array with at least two items")
    outcomes: set[str] = set()
    outcome_values: dict[str, dict[str, Any]] = {}
    for index, outcome in enumerate(outcomes_raw):
        _validate_object(
            outcome,
            f"outcome {index}",
            required={"id", "label"},
            allowed={"id", "label", "description", "extensions"},
        )
        outcome_id = _require_local_id(outcome["id"], "outcome id")
        if outcome_id in outcomes:
            raise EvaluationInputError(f"duplicate outcome id {outcome_id!r}")
        _require_non_empty_string(outcome["label"], f"outcome {outcome_id!r} label")
        if "description" in outcome:
            _require_non_empty_string(
                outcome["description"], f"outcome {outcome_id!r} description"
            )
        if "extensions" in outcome:
            _validate_extensions(
                outcome["extensions"],
                f"outcome {outcome_id!r} extensions",
                extension_values,
                allow_outcome_values=enable_rfc0016,
            )
            if enable_rfc0016 and OUTCOME_VALUES_EXTENSION in outcome["extensions"]:
                declaration = outcome["extensions"][OUTCOME_VALUES_EXTENSION]
                validate_value_declaration(declaration, f"outcome {outcome_id!r}")
                outcome_values[outcome_id] = declaration
        outcomes.add(outcome_id)

    requirements_raw = pack.get("evidenceRequirements", [])
    if not isinstance(requirements_raw, list):
        raise EvaluationInputError("evidenceRequirements must be an array")
    requirements: list[dict[str, Any]] = []
    requirement_ids: set[str] = set()
    for index, requirement in enumerate(requirements_raw):
        _validate_object(
            requirement,
            f"evidence requirement {index}",
            required={"id", "description", "required"},
            allowed={"id", "description", "required", "kind", "extensions"},
        )
        requirement_id = _require_local_id(
            requirement["id"], "evidence requirement id"
        )
        if requirement_id in requirement_ids:
            raise EvaluationInputError(f"duplicate evidence requirement id {requirement_id!r}")
        _require_non_empty_string(
            requirement["description"],
            f"evidence requirement {requirement_id!r} description",
        )
        if not isinstance(requirement["required"], bool):
            raise EvaluationInputError(
                f"evidence requirement {requirement_id!r} has invalid required flag"
            )
        if "kind" in requirement and (
            not isinstance(requirement["kind"], str)
            or requirement["kind"]
            not in {"document", "fact", "measurement", "attestation"}
        ):
            raise EvaluationInputError(
                f"evidence requirement {requirement_id!r} has invalid kind"
            )
        if "extensions" in requirement:
            _validate_extensions(
                requirement["extensions"],
                f"evidence requirement {requirement_id!r} extensions",
                extension_values,
            )
        requirement_ids.add(requirement_id)
        requirements.append(requirement)

    sources_raw = pack.get("sources", [])
    if not isinstance(sources_raw, list):
        raise EvaluationInputError("sources must be an array")
    source_ids: set[str] = set()
    for index, source in enumerate(sources_raw):
        source_id = _validate_source(source, index, extension_values)
        if source_id in source_ids:
            raise EvaluationInputError(f"duplicate source id {source_id!r}")
        source_ids.add(source_id)

    if "applicability" in pack and pack["applicability"] is None:
        raise EvaluationInputError("applicability must be a condition when present")
    applicability = pack.get("applicability")
    if applicability is not None:
        _validate_condition(
            applicability,
            requirement_ids,
            "applicability",
            enable_rfc0008=enable_rfc0008,
        )

    rules_raw = pack["rules"]
    if not isinstance(rules_raw, list) or not rules_raw:
        raise EvaluationInputError("pack rules must be a non-empty array")
    rule_ids: set[str] = set()
    rules: list[dict[str, Any]] = []
    for index, rule in enumerate(rules_raw):
        _validate_object(
            rule,
            f"rule {index}",
            required={"id", "description", "when", "outcome", "onUnknown"},
            allowed={
                "id",
                "description",
                "when",
                "outcome",
                "onUnknown",
                "evidenceRequirementRefs",
                "sourceRefs",
                "rationale",
                "extensions",
            },
        )
        rule_id = _require_local_id(rule["id"], "rule id")
        if rule_id in rule_ids:
            raise EvaluationInputError(f"duplicate rule id {rule_id!r}")
        _require_non_empty_string(rule["description"], f"rule {rule_id!r} description")
        if not isinstance(rule.get("outcome"), str) or rule["outcome"] not in outcomes:
            raise EvaluationInputError(f"rule {rule_id!r} names an undeclared outcome")
        if (
            not isinstance(rule.get("onUnknown"), str)
            or rule["onUnknown"] not in {"ignore", "escalate"}
        ):
            raise EvaluationInputError(f"rule {rule_id!r} has invalid onUnknown")
        _validate_condition(
            rule.get("when"),
            requirement_ids,
            f"rule {rule_id!r}",
            enable_rfc0008=enable_rfc0008,
        )
        _validate_reference_list(
            rule.get("evidenceRequirementRefs", []),
            requirement_ids,
            f"rule {rule_id!r} evidenceRequirementRefs",
        )
        _validate_reference_list(
            rule.get("sourceRefs", []),
            source_ids,
            f"rule {rule_id!r} sourceRefs",
        )
        if "rationale" in rule:
            _require_non_empty_string(rule["rationale"], f"rule {rule_id!r} rationale")
        if "extensions" in rule:
            _validate_extensions(
                rule["extensions"], f"rule {rule_id!r} extensions", extension_values
            )
        rule_ids.add(rule_id)
        rules.append(rule)

    exceptions_raw = pack.get("exceptions", [])
    if not isinstance(exceptions_raw, list):
        raise EvaluationInputError("exceptions must be an array")
    exceptions: list[dict[str, Any]] = []
    exception_ids: set[str] = set()
    for index, exception in enumerate(exceptions_raw):
        _validate_object(
            exception,
            f"exception {index}",
            required={"id", "description", "when", "effect", "onUnknown"},
            allowed={
                "id",
                "description",
                "when",
                "effect",
                "targetRule",
                "outcome",
                "onUnknown",
                "sourceRefs",
                "extensions",
            },
        )
        exception_id = _require_local_id(exception["id"], "exception id")
        if exception_id in exception_ids:
            raise EvaluationInputError(f"duplicate exception id {exception_id!r}")
        _require_non_empty_string(
            exception["description"], f"exception {exception_id!r} description"
        )
        if (
            not isinstance(exception.get("onUnknown"), str)
            or exception["onUnknown"] not in {"ignore", "escalate"}
        ):
            raise EvaluationInputError(f"exception {exception_id!r} has invalid onUnknown")
        _validate_condition(
            exception.get("when"),
            requirement_ids,
            f"exception {exception_id!r}",
            enable_rfc0008=enable_rfc0008,
        )
        effect = exception.get("effect")
        if effect == "suppress-rule":
            if (
                not isinstance(exception.get("targetRule"), str)
                or exception["targetRule"] not in rule_ids
                or "outcome" in exception
            ):
                raise EvaluationInputError(
                    f"exception {exception_id!r} has invalid suppress-rule fields"
                )
        elif effect == "force-outcome":
            if (
                not isinstance(exception.get("outcome"), str)
                or exception["outcome"] not in outcomes
                or "targetRule" in exception
            ):
                raise EvaluationInputError(
                    f"exception {exception_id!r} has invalid force-outcome fields"
                )
        elif effect == "escalate":
            if "outcome" in exception or "targetRule" in exception:
                raise EvaluationInputError(
                    f"exception {exception_id!r} has invalid escalate fields"
                )
        else:
            raise EvaluationInputError(f"exception {exception_id!r} has invalid effect")
        _validate_reference_list(
            exception.get("sourceRefs", []),
            source_ids,
            f"exception {exception_id!r} sourceRefs",
        )
        if "extensions" in exception:
            _validate_extensions(
                exception["extensions"],
                f"exception {exception_id!r} extensions",
                extension_values,
            )
        exception_ids.add(exception_id)
        exceptions.append(exception)

    if "fallbackOutcome" in pack and pack["fallbackOutcome"] is None:
        raise EvaluationInputError("fallbackOutcome must name an outcome when present")
    fallback = pack.get("fallbackOutcome")
    if fallback is not None:
        if not isinstance(fallback, str) or fallback not in outcomes:
            raise EvaluationInputError("fallbackOutcome names an undeclared outcome")
    if "escalation" in pack and pack["escalation"] is None:
        raise EvaluationInputError("escalation must be an object when present")
    escalation = _validate_escalation(pack.get("escalation"), extension_values)
    if "metadata" in pack and pack["metadata"] is None:
        raise EvaluationInputError("metadata must be an object when present")
    required_extensions = _validate_metadata(
        pack.get("metadata"), extension_values, enable_rfc0016=enable_rfc0016
    )
    if outcome_values and OUTCOME_VALUES_EXTENSION not in required_extensions:
        raise EvaluationInputError(
            f"{OUTCOME_VALUES_EXTENSION} must be listed in metadata.requiredExtensions"
        )
    missing_values = required_extensions - extension_values
    if missing_values:
        raise EvaluationInputError(
            "required extension has no corresponding value: "
            + ", ".join(sorted(missing_values))
        )

    return _PackView(
        applicability=applicability,
        requirements=tuple(requirements),
        requirement_ids=frozenset(requirement_ids),
        outcomes=frozenset(outcomes),
        outcome_values=outcome_values,
        rules=tuple(rules),
        exceptions=tuple(exceptions),
        fallback=fallback,
        escalation=escalation,
        required_extensions=required_extensions,
        evaluation_collection_items=(
            len(requirements) + len(outcomes) + len(rules) + len(exceptions)
            + sum(len(declaration) for declaration in outcome_values.values())
        ),
    )


def _validate_object(
    value: Any,
    description: str,
    *,
    required: set[str],
    allowed: set[str],
) -> None:
    if not isinstance(value, dict):
        raise EvaluationInputError(f"{description} must be an object")
    missing = required - value.keys()
    if missing:
        raise EvaluationInputError(
            f"{description} is missing required member {sorted(missing)[0]!r}"
        )
    extra = value.keys() - allowed
    if extra:
        raise EvaluationInputError(
            f"{description} has undeclared member {sorted(extra)[0]!r}"
        )


def _require_non_empty_string(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationInputError(f"{description} must be a non-empty string")
    return value


def _validate_absolute_uri(value: Any, description: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or _URI_SCHEME_RE.match(value) is None
        or _URI_CHAR_RE.fullmatch(value) is None
        or _BAD_PERCENT_RE.search(value) is not None
    ):
        raise EvaluationInputError(f"{description} must be an absolute RFC 3986 URI")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise EvaluationInputError(
            f"{description} must be an absolute RFC 3986 URI"
        ) from exc
    if not parsed.scheme:
        raise EvaluationInputError(f"{description} must be an absolute RFC 3986 URI")


def _validate_extensions(
    value: Any, description: str, found: set[str], *, allow_outcome_values: bool = False
) -> None:
    if not isinstance(value, dict):
        raise EvaluationInputError(f"{description} must be an object")
    for name in value:
        if allow_outcome_values and name == OUTCOME_VALUES_EXTENSION:
            found.add(name)
            continue
        if _EXTENSION_RE.fullmatch(name) is None:
            raise EvaluationInputError(
                f"{description} has invalid extension name {name!r}"
            )
        found.add(name)


def _validate_decision(value: Any, extension_values: set[str]) -> None:
    _validate_object(
        value,
        "decision",
        required={"intent", "question"},
        allowed={"intent", "question", "extensions"},
    )
    _require_non_empty_string(value["intent"], "decision intent")
    _require_non_empty_string(value["question"], "decision question")
    if "extensions" in value:
        _validate_extensions(
            value["extensions"], "decision extensions", extension_values
        )


def _validate_source(
    value: Any, index: int, extension_values: set[str]
) -> str:
    description = f"source {index}"
    _validate_object(
        value,
        description,
        required={"id", "title", "locator"},
        allowed={
            "id",
            "title",
            "publisher",
            "publishedAt",
            "locator",
            "citation",
            "rights",
            "extensions",
        },
    )
    source_id = _require_local_id(value["id"], "source id")
    _require_non_empty_string(value["title"], f"source {source_id!r} title")
    for member in ("publisher", "rights"):
        if member in value:
            _require_non_empty_string(
                value[member], f"source {source_id!r} {member}"
            )
    if "publishedAt" in value:
        _validate_date(value["publishedAt"], f"source {source_id!r} publishedAt")

    locator = value["locator"]
    _validate_object(
        locator,
        f"source {source_id!r} locator",
        required={"kind", "value"},
        allowed={"kind", "value"},
    )
    if (
        not isinstance(locator["kind"], str)
        or locator["kind"] not in {"uri", "repository", "path", "other"}
    ):
        raise EvaluationInputError(f"source {source_id!r} locator kind is invalid")
    _require_non_empty_string(
        locator["value"], f"source {source_id!r} locator value"
    )

    if "citation" in value:
        citation = value["citation"]
        _validate_object(
            citation,
            f"source {source_id!r} citation",
            required={"location", "excerpt"},
            allowed={"location", "excerpt"},
        )
        _require_non_empty_string(
            citation["location"], f"source {source_id!r} citation location"
        )
        _require_non_empty_string(
            citation["excerpt"], f"source {source_id!r} citation excerpt"
        )
    if "extensions" in value:
        _validate_extensions(
            value["extensions"], f"source {source_id!r} extensions", extension_values
        )
    return source_id


def _validate_reference_list(
    value: Any, declared: set[str], description: str
) -> None:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or item not in declared for item in value)
        or len(set(value)) != len(value)
    ):
        raise EvaluationInputError(f"{description} is invalid")


def _validate_date(value: Any, description: str) -> None:
    if not isinstance(value, str):
        raise EvaluationInputError(f"{description} must be an RFC 3339 full-date")
    match = _DATE_RE.fullmatch(value)
    if match is None:
        raise EvaluationInputError(f"{description} must be an RFC 3339 full-date")
    try:
        date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError as exc:
        raise EvaluationInputError(
            f"{description} must be an RFC 3339 full-date"
        ) from exc


def _validate_datetime(value: Any, description: str) -> None:
    if not isinstance(value, str):
        raise EvaluationInputError(f"{description} must be an RFC 3339 date-time")
    match = _DATETIME_RE.fullmatch(value)
    if match is None:
        raise EvaluationInputError(f"{description} must be an RFC 3339 date-time")
    _validate_date(match.group("date"), description)
    if (
        int(match.group("hour")) > 23
        or int(match.group("minute")) > 59
        or int(match.group("second")) > 60
        or (
            match.group("offset_hour") is not None
            and (
                int(match.group("offset_hour")) > 23
                or int(match.group("offset_minute")) > 59
            )
        )
    ):
        raise EvaluationInputError(f"{description} must be an RFC 3339 date-time")


def _require_local_id(value: Any, description: str) -> str:
    if not isinstance(value, str) or _LOCAL_ID_RE.fullmatch(value) is None:
        raise EvaluationInputError(f"{description} is invalid")
    return value


def _validate_condition(
    condition: Any,
    requirement_ids: set[str],
    description: str,
    *,
    enable_rfc0008: bool,
    aggregate_depth: int = 0,
) -> None:
    if not isinstance(condition, dict):
        raise EvaluationInputError(f"{description} condition must be an object")
    op = condition.get("op")
    if not isinstance(op, str):
        raise EvaluationInputError(f"{description} condition has unsupported op")
    if op in _RFC0008_AGGREGATE_OPS and not enable_rfc0008:
        raise EvaluationInputError(
            f"{description} condition uses RFC 0008 op {op!r}; "
            "pass enable_rfc0008=True to opt in"
        )
    if op not in _CORE_CONDITION_OPS | _RFC0008_AGGREGATE_OPS:
        raise EvaluationInputError(f"{description} condition has unsupported op")
    if op == "literal":
        if set(condition) != {"op", "value"} or not isinstance(condition["value"], bool):
            raise EvaluationInputError(f"{description} literal condition is malformed")
        return
    if op in {"all", "any"}:
        if set(condition) != {"op", "conditions"}:
            raise EvaluationInputError(f"{description} {op} condition is malformed")
        children = condition["conditions"]
        if not isinstance(children, list) or not children:
            raise EvaluationInputError(f"{description} {op} condition needs children")
        for child in children:
            _validate_condition(
                child,
                requirement_ids,
                description,
                enable_rfc0008=enable_rfc0008,
                aggregate_depth=aggregate_depth,
            )
        return
    if op == "not":
        if set(condition) != {"op", "condition"}:
            raise EvaluationInputError(f"{description} not condition is malformed")
        _validate_condition(
            condition["condition"],
            requirement_ids,
            description,
            enable_rfc0008=enable_rfc0008,
            aggregate_depth=aggregate_depth,
        )
        return
    if op == "evidence-present":
        if set(condition) != {"op", "evidenceRequirement"}:
            raise EvaluationInputError(
                f"{description} evidence-present condition is malformed"
            )
        if (
            not isinstance(condition["evidenceRequirement"], str)
            or condition["evidenceRequirement"] not in requirement_ids
        ):
            raise EvaluationInputError(
                f"{description} condition names an undeclared evidence requirement"
            )
        return

    if op in _RFC0008_AGGREGATE_OPS:
        next_depth = aggregate_depth + 1
        if next_depth > 2:
            raise EvaluationInputError(
                f"{description} condition exceeds RFC 0008 aggregate depth 2"
            )
        if op == "uniform":
            if set(condition) != {"op", "path", "at"}:
                raise EvaluationInputError(
                    f"{description} uniform condition is malformed"
                )
            _validate_pointer(condition["path"], description)
            _validate_pointer(condition["at"], description)
            return

        if set(condition) != {"op", "path", "where"}:
            raise EvaluationInputError(f"{description} {op} condition is malformed")
        _validate_pointer(condition["path"], description)
        _validate_condition(
            condition["where"],
            requirement_ids,
            description,
            enable_rfc0008=enable_rfc0008,
            aggregate_depth=next_depth,
        )
        return

    if set(condition) != {"op", "path", "operator", "value"}:
        raise EvaluationInputError(f"{description} fact condition is malformed")
    path = condition["path"]
    operator = condition["operator"]
    if (
        not isinstance(path, str)
        or not isinstance(operator, str)
        or operator not in _FACT_OPERATORS
    ):
        raise EvaluationInputError(f"{description} fact condition is malformed")
    _validate_pointer(path, description)
    if operator in _ORDERED_OPERATORS and not is_decimal_string(condition["value"]):
        raise EvaluationInputError(
            f"{description} ordered condition operand is not a decimal string"
        )
    if operator == "in" and (
        not isinstance(condition["value"], list) or not condition["value"]
    ):
        raise EvaluationInputError(f"{description} in operand must be a non-empty array")


def _validate_pointer(path: Any, description: str) -> None:
    if not isinstance(path, str):
        raise EvaluationInputError(f"{description} condition has invalid JSON Pointer")
    try:
        _pointer_tokens(path)
    except PointerSyntaxError as exc:
        raise EvaluationInputError(f"{description} has invalid JSON Pointer") from exc


def _validate_escalation(
    value: Any, extension_values: set[str]
) -> dict[str, Any] | None:
    if value is None:
        return None
    _validate_object(
        value,
        "escalation",
        required={"triggers", "target"},
        allowed={"triggers", "target", "message", "extensions"},
    )
    triggers = value["triggers"]
    target = value["target"]
    if (
        not isinstance(triggers, list)
        or not triggers
        or any(not isinstance(trigger, str) for trigger in triggers)
        or len(set(triggers)) != len(triggers)
        or any(trigger not in _TRIGGERS for trigger in triggers)
    ):
        raise EvaluationInputError("escalation triggers are invalid")
    _validate_object(
        target,
        "escalation target",
        required={"kind", "name"},
        allowed={"kind", "name"},
    )
    if (
        not isinstance(target["kind"], str)
        or target["kind"] not in {"human-role", "queue", "system"}
    ):
        raise EvaluationInputError("escalation target is invalid")
    _require_non_empty_string(target["name"], "escalation target name")
    if "message" in value:
        _require_non_empty_string(value["message"], "escalation message")
    if "extensions" in value:
        _validate_extensions(
            value["extensions"], "escalation extensions", extension_values
        )
    return value


def _validate_metadata(
    value: Any, extension_values: set[str], *, enable_rfc0016: bool = False
) -> frozenset[str]:
    if value is None:
        return frozenset()
    _validate_object(
        value,
        "metadata",
        required=set(),
        allowed={
            "authors",
            "createdAt",
            "license",
            "requiredExtensions",
            "reviews",
            "extensions",
        },
    )
    if "authors" in value:
        authors = value["authors"]
        if (
            not isinstance(authors, list)
            or not authors
            or any(not isinstance(author, str) or not author for author in authors)
            or len(set(authors)) != len(authors)
        ):
            raise EvaluationInputError("metadata.authors is invalid")
    if "createdAt" in value:
        _validate_datetime(value["createdAt"], "metadata.createdAt")
    if "license" in value:
        _require_non_empty_string(value["license"], "metadata.license")

    required = value.get("requiredExtensions", [])
    if (
        not isinstance(required, list)
        or any(
            not isinstance(name, str) or (
                _EXTENSION_RE.fullmatch(name) is None
                and not (enable_rfc0016 and name == OUTCOME_VALUES_EXTENSION)
            )
            for name in required
        )
        or len(set(required)) != len(required)
    ):
        raise EvaluationInputError("metadata.requiredExtensions is invalid")

    if "reviews" in value:
        reviews = value["reviews"]
        if not isinstance(reviews, list):
            raise EvaluationInputError("metadata.reviews must be an array")
        for index, review in enumerate(reviews):
            _validate_object(
                review,
                f"metadata review {index}",
                required={"reviewer", "reviewedAt", "disposition"},
                allowed={"reviewer", "reviewedAt", "disposition", "note"},
            )
            _require_non_empty_string(
                review["reviewer"], f"metadata review {index} reviewer"
            )
            _validate_datetime(
                review["reviewedAt"], f"metadata review {index} reviewedAt"
            )
            if (
                not isinstance(review["disposition"], str)
                or review["disposition"]
                not in {"approved", "changes-requested", "rejected"}
            ):
                raise EvaluationInputError(
                    f"metadata review {index} disposition is invalid"
                )
            if "note" in review:
                _require_non_empty_string(
                    review["note"], f"metadata review {index} note"
                )

    if "extensions" in value:
        _validate_extensions(
            value["extensions"], "metadata extensions", extension_values
        )
    return frozenset(required)


def _normalize_supported_extensions(value: Iterable[str]) -> frozenset[str]:
    if isinstance(value, (str, bytes)) or value is None:
        raise EvaluationInputError("supported_extensions must be an iterable of strings")
    try:
        names = tuple(value)
    except TypeError as exc:
        raise EvaluationInputError(
            "supported_extensions must be an iterable of strings"
        ) from exc
    if any(not isinstance(name, str) for name in names):
        raise EvaluationInputError("supported extension names must be strings")
    return frozenset(names)


def _prepare_evidence(
    evidence: Any, declared: frozenset[str]
) -> dict[str, str]:
    if not isinstance(evidence, dict):
        raise EvaluationInputError("evidence availability must be a JSON object")
    result: dict[str, str] = {}
    for requirement, state in evidence.items():
        if requirement not in declared:
            raise EvaluationInputError(
                f"evidence availability names undeclared requirement {requirement!r}"
            )
        if not isinstance(state, str) or state not in {"present", "absent", "unknown"}:
            raise EvaluationInputError(
                f"evidence availability for {requirement!r} must be "
                "'present', 'absent', or 'unknown'"
            )
        result[requirement] = state
    return result


def _make_disposition(
    kind: str,
    *,
    outcome_id: str | None = None,
    reasons: set[str] | None = None,
    escalation: Mapping[str, Any] | None = None,
    direct_escalation: bool = False,
) -> dict[str, Any]:
    reasons = reasons or set()
    ordered_reasons = sorted(reasons)
    triggered_by = (
        reasons.intersection(escalation.get("triggers", []))
        if escalation is not None
        else set()
    )
    if direct_escalation:
        triggered_by.add("exception-escalation")
    handoff: dict[str, Any] = {
        "state": "requested" if triggered_by else "none",
    }
    if triggered_by:
        handoff["triggeredBy"] = sorted(triggered_by)
    result: dict[str, Any] = {
        "kind": kind,
        "reasons": ordered_reasons,
        "handoff": handoff,
    }
    if kind == "outcome":
        if outcome_id is None:
            raise AssertionError("outcome disposition requires outcome id")
        result["outcomeId"] = outcome_id
    return result
