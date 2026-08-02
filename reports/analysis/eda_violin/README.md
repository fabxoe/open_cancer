# Train mutation violin EDA

이 분석은 모델 학습·피처 선택·제출에 사용하지 않는 탐색용 산출물입니다.

- 입력: `data/raw/train.csv`
- 그룹: `SUBCLASS` 26개
- 수치: mutated gene 수, 전체 변이 token 수, 변이 유형별 token 수, truncating 수, complex 존재 flag
- 변이 분류: 프로젝트의 보수적 문자열 규칙을 단순화해 사용
- 결과: `train_mutation_violin.png`, `train_mutation_violin_log1p.png`, `summary_by_subclass.csv`
- train/test 비교: `train_test_burden_ood.csv` (test에는 암종 라벨을 사용하지 않음)
- 단일 피처 OOF: `single_feature_oof.csv` (별도 `scripts/run_eda_burden_oof.py` 실행)

분포 차이는 후속 실험의 가설을 세우는 데만 사용하며, OOF 평가 없이 피처 채택 근거로 사용하지 않습니다.
특히 전역적인 test burden 상승은 생물학적 차이보다 기술적 batch effect를 먼저 의심할
근거로 기록합니다. `complex_count`는 train/test 표기 차이가 커서 성능 피처보다
`has_complex_any`와 함께 OOD/shortcut 진단 대상으로 제한합니다.

## 권고 수용 범위

1. 플랫폼·caller·필터·표기 차이(batch effect)를 1순위 가설로 둡니다.
2. burden 변환은 fold-train 통계로만 fit합니다(log1p, clip, robust, percentile).
3. 단일 피처 및 기준 모델 대비 incremental ablation을 OOF로 확인합니다.
4. Public 점수나 test 라벨로 피처를 선택하지 않으며, 공식 Feature Spec은 별도
   Experiment Issue에서만 변경합니다.

## 실제 단일 피처 OOF 관찰

탐색 실행 결과(공식 실험 아님)는 다음과 같습니다.

| feature/transform | OOF Macro F1 | fold std | Log Loss | 하위 7개 클래스 평균 F1 |
|---|---:|---:|---:|---:|
| mutated_gene_count / clip995 | 0.094531 | 0.007246 | 2.826880 | 0.014866 |
| mutated_gene_count / raw | 0.093271 | 0.003403 | 2.826423 | 0.011599 |
| total_variant_count / raw | 0.090775 | 0.007588 | 2.830262 | 0.014113 |
| missense_count / raw | 0.068629 | 0.006038 | 2.872850 | 0.003653 |
| truncating_count / raw | 0.042931 | 0.005468 | 3.059446 | 0.000000 |
| complex_count / raw | 0.020659 | 0.001870 | 3.226786 | 0.000000 |

`mutated_gene_count`의 `clip995`가 raw보다 `+0.001260` 높았지만 fold 표준편차가
`0.003403 → 0.007246`으로 악화됐습니다. 또한 기준 모델에 burden 하나를 추가한
incremental ablation이 아니므로 공식 Feature Spec으로 승격하지 않습니다. 단조
변환인 log1p·robust·percentile은 이 1차원 tree screening에서 raw와 같은 순위를
보였습니다. 다음 단계는 EXP-094 고정 Feature Spec에 burden 하나만 추가하는
incremental OOF 검증이며, Macro F1 `+0.001`, fold 표준편차 악화 `0.002` 미만,
Log Loss와 하위 25% 클래스 F1 악화 없음이 모두 필요합니다.
