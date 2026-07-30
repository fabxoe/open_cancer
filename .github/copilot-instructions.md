# Open Cancer repository instructions

Before answering a repository question or changing any file:

1. Read the root `PROJECT_CONTEXT.md` completely. It is the canonical project,
   experiment, reproducibility, and GitHub workflow specification.
2. Read the root `EXPERIMENT_HISTORY.md` completely. Treat only its actual entries
   as executed experiments or measured results.
3. Confirm that the work is linked to a GitHub Issue and that the current branch
   contains the same Issue number.

Never invent an experiment, score, leaderboard result, model artifact, or
reproduction status. Do not copy example values into the experiment history.

Use `uv` and the committed `uv.lock` for the Python environment. Prefer commands
documented in `PROJECT_CONTEXT.md` and `docs/VSCODE_SETUP.md`. Before completing a
change, run the relevant tests and confirm that raw competition data, checkpoints,
OOF predictions, secrets, and other ignored artifacts are not staged.

If an instruction conflicts with repository state, explain the conflict instead
of silently guessing.
