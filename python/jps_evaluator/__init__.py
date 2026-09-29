"""Core evaluator with opt-in draft RFC 0008 aggregates and RFC 0016 values."""

from .canonical import canonicalize_disposition
from .conditions import (
    DEFAULT_EVALUATION_WORK_LIMIT,
    EvaluationBudget,
    TriValue,
    compare_decimal_strings,
    evaluate_condition,
    is_decimal_string,
    json_equal,
    measure_condition_work,
    resolve_pointer,
    strong_all,
    strong_any,
    tri_not,
)
from .errors import (
    EvaluationError,
    EvaluationInputError,
    MalformedInputError,
    PackNotConformantError,
    PointerResolutionError,
    PointerSyntaxError,
    ResourceLimitError,
    UnsupportedExtensionError,
)
from .evaluator import evaluate
from .json_input import ExactJSONNumber, load_json_file, normalize_json, strict_loads

__all__ = [
    "DEFAULT_EVALUATION_WORK_LIMIT",
    "EvaluationBudget",
    "EvaluationError",
    "EvaluationInputError",
    "ExactJSONNumber",
    "MalformedInputError",
    "PackNotConformantError",
    "PointerResolutionError",
    "PointerSyntaxError",
    "ResourceLimitError",
    "TriValue",
    "UnsupportedExtensionError",
    "compare_decimal_strings",
    "canonicalize_disposition",
    "evaluate",
    "evaluate_condition",
    "is_decimal_string",
    "json_equal",
    "load_json_file",
    "normalize_json",
    "measure_condition_work",
    "resolve_pointer",
    "strict_loads",
    "strong_all",
    "strong_any",
    "tri_not",
]
