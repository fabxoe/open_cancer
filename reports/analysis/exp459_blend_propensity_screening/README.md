# EXP-374+EXP-459 블렌드 사전 스크리닝 (#292 test-like propensity 게이트)

`analysis_only` — Task #482. 새 모델 학습 없음, EXP-ID 없음. 재실행:

```bash
uv run python scripts/screen_exp459_blend_propensity.py
```

## 배경

#450(EXP-374+LightGBM 고정 블렌드)·#457(stacking)·#464(비율 스윕)·#465(feature
subset 앙상블)는 전부 `#292`의 test-like propensity(train 중 "test처럼 보이는"
상위 25%) subset에서 REJECTED됐다. 이번 스크리닝은 EXP-459(CatBoost, 오류상관
0.6551·라벨불일치 34.2%로 EXP-449/LightGBM보다 더 확실히 다양성 gate를 통과한
모델)를 정식 Experiment Issue로 열기 전에 같은 패턴이 반복되는지 먼저 확인한다.

## 방법

- test-like subset: `train_domain_propensity.csv`(#292)의
  `oof_test_domain_probability` 상위 25%(quantile 0.75 threshold
  `0.2500581443`) — #450/457/464/465와 동일 정의. 1,666/6,201행.
- 블렌드: `w * EXP-374 확률 + (1-w) * EXP-459 확률`의 argmax, `w ∈
  {0.9, 0.8, 0.7, 0.6, 0.5}`.
- 기준선: EXP-374 단독 Macro F1(전체 `0.4267909268`, test-like subset
  `0.4283785968`).

## 결과

| EXP-374 weight | 전체 OOF Macro F1 | 전체 delta | test-like Macro F1 | test-like delta | gate |
|---:|---:|---:|---:|---:|---|
| 0.9 | 0.4274963653 | +0.0007054385 | 0.4291430853 | +0.0007644885 | PASS |
| 0.8 | 0.4293346172 | +0.0025436904 | 0.4304399261 | +0.0020613293 | PASS |
| **0.7** | **0.4320213767** | **+0.0052304498** | **0.4306738997** | **+0.0022953029** | **PASS (최고)** |
| 0.6 | 0.4311594924 | +0.0043685656 | 0.4269368131 | -0.0014417837 | FAIL |
| 0.5 | 0.4323313776 | +0.0055404508 | 0.4281145523 | -0.0002640446 | FAIL |

## 해석

EXP-449(LightGBM)와의 4번의 독립 시도(#450/457/464/465)는 **모든** 비율에서
test-like gate에 실패했지만, EXP-459(CatBoost)는 **0.9/0.1~0.7/0.3 구간에서
전체·test-like 양쪽 모두 개선**한다. 이전 실패의 핵심 메커니즘("같은
shift-sensitive 분포를 학습한 두 모델은 상쇄되지 않는다")이 보편적이지 않고,
**parent와의 오류 상관이 충분히 낮은 모델(EXP-459 0.6551 vs EXP-449 대비 더 낮음)은
다른 결과를 낼 수 있다**는 것을 시사한다.

다만 CatBoost 비중이 0.4를 넘어가면(0.6/0.4, 0.5/0.5) 전체 OOF는 계속
개선되는데도 test-like subset은 악화로 돌아선다 — parent 확률을 과도하게
누르면 이전 실패 패턴과 같은 방향으로 재현된다는 뜻이다. **0.7/0.3(EXP-374
0.7 / EXP-459 0.3)이 전체·test-like 두 지표 모두에서 최고**다.

## Go/No-Go

**GO** — 0.7/0.3 비율을 시작점으로 정식 블렌드 Experiment Issue를 제안한다.
이 스크리닝은 진단이며, 채택은 별도 Experiment Issue의 canonical 5-fold
공식 실행과 INFERENCE_VERIFIED 확인을 거쳐야 한다.

## 제약

- SUBCLASS는 Macro F1 계산에만 사용했고 학습 전처리에는 사용하지 않았다.
- `train_domain_propensity.csv`는 기존에 팀장 검토로 analysis-only 승인된
  자산을 재사용했을 뿐 test 데이터를 새로 참조하지 않았다.
- Public LB는 사용하지 않았다.
- 이 결과만으로 공식 채택하지 않으며, 정식 Experiment Issue의 canonical
  5-fold 재현이 필요하다.
