#!/usr/bin/env python3
"""Decisions by gold class, and what a constant answer would score.

WHAT THIS FILE DOES
-------------------
Two descriptive tables over the same paired analysis set ``score.py`` uses:

* **Decisions by gold class.** For every condition, how many trials on
  instances of each gold class returned each decision. A trial that did not
  parse, or parsed to something that is not one of the three decisions, is
  counted in its own column. Nothing is dropped, so each row sums to the class's
  instances times the trials per instance.
* **Constant-answer baselines.** For each of the three decisions, the share of
  the analysis set whose gold is that decision. That share is what an arm that
  always gave that answer would score on accuracy, and on pass^k too, because a
  constant answer is the same on every trial.

Both tables are secondary, post hoc and descriptive. PREREGISTRATION.md names no
constant-answer baseline and no per-class breakdown; both were added after the
results were read and are recorded as such in DEVIATIONS.md section 9. They
change no registered figure.

The analysis set follows ``score.py``'s rules: the instances every condition
covers, restricted by ``--population`` on the instance document's ``variant``
field, with k per instance the smallest trial count across conditions and the
first k trials read. The population filter, the gold class, the result loader
and the instance key are the scorer's own functions. The intersection across
conditions and the first-k rule are repeated here in the scorer's form, and
accuracy is the mean over instances of the share of an instance's trials that
match gold, as ``score.aggregate`` computes it. The tests hold the accuracy
printed here to the accuracy ``score.py`` reports for the same instances and
rows.

Two inputs the scorer accepts are refused here, because a class table cannot
place them: an instance with no gold decision, which belongs to no class (the
scorer counts every trial on it as wrong), and an instance with no trial under
some condition (the scorer gives it k = 0).

WHAT THIS FILE DELIBERATELY DOES NOT DO
---------------------------------------
* No interval and no test. These are counts, and rates that are those counts
  divided.
* No default population. ``--population`` is required: DEVIATIONS.md section 2
  records what reporting on an unstated population cost this study.
* No verdict. Whether a hypothesis passed is settled by PREREGISTRATION.md
  section 6, and a baseline is not one of its criteria.

Python 3.10+ (``from __future__ import annotations`` keeps it importable on 3.8).
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from arms import instance_key  # noqa: E402
from run import load_instances  # noqa: E402
from score import (DECISIONS, POPULATIONS, filter_population,  # noqa: E402
                   gold_decision, load_results)

SCHEMA = "jps-study-001-class-table/1"

#: The column for a trial with no usable decision: the row did not parse, or it
#: parsed to a value outside ``DECISIONS``. ``score.py`` scores both as wrong.
NO_DECISION = "no_decision"
COLUMNS = DECISIONS + (NO_DECISION,)


def trial_decision(row: Mapping[str, Any]) -> str:
    """The column one result row is counted in."""
    if not row.get("parse_ok"):
        return NO_DECISION
    decision = (row.get("prediction") or {}).get("decision")
    return decision if decision in DECISIONS else NO_DECISION


def class_table(instances: Sequence[Mapping[str, Any]],
                results: Mapping[str, Mapping[str, List[Dict[str, Any]]]],
                *, population: str) -> Dict[str, Any]:
    by_id = {instance_key(i): i for i in instances}
    if len(by_id) != len(instances):
        raise ValueError(
            "instance identities collide: %d documents map to %d keys. Twins must "
            "carry distinct twin_id values." % (len(instances), len(by_id)))
    conditions = sorted(results)
    if not conditions:
        raise ValueError("no result rows found")

    shared = set(by_id)
    for cond in conditions:
        shared &= set(results[cond])
    paired = sorted(shared)
    if not paired:
        raise ValueError(
            "the conditions share no instances; a paired comparison is impossible")
    paired = filter_population(paired, by_id, population)

    gold = {iid: gold_decision(by_id[iid]) for iid in paired}
    unlabelled = sorted(iid for iid in paired if gold[iid] is None)
    if unlabelled:
        raise ValueError(
            "%d instance(s) carry no gold decision, so they belong to no class: %s"
            % (len(unlabelled), ", ".join(unlabelled[:5])))

    k_by_instance = {
        iid: min(len(results[cond][iid]) for cond in conditions) for iid in paired}
    untried = sorted(iid for iid in paired if k_by_instance[iid] == 0)
    if untried:
        raise ValueError(
            "%d instance(s) have no trial under some condition, so they have no "
            "decision to count: %s" % (len(untried), ", ".join(untried[:5])))

    gold_instances = {d: sum(1 for iid in paired if gold[iid] == d) for d in DECISIONS}
    gold_trials = {d: sum(k_by_instance[iid] for iid in paired if gold[iid] == d)
                   for d in DECISIONS}

    by_condition: Dict[str, Any] = {}
    for cond in conditions:
        counts = {g: {c: 0 for c in COLUMNS} for g in DECISIONS}
        rate_sum = 0.0
        for iid in paired:
            k = k_by_instance[iid]
            matching = 0
            for row in results[cond][iid][:k]:
                decision = trial_decision(row)
                counts[gold[iid]][decision] += 1
                matching += int(decision == gold[iid])
            rate_sum += matching / k
        by_condition[cond] = {
            "trials_by_gold_and_decision": counts,
            "trials": sum(gold_trials.values()),
            "trials_correct": sum(counts[d][d] for d in DECISIONS),
            "accuracy": rate_sum / len(paired),
        }

    n = len(paired)
    constant = {
        d: {"instances_correct": gold_instances[d], "accuracy": gold_instances[d] / n,
            "pass_at_k": gold_instances[d] / n}
        for d in DECISIONS}

    ks = sorted(set(k_by_instance.values()))
    return {
        "schema": SCHEMA,
        "population": population,
        "paired_instances": n,
        "trials_per_instance": {"min": ks[0], "max": ks[-1]},
        "gold_instances": gold_instances,
        "gold_trials": gold_trials,
        "conditions": by_condition,
        "constant_answer": constant,
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    ks = summary["trials_per_instance"]
    lines = [
        "# Study 001 -- decisions by gold class, and constant-answer baselines",
        "",
        "**Secondary, post hoc and descriptive; not registered.** Computed after the "
        "results were read (DEVIATIONS.md section 9). Counts and descriptive rates, "
        "without intervals: no test, no verdict.",
        "",
        "Analysis population: `%s`. %d instances shared by every condition. "
        "Trials per instance: %d-%d." % (
            summary["population"], summary["paired_instances"], ks["min"], ks["max"]),
        "",
        "## Constant-answer baselines",
        "",
        "What an arm that always gave one answer would score. Its pass^k equals its "
        "accuracy, because a constant answer is the same on every trial.",
        "",
        "| constant answer | instances it gets right | accuracy = pass^k |",
        "|---|---:|---:|",
    ]
    n = summary["paired_instances"]
    for d in DECISIONS:
        row = summary["constant_answer"][d]
        lines.append("| `%s` | %d of %d | %.3f |" % (
            d, row["instances_correct"], n, row["accuracy"]))

    lines += [
        "",
        "## Decisions by gold class (trials)",
        "",
        "Each row sums to the class's trials. `%s` is a trial that did not parse, or "
        "parsed to something that is not one of the three decisions." % NO_DECISION,
        "",
        "| condition | gold class | trials | " + " | ".join(
            "got `%s`" % c for c in COLUMNS) + " | share of trials matching gold |",
        "|---|---|---:|" + "---:|" * (len(COLUMNS) + 1),
    ]
    for cond in sorted(summary["conditions"]):
        counts = summary["conditions"][cond]["trials_by_gold_and_decision"]
        for g in DECISIONS:
            total = summary["gold_trials"][g]
            if not total:
                continue
            lines.append("| `%s` | `%s` | %d | %s | %.3f |" % (
                cond, g, total, " | ".join(str(counts[g][c]) for c in COLUMNS),
                counts[g][g] / total))

    lines += [
        "",
        "## Accuracy from these counts",
        "",
        "Accuracy is the mean over instances of the share of an instance's trials "
        "that match gold, as `score.py` computes it, and equals the accuracy it "
        "reports for the same population and result files. When every instance has "
        "the same number of trials it is the second column over the third.",
        "",
        "| condition | trials matching gold | trials | accuracy |",
        "|---|---:|---:|---:|",
    ]
    for cond in sorted(summary["conditions"]):
        entry = summary["conditions"][cond]
        lines.append("| `%s` | %d | %d | %.3f |" % (
            cond, entry["trials_correct"], entry["trials"], entry["accuracy"]))
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="class_table.py",
        description="Study-001 decisions by gold class and constant-answer "
                    "baselines. Descriptive; not a registered analysis.")
    p.add_argument("--instances", required=True,
                   help="directory of *.json instance documents, or an index.json")
    p.add_argument("--results", required=True, nargs="+", help="result JSONL files")
    p.add_argument("--population", choices=POPULATIONS, required=True,
                   help="the twin variant to report on, by the instance "
                        "document's 'variant' field. Required: there is no "
                        "default population.")
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    summary = class_table(load_instances(args.instances), load_results(args.results),
                          population=args.population)
    markdown = render_markdown(summary)

    if args.out_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_json)) or ".", exist_ok=True)
        with open(args.out_json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, sort_keys=True)
            fh.write("\n")
    if args.out_md:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_md)) or ".", exist_ok=True)
        with open(args.out_md, "w", encoding="utf-8") as fh:
            fh.write(markdown)

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
