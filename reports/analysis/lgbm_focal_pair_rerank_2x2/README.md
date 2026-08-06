# LightGBM focal loss·혼동쌍 재분류 2×2 비교

## 결론

별도 `StratifiedKFold`에서 가장 좋은 arm은 기존
`multiclass + balanced sample weight` 기본 모델이었다. 2024 노트북의
one-vs-rest sigmoid focal loss와 KIPAN/KIRC·GBMLGG/LGG 전용 재분류를 그대로
분리해 시험했지만 둘 다 기본 모델을 개선하지 못했다.

이 분석은 canonical split을 사용하지 않은 일반 Task 탐색이다. 아래 점수를 기존
공식 History 점수와 직접 순위 비교하거나 `EXPERIMENT_HISTORY.md`에 기록하지 않는다.

## 통제 조건

- Issue: #622
- 피처: Parser-v4 `native_v3_semantic_range`
- 입력 shape: `(6201, 35080)`
- split: `StratifiedKFold(n_splits=5, shuffle=True, random_state=20240807)`
- canonical split 사용: 아니오
- 네 arm은 동일 행·피처·fold를 사용
- test·SUBCLASS 이외의 외부 정보·Public LB 미사용
- 재분류기는 각 outer-train의 해당 두 클래스만 사용

## 결과

| arm | 전체 OOF Macro F1 | fold 표준편차 | 기본 arm 대비 | 판단 |
|---|---:|---:|---:|---|
| balanced 기본 | 0.4306427197 | 0.0087628353 | 기준 | **최고** |
| balanced + pair rerank | 0.4219536240 | 0.0115223097 | -0.0086890958 | 기각 |
| focal 기본 | 0.2247035110 | 0.0134191259 | -0.2059392087 | 기각 |
| focal + pair rerank | 0.2336792475 | 0.0147332409 | -0.1969634723 | 기각 |

balanced 기본의 확률 Log Loss는 `1.8551370747`, focal 기본은
`3.0903992262`였다. pair rerank는 외부 노트북과 같이 최종 label만 교체하므로
일관된 26-class 확률을 만들지 않으며 Log Loss를 계산하지 않았다.

## 1. Focal loss 비교

외부 노트북과 같은 정의를 사용했다.

- one-vs-rest sigmoid focal loss
- `alpha=0.25`
- `gamma=1.0`
- 수치 미분 대신 동일 loss의 해석적 gradient/Hessian
- validation Macro F1 checkpoint

fold별 Macro F1은 `0.231744, 0.221630, 0.222165, 0.239238, 0.199382`였다.
여러 클래스의 F1이 0에 가깝게 붕괴했고 CESC로 예측이 과도하게 집중됐다. 이는
26-class softmax 문제에 binary one-vs-rest focal objective를 그대로 옮긴 결과다.
이번 설정을 Parser-v4 공식 실험으로 승격하지 않는다.

## 2. 혼동쌍 전용 재분류 비교

외부 노트북의 두 specialist 설정을 유지했다.

- KIPAN/KIRC: leaves 20, estimator 10, learning rate 0.1, min child 20
- GBMLGG/LGG: leaves 20, estimator 100, learning rate 0.02, min child 10
- 기본 모델이 해당 pair 중 하나를 예측한 행만 specialist label로 교체

balanced 모델에서 총 563개 OOF label이 바뀌었다. 일부 상위 집합형 클래스의 F1은
올랐지만 하위 클래스가 크게 붕괴했다.

| 클래스 | 기본 F1 | 재분류 F1 | 변화 |
|---|---:|---:|---:|
| KIPAN | 0.2040816327 | 0.4268104777 | +0.2227288450 |
| KIRC | 0.2794871795 | 0.0193704600 | -0.2601167194 |
| GBMLGG | 0.3169107856 | 0.4128342246 | +0.0959234390 |
| LGG | 0.4794520548 | 0.1950000000 | -0.2844520548 |

즉 specialist는 `KIRC → KIPAN`, `LGG → GBMLGG` 방향으로 지나치게 쏠렸다.
KIPAN과 GBMLGG가 각각 포괄 cohort 성격을 가진 데이터 라벨이라는 점을 단순 이진
재분류기가 해결하지 못했다. 이 방식은 Macro F1에서 특히 불리하다.

## 결정

1. 외부 노트북의 focal 설정은 공식 후보에서 제외한다.
2. 두 pair를 무조건 재판정하는 후처리는 제외한다.
3. 이번 결과는 현재 balanced LightGBM 설정을 바꿀 근거가 아니다.
4. pair 문제를 다시 다룬다면 hard rerank가 아니라 원 26-class 확률을 보존하는
   제한적 margin/offset 또는 계층적 joint objective가 필요하다.
5. 별도 split의 단일 결과이므로 balanced 기본 점수 자체를 공식 채택 점수로
   사용하지 않는다.

## 산출물

- `metrics.json`: 전체 지표, fold audit, confusion matrix
- `split_assignments.csv`: 이번 탐색 전용 fold 배정
- `oof_labels.csv`: 네 arm의 OOF label

재실행:

```bash
uv run --frozen --group experiment python scripts/compare_lgbm_focal_pair_rerank.py
```
