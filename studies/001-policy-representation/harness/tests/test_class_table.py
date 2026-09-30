"""Tests for ``class_table.py``: decisions by gold class and constant answers.

WHAT THIS FILE DOES
-------------------
* Counts a small synthetic corpus --- three base instances, both twins, two
  conditions --- whose every cell is worked out in comments beside the fixture.
* Checks that no trial is dropped: a row that did not parse, and a row that
  parsed to something outside the three decisions, land in ``no_decision``, and
  every gold class's row sums to its trials.
* Checks that the analysis set is the scorer's: only instances every condition
  covers, only the population asked for, and only the first k trials, k being
  the smallest trial count across conditions.
* Checks the constant-answer baselines against the class shares.
* Holds the accuracy printed here to the accuracy ``score.py`` reports for the
  same corpus, on a corpus where instances differ in k, so that trials matching
  gold over trials would give a different number.
* Checks that ``--population`` has no default and takes only the scorer's
  population names.
* Checks each refusal: colliding instance identities, no result rows, conditions
  that share no instance, an instance with no gold decision, and an instance
  with no trial under some condition.

WHAT THIS FILE DELIBERATELY DOES NOT DO
---------------------------------------
* No reading of the real ``results/`` corpus. The study's own table is checked by
  re-running ``class_table.py``, not by a unit test that would freeze it.
* No assertion about what any arm scored, and none about any hypothesis.

Standard library plus pytest only.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.dirname(HERE)
if HARNESS not in sys.path:
    sys.path.insert(0, HARNESS)

import class_table as ct  # noqa: E402
import score as score_mod  # noqa: E402

A = "A::mock::m"
B = "B::mock::m"


# --------------------------------------------------------------------------- #
# Fixture
# --------------------------------------------------------------------------- #
#
# Gold on the answerable twins: p0 illegal, p1 legal, p2 illegal. Every redacted
# twin's gold is cannot_decide. p3 is covered by arm A only.
#
# Trials, in order. Arm B has a third trial on p0 that k = 2 must leave unread.
#
#   answerable   arm A                       arm B
#   p0 illegal   illegal, legal              illegal, illegal, (legal: unread)
#   p1 legal     legal                       illegal
#   p2 illegal   cannot_decide, <no parse>   illegal, "maybe"
#   p3 illegal   illegal, illegal            (absent: p3 is not paired)
#
# The unparsed row carries a prediction of "illegal", which is p2's gold. Read
# as a decision it would be a trial matching gold.
#
#   redacted     arm A                       arm B
#   p0           illegal, illegal            cannot_decide, cannot_decide
#   p1           legal                       cannot_decide
#   p2           cannot_decide, illegal      cannot_decide, illegal
#
# k per instance is 2 for p0 and p2 and 1 for p1, on both twins.
#
# answerable, trials by gold class (legal / illegal / cannot_decide / no_decision):
#   arm A   gold legal   (1 trial):  1 / 0 / 0 / 0
#           gold illegal (4 trials): 1 / 1 / 1 / 1
#   arm B   gold legal   (1 trial):  0 / 1 / 0 / 0
#           gold illegal (4 trials): 0 / 3 / 0 / 1
#
# answerable accuracy, the mean over instances of the share matching gold:
#   arm A   (1/2 + 1/1 + 0/2) / 3 = 0.5      trials matching gold: 2 of 5 = 0.4
#   arm B   (2/2 + 0/1 + 1/2) / 3 = 0.5      trials matching gold: 3 of 5 = 0.6


GOLD_ANSWER = {0: True, 1: False, 2: True, 3: True}  # True is "illegal"


def _instance(base, variant):
    return {
        "instance_id": "p%d" % base,
        "pair_id": "p%d" % base,
        "twin_id": "p%d__%s" % (base, variant),
        "variant": variant,
        "facts": {"teams": {"A": {"salary": "1"}}},
        "gold": {"answer": GOLD_ANSWER[base], "relevant_rules": ["R1"]},
        "redaction": {"applied": variant == "redacted",
                      "base_instance_id": "p%d" % base},
    }


def _corpus():
    return [_instance(base, variant)
            for base in range(4) for variant in ("answerable", "redacted")]


def _row(twin_id, trial, decision, *, arm, parse_ok=True):
    return {
        "schema": "jps-study-001-result/1",
        "instance_id": twin_id.split("__", 1)[0],
        "row_id": twin_id,
        "arm": arm, "backend": "mock", "model": "m",
        "params": {}, "trial": trial, "seed": 0,
        # An unparsed row keeps a prediction here on purpose. ``score.py`` reads
        # no decision from a row that did not parse, whatever the row carries,
        # and neither may this file.
        "prediction": {"decision": decision, "cited_rules": ["R1"], "reason": ""},
        "raw_text": "", "parse_ok": parse_ok,
        "parse_error": None if parse_ok else "no-json-object",
        "latency_ms": 1, "error": None,
        "facts_sha256": "x", "prompt_sha256": "y",
        "harness_commit": "c", "harness_dirty": False, "arm_config": {},
    }


NO_PARSE = object()

TRIALS = {
    "A": {
        "p0__answerable": ["illegal", "legal"],
        "p1__answerable": ["legal"],
        "p2__answerable": ["cannot_decide", NO_PARSE],
        "p3__answerable": ["illegal", "illegal"],
        "p0__redacted": ["illegal", "illegal"],
        "p1__redacted": ["legal"],
        "p2__redacted": ["cannot_decide", "illegal"],
    },
    "B": {
        "p0__answerable": ["illegal", "illegal", "legal"],
        "p1__answerable": ["illegal"],
        "p2__answerable": ["illegal", "maybe"],
        "p0__redacted": ["cannot_decide", "cannot_decide"],
        "p1__redacted": ["cannot_decide"],
        "p2__redacted": ["cannot_decide", "illegal"],
    },
}


def _rows():
    rows = []
    for arm, by_twin in TRIALS.items():
        for twin_id, decisions in by_twin.items():
            for trial, decision in enumerate(decisions, 1):
                if decision is NO_PARSE:
                    rows.append(_row(twin_id, trial, "illegal", arm=arm, parse_ok=False))
                else:
                    rows.append(_row(twin_id, trial, decision, arm=arm))
    return rows


def _results():
    out = {}
    for row in _rows():
        out.setdefault(score_mod.condition_key(row), {}).setdefault(
            row["row_id"], []).append(row)
    for by_instance in out.values():
        for rows in by_instance.values():
            rows.sort(key=lambda r: r["trial"])
    return out


def _table(population):
    return ct.class_table(_corpus(), _results(), population=population)


def _cells(summary, cond, gold):
    counts = summary["conditions"][cond]["trials_by_gold_and_decision"][gold]
    return tuple(counts[c] for c in ct.COLUMNS)


# --------------------------------------------------------------------------- #
# Counts
# --------------------------------------------------------------------------- #


def test_columns_are_the_three_decisions_and_no_decision():
    assert ct.COLUMNS == ("legal", "illegal", "cannot_decide", "no_decision")


def test_answerable_counts_match_the_fixture():
    s = _table("answerable")
    assert s["paired_instances"] == 3
    assert s["gold_instances"] == {"legal": 1, "illegal": 2, "cannot_decide": 0}
    assert s["gold_trials"] == {"legal": 1, "illegal": 4, "cannot_decide": 0}
    assert _cells(s, A, "legal") == (1, 0, 0, 0)
    assert _cells(s, A, "illegal") == (1, 1, 1, 1)
    assert _cells(s, B, "legal") == (0, 1, 0, 0)
    assert _cells(s, B, "illegal") == (0, 3, 0, 1)


def test_a_row_without_a_usable_decision_is_counted_not_dropped():
    s = _table("answerable")
    # Arm A's unparsed trial and arm B's "maybe" are both on p2, gold illegal.
    assert s["conditions"][A]["trials_by_gold_and_decision"]["illegal"]["no_decision"] == 1
    assert s["conditions"][B]["trials_by_gold_and_decision"]["illegal"]["no_decision"] == 1
    for population in score_mod.POPULATIONS:
        summary = _table(population)
        for cond in (A, B):
            for gold in score_mod.DECISIONS:
                assert sum(_cells(summary, cond, gold)) == summary["gold_trials"][gold]


def test_only_the_first_k_trials_are_read():
    # Arm B's third trial on p0 is "legal". k is 2 there, because arm A ran two.
    s = _table("answerable")
    assert s["conditions"][B]["trials_by_gold_and_decision"]["illegal"]["legal"] == 0
    assert s["trials_per_instance"] == {"min": 1, "max": 2}


def test_an_instance_one_condition_lacks_is_left_out_of_both():
    # p3 has rows under arm A only. Counting it would give arm A two more
    # illegal-on-illegal trials and a fourth instance.
    s = _table("answerable")
    assert s["paired_instances"] == 3
    assert s["conditions"][A]["trials"] == 5
    assert s["conditions"][A]["trials_by_gold_and_decision"]["illegal"]["illegal"] == 1


def test_population_selects_by_variant():
    redacted = _table("redacted")
    assert redacted["gold_instances"] == {"legal": 0, "illegal": 0, "cannot_decide": 3}
    assert _cells(redacted, A, "cannot_decide") == (1, 3, 1, 0)
    assert _cells(redacted, B, "cannot_decide") == (0, 1, 4, 0)

    everything = _table("all")
    assert everything["paired_instances"] == 6
    assert everything["gold_instances"] == {"legal": 1, "illegal": 2, "cannot_decide": 3}
    # The answerable classes are untouched by adding the redacted twins.
    assert _cells(everything, A, "illegal") == (1, 1, 1, 1)


# --------------------------------------------------------------------------- #
# Constant answers
# --------------------------------------------------------------------------- #


def test_constant_answer_scores_are_the_class_shares():
    s = _table("answerable")
    assert s["constant_answer"]["illegal"] == {
        "instances_correct": 2, "accuracy": 2 / 3, "pass_at_k": 2 / 3}
    assert s["constant_answer"]["legal"]["accuracy"] == 1 / 3
    assert s["constant_answer"]["cannot_decide"]["accuracy"] == 0.0
    assert sum(v["accuracy"] for v in s["constant_answer"].values()) == pytest.approx(1.0)

    everything = _table("all")
    assert everything["constant_answer"]["cannot_decide"]["accuracy"] == 0.5


# --------------------------------------------------------------------------- #
# Agreement with score.py
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("population", score_mod.POPULATIONS)
def test_accuracy_is_the_accuracy_score_py_reports(population):
    # Instances differ in k here (p1 has one trial, the others two), so trials
    # matching gold over trials is a different number from the scorer's mean of
    # per-instance shares: on the answerable set 0.4 and 0.6 against 0.5 and 0.5.
    table = _table(population)
    scored = score_mod.score(_corpus(), _results(), bootstrap=10, seed=1,
                             baseline=A, population=population)
    for cond in (A, B):
        assert table["conditions"][cond]["accuracy"] == pytest.approx(
            scored["conditions"][cond]["point"]["accuracy"])
    assert table["paired_instances"] == scored["paired_instances"]


def test_accuracy_is_not_trials_matching_gold_over_trials():
    s = _table("answerable")
    assert s["conditions"][A]["accuracy"] == pytest.approx(0.5)
    assert s["conditions"][A]["trials_correct"] / s["conditions"][A]["trials"] == 0.4
    assert s["conditions"][B]["accuracy"] == pytest.approx(0.5)
    assert s["conditions"][B]["trials_correct"] / s["conditions"][B]["trials"] == 0.6


# --------------------------------------------------------------------------- #
# Refusals and the command line
# --------------------------------------------------------------------------- #


def test_an_instance_with_no_gold_decision_is_refused():
    corpus = _corpus()
    for doc in corpus:
        if doc["twin_id"] == "p0__answerable":
            doc["gold"] = {"relevant_rules": ["R1"]}
    with pytest.raises(ValueError, match="no gold decision"):
        ct.class_table(corpus, _results(), population="answerable")


def test_colliding_instance_identities_are_refused():
    corpus = _corpus()
    corpus.append(_instance(0, "answerable"))
    with pytest.raises(ValueError, match="instance identities collide"):
        ct.class_table(corpus, _results(), population="answerable")


def test_no_result_rows_is_refused():
    with pytest.raises(ValueError, match="no result rows"):
        ct.class_table(_corpus(), {}, population="answerable")


def test_conditions_that_share_no_instance_are_refused():
    results = _results()
    results[B] = {"p3__answerable": results[A]["p3__answerable"]}
    del results[A]["p3__answerable"]
    with pytest.raises(ValueError, match="share no instances"):
        ct.class_table(_corpus(), results, population="answerable")


def test_an_instance_with_no_trial_under_a_condition_is_refused():
    # score.py gives such an instance k = 0 and an accuracy of 0. A class table
    # has no decision to count for it, and a constant answer would be credited
    # with an instance nobody answered.
    results = _results()
    results[B]["p1__answerable"] = []
    with pytest.raises(ValueError, match="no trial under some condition"):
        ct.class_table(_corpus(), results, population="answerable")


def test_rows_for_a_twin_with_no_instance_document_are_left_out():
    results = _results()
    for arm, cond in (("A", A), ("B", B)):
        results[cond]["p9__answerable"] = [
            _row("p9__answerable", 1, "illegal", arm=arm)]
    assert ct.class_table(_corpus(), results, population="answerable") == _table(
        "answerable")


def test_a_parsed_row_with_no_prediction_has_no_decision():
    row = _row("p0__answerable", 1, "illegal", arm="A")
    assert ct.trial_decision(row) == "illegal"
    row["prediction"] = None
    assert ct.trial_decision(row) == ct.NO_DECISION
    del row["prediction"]
    assert ct.trial_decision(row) == ct.NO_DECISION


def _write_inputs(tmp_path):
    instances = tmp_path / "instances.json"
    instances.write_text(json.dumps(_corpus()), encoding="utf-8")
    results = tmp_path / "rows.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in _rows()), encoding="utf-8")
    return str(instances), str(results)


def test_population_has_no_default(tmp_path, capsys):
    instances, results = _write_inputs(tmp_path)
    with pytest.raises(SystemExit):
        ct.main(["--instances", instances, "--results", results])
    assert "--population" in capsys.readouterr().err


def test_population_takes_only_the_scorers_names(tmp_path, capsys):
    instances, results = _write_inputs(tmp_path)
    with pytest.raises(SystemExit):
        ct.main(["--instances", instances, "--results", results,
                 "--population", "answerable-and-redacted"])
    assert "invalid choice" in capsys.readouterr().err


def test_main_writes_both_reports_and_says_what_they_are(tmp_path, capsys):
    instances, results = _write_inputs(tmp_path)
    out_json = tmp_path / "out" / "table.json"
    out_md = tmp_path / "out" / "table.md"
    assert ct.main(["--instances", instances, "--results", results,
                    "--population", "answerable",
                    "--out-json", str(out_json), "--out-md", str(out_md)]) == 0
    capsys.readouterr()

    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary == _table("answerable")
    assert summary["schema"] == ct.SCHEMA

    markdown = out_md.read_text(encoding="utf-8")
    assert "Secondary, post hoc and descriptive; not registered" in markdown
    assert "Counts only" not in markdown
    assert "Analysis population: `answerable`" in markdown
    assert "| `illegal` | 2 of 3 | 0.667 |" in markdown
    assert "| `%s` | `illegal` | 4 | 1 | 1 | 1 | 1 | 0.250 |" % A in markdown
    # A gold class with no instance in the population has no row.
    assert "| `%s` | `cannot_decide` |" % A not in markdown
