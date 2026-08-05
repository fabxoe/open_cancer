# EXP-459 CatBoost on EXP-374 feature set (모델 다양성, CPU-bounded)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-459 / #459 |
| 목적 | EXP-374와 완전히 동일한 feature set 위에서 모델만 CatBoost로 교체해 모델 다양성 확보(EXP-449 LightGBM, #457 stacking과 병렬 트랙) |
| 핵심 입력 | EXP-374의 `build_fold_features()` 그대로(parser v2.1.0 stop-notation-invariant + Ensembl isoform mask + pathway families + hotspot-34), 35,181 fold-level 피처 |
| 모델 | CatBoost(CPU, depth=6, iterations=400, rsm=0.1 — GPU 미보유로 인한 compute-bounded 설정) |
| Local OOF Macro F1 | 0.4120129509 |
| Public LB | 미제출 |
| 판단 | 단독 성능은 EXP-374 미달(quality gate 실패), 다양성 gate는 명확히 통과 — 후속 blend/stacking 논의 대상으로 보존 |

## 원본 데이터와 입력

한 환자는 4,384개 유전자 각각에 대해 `WT` 또는 변이 표기 문자열로 표현된다.
이 실험은 EXP-374가 이미 만든 fold-safe 피처(변이 유무·유형, stop 표기
정규화, Ensembl isoform mask가 적용된 residue-position, pathway burden·구성,
hotspot-34)를 100% 그대로 재사용한다. 이 실험에서 새로 추가되거나 바뀐 피처는
없다.

## 핵심 개념과 피처

이 실험의 유일한 변경은 "어떤 모델이 이 피처를 학습하는가"다. EXP-374는
XGBoost(`tree_method=hist`)를 쓰고, EXP-459는 같은 입력을 CatBoost로 학습한다.
모델 계열이 다르면 같은 피처에서도 다른 오류 패턴을 보일 수 있고, 이는 이후
blend나 stacking에서 유용한 다양성 자원이 될 수 있다.

CatBoost 하이퍼파라미터는 EXP-127(GPU 실행)의 값을 출발점으로 삼았지만, 이번
실행 환경에는 GPU가 없어(EXP-127도 CPU에서 depth=8/iterations=1000이 fold
1개를 30분 안에 못 끝내 RunPod RTX 4090으로 옮긴 전례가 있다) 짧은 preflight
타이밍 측정(depth=6/rsm=0.1/border_count=32/thread_count=10에서
1.30초/iteration, `configs/exp459_catboost_exp374.yaml`의
`preflight.attempts` 참고)을 근거로 depth=6, iterations=400, rsm=0.1로
축소했다. 이는 재튜닝이 아니라 컴퓨트 제약에 따른 축소이므로, EXP-127의 GPU
결과와 직접 비교할 수 있는 값이 아니다.

## 모델이 학습하는 정보

입력은 EXP-374와 동일한 fold별 sparse 행렬(35,181 base 피처 + fold-train에서만
fit하는 pathway 추가 피처)이고, 타깃은 26개 고정 클래스 순서의 `SUBCLASS`다.
`balanced_sample_weight`를 사용했고, canonical stratified 5-fold(seed 42)를
그대로 따랐다. early stopping은 50 round로 설정했지만 5개 fold 모두
`best_iteration=399`(iterations 상한 도달)로 끝나, 이 축소된 설정에서는
학습이 완전히 수렴하지 않았을 가능성이 있다.

## 검증 방법

`data/splits/stratified_5fold_seed42.csv` 공용 fold를 사용했고, 각 fold의
pathway 추가 피처는 해당 fold의 train 행에서만 fit했다(EXP-374와 동일한
`PathwayMutationTypeFoldBuilder`). test/validation 정보를 전처리에 사용하지
않았다. 저장한 fold별 checkpoint(`.cbm`)로 test를 다시 추론해 제출 CSV
SHA-256과 라벨·확률 일치를 확인했다(`INFERENCE_VERIFIED`).

canonical EXP-374 자체는 Release·checkpoint가 실제로는 어디에도 업로드돼
있지 않아(manifest의 `storage_uri`가 전부 null) 로컬에 없었다. 다양성 gate를
정확히 계산하기 위해 별도 git worktree에서 main의
`scripts/run_exp374_stop_isoform_residue_mask.py`를 그대로 재실행해
`0.4267909268`(기록값과 완전히 일치, `INFERENCE_VERIFIED`)를 재확인한 뒤
그 OOF로 비교했다.

## 실제 결과

| 지표 | EXP-459 (CatBoost) | EXP-374 (XGBoost, parent) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4120129509 | 0.4267909268 | -0.0147779759 |
| Fold 평균 | 0.4113101437 | 0.4266436967 | -0.0153335530 |
| Fold 표준편차 | 0.0107206162 | 0.0085032169 | +0.0022173993 |
| Accuracy | 0.4004192872 | 0.4128366393 | -0.0124173521 |
| Log Loss | 1.9682460078 | 1.8440648317 | +0.1241811761 |

Fold별 Macro F1: `0.4030799284 / 0.4040365203 / 0.4244027938 / 0.4006900961 /
0.4243413801`.

### 클래스별 비교(EXP-374 대비)

큰 개선: KIRC `+0.2588`, LGG `+0.1595`.
큰 하락: STES `-0.1361`, SARC `-0.1185`, UCEC `-0.0783`, TGCT `-0.0709`,
GBMLGG `-0.0702`, BRCA `-0.0610`.

XGBoost와 CatBoost가 서로 다른 클래스에서 강점을 보이는 뚜렷한 보완 패턴이
있다(특히 KIRC·LGG는 CatBoost가 크게 우세).

### 다양성 gate

| 비교 항목 | 값 | 기준(PROJECT_CONTEXT.md 스태킹 조건) |
|---|---:|---|
| OOF 오류(정오답) 상관 | 0.6550612572 | ≤0.92 → 통과 |
| 예측 라벨 불일치율 | 0.3422028705 | ≥10% → 통과 |
| 확률 Pearson 상관(참고) | 0.8871325166 | - |

두 조건 모두 넉넉히 통과한다(EXP-449 LightGBM은 확률 상관 기준은 넘겼지만
불일치율로만 겨우 통과했던 것과 달리, CatBoost는 두 조건 다 명확히 통과).

## 해석과 한계

- 단독 성능은 EXP-374보다 낮고 fold 변동성과 Log Loss도 악화됐다. 이는
  compute-bounded 설정(rsm=0.1로 tree마다 피처 10%만 사용, depth=6,
  iterations=400에서 미수렴)의 직접적인 결과로 해석하며, CatBoost라는 모델
  계열 자체의 한계로 확대 해석하지 않는다. GPU로 EXP-127 수준의
  depth=8/iterations=1000을 썼다면 결과가 달라질 수 있다.
- 다양성 gate는 명확히 통과해 후속 blend·stacking 후보로는 유효하다. 다만
  EXP-253/EXP-450이 Local 게이트를 통과한 고정 블렌드도 test-like 서브셋에서
  무너진 전례가 있으므로, 이 모델을 blend에 쓰려면 같은 test-like propensity
  검증을 반드시 거쳐야 한다.
- best_iteration이 5-fold 모두 상한에 도달했다는 것은 이 축소 설정이 모델
  용량을 제한하는 병목이라는 신호다. 시간이 더 있다면 rsm을 높이거나
  iterations을 늘리는 재시도가 이 모델의 실제 한계를 더 정확히 보여줄 것이다.

## 다음 실험 후보

- GPU 환경이 확보되면 EXP-127과 동일한 depth=8/iterations=1000 설정으로
  재실행해 compute-bounded 효과와 모델 자체 효과를 분리한다.
- #457(stacking)과의 관계: #457은 EXP-449(LightGBM)를 대상으로 하지만, 같은
  fold-safe stacking 설계를 EXP-459에도 확장 검토할 수 있다.
- 다양성 자산으로 보존하고, 단독 채택은 하지 않는다.

## 재현과 관련 파일

- Config: `configs/exp459_catboost_exp374.yaml`
- Resolved config: `reproducibility/exp459_catboost_exp374/config.resolved.yaml`
- Metrics: `reports/exp459_catboost_exp374/metrics.json`
- OOF: `oof/exp459_catboost_exp374.csv`
- Test probability: `preds/exp459_catboost_exp374_test_proba.csv`
- Submission: `submissions/exp459_catboost_exp374.csv`(DACON 미제출)
- Source commit: `09430f2632c14ef459fb309915368bac561533f2`
- Reproduction status: `INFERENCE_VERIFIED`(저장 checkpoint 추론으로 제출 SHA-256·라벨·확률 일치 확인)
