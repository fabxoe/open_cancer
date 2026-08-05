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

### 재설계 검토(2026-08-05) — 포기로 확정

"유전자별 mutation indicator를 공통 base로 포함하고 그 위에 hotspot만
추가한 모델 vs burden만 추가한 모델"로 재설계하면 예측력 격차 문제는
해결되는지 계산해봤다. 이번 실행에서 이미 만든 feature 산출물
(`data/processed/exp465_feature_subset_ensemble_features/feature_names.json`,
`reproducibility/exp374_stop_isoform_residue_mask/config.resolved.yaml`)
로 실측한 결과:

| 구성 요소 | 열 수 |
|---|---:|
| Base(유전자별 mutation indicator 등, "공통 포함" 대상) | 35,119 |
| Base 안의 `hotspot__*` (이미 base에 전부 포함됨) | 35 |
| Base 안의 `sample__*`(robust burden aggregate 등) | 12 |
| Fold-safe extra(pathway burden+composition, 전부 `sample__*`) | 62~63(fold별 상이) |
| EXP-374 전체 feature 수 | 35,119 + 62~63 ≈ **35,182** |

`hotspot__` 열은 이미 base 안에 전부 들어 있으므로, "base + hotspot
추가"는 base 그대로다. "base + burden 추가"는 base + fold-safe
extra(62~63) = **EXP-374 전체 feature set과 완전히 동일**하다. 즉
재설계하면:

- Model B'(base+burden) = EXP-374와 100% 동일한 feature set
- Model A'(base+hotspot) = EXP-374에서 62~63개(전체 대비 **0.18%**)만
  제거한 것

두 모델이 35,182개 열 중 99.82%를 공유하게 되어, 오차가 사실상 완전히
상관될 수밖에 없다 — 팀 다양성 게이트(OOF 확률 상관 ≤0.92 또는 예측
라벨 불일치율 ≥10%, #449/#459와 동일 기준)를 통과할 가능성이 사실상
없다. 학습 자체는 저렴하다(같은 머신 실측 기준 EXP-465의 좁은 모델
2개가 132초, EXP-449의 전체 feature 모델 1개가 279초였던 것을
근거로 전체급 모델 2개는 대략 15~35분 수준으로 추정 — 마감까지
남은 시간에 비하면 부담 없는 규모). **그러나 시간이 남아도 재설계는
진행하지 않는다** — 결과가 나와도 "EXP-374를 두 번 학습해 섞은 것"과
통계적으로 구분되지 않을 가능성이 높아 새로운 정보를 얻기 어렵고,
애초에 검증하려던 "다른 shift 민감도를 가진 컴포넌트의 앙상블"이라는
가설 자체를 이 feature space 구조(hotspot이 이미 base에 포함되어
있고, pathway/burden extra가 전체의 0.18%에 불과) 안에서는 물리적으로
구성할 수 없다는 것이 이번 계산의 핵심 결론이다. EXP-450(고정
블렌드)·EXP-457(stacking)·EXP-464(비율 스윕)·EXP-465(feature subset)
네 가지가 모두 이 EXP-374+EXP-449 기반 앙상블 공간에서 exploitable한
다양성을 찾지 못했다는 결과와 합쳐, **이 앙상블 축은 여기서 완전히
접는다.**

## 재현성

- Config: `configs/exp465_feature_subset_ensemble.yaml`
- Runner: `scripts/run_exp465_feature_subset_ensemble.py`
- Test-like 체크: `scripts/check_exp465_test_like_subset.py`
- 컴포넌트 단독 진단: `reports/exp465_feature_subset_ensemble/component_metrics.json`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출(게이트 대폭 미달)
