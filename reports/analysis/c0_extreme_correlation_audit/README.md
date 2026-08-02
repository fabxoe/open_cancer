# C0 극단 Phi/Jaccard 중복 진단

> Issue #187의 분석 전용 단계입니다. 공식 EXP, 모델 학습, OOF, Public LB, test 데이터 사용을 포함하지 않습니다.

## 결과

- 분석 행: 6,201
- mutation-presence 유전자 열: 4,384
- 기록된 변이 존재 셀: 218,893
- 극단 중복 후보: **없음 (0개)**

## 사전 고정 기준

- Phi ≥ 0.50
- Jaccard ≥ 0.90
- 공동 변이 수 ≥ 20
- `GENE__mutated` 열만 검사

## 해석

이 기준은 사실상 같은 정보를 반복하는 열이 있는지만 확인하는 보수적 감사다. 후보가 없으므로 C0 자체는 어떤 열도 삭제하지 않으며, Feature Spec이나 모델을 변경하지 않는다. 이후 C1~C3 공식 실험은 전체 train 진단 결과를 재사용하지 않고 각 outer-fold 학습 행에서 후보와 mask를 새로 계산한다.

## 산출물

- `summary.json`: 입력 해시, 기준, 후보 수와 사용 범위
- `candidate_pairs.csv`: 기준을 통과한 모든 pair (없어도 header 유지)
