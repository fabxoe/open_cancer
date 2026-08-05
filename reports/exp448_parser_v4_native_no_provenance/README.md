# EXP-448 — Parser v4 native consequence without sample provenance

> Issue: [#448](https://github.com/fabxoe/open_cancer/issues/448)

## 목적

EXP-438의 native consequence schema는 유지하면서 annotation source를 설명하는
sample-level provenance summary 6개만 제거했습니다.

제거한 피처:

- parse complete / partial / unresolved affected-gene count 3개
- frameshift source grammar affected-gene count 3개

유지한 피처:

- mutation presence·missing
- native consequence 6종의 sample affected-gene count
- native consequence 6종의 4,384개 gene-level any

hotspot, residue-position, pathway, isoform, driver, extra aggregate, Optuna와
compatibility 5-family는 사용하지 않았습니다.

## 결과

- Fold Macro F1: `0.3977343170`, `0.4209850212`, `0.4045872725`,
  `0.4059045365`, `0.4200137245`
- OOF Macro F1: **`0.4104538324`**
- Fold std: `0.0091361111`
- Accuracy: `0.4015481374`
- Log Loss: `1.8858425617`
- Runtime: `617.45초`
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

### EXP-438 대비

- Macro F1: `+0.0002487951`
- Fold std: `-0.0018203860` (개선)
- Accuracy: `-0.0006450572`
- Log Loss: `-0.0873434544` (개선)
- KIRC F1: `-0.0547828750`
- LGG F1: `-0.0515871203`

### Legacy L(EXP-433) 대비

- Macro F1: `-0.0028224576`
- Fold std: `-0.0003980924` (개선)
- Accuracy: `-0.0014513788`
- Log Loss: `-0.0677431822` (개선)
- PAAD F1: `-0.0524070915`

## 판단

sample provenance summary 제거는 확률 품질과 fold 안정성을 개선했지만 공식 지표
개선은 미미했고, Legacy L 대비 Macro F1과 클래스 붕괴 gate를 모두 실패했습니다.
따라서 `ARCHIVE`이며 제출하지 않습니다.

이 결과는 parser correctness를 기각하는 근거가 아닙니다. 현재 native v1의 여섯
consequence 중 `non_simple_or_unresolved`가 deletion, insertion, duplication,
delins와 unresolved를 함께 담는 구조 자체가 다음 병목입니다. EXP-444에서 독립
range 의미는 compatibility 위에서 유효했으므로, 다음 작업은 추가 파라미터 ablation이
아니라 #393·#394·#395·#399 의미 계약을 각각의 model-active family로 연결하는
**native adapter v2 구현**입니다.

## 재현 정보

- Source commit: `e3f1d79`
- Config: `configs/exp448_parser_v4_native_no_provenance.yaml`
- Runner: `scripts/run_exp448_parser_v4_native_no_provenance.py`
- Resolved config:
  `reproducibility/exp448_parser_v4_native_no_provenance/config.resolved.yaml`
- Metrics: `reports/exp448_parser_v4_native_no_provenance/metrics.json`
- OOF: `oof/exp448_parser_v4_native_no_provenance.csv`
- Test probability: `preds/exp448_parser_v4_native_no_provenance_test_proba.csv`
- Submission: `submissions/exp448_parser_v4_native_no_provenance.csv`

checkpoint 재추론과 독립 재학습 검증은 수행하지 않아 재현 상태를 승격하지 않았습니다.
