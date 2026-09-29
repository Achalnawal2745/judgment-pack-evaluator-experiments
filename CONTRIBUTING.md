# Contributing

This repository holds the evaluator experiments: registered studies, the shared harnesses they run on, and the tooling that checks them. The [README](README.md) says what each study is.

## Working on an issue

You're welcome to comment that you'd like to take an issue, and a maintainer may assign it to you. Only that assignment reserves it. Without one, the first pull request that meets the issue's acceptance criteria is the one that gets merged, and until then the issue stays open to anyone.

Work on one issue at a time. Finish the pull request you have open, or say you're withdrawing it, before you take another. We assign at most one issue to each contributor at once.

If an assigned issue goes quiet for a couple of weeks with no pull request, a maintainer will check in. If there's no reply within a week after that, the issue is unassigned so someone else can pick it up. You're welcome to take it back while it's still open.

## Frozen studies

A study records a freeze. Each `studies/*/harness/STUDY-MANIFEST.sha256` pins the files of its study, and some shared files outside `studies/` are pinned by a study's `FREEZE.json`. Changing a pinned file breaks that study's record. Before you edit a file outside `studies/`, check whether a study pins it:

```bash
git grep -l '<path>' -- 'studies/*/FREEZE.json'
```

If an issue asks you to change something a study pins, it says so.

## Checks

CI runs the jobs in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Before you open a pull request, run the ones that cover the files you touched.

## Sign-off

Every commit needs a Developer Certificate of Origin sign-off. Create it with `git commit -s`. The sign-off must match the commit's author name and email exactly, because the DCO check refuses a mismatch. If you forgot it, or signed with a different name, run `git rebase --signoff origin/main` and then `git push --force-with-lease`.
