# EXP-233 nested class-wise decision offset — 기각(ARCHIVE)

## 결론

baseline **EXP-219**(macro-f1-checkpoint 정책 XGBoost)의 이미 저장된 OOF
확률에, 각 outer fold의 train 부분에서만 inner cross-fitting(K=3)으로
고른 26-값 class-wise logit offset을 transform-only로 적용했습니다. 전체
OOF Macro F1은 **0.4241894920**으로 baseline보다 **+0.0019573460**
개선됐지만, **DLBC(38건, 최소 클래스) F1이 -0.1235 붕괴**했고 Log Loss도
`+0.0207270628` 악화, fold 표준편차도 `+0.0014296379` 악화됐으며 5개
outer fold 중 2개(fold 2, 3)는 오히려 하락했습니다. **소수 클래스 붕괴와
fold 불안정성 때문에 기각(ARCHIVE)합니다** — Macro F1이 순증가했다는
사실만으로 채택하지 않습니다.

## 설계

`reports/analysis/external_biological_knowledge_feature_review.md`
(91~106행)의 nested decision rule 설계 제약을 그대로 구현했습니다.

- **재학습 없음**: outer 모델은 EXP-219의 저장된 checkpoint/OOF를 그대로
  사용(`exp-219-repro-v1` Release 번들, SHA-256 이중 검증 완료)합니다.
- **Inner cross-fitting**: 각 outer fold의 train 부분(~4961행) 안에서만
  `StratifiedKFold(n_splits=3)`로 3개 inner 모델을 새로 학습해(총 15개)
  outer-train 전체를 커버하는 honest(leak-free) 확률을 만듭니다. 이
  확률로만 offset을 탐색합니다 — outer validation/test는 어디에도 fit에
  쓰지 않습니다.
- **Offset 탐색**: 26개 클래스 각각 `[-1.0, 1.0]` 범위(0.1 step, 21개
  candidate)에서 좌표하강(coordinate descent, 최대 5 pass)으로
  regularized Macro F1(`macro_f1 - 0.001 * Σoffset²`)을 최대화하는 값을
  고릅니다. 범위·step·정규화 강도는 실행 전 config에 고정했습니다
  (`configs/exp233_nested_decision_offset.yaml`).
- **적용**: `softmax(z+o) ∝ softmax(z)·exp(o)` — 확률 공간에서 곱셈 후
  재정규화이므로 raw margin 재학습이 필요 없습니다. outer validation에는
  탐색된 offset을 transform만 합니다.
- **Test 범위 밖**: 이번 라운드는 완료 조건(OOF Macro F1/fold-std/클래스별
  F1)에 명시된 대로 OOF만 다룹니다. test 확률 적용(저장된 5개 fold
  checkpoint를 다시 불러와 fold별로 offset을 적용한 뒤 평균)은 이번
  스코프에 포함하지 않았습니다.

## 결과

| 항목 | EXP-219 (baseline) | EXP-233 (offset 적용) | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4222321460 | 0.4241894920 | **+0.0019573460** |
| Fold 표준편차 | 0.0067203936 | 0.0081500315 | +0.0014296379 (악화) |
| Log Loss | 1.8476127465 | 1.8683398093 | +0.0207270628 (악화) |

Fold별 outer-validation Macro F1(offset 적용 전 → 후):

| outer fold | before | after | delta |
|---:|---:|---:|---:|
| 0 | 0.4211513302 | 0.4214118590 | +0.0002605287 |
| 1 | 0.4235533012 | 0.4250889014 | +0.0015356002 |
| 2 | 0.4113978176 | 0.4102364970 | **-0.0011613206** |
| 3 | 0.4214009350 | 0.4182223664 | **-0.0031785686** |
| 4 | 0.4324842903 | 0.4350221884 | +0.0025378981 |

5개 fold 중 **2개(fold 2, 3)가 offset 적용 후 오히려 하락**했습니다 —
전체 OOF가 개선된 건 fold 1/4의 큰 개선이 fold 2/3의 하락을 상쇄했기
때문이지, 모든 fold에서 일관되게 나아진 게 아닙니다.

## 소수 클래스 붕괴 — DLBC

| 클래스 | before | after | delta |
|---|---:|---:|---:|
| **DLBC** | 0.4286 | 0.3051 | **-0.1235** |
| BLCA | 0.5028 | 0.4646 | -0.0381 |
| LIHC | 0.3217 | 0.2932 | -0.0284 |
| GBMLGG | 0.3062 | 0.2840 | -0.0222 |

DLBC의 -0.1235는 이번 세션에서 관측된 어떤 DLBC 교란보다도 큽니다
(feature 추가 실험들은 -0.03~-0.09 범위,
`reports/analysis/sparse_binary_feature_dlbc_sensitivity.md` 참고).
원인은 outer fold별로 탐색된 DLBC(index 5) offset 자체가 부호와 크기가
전혀 일관되지 않다는 데 있습니다.

| outer fold | DLBC offset |
|---:|---:|
| 0 | +0.3 |
| 1 | -0.5 |
| 2 | +0.8 |
| 3 | -0.7 |
| 4 | -0.0 |

fold마다 DLBC를 올렸다 내렸다 하는 이 패턴은 inner cross-fitting이
DLBC에 대해서는 진짜 신호가 아니라 **노이즈를 학습해 fold마다 다른
방향으로 과적합**하고 있다는 뜻입니다 — outer fold당 DLBC 표본이
7~8건뿐이라 inner-CV로도 안정적인 신호를 얻기엔 근본적으로 부족합니다.
이는 이번 세션에서 반복 확인한 DLBC의 구조적 config-민감성(seed·
hyperparameter·feature 추가 어떤 축으로 흔들어도 비슷한 크기로,
그러나 방향은 예측 불가능하게 움직임)과 정확히 같은 패턴이 **post-hoc
calibration이라는 완전히 다른 메커니즘에서도 재현**된 것입니다.

가장 크게 개선된 클래스는 TGCT(+0.0796), LGG(+0.0763), HNSC(+0.0319),
KIRC(+0.0300)로, DLBC만큼 극단적이지 않은 중간 규모 클래스들입니다.

## 낙관 편향 디스클로저 (PROJECT_CONTEXT.md 정책)

- **EXP-219(baseline)**: 각 outer fold의 checkpoint iteration을 그 fold의
  validation Macro F1으로 고른 뒤 같은 fold 점수를 보고합니다 — 선택
  과정에서 생긴 낙관 편향이 baseline 자체에 이미 존재합니다.
- **EXP-233(이 실험)**: inner fold의 early stopping이 그 inner holdout을
  eval_set으로 동시에 사용합니다(프로젝트 전반의 outer-fold OOF 생성과
  동일한 기존 관행) — inner cross-fit 확률에도 같은 종류의, 정도가 더
  약한 낙관 편향이 존재할 수 있습니다.
- 두 편향 모두 outer validation의 최종 판정(위 표의 macro F1)에는
  영향을 주지 않습니다(outer validation은 offset을 fit이 아니라
  transform으로만 받았습니다). 다만 이 결과를 현재 최고·최종 후보로
  승격하려면 반복 seed, 독립 재학습 또는 Public LB로 추가 안정성 확인이
  필요합니다 — 이번 실험 자체가 그 확인을 대체하지 않습니다.

## 재현성

- Issue: [#233](https://github.com/fabxoe/open_cancer/issues/233)
- Config: `configs/exp233_nested_decision_offset.yaml`
- Resolved config: `reproducibility/exp233_nested_decision_offset/config.resolved.yaml`
- Metrics: `reports/exp233_nested_decision_offset/metrics.json`
- Fold별 offset·탐색 상세: `reports/exp233_nested_decision_offset/offset_search_detail.json`
- 재현 상태: `NOT_STARTED`(일반 Local 실험, 리더보드 미제출·팀 상위 모델
  아님이라 재현 번들 불필요, PROJECT_CONTEXT.md 8절 기준)
- 실행 시간: 2651.81초(약 44분, inner 모델 15개 학습 포함)
- 제출: 없음(기각된 실험, test 확률 적용도 이번 스코프 밖)
