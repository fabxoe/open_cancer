# EXP-620: LightGBM Regularization and Multi-Seed Stability

## Experiment contract

- Parent: EXP-571 Parser QC arm
- Canonical split: stratified 5-fold seed 42
- Feature change: none
- Official model seed: 42
- Diagnostic model seeds: 142, 242
- Public LB/test distribution used for selection: no

## Official seed result

| Metric | Value | Delta from EXP-571 Parser QC |
|---|---:|---:|
| OOF Macro F1 | 0.4453064322 | -0.0061221121 |
| Log Loss | 1.7857167764 | -0.0496525836 |
| Fold std | 0.0063324856 | -0.0015331099 |
| Accuracy | 0.4400903080 | N/A |

## Multi-seed diagnostics

| Model seed | OOF Macro F1 | Accuracy | Log Loss | Fold std |
|---:|---:|---:|---:|---:|
| 42 | 0.4453064322 | 0.4400903080 | 1.7857167764 | 0.0063324856 |
| 142 | 0.4464893308 | 0.4425092727 | 1.7922914491 | 0.0055262383 |
| 242 | 0.4448707485 | 0.4381551363 | 1.7738919609 | 0.0074624881 |

Seed 42 is the only official parent comparison. Seeds 142 and 242 are robustness
diagnostics on the same canonical folds and are not searched or selected by score.

## Decision checks

```json
{
  "official_macro_f1_not_lower": false,
  "official_log_loss_improved": true,
  "official_fold_std_improved": true,
  "no_class_f1_collapse": false
}
```

The final adoption decision must consider Macro F1, Log Loss, fold variability,
seed stability, and the worst per-class F1 delta together. This experiment does
not use Public LB feedback to alter the preregistered preset.

## Artifacts

- `stability_summary.json`
- seed-specific metrics under `reports/exp620_lightgbm_regularization_multiseed_seed*/metrics.json`
- seed-specific reproducibility bundles under `reproducibility/exp620_lightgbm_regularization_multiseed_seed*/`
