"""Pytest-only environment guards for macOS multiprocessing/threading hangs.

Without these, `uv run pytest` can hang indefinitely on this stack:
- OBJC_DISABLE_INITIALIZE_FORK_SAFETY: joblib/loky (used by RandomForestAdapter's
  n_jobs>1 default and fold_feature_selection.py's Parallel(prefer="processes"))
  forks worker processes; macOS's Objective-C runtime fork-safety check can
  deadlock the fork inside a process that has already touched Accelerate/BLAS.
- OMP_NUM_THREADS / KMP_DUPLICATE_LIB_OK: torch (test_saint.py) and numpy/
  scikit-learn each bundle their own OpenMP runtime; two runtimes racing to
  initialize in one process can deadlock instead of erroring.

These must be set before torch/joblib/numpy are imported by any test module,
so this lives in a root conftest.py (pytest imports it first) rather than in
individual test files. Production training scripts (scripts/run_exp*.py) are
unaffected -- they do not import this file.
"""

from __future__ import annotations

import os

os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
