# Train/Test tokenization OOD QC

이 탐색 분석은 test의 `SUBCLASS`나 모델 예측을 사용하지 않고, 같은 유전자 컬럼에
대해 train/test의 토큰화·표기 분포만 비교한다. 결과는 피처 채택이나 Public 제출을
결정하는 근거가 아니라 기술적 batch effect 후보를 찾는 QC 자료다.

- `gene_tokenization_shift.csv`: 유전자별 변이 셀 비율, token 수, complex 비율과 차이
- `row_tokenization_summary.csv`: 샘플별 전체 token/complex 요약
- `abs_shift_score`: 후보 유전자를 찾기 위한 탐색 정렬값이며 통계적 유의성 검정값이 아님

해석 순서:

1. `mutated_cell_rate_diff`가 큰 유전자는 호출·필터·패널 차이 후보로 확인한다.
2. `token_mean_ratio_test_over_train`가 큰 유전자는 한 셀의 다중 token 표기 차이를 확인한다.
3. `complex_fraction_diff`가 큰 유전자는 complex 표기/파서 차이를 확인한다.
4. 이 결과만으로 Feature Spec을 변경하지 않고, 필요하면 별도 negative control과
   EXP-094 incremental ablation으로 검증한다.
