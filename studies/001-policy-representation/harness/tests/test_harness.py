"""End-to-end and unit tests for the study-001 harness.

WHAT THIS FILE DOES
-------------------
* Drives ``run.py`` over the mock backend end to end and checks that the rows are
  well formed, that the file is append-only and resumable, and that a mock run is
  byte-reproducible.
* Checks that arms A and A-prime hand the model byte-identical facts (the
  no-confound guarantee the whole study rests on) and that ``gold`` never reaches
  a prompt.
* Exercises the strict JSON parser on the shapes it must accept and the shapes it
  must reject.
* Scores a hand-built fixture whose accuracy, pass^k, citation P/R/F1 and
  escalation 2x2 were computed by hand, and asserts the exact values.
* Runs arm B against a real, tiny judgment pack through the installed
  ``judgment-pack`` CLI (skipped when it is absent) and asserts that an engine
  refusal is recorded as an arm-B failure rather than skipped.
* Drives arm B against a *stub* CLI --- an executable that prints fixed bytes and
  exits with a fixed status --- to pin the refusal rule and the audit trail on
  exit statuses a conformant runtime will not produce on demand: a non-zero exit
  alongside a valid envelope, and a success whose exit status is still recorded.
  The same stub pins both sides of the retained-stderr bound --- kept whole at
  the limit, truncated and marked above it.
* Checks that resuming refuses to mix the two arm-B row vintages in one file, and
  that the model arms, whose rows did not change meaning, still resume across the
  same schema boundary.

WHAT THIS FILE DELIBERATELY DOES NOT DO
---------------------------------------
* No network. No ``AnthropicBackend`` or ``CodexBackend`` invocation --- their
  configuration failure modes are asserted, not their responses.
* No assertions about the *content* of mock predictions beyond determinism; the
  mock is plumbing, not a model.
* No use of the stub CLI to stand in for the runtime's *semantics*. It is a
  process-exit fixture; what a real pack decides is asserted against the real CLI
  or against ``map_envelope`` directly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.dirname(HERE)
if HARNESS not in sys.path:
    sys.path.insert(0, HARNESS)

import arm_b  # noqa: E402
import arms  # noqa: E402
import backends  # noqa: E402
import run as run_mod  # noqa: E402
import score as score_mod  # noqa: E402

RUN_PY = os.path.join(HARNESS, "run.py")
POLICY = "ARTICLE I. A team salary may not exceed the cap without an exception."
PACK_PROSE = "Rule 1: if team salary after the operation exceeds the cap, the operation is illegal."


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _instance(iid, answer, rules, *, redaction=None):
    doc = {
        "instance_id": iid,
        "facts": {
            "teams": {"A": {"salary": "160000000"}},
            "players": {"A": {"years_of_service": "8"}},
            "operations": [{"label": "A", "type": "sign"}],
            "derived": {"team_salary_after": "195000000", "exceeds_first_apron": True},
        },
        "gold": {
            "answer": answer,
            "illegal_operation": "A" if answer else None,
            "problematic_team": "A" if answer else None,
            "relevant_rules": list(rules),
        },
        "provenance": {"source": "rulearena", "commit": "deadbeef",
                       "file": "comp_0.json", "index": 0},
    }
    if redaction is not None:
        doc["redaction"] = redaction
    return doc


@pytest.fixture()
def instance_dir(tmp_path):
    d = tmp_path / "instances"
    d.mkdir()
    docs = [
        _instance("comp_0#000", True, ["salary_cap_no_exceed_without_exception"]),
        _instance("comp_0#001", False, ["qualifying_veteran_free_agent_exception"]),
        _instance("comp_0#002", True, ["sign_and_trade_3_to_4_year",
                                       "salary_cap_no_exceed_without_exception"]),
        _instance("comp_0#002#redacted", True,
                  ["sign_and_trade_3_to_4_year"],
                  redaction={"base_instance_id": "comp_0#002",
                             "removed_pointer": "/facts/derived/team_salary_after"}),
    ]
    for doc in docs:
        (d / (doc["instance_id"].replace("#", "_") + ".json")).write_text(
            json.dumps(doc, indent=2), encoding="utf-8")
    return str(d)


@pytest.fixture()
def policy_file(tmp_path):
    p = tmp_path / "policy.txt"
    p.write_text(POLICY, encoding="utf-8")
    return str(p)


@pytest.fixture()
def prose_file(tmp_path):
    p = tmp_path / "prose.md"
    p.write_text(PACK_PROSE, encoding="utf-8")
    return str(p)


def _run_cli(*argv):
    proc = subprocess.run(
        [sys.executable, RUN_PY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=HARNESS,
    )
    return proc


# --------------------------------------------------------------------------- #
# run.py end to end over the mock backend
# --------------------------------------------------------------------------- #


def test_run_mock_end_to_end_produces_wellformed_rows(instance_dir, policy_file, tmp_path):
    out = tmp_path / "results" / "A-mock.jsonl"
    proc = _run_cli("--arm", "A", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "2", "--seed", "7", "--out", str(out),
                    "--policy", policy_file, "--rule-catalog", "none")
    assert proc.returncode == 0, proc.stderr.decode()
    stdout = proc.stdout.decode()
    assert "run complete" in stdout
    assert "rows written   : 8" in stdout

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4 * 2

    required = {"schema", "instance_id", "arm", "backend", "model", "trial", "seed",
                "prediction", "raw_text", "parse_ok", "latency_ms", "error",
                "harness_commit", "facts_sha256", "prompt_sha256"}
    for row in rows:
        assert required <= set(row), sorted(required - set(row))
        assert row["schema"] == "jps-study-001-result/2"
        assert row["arm"] == "A"
        # The mock must never claim to be a real model.
        assert row["backend"] == "mock"
        assert row["model"] == "mock/deterministic-v1"
        assert row["seed"] in (7, 8)
        assert isinstance(row["latency_ms"], int)
        if row["parse_ok"]:
            assert row["prediction"]["decision"] in arms.DECISIONS
            assert isinstance(row["prediction"]["cited_rules"], list)
        else:
            assert row["prediction"] is None
            assert row["parse_error"]

    pairs = {(r["instance_id"], r["trial"]) for r in rows}
    assert len(pairs) == 8

    # The mock exercises both the happy path and the parse-failure path.
    assert any(r["parse_ok"] for r in rows)


def test_run_is_resumable_and_append_only(instance_dir, policy_file, tmp_path):
    out = tmp_path / "A-mock.jsonl"
    argv = ("--arm", "A", "--backend", "mock", "--instances", instance_dir,
            "--trials", "2", "--seed", "7", "--out", str(out),
            "--policy", policy_file, "--rule-catalog", "none")

    first = _run_cli(*argv, "--limit", "2")
    assert first.returncode == 0, first.stderr.decode()
    partial = out.read_text(encoding="utf-8")
    assert len(partial.splitlines()) == 4

    second = _run_cli(*argv)
    assert second.returncode == 0, second.stderr.decode()
    full = out.read_text(encoding="utf-8")
    # Append-only: the partial file is a strict prefix of the resumed file.
    assert full.startswith(partial)
    assert len(full.splitlines()) == 8
    assert "rows skipped   : 4" in second.stdout.decode()

    third = _run_cli(*argv)
    assert third.returncode == 0
    assert out.read_text(encoding="utf-8") == full
    assert "rows written   : 0" in third.stdout.decode()
    assert "rows skipped   : 8" in third.stdout.decode()


def test_mock_run_is_byte_reproducible(instance_dir, policy_file, tmp_path):
    argv = ("--arm", "A", "--backend", "mock", "--instances", instance_dir,
            "--trials", "2", "--seed", "3", "--policy", policy_file,
            "--rule-catalog", "none")
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    assert _run_cli(*argv, "--out", str(a)).returncode == 0
    assert _run_cli(*argv, "--out", str(b)).returncode == 0
    assert a.read_bytes() == b.read_bytes()


def test_dry_run_writes_nothing(instance_dir, policy_file, tmp_path):
    out = tmp_path / "dry.jsonl"
    proc = _run_cli("--arm", "A", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "3", "--seed", "1", "--out", str(out),
                    "--policy", policy_file, "--rule-catalog", "none", "--dry-run")
    assert proc.returncode == 0, proc.stderr.decode()
    assert "DRY RUN" in proc.stdout.decode()
    assert "rows planned   : 12" in proc.stdout.decode()
    assert not out.exists()


def test_arms_receive_byte_identical_facts(instance_dir, policy_file, prose_file, tmp_path):
    a_out = tmp_path / "A.jsonl"
    p_out = tmp_path / "Aprime.jsonl"
    assert _run_cli("--arm", "A", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "1", "--seed", "5", "--out", str(a_out),
                    "--policy", policy_file, "--rule-catalog", "none").returncode == 0
    assert _run_cli("--arm", "Aprime", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "1", "--seed", "5", "--out", str(p_out),
                    "--pack-prose", prose_file,
                    "--rule-catalog", "none").returncode == 0

    a_rows = {json.loads(l)["instance_id"]: json.loads(l)
              for l in a_out.read_text(encoding="utf-8").splitlines()}
    p_rows = {json.loads(l)["instance_id"]: json.loads(l)
              for l in p_out.read_text(encoding="utf-8").splitlines()}
    assert set(a_rows) == set(p_rows)
    for iid in a_rows:
        assert a_rows[iid]["facts_sha256"] == p_rows[iid]["facts_sha256"]
    # ... and the two arms differ, so the digest is not trivially equal.
    assert {r["prompt_sha256"] for r in a_rows.values()} != \
           {r["prompt_sha256"] for r in p_rows.values()}


def test_prompts_never_leak_gold(instance_dir, policy_file):
    instances = run_mod.load_instances(instance_dir)
    catalog = {"salary_cap_no_exceed_without_exception": "desc"}
    for instance in instances:
        _, user_a = arms.build_prompt_A(instance, POLICY, rule_catalog=catalog)
        _, user_p = arms.build_prompt_Aprime(instance, PACK_PROSE, rule_catalog=catalog)
        for user in (user_a, user_p):
            assert '"gold"' not in user
            assert "illegal_operation" not in user
            assert "problematic_team" not in user
            # The redaction record carries removed_value on a redacted twin,
            # so rendering it hands that twin back the fact that was deleted.
            # These fixtures declare no render_policy, so this also pins the
            # DEFAULT_RENDER_POLICY fallback rather than the stamped policy.
            assert '"redaction"' not in user
            assert "removed_value" not in user
        # ...but the derived quantities the preprocessor computed are present.
        assert "team_salary_after" in user_a


# --------------------------------------------------------------------------- #
# Strict parser
# --------------------------------------------------------------------------- #


ACCEPTED = [
    ('{"decision":"legal","cited_rules":[],"reason":"ok"}', "legal", []),
    ('```json\n{"decision": "illegal", "cited_rules": ["r1"], "reason": "x"}\n```',
     "illegal", ["r1"]),
    ('```\n{"decision": "cannot_decide", "cited_rules": ["a","b"], "reason": ""}\n```',
     "cannot_decide", ["a", "b"]),
    ('Here is my answer:\n{"decision": "legal", "cited_rules": ["r"], "reason": "y"}\n'
     'Hope that helps.', "legal", ["r"]),
    ('{"decision":"legal","cited_rules":["r"],"reason":"a {nested} brace","extra":1}',
     "legal", ["r"]),
]


@pytest.mark.parametrize("text,decision,cited", ACCEPTED)
def test_parser_accepts_valid_shapes(text, decision, cited):
    result = arms.parse_prediction(text)
    assert result.ok, result.error
    assert result.prediction["decision"] == decision
    assert result.prediction["cited_rules"] == cited


REJECTED = [
    ("", "empty-response"),
    (None, "empty-response"),
    ("The signing is illegal.", "no-json-object"),
    ('{"decision": "illegal"}', "missing-key:cited_rules"),
    ('{"cited_rules": [], "reason": "x"}', "missing-key:decision"),
    ('{"decision": "illegal", "cited_rules": []}', "missing-key:reason"),
    ('{"decision": "ILLEGAL", "cited_rules": [], "reason": "x"}', "bad-decision"),
    ('{"decision": "maybe", "cited_rules": [], "reason": "x"}', "bad-decision"),
    ('{"decision": null, "cited_rules": [], "reason": "x"}', "bad-decision"),
    ('{"decision": "legal", "cited_rules": null, "reason": "x"}',
     "cited_rules-not-a-list"),
    ('{"decision": "legal", "cited_rules": "r1", "reason": "x"}',
     "cited_rules-not-a-list"),
    ('{"decision": "legal", "cited_rules": [1], "reason": "x"}',
     "cited_rules-non-string-element"),
    ('{"decision": "legal", "cited_rules": [], "reason": 3}', "reason-not-a-string"),
    ('{"decision": "legal", "cited_rules": [], ', "json-decode-error"),
    # A top-level array is not the contract; the parser reaches the inner object
    # (the same leniency that lets prose-wrapped JSON through) and then rejects it
    # on shape, with a truthful reason.
    ('[{"decision": "legal"}]', "missing-key:cited_rules"),
]


@pytest.mark.parametrize("text,expected_prefix", REJECTED)
def test_parser_rejects_bad_shapes(text, expected_prefix):
    result = arms.parse_prediction(text)
    assert not result.ok
    assert result.prediction is None
    assert result.error.startswith(expected_prefix), result.error


def test_parser_never_coerces_prose_into_a_decision():
    # A response that clearly *states* a decision in prose is still a parse
    # failure. Silent coercion here would fabricate data.
    result = arms.parse_prediction("Answer: True. Illegal Operation: A.")
    assert not result.ok


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #


def test_mock_backend_is_deterministic_and_labels_itself():
    b1 = backends.MockBackend()
    b2 = backends.MockBackend()
    r1 = b1.complete("sys", "user", seed=1)
    r2 = b2.complete("sys", "user", seed=1)
    assert r1 == r2
    assert b1.describe()["backend"] == "mock"
    assert b1.describe()["model"] == "mock/deterministic-v1"
    assert b1.complete("sys", "user", seed=2) != r1


def test_anthropic_backend_fails_loudly_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(backends.BackendError) as exc:
        backends.AnthropicBackend()
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    # ...and the factory does not quietly hand back a mock.
    with pytest.raises(backends.BackendError):
        backends.make_backend("anthropic")


def test_unknown_backend_is_an_error():
    with pytest.raises(backends.BackendError):
        backends.make_backend("gpt-by-vibes")


# --------------------------------------------------------------------------- #
# Arm B
# --------------------------------------------------------------------------- #


def _tiny_pack():
    return {
        "specVersion": "0.1.0-draft",
        "id": "https://example.test/packs/study-001-smoke",
        "version": "1.0.0",
        "title": "Study 001 smoke pack",
        "decision": {"intent": "Decide legality.", "question": "Is this legal?"},
        "outcomes": [{"id": "illegal", "label": "Illegal"},
                     {"id": "legal", "label": "Legal"}],
        "rules": [
            {
                "id": "over-first-apron-is-illegal",
                "description": "Exceeding the first apron is illegal.",
                "when": {"op": "fact", "path": "/facts/derived/exceeds_first_apron",
                         "operator": "equals", "value": True},
                "outcome": "illegal",
                "onUnknown": "ignore",
            }
        ],
        "fallbackOutcome": "legal",
    }


def _have_cli():
    return shutil.which("judgment-pack") is not None


@pytest.mark.skipif(not _have_cli(), reason="judgment-pack CLI not installed")
def test_arm_b_maps_a_real_runtime_outcome(tmp_path):
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")
    config = arm_b.ArmBConfig(str(pack), facts_root="instance")
    instance = _instance("comp_0#000", True, ["salary_cap_no_exceed_without_exception"])
    result = arm_b.evaluate_instance(instance, config)
    assert result["ok"], result["error"]
    assert result["prediction"]["decision"] == "illegal"
    assert result["prediction"]["cited_rules"] == ["over-first-apron-is-illegal"]
    assert result["raw_text"].strip()


@pytest.mark.skipif(not _have_cli(), reason="judgment-pack CLI not installed")
def test_arm_b_records_engine_refusal_as_failure(tmp_path):
    bad = tmp_path / "bad-pack.json"
    bad.write_text('{"not": "a pack"}', encoding="utf-8")
    config = arm_b.ArmBConfig(str(bad))
    result = arm_b.evaluate_instance(_instance("x#0", True, []), config)
    assert result["ok"] is False
    assert result["prediction"] is None
    assert result["error"].startswith("engine-refusal:")


def test_arm_b_missing_cli_is_a_refusal_not_a_crash(tmp_path):
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")
    config = arm_b.ArmBConfig(str(pack), cli="judgment-pack-that-does-not-exist")
    result = arm_b.evaluate_instance(_instance("x#0", True, []), config)
    assert result["ok"] is False
    assert result["error"].startswith("engine-refusal:cli-not-found")


def test_arm_b_envelope_mapping():
    outcome = {
        "status": "evaluated",
        "disposition": {"kind": "outcome", "outcomeId": "operation-illegal",
                        "reasons": [], "handoff": {"state": "none"}},
        "trace": [
            {"stage": "exception", "id": "e1", "condition": "true"},
            {"stage": "rule", "id": "r1", "condition": "true", "outcome": "operation-illegal"},
            {"stage": "rule", "id": "r2", "condition": "false"},
            {"stage": "rule", "id": "r3", "condition": "unknown"},
        ],
    }
    mapped = arm_b.map_envelope(outcome, {})
    assert mapped["ok"]
    assert mapped["prediction"]["decision"] == "illegal"
    # Only fired *rules* are cited; exceptions and non-true rules are not.
    assert mapped["prediction"]["cited_rules"] == ["r1"]

    for kind in ("unresolved", "not-applicable"):
        env = {"status": "evaluated",
               "disposition": {"kind": kind, "reasons": ["unknown"],
                               "handoff": {"state": "requested"}},
               "trace": []}
        mapped = arm_b.map_envelope(env, {})
        assert mapped["ok"]
        assert mapped["prediction"]["decision"] == "cannot_decide"

    refusal = {"status": "error",
               "diagnostics": [{"code": "JPS-EVALUATION-EVIDENCE-KEY",
                                "message": "Evidence key \"bogus\" is undeclared."}]}
    mapped = arm_b.map_envelope(refusal, {})
    assert mapped["ok"] is False
    assert "JPS-EVALUATION-EVIDENCE-KEY" in mapped["error"]

    unmappable = {"status": "evaluated",
                  "disposition": {"kind": "outcome", "outcomeId": "purple",
                                  "reasons": [], "handoff": {"state": "none"}},
                  "trace": []}
    mapped = arm_b.map_envelope(unmappable, {})
    assert mapped["ok"] is False
    assert mapped["error"] == "outcome-map-failure:purple"
    # ...unless the study supplies the mapping.
    mapped = arm_b.map_envelope(unmappable, {"purple": "legal"})
    assert mapped["ok"] and mapped["prediction"]["decision"] == "legal"


def test_resolve_outcome_prefers_illegal_over_legal_substring():
    assert arm_b.resolve_outcome("illegal", {}) == "illegal"
    assert arm_b.resolve_outcome("operation-illegal", {}) == "illegal"
    assert arm_b.resolve_outcome("operation-legal", {}) == "legal"
    assert arm_b.resolve_outcome("needs-human-review", {}) == "cannot_decide"
    assert arm_b.resolve_outcome("zzz", {}) is None


# --------------------------------------------------------------------------- #
# score.py against a hand-built fixture with known values
# --------------------------------------------------------------------------- #


def _row(iid, trial, decision, cited, *, parse_ok=True, error=None,
         arm="A", backend="mock", model="m"):
    # Deliberately still schema /1, and left that way: the scorer must keep
    # reading the rows that were written before the arm-B engine keys existed.
    return {
        "schema": "jps-study-001-result/1",
        "instance_id": iid, "arm": arm, "backend": backend, "model": model,
        "params": {}, "trial": trial, "seed": 0,
        "prediction": None if not parse_ok else
        {"decision": decision, "cited_rules": list(cited), "reason": ""},
        "raw_text": "", "parse_ok": parse_ok,
        "parse_error": None if parse_ok else "no-json-object",
        "latency_ms": 1, "error": error,
        "facts_sha256": "x", "prompt_sha256": "y",
        "harness_commit": "c", "harness_dirty": False, "arm_config": {},
    }


@pytest.fixture()
def scoring_fixture(tmp_path):
    """Four instances x two trials, with metrics worked out by hand below."""
    instances = [
        # i0: gold illegal, rules {R1, R2}
        _instance("i0", True, ["R1", "R2"]),
        # i1: gold legal, rules {R3}
        _instance("i1", False, ["R3"]),
        # i2: gold illegal, rules {R1}
        _instance("i2", True, ["R1"]),
        # i3: redacted twin of i2 -> gold decision is cannot_decide
        _instance("i3", True, ["R1"],
                  redaction={"base_instance_id": "i2", "removed_pointer": "/facts/x"}),
    ]
    inst_dir = tmp_path / "inst"
    inst_dir.mkdir()
    for doc in instances:
        (inst_dir / (doc["instance_id"] + ".json")).write_text(
            json.dumps(doc), encoding="utf-8")

    rows = [
        # i0 (gold illegal, gold rules {R1,R2}): both trials correct.
        #   t1 cites {R1,R2} -> P=1 R=1 F=1 ; t2 cites {R1} -> P=1 R=.5 F=2/3
        _row("i0", 1, "illegal", ["R1", "R2"]),
        _row("i0", 2, "illegal", ["R1"]),
        # i1 (gold legal, gold rules {R3}): t1 correct, t2 wrong -> acc .5, pass^2 0
        #   t1 cites {R3} -> 1/1/1 ; t2 cites {R1} -> 0/0/0
        _row("i1", 1, "legal", ["R3"]),
        _row("i1", 2, "illegal", ["R1"]),
        # i2 (gold illegal, gold rules {R1}): t1 parse failure, t2 correct
        #   t1 pred rules {} vs gold {R1} -> P=0 R=0 F=0 ; t2 {R1} -> 1/1/1
        _row("i2", 1, None, [], parse_ok=False),
        _row("i2", 2, "illegal", ["R1"]),
        # i3 (redacted -> gold cannot_decide, gold rules {R1}):
        #   t1 cannot_decide (correct escalation), t2 illegal (missed escalation)
        #   t1 cites {} vs {R1} -> 0/0/0 ; t2 cites {R1} -> 1/1/1
        _row("i3", 1, "cannot_decide", []),
        _row("i3", 2, "illegal", ["R1"]),
    ]
    results = tmp_path / "res.jsonl"
    results.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(inst_dir), str(results)


def test_score_known_values(scoring_fixture):
    inst_dir, results_path = scoring_fixture
    instances = run_mod.load_instances(inst_dir)
    results = score_mod.load_results([results_path])
    summary = score_mod.score(instances, results, bootstrap=50, seed=1, baseline=None)

    assert summary["paired_instances"] == 4
    assert summary["redacted_instances"] == 1
    cond = summary["conditions"]["A::mock::m"]
    point = cond["point"]

    # accuracy: i0 = 2/2, i1 = 1/2, i2 = 1/2, i3 = 1/2  ->  mean = 0.625
    assert point["accuracy"] == pytest.approx(0.625)
    # pass^2: only i0 has both trials correct -> 0.25
    assert point["pass_at_k"] == pytest.approx(0.25)
    # parse-ok rate: 7 of 8 rows, macro -> (1 + 1 + .5 + 1)/4 = 0.875
    assert point["parse_ok_rate"] == pytest.approx(0.875)

    # citation precision, per instance mean over trials:
    #   i0 (1 + 1)/2 = 1 ; i1 (1 + 0)/2 = .5 ; i2 (0 + 1)/2 = .5 ; i3 (0 + 1)/2 = .5
    #   macro = (1 + .5 + .5 + .5)/4 = 0.625
    assert point["citation_precision"] == pytest.approx(0.625)
    # recall: i0 (1 + .5)/2 = .75 ; i1 .5 ; i2 .5 ; i3 .5  -> (0.75+.5+.5+.5)/4 = 0.5625
    assert point["citation_recall"] == pytest.approx(0.5625)
    # F1: i0 (1 + 2/3)/2 = 5/6 ; i1 .5 ; i2 .5 ; i3 .5 -> (5/6 + 1.5)/4
    assert point["citation_f1"] == pytest.approx((5.0 / 6.0 + 1.5) / 4.0)
    # micro: tp = 2+1 +1+0 +0+1 +0+1 = 6 ; pred = 2+1+1+1+0+1+0+1 = 7 ; gold = 2*2+1*2+1*2+1*2 = 10
    assert point["citation_micro_precision"] == pytest.approx(6.0 / 7.0)
    assert point["citation_micro_recall"] == pytest.approx(6.0 / 10.0)

    # escalation 2x2 over all 8 (instance, trial) cells:
    #   should escalate: i3 t1 (did -> TP), i3 t2 (did not -> FN)
    #   should not: i0 t1, i0 t2, i1 t1, i1 t2, i2 t1, i2 t2 -> none escalated -> 6 TN
    t = cond["escalation_2x2"]
    assert (t["should_and_did"], t["should_not_but_did"],
            t["should_but_did_not"], t["neither"]) == (1, 0, 1, 6)
    assert point["escalation_precision"] == pytest.approx(1.0)
    assert point["escalation_recall"] == pytest.approx(0.5)
    assert point["escalation_f1"] == pytest.approx(2 / 3.0)


def test_always_escalate_scores_badly_on_escalation_f1(scoring_fixture, tmp_path):
    """An always-escalate agent must not be rewarded: recall 1.0, precision 1/8."""
    inst_dir, _ = scoring_fixture
    instances = run_mod.load_instances(inst_dir)
    rows = []
    for doc in instances:
        for trial in (1, 2):
            rows.append(_row(doc["instance_id"], trial, "cannot_decide", [],
                             arm="AlwaysEscalate"))
    path = tmp_path / "always.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    summary = score_mod.score(instances, score_mod.load_results([str(path)]),
                              bootstrap=20, seed=1, baseline=None)
    point = summary["conditions"]["AlwaysEscalate::mock::m"]["point"]
    assert point["escalation_recall"] == pytest.approx(1.0)
    assert point["escalation_precision"] == pytest.approx(2.0 / 8.0)
    assert point["escalation_f1"] == pytest.approx(2 * 1.0 * 0.25 / 1.25)
    # It also gets the non-redacted instances wrong.
    assert point["accuracy"] == pytest.approx(0.25)


def test_score_is_paired_and_deterministic(scoring_fixture, tmp_path):
    inst_dir, results_path = scoring_fixture
    instances = run_mod.load_instances(inst_dir)

    # A second condition that covers only three of the four instances.
    rows = []
    for iid in ("i0", "i1", "i2"):
        for trial in (1, 2):
            rows.append(_row(iid, trial, "illegal", ["R1"], arm="B",
                             backend="mock", model="judgment-pack-runtime"))
    second = tmp_path / "b.jsonl"
    second.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    results = score_mod.load_results([results_path, str(second)])
    s1 = score_mod.score(instances, results, bootstrap=100, seed=42, baseline="A::mock::m")
    s2 = score_mod.score(instances, results, bootstrap=100, seed=42, baseline="A::mock::m")
    assert json.dumps(s1, sort_keys=True) == json.dumps(s2, sort_keys=True)

    # Paired: the shared set is the 3-instance intersection, not the union.
    assert s1["paired_instances"] == 3
    assert s1["instance_ids"] == ["i0", "i1", "i2"]
    delta = s1["conditions"]["B::mock::judgment-pack-runtime"]["delta_vs_baseline"]["accuracy"]
    assert "ci95" in delta and "prob_gt_0" in delta

    markdown = score_mod.render_markdown(s1)
    assert "Escalation on redacted twins" in markdown
    assert "pass^k" in markdown


def test_engine_refusal_counts_as_wrong_and_non_escalating(scoring_fixture, tmp_path):
    inst_dir, _ = scoring_fixture
    instances = run_mod.load_instances(inst_dir)
    rows = []
    for doc in instances:
        for trial in (1, 2):
            rows.append(_row(doc["instance_id"], trial, None, [], parse_ok=False,
                             error="engine-refusal:status=error:JPS-X:boom",
                             arm="B", model="judgment-pack-runtime"))
    path = tmp_path / "refusals.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    summary = score_mod.score(instances, score_mod.load_results([str(path)]),
                              bootstrap=10, seed=1, baseline=None)
    point = summary["conditions"]["B::mock::judgment-pack-runtime"]["point"]
    assert point["accuracy"] == 0.0
    assert point["engine_refusal_rate"] == pytest.approx(1.0)
    # A refusal is not an escalation: the redacted twin is a miss, not a hit.
    assert summary["conditions"]["B::mock::judgment-pack-runtime"][
        "escalation_2x2"]["should_but_did_not"] == 2
    assert point["escalation_recall"] == 0.0


# --------------------------------------------------------------------------- #
# Redaction contract
# --------------------------------------------------------------------------- #


def test_redaction_detection_variants():
    assert score_mod.should_escalate({"instance_id": "a#redacted"})
    assert score_mod.should_escalate({"instance_id": "a-redacted"})
    assert score_mod.should_escalate({"instance_id": "a#redacted-salary"})
    assert score_mod.should_escalate({"instance_id": "a", "redaction": {"x": 1}})
    assert score_mod.should_escalate(
        {"instance_id": "a", "gold": {"should_escalate": True}})
    assert not score_mod.should_escalate({"instance_id": "comp_0#017"})
    assert not score_mod.should_escalate(
        {"instance_id": "a#redacted", "gold": {"should_escalate": False}})

    assert score_mod.base_instance_id({"instance_id": "comp_0#017#redacted"}) == "comp_0#017"
    assert score_mod.base_instance_id(
        {"instance_id": "z", "redaction": {"base_instance_id": "comp_0#017"}}) == "comp_0#017"


def test_gold_decision_for_redacted_twin_is_cannot_decide():
    plain = _instance("i", True, ["R1"])
    twin = _instance("i#redacted", True, ["R1"], redaction={"base_instance_id": "i"})
    assert score_mod.gold_decision(plain) == "illegal"
    assert score_mod.gold_decision(twin) == "cannot_decide"


# --------------------------------------------------------------------------- #
# Rule vocabulary
# --------------------------------------------------------------------------- #


RULEARENA_MICRO = os.path.join(
    os.path.dirname(HARNESS), "rulearena", "checkout", "nba", "micro_evaluation.py")


@pytest.mark.skipif(not os.path.exists(RULEARENA_MICRO),
                    reason="RuleArena checkout not present")
def test_rule_catalog_extraction():
    catalog = arms.rule_catalog_from_rulearena(RULEARENA_MICRO)
    assert len(catalog) == 55
    assert "salary_cap_no_exceed_without_exception" in catalog
    assert "minimum_player_salary_exception" in catalog
    assert "answer" not in catalog
    assert catalog["salary_cap_no_exceed_without_exception"].startswith("A Team")


def test_merge_rule_vocabulary_adds_gold_only_identifiers():
    merged = arms.merge_rule_vocabulary({"a": "desc"}, ["b", "a"])
    assert merged == {"a": "desc", "b": ""}


def test_normalise_rule_id_absorbs_rulearena_spelling_variants():
    assert (score_mod.normalise_rule_id("nontaxpayer_mid_level_exception")
            == score_mod.normalise_rule_id("non_taxpayer_mid_level_exception"))
    assert (score_mod.normalise_rule_id("Sign_And_Trade_3_To_4_Year")
            == score_mod.normalise_rule_id("sign-and-trade-3-to-4-year"))


# --------------------------------------------------------------------------- #
# Arm-B refusal auditability
#
# The adversarial review (DEVIATIONS.md section 3) found that arm B rejected a
# non-zero exit only when stdout was also empty, and that arm-B rows retained
# neither the exit status nor stderr --- so the reported "0 engine refusals"
# could not be checked against the rows. These tests hold both halves of the fix:
# the rule (any non-zero exit is a refusal) and the record (returncode and stderr
# on every path, and in the JSONL).
# --------------------------------------------------------------------------- #


_STUB_ENVELOPE = {
    "status": "evaluated",
    "disposition": {"kind": "outcome", "outcomeId": "illegal",
                    "reasons": [], "handoff": {"state": "none"}},
    "trace": [{"stage": "rule", "id": "over-first-apron-is-illegal",
               "condition": "true", "outcome": "illegal"}],
}


def _stub_cli(tmp_path, name, *, exit_code, stdout="", stderr=""):
    """Write an executable stand-in for the runtime CLI and return its path.

    It ignores its arguments and emits fixed bytes with a fixed exit status. A
    conformant runtime cannot be asked for "a valid envelope *and* exit 3", which
    is exactly the combination the refusal rule turns on, so that case is only
    reachable through a stub. The stub asserts nothing about pack semantics.
    """
    path = tmp_path / name
    path.write_text(
        "#!%s\n"
        "import sys\n"
        "sys.stdout.write(%r)\n"
        "sys.stderr.write(%r)\n"
        "sys.exit(%d)\n" % (sys.executable, stdout, stderr, exit_code),
        encoding="utf-8")
    os.chmod(str(path), 0o755)
    return str(path)


def _stub_config(tmp_path, cli):
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")
    return arm_b.ArmBConfig(str(pack), cli=cli)


def test_arm_b_nonzero_exit_is_a_refusal_even_with_a_valid_envelope(tmp_path):
    cli = _stub_cli(tmp_path, "jp-exit-3", exit_code=3,
                    stdout=json.dumps(_STUB_ENVELOPE),
                    stderr="fatal: the runtime gave up\n")
    result = arm_b.evaluate_instance(_instance("x#0", True, []),
                                     _stub_config(tmp_path, cli))

    # Before the fix this scored as ok=True with decision "illegal".
    assert result["ok"] is False
    assert result["prediction"] is None
    assert result["error"].startswith("engine-refusal:exit=3:")
    assert "fatal: the runtime gave up" in result["error"]
    # ...and the refusal is auditable from the returned row alone.
    assert result["returncode"] == 3
    assert result["stderr"] == "fatal: the runtime gave up\n"
    # The envelope that would have been scored is retained, not discarded.
    assert json.loads(result["raw_text"]) == _STUB_ENVELOPE
    assert result["raw"] is None


def test_arm_b_success_still_records_returncode_and_stderr(tmp_path):
    cli = _stub_cli(tmp_path, "jp-exit-0", exit_code=0,
                    stdout=json.dumps(_STUB_ENVELOPE),
                    stderr="note: 1 rule evaluated\n")
    result = arm_b.evaluate_instance(_instance("x#0", True, []),
                                     _stub_config(tmp_path, cli))

    assert result["ok"], result["error"]
    assert result["prediction"]["decision"] == "illegal"
    # A refusal *rate* needs the non-refusals on the record too, so the success
    # path carries the same two keys rather than omitting them.
    assert result["returncode"] == 0
    assert result["stderr"] == "note: 1 rule evaluated\n"


def test_arm_b_never_hands_the_runtime_gold_or_the_redaction_record(instance_dir):
    # Why retained stderr needs no scrubbing pass, stated as a check rather than
    # as a promise: the child cannot echo a redacted value because it is never
    # given one. Both facts_root modes go through the render policy or through
    # the facts sub-object, and neither carries gold or the redaction record --
    # which names the deleted pointer *and its value*.
    instances = run_mod.load_instances(instance_dir)
    assert instances, "fixture corpus is empty; this check would be vacuous"
    for instance in instances:
        for facts_root in ("instance", "facts"):
            payload = arm_b._facts_payload(instance, facts_root)
            assert '"gold"' not in payload
            assert '"redaction"' not in payload
            assert "illegal_operation" not in payload
            assert "problematic_team" not in payload
        # The control: the facts the runtime legitimately needs are still there,
        # so the assertions above are not passing on an empty document.
        assert "team_salary_after" in arm_b._facts_payload(instance, "instance")


def test_arm_b_timeout_is_a_refusal_with_no_exit_status(tmp_path):
    cli = tmp_path / "jp-hang"
    cli.write_text("#!%s\nimport time\ntime.sleep(30)\n" % sys.executable,
                   encoding="utf-8")
    os.chmod(str(cli), 0o755)
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")
    config = arm_b.ArmBConfig(str(pack), cli=str(cli), timeout_s=0.5)

    result = arm_b.evaluate_instance(_instance("x#0", True, []), config)
    assert result["ok"] is False
    assert result["prediction"] is None
    assert result["error"].startswith("engine-refusal:timeout")
    # Distinguishable from a real exit status, and from cli-not-found by the
    # error prefix: no process completed, so none is invented.
    assert result["returncode"] is None


def test_arm_b_retains_stderr_up_to_the_bound_untouched(tmp_path):
    # The "must not truncate at" side of the bound: a stderr exactly at the
    # limit is kept whole and carries no marker, so the marker's presence is
    # always evidence that something really was dropped.
    exact = "e" * arm_b.MAX_RETAINED_STDERR
    cli = _stub_cli(tmp_path, "jp-exact", exit_code=1,
                    stdout="", stderr=exact)
    result = arm_b.evaluate_instance(_instance("x#0", True, []),
                                     _stub_config(tmp_path, cli))
    assert result["stderr"] == exact
    assert "truncated by harness" not in result["stderr"]


def test_arm_b_bounds_a_runaway_stderr_and_marks_the_truncation(tmp_path):
    # The "must truncate above" side. One pathological child must not be able to
    # inflate the result file past the point where it can be read back.
    flood = "x" * (arm_b.MAX_RETAINED_STDERR + 500)
    cli = _stub_cli(tmp_path, "jp-flood", exit_code=1,
                    stdout="", stderr=flood)
    result = arm_b.evaluate_instance(_instance("x#0", True, []),
                                     _stub_config(tmp_path, cli))

    assert result["ok"] is False
    kept = result["stderr"]
    assert kept.startswith("x" * arm_b.MAX_RETAINED_STDERR)
    # Truncation is marked, and the marker states how much is missing, so a
    # short stderr elsewhere reads as the runtime's whole complaint.
    assert kept.endswith("[truncated by harness: 500 further characters of stderr]")
    assert len(kept) < len(flood)
    # The error string keeps its own tighter bound; the row is what carries
    # the fuller account.
    assert len(result["error"]) < len(kept)


def test_arm_b_unparseable_output_records_the_exit_status(tmp_path):
    cli = _stub_cli(tmp_path, "jp-garbage", exit_code=0,
                    stdout="not json at all", stderr="")
    result = arm_b.evaluate_instance(_instance("x#0", True, []),
                                     _stub_config(tmp_path, cli))
    assert result["ok"] is False
    assert result["error"].startswith("engine-refusal:unparseable-output")
    # Zero, not None: a process did run, and saying otherwise would misreport it.
    assert result["returncode"] == 0
    assert result["stderr"] == ""


def test_arm_b_missing_cli_records_no_exit_status(tmp_path):
    config = _stub_config(tmp_path, "judgment-pack-that-does-not-exist")
    result = arm_b.evaluate_instance(_instance("x#0", True, []), config)
    assert result["ok"] is False
    assert result["error"].startswith("engine-refusal:cli-not-found")
    # No process completed, so no exit status is invented. None is not 0.
    assert result["returncode"] is None
    assert result["stderr"] == ""


def test_run_retains_engine_keys_on_arm_b_rows_only(instance_dir, policy_file, tmp_path):
    cli = _stub_cli(tmp_path, "jp-run", exit_code=0,
                    stdout=json.dumps(_STUB_ENVELOPE),
                    stderr="note: deterministic runtime\n")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")

    b_out = tmp_path / "B-mock.jsonl"
    b_proc = _run_cli("--arm", "B", "--backend", "mock", "--instances", instance_dir,
                      "--trials", "1", "--seed", "0", "--out", str(b_out),
                      "--pack", str(pack), "--judgment-pack-cli", cli,
                      "--rule-catalog", "none")
    assert b_proc.returncode == 0, b_proc.stderr.decode()
    b_rows = [json.loads(line) for line in b_out.read_text(encoding="utf-8").splitlines()]
    assert len(b_rows) == 4
    for row in b_rows:
        assert row["schema"] == "jps-study-001-result/2"
        assert row["engine_returncode"] == 0
        assert row["engine_stderr"] == "note: deterministic runtime\n"
        # The keys sit immediately after `error`, where ROW_KEYS puts them.
        keys = list(row)
        assert keys[keys.index("error") + 1:keys.index("error") + 3] == \
            ["engine_returncode", "engine_stderr"]

    a_out = tmp_path / "A-mock.jsonl"
    a_proc = _run_cli("--arm", "A", "--backend", "mock", "--instances", instance_dir,
                      "--trials", "1", "--seed", "0", "--out", str(a_out),
                      "--policy", policy_file, "--rule-catalog", "none")
    assert a_proc.returncode == 0, a_proc.stderr.decode()
    a_rows = [json.loads(line) for line in a_out.read_text(encoding="utf-8").splitlines()]
    assert len(a_rows) == 4
    for row in a_rows:
        assert row["schema"] == "jps-study-001-result/2"
        # A model arm has no child process, so it claims no exit status.
        assert "engine_returncode" not in row
        assert "engine_stderr" not in row


def test_run_records_a_nonzero_exit_as_an_arm_b_error_row(instance_dir, tmp_path):
    cli = _stub_cli(tmp_path, "jp-run-fail", exit_code=70,
                    stdout=json.dumps(_STUB_ENVELOPE),
                    stderr="fatal: internal error\n")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")

    out = tmp_path / "B-fail.jsonl"
    proc = _run_cli("--arm", "B", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "1", "--seed", "0", "--out", str(out),
                    "--pack", str(pack), "--judgment-pack-cli", cli,
                    "--rule-catalog", "none")
    assert proc.returncode == 0, proc.stderr.decode()
    # The run reports the refusals rather than exiting on them: they are data.
    assert "errors         : 4" in proc.stdout.decode()

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4
    for row in rows:
        assert row["parse_ok"] is False
        assert row["prediction"] is None
        assert row["error"].startswith("engine-refusal:exit=70")
        assert row["engine_returncode"] == 70
        assert "internal error" in row["engine_stderr"]


# --------------------------------------------------------------------------- #
# Resuming across the two arm-B row vintages
#
# The refusal rule is what an arm-B row *means*, and it changed with the schema:
# a `/1` arm-B row could record a non-zero exit that printed an envelope as a
# success. Resume keys on (row_id, trial) and cannot see that, so one file could
# end up holding both definitions with nothing able to tell them apart --- every
# rate computed over it would silently mix the two.
# --------------------------------------------------------------------------- #


def _legacy_arm_b_row(instance_id, trial=1):
    """One arm-B row as `/1` wrote them: no engine_returncode, no engine_stderr."""
    return {
        "schema": "jps-study-001-result/1",
        "row_id": instance_id, "instance_id": instance_id,
        "arm": "B", "backend": "mock", "model": "judgment-pack-runtime",
        "params": {}, "trial": trial, "seed": 0,
        "prediction": {"decision": "illegal", "cited_rules": [], "reason": ""},
        "raw_text": "{}", "parse_ok": True, "parse_error": None,
        "latency_ms": 1, "error": None,
        "facts_sha256": "x", "prompt_sha256": None,
        "harness_commit": "c", "harness_dirty": False, "arm_config": {},
    }


def test_run_refuses_to_resume_arm_b_across_row_vintages(instance_dir, tmp_path):
    cli = _stub_cli(tmp_path, "jp-resume", exit_code=0,
                    stdout=json.dumps(_STUB_ENVELOPE), stderr="")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")

    out = tmp_path / "B-mixed.jsonl"
    legacy = json.dumps(_legacy_arm_b_row("comp_0#000")) + "\n"
    out.write_text(legacy, encoding="utf-8")

    proc = _run_cli("--arm", "B", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "1", "--seed", "0", "--out", str(out),
                    "--pack", str(pack), "--judgment-pack-cli", cli,
                    "--rule-catalog", "none")
    assert proc.returncode == 2
    stderr = proc.stderr.decode()
    assert "refusing to resume" in stderr
    assert "jps-study-001-result/1" in stderr
    # Nothing was appended: the file is exactly as it was left.
    assert out.read_text(encoding="utf-8") == legacy


def test_dry_run_refuses_the_same_mixture_before_reporting_a_plan(instance_dir, tmp_path):
    """A plan that cannot legally be appended is not a plan worth printing."""
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_tiny_pack()), encoding="utf-8")
    out = tmp_path / "B-mixed-dry.jsonl"
    out.write_text(json.dumps(_legacy_arm_b_row("comp_0#000")) + "\n",
                   encoding="utf-8")

    proc = _run_cli("--arm", "B", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "1", "--seed", "0", "--out", str(out),
                    "--pack", str(pack), "--rule-catalog", "none", "--dry-run")
    assert proc.returncode == 2
    assert "refusing to resume" in proc.stderr.decode()


def test_model_arms_still_resume_across_the_schema_boundary(instance_dir, policy_file,
                                                            tmp_path):
    """Arm-A rows did not change meaning between `/1` and `/2`, so they may mix."""
    out = tmp_path / "A-mixed.jsonl"
    legacy = _legacy_arm_b_row("comp_0#000")
    legacy.update({"arm": "A", "model": "mock/deterministic-v1",
                   "prompt_sha256": "p"})
    out.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    proc = _run_cli("--arm", "A", "--backend", "mock", "--instances", instance_dir,
                    "--trials", "1", "--seed", "0", "--out", str(out),
                    "--policy", policy_file, "--rule-catalog", "none")
    assert proc.returncode == 0, proc.stderr.decode()
    assert "rows skipped   : 1 (already present -- resumed)" in proc.stdout.decode()
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4
    assert [row["schema"] for row in rows] == (
        ["jps-study-001-result/1"] + ["jps-study-001-result/2"] * 3)


def test_arm_b_vintage_guard_is_a_no_op_on_a_uniform_or_absent_file(tmp_path):
    missing = tmp_path / "nothing.jsonl"
    run_mod.assert_uniform_arm_b_vintage(str(missing), "B")  # no file, no opinion

    uniform = tmp_path / "B-uniform.jsonl"
    row = _legacy_arm_b_row("comp_0#000")
    row["schema"] = run_mod.SCHEMA
    uniform.write_text(json.dumps(row) + "\n", encoding="utf-8")
    run_mod.assert_uniform_arm_b_vintage(str(uniform), "B")

    stale = tmp_path / "B-stale.jsonl"
    stale.write_text(json.dumps(_legacy_arm_b_row("comp_0#000")) + "\n",
                     encoding="utf-8")
    # The same file is fine for a model arm and refused for arm B.
    run_mod.assert_uniform_arm_b_vintage(str(stale), "A")
    with pytest.raises(ValueError) as exc:
        run_mod.assert_uniform_arm_b_vintage(str(stale), "B")
    assert "jps-study-001-result/1" in str(exc.value)


# --------------------------------------------------------------------------- #
# load_results validates rows before scoring
# --------------------------------------------------------------------------- #


def _results_file(tmp_path, name, entries):
    """Write a JSONL file; dicts are dumped, strings are written as-is."""
    lines = [e if isinstance(e, str) else json.dumps(e) for e in entries]
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _valid_row(iid="i9", trial=1):
    return _row(iid, trial, "legal", ["R1"])


def test_valid_rows_with_unknown_extra_fields_load(tmp_path):
    extra = _valid_row()
    extra["zz_unknown"] = {"anything": [1, "goes"]}
    twin = _valid_row("p0", 1)
    twin["row_id"] = "p0__answerable"
    path = _results_file(tmp_path, "ok.jsonl", ["", extra, "", twin])
    results = score_mod.load_results([path])
    assert set(results) == {"A::mock::m"}
    assert set(results["A::mock::m"]) == {"i9", "p0__answerable"}
    assert results["A::mock::m"]["i9"][0]["zz_unknown"] == {"anything": [1, "goes"]}


@pytest.mark.parametrize(
    "field,value",
    [
        ("arm", None), ("arm", ""), ("arm", 7),
        ("backend", None), ("backend", ""), ("backend", ["mock"]),
        ("model", None), ("model", ""), ("model", {"m": 1}),
    ],
)
def test_grouping_fields_must_be_non_empty_strings(tmp_path, field, value):
    row = _valid_row()
    row[field] = value
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert str(path) in str(exc.value)
    assert "line 1" in str(exc.value)


@pytest.mark.parametrize("field", ["arm", "backend", "model"])
def test_missing_grouping_field_is_rejected(tmp_path, field):
    row = _valid_row()
    del row[field]
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert str(path) in str(exc.value)
    assert "line 1" in str(exc.value)


@pytest.mark.parametrize("schema", ["bogus", "", None])
def test_unsupported_schema_is_rejected(tmp_path, schema):
    row = _valid_row()
    row["schema"] = schema
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert str(path) in str(exc.value)
    assert "line 1" in str(exc.value)


@pytest.mark.parametrize("raw", ["[1, 2]", '"just a string"', "42", "null"])
def test_non_object_row_is_rejected(tmp_path, raw):
    path = _results_file(tmp_path, "bad.jsonl", [raw])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert str(path) in str(exc.value)
    assert "line 1" in str(exc.value)


def test_truthy_non_string_row_id_is_rejected(tmp_path):
    row = _valid_row()
    row["row_id"] = 7
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert "row_id" in str(exc.value)


def test_missing_identity_is_rejected(tmp_path):
    row = _valid_row()
    del row["instance_id"]
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert "row_id" in str(exc.value)


def test_empty_fallback_identity_is_rejected(tmp_path):
    row = _valid_row()
    row["instance_id"] = ""
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError):
        score_mod.load_results([path])


def test_empty_or_null_row_id_falls_back_to_instance_id(tmp_path):
    empty = _valid_row("i9", 1)
    empty["row_id"] = ""
    null = _valid_row("i9", 2)
    null["row_id"] = None
    path = _results_file(tmp_path, "ok.jsonl", [empty, null])
    results = score_mod.load_results([path])
    assert [r["trial"] for r in results["A::mock::m"]["i9"]] == [1, 2]


@pytest.mark.parametrize("trial", [True, False, 0, -1, "1", 1.5, None])
def test_bad_trial_is_rejected(tmp_path, trial):
    row = _valid_row()
    row["trial"] = trial
    path = _results_file(tmp_path, "bad.jsonl", [row])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert "trial" in str(exc.value)
    assert str(path) in str(exc.value)


def test_duplicate_cell_in_one_file_is_rejected(tmp_path):
    path = _results_file(tmp_path, "dup.jsonl", [_valid_row(), _valid_row()])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert "duplicate" in str(exc.value)
    assert str(path) in str(exc.value)
    assert "line 2" in str(exc.value)


def test_duplicate_cell_across_files_is_rejected(tmp_path):
    first = _results_file(tmp_path, "a.jsonl", [_valid_row()])
    second = _results_file(tmp_path, "b.jsonl", [_valid_row()])
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([first, second])
    assert "duplicate" in str(exc.value)
    assert str(second) in str(exc.value)
    assert "line 1" in str(exc.value)


def test_same_identity_different_trials_is_not_a_duplicate(tmp_path):
    path = _results_file(tmp_path, "ok.jsonl", [_valid_row("i9", 1), _valid_row("i9", 2)])
    results = score_mod.load_results([path])
    assert [r["trial"] for r in results["A::mock::m"]["i9"]] == [1, 2]


def test_error_names_the_file_and_line(tmp_path):
    rows = [_valid_row("i1", 1), _valid_row("i2", 1), _valid_row("i3", 1)]
    del rows[2]["arm"]
    path = _results_file(tmp_path, "bad.jsonl", rows)
    with pytest.raises(ValueError) as exc:
        score_mod.load_results([path])
    assert str(path) in str(exc.value)
    assert "line 3" in str(exc.value)
