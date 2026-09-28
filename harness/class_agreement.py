#!/usr/bin/env python3
"""Cross-implementation agreement over the Core 0.2.0-draft evaluation corpus.

Runs every row of the frozen corpus (reference/conformance-evaluation/manifest.json)
through BOTH implementations and compares the two §8.3 canonical dispositions to each
other, byte for byte. Each implementation's agreement with the manifest is asserted by
its own test suite; this driver checks the implementations against each other, which is
the RFC 0006 evidence shape. A divergence is adjudicated against the TEXT, never by
preferring one implementation.

Usage: class_agreement.py <go-binary> <python-repo-dir>
"""
import json
import os
import subprocess
import sys
import tempfile

def main():
    gobin, pyrepo = sys.argv[1], sys.argv[2]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = os.path.join(root, "reference", "conformance-evaluation")
    manifest = json.load(open(os.path.join(base, "manifest.json")))
    agree, rows = 0, []
    for case in manifest["cases"]:
        pack = os.path.join(base, os.path.basename(case["pack"]))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(case["facts"], f)
            facts = f.name
        evidence = None
        if case.get("evidenceAvailability") is not None:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                json.dump(case["evidenceAvailability"], f)
                evidence = f.name
        goargs = [gobin, "experimental", "evaluate", pack, "--facts", facts, "--format", "json"]
        pyargs = [sys.executable, "-m", "jps_evaluator", "--pack", pack, "--facts", facts]
        if evidence:
            goargs += ["--evidence", evidence]
            pyargs += ["--evidence", evidence]
        for ext in case.get("supportedExtensions", []):
            goargs += ["--supported-extension", ext]
            pyargs += ["--supported-extension", ext]
        g = subprocess.run(goargs, capture_output=True, text=True, timeout=60)
        p = subprocess.run(pyargs, capture_output=True, text=True, timeout=60, cwd=pyrepo)

        def disposition(proc):
            if proc.returncode != 0:
                return ("error", (proc.stdout + proc.stderr)[:200])
            member = json.loads(proc.stdout).get("disposition")
            if member is None:
                return ("error", "no disposition member")
            return ("ok", json.dumps(member, separators=(",", ":"), sort_keys=False))

        gd, pd = disposition(g), disposition(p)
        ok = gd == pd and gd[0] == "ok"
        agree += ok
        rows.append((case["id"], ok, gd, pd))
        os.unlink(facts)
        if evidence:
            os.unlink(evidence)
    if not rows:
        print(
            "refused: corpus ran zero rows; nothing was compared, "
            "so no agreement can be reported",
            file=sys.stderr,
        )
        return 1
    for cid, ok, gd, pd in rows:
        print(f"{'AGREE' if ok else 'DIFF':7s} {cid}")
        if not ok:
            print(f"        go={gd}\n        py={pd}")
    print(f"\n{agree}/{len(rows)} rows byte-agree between implementations")
    return 0 if agree == len(rows) else 1

if __name__ == "__main__":
    raise SystemExit(main())
