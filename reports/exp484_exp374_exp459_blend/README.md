# EXP-484 EXP-374+EXP-459 고정 0.7/0.3 확률 블렌드

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-484 / #484 |
| 목적 | Task #482 스크리닝(PR #483)에서 test-like propensity gate를 통과한 EXP-374+EXP-459 블렌드 비율(0.7/0.3)을 canonical 5-fold 공식 실행으로 확정 |
| 방법 | 재학습 없음, `0.7 * EXP-374 확률 + 0.3 * EXP-459 확률` 산술 평균(inference-only, EXP-075/135/253과 동일 패턴) |
| Local OOF Macro F1 | 0.4320213767 (EXP-374 대비 +0.0052304498) |
| Public LB | 미제출(팀 논의 후 진행) |
| 판단 | 전체 OOF·test-like subset·Log Loss·클래스 붕괴 기준은 모두 통과. Fold 표준편차만 사전 설정한 +0.002 임계값을 초과했으나, 모든 fold가 개선(악화된 fold 없음)한 상태에서 개선폭이 fold마다 고르지 않아 발생한 것으로 확인 — `ADOPT_WITH_CAUTION` |

## 배경

Task #482(PR #483)는 새 모델 학습 없이 기존 OOF 확률만으로 EXP-374+EXP-459
블렌드 후보 비율을 `#292` test-like propensity(train 중 "test처럼 보이는"
상위 25%) subset 게이트로 사전 스크리닝했다. LightGBM 계열(EXP-449,
#450/457/464/465)은 4번의 독립 시도 전부 test-like subset에서 REJECTED됐지만,
CatBoost(EXP-459)는 EXP-374 가중치 0.9~0.7 구간에서 전체·test-like 양쪽 모두
개선했고 **0.7/0.3이 두 지표 모두 최고**였다. 이 실험은 그 스크리닝 결과를
공식 실행으로 확정한다.

## 핵심 개념과 방법

새 모델을 학습하지 않는다. EXP-374(XGBoost, parent)와 EXP-459(CatBoost, 같은
EXP-374 feature set 위에서 모델만 교체)의 저장된 OOF·test 확률을
`0.7 * EXP-374 + 0.3 * EXP-459` 산술 평균으로 합치고, 그 argmax를 예측
라벨로 쓴다. 비율 0.7/0.3은 이 실행 전에 Task #482에서 이미 고정했으며,
test 분포나 Public LB로 선택하지 않았다.

canonical EXP-374는 Release·checkpoint가 업로드돼 있지 않아(manifest
`storage_uri` 전부 null), EXP-459 작업 중 별도 git worktree에서
`scripts/run_exp374_stop_isoform_residue_mask.py`를 재실행해 기록값과 완전히
일치하는 OOF(`0.4267909268`, `INFERENCE_VERIFIED`)를 이미 재확인해뒀다. 이
블렌드는 그 재현된 확률(`oof/exp374_stop_notation_isoform_mask.csv`)을
재사용한다.

## 검증 방법

`data/splits/stratified_5fold_seed42.csv` 공용 fold를 그대로 따르는 두
parent의 OOF에서 확률 평균만 계산했으므로 별도 학습·검증 절차는 없다. 두
parent 확률을 다시 읽어 블렌드를 재계산해 제출 CSV SHA-256과 라벨·확률
일치를 확인했다(`INFERENCE_VERIFIED`, 결정론적 계산이라 최대 절대 오차
`1e-6` 이내에서 완전 일치).

## 실제 결과

| 지표 | EXP-484 (블렌드) | EXP-374 (parent) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4320213767 | 0.4267909268 | +0.0052304498 |
| Fold 평균 | 0.4317393415 | 0.4266436967 | +0.0050956448 |
| Fold 표준편차 | 0.0137419885 | 0.0085032169 | +0.0052387716 |
| Accuracy | 0.4184808902 | 0.4128366393 | +0.0056442509 |
| Log Loss | 1.8336908448 | 1.8440648317 | -0.0103739869 |

Fold별 Macro F1(EXP-374 → EXP-484):

| Fold | EXP-374 | EXP-484 | 차이 |
|---:|---:|---:|---:|
| 0 | 0.4243902236 | 0.4243665025 | -0.0000237211 |
| 1 | 0.4214466890 | 0.4239061489 | +0.0024594600 |
| 2 | 0.4201172029 | 0.4218148394 | +0.0016976365 |
| 3 | 0.4239068711 | 0.4299131875 | +0.0060063164 |
| 4 | 0.4433574970 | 0.4586960290 | +0.0153385320 |

**fold 표준편차가 늘어난 원인은 악화가 아니라 불균등한 개선이다.** 5개 fold
전부 개선했거나(fold0은 사실상 동일, -0.00002) 뚜렷이 개선했는데, fold4의
개선폭(+0.0153)이 다른 fold(+0.002~+0.006)보다 훨씬 커서 fold 간 분산이
커졌다. 어떤 fold도 실제로 나빠지지 않았다는 점에서, 일부 fold가 무너져서
발생하는 전형적인 fold_std 악화(EXP-151/154/158/179 등)와는 다른 패턴이다.

### test-like propensity gate 재확인(#292)

공식 실행 결과로 Task #482 스크리닝을 다시 계산해 byte-level로 일치함을
확인했다.

| 지표 | 값 |
|---|---:|
| 전체 OOF delta | +0.0052304498 |
| test-like subset(상위 25%, 1,666/6,201행) delta | +0.0022953029 |

### 클래스별 비교(EXP-374 대비)

큰 개선: LGG `+0.0626`, LIHC `+0.0451`, CESC `+0.0450`, KIRC `+0.0319`,
DLBC `+0.0185`.
큰 하락: THYM `-0.0233`, BLCA `-0.0170`, TGCT `-0.0147`, STES `-0.0146`,
PRAD `-0.0107`.

`-0.05` 붕괴 기준을 넘는 클래스는 없다. XGBoost가 약했던 KIRC·LGG에서
CatBoost의 보완 효과(EXP-459 보고서에서 이미 확인된 우세 클래스)가 그대로
블렌드에 반영됐다.

## 해석과 한계

- 전체 OOF Macro F1·test-like subset·Log Loss·Accuracy는 모두 명확히
  개선했고 클래스 붕괴도 없다. Task #482 스크리닝과 공식 실행 결과가
  byte-level로 완전히 일치해 스크리닝 방법론 자체의 신뢰성도 확인됐다.
- Fold 표준편차만 사전 설정 임계값(`+0.002`)을 크게 초과했다(`+0.0052`).
  다만 원인 분해 결과 모든 fold가 개선(또는 사실상 동일)했고 개선폭이
  fold마다 다른 것이 원인이라, 전형적인 "일부 fold 붕괴로 인한 불안정"과는
  질적으로 다르다. 이 지표만으로 기계적으로 ARCHIVE 처리하지 않고
  `ADOPT_WITH_CAUTION`으로 기록한다.
- EXP-449(LightGBM) 계열 블렌드가 전부 실패했던 이유가 CatBoost보다 낮은
  오류 상관(다양성 부족)이었을 가능성을 시사한다 — 이 결과 자체가
  `project_model_diversity_ensemble_track` 트랙의 이전 결론("어떤 모델을
  블렌드해도 실패한다")을 반박하는 반례다.
- Public 제출은 이 보고서만으로 진행하지 않으며, Issue #484에서 팀 논의를
  거친다.

## 다음 실험 후보

- 팀 논의 후 Public 제출 검토(제출 시 별도 리더보드 제출 이력에 기록).
- fold4에 개선이 집중된 원인(클래스 구성·CatBoost가 특히 강한 KIRC/LGG의
  fold별 비율 차이 등) 진단은 선택 사항으로 남긴다 — 채택 여부에 필수는
  아니다.
- Kangho-Park의 비율 스윕·feature subset 통찰과 결합한 추가 블렌드 변형은
  이 실험과 별도 Issue로 진행한다.

## 재현과 관련 파일

- Config: `configs/exp484_exp374_exp459_blend.yaml`
- Runner: `scripts/run_exp484_exp374_exp459_blend.py`
- Resolved config: `reproducibility/exp484_exp374_exp459_blend/config.resolved.yaml`
- Metrics: `reports/exp484_exp374_exp459_blend/metrics.json`
- OOF: `oof/exp484_exp374_exp459_blend.csv`
- Test probability: `preds/exp484_exp374_exp459_blend_test_proba.csv`
- Submission: `submissions/exp484_exp374_exp459_blend.csv`(DACON 미제출)
- Screening: Task #482, `reports/analysis/exp459_blend_propensity_screening/`
- Reproduction status: `INFERENCE_VERIFIED`(결정론적 블렌드 재계산으로 제출 SHA-256·라벨·확률 일치 확인)
