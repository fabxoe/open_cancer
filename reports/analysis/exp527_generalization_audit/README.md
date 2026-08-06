# EXP-527 class-cosine 일반화·분포 이동 감사

> Issue [#530](https://github.com/fabxoe/open_cancer/issues/530)의 분석 전용 결과다.
> 새 모델 학습·EXP-ID·Public LB 사용 없이 EXP-527의 26개 class-cosine 점수와
> EXP-374/527 OOF·test 확률만 감사했다.

## 결론

EXP-527의 OOF 상승은 EXP-374와 다른 오류를 실제로 교정한 결과다. EXP-527만
맞힌 환자가 621명으로 EXP-374만 맞힌 490명보다 131명 많고, 두 모델의 오류
상관은 `0.633819`다. 따라서 parser-v4 class profile은 독립적인 유효 신호로
보존한다.

다만 26개 cosine 점수만으로 train/test를 구분한 OOF AUC가 `0.647015`이고,
모든 class cosine 평균이 test에서 상승했다. 또한 EXP-527은 EXP-374보다 확률이
크게 평평해져 Macro F1은 개선됐지만 Log Loss는 악화됐다. 현재 판단은 다음과
같다.

- EXP-527을 leakage-safe class-profile 연구 기준선으로 유지한다.
- Public 일반화가 증명되기 전 대표 제출로 확정하지 않는다.
- test 분포를 보고 feature·threshold·weight를 선택하지 않는다.
- 공통 cosine offset 제거는 기하학적으로 타당한 별도 단일변수 ablation 후보지만,
  test AUC를 채택 근거로 사용하지 않고 canonical OOF로만 판정해야 한다.

## 26개 profile score 분포

EXP-527과 같은 canonical outer fold에서 validation score를 OOF 위치에 재구성하고,
test score는 다섯 outer-train centroid 변환의 평균으로 계산했다. 모델 예측 확률이
아니라 XGBoost에 추가된 26개 입력 피처 자체를 비교한 것이다.

- domain classifier OOF AUC: `0.647015`
- fold AUC: `0.635207`, `0.655956`, `0.649956`, `0.641013`, `0.659239`
- 26개 class 모두 test 평균이 train OOF 평균보다 높음
- 평균 차이 범위: `+0.015289` ~ `+0.045571`
- 가장 큰 표준화 평균 차이: ACC `0.249818`

이는 test 환자가 특정 한 암종 centroid에만 가까워진 현상이라기보다 여러 class
centroid에 동시에 더 가까워진 공통 이동이 있음을 뜻한다. 가능한 원인은 test의
semantic token 밀도·구성 또는 profile geometry 차이다. 이 결과만으로 원인을
확정하거나 입력을 삭제하지 않는다.

세부 값은 [`profile_score_distribution.csv`](profile_score_distribution.csv)와
[`adversarial_auc.json`](adversarial_auc.json)에 있다.

## EXP-374 대비 OOF 오류 구조

| 항목 | 값 |
|---|---:|
| 두 모델 모두 정답 | 2,070 |
| EXP-374만 정답 | 490 |
| EXP-527만 정답 | 621 |
| 두 모델 모두 오답 | 3,020 |
| 예측 라벨 변경 | 2,371 (38.24%) |
| 오류 indicator 상관 | 0.633819 |
| 평균 절대 확률 차이 | 0.025863 |

EXP-527의 주요 클래스 개선은 CESC `+0.18544`, SKCM `+0.12666`, PAAD
`+0.11303`, KIRC `+0.10534`다. 반면 ACC `-0.10178`, BLCA `-0.05178`,
SARC `-0.04727`, BRCA `-0.04255`는 악화됐다. Macro F1의 순개선만 보고 모든
클래스가 좋아졌다고 해석하면 안 된다.

세부 값은 [`class_f1_comparison.csv`](class_f1_comparison.csv)와
[`oof_comparison.json`](oof_comparison.json)에 있다.

## Confidence와 Log Loss

| 지표 | EXP-374 | EXP-527 |
|---|---:|---:|
| 평균 최고 확률 | 0.459967 | 0.318997 |
| 평균 top-1 margin | 0.309379 | 0.206730 |
| 평균 entropy | 1.824352 | 2.528205 |

EXP-527은 더 많은 정답 라벨을 만들었지만 확률 분포는 훨씬 평평하다. 이는
EXP-527 OOF Macro F1 `0.446872`와 Log Loss `2.027489`가 함께 나타나는 이유와
일치한다. 후속 모델은 Macro F1 checkpoint를 유지하되 confidence calibration을
별도 지표로 계속 감사해야 한다.

## test blank 237개 감사

test의 실제 빈 셀은 237개이며 128명에게 분포한다. EXP-374/527의 예측 불일치율은
빈 셀이 있는 128명에서 `28.13%`, 나머지 2,418명에서 `38.30%`였다. 두 모델의
평균 절대 확률 차이도 각각 `0.02511`, `0.02608`로 유사하다.

따라서 관찰 수준에서는 blank가 EXP-527 변화의 주원인으로 보이지 않는다. 다만
checkpoint를 사용해 blank를 WT로 바꾼 counterfactual inference를 수행한 것은
아니므로 인과 결론은 금지한다. blank와 WT의 의미 계약도 계속 분리한다.

## 재실행

```bash
uv run python scripts/analyze_exp527_generalization.py
```

산출물:

- `summary.json`: 핵심 결과와 입력 SHA-256
- `profile_reconstruction.json`: fold별 profile fit 감사
- `profile_score_distribution.csv`: 26개 score train/test quantile
- `adversarial_auc.json`: 분석 전용 domain AUC
- `oof_comparison.json`: EXP-374/527 정오답·확률 비교
- `class_f1_comparison.csv`: 클래스별 F1 변화
- `test_blank_audit.json`, `test_blank_affected_rows.csv`: blank 연관 감사

## 다음 행동

1. #531에서 parser-v4 canonical event-token schema를 구현한다.
2. token support·OOV·환자별 길이를 모델 학습 전에 감사한다.
3. row-L2 sparse linear와 TF-IDF+L2는 별도 Experiment Issue에서 canonical
   5-fold로만 비교한다.
4. EmbeddingBag/DeepSets는 유전자 열 순서를 시퀀스로 오해하지 않는
   order-invariant 다양성 모델로 검증한다.
5. EXP-527의 공통 cosine offset 제거는 #531과 섞지 않고, 필요할 경우 별도
   단일변수 Experiment로 사전 고정한다.

