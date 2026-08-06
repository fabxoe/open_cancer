# EXP-642 EXP-374+EXP-459 블렌드 가중치 nested 선택 (test-like 안정성 게이트)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-642 / #642 |
| 목적 | EXP-484(0.7/0.3 고정)를 EXP-628과 같은 nested search로 더 세밀하게(0.05 간격) 재탐색, 단 test-like subset 안정성을 해치지 않는 후보로 제한 |
| 방법 | 재학습 없음. leave-one-outer-fold-out nested weight search + 각 fold inner test-like subset이 순수 EXP-374 대비 악화되지 않는 후보만 허용 |
| Local OOF Macro F1 | 0.4278840047 (EXP-484 대비 -0.0041373720) |
| Public LB | 미제출 |
| 판단 | EXP-484보다 낮고 fold별 선택 가중치가 크게 흩어짐(0.5~0.85) — `ARCHIVE`. EXP-484의 0.7/0.3을 그대로 유지 |

## 배경

EXP-628에서 같은 nested search 방법(EXP-527+EXP-596)이 0.1 간격 스윕이
놓친 더 나은 지점(0.35)을 5개 fold 전부 동일하게 찾아내며 성공했다. 같은
아이디어가 EXP-374+EXP-459(legacy 계보)에서도 통하는지 확인했다. 다만 이
트랙은 test-like subset 안정성이 핵심 가치이므로(오늘 EXP-628 Public
제출로 native가 legacy보다 domain-shift에 훨씬 취약함이 실측 확인됨),
각 fold의 후보 가중치가 inner test-like subset에서 순수 EXP-374(가중치
1.0) 대비 악화되면 애초에 제외하도록 게이트를 걸었다.

## 실제 결과

| 지표 | EXP-642(nested) | EXP-484(0.7/0.3 고정) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4278840047 | 0.4320213767 | -0.0041373720 |
| Fold 표준편차 | 0.0155853635 | 0.0137419885 | +0.0018433750(악화) |
| Accuracy | 0.4160619255 | 0.4184808902 | -0.0024189647 |
| Log Loss | 1.8393414029 | 1.8336908448 | +0.0056505581(소폭 악화) |

### fold별 선택 가중치와 비교

| Fold | EXP-484(고정 0.7) | EXP-642(nested) | 선택된 EXP-374 가중치 | fallback |
|---:|---:|---:|---:|---|
| 0 | 0.4244 | 0.4160 | 0.50 | 아니오 |
| 1 | 0.4239 | 0.4210 | 0.85 | 아니오 |
| 2 | 0.4218 | 0.4226 | 0.65 | 아니오 |
| 3 | 0.4299 | 0.4210 | 0.50 | 아니오 |
| 4 | 0.4587 | 0.4587 | 0.70 | 아니오 |

`weight_range_across_folds = 0.35`(0.50~0.85) — EXP-628에서 5개 fold
전부 정확히 0.35로 수렴했던 것과 뚜렷이 대비된다. fold4는 우연히 고정
비율과 같은 0.70을 선택해 점수가 완전히 같지만, 나머지 4개 fold는 서로
다른 방향(더 균등하게 또는 더 EXP-374 쪽으로)으로 흩어졌고 결과도
EXP-484보다 대체로 낮다.

## 해석과 한계

- **fold 간 선택 가중치가 크게 흩어진다는 것 자체가 핵심 발견이다.**
  EXP-527+EXP-596 쌍은 어떤 4-fold 조합으로 봐도 같은 답(0.35)에
  수렴했지만, EXP-374+EXP-459 쌍은 그렇지 않다 — 이 쌍에는 안정적인
  "진짜 최적 가중치"가 존재하지 않고, fold별로 다른 지점이 우연히 더
  잘 맞을 뿐이다. 이런 상황에서 fold별로 다른 가중치를 쓰는 patchwork는
  Task #482가 전체 test-like subset을 종합해서 고른 단일 고정값(0.7)보다
  오히려 못하다.
- test-like 안정성 게이트는 정상 작동했다(fallback 없이 모든 fold가
  게이트를 통과하는 후보를 찾음). 게이트가 막은 게 아니라, 게이트를
  통과한 후보들 사이에서도 fold마다 다른 값이 이겨서 전체적으로 손해를
  본 것이다.
- 결론적으로 "더 세밀한 grid로 nested search를 하면 항상 더 좋아진다"는
  EXP-628의 교훈이 모든 모델 쌍에 적용되지는 않는다. 두 base 모델의
  오류가 fold마다 다르게 반응하면 nested 접근이 오히려 노이즈를 더할 수
  있다.
- EXP-484의 0.7/0.3 고정 비율은 그대로 유지한다. 재현성 검증은
  `INFERENCE_VERIFIED`로 정상 통과했으므로 방법 자체의 구현 문제는 아니다.

## 다음 실험 후보

- EXP-484(0.7/0.3)를 legacy 계보의 대표 후보로 유지.
- EXP-643(RandomForest on EXP-374 feature set)이 완료되면 3-way
  블렌드(EXP-374+EXP-459+EXP-643)를 고정 비율로 먼저 시도하고, nested
  search는 fold 간 합의가 확인될 때만 추가로 고려한다.

## 재현과 관련 파일

- Config: `configs/exp642_nested_blend_weight_exp374_exp459.yaml`
- Runner: `scripts/run_exp642_nested_blend_weight_exp374_exp459.py`
- Resolved config: `reproducibility/exp642_nested_blend_weight_exp374_exp459/config.resolved.yaml`
- Metrics: `reports/exp642_nested_blend_weight_exp374_exp459/metrics.json`
- Submission: `submissions/exp642_nested_blend_weight_exp374_exp459.csv`(DACON 미제출, ARCHIVE)
- Reproduction status: `INFERENCE_VERIFIED`(결정론적 재계산으로 가중치 선택·확률·제출 SHA-256 완전 일치)
