#!/usr/bin/env python3
"""Score study-001 result JSONL files with a paired, instance-level design.

WHAT THIS FILE DOES
-------------------
::

    python score.py --instances <dir-or-index.json> --results a.jsonl b.jsonl ... \
                    [--baseline "A::mock::mock/deterministic-v1"] \
                    [--registered] \
                    [--population all|answerable|redacted] \
                    [--bootstrap-unit twin|pair] \
                    [--out-md report.md] [--out-json report.json] \
                    [--bootstrap 2000] [--seed 20260727]

Reads one or more result files, groups rows into **conditions**
(``arm::backend::model`` --- a ``::`` separator, because model identifiers
themselves contain slashes), restricts every condition to the **intersection** of
the instance ids they all cover, and reports, for each condition:

* **accuracy** against gold, macro-averaged over instances (each instance
  contributes the mean of its trials, so an instance with more trials does not
  get more weight);
* **pass^k consistency** --- the probability that *all* k trials on an instance are
  correct. A model that is right on average but flips between runs is penalised
  here and nowhere else;
* **citation precision / recall / F1** against the gold ``relevant_rules`` set,
  reported both macro (per-instance mean) and micro (pooled counts);
* **escalation precision, recall and F1** on the redacted twins, from the full
  ``should-escalate x did-escalate`` 2x2 --- never recall alone, because an
  always-escalate agent achieves recall 1.0 and must be visibly punished for it
  by precision;
* **parse-failure rate** and, for arm B, **engine-refusal rate**.

Uncertainty comes from a **paired bootstrap**: instances are resampled with
replacement, the *same* resample is applied to every condition, and every metric
plus every baseline-relative difference is recomputed. Percentile intervals are
reported. ``random.Random`` with a fixed seed; the same inputs give the same
numbers. Alongside it, and only alongside it, **McNemar's test** on the pass^k
indicator. PREREGISTRATION.md section 5 registers "McNemar's test for paired
binary outcomes" and no more: the exact (rather than asymptotic) form, the
two-sided reading, and the choice of the pass^k indicator as the binary are
implementation decisions recorded in DEVIATIONS.md section 4, and the test is
computed for *every* non-baseline condition, of which only the B-vs-A contrast
on the answerable population is the registered primary --- any other cell it
prints is exploratory.

ANALYSIS POPULATION (``--population``, default ``all``)
--------------------------------------------------------
The filter is applied to the paired instance set *after* the cross-condition
intersection, on the instance document's ``variant`` field, which ``redact.py``
stamps into both twins: ``answerable`` keeps the unredacted twins, ``redacted``
keeps their counterparts, ``all`` keeps both and is the shipped behaviour. A
filter that selects nothing is an error, never an empty report.

It exists because of DEVIATIONS.md section 2. PREREGISTRATION.md section 2
registers the primary endpoint as pass^k **on answerable instances**, and the
shipped scorer could not express that population --- it intersected the twin ids
and stopped --- so the first k = 5 write-up reported the composite over all 432
twins as though it were the registered endpoint. On the registered population the
sign of the headline difference flips. A scorer that cannot name the population
it is computing on invites exactly that mistake, so it now names it, and the choice is
recorded in the JSON summary and stated in the markdown header rather than left
to a reader's memory of the command line. The flag does not *know* which
population any given hypothesis registered; it only makes the choice explicit and
auditable.

BOOTSTRAP UNIT (``--bootstrap-unit``, default ``twin``)
--------------------------------------------------------
``twin`` resamples each twin independently. It is the shipped behaviour and it
stays the default: every interval this study has published was computed that way,
and a default that restated them all without a flag, a warning or a note would be
a worse defect than the one the option was added to answer. ``pair`` resamples the
**base-instance clusters** (grouped by ``base_instance_id``): as many clusters are
drawn with replacement as there are clusters, and each drawn cluster contributes
all of its members, so a pair is always in or out together. DEVIATIONS.md section
3 recorded the absence of the clustered option as a deviation; section 4 records
its arrival and the default that was deliberately not changed with it.

What clustering does to an interval here is **measured, not assumed, and it does
not go one way.** Over this study's corpus on the composite population (2000
replicates, seed 20260806) ``pair`` is *narrower* on 15 of the 33 non-degenerate
(condition x metric) intervals --- every accuracy, pass^k and escalation one ---
and wider on the other 18, which are the citation metrics. The headline paired
difference is the clearest case: delta pass^k, B - A is [0.100, 0.160] clustered
against [0.076, 0.181] unclustered, 42% narrower. The mechanism is mechanical
rather than statistical: in this corpus every cluster is exactly one answerable
twin plus its redacted counterpart (216 clusters, all of size two), so a cluster
resample holds the answerable:redacted mix at exactly 50% in every replicate and
removes the mixture-composition variance that dominates the composite population.
That is stratification, and wanting it is defensible --- but it is the opposite of
"the twins are dependent, so clustering must widen the interval", and this file
will not carry a justification its own data contradicts. On the registered
``answerable`` population the choice is inert, so the primary endpoint does not
turn on it either way.

Under ``--population answerable`` (likewise ``redacted``) every cluster is a
singleton, so the two units consume the same random draws from the same seed and
give identical resamples and identical intervals; the flag only bites on the
composite population.

WHEN THE ESCALATION 2x2 IS NOT ESTIMABLE
------------------------------------------
The escalation metrics cross should-escalate (a redacted twin) against
did-escalate. That table needs **both** of its rows to be non-empty, and an
analysis set restricted to one variant has only one of them --- so on
``--population answerable`` there is no should-escalate instance, recall is 0/0,
and precision is 0.0 whatever the arm did (its numerator is a structural zero);
on ``--population redacted`` there is no should-NOT-escalate instance, so
precision cannot be wrong --- it is 1.0 for any arm that escalates at all --- and
F1 collapses to a monotone function of recall, which is the recall-alone number
PREREGISTRATION.md section 5 forbids reporting.
``aggregate`` returns 0.0 for an empty denominator because it must return a
float into the bootstrap, so left alone the report would print "escalation F1
0.000, 95% CI [0.000, 0.000]" and a paired difference of the same --- a number
that reads as a precisely estimated null and is in fact an artefact of the
population. That is the failure DEVIATIONS.md section 2 records, and the
``--population`` flag would have reintroduced it.

So: whenever the analysis set is missing either row of the 2x2, escalation
precision, recall and F1 are reported as **undefined** --- ``null`` in the JSON
summary, ``n/a`` in the markdown, and the section heading says NOT ESTIMABLE ---
in the point estimate, the interval and the paired difference alike. The
**counts** are still counts and are still printed: on the answerable population
the should-not-but-did column is the numerator of the false-escalation **rate**
that PREREGISTRATION.md section 6 names as H2's explicit cost criterion (the
registered quantity is the rate; the count over the population's trials is how
it is computed), and it is the reason the table is annotated rather than
dropped. The condition is a
property of the analysis set, not of the flag: an intersection that happens to
contain no redacted twin is suppressed the same way.

MCNEMAR'S EXACT TEST (PREREGISTRATION.md section 5)
----------------------------------------------------
Section 5 registers "paired bootstrap confidence intervals ... and McNemar's
test for paired binary outcomes". The paired binary outcome is the per-instance
pass^k indicator (``InstanceStats.all_correct``). For every non-baseline
condition, over the analysis population, the scorer counts the discordant
instances --- the ones the baseline got right and the condition did not, and the
reverse --- and reports the exact two-sided binomial p,
``min(1, 2 * P(X <= min(b, c)))`` for ``X ~ Binomial(b + c, 1/2)``, computed in
exact integer arithmetic and converted to float only at the end. No normal
approximation and no continuity correction: at these counts the exact test is
free. ``n_discordant == 0`` gives p = 1.0. Concordant instances carry no
information for this test and are not counted by it.

SCORING CONVENTIONS (fixed here, so they cannot drift between analyses)
-----------------------------------------------------------------------
* Gold decision is ``"illegal"`` when ``gold.answer`` is true, ``"legal"`` when it
  is false, and ``"cannot_decide"`` for a redacted twin --- on a redacted
  instance, abstaining *is* the right answer.
* A **parse failure is a wrong answer** and is **not** an escalation. It is also
  counted separately so a condition cannot hide behind unparseable output.
* An **arm-B engine refusal** is likewise a wrong, non-escalating answer, per the
  preregistered rule.
* ``cited_rules`` is compared as a **set** after normalisation to lowercase
  alphanumerics. RuleArena's gold column spells a handful of identifiers
  inconsistently (``nontaxpayer_...`` vs ``non_taxpayer_...``); normalising means
  the citation metric measures rule identification, not spelling. Instances whose
  gold carries no ``relevant_rules`` are excluded from citation metrics only.
* Empty-vs-empty citation sets score 1.0; predicting a non-empty set against an
  empty gold scores precision 0.0.
* ``pass^k`` uses the first k trials in trial order, where k is the smallest trial
  count any condition has for that instance, so the comparison is like for like.

REDACTED-TWIN DETECTION (the contract this file consumes)
----------------------------------------------------------
An instance should escalate when, in priority order:

1. ``gold.should_escalate`` is a boolean --- that value wins;
2. ``variant`` is ``"redacted"`` / ``"answerable"`` --- ``redact.py``'s own label,
   which is authoritative because it stamps a ``redaction`` record into **both**
   twins of a pair (the answerable twin records what its counterpart lost);
3. ``expected_decision == "cannot_decide"``;
4. ``instance["redaction"]["applied"]`` is true, or, for documents that predate
   that key, ``instance["redaction"]`` is present and truthy;
5. the ``instance_id`` ends with ``#redacted`` / ``-redacted`` or contains
   ``#redacted-``.

Its non-redacted partner is ``pair_id`` when present, else
``redaction.base_instance_id``, else the id with that suffix stripped. Every other
instance is a should-NOT-escalate case and is included in the 2x2, which is what
makes always-escalate score badly.

INSTANCE IDENTITY
-----------------
``redact.py`` gives the two twins of a pair the **same** ``instance_id`` --- they
are the same problem --- and tells them apart with ``twin_id``. Rows and
instances are therefore keyed by ``twin_id`` when it is present (``arms.
instance_key``), matching the ``row_id`` that ``run.py`` writes. Keying on
``instance_id`` would collapse each pair into one instance and silently destroy
the escalation design.

SUMMARY SCHEMA
--------------
The JSON summary is ``jps-study-001-score/3``. Version 2 added five fields and
removes none: top-level ``population`` and ``bootstrap_unit`` (the two choices
above, recorded so a report says on what it was computed), ``bootstrap_clusters``
(how many resampling units the bootstrap drew from) and ``escalation_estimable``
(whether the 2x2 has both its rows on this analysis set), plus
``mcnemar_pass_at_k`` on every **non-baseline** condition ---
``n_baseline_only_correct``, ``n_condition_only_correct``, ``n_discordant``,
``p_value``. The baseline condition carries no such entry: a condition has no
discordant instances against itself, and writing p = 1.0 there would look like a
result. Everything version 1 wrote is still written and still means the same
thing, with one deliberate exception in one new situation: when
``escalation_estimable`` is false the three escalation rate metrics are ``null``
instead of the 0.0 a version-1 report would have printed, in ``point``, in
``ci95`` and in ``delta_vs_baseline``. Reaching it takes an analysis set missing
one row of the 2x2, which the study's own runs are not (216 twins of each
variant, all paired), so on this corpus ``--population all --bootstrap-unit
twin`` reproduces a version-1 report's numbers exactly --- checked field by field
against ``results/k5-report.json``, which differs only in ``schema`` and in the
added fields.

Version 3 adds two more fields and removes none. ``analysis_role`` is
``registered-primary`` when the run is on the configuration
``REGISTERED_ANALYSIS`` names and ``secondary`` otherwise --- including on the
defaults, which are the shipped behaviour rather than the registered one.
``registered_primary`` records whether the registered endpoint is estimable at
all from this analysis set and, when it is not, every reason why. The reason
that matters here is not hypothetical: the endpoint is pooled across both model
families, only Codex ran, and this scorer has no cross-backend pooling
operation, so no invocation of it can produce that endpoint. Marking the
all-twins run ``secondary`` is the same guard in the other direction --- that
population is what the first draft reported as though it were primary. Every
version-2 field is still written and still means the same thing.

WHAT THIS FILE DELIBERATELY DOES NOT DO
---------------------------------------
* No unpaired comparisons and no "best of the trials". Conditions are only ever
  compared on the shared instance set.
* No recall-only escalation number, anywhere.
* Exactly one significance test: McNemar's exact test on the pass^k indicator,
  computed because PREREGISTRATION.md section 5 registers it and its absence from
  this file was a recorded deviation (DEVIATIONS.md section 3). No OTHER test is
  added --- no test on accuracy, on the citation metrics, or on the escalation
  2x2, all of which carry bootstrap intervals and the bootstrap probability that
  a difference exceeds zero, and nothing else.
* No multiplicity correction, because the study registered one primary endpoint;
  a p reported beside a secondary metric would need one, so none is reported.
* No decision rule. The scorer prints the counts and the p; whether a hypothesis
  passed is settled by the falsification criteria in PREREGISTRATION.md section
  6, not here.
* No repair of malformed rows, no imputation of missing trials.
* No knowledge of which population a hypothesis registered: ``--population``
  makes the analysis set explicit and auditable, it does not choose it.

Python 3.10+ (``from __future__ import annotations`` keeps it importable on 3.8).
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from fractions import Fraction
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from arms import instance_key  # noqa: E402
from run import load_instances  # noqa: E402

DECISIONS = ("legal", "illegal", "cannot_decide")
_NORM_RE = re.compile(r"[^a-z0-9]+")
_REDACTED_SUFFIXES = ("#redacted", "-redacted")
POPULATIONS = ("all", "answerable", "redacted")
BOOTSTRAP_UNITS = ("twin", "pair")

#: The analysis PREREGISTRATION.md section 2 registers: H1 as pass^k on the
#: **answerable** population, arm B against arm A, **pooled across both model
#: families**. The scorer's defaults are deliberately *not* this --- they are
#: the shipped behaviour every published interval was computed with --- so the
#: registered configuration has to be nameable rather than assembled by an
#: operator who remembers two flags. That is what ``--registered`` selects.
REGISTERED_ANALYSIS = {"population": "answerable", "bootstrap_unit": "pair"}

#: Section 3 registers three arms x **two model families**. ``mock`` is not one
#: of them: ``backends.py`` says of it that it "never claims to be a real
#: model", and arm B reaches the deterministic evaluator through it. Counting a
#: mock backend as a family would let a run with no model in it at all report
#: the pooled endpoint.
REGISTERED_MODEL_FAMILIES = ("anthropic", "codex")
# The three escalation numbers that are ratios rather than counts. They are the
# ones a single-row 2x2 makes undefined, and the ones suppressed when it is.
ESCALATION_RATE_METRICS = (
    "escalation_precision", "escalation_recall", "escalation_f1")


# --------------------------------------------------------------------------- #
# Gold / redaction contract
# --------------------------------------------------------------------------- #


def should_escalate(instance: Mapping[str, Any]) -> bool:
    gold = instance.get("gold") or {}
    if isinstance(gold.get("should_escalate"), bool):
        return bool(gold["should_escalate"])
    variant = instance.get("variant")
    if variant == "redacted":
        return True
    if variant == "answerable":
        return False
    if instance.get("expected_decision") == "cannot_decide":
        return True
    redaction = instance.get("redaction")
    if isinstance(redaction, Mapping) and isinstance(redaction.get("applied"), bool):
        return bool(redaction["applied"])
    if redaction:
        return True
    iid = str(instance.get("instance_id", ""))
    if any(iid.endswith(sfx) for sfx in _REDACTED_SUFFIXES):
        return True
    return "#redacted-" in iid


def base_instance_id(instance: Mapping[str, Any]) -> str:
    iid = str(instance.get("instance_id", ""))
    if isinstance(instance.get("pair_id"), str) and instance["pair_id"]:
        return instance["pair_id"]
    redaction = instance.get("redaction")
    if isinstance(redaction, Mapping) and isinstance(redaction.get("base_instance_id"), str):
        return redaction["base_instance_id"]
    for sfx in _REDACTED_SUFFIXES:
        if iid.endswith(sfx):
            return iid[: -len(sfx)]
    if "#redacted-" in iid:
        return iid.split("#redacted-", 1)[0]
    return iid


def gold_decision(instance: Mapping[str, Any]) -> Optional[str]:
    if should_escalate(instance):
        return "cannot_decide"
    gold = instance.get("gold") or {}
    answer = gold.get("answer")
    if isinstance(answer, bool):
        return "illegal" if answer else "legal"
    if isinstance(gold.get("decision"), str) and gold["decision"] in DECISIONS:
        return gold["decision"]
    return None


def gold_rules(instance: Mapping[str, Any]) -> Optional[set]:
    gold = instance.get("gold") or {}
    rules = gold.get("relevant_rules")
    if not isinstance(rules, list):
        return None
    return {normalise_rule_id(r) for r in rules if isinstance(r, str)}


def normalise_rule_id(rule_id: str) -> str:
    return _NORM_RE.sub("", rule_id.lower())


# --------------------------------------------------------------------------- #
# Result loading
# --------------------------------------------------------------------------- #


def condition_key(row: Mapping[str, Any]) -> str:
    return "%s::%s::%s" % (row.get("arm"), row.get("backend"), row.get("model"))


RESULT_SCHEMA = "jps-study-001-result/1"


def _check_result_row(row: Any, path: str, lineno: int) -> Tuple[str, str, int]:
    """Validate one decoded JSONL line; return its (condition, identity, trial).

    Identity and grouping fields only: unknown extra fields are allowed, and
    the scoring fields (``prediction``, ``parse_ok``, ...) are the scorer's
    business, not the loader's. Every failure names its file and line number.
    """
    if not isinstance(row, dict):
        raise ValueError("%s line %d: result row must be a JSON object" % (path, lineno))
    if row.get("schema") != RESULT_SCHEMA:
        raise ValueError(
            "%s line %d: unsupported schema %r (expected %r)"
            % (path, lineno, row.get("schema"), RESULT_SCHEMA)
        )
    for field in ("arm", "backend", "model"):
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(
                "%s line %d: %s must be a non-empty string" % (path, lineno, field)
            )
    trial = row.get("trial")
    if isinstance(trial, bool) or not isinstance(trial, int) or trial < 1:
        raise ValueError("%s line %d: trial must be an integer >= 1" % (path, lineno))
    rid = row.get("row_id")
    if not rid:
        rid = row.get("instance_id")
        if not isinstance(rid, str) or not rid:
            raise ValueError(
                "%s line %d: row_id is absent or empty and instance_id is not "
                "a non-empty string" % (path, lineno)
            )
    elif not isinstance(rid, str):
        raise ValueError("%s line %d: row_id must be a string" % (path, lineno))
    return condition_key(row), rid, trial


def load_results(paths: Sequence[str]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Return ``{condition: {row_id: [rows sorted by trial]}}``.

    Rows are keyed by ``row_id`` (``run.py``'s twin-aware identity) and fall back
    to ``instance_id`` for documents that are not twins.

    Every non-empty line is validated before it enters the map: it must decode
    to an object with schema ``jps-study-001-result/1``, non-empty string
    ``arm``/``backend``/``model``, an integer ``trial`` of at least 1 (booleans
    rejected), and a string ``row_id`` -- falling back to a non-empty string
    ``instance_id`` when ``row_id`` is absent or empty. A repeated ``(arm,
    backend, model, row identity, trial)`` cell, within one file or across the
    files of one call, is rejected: it would otherwise fail later with an
    unclear exception or silently distort the cell. Unknown extra fields are
    allowed. Every error names its file and line number.
    """
    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    seen: set = set()
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError as exc:
                    raise ValueError("%s line %d: %s" % (path, lineno, exc))
                cond, rid, trial = _check_result_row(row, path, lineno)
                cell = (row["arm"], row["backend"], row["model"], rid, trial)
                if cell in seen:
                    raise ValueError(
                        "%s line %d: duplicate result cell %r" % (path, lineno, cell)
                    )
                seen.add(cell)
                out.setdefault(cond, {}).setdefault(rid, []).append(row)
    for by_instance in out.values():
        for rows in by_instance.values():
            rows.sort(key=lambda r: r.get("trial", 0))
    return out


# --------------------------------------------------------------------------- #
# Per-instance sufficient statistics
# --------------------------------------------------------------------------- #


class InstanceStats:
    """Everything a metric needs from one (condition, instance), precomputed.

    Keeping the bootstrap on these aggregates rather than on raw rows makes 2000
    replicates over 216 instances cheap and, more importantly, guarantees that the
    resample is at the *instance* level --- the paired unit of the design.
    """

    __slots__ = ("k", "n_correct", "all_correct", "n_parse_ok", "n_engine_refusal",
                 "cite_precision", "cite_recall", "cite_f1", "has_citation_gold",
                 "cite_tp", "cite_pred", "cite_gold",
                 "esc_tp", "esc_fp", "esc_fn", "esc_tn")

    def __init__(self) -> None:
        self.k = 0
        self.n_correct = 0
        self.all_correct = False
        self.n_parse_ok = 0
        self.n_engine_refusal = 0
        self.cite_precision = 0.0
        self.cite_recall = 0.0
        self.cite_f1 = 0.0
        self.has_citation_gold = False
        self.cite_tp = 0
        self.cite_pred = 0
        self.cite_gold = 0
        self.esc_tp = 0
        self.esc_fp = 0
        self.esc_fn = 0
        self.esc_tn = 0


def _prf(pred: set, gold: set) -> Tuple[float, float, float]:
    tp = len(pred & gold)
    if not pred and not gold:
        return (1.0, 1.0, 1.0)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 1.0
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return (precision, recall, f1)


def compute_instance_stats(rows: Sequence[Mapping[str, Any]],
                           instance: Mapping[str, Any],
                           k: int) -> InstanceStats:
    stats = InstanceStats()
    stats.k = k
    target = gold_decision(instance)
    g_rules = gold_rules(instance)
    stats.has_citation_gold = g_rules is not None
    escalate_expected = should_escalate(instance)

    p_sum = r_sum = f_sum = 0.0
    all_correct = True
    for row in rows[:k]:
        parse_ok = bool(row.get("parse_ok"))
        prediction = row.get("prediction") if parse_ok else None
        decision = (prediction or {}).get("decision")
        correct = bool(parse_ok and target is not None and decision == target)
        stats.n_correct += int(correct)
        all_correct = all_correct and correct
        stats.n_parse_ok += int(parse_ok)
        error = row.get("error") or ""
        if isinstance(error, str) and (error.startswith("engine-refusal")
                                       or error.startswith("outcome-map-failure")):
            stats.n_engine_refusal += 1

        if g_rules is not None:
            pred_rules = set()
            if parse_ok:
                pred_rules = {normalise_rule_id(x)
                              for x in (prediction or {}).get("cited_rules", [])
                              if isinstance(x, str)}
            precision, recall, f1 = _prf(pred_rules, g_rules)
            p_sum += precision
            r_sum += recall
            f_sum += f1
            stats.cite_tp += len(pred_rules & g_rules)
            stats.cite_pred += len(pred_rules)
            stats.cite_gold += len(g_rules)

        did_escalate = bool(parse_ok and decision == "cannot_decide")
        if escalate_expected and did_escalate:
            stats.esc_tp += 1
        elif (not escalate_expected) and did_escalate:
            stats.esc_fp += 1
        elif escalate_expected and (not did_escalate):
            stats.esc_fn += 1
        else:
            stats.esc_tn += 1

    stats.all_correct = all_correct and k > 0
    if k and g_rules is not None:
        stats.cite_precision = p_sum / k
        stats.cite_recall = r_sum / k
        stats.cite_f1 = f_sum / k
    return stats


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def aggregate(stats_by_instance: Mapping[str, InstanceStats],
              instance_ids: Sequence[str]) -> Dict[str, float]:
    """Aggregate per-instance stats over a (possibly resampled) list of ids."""
    n = len(instance_ids)
    if n == 0:
        return {}
    acc = pass_k = parse_ok = refusal = 0.0
    cp = cr = cf = 0.0
    cite_n = 0
    tp_sum = pred_sum = gold_sum = 0
    e_tp = e_fp = e_fn = e_tn = 0
    for iid in instance_ids:
        s = stats_by_instance[iid]
        acc += (s.n_correct / s.k) if s.k else 0.0
        pass_k += 1.0 if s.all_correct else 0.0
        parse_ok += (s.n_parse_ok / s.k) if s.k else 0.0
        refusal += (s.n_engine_refusal / s.k) if s.k else 0.0
        if s.has_citation_gold:
            cite_n += 1
            cp += s.cite_precision
            cr += s.cite_recall
            cf += s.cite_f1
            tp_sum += s.cite_tp
            pred_sum += s.cite_pred
            gold_sum += s.cite_gold
        e_tp += s.esc_tp
        e_fp += s.esc_fp
        e_fn += s.esc_fn
        e_tn += s.esc_tn

    micro_p = (tp_sum / pred_sum) if pred_sum else (1.0 if gold_sum == 0 else 0.0)
    micro_r = (tp_sum / gold_sum) if gold_sum else 1.0
    micro_f = 0.0 if (micro_p + micro_r) == 0 else 2 * micro_p * micro_r / (micro_p + micro_r)

    esc_p = (e_tp / (e_tp + e_fp)) if (e_tp + e_fp) else 0.0
    esc_r = (e_tp / (e_tp + e_fn)) if (e_tp + e_fn) else 0.0
    esc_f = 0.0 if (esc_p + esc_r) == 0 else 2 * esc_p * esc_r / (esc_p + esc_r)

    return {
        "accuracy": acc / n,
        "pass_at_k": pass_k / n,
        "parse_ok_rate": parse_ok / n,
        "engine_refusal_rate": refusal / n,
        "citation_precision": (cp / cite_n) if cite_n else 0.0,
        "citation_recall": (cr / cite_n) if cite_n else 0.0,
        "citation_f1": (cf / cite_n) if cite_n else 0.0,
        "citation_micro_precision": micro_p,
        "citation_micro_recall": micro_r,
        "citation_micro_f1": micro_f,
        "escalation_precision": esc_p,
        "escalation_recall": esc_r,
        "escalation_f1": esc_f,
        "escalation_tp": float(e_tp),
        "escalation_fp": float(e_fp),
        "escalation_fn": float(e_fn),
        "escalation_tn": float(e_tn),
    }


POINT_METRICS = (
    "accuracy", "pass_at_k", "parse_ok_rate", "engine_refusal_rate",
    "citation_precision", "citation_recall", "citation_f1",
    "citation_micro_precision", "citation_micro_recall", "citation_micro_f1",
    "escalation_precision", "escalation_recall", "escalation_f1",
)


def percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


# --------------------------------------------------------------------------- #
# Analysis population and resampling unit
# --------------------------------------------------------------------------- #


def filter_population(instance_ids: Sequence[str],
                      by_id: Mapping[str, Mapping[str, Any]],
                      population: str) -> List[str]:
    """Restrict a paired instance set to one twin variant.

    ``population`` is one of ``POPULATIONS``. ``all`` is the identity. The other
    two match the instance document's ``variant`` field exactly --- the label
    ``redact.py`` stamps into both twins --- and never infer the variant from the
    id or from ``should_escalate``: an inference here would quietly re-define the
    registered population, which is the failure DEVIATIONS.md section 2 records.

    Selecting nothing raises. An empty analysis set is a mistake in the command
    line or in the instance corpus, and a report over zero instances would be
    worse than no report.
    """
    if population not in POPULATIONS:
        raise ValueError("unknown population %r; expected one of %s"
                         % (population, ", ".join(POPULATIONS)))
    if population == "all":
        return list(instance_ids)
    kept = [iid for iid in instance_ids
            if by_id[iid].get("variant") == population]
    if not kept:
        raise ValueError(
            "--population %s selects no instances out of the %d paired ones: no "
            "instance document carries variant == %r. The filter reads the "
            "'variant' field written by redact.py and nothing else."
            % (population, len(instance_ids), population))
    return kept


def bootstrap_clusters(instance_ids: Sequence[str],
                       by_id: Mapping[str, Mapping[str, Any]],
                       unit: str) -> List[List[str]]:
    """Group the analysis set into the units the bootstrap resamples.

    ``twin`` gives one singleton cluster per instance, in the order of
    ``instance_ids``. ``pair`` groups by ``base_instance_id`` so that the two
    twins of a pair are drawn or dropped together; clusters are ordered by first
    appearance in ``instance_ids``, which is deterministic (the caller passes a
    sorted list) and makes the two units *identical* --- same order, same
    singletons --- whenever every cluster has one member, as on a single-variant
    population.
    """
    if unit not in BOOTSTRAP_UNITS:
        raise ValueError("unknown bootstrap unit %r; expected one of %s"
                         % (unit, ", ".join(BOOTSTRAP_UNITS)))
    if unit == "twin":
        return [[iid] for iid in instance_ids]
    order: List[str] = []
    members: Dict[str, List[str]] = {}
    for iid in instance_ids:
        key = base_instance_id(by_id[iid])
        if key not in members:
            members[key] = []
            order.append(key)
        members[key].append(iid)
    return [members[key] for key in order]


def model_families_present(conditions: Sequence[str]) -> List[str]:
    """Which preregistered model families this analysis set actually contains.

    Read off the ``backend`` field of the condition keys, keeping only the
    families section 3 registered. A backend outside that set --- ``mock``, or
    anything added later --- is not counted, so an all-mock run reports zero
    families rather than one.
    """
    present = set()
    for cond in conditions:
        parts = cond.split("::")
        if len(parts) >= 2 and parts[1] in REGISTERED_MODEL_FAMILIES:
            present.add(parts[1])
    return sorted(present)


def registered_primary_status(conditions: Sequence[str],
                              population: str) -> Dict[str, Any]:
    """Can the registered primary endpoint be estimated from this analysis set?

    The endpoint is H1 as pass^k on the answerable population, B against A,
    **pooled across both model families**. This scorer produces separate
    ``arm::backend::model`` conditions and has no cross-backend pooling
    operation, so with one family present the endpoint is not estimable --- and
    saying so is the point. The failure this encodes is not hypothetical: the
    study ran Codex only, and its first draft reported a Codex-only number as
    though it were the registered endpoint.

    Reports every reason it fails rather than the first, so an operator fixing
    one does not rediscover the next on the following run.
    """
    families = model_families_present(conditions)
    missing = [f for f in REGISTERED_MODEL_FAMILIES if f not in families]
    reasons: List[str] = []
    if missing:
        reasons.append(
            "only %d of the %d preregistered model families ran (%s); missing %s"
            % (len(families), len(REGISTERED_MODEL_FAMILIES),
               ", ".join(families) or "none", ", ".join(missing)))
    if population != REGISTERED_ANALYSIS["population"]:
        reasons.append(
            "the registered endpoint is defined on the '%s' population, "
            "not '%s'" % (REGISTERED_ANALYSIS["population"], population))
    return {
        "endpoint": ("H1 as pass^k on the answerable population, arm B against "
                     "arm A, pooled across both model families"),
        "estimable": not reasons,
        "reasons": reasons,
        "families_present": families,
        "families_required": list(REGISTERED_MODEL_FAMILIES),
    }


def escalation_is_estimable(instance_ids: Sequence[str],
                            by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    """Does this analysis set populate **both** rows of the escalation 2x2?

    True only when it holds at least one should-escalate instance and at least
    one should-NOT-escalate instance. With a row missing, escalation precision,
    recall and F1 are artefacts of the population rather than measurements of an
    arm --- see the module docstring for which of them degenerates in which
    direction --- and ``score`` reports all three as undefined rather than as the
    0.0 that ``aggregate`` must return into the bootstrap.

    Deliberately a property of the *instance set*, not of ``--population``: a
    cross-condition intersection that happens to contain no redacted twin is
    exactly as unable to estimate the 2x2 as ``--population answerable`` is.
    """
    seen_should = seen_should_not = False
    for iid in instance_ids:
        if should_escalate(by_id[iid]):
            seen_should = True
        else:
            seen_should_not = True
        if seen_should and seen_should_not:
            return True
    return False


def resample_clusters(clusters: Sequence[Sequence[str]],
                      rng: random.Random) -> List[str]:
    """Draw ``len(clusters)`` clusters with replacement and concatenate members.

    Exactly one ``rng.randrange(len(clusters))`` call per drawn cluster, in
    order. With singleton clusters this consumes randomness identically to the
    twin-level resample this file shipped with, so a ``--bootstrap-unit twin``
    run reproduces previously published intervals bit for bit.
    """
    n = len(clusters)
    out: List[str] = []
    for _ in range(n):
        out.extend(clusters[rng.randrange(n)])
    return out


# --------------------------------------------------------------------------- #
# McNemar's exact test (PREREGISTRATION.md section 5)
# --------------------------------------------------------------------------- #


def mcnemar_exact_p(n_baseline_only: int, n_condition_only: int) -> float:
    """Exact two-sided binomial p for a McNemar table's discordant cells.

    ``min(1, 2 * P(X <= min(b, c)))`` with ``X ~ Binomial(b + c, 1/2)``. The tail
    is summed with ``math.comb`` over exact integers and divided as a
    ``Fraction``, so the only rounding is the final conversion to float; no
    normal approximation, no continuity correction. Zero discordant instances is
    no evidence either way and returns 1.0.
    """
    if n_baseline_only < 0 or n_condition_only < 0:
        raise ValueError("discordant counts must be non-negative, got (%d, %d)"
                         % (n_baseline_only, n_condition_only))
    n = n_baseline_only + n_condition_only
    if n == 0:
        return 1.0
    lo = min(n_baseline_only, n_condition_only)
    tail = Fraction(sum(math.comb(n, i) for i in range(lo + 1)), 1 << n)
    return float(min(Fraction(1), 2 * tail))


def mcnemar_pass_at_k(baseline_stats: Mapping[str, InstanceStats],
                      condition_stats: Mapping[str, InstanceStats],
                      instance_ids: Sequence[str]) -> Dict[str, Any]:
    """The registered paired test, on the per-instance pass^k indicator.

    The indicator is ``InstanceStats.all_correct``: every one of the k trials on
    that instance produced the correct decision. Instances the two conditions
    agree about contribute nothing and are not counted here.
    """
    b = c = 0
    for iid in instance_ids:
        base_ok = baseline_stats[iid].all_correct
        cond_ok = condition_stats[iid].all_correct
        if base_ok and not cond_ok:
            b += 1
        elif cond_ok and not base_ok:
            c += 1
    return {
        "n_baseline_only_correct": b,
        "n_condition_only_correct": c,
        "n_discordant": b + c,
        "p_value": mcnemar_exact_p(b, c),
    }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def score(instances: Sequence[Mapping[str, Any]],
          results: Mapping[str, Mapping[str, List[Dict[str, Any]]]],
          *, bootstrap: int, seed: int,
          baseline: Optional[str],
          population: str = "all",
          bootstrap_unit: str = "twin") -> Dict[str, Any]:
    by_id = {instance_key(i): i for i in instances}
    if len(by_id) != len(instances):
        raise ValueError(
            "instance identities collide: %d documents map to %d keys. Twins must "
            "carry distinct twin_id values." % (len(instances), len(by_id)))
    conditions = sorted(results)
    if not conditions:
        raise ValueError("no result rows found")

    # Paired instance set: covered by every condition and present in the gold set.
    shared = set(by_id)
    for cond in conditions:
        shared &= set(results[cond])
    paired = sorted(shared)
    if not paired:
        raise ValueError(
            "the conditions share no instances; a paired comparison is impossible")

    # Analysis population: applied after the intersection, so that every
    # condition is still compared on exactly the same instances.
    paired = filter_population(paired, by_id, population)

    # k per instance = min trial count across conditions.
    k_by_instance: Dict[str, int] = {}
    for iid in paired:
        k_by_instance[iid] = min(len(results[cond][iid]) for cond in conditions)

    stats: Dict[str, Dict[str, InstanceStats]] = {}
    for cond in conditions:
        stats[cond] = {
            iid: compute_instance_stats(results[cond][iid], by_id[iid], k_by_instance[iid])
            for iid in paired
        }

    point = {cond: aggregate(stats[cond], paired) for cond in conditions}

    if baseline is not None and baseline not in point:
        raise ValueError("baseline %r is not among the conditions: %s"
                         % (baseline, ", ".join(conditions)))
    if baseline is None:
        baseline = conditions[0]

    # ---- paired bootstrap -------------------------------------------------- #
    clusters = bootstrap_clusters(paired, by_id, bootstrap_unit)
    rng = random.Random(seed)
    n = len(paired)
    draws: Dict[str, Dict[str, List[float]]] = {
        cond: {m: [] for m in POINT_METRICS} for cond in conditions}
    delta_draws: Dict[str, Dict[str, List[float]]] = {
        cond: {m: [] for m in POINT_METRICS} for cond in conditions}

    for _ in range(bootstrap):
        resample = resample_clusters(clusters, rng)
        agg = {cond: aggregate(stats[cond], resample) for cond in conditions}
        base_agg = agg[baseline]
        for cond in conditions:
            for metric in POINT_METRICS:
                draws[cond][metric].append(agg[cond][metric])
                delta_draws[cond][metric].append(agg[cond][metric] - base_agg[metric])

    summary: Dict[str, Any] = {
        "schema": "jps-study-001-score/3",
        "paired_instances": n,
        "instance_ids": paired,
        "population": population,
        "trials_per_instance": {
            "min": min(k_by_instance.values()),
            "max": max(k_by_instance.values()),
        },
        "redacted_instances": sum(1 for iid in paired if should_escalate(by_id[iid])),
        "bootstrap_replicates": bootstrap,
        "bootstrap_seed": seed,
        "bootstrap_unit": bootstrap_unit,
        "bootstrap_clusters": len(clusters),
        "escalation_estimable": escalation_is_estimable(paired, by_id),
        "analysis_role": (
            "registered-primary"
            if (population == REGISTERED_ANALYSIS["population"]
                and bootstrap_unit == REGISTERED_ANALYSIS["bootstrap_unit"])
            else "secondary"),
        "registered_primary": registered_primary_status(conditions, population),
        "baseline": baseline,
        "conditions": {},
    }

    for cond in conditions:
        entry: Dict[str, Any] = {"point": point[cond], "ci95": {}, "delta_vs_baseline": {}}
        for metric in POINT_METRICS:
            vals = sorted(draws[cond][metric])
            entry["ci95"][metric] = [percentile(vals, 0.025), percentile(vals, 0.975)]
            dvals = sorted(delta_draws[cond][metric])
            gt0 = sum(1 for v in delta_draws[cond][metric] if v > 0)
            entry["delta_vs_baseline"][metric] = {
                "point": point[cond][metric] - point[baseline][metric],
                "ci95": [percentile(dvals, 0.025), percentile(dvals, 0.975)],
                "prob_gt_0": (gt0 / bootstrap) if bootstrap else float("nan"),
            }
        entry["escalation_2x2"] = {
            "should_and_did": int(point[cond]["escalation_tp"]),
            "should_not_but_did": int(point[cond]["escalation_fp"]),
            "should_but_did_not": int(point[cond]["escalation_fn"]),
            "neither": int(point[cond]["escalation_tn"]),
        }
        if cond != baseline:
            entry["mcnemar_pass_at_k"] = mcnemar_pass_at_k(
                stats[baseline], stats[cond], paired)
        summary["conditions"][cond] = entry

    if not summary["escalation_estimable"]:
        # One row of the 2x2 is empty on this analysis set, so its three ratio
        # metrics are undefined, not zero. They are nulled here rather than at
        # the source: `aggregate` has to hand a float to the bootstrap, and the
        # differences above must be built before anything is suppressed so that
        # nothing silently differences a null. The 2x2 counts, which are
        # perfectly well defined, are left exactly as they are.
        for entry in summary["conditions"].values():
            for metric in ESCALATION_RATE_METRICS:
                entry["point"][metric] = None
                entry["ci95"][metric] = None
                entry["delta_vs_baseline"][metric] = None
    return summary


def _fmt(value: Optional[float]) -> str:
    """Three decimals; ``n/a`` for NaN and for the ``None`` of an undefined metric.

    A metric the analysis set cannot estimate is ``None`` in the summary and must
    not be rendered as a number: "0.000" and "undefined" are different claims.
    """
    if value is None:
        return "n/a"
    if value != value:  # NaN
        return "n/a"
    return "%.3f" % value


def _fmt_ci(bounds: Optional[Sequence[float]]) -> str:
    if bounds is None:
        return "n/a"
    return "[%s, %s]" % (_fmt(bounds[0]), _fmt(bounds[1]))


def _delta_cells(delta: Optional[Mapping[str, Any]]) -> Tuple[str, str]:
    """The (point, interval) pair of cells for one paired difference.

    ``("n/a", "n/a")`` when the whole difference is ``None`` --- the metric is not
    estimable on this analysis set, so neither is a difference in it.
    """
    if delta is None:
        return ("n/a", "n/a")
    return (_fmt(delta["point"]), _fmt_ci(delta["ci95"]))


def _fmt_p(value: float) -> str:
    """Four decimals down to 0.001, scientific below it --- never "p < 0.05"."""
    if value != value:  # NaN
        return "n/a"
    if value >= 1e-3:
        return "%.4f" % value
    return "%.3e" % value


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Study 001 -- policy representation: scored results")
    lines.append("")
    lines.append("Paired design over %d instances shared by every condition "
                 "(%d of them redacted twins). Analysis population: `%s`. "
                 "Trials per instance: %d-%d. "
                 "Intervals are 95%% percentile intervals from %d paired bootstrap "
                 "resamples of %d `%s` clusters (seed %d). Baseline: `%s`."
                 % (summary["paired_instances"], summary["redacted_instances"],
                    summary["population"],
                    summary["trials_per_instance"]["min"],
                    summary["trials_per_instance"]["max"],
                    summary["bootstrap_replicates"],
                    summary["bootstrap_clusters"], summary["bootstrap_unit"],
                    summary["bootstrap_seed"], summary["baseline"]))
    lines.append("")

    # Stated before any number, because the number's standing is the first
    # thing a reader needs and the last thing a reader checks.
    reg = summary.get("registered_primary")
    role = summary.get("analysis_role")
    if role == "registered-primary":
        lines.append("**Analysis role: the registered configuration.** "
                     "Population and resampling unit are the ones "
                     "PREREGISTRATION.md section 2 registers.")
    elif role is not None:
        lines.append("**Analysis role: SECONDARY.** This is not the registered "
                     "configuration (registered: population `%s`, bootstrap "
                     "unit `%s`); it cannot stand in for the primary endpoint."
                     % (REGISTERED_ANALYSIS["population"],
                        REGISTERED_ANALYSIS["bootstrap_unit"]))
    if reg is not None and not reg["estimable"]:
        lines.append("")
        lines.append("**The registered primary endpoint is NOT ESTIMABLE from "
                     "this analysis set.** It is %s. Reasons: %s. No table "
                     "below is that endpoint."
                     % (reg["endpoint"], "; ".join(reg["reasons"])))
    lines.append("")

    conds = list(summary["conditions"])

    lines.append("## Accuracy and consistency")
    lines.append("")
    lines.append("| condition | accuracy | 95% CI | pass^k | 95% CI | parse-ok rate | "
                 "engine-refusal rate |")
    lines.append("|---|---:|---|---:|---|---:|---:|")
    for cond in conds:
        c = summary["conditions"][cond]
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s |" % (
            cond,
            _fmt(c["point"]["accuracy"]), _fmt_ci(c["ci95"]["accuracy"]),
            _fmt(c["point"]["pass_at_k"]), _fmt_ci(c["ci95"]["pass_at_k"]),
            _fmt(c["point"]["parse_ok_rate"]),
            _fmt(c["point"]["engine_refusal_rate"]),
        ))
    lines.append("")

    lines.append("## Citation quality vs gold `relevant_rules`")
    lines.append("")
    lines.append("| condition | precision | recall | F1 | 95% CI (F1) | micro F1 |")
    lines.append("|---|---:|---:|---:|---|---:|")
    for cond in conds:
        c = summary["conditions"][cond]
        lines.append("| `%s` | %s | %s | %s | %s | %s |" % (
            cond,
            _fmt(c["point"]["citation_precision"]),
            _fmt(c["point"]["citation_recall"]),
            _fmt(c["point"]["citation_f1"]),
            _fmt_ci(c["ci95"]["citation_f1"]),
            _fmt(c["point"]["citation_micro_f1"]),
        ))
    lines.append("")

    estimable = summary.get("escalation_estimable", True)
    lines.append("## Escalation on redacted twins (full 2x2)%s"
                 % ("" if estimable else " -- NOT ESTIMABLE on this analysis set"))
    lines.append("")
    if estimable:
        lines.append("Recall alone is not reported: an always-escalate agent scores "
                     "recall 1.0 and must be visible as such through precision and "
                     "F1.")
    else:
        if summary["redacted_instances"] == 0:
            missing = "no redacted (should-escalate) instance"
            kept = ("the should-not-but-did column is the false-escalation count "
                    "that PREREGISTRATION.md section 6 names as H2's explicit "
                    "cost criterion")
        else:
            missing = "no answerable (should-not-escalate) instance"
            kept = ("the should-but-did-not column counts the redacted trials "
                    "each arm failed to escalate on")
        lines.append(
            "**This analysis set (`population: %s`, %d instances) contains %s, so "
            "one row of the 2x2 is empty and precision, recall and F1 are "
            "undefined on it.** They are printed as `n/a`, never as 0.000, here "
            "and in the paired differences below; H2 is not estimable on this "
            "set. The counts are still counts and are still shown: %s."
            % (summary["population"], summary["paired_instances"], missing, kept))
    lines.append("")
    lines.append("| condition | should & did | should-not but did | should but did not | "
                 "neither | precision | recall | F1 | 95% CI (F1) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for cond in conds:
        c = summary["conditions"][cond]
        t = c["escalation_2x2"]
        lines.append("| `%s` | %d | %d | %d | %d | %s | %s | %s | %s |" % (
            cond, t["should_and_did"], t["should_not_but_did"],
            t["should_but_did_not"], t["neither"],
            _fmt(c["point"]["escalation_precision"]),
            _fmt(c["point"]["escalation_recall"]),
            _fmt(c["point"]["escalation_f1"]),
            _fmt_ci(c["ci95"]["escalation_f1"]),
        ))
    lines.append("")

    lines.append("## Paired differences vs baseline `%s`" % summary["baseline"])
    lines.append("")
    lines.append("| condition | d accuracy | 95% CI | P(d>0) | d pass^k | 95% CI | "
                 "d citation F1 | 95% CI | d escalation F1 | 95% CI |")
    lines.append("|---|---:|---|---:|---:|---|---:|---|---:|---|")
    for cond in conds:
        if cond == summary["baseline"]:
            continue
        d = summary["conditions"][cond]["delta_vs_baseline"]
        esc_point, esc_ci = _delta_cells(d["escalation_f1"])
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            cond,
            _fmt(d["accuracy"]["point"]), _fmt_ci(d["accuracy"]["ci95"]),
            _fmt(d["accuracy"]["prob_gt_0"]),
            _fmt(d["pass_at_k"]["point"]), _fmt_ci(d["pass_at_k"]["ci95"]),
            _fmt(d["citation_f1"]["point"]), _fmt_ci(d["citation_f1"]["ci95"]),
            esc_point, esc_ci,
        ))
    lines.append("")

    lines.append("## McNemar's exact test on the pass^k indicator")
    lines.append("")
    lines.append("PREREGISTRATION.md section 5 registers \"McNemar's test for "
                 "paired binary outcomes\"; the exact two-sided form and the "
                 "pass^k indicator as the binary are implementation choices "
                 "recorded in DEVIATIONS.md section 4. The registered primary "
                 "contrast is B vs A on the answerable population; every other "
                 "row below is exploratory and unadjusted. The paired binary "
                 "outcome is whether a condition got *all* k trials right on an "
                 "instance; only instances the two conditions disagree about "
                 "carry information, and the p is the exact two-sided binomial "
                 "probability under an even split of them.")
    lines.append("")
    lines.append("| condition vs baseline | baseline only correct | "
                 "condition only correct | discordant | exact two-sided p |")
    lines.append("|---|---:|---:|---:|---:|")
    for cond in conds:
        if cond == summary["baseline"]:
            continue
        m = summary["conditions"][cond].get("mcnemar_pass_at_k")
        if m is None:
            continue
        lines.append("| `%s` | %d | %d | %d | %s |" % (
            cond, m["n_baseline_only_correct"], m["n_condition_only_correct"],
            m["n_discordant"], _fmt_p(m["p_value"])))
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="score.py",
        description="Score study-001 results with a paired instance-level design.")
    p.add_argument("--instances", required=True,
                   help="directory of *.json instance documents, or an index.json")
    p.add_argument("--results", required=True, nargs="+", help="result JSONL files")
    p.add_argument("--baseline", default=None,
                   help="condition key 'arm::backend::model' to difference against")
    p.add_argument("--registered", action="store_true",
                   help="run the configuration PREREGISTRATION.md section 2 "
                        "registers: --population answerable --bootstrap-unit "
                        "pair. Passing either of those explicitly with a "
                        "different value is an error rather than a silent "
                        "override. Selecting it does not make the registered "
                        "endpoint estimable --- that also needs both model "
                        "families, and the summary says so either way.")
    p.add_argument("--population", choices=POPULATIONS, default=None,
                   help="restrict the paired set to one twin variant, by the "
                        "instance document's 'variant' field (default: all). The "
                        "registered primary endpoint lives on 'answerable'.")
    p.add_argument("--bootstrap-unit", choices=BOOTSTRAP_UNITS, default=None,
                   help="resample individual twins (default: twin, the shipped "
                        "behaviour every published interval was computed with) or "
                        "base-instance pair clusters. On this corpus clustering "
                        "narrows the accuracy, pass^k and escalation intervals and "
                        "widens the citation ones; it is inert on a "
                        "single-variant population.")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260727)
    p.add_argument("--out-json", default=None)
    p.add_argument("--out-md", default=None)
    return p


def resolve_analysis_flags(args: argparse.Namespace) -> Dict[str, str]:
    """Settle ``--population`` / ``--bootstrap-unit`` against ``--registered``.

    ``--registered`` is a name for a configuration, not an override of one: if
    the operator also spelled out a *different* population or unit, that is a
    contradiction in the command line and the run stops. Silently winning would
    produce a report stamped ``registered-primary`` that the command line says
    is something else.
    """
    chosen = {"population": args.population, "bootstrap_unit": args.bootstrap_unit}
    if not args.registered:
        return {"population": chosen["population"] or "all",
                "bootstrap_unit": chosen["bootstrap_unit"] or "twin"}
    for key, flag in (("population", "--population"),
                      ("bootstrap_unit", "--bootstrap-unit")):
        want = REGISTERED_ANALYSIS[key]
        if chosen[key] is not None and chosen[key] != want:
            raise SystemExit(
                "--registered fixes %s %s; refusing to run it as %s. Drop one "
                "of the two flags." % (flag, want, chosen[key]))
    return dict(REGISTERED_ANALYSIS)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    resolved = resolve_analysis_flags(args)
    args.population = resolved["population"]
    args.bootstrap_unit = resolved["bootstrap_unit"]
    instances = load_instances(args.instances)
    results = load_results(args.results)
    summary = score(instances, results, bootstrap=args.bootstrap, seed=args.seed,
                    baseline=args.baseline, population=args.population,
                    bootstrap_unit=args.bootstrap_unit)
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
            if not markdown.endswith("\n"):
                fh.write("\n")

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
