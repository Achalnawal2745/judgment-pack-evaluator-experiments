#!/usr/bin/env python3
"""Cross-implementation agreement on draft RFC 0016 (outcome values).

Runs every row of rfc0016_cases.json through BOTH implementations and compares three
things: what the Go reference runtime answered, what the clean-room Python evaluator
answered, and the answer the RFC's text gives for the row. The rows are the cases the RFC
lists under Conformance and Examples. They are in no corpus, and nothing here is a corpus
result or evidence for a conformance claim.

A disposition is compared BYTE FOR BYTE, as each implementation wrote it: the RFC extends
the byte-identity requirement of Core §8.3 to the new member. The bytes are cut out of each
implementation's output and are never decoded and written again, which would compare what
this driver wrote. An error is compared by its Core §8.4 class alone: §8.4 leaves the
transport of an error undefined, and the two implementations differ on it.

Each row gets one verdict:

  matches-rfc            both agree with each other and with the RFC's answer
  AGREE-OFF-RFC          both agree with each other, and not with the RFC's answer
  DIVERGENT              the two implementations differ

A divergence is adjudicated against the TEXT, never by making one implementation copy the
other. A row where both agree off the RFC's answer is a finding about the RFC or about both
implementations, and is reported as one. The run fails on any verdict in capitals that the
cases file does not name under "known", with the reason it gives there. A row named there
that does not get the verdict it names fails the run too, so the list cannot go stale.

Both implementations are opted in for a row whose "optIn" is true: the Go runtime with
`--rfc0016-outcome-values`, the Python evaluator with `--enable-rfc0016`. A row whose
"optIn" is false is run with neither flag: it is a row the RFC writes for an implementation
that does not support the extension.

Usage: rfc0016_harness.py <go-binary> <python-repo-dir> [<cases.json>] [--json-out FILE]
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def member_bytes(text, name):
    """The text of one member of the JSON object `text`, as it is written there.

    The object is scanned, not decoded and re-encoded. Returns None where the text is not
    one JSON object or has no such member at its top level.
    """
    decoder = json.JSONDecoder()
    at = 0
    while at < len(text) and text[at] in " \t\r\n":
        at += 1
    if at >= len(text) or text[at] != "{":
        return None
    at += 1
    while True:
        while at < len(text) and text[at] in " \t\r\n,":
            at += 1
        if at >= len(text) or text[at] == "}":
            return None
        try:
            key, at = decoder.raw_decode(text, at)
        except ValueError:
            return None
        while at < len(text) and text[at] in " \t\r\n":
            at += 1
        if at >= len(text) or text[at] != ":":
            return None
        at += 1
        while at < len(text) and text[at] in " \t\r\n":
            at += 1
        try:
            _, end = decoder.raw_decode(text, at)
        except ValueError:
            return None
        if key == name:
            return text[at:end]
        at = end


def answer_of(result_text, error_text, error_member):
    """What one implementation answered: ("disposition", bytes), ("error", class),
    ("both", class) where an error came with a disposition, which §8.4 forbids, or
    ("unparsed", detail)."""
    disposition = member_bytes(result_text, "disposition")
    error = None
    raw = member_bytes(error_text, error_member)
    if raw is not None:
        try:
            decoded = json.loads(raw)
        except ValueError:
            decoded = None
        if isinstance(decoded, dict) and isinstance(decoded.get("class"), str):
            error = decoded["class"]
    if error is not None and disposition is not None:
        return ("both", error)
    if error is not None:
        return ("error", error)
    if disposition is not None:
        return ("disposition", disposition)
    return ("unparsed", (result_text + error_text)[:200])


def expected_of(case):
    expected = case["expected"]
    if "disposition" in expected:
        return ("disposition", expected["disposition"])
    return ("error", expected["errorClass"])


def verdict_of(go, python, expected):
    if go != python or go[0] in ("both", "unparsed"):
        return "DIVERGENT"
    if go != expected:
        return "AGREE-OFF-RFC"
    return "matches-rfc"


def _file(directory, name, text):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def run_case(gobin, pyrepo, case):
    with tempfile.TemporaryDirectory() as directory:
        pack = _file(directory, "pack.json", case["pack"])
        facts = _file(directory, "facts.json", case["facts"])
        goargs = [gobin, "experimental", "evaluate", pack, "--facts", facts, "--format", "json"]
        pyargs = [sys.executable, "-m", "jps_evaluator", "--pack", pack, "--facts", facts]
        if case.get("evidenceAvailability") is not None:
            evidence = _file(directory, "evidence.json", case["evidenceAvailability"])
            goargs += ["--evidence", evidence]
            pyargs += ["--evidence", evidence]
        if case["optIn"]:
            goargs.append("--rfc0016-outcome-values")
            pyargs.append("--enable-rfc0016")
        # The Go runtime consults a project configuration in the directory it runs in. The
        # rows are run in the empty directory that holds their documents, so none is found.
        g = subprocess.run(goargs, capture_output=True, text=True, timeout=60, cwd=directory)
        environment = dict(os.environ, PYTHONPATH=os.path.abspath(pyrepo), PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run(pyargs, capture_output=True, text=True, timeout=60, cwd=directory, env=environment)
    # Go writes a result and an error to stdout; Python a result to stdout and an error to stderr.
    return (answer_of(g.stdout, g.stdout, "evaluationError"),
            answer_of(p.stdout, p.stderr, "error"))


def main(argv):
    arguments = [a for a in argv[1:] if not a.startswith("--json-out")]
    json_out = None
    for index, argument in enumerate(argv):
        if argument == "--json-out":
            json_out = argv[index + 1]
            arguments.remove(json_out)
    if len(arguments) not in (2, 3):
        print(__doc__.split("Usage:")[1].strip(), file=sys.stderr)
        return 2
    gobin, pyrepo = os.path.abspath(arguments[0]), arguments[1]
    cases_path = arguments[2] if len(arguments) == 3 else os.path.join(HERE, "rfc0016_cases.json")
    document = json.load(open(cases_path, encoding="utf-8"))
    cases, known = document["cases"], document.get("known", {})
    if not cases:
        print("refused: the cases file holds zero rows; nothing was compared, so no agreement "
              "can be reported", file=sys.stderr)
        return 1
    unknown = sorted(set(known) - {case["id"] for case in cases})
    if unknown:
        print("refused: \"known\" names rows the cases file does not hold: %s" % ", ".join(unknown),
              file=sys.stderr)
        return 1
    rows, counts, failed = [], {}, []
    for case in cases:
        go, python = run_case(gobin, pyrepo, case)
        expected = expected_of(case)
        verdict = verdict_of(go, python, expected)
        counts[verdict] = counts.get(verdict, 0) + 1
        named = known.get(case["id"], {}).get("verdict", "matches-rfc")
        if verdict != named:
            failed.append(case["id"])
        rows.append({"id": case["id"], "origin": case["origin"], "optIn": case["optIn"],
                     "verdict": verdict, "named": named, "go": go, "python": python,
                     "expected": expected})
        print("%-14s %s" % (verdict, case["id"]))
        if verdict != "matches-rfc":
            print("               rfc    = %s: %s" % expected)
            print("               go     = %s: %s" % go)
            print("               python = %s: %s" % python)
            if case["id"] in known:
                print("               known: %s" % known[case["id"]]["reason"])
    print()
    for verdict in ("matches-rfc", "AGREE-OFF-RFC", "DIVERGENT"):
        print("%-14s %d" % (verdict, counts.get(verdict, 0)))
    print("%d rows; %d where the two implementations agree byte for byte or class for class"
          % (len(rows), len(rows) - counts.get("DIVERGENT", 0)))
    if failed:
        print("FAILED: these rows did not get the verdict the cases file names for them: %s"
              % ", ".join(failed))
    if json_out:
        with open(json_out, "w", encoding="utf-8") as handle:
            json.dump({"rows": rows, "counts": counts, "failed": failed}, handle, indent=1)
            handle.write("\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
