# EXP-029: 변이유형 구성비·log burden 피처

## 요약

EXP-005의 유전자×변이유형 희소 피처와 XGBoost 설정을 유지하고, 환자별 변이량을
로그로 압축한 피처와 변이유형 구성비 피처를 함께 추가했다. 팀 공용
`data/splits/stratified_5fold_seed42.csv`로 검증한 전체 OOF Macro F1은
`0.3988980085`였다. Public leaderboard에는 제출하지 않았다.

## 변경한 피처

- 변이 유전자 수, 전체 변이 수, 다중 변이 유전자 수의 `log1p`
- missense, synonymous, truncating, splice, inframe 변이 구성비
- 다중 변이 유전자 비율
- 결측 유전자 비율

타깃에서 계산한 피처, 상관분석, Mutual Information, 피처 선택은 사용하지 않았다.
원본 CSV와 공용 split도 변경하지 않았다.

## 내부 검증 결과

| 항목 | EXP-005 | EXP-029 | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4043796587 | 0.3988980085 | -0.0054816502 |
| fold 평균 | 0.4028662325 | 0.3970013403 | -0.0058648922 |
| fold 표준편차 | 0.0086812077 | 0.0120777005 | +0.0033964928 |

EXP-029 fold Macro F1은 `0.4050881006`, `0.3992122410`, `0.3830162610`,
`0.3837339691`, `0.4139561300`이었다.

## 판단

추가 피처 전체를 함께 넣은 구성은 EXP-005보다 OOF가 낮고 fold 간 변동성도
커졌다. 따라서 현 구성을 제출 후보로 채택하지 않는다. 다만 이 결과만으로 모델의
과적합을 확정할 수는 없다. Public leaderboard 평가를 수행하지 않았고, leaderboard
점수는 OOF와 평가 표본이 다르기 때문이다.

후속 실험에서는 같은 Issue의 공식 결과를 덮어쓰지 않고 새 Experiment Issue에서
다음 피처군을 각각 분리해 ablation하는 것이 적절하다.

1. log burden 3개만 추가
2. 변이유형 구성비만 추가
3. 다중 변이·결측 비율만 추가

## 재현 상태

resolved config와 metrics는 생성됐지만, 이 실행은 자동 checkpoint 추론 검증을
도입하기 전 dirty worktree에서 수행됐다. 따라서 재현 상태는 `NOT_STARTED`이며
`INFERENCE_VERIFIED`로 기록하지 않는다.
