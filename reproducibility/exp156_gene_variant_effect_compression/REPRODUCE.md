# EXP-156 재현 절차

```bash
uv sync --frozen
uv run python scripts/run_exp156_gene_variant_effect_compression.py --config configs/exp156_gene_variant_effect_compression.yaml
uv run python scripts/validate_experiment.py
```
