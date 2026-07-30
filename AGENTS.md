# Open Cancer Agent Instructions

Before doing any work:

1. Read `PROJECT_CONTEXT.md` completely.
2. Read `EXPERIMENT_HISTORY.md` for the current experiment state.
3. Report the current experiment count, Git branch, and linked Issue.
4. Confirm that the branch is `N`, `N-<slug>`, `issue-N`, or
   `issue-N-<slug>` and resolves to the linked GitHub Issue number.
5. For an official experiment only, derive `EXP-NNN` from Issue #N. Never
   reserve or manually invent a separate sequential EXP-ID.

Treat `PROJECT_CONTEXT.md` as the canonical source for data, experiment,
reproducibility, artifact, testing, and Git workflow rules. Never invent experiment
results or leaderboard scores. Use the canonical split unless a separate experiment
Issue explicitly changes it. Run the relevant `uv` validation commands before
finishing.

The experiment Issue title is the only required human input. Hypothesis, parent
experiment, change notes, acceptance criteria, artifact plans, and reproducibility
target are optional. Apply repository/model defaults when no override is requested,
save the fully resolved runtime config, and do not ask a person to duplicate
parameters in the Issue or History.
