# EXP-643 EXP-374 legacy 피처 + RandomForest (legacy 모델 다양성)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-643 / #643 |
| 목적 | EXP-596(native RandomForest)에 이어 legacy 계보(EXP-374)에도 CatBoost(EXP-459) 외 두 번째 모델 다양성 후보 확보 |
| 방법 | `run_exp374_stop_isoform_residue_mask.build_fold_features()` 100% 재사용, 모델만 RandomForest(EXP-596과 동일 하이퍼파라미터)로 교체 |
| Local OOF Macro F1 | 0.3999667430 (EXP-374 대비 -0.0268241839, 단독 품질 게이트 미달) |
| Public LB | 미제출 |
| 판단 | 단독 품질 게이트는 미달하지만 다양성 게이트(오류상관 0.6488, 라벨불일치 34.83%)는 명확히 통과 — EXP-459와 같은 판단으로 blend/stacking 자산으로 보존 |

## 배경

legacy 계보(EXP-374)는 지금까지 CatBoost(EXP-459) 하나만 모델 다양성
후보로 갖고 있었다. native 계보가 XGBoost(EXP-527)+RandomForest(EXP-596)
조합에서 성공을 거둔 것과 같은 구조를 legacy에도 만들기 위해, EXP-374
피처 위에 RandomForest를 추가로 학습했다. 하이퍼파라미터는 EXP-596이
같은 하드웨어·비슷한 35,119차원 sparse 입력에서 5-fold 전체 62초로
끝난 전례를 그대로 재사용해 preflight 없이 진행했다(실제로도 108초에
완료).

## 실제 결과

| 지표 | EXP-643(RandomForest) | EXP-374(parent) | EXP-459(CatBoost) |
|---|---:|---:|---:|
| OOF Macro F1 | 0.3999667430 | 0.4267909268 | 0.4120129509 |
| Fold 표준편차 | 0.0080176704 | - | 0.0107206162 |
| Accuracy | 0.3975165296 | - | 0.4004192872 |
| Log Loss | 2.0756178206 | - | 1.9682460078 |

Fold별 Macro F1: `0.4067, 0.3864, 0.4081, 0.3991, 0.4059` — fold 표준편차
0.008로 EXP-459보다도 안정적이다.

약한 클래스: SARC `0.1772`, KIPAN `0.1963`, PAAD `0.2353`, CESC `0.2437`,
STES `0.2447`, GBMLGG `0.2500`. 극단적 붕괴(F1=0)는 없다.

### 다양성 게이트

| 비교 | 오류(정오답) 상관 | 라벨 불일치율 |
|---|---:|---:|
| vs EXP-374 | 0.6487891390 | 34.83% |
| vs EXP-459 | 0.7606003270 | 28.79% |

두 비교 모두 다양성 게이트 임계값(오류상관 ≤0.92 또는 라벨 불일치
≥10%)을 명확히 통과한다.

## 해석과 한계

- 단독 품질은 EXP-374 대비 `-0.0268`로 ABC-Stack 로드맵의 wildcard
  허용치(`-0.010`)도 넘는 하락이라 단독 후보로 채택하지 않는다. legacy
  피처(35,119차원, 대부분 매우 희소한 유전자별 indicator)에서
  RandomForest가 boosting만큼 신호를 뽑아내지 못하는 것으로 보인다 —
  같은 패턴이 native 쪽 EXP-596(0.4052772619, CatBoost v1 최고 대비
  -0.0141799675로 단독 품질 게이트 미달)에서도 나타났었다.
- 다양성 게이트는 명확히 통과해 blend/stacking 자산으로 보존한다.
  EXP-596이 native 계보에서 한 역할과 동일한 역할을 legacy 계보에서
  맡을 수 있다.
- fold 표준편차가 EXP-459보다 낮아(0.008 vs 0.011) 비교적 안정적인
  모델이다.

## 다음 실험 후보

- EXP-374+EXP-459+EXP-643 3-way 고정 비율 블렌드를 공식 Experiment로
  시도(사전 고정 비율, 예: 0.6/0.25/0.15 등 — 팀 논의 필요).
- 3-way 이상은 nested weight search보다 고정 비율 스크리닝을 먼저 —
  EXP-642에서 2-way nested search조차 불안정했던 전례를 감안.

## 재현과 관련 파일

- Config: `configs/exp643_random_forest_exp374.yaml`
- Runner: `scripts/run_exp643_random_forest_exp374.py`
- Resolved config: `reproducibility/exp643_random_forest_exp374/config.resolved.yaml`
- Metrics: `reports/exp643_random_forest_exp374/metrics.json`
- Submission: `submissions/exp643_random_forest_exp374.csv`(DACON 미제출)
- Reproduction status: `INFERENCE_VERIFIED`(저장 checkpoint 추론으로 제출 SHA-256·라벨·확률 완전 일치)
