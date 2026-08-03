# POLE·Cell Cycle pathway feature — Macro-F1-checkpoint 재평가

> 새 모델 실험이나 EXP-ID를 만들지 않는 target-independent 재평가입니다.
> 재학습 없이 이미 저장된 checkpoint를 재사용했습니다. 실제 실험 결과의
> 단일 원본은 [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)와
> 실험별 `metrics.json`입니다.

## 배경

EXP-219(`EXP-094` + validation Macro-F1-best checkpoint 선택)와
EXP-223(`EXP-096` + 동일 정책)은 **feature를 하나도 바꾸지 않고** checkpoint
선택 기준만 mlogloss-best에서 Macro-F1-best로 바꿔 OOF Macro F1을 각각
`+0.0053`, `+0.0033` 개선했다. 그런데 이번 세션의 pathway feature
실험(EXP-170, EXP-173, EXP-181, EXP-226)은 전부 **mlogloss-checkpoint**
기준으로 기각 판정을 받았다. checkpoint 선택 방식이 feature 하나의 효과보다
큰 폭으로 결과를 흔들 수 있다는 것이 확인된 이상, 이 네 실험의 기각 판정이
checkpoint 정책 때문에 왜곡된 것은 아닌지 확인이 필요했다.

## 방법

- 4개 실험(EXP-170, EXP-173, EXP-181, EXP-226) 각각의 **이미 저장된 fold
  checkpoint**(`models/<slug>/fold_0X.json`)를 재사용했다. 재학습은
  하지 않았다. 각 checkpoint가 XGBoost early stopping의 patience
  round까지 전체 boosting 이력을 담고 있음을 먼저 확인했다(예: EXP-181
  fold 0은 `best_iteration=201`이지만 실제로는 232 round가 저장돼 있음).
- `src/open_cancer/checkpoint_selection.py`의
  `audit_xgboost_validation_iterations`(EXP-217/219/223이 만든 동일
  인프라)로 각 fold의 **validation 파티션에서만** 매 iteration의 Macro
  F1을 계산해 최고 iteration을 선택했다. test/Public LB는 선택에 전혀
  관여하지 않는다(fold-safe).
- **비교 기준(baseline)을 EXP-094(mlogloss-checkpoint)가 아니라
  EXP-219(macro-f1-checkpoint)로 교체**했다. checkpoint 정책 효과와
  feature 효과를 분리하기 위한 필수 조건이다 — EXP-094와 비교하면 두
  효과가 섞여 feature가 실제보다 나아 보일 수 있다.

## 결과

| 실험 | mlogloss-checkpoint OOF(기존) | macro-f1-checkpoint OOF(재평가) | checkpoint 정책만의 효과 | **EXP-219 대비 delta** | Gate(EXP-219 기준) |
|---|---:|---:|---:|---:|---|
| EXP-170(Cell Cycle A) | 0.4137048981 | 0.4187539579 | +0.0050490598 | **-0.0034781881** | ❌ |
| EXP-173(Cell Cycle B) | 0.4135108482 | 0.4190943128 | +0.0055834646 | **-0.0031378332** | ❌ |
| EXP-181(POLE D) | 0.4137048981 | 0.4183917895 | +0.0046868913 | **-0.0038403565** | ❌ |
| EXP-226(POLE E) | 0.4141560542 | 0.4182176287 | +0.0040615745 | **-0.0040145173** | ❌ |

EXP-219 baseline: OOF Macro F1 `0.4222321460`, fold 표준편차
`0.0067203936`, Log Loss는 `reports/exp219_macro_f1_checkpoint_selection/metrics.json`
참고.

**checkpoint 정책 전환 자체는 4개 전부에서 확실히 도움이 됐다**
(`+0.0041`~`+0.0056`, EXP-219/223과 같은 방향). 하지만 이는 feature와
무관하게 항상 나타나는 효과이므로, 같은 정책을 쓴 EXP-219와 비교하면
**4개 feature 전부 여전히 순손실**이다. 즉 mlogloss-checkpoint 기준의
기존 기각 판정은 checkpoint 정책 때문에 왜곡된 것이 아니라, feature
자체의 효과가 두 정책 모두에서 마이너스였다.

### Watch class(COAD/UCEC/DLBC) — EXP-219 대비

| 실험 | COAD | UCEC | DLBC |
|---|---:|---:|---:|
| EXP-170 | +0.0034111136 | -0.0049431203 | -0.0414746544 |
| EXP-173 | +0.0034111136 | -0.0086351755 | -0.0357142857 |
| EXP-181 | **+0.0108730775** | +0.0044351835 | -0.0582010582 |
| EXP-226 | +0.0078304353 | +0.0029496470 | -0.0582010582 |

COAD는 4개 실험 전부 여전히 양의 방향이고, DLBC는 4개 전부 여전히 크게
음의 방향이다(D/E는 오히려 EXP-094 대비 비교 때보다 더 악화).

## 결론

1. **게이트는 뒤집히지 않는다.** 4개 실험 전부 macro-f1-checkpoint로
   재평가해도 EXP-219 대비 여전히 기준 미달이다. mlogloss-checkpoint
   기준으로 내린 원래의 기각 판정(EXP-170/173/181/226)은 그대로 확정한다.
2. 게이트가 발동하지 않았으므로, **#174 정책 문서의 결론(gene-group
   aggregation·단일 유전자 위치 정밀화의 우선순위를 낮춘 판단)을 재검토할
   근거도 발생하지 않는다.**
3. **POLE pilot 트랙(D/E)과 Cell Cycle pilot 트랙(A/B)을 모두 최종
   종료한다.** 추가 재평가나 F(`POLE_ED_any_missense`) 진행은 하지 않는다.

## COAD 잔여 신호: 두 가지 대안 가설 (판단 보류)

COAD가 서로 완전히 무관한 두 gene-set(Cell Cycle 15/6개 유전자, POLE
5/21개 위치)에서 **공통으로**, 그리고 mlogloss-checkpoint와
macro-f1-checkpoint 두 정책 모두에서 일관되게 양의 방향을 보였다. 이 관찰에
대해 판단을 유보한 채 두 가설을 함께 남긴다.

- **가설 A(feature 정보 가설)**: 두 gene-set 모두 POLE-proofreading-deficient
  종양이 흔한 암종(UCEC, COAD)과 실제로 관련이 있어, 어떤 sparse feature를
  추가하든 COAD 관련 split이 우연이 아니라 실제로 약간의 이득을 얻는다는
  가설. Vera Health 도메인 자문과 부합하는 해석이다.
- **가설 B(구조적 상호작용 가설, 이번에 새로 추가)**: 서로 무관한 두
  gene-set에서 공통으로 나타난다는 사실 자체가, 이것이 추가한 feature의
  *내용*과는 무관하고, **COAD 클래스 자체가 (a) 소수 sparse 컬럼 추가에
  따른 `colsample_bytree` weighting perturbation, 그리고/또는 (b)
  macro-f1-checkpoint 선택 메커니즘과 구조적으로 상호작용하는 특성**일
  가능성을 시사한다. DLBC가 두 gene-set·두 checkpoint 정책 모두에서
  일관되게 나빠지는 것과 대칭적인 패턴이라, "특정 소수 클래스가 어떤
  perturbation에도 유난히 민감하게 반응한다"는 이미 확인된 메커니즘
  (`sparse_binary_feature_dlbc_sensitivity.md`)의 COAD 버전일 수 있다.

**이 문서는 두 가설 중 하나를 선택하지 않는다.** COAD가 두 checkpoint
정책 모두에서 일관됐다는 사실은 가설 A(생물학적 신호)와 가설 B(구조적
아티팩트) 둘 다와 양립 가능하다 — 가설 B가 맞다면 checkpoint 정책을
바꿔도 사라지지 않는 게 당연하고, 가설 A가 맞다면 진짜 신호이므로 역시
사라지지 않는 게 당연하다. 두 가설을 구분하려면 이 관찰만으로는 부족하고
별도 검증이 필요하다. 향후 pathway aggregation 트랙을 다시 열거나
클래스별 checkpoint 정책을 검토할 때 참고할 관찰로만 남긴다.

## 알려진 한계

- `predict_proba(..., iteration_range=...)`로 얻은 확률이 부동소수점
  오차로 정확히 1.0으로 합산되지 않아 `sklearn`이 경고를 출력했다(각
  fold당 최대 오차는 무시할 수준). Macro F1은 argmax 기반이라 이 오차의
  영향을 받지 않으며, Log Loss도 이 문서의 결론(게이트 통과 여부)에
  영향을 주지 않는 수준이다.
- 이 재평가는 EXP-219/223과 동일하게 "같은 validation fold에서 checkpoint를
  선택하고 점수도 그 fold로 측정"하므로 낙관 편향 가능성이 남아있다는
  주의사항이 그대로 적용된다.

## 재현

```bash
uv run python scripts/verify_macro_f1_checkpoint_reevaluation.py
```

원본 결과: `reports/analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.json`

## 관련 실험/문서

- [EXP-170](../exp170_cellcycle_any_nonsilent/README.md),
  [EXP-173](../exp173_cellcycle_lof_tsg/README.md),
  [EXP-181](../exp181_pole_hotspot5/README.md),
  [EXP-226](../exp226_pole_ed_driver_extended/README.md)
- [EXP-219](../exp219_macro_f1_checkpoint_selection/README.md)(비교 baseline),
  EXP-223(같은 정책의 pathway feature 적용 사례)
- [`sparse_binary_feature_dlbc_sensitivity.md`](sparse_binary_feature_dlbc_sensitivity.md)
  (DLBC 구조적 민감도, 이번 COAD 가설 B와 대칭)
