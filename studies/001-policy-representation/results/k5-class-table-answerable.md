# Study 001 -- decisions by gold class, and constant-answer baselines

**Secondary, post hoc and descriptive; not registered.** Computed after the results were read (DEVIATIONS.md section 9). Counts and descriptive rates, without intervals: no test, no verdict.

Analysis population: `answerable`. 216 instances shared by every condition. Trials per instance: 5-5.

## Constant-answer baselines

What an arm that always gave one answer would score. Its pass^k equals its accuracy, because a constant answer is the same on every trial.

| constant answer | instances it gets right | accuracy = pass^k |
|---|---:|---:|
| `legal` | 37 of 216 | 0.171 |
| `illegal` | 179 of 216 | 0.829 |
| `cannot_decide` | 0 of 216 | 0.000 |

## Decisions by gold class (trials)

Each row sums to the class's trials. `no_decision` is a trial that did not parse, or parsed to something that is not one of the three decisions.

| condition | gold class | trials | got `legal` | got `illegal` | got `cannot_decide` | got `no_decision` | share of trials matching gold |
|---|---|---:|---:|---:|---:|---:|---:|
| `A::codex::gpt-5.6-sol` | `legal` | 185 | 70 | 112 | 3 | 0 | 0.378 |
| `A::codex::gpt-5.6-sol` | `illegal` | 895 | 113 | 773 | 9 | 0 | 0.864 |
| `Aprime::codex::gpt-5.6-sol` | `legal` | 185 | 50 | 120 | 15 | 0 | 0.270 |
| `Aprime::codex::gpt-5.6-sol` | `illegal` | 895 | 69 | 790 | 36 | 0 | 0.883 |
| `B::mock::judgment-pack-runtime` | `legal` | 185 | 50 | 90 | 45 | 0 | 0.270 |
| `B::mock::judgment-pack-runtime` | `illegal` | 895 | 65 | 575 | 255 | 0 | 0.642 |

## Accuracy from these counts

Accuracy is the mean over instances of the share of an instance's trials that match gold, as `score.py` computes it, and equals the accuracy it reports for the same population and result files. When every instance has the same number of trials it is the second column over the third.

| condition | trials matching gold | trials | accuracy |
|---|---:|---:|---:|
| `A::codex::gpt-5.6-sol` | 843 | 1080 | 0.781 |
| `Aprime::codex::gpt-5.6-sol` | 840 | 1080 | 0.778 |
| `B::mock::judgment-pack-runtime` | 625 | 1080 | 0.579 |
