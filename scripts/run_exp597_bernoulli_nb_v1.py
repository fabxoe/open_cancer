#!/usr/bin/env python
"""Run EXP-597: BernoulliNB on frozen Feature Spec v1."""

from run_exp123_sparse_logistic_v1 import ROOT, main


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp597_bernoulli_nb_v1.yaml",
        expected_experiment_id="EXP-597",
        runner_command="uv run python scripts/run_exp597_bernoulli_nb_v1.py",
    )
