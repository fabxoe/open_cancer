# Adversarial validation: train/test 분리 가능성

이 진단은 `SUBCLASS`를 전혀 사용하지 않고, 동결 Feature Spec v1 행렬만으로
train 행(도메인 라벨 0)과 test 행(도메인 라벨 1)을 구분하는 이진 분류기를
학습한다. OOF AUC가 0.5에 가까우면 이 feature 표현에서 두 도메인이 구분
불가능하다는 뜻이고, 1.0에 가까우면 강한 분포 차이(batch effect 후보)가
있다는 뜻이다.

- `metrics.json`: fold별/전체 OOF AUC, feature 수, 상위 shift feature
- `top_shift_features.csv`: gain 기준 train/test를 가장 잘 구분하는 feature
- `train_domain_propensity.csv`: 각 train 행이 "test처럼 보이는" OOF 확률과
  `p/(1-p)` 기반 제안 importance weight(99th percentile로 clip)

여기서 사용한 5-fold는 도메인 분류(train vs test)를 위한 별도 stratified
split이며, 공식 `data/splits/stratified_5fold_seed42.csv`(SUBCLASS 계층화)와
다르다. 두 split을 섞어 쓰지 않는다.

## 해석 순서와 제약

1. 이 결과는 진단(QC)이며 그 자체로 Feature Spec, threshold, 제출 후보를
   바꾸는 근거가 아니다. `PROJECT_CONTEXT.md`의 OOD QC 제약을 따른다.
2. AUC가 뚜렷하게 0.5보다 크면(예: 0.7 이상) 상위 shift feature가 실제로
   `reports/analysis/eda_violin`, `reports/analysis/tokenization_ood`에서 이미
   확인한 burden/complex 계열과 겹치는지 대조한다.
3. 겹친다면 `train_domain_propensity.csv`의 weight로 outer-fold train만
   재가중한 재학습을 새 Experiment Issue에서 OOF로 검증한 뒤에만 Public 제출
   여부를 판단한다. 이 진단 실행만으로 제출하지 않는다.
4. `SUBCLASS`와 Public 점수는 이 스크립트의 어떤 단계에서도 사용하지 않았다.
