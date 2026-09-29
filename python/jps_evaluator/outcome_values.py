"""Declaration and resolution for the opt-in draft RFC 0016 prototype."""

from __future__ import annotations

import re
from typing import Any

from .conditions import (
    EvaluationBudget,
    _pointer_tokens,
    _resolve_pointer_for_work,
    is_decimal_string,
)
from .errors import EvaluationInputError, PointerSyntaxError


OUTCOME_VALUES_EXTENSION = "org.judgmentpack.outcome-values"
_VALUE_NAME_RE = re.compile(r"[a-z][A-Za-z0-9]*")


def _admits_value(value_type: str, value: Any) -> bool:
    if value_type == "string":
        return isinstance(value, str) and all(
            not 0xD800 <= ord(character) <= 0xDFFF for character in value
        )
    if value_type == "decimal":
        return is_decimal_string(value)
    if value_type == "boolean":
        return isinstance(value, bool)
    return False


def validate_value_declaration(declaration: Any, description: str) -> None:
    """Check every source during pack preflight, including unselected outcomes."""

    if not isinstance(declaration, dict) or not declaration:
        raise EvaluationInputError(f"{description} must be a non-empty value declaration")
    for name, source in declaration.items():
        if _VALUE_NAME_RE.fullmatch(name) is None:
            raise EvaluationInputError(f"{description} has invalid value name {name!r}")
        if not isinstance(source, dict) or set(source) not in (
            {"type", "constant"}, {"type", "fromFact"}
        ):
            raise EvaluationInputError(
                f"{description} value {name!r} needs type and exactly one of "
                "constant/fromFact, with no other members"
            )
        value_type = source["type"]
        if not isinstance(value_type, str) or value_type not in {
            "string", "decimal", "boolean"
        }:
            raise EvaluationInputError(f"{description} value {name!r} has invalid type")
        if "constant" in source:
            if not _admits_value(value_type, source["constant"]):
                raise EvaluationInputError(
                    f"{description} value {name!r} constant does not satisfy {value_type}"
                )
        else:
            try:
                _pointer_tokens(source["fromFact"])
            except PointerSyntaxError as exc:
                raise EvaluationInputError(
                    f"{description} value {name!r} has invalid fromFact JSON Pointer"
                ) from exc


def resolve_values(
    declaration: dict[str, Any], facts: Any, budget: EvaluationBudget
) -> dict[str, str | bool] | None:
    """Resolve one outcome atomically; no calculation, coercion, or side effects.

    Measure all sources before checking types, so declaration member order cannot
    decide whether a limit is reached. Composite values cost one type inspection:
    they are rejected without traversing their contents. See decision 31.
    """

    selected = []
    units = 0
    for name, source in declaration.items():
        units += 1 + len(name)
        if "constant" in source:
            resolved, value = True, source["constant"]
        else:
            resolved, value, pointer_units = _resolve_pointer_for_work(
                facts, source["fromFact"]
            )
            units += pointer_units
        if resolved:
            units += 1 + len(value) if isinstance(value, str) else 1
        selected.append((name, source["type"], resolved, value))
    budget.charge(units)

    values: dict[str, str | bool] = {}
    for name, value_type, resolved, value in selected:
        if not resolved or not _admits_value(value_type, value):
            return None
        values[name] = value
    return values
