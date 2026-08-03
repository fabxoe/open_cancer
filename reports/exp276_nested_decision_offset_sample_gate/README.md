# EXP-276 nested class-wise decision offset — 표본 게이트 적용 — 기각(ARCHIVE)

## 결론

[#233](https://github.com/fabxoe/open_cancer/issues/233)(post-hoc
class-wise logit offset, 기각)에 표본 게이트를 추가했습니다 — inner
fold당 최소 표본 수가 임계값 미만인 클래스는 offset 탐색에서 제외하고
원본 EXP-219 확률을 그대로 둡니다. inner cross-fitting(15개 모델 학습)은
**한 번만** 수행하고 threshold 3개(15/20/25)는 그 결과를 재사용해
offset 탐색만 반복했습니다(2899.32초, 약 48분).

가장 좋은 threshold(20, 25는 동일)는 OOF Macro F1 **+0.0039789886**로
EXP-233(게이트 없음, +0.0019573460)의 **약 2배**, fold 하락도 5개 중
1개로 줄었습니다. 그럼에도 **기각(ARCHIVE)합니다** — 사전에 고정한 채택
규칙(Macro F1 개선 AND Log Loss 악화 없음 AND fold 표준편차 악화 없음)을
세 threshold 전부 충족하지 못했고, 무엇보다 **게이트로 보호되는 클래스가
자기 offset이 0으로 고정돼 있어도 F1이 실제로 보호되지는 않는다**는
사실을 확인했습니다(아래 참고).

## 설계

EXP-233과 완전히 동일한 inner cross-fitting(outer-train 안에서 K=3,
seed_base=5000)을 재사용하고, 다음만 추가했습니다.

- **게이트 통계량**: `min_class_count_per_inner_fold` — 클래스별로 3개
  inner fold holdout 중 **최솟값**. outer-train 원시 표본 수가 아닙니다
  — #233에서 DLBC(outer-train 30~31건)가 ACC(57건)와 원시 수로는
  크게 다르지 않아 15/20/25 어떤 threshold로도 안 걸러진다는 걸 미리
  확인했고, inner fold당 최솟값(DLBC 10.0 vs ACC 19.0)이 실제로 탐색
  안정성을 좌우하는 양이라고 판단해 이 정의로 고정했습니다.
- 임계값 미만인 클래스는 좌표하강 탐색에서 완전히 제외(offset=0 고정,
  원본 EXP-219 확률 유지)
- 채택 규칙(실행 전 고정): 3개 threshold 중 baseline 대비 Macro F1
  개선 AND Log Loss 악화 없음 AND fold-std 악화 없음을 만족하는 가장
  작은 threshold를 공식 결과로 선택, 없으면 Macro F1이 가장 높은
  threshold를 참고용 대표값으로 보고하고 ARCHIVE 처리

## 결과 — threshold별 비교

| threshold | 게이트 제외 클래스 | OOF Macro F1 | delta | Log Loss delta | fold-std delta | 채택 규칙 충족 |
|---:|---|---:|---:|---:|---:|:---:|
| baseline(EXP-219) | — | 0.4222321460 | — | — | — | — |
| 15 | DLBC | 0.4238680837 | +0.0016359377 | +0.0243038788 | +0.0005752852 | ❌ |
| **20** | **DLBC, ACC** | **0.4262111346** | **+0.0039789886** | +0.0242183158 | +0.0026238894 | ❌ |
| 25 | DLBC, ACC (20과 동일) | 0.4262111346 | +0.0039789886 | +0.0242183158 | +0.0026238894 | ❌ |

Log Loss는 세 threshold 전부 EXP-233(게이트 없음, +0.0207270628)보다도
더 악화됐습니다 — 게이트로 제외된 클래스 외 나머지 클래스들의 offset이
좀 더 공격적으로 맞춰지면서 확률 보정 품질은 오히려 나빠진 것으로
보입니다.

Fold별 outer-validation delta:

| outer fold | threshold 15 | threshold 20/25 |
|---:|---:|---:|
| 0 | -0.004571 | -0.002659 |
| 1 | -0.003654 | +0.010772 |
| 2 | +0.003389 | +0.000224 |
| 3 | +0.003958 | +0.003958 |
| 4 | +0.002538 | +0.003848 |

threshold 20/25는 5개 중 1개(fold 0)만 하락, threshold 15는 2개(fold
0, 1) 하락 — fold 안정성만 보면 threshold 20/25가 더 낫습니다.

## 핵심 발견: 게이트가 그 클래스 자체를 보호하지 않는다

DLBC는 세 threshold 전부에서 자기 offset이 0으로 고정돼(원본 확률 그대로)
있는데도 F1이 그대로 유지되지 않았습니다.

| threshold | DLBC F1 (baseline 0.4286) | delta | ACC F1 (baseline 0.8296) | delta |
|---:|---:|---:|---:|---:|
| EXP-233(게이트 없음) | 0.3051 | -0.1235 | — | — |
| 15 (DLBC만 제외) | 0.3774 | **-0.0512** | 0.8296 | +0.0000 |
| 20/25 (DLBC+ACC 제외) | 0.3462 | **-0.0824** | 0.8321 | +0.0025 |

게이트가 있으면 게이트 없음(-0.1235)보다는 확실히 낫지만, **DLBC 자기
확률이 안 바뀌어도 F1은 여전히 하락**합니다 — argmax는 26개 클래스
확률의 상대적 경쟁이라, 이웃 클래스의 offset이 커지면 DLBC 확률이
그대로여도 다른 클래스에 argmax를 뺏길 수 있기 때문입니다. 더 흥미로운
점은 **ACC까지 같이 게이트를 걸면(threshold 20/25) DLBC가 threshold
15보다 오히려 더 나빠진다**(-0.0512 → -0.0824)는 것입니다 — 게이트로
묶인 클래스가 늘수록 남은(여전히 탐색 가능한) 클래스들의 offset이 더
크게 움직이며 DLBC 쪽으로 더 강하게 압박을 가하는 것으로 보입니다.

**목표에 따라 "최적점"이 갈립니다**:
- DLBC 보호가 최우선이면 threshold=15(DLBC만 제외)가 더 안전합니다.
- 전체 Macro F1이 최우선이면 threshold=20/25(DLBC+ACC 제외)가 2배
  더 크게 개선되고 fold 안정성도 낫지만, DLBC 손실은 더 커집니다.

ACC 자체 관점에서는 게이트가 명확히 이득입니다(F1 변화 사실상 0, 전체
개선에 기여) — ACC를 게이트에 포함하는 것 자체는 타당합니다. 다만 그
이득이 DLBC의 추가 희생과 함께 온다는 점은 이 방법론의 한계로 기록해
둡니다.

## 낙관 편향 디스클로저

EXP-233과 동일 — EXP-219(baseline)의 same-fold checkpoint 선택과 이
실험의 inner-fold early stopping(inner holdout을 eval_set 겸용) 둘 다
경미한 낙관 편향을 포함할 수 있습니다. outer validation은 offset을
transform으로만 받았으므로 위 결과 자체는 이 편향의 직접 영향을 받지
않습니다.

## 재현성

- Issue: [#276](https://github.com/fabxoe/open_cancer/issues/276)
- Config: `configs/exp276_nested_decision_offset_sample_gate.yaml`
- Resolved config: `reproducibility/exp276_nested_decision_offset_sample_gate/config.resolved.yaml`
- Metrics(공식 threshold=20 기준): `reports/exp276_nested_decision_offset_sample_gate/metrics.json`
- Threshold별 전체 비교(fold·클래스별 상세 포함): `reports/exp276_nested_decision_offset_sample_gate/threshold_comparison.json`
- 재현 상태: `NOT_STARTED`(일반 Local 실험, 재현 번들 불필요)
- 실행 시간: 2899.32초(약 48분, inner 모델 15개는 1회만 학습해 3개
  threshold가 공유)
- 제출: 없음(기각된 실험)
