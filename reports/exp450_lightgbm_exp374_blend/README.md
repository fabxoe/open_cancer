# EXP-450 EXP-374 + EXP-449(LightGBM) 0.5/0.5 블렌드

## 결론

**REJECTED.** 전체 OOF에서는 미미한 개선(+0.0004787061, 게이트 `+0.001`
미달)이었지만, **test-like 서브셋에서는 오히려 -0.0104454301로 악화** —
EXP-253과 정확히 같은 실패 패턴(Local 전체에서는 버티지만 test 분포에
가까운 샘플에서 무너짐)이 재현됐다. 이번엔 사전에 이 체크를 필수
완료조건으로 걸어둬서 Public 제출 없이 로컬에서 미리 잡아냈다.

## 실험 설계

- Issue: [#450](https://github.com/fabxoe/open_cancer/issues/450)
- 구성: EXP-374(XGBoost, 0.5) + EXP-449(LightGBM, 동일 feature set, 0.5)
  고정 산술 평균(`run_exp135_fixed_probability_blend.py` 엔진 재사용)
- `train_domain_propensity.csv`(#292) 상위 25% test-like 서브셋에서
  블렌드 vs EXP-374 단독 비교를 완료 조건에 필수로 포함(EXP-253 실패
  재현 방지 목적)

## 결과

| 지표 | 블렌드 | EXP-374 단독 | 변화 | 게이트 |
|---|---:|---:|---:|---|
| OOF Macro F1(전체) | 0.4272696329 | 0.4267909268 | +0.0004787061 | **미달**(`+0.001` 필요) |
| Fold 표준편차 | 0.0131082006 | 0.0085032169 | +0.0046049837 | **미달**(`<0.002` 필요) |
| Log Loss | 1.8085013600 | 1.8440648317 | -0.0355634717 | 통과(개선) |
| **test-like 서브셋(n=1,666) Macro F1** | **0.4179331667** | **0.4283785968** | **-0.0104454301** | **미달 — 핵심 실패 신호** |

## 판단

- test-like 서브셋에서 블렌드가 EXP-374 단독보다 뚜렷이 나쁘다는 건,
  LightGBM이 XGBoost와 다른 방향으로 실수하는 게 아니라 **같은 shift
  분포에 노출된 두 모델이 systematic bias를 상쇄하지 못하고 오히려
  증폭**시켰을 가능성을 시사한다 — EXP-253이 Public에서 -0.0178
  무너졌던 것과 같은 메커니즘으로 해석된다.
- 전체 OOF만 봤다면 "게이트 근소 미달이니 재시도해볼까"로 흘렀을
  수 있지만, test-like 체크가 훨씬 명확한 REJECT 신호를 줬다 — 이
  체크를 필수 완료조건으로 못박은 설계가 제 역할을 했다.
- Public 제출 없이 로컬에서 EXP-253급 실패를 미리 걸러냈다는 것
  자체가 이 실험의 실질적 성과.
- 추가 가중치 스윕(예: 0.6/0.4, 0.7/0.3)은 진행하지 않는다 — 마감
  임박, 그리고 fold_std·test-like 둘 다 큰 폭으로 미달이라 가중치
  조정으로 해결될 문제로 보이지 않는다.

## 재현성

- Config: `configs/exp450_lightgbm_exp374_blend.yaml`
- Runner: `scripts/run_exp450_lightgbm_exp374_blend.py`
- 재현 상태: `INFERENCE_VERIFIED`(inference-only 블렌드)
- Public LB: 미제출(게이트 미달)
