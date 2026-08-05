# EXP-457 XGBoost(EXP-374) + LightGBM(EXP-449) Stacking 앙상블

## 결론

**REJECTED.** 고정 가중 블렌드(EXP-450)의 test-like 실패를 극복하려고
샘플별로 신뢰도를 다르게 학습하는 stacking 메타모델을 시도했지만,
결과는 더 나빴다 — 전체 OOF가 이미 **-0.0287** 하락(게이트 `+0.001`
미달), **test-like 서브셋은 -0.0473으로 오히려 더 크게 악화**됐고,
LGG/DLBC 등 소수 클래스 F1이 최대 -0.413까지 붕괴했다(게이트
`-0.05` 대폭 초과). 재현성은 `INFERENCE_VERIFIED`로 확인되어 코드
버그가 아니라 이 메타모델 설계 자체의 실패로 판단한다.

## 실험 설계

- Issue: [#457](https://github.com/fabxoe/open_cancer/issues/457)
- Base learner: EXP-374(XGBoost), EXP-449(LightGBM) — 재학습 없이
  기존 OOF/test 확률(26-class, `PROBA_` prefix)을 그대로 재사용
- Meta learner: `LogisticRegression(C=0.2, max_iter=1000, class_weight=None,
  random_state=42)` — 두 모델의 26-class 확률을 이어붙인 52차원 입력
  (EXP-137 전례와 동일 하이퍼파라미터)
- **Fold-safe 설계**: outer canonical 5-fold 구조 안에서 메타러너를
  cross-fit — 각 outer fold마다 나머지 4-fold의 base-OOF 행으로만
  메타러너를 학습하고, 해당 fold는 transform(예측)만 수행. Base OOF
  확률 자체가 이미 base 모델 기준으로 out-of-fold이므로, 어떤 행도
  자기 자신의 정답 레이블이 자신의 메타피처에 영향을 주지 않는다
  (#233 사고 계열의 이중 데이터 누수 없음). 최종 test 추론은 전체
  OOF 행으로 학습한 `final_model` 하나로 수행.
- `train_domain_propensity.csv`(#292) 상위 25% test-like 서브셋에서
  stacking vs EXP-374 단독 비교를 완료 조건에 필수 포함(EXP-253/
  EXP-450 실패 재현 방지 목적) — 이번에도 핵심 판정 기준으로 사용.

## 결과

| 지표 | Stacking | EXP-374 단독 | 변화 | 게이트 |
|---|---:|---:|---:|---|
| OOF Macro F1(전체) | 0.3981144756 | 0.4267909268 | -0.0286764512 | **미달**(`+0.001` 필요) |
| Fold 표준편차 | 0.0057992691 | 0.0085032169 | -0.0027039478 | 통과(개선) |
| Log Loss | 1.8327800269 | 1.8440648317 | -0.0112848048 | 통과(개선) |
| **test-like 서브셋(n=1,666) Macro F1** | **0.3811231363** | **0.4283785968** | **-0.0472554605** | **미달 — 핵심 실패 신호** |
| LGG F1 | 0.0474308300 | 0.4186046512(참고) | **-0.3711738211** | **대폭 미달**(`-0.05` 필요) |
| DLBC F1 | 0.0512820513 | 0.4642857143(참고) | **-0.4130036630** | **대폭 미달**(`-0.05` 필요) |

(참고 열은 동일 계산식으로 산출한 EXP-374 단독 OOF per-class F1)

## 판단

- Fold 표준편차와 Log Loss만 보면 오히려 개선된 것처럼 보이지만,
  이는 메타러너가 대부분의 클래스에서 다수 클래스(GBMLGG 등) 쪽으로
  확률을 밀어붙여 **분산은 줄었지만 소수 클래스 판별력을 통째로
  잃은** 결과다. Confusion matrix 기준 LGG 228건 중 204건이
  GBMLGG로 오분류됐다 — 두 클래스의 결정 경계가 사실상 사라졌다.
- 이 실패 패턴은 EXP-137(Issue #137)에서 이미 관측된 것과 동일한
  메커니즘이다: 52차원 확률 입력에 강한 L2 정규화(`C=0.2`)를 걸면
  메타러너가 클래스별 미세한 신뢰도 차이보다 다수 클래스 쪽으로
  수렴하는 지름길을 학습한다. 코드 버그가 아니라 이 데이터셋·클래스
  불균형 조건에서 다항 로지스틱 stacking 자체가 구조적으로 불리하다는
  두 번째 독립 확인이다.
- test-like 서브셋 delta(-0.0473)가 전체 delta(-0.0287)보다 더
  나쁘다는 것은, EXP-450과는 다른 메커니즘(같은 shift 분포 노출로 인한
  bias 증폭이 아니라 소수 클래스 붕괴)이지만 결과적으로 test 분포에
  가까운 샘플에서 더 크게 무너진다는 점은 동일하다 — 두 개의 서로
  다른 앙상블 기법(고정 블렌드, stacking)이 연속으로 test-like
  서브셋에서 실패한 만큼, EXP-374+EXP-449 조합 자체를 앙상블로 묶는
  접근은 당분간 보류하는 것이 합리적이다.
- Base OOF 확률의 정렬(`ID`/`SUBCLASS_TRUE`/`FOLD` 일치)과 outer
  cross-fit 루프는 EXP-137 전례를 그대로 따랐고, 저장된 fold별/최종
  모델을 다시 로드해 OOF·test 확률과 제출 파일을 재계산한 결과가
  원본과 100% 일치(`INFERENCE_VERIFIED`)해 누수나 재현성 버그가
  아님을 확인했다.
- 요약/축소 입력(max prob, entropy 등, Issue 본문에서 검토 항목으로
  언급됨)이나 정규화를 약하게 준 재시도는 진행하지 않는다 — 마감
  임박, 그리고 소수 클래스 붕괴 폭(-0.37~-0.41)이 하이퍼파라미터
  미세조정으로 해결될 수준을 넘어선다.

## 재현성

- Config: `configs/exp457_stacking_ensemble.yaml`
- Runner: `scripts/run_exp457_stacking_ensemble.py`
- Test-like 체크: `scripts/check_exp457_test_like_subset.py`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출(게이트 대폭 미달)
