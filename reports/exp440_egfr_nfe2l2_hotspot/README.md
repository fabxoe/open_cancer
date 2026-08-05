# EXP-440 EGFR A289/G598 + NFE2L2 E79 hotspot 확장

## 결론

burden-clean 확인된 대기열 후보 3개(EGFR 289/598, NFE2L2 79)를 EXP-374
위에 additive-only hotspot 컬럼으로 추가했다. **채택 게이트 2개(Macro F1,
Log Loss)를 동시에 미달해 REJECTED.**

## 실험 설계

- Issue: [#440](https://github.com/fabxoe/open_cancer/issues/440)
- 부모: EXP-374
- 유일한 변경: `hotspot__EGFR_289`, `hotspot__EGFR_598`, `hotspot__NFE2L2_79`
  3개 컬럼(stateless, position-level match, alternate AA 무관 —
  `EXTENDED_HOTSPOTS`/CTNNB1 D32-S33와 동일 관례) 추가
- Parser-invariant 확인: 단순 substitution 토큰(position+reference AA)만
  사용, stop-notation 재분류와 무관 — N5 native adapter가 나와도 이 결론은
  안 바뀔 것으로 판단됨
- canonical stratified 5-fold, seed 42, 공식 1회 실행(안정성 체크는
  게이트 통과 시에만 진행하기로 사전 합의 — 게이트 미달로 미실행)

## 결과

| 지표 | EXP-440 | EXP-374(부모) | 변화 | 게이트 |
|---|---:|---:|---:|---|
| OOF Macro F1 | 0.4270222874 | 0.4267909268 | +0.0002313605 | **미달**(`+0.001` 필요) |
| Fold 표준편차 | 0.0092560370 | 0.0085032169 | +0.0007528201 | 통과(`<0.002`) |
| Log Loss | 1.8624960184 | 1.8440648317 | +0.0184311867 | **미달**(명백한 악화) |
| worst per-class F1 | LUAD -0.0462494028 | — | — | 통과(`>-0.05`, 근접) |

클래스별 최대 하락은 LUAD(-0.0462), THYM(-0.0330). 최대 개선은
DLBC(+0.0269), CESC(+0.0185).

## 컬럼별 개별 기여도 (fold별 XGBoost gain)

| 컬럼 | fold 0 | fold 1 | fold 2 | fold 3 | fold 4 | 사용된 fold 수 |
|---|---:|---:|---:|---:|---:|---:|
| hotspot__EGFR_289 | 1.221 | 2.964 | 0.000 | 0.488 | 0.000 | 3/5 |
| hotspot__EGFR_598 | 1.422 | 3.304 | 0.276 | 0.526 | 1.057 | **5/5** |
| hotspot__NFE2L2_79 | 0.000 | 0.000 | 0.000 | 0.811 | 0.917 | 2/5 |

`hotspot__NFE2L2_79`는 5-fold 중 3개에서 전혀 split에 사용되지 않았다
(train 지지 n=4로 애초에 너무 희소함 — 예상된 결과). `hotspot__EGFR_598`이
5-fold 전부에서 일관되게 사용된 유일한 컬럼이다. 다만 전체 OOF Macro F1이
게이트를 미달했으므로, 이 컬럼별 차이가 "일부만 채택하면 통과"를
보장하지 않는다 — 셋 다 제외한다.

## 판단

- Macro F1 개선폭(+0.00023)이 게이트(+0.001)의 4분의 1에도 못 미치고,
  Log Loss는 오히려 뚜렷이 악화됐다 — 3-4 seed 안정성 체크로 넘어가지
  않는다(사전 합의된 조기 종료 조건).
- `hotspot__NFE2L2_79`는 표본 부족(n=4)으로 사실상 기여가 없다는 게
  기여도 분석으로 확인됐다 — 향후 재시도한다면 EGFR 2개만으로 좁히는 게
  더 합리적이겠으나, 전체 delta 자체가 미미해 재시도 우선순위는 낮다.
- CTNNB1 D32/S33(EXP-296)에 이어 이 세션에서 두 번째로 기각된 hotspot
  확장 시도 — 두 사례 모두 "burden-clean + 문헌적으로 타당"한 후보도
  실제 모델 게이트는 통과 못 할 수 있음을 재확인.

## 재현성

- Config: `configs/exp440_egfr_nfe2l2_hotspot.yaml`
- Runner: `scripts/run_exp440_egfr_nfe2l2_hotspot.py`
- Metrics: `reports/exp440_egfr_nfe2l2_hotspot/metrics.json`
- Public LB: 미제출(게이트 미달)
