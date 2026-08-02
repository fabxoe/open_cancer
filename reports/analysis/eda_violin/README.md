# Train mutation violin EDA

이 분석은 모델 학습·피처 선택·제출에 사용하지 않는 탐색용 산출물입니다.

- 입력: `data/raw/train.csv`
- 그룹: `SUBCLASS` 26개
- 수치: mutated gene 수, 전체 변이 token 수, 변이 유형별 token 수, truncating 수
- 변이 분류: 프로젝트의 보수적 문자열 규칙을 단순화해 사용
- 결과: `train_mutation_violin.png`, `train_mutation_violin_log1p.png`, `summary_by_subclass.csv`
- train/test 비교: `train_test_burden_ood.csv` (test에는 암종 라벨을 사용하지 않음)
- 단일 피처 OOF: `single_feature_oof.csv` (별도 `scripts/run_eda_burden_oof.py` 실행)

분포 차이는 후속 실험의 가설을 세우는 데만 사용하며, OOF 평가 없이 피처 채택 근거로 사용하지 않습니다.

## 실제 관찰

train/test 전체 분포는 상당히 다릅니다. train 대비 test의 중앙값 비율은
mutated-gene count `2.00`, total token count `2.43`, missense count `2.56`이며,
test의 p99도 각각 `1154.10`, `1997.80`, `1362.60`까지 올라갑니다. 따라서 burden
피처는 암종 신호일 수 있지만 test shift를 이용한 shortcut이 될 위험도 함께 기록합니다.
complex token의 zero 비율은 train `0.9595`, test `0.5911`로 차이가 특히 커서,
현재 단계에서는 성능 피처보다 표기·OOD 진단 대상으로 취급합니다.

## 단일 피처 OOF 탐색

아래 점수는 공식 실험 점수가 아닙니다. 단일 scalar를 입력으로 사용하고 XGBoost
100 trees, canonical 5-fold, balanced sample weight를 적용한 screening 결과입니다.

| feature/transform | OOF Macro F1 | fold std | Log Loss | 하위 7개 클래스 평균 F1 |
|---|---:|---:|---:|---:|
| mutated_gene_count / clip99 | 0.093465 | 0.005337 | 2.824254 | 0.014325 |
| mutated_gene_count / raw | 0.093271 | 0.003403 | 2.826423 | 0.011599 |
| total_variant_count / raw | 0.090775 | 0.007588 | 2.830262 | 0.014113 |
| missense_count / raw | 0.068629 | 0.006038 | 2.872850 | 0.003653 |
| truncating_count / raw | 0.042931 | 0.005468 | 3.059446 | 0.000000 |
| complex_count / raw | 0.020659 | 0.001870 | 3.226786 | 0.000000 |

`mutated_gene_count`가 단일 피처 중 가장 높았지만, 기준 모델 대비 직접적인 채택
근거가 되지는 않습니다. train/test shift가 크고 단일 피처 성능도 낮으므로, 이
분석만으로 Feature Spec이나 제출 모델을 변경하지 않습니다. `clip99`의 개선폭도
`+0.000194`로 공식 승격 기준 `+0.001`에 미달합니다.
