# EXP-158: EXP-094 + `log1p(missense_count)`

## 목적

EXP-094의 동결 Feature Spec v1에 샘플별 missense 변이 개수의 `log1p` 피처
하나만 추가한 XGBoost incremental ablation입니다. test 라벨은 사용하지 않았습니다.

## 실행 조건

- Issue: [#158](https://github.com/fabxoe/open_cancer/issues/158)
- 부모 실험: EXP-094
- 분할: canonical `stratified_5fold_seed42.csv`, seed 42
- 모델: XGBoost, `configs/exp158_missense_burden.yaml`
- 환경: RunPod Secure Cloud RTX 4090, Python 3.11.10, XGBoost 3.2.0
- 실행 시간: 171.1666초
- 소스 commit: `aa145d7889836286ae9d48f4fd22c269b7525e41`

## 결과

| 지표 | EXP-158 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4183327348 | 0.4168865739 | +0.0014461609 |
| Fold 표준편차 | 0.0111795533 | 0.0078842521 | +0.0032953012 |
| Log Loss | 1.8384449866 | 1.8399373293 | -0.0014923427 |

Fold Macro F1은 `0.4119356604, 0.4185613137, 0.4035986033,
0.4193959228, 0.4374589988`였고 best iteration은 `214, 201, 232, 205, 221`입니다.

## 판단

Macro F1과 Log Loss는 개선됐지만 fold 표준편차가 EXP-094 대비 `+0.0032953`으로
사전 gate `+0.002`를 초과했습니다. 따라서 Feature Spec v1이나 Public 제출
후보로 채택하지 않고, burden 계열의 보조 분석 결과로 보존합니다.

## 산출물

- Metrics: [`metrics.json`](metrics.json)
- OOF 확률: `oof/exp158_missense_burden.csv`
- Test 확률: `preds/exp158_missense_burden_test_proba.csv`
- Submission: [`submissions/exp158_missense_burden.csv`](../../submissions/exp158_missense_burden.csv)
- Checkpoint: `models/exp158_missense_burden/`

현재 저장 checkpoint를 재로드한 확률이 원본 실행 확률과 byte-level로 일치하지 않아
재현 상태는 `NOT_STARTED`로 유지합니다. 원본 실행 결과를 임의로
`INFERENCE_VERIFIED`로 승격하지 않습니다.
