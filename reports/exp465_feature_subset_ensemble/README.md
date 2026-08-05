# EXP-465 Feature subset 다양성 앙상블 (hotspot-only vs sample-aggregate-burden-only)

## 결론

**REJECTED.** 서로 다른 shift 민감도를 가진 두 feature subset을
블렌드하면 EXP-450/EXP-457과 다른 실패 메커니즘이 나올 것으로
기대했지만, 실제로는 **두 컴포넌트 모두 feature가 극단적으로
부족해(35개, 74개) 단독 성능이 애초에 너무 낮았다**(OOF Macro F1
0.1427, 0.2770). 블렌드도 0.3082로 EXP-374(0.4268) 대비 -0.1186
붕괴, test-like 서브셋은 -0.1399로 더 크게 붕괴됐다. 이건 shift
민감도 차이로 설명되는 실패가 아니라 **실험 설계 자체의 결함**
(family-level shift-AUC 진단과 family-level 예측 충분성은 다른
질문이라는 것을 사전에 반영하지 못함)이다.

## 실험 설계

- Issue: [#465](https://github.com/fabxoe/open_cancer/issues/465)
- EXP-374의 feature build(파서, hotspot, pathway family, canonical
  5-fold/seed, 고정 하이퍼파라미터)를 그대로 재사용하되, column mask로
  두 하위 모델을 분리 학습
  - Model A(hotspot-only): `hotspot__*` 열만(fixed_hotspot family,
    #292 기준 shift-AUC ~0.55) — 35개 feature
  - Model B(sample-aggregate-burden-only): `sample__*` 열만
    (sample_aggregate_burden family — robust burden aggregate 3개 +
    fixed-pathway burden/composition, #292 기준 shift-AUC ~0.73) —
    74개 feature
- 블렌드: 고정 0.5/0.5
- `train_domain_propensity.csv`(#292) 상위 25% test-like 서브셋 delta가
  핵심 판정 기준(EXP-351/450/457/464와 동일 boundary)

## 결과

| 모델 | OOF Macro F1 | feature 수 |
|---|---:|---:|
| Model A(hotspot-only) | 0.1427365706 | 35 |
| Model B(burden-only) | 0.2769648421 | 74 |
| EXP-374(전체 feature) | 0.4267909268 | ~4,470+ |

| 지표 | 블렌드(A+B, 0.5/0.5) | EXP-374 단독 | 변화 | 게이트 |
|---|---:|---:|---:|---|
| OOF Macro F1(전체) | 0.3081813284 | 0.4267909268 | -0.1186095984 | **대폭 미달**(`+0.001` 필요) |
| **test-like 서브셋(n=1,666) Macro F1** | **0.2884492965** | **0.4283785968** | **-0.1399293003** | **대폭 미달 — 핵심 실패 신호** |
| worst-class delta | ACC `-0.4049386575` | — | — | **대폭 미달**(`-0.05` 필요) |

주요 붕괴 클래스: ACC(-0.4049), DLBC(-0.3976), BLCA(-0.2771), LAML
(-0.2560), GBMLGG(-0.2106), LUAD(-0.1640).

## 판단

- 원래 가설은 "hotspot(shift-AUC 낮음)과 burden(shift-AUC 높음)처럼
  shift 민감도가 다른 두 모델을 섞으면 EXP-450/457과 다른 실패(혹은
  성공)가 나올 것"이었다. 하지만 실제로는 **두 subset 모두 예측력
  자체가 너무 약해서(각각 34개·26-class 문제에 35개·74개 feature만
  사용) 이 가설을 검증할 수 있는 조건이 아니었다.** EXP-374 전체
  feature의 대부분(~4,300개 이상)을 차지하는 유전자별 mutation
  presence/type indicator가 두 subset 어디에도 포함되지 않았다 —
  #292의 family-level shift-AUC는 "이 열들만으로 train/test 도메인을
  구분할 수 있는 정도"를 측정한 진단이지 "이 열들만으로 26-class
  분류를 얼마나 잘 하는가"를 측정한 게 아니었다는 점을 설계 단계에서
  충분히 반영하지 못했다.
- 즉 이번 실패는 EXP-450/EXP-457(둘 다 EXP-374 수준의 예측력을 가진
  두 모델을 섞다가 shift/정규화 문제로 실패)과 성격이 다르다 —
  애초에 컴포넌트 자체가 경쟁력이 없었던 설계 실수에 가깝다.
- 방법론적 교훈: shift 민감도가 다른 컴포넌트로 다양성 앙상블을
  시도하려면, 각 컴포넌트가 EXP-449(단일 모델 교체, feature set
  100% 유지)처럼 최소한 근접한 예측력을 유지한 채 diversity 축만
  바꿔야 한다 — feature subset을 좁히는 방식은 예측력과 diversity를
  동시에 훼손해 비교 자체가 무의미해질 위험이 크다.
- 재시도(예: 각 subset에 raw mutation-presence 열을 공통으로 포함시켜
  예측력 격차를 줄이는 재설계)는 진행하지 않는다 — 마감 임박, 그리고
  이 경우 두 모델의 feature 대부분이 겹치게 되어 애초에 의도했던
  "다른 shift 민감도" 축이 흐려질 가능성이 높다.

## 재현성

- Config: `configs/exp465_feature_subset_ensemble.yaml`
- Runner: `scripts/run_exp465_feature_subset_ensemble.py`
- Test-like 체크: `scripts/check_exp465_test_like_subset.py`
- 컴포넌트 단독 진단: `reports/exp465_feature_subset_ensemble/component_metrics.json`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출(게이트 대폭 미달)
