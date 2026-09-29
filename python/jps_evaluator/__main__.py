"""Command-line interface for ``python -m jps_evaluator``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .canonical import canonicalize_disposition
from .conditions import DEFAULT_EVALUATION_WORK_LIMIT
from .errors import EvaluationError, EvaluationInputError, PackNotConformantError
from .evaluator import _admit_pack, evaluate
from .json_input import load_json_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m jps_evaluator",
        description=(
            "Apply Judgment Pack Core evaluator semantics, optionally with the "
            "experimental RFC 0008 and RFC 0016 prototypes, to one pack."
        ),
    )
    parser.add_argument("--pack", required=True, help="path to a conformant pack JSON document")
    parser.add_argument("--facts", required=True, help="path to a facts JSON document")
    parser.add_argument("--evidence", help="path to an evidence-availability JSON object")
    parser.add_argument(
        "--supported-extension",
        action="append",
        nargs="+",
        default=[],
        metavar="NAME",
        help="declare one or more supported extension capabilities; may be repeated",
    )
    parser.add_argument(
        "--enable-rfc0008",
        action="store_true",
        help="opt in to the draft RFC 0008 exists/every/uniform prototype",
    )
    parser.add_argument(
        "--enable-rfc0016",
        action="store_true",
        help="opt in to the draft RFC 0016 outcome-values prototype",
    )
    parser.add_argument(
        "--evaluation-work-limit",
        type=int,
        default=DEFAULT_EVALUATION_WORK_LIMIT,
        metavar="UNITS",
        help=(
            "evaluation work-unit limit "
            f"(default: {DEFAULT_EVALUATION_WORK_LIMIT})"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        try:
            pack = load_json_file(args.pack)
        except EvaluationInputError as exc:
            raise PackNotConformantError(str(exc)) from exc
        _admit_pack(
            pack, enable_rfc0008=args.enable_rfc0008, enable_rfc0016=args.enable_rfc0016
        )
        facts = load_json_file(args.facts)
        evidence = load_json_file(args.evidence) if args.evidence else None
        if args.evidence and evidence is None:
            raise EvaluationInputError(
                "evidence availability must be a JSON object"
            )
        disposition = evaluate(
            pack,
            facts,
            evidence,
            supported_extensions=[
                name for group in args.supported_extension for name in group
            ],
            enable_rfc0008=args.enable_rfc0008,
            enable_rfc0016=args.enable_rfc0016,
            evaluation_work_limit=args.evaluation_work_limit,
        )
    except EvaluationError as exc:
        json.dump(
            {
                "error": {
                    "class": exc.error_class,
                    "phase": exc.phase,
                    "message": str(exc),
                },
                "experimental": True,
                "conformanceClaim": "none",
            },
            sys.stderr,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        sys.stderr.write("\n")
        return 2

    # Keep diagnostics/claim markers outside the §8.3 object. The nested member
    # is emitted from the exact RFC 8785 bytes used for corpus comparison.
    canonical = canonicalize_disposition(disposition)
    sys.stdout.buffer.write(
        b'{"conformanceClaim":"none","disposition":'
        + canonical
        + b',"experimental":true}\n'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
