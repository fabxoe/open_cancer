# EXP-592 재현

EXP-589 checkpoint와 feature cache를 먼저 복구한 뒤 실행합니다.

```bash
uv sync --frozen
uv run python scripts/run_exp592_hierarchical_pair_specialists.py
```
