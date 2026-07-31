# EXP-069 Maximum residue-position 단독 검증

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-069 / #69 |
| 부모 실험 | EXP-047 |
| 유일한 입력 변경 | 유전자별 최소 위치 대신 최대 위치 사용 |
| 모델 | XGBoost, EXP-047과 동일 설정 |
| 전체 피처 수 | 35,084 |
| Local OOF Macro F1 | 0.4131007993 |
| Public LB | 미제출 |
| 판단 | OOF 개선·fold 변동성 감소로 채택 후보 |

## 무엇을 비교했나

EXP-047은 한 환자의 각 유전자에서 관측된 변이 위치 중 가장 작은 값 `min`을
사용한다. EXP-069는 나머지 조건을 유지하고 가장 큰 값 `max`만 사용한다.

예를 들어 한 유전자 셀에 위치 132, 312, 313의 변이가 있다면 EXP-047은
132를, EXP-069는 313을 입력한다. 위치가 하나뿐이면 min과 max는 같고,
여러 위치가 있을 때만 두 실험의 입력이 달라진다.

## 검증 계약

- 공용 split: `data/splits/stratified_5fold_seed42.csv`
- 비교 기준: EXP-047
- 유지한 설정: `zero + complex include + raw`
- 유일한 변경: residue aggregate `min → max`
- 모델: EXP-047과 동일한 XGBoost와 balanced sample weight
- Feature Factory: `1.1.0`
- Feature Spec SHA-256:
  `1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`

## 실제 결과

| 항목 | EXP-047 min | EXP-069 max | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4088132438 | 0.4131007993 | +0.0042875555 |
| fold 평균 | 0.4084268650 | 0.4127757527 | +0.0043488877 |
| fold 표준편차 | 0.0085063656 | 0.0082058569 | -0.0003005087 |
| Accuracy | 0.4031607805 | 0.4052572166 | +0.0020964361 |
| Log Loss | 1.8519974947 | 1.8525067568 | +0.0005092621 |

| fold | Macro F1 | best iteration |
|---:|---:|---:|
| 0 | 0.4088270533 | 209 |
| 1 | 0.4239996903 | 213 |
| 2 | 0.3999078004 | 285 |
| 3 | 0.4129369619 | 205 |
| 4 | 0.4182072576 | 228 |

크게 개선된 클래스는 LUAD `+0.0629`, BLCA `+0.0275`, DLBC `+0.0256`,
UCEC `+0.0181`이었다. 크게 하락한 클래스는 COAD `-0.0203`, HNSC
`-0.0194`, LGG `-0.0114`, SKCM `-0.0111`이었다.

## 해석과 판단

max 위치는 min보다 OOF Macro F1과 Accuracy를 높이고 fold 변동성을 줄였다.
여러 위치가 기록된 유전자에서는 뒤쪽 residue 정보가 앞쪽 residue 정보보다
암종 구분에 더 유용한 경우가 있음을 시사한다. 그러나 Log Loss는 소폭
악화됐으므로 예측 확률의 보정까지 개선됐다고 보기는 어렵다.

다음 `span = max - min` 실험은 위치 범위 자체가 추가 신호인지 독립적으로
확인한다. 그 결과를 보기 전에는 max와 span을 한 모델에 함께 넣지 않는다.

## 재현 상태

clean source commit `8b603bcf8b03658e54d158b5976df51c90cea5f8`에서 실행했다.

- 원본·재생성 submission SHA-256:
  `4e0046564d4b291c3f0c12370d3fe542b3faeb3fa2d105d36fe7386bfb7c3f08`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.974472046446408e-08`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다.

## 관련 파일

- Config: `configs/exp069_xgb_max_residue_position.yaml`
- Resolved config:
  `reproducibility/exp069_xgb_max_residue_position/config.resolved.yaml`
- Metrics: `reports/exp069_xgb_max_residue_position/metrics.json`
- OOF: `oof/exp069_xgb_max_residue_position.csv` (로컬·재현 번들 대상)
- Test probability: `preds/exp069_xgb_max_residue_position_test_proba.csv`
- Submission: `submissions/exp069_xgb_max_residue_position.csv` (미제출)
- Reproduction: `reproducibility/exp069_xgb_max_residue_position/`
