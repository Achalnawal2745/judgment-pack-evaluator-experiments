# Deviations from the preregistration

Every departure from [`PREREGISTRATION.md`](PREREGISTRATION.md) is recorded here with its date and
reason. The preregistration itself is never edited after freeze. An empty table means the study ran
as preregistered.

| Date | Section | Deviation | Reason | Effect on the claim |
| --- | --- | --- | --- | --- |
| — | — | none yet | — | — |

## First prompt-arm execution (2026-08-06)

Arms A and A′ had never been run against a real model beyond a two-instance
pilot. They were run over the full 432-twin corpus on this date. Three
deviations from the registered design, all forced, all recorded before the
numbers were read:

1. **k = 1 in the first pass, superseded by k = 5.** The registered
   primary endpoint (H1, pass^k) requires k > 1; at k = 1 pass^k
   degenerates to accuracy. The first pass therefore measured secondary
   endpoints only and said so. The k = 5 run followed and is what
   `RESULTS-FIRST-PROMPT-ARMS.md` now reports.

   Two things surfaced while scoring it, both recorded because either
   could have produced a silently wrong headline:

   - The first k = 5 scoring still reported `trials per instance: 1-1` and
     a pass^k identical to accuracy. `score.py` sets k to the **minimum**
     trial count across conditions — correct for a paired comparison — and
     arm B still had only one trial, collapsing k to 1 for every arm. Arm
     B was re-run at k = 5 (37 seconds; it is deterministic) and the
     pairing then resolved correctly. Had this gone unnoticed, the k = 1
     accuracy would have been reported as the primary endpoint.
   - **Arm B's pass^k is 1.0 by construction**, because the evaluator is
     deterministic. H1 is therefore not a contest arm B can lose, and the
     +0.130 measures prompt-arm inconsistency rather than a stability win.
     The results document says so in its own section rather than leaving
     a reader to infer it.

2. **One model family, not two.** The design pools across Claude and
   Codex. No Anthropic credential was available in this environment, so
   arms A and A′ ran on the Codex backend (`gpt-5.6-sol`) only. A
   single-family result cannot stand in for the pooled endpoint, and no
   pooled claim is made.

3. **Arm B ran on `judgment-pack 0.2.0`, not the current runtime.** This
   was forced rather than chosen: `jpack 0.15.0` refuses the study's pack,
   because the pack declares `specVersion 0.1.0-draft` while the current
   evaluator implements the 0.2.0-draft contract, and JPS §11 makes the
   declared value exact. Re-declaring the pack to satisfy a newer
   evaluator would have been an edit to a study artifact mid-study, so the
   original binary was used instead — it is still published, and arm B
   reproduced its recorded result exactly. The drift itself is worth
   recording: a study artifact can fall out of its evaluator's conformance
   window while the study is still open.

## 2. The primary endpoint was first reported on the wrong population

**What happened.** The first k = 5 write-up reported "H1 passes,
B − A = +0.130 [0.076, 0.181]". The preregistration §2 registers H1 as
pass^k **on answerable instances**. The number reported was the composite
over all 432 twins, which pools the 216 answerable instances with the 216
manufactured-redaction ones. On the registered population the sign flips:
**B − A = −0.148 [−0.213, −0.088]**, McNemar p = 2.09 × 10⁻⁵ favouring A.

The post-run adversarial review caught it as its first blocker. Every
number was independently recomputed before the correction was accepted.

**Why it happened, stated plainly.** `score.py` intersects all shared twin
ids and never filters to `variant == "answerable"`. The scorer does not
enforce the registered population, and the author did not verify that the
population matched the endpoint before writing "passes". A preregistration
constrains what you may claim; it does not check that the claim was
computed on what it names. That check is manual and it was skipped.

**Consequences.** `RESULTS-FIRST-PROMPT-ARMS.md` was rewritten to lead
with the negative result. H1, H4, and H5 are all reported as not
supported. The earlier commit `a01d686` is left in history rather than
amended, so the error and its correction are both auditable.

## 3. Other departures recorded during the same review

- **The registered primary endpoint is not estimable from this execution.**
  It is defined as pooled across Claude and Codex; only Codex ran, and
  `score.py` has no cross-backend pooling operation. Everything reported
  is a Codex-only deviated analysis.
- **McNemar's test, committed in §5, is not implemented** in `score.py`,
  which provides only paired bootstrap intervals. It was computed by hand
  for the primary endpoint and reported; the omission is recorded here
  rather than left silent.
- **The shipped scorer bootstraps 432 twins independently** rather than
  resampling the 216 pair clusters. Pair-clustering the H2 interval gives
  [0.397, 0.505]; the conclusion is unchanged. Reported figures note which
  intervals are clustered.
- **`arm_b.py` can score a nonzero-exit run as a success.** It rejects a
  nonzero return code only when stdout is empty, and arm-B rows retain
  neither return code nor stderr, so the reported "0 engine refusals"
  cannot be audited from the retained JSONL. No retained envelope shows a
  refusal signal. Fixing the check and re-running the deterministic arm is
  filed as follow-up rather than performed under a result already
  corrected once.

## 4. Harness changes made after the results were read (2026-08-06)

The harness defects §3 records were answered in code on the same day —
*after* the k = 5 numbers had been read and written up. That ordering is
itself worth recording: an analysis rule changed after the result is a
rule the result could have influenced, and none of this was preregistered.
What follows is what changed, what it does to a published number, and what
was deliberately not done. (§3's three harness items resolve as follows:
the McNemar omission by item 1 below, the twin-only resample by item 3,
and the refusal check by item 5 — whose outstanding re-run half was then
performed the same day, §5.)

**Nothing in `results/` was re-run or re-scored for this entry.** Every
figure in `RESULTS-FIRST-PROMPT-ARMS.md` is still the one its recorded
command produced, and each item below was checked against those artifacts
rather than asserted.

1. **McNemar's exact test is implemented** (`score.py`,
   `mcnemar_exact_p` / `mcnemar_pass_at_k`), on the per-instance pass^k
   indicator, for every non-baseline condition. It reproduces the figure
   §2 computed by hand: on the answerable population, B against A gives 44
   discordant instances favouring A and 12 favouring B, exact two-sided
   p = 2.0876568218419767 × 10⁻⁵. No published number changes; the study
   simply no longer computes its registered test by hand.

2. **`--population {all,answerable,redacted}`** makes the analysis set
   explicit, filtering on the `variant` field `redact.py` stamps into both
   twins. `--population answerable` reproduces §2's corrected figures
   exactly (pass^k A 0.727 [0.667, 0.787], A′ 0.778 [0.718, 0.833], B
   0.579 [0.509, 0.644]; Δ B − A = −0.148 [−0.213, −0.088]). The flag does
   not know which population a hypothesis registered — it makes the choice
   visible, it does not make it.

3. **`--bootstrap-unit {twin,pair}`** adds the pair-clustered resample §3
   said was missing. **The default is deliberately still `twin`**, so
   every recorded scoring command keeps producing the published intervals:
   `--population all --bootstrap-unit twin` reproduces
   `results/k5-report.json` field for field (the only differences are the
   `schema` string and the fields version 2 adds). The effect of clustering
   was measured rather than assumed, and it does not run the way §3's
   phrasing implies: on the composite population it *narrows* 15 of the 33
   non-degenerate intervals — every accuracy, pass^k and escalation one,
   e.g. Δ pass^k B − A [0.100, 0.160] clustered against [0.076, 0.181]
   unclustered — and widens the other 18, all citation metrics. The cause
   is mechanical: every cluster is exactly one answerable twin plus its
   redacted counterpart, so clustering pins the answerable:redacted mix at
   50% in every replicate and removes the mixture variance that dominates
   the composite. That is stratification, not a correction for dependence.
   On a single-variant population every cluster is a singleton and the two
   units are identical, so **the registered endpoint is unaffected by this
   choice**. §3's clustered H2 interval [0.397, 0.505] is reproduced by
   `--bootstrap-unit pair`.

4. **Escalation metrics are suppressed where they are undefined.** When
   the analysis set holds only one twin variant, one row of the escalation
   2×2 is empty by construction, and precision, recall and F1 are then
   artifacts of the population rather than measurements: on an
   answerable-only set recall is 0/0 and precision is a structural zero.
   The scorer reports all three as `null` / `n/a` with the section marked
   NOT ESTIMABLE, instead of the "escalation F1 0.000 [0.000, 0.000]" a
   naïve filter would print — which would have been §2's defect
   reintroduced by the flag added to prevent it. The 2×2 counts are still
   reported, because on answerable twins the should-not-but-did count is
   the numerator of the false-escalation **rate** §6 names as H2's cost
   criterion (the count over the population's trials; §6 registers the
   rate, not the count).

5. **`arm_b.py`'s refusal rule was tightened and arm B was NOT re-run**
   *(as of this entry; the re-run was performed later the same day — §5).*
   A non-zero exit is now a refusal on the exit code alone, and every
   arm-B row carries `engine_returncode` and `engine_stderr`
   (`jps-study-001-result/2`). Both halves matter for reading the
   published result:
   - The rule changed after the result was read. It converts recorded
     successes into refusals and never the reverse, so **accuracy and
     pass^k** can only fall or stay equal — but that bound does not extend
     to every published metric: under the scorer a refusal is
     non-escalating with empty citations, so converting a false
     escalation into a refusal would *raise* escalation precision and can
     raise citation scores. No ex-ante direction covers all metrics; what
     settles it is the re-run (§5), which converted zero rows.
   - The retained corpus predates it. All 2,160 rows of
     `results/pilot-B-runtime.jsonl` are `jps-study-001-result/1`, none
     carries `engine_returncode` or `engine_stderr`, and every `error` is
     null — verified by reading the file. So
     `RESULTS-FIRST-PROMPT-ARMS.md`'s "0 errors" for arm B rests on the
     old rule, and the new keys audit future runs only. §3's follow-up is
     half done, and the outstanding half is the half that would change
     what can be claimed.

6. **`run.py` refuses to resume an arm-B file across the two vintages.**
   Because the refusal rule defines what an arm-B row *means*, appending
   `/2` rows to a file holding `/1` arm-B rows would give one file two
   definitions of "engine refusal" with nothing downstream able to tell
   them apart (`score.py` never reads the schema string). The model arms
   are unaffected — their rows are identical across the two versions — and
   resume across it as before.

## 5. The deterministic arm re-run, performed (2026-08-06, later the same day)

§3's outstanding half — re-running arm B under the tightened rule — was
done after §4 was written. `results/k5-B-runtime-audited.jsonl` is the full
432 × 5 run through the fixed harness (`jps-study-001-result/2`, same
binary `judgment-pack 0.2.0`, same pack, same seeds 20260806–20260810),
and three facts about it were verified programmatically rather than
asserted:

1. **Every row retains `engine_returncode: 0`** and its `engine_stderr`,
   so "0 engine refusals" is now a claim a reader can check against a
   retained artifact produced under the strict rule — for this corpus. The
   original `/1` rows stay as they were; their unauditability is §4 item
   5's record and it stands for them.
2. **The tightened rule changed nothing.** All 2,160 rows carry a
   disposition and trace byte-identical to `results/pilot-B-runtime.jsonl`
   (verified per row), and the decision distribution is the recorded
   235 `illegal` / 45 `legal` / 152 `cannot_decide` per trial. Zero
   recorded successes converted to refusals — the empirical fact that
   settles what no ex-ante directional bound could (§4 item 5): with no
   nonzero exits in the corpus, no metric moved in either direction.
3. **The registered analysis now exists as a scorer artifact.**
   `results/k5-report-answerable.{json,md}` scores the audited arm-B rows
   with the retained model-arm rows on the registered population
   (`--population answerable`, seed 20260806, 2000 resamples): pass^5
   A 0.727, A′ 0.778, B 0.579; Δ B − A = −0.148 [−0.213, −0.088];
   McNemar 44/12, p = 2.0876568218419767 × 10⁻⁵ — identical, field for
   field, to scoring the original rows (verified), and identical to §2's
   corrected figures. Escalation is reported NOT ESTIMABLE there, as §4
   item 4 requires.

The 2026-07-27 reproduction note in `RESULTS-FIRST-PROMPT-ARMS.md` is
thereby extended: the corpus has now reproduced exactly under both the
permissive and the strict refusal rule.

G-3 is also no longer open: every one of the 18 false-`illegal` verdicts
is diagnosed to a named field or rule in [`G3-DIAGNOSIS.md`](G3-DIAGNOSIS.md),
each verified by counterfactual through the same binary, and the whole
note was adversarially re-derived (all 18 instances) by an independent
check whose four corrections are incorporated and credited inline.

4. **Provenance of the committed artifact.** The first regeneration was
   produced from a working tree whose harness edits were not yet
   committed, so its rows carried `harness_dirty: true` — a provenance
   gap the cross-vendor review flagged. The committed
   `results/k5-B-runtime-audited.jsonl` was regenerated from the
   committed harness revision on a clean tree; every row's
   `harness_commit` / `harness_dirty: false` fields are the check, and
   the substantive fields and raw envelopes are identical across both
   regenerations (only measured latencies differ).

## 6. Corrections to this ledger's own earlier entries (2026-08-06)

Appended rather than edited in place: the entries above are the record as
merged, errors included.

1. **§1's "Arm B's pass^k is 1.0 by construction" is wrong.** What
   determinism buys is within-instance repeat agreement of 1.0, which
   makes pass^5 *equal accuracy* — 0.579 on the answerable population,
   not 1.0. H1 remained a contest arm B could lose, and it lost it.
   `RESULTS-FIRST-PROMPT-ARMS.md` states this correctly; the
   cross-vendor review of the follow-up work flagged that this ledger
   still carried the uncorrected claim.

2. **An earlier commit on the follow-up branch retensed §§2–3 of this
   ledger in place** (annotating the entries with their later status).
   The same review caught it as a violation of the ledger's append-only
   discipline; the merged wording above is restored byte-for-byte, the
   status those annotations carried lives in §§4–5, and the in-place
   edit remains visible in the branch history rather than being
   squashed away.

## 7. Retained-evidence bound, render-policy fallback, and first CI (2026-08-15)

Follow-up to §4 item 5 and §5, closing the remaining acceptance criteria on
the fail-closed adapter. **Nothing in `results/` was re-run or re-scored for
this entry**, and no published figure changes.

1. **Retained stderr is bounded** (`arm_b.MAX_RETAINED_STDERR`, 8000
   characters). §4 put the child's `returncode` and `stderr` on every return
   path so the refusal count could be checked against the rows; unbounded,
   one pathological child could inflate a result file past the point where it
   can be read back. Truncation is *marked* in the retained text with the
   count of dropped characters, so a short stderr still reads as the whole of
   what the runtime said rather than as the harness having quietly dropped
   the rest. Both sides are pinned: kept whole at the bound, truncated and
   marked above it. The existing rows are unaffected, and not merely within
   the bound: all 2160 rows of `k5-B-runtime-audited.jsonl` carry
   `engine_stderr: ""` alongside `engine_returncode: 0`, which is what the
   audited corpus's "0 engine refusals" claim looks like row by row.

2. **The retained stderr is not scrubbed, and does not need to be.** It could
   only echo a redacted fact if the child had been given one. It is not: the
   runtime reads `_facts_payload`, which is either `apply_render_policy`
   output or the bare `facts` sub-object. This is now asserted against the
   payload the child receives, rather than left as a claim about stderr that
   a stub could not falsify.

3. **`DEFAULT_RENDER_POLICY` now excludes `/redaction`.** Writing check 2
   surfaced this: the fallback applied to a document that declares no
   `render_policy` excluded `/gold` and `/provenance` but not the redaction
   record, which on a redacted twin carries `removed_value` — the deleted
   fact itself. **No published number changes, and this is checked rather
   than assumed**: `redact.py`'s `make_twins` puts `render_policy` in the
   `common` block both twins are built from, so every corpus instance
   carries the fuller `loadbearing_map.json` policy (which already excluded
   `/redaction`) and never reaches the fallback. What was exposed was any
   *unstamped* document — every test fixture in the suite, where the leak was
   real and invisible, because the prompt-side leak check asserted on `gold`
   keys only. That check now covers the redaction record too.

4. **The suite runs in CI for the first time** (`study-001-harness`). Study
   001's 99 harness tests were in no CI job, including the §4/§5 fail-closed
   regression tests: the stub-CLI check that a non-zero exit is a refusal
   even alongside a valid envelope had never been enforced on a pull request.
   A regression test that does not run does not catch regressions. The graded
   batch remains an attempt, not a test, and does not run there.

## 8. The registered analysis is nameable in the scorer (2026-08-15)

Follow-up to §2 and §4. **Nothing in `results/` was re-run or re-scored for
this entry**, and no published figure changes: the new scorer was run against
the previous one over every population and resampling unit, and the summaries
are identical apart from the two added fields and the schema string.

1. **`--registered` names the preregistered configuration.** §2 registers the
   primary endpoint on the answerable population; §4 added `--population` and
   `--bootstrap-unit` but left the defaults at the shipped behaviour, for the
   good reason recorded there. The consequence was that the registered
   configuration still had to be *assembled* by an operator who remembered two
   flags — which is the shape of the mistake §2 records. It is now a name.
   The defaults are unchanged, so every previously recorded command still means
   what it meant.

2. **A contradicting command line is refused, not resolved.** `--registered`
   together with `--population all` exits rather than picking a winner; a
   report stamped `registered-primary` whose command line says otherwise would
   be worse than either reading.

3. **`analysis_role` marks every non-registered run `secondary`**, in the JSON
   and in the markdown header. That includes the default all-twins run — the
   population the first draft reported as though it were the primary endpoint.

4. **`registered_primary` records whether the endpoint is estimable at all**,
   and if not, every reason rather than the first. On this study's corpus it is
   not: the endpoint is pooled across both model families, only Codex ran, and
   this scorer has no cross-backend pooling operation. That was already stated
   in prose in `RESULTS-FIRST-PROMPT-ARMS.md`; it is now computed. `mock` is
   not counted as a model family, so an all-mock run reports zero families
   rather than one.

   **Selecting `--registered` does not make the endpoint estimable** — the two
   are independent, and the summary reports them separately, so a run cannot
   acquire the endpoint's standing by naming it.

The JSON summary is now `jps-study-001-score/3`; version 2's fields are all
still written and still mean the same thing.

## 9. A constant-answer baseline and decisions by gold class, added after the results were read (2026-09-30)

**No model or evaluator execution was repeated, and no existing result
artifact was replaced.** The retained rows were re-scored to check them and
were used to write two new descriptive reports. No published figure changes.
Two tables were added to `RESULTS-FIRST-PROMPT-ARMS.md` and one sentence to
the README's banner, each labelled secondary, post hoc and descriptive, as
§2 of the preregistration requires of everything outside the primary
endpoint.

1. **Neither table is registered.** §5 of the preregistration defines
   accuracy as per-trial agreement with the benchmark's gold `answer`. It
   names no constant-answer baseline to read it against (the baseline §8
   speaks of is arm A) and no breakdown by gold class. Both were computed
   after the results were read, and both are labelled as such where they
   appear. They do not test the preregistered hypotheses and do not change
   their registered decision criteria.

   **They also depart from two sentences of §5**, which says every metric is
   computed by `harness/score.py` and that "No metric is reported without an
   interval". The tables come from a separate file and are counts; the
   percentages beside them are those counts divided, and carry no interval.
   No arm is tested against the baseline. The results document says which of
   the published intervals reach 0.829 and that those intervals are not a
   comparison with it.

2. **What was added.** On the registered answerable population 179 of the
   216 gold labels are `illegal` and 37 are `legal`, so an arm that always
   answered `illegal` would score 179/216 = 0.829 on accuracy and, a
   constant answer being the same on every trial, 0.829 on pass^5. Every
   arm's point estimate is below that on both measures (accuracy 0.781, 0.778,
   0.579; pass^5 0.727, 0.778, 0.579). The second table counts each arm's
   trials by gold class and decision.

3. **Why it was added.** The accuracy figures were published with nothing
   to read them against, on labels this unbalanced. A reader could take
   0.78 for a strong result and 0.58 for a weak one; against 0.829, neither
   shows an arm doing better than a constant answer would.

4. **How it was computed.** `harness/class_table.py` is new and changes
   nothing in `score.py`. The `variant` filter, `gold_decision`, the result
   loader and the instance key are the scorer's own functions. The
   intersection across conditions and the first-k rule are repeated in the
   new file in the scorer's form, and its tests hold its accuracy to the
   scorer's on a corpus where instances differ in k. It takes `--population`
   with no default, for the reason §2 of this ledger records. It refuses two
   inputs the scorer accepts, an instance with no gold decision and an
   instance with no trial under some condition; neither occurs in this
   corpus. Run over the twins regenerated from the pinned benchmark commit
   and the rows `results/k5-report-answerable.json` was scored from:

   ```bash
   python harness/class_table.py --instances pipeline/out/twins \
       --results results/pilot-A-codex.jsonl results/pilot-Aprime-codex.jsonl \
                 results/k5-B-runtime-audited.jsonl \
       --population answerable \
       --out-json results/k5-class-table-answerable.json \
       --out-md results/k5-class-table-answerable.md
   ```

5. **Three checks on the counts.** The accuracy the table derives from its
   own counts equals the scorer's for every arm (843, 840 and 625 of 1,080
   trials). Each arm's `cannot_decide` column sums to the false escalations
   in `results/k5-report-answerable.json` (12, 51, 300). Arm B's rows are
   five times the per-instance table in `PIPELINE-STATUS.md` §6.3.
   Re-scoring the same instances and rows reproduces
   `results/k5-report-answerable.json` in every field it holds; the
   re-scored summary differs only in the schema string and the two fields
   §8 added.
