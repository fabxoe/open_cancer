# EXP-065 Complex-token residue 위치 제외 단독 검증

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-065 / #65 |
| 부모 실험 | EXP-047 |
| 유일한 입력 변경 | complex token에서 읽은 위치를 residue aggregate에서 제외 |
| 모델 | XGBoost, EXP-047과 동일 설정 |
| 전체 피처 수 | 35,084 |
| Local OOF Macro F1 | 0.4108923084 |
| Public LB | 미제출 |
| 판단 | OOF 개선·fold 변동성 소폭 감소로 채택 후보 |

## 무엇을 비교했나

EXP-047의 `min + zero + complex include + raw`에서 complex token 위치 포함
정책만 `exclude`로 바꿨다. 예를 들어 다음 셀이 있다고 하자.

```text
R132H 312_313QY>HH
```

| 설정 | 최소 위치 계산에 사용하는 후보 | min |
|---|---|---:|
| EXP-047 `include` | 132, 312, 313 | 132 |
| EXP-065 `exclude` | 132 | 132 |

단순 치환 `R132H`는 유지하고 `_`, `>` 등이 포함된 complex token의 위치만
aggregate에서 제외한다. frameshift는 별도 mutation type이므로 이 설정으로
자동 제외하지 않는다.

## 검증 계약

- 공용 split: `data/splits/stratified_5fold_seed42.csv`
- 비교 기준: EXP-047
- 유지한 설정: `min + zero + raw`
- 유일한 변경: `complex_tokens: include → exclude`
- 모델: EXP-047과 동일한 XGBoost와 balanced sample weight
- Feature Factory: `1.1.0`
- Feature Spec SHA-256:
  `8a3fd33b7185d1d9a6166c8c90b5fc58f8e204e7570ffc9fb8dabe916086ee1e`

## 실제 결과

| 항목 | EXP-047 include | EXP-065 exclude | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4088132438 | 0.4108923084 | +0.0020790646 |
| fold 평균 | 0.4084268650 | 0.4106304222 | +0.0022035572 |
| fold 표준편차 | 0.0085063656 | 0.0084461093 | -0.0000602563 |
| Accuracy | 0.4031607805 | 0.4036445735 | +0.0004837929 |
| Log Loss | 1.8519974947 | 1.8529859781 | +0.0009884834 |

| fold | Macro F1 | best iteration |
|---:|---:|---:|
| 0 | 0.4092990615 | 200 |
| 1 | 0.4148643315 | 213 |
| 2 | 0.3958933689 | 260 |
| 3 | 0.4115588463 | 196 |
| 4 | 0.4215365027 | 228 |

크게 개선된 클래스는 LUAD `+0.0311`, LIHC `+0.0202`, PAAD `+0.0167`,
ACC `+0.0148`이었다. 크게 하락한 클래스는 CESC `-0.0127`, LAML
`-0.0113`, UCEC `-0.0113`이었다.

## 해석과 판단

complex 위치를 제외했을 때 공식 지표와 fold 안정성이 함께 개선됐다. 개선폭은
크지 않지만 방향이 일관되므로 채택 후보로 유지한다. 다만 Log Loss는 소폭
악화돼 확률 품질까지 개선됐다고 보기는 어렵다.

train의 complex token 비율은 약 0.13%, test는 약 5.65%로 차이가 크다.
이 사실은 사후 해석에만 사용하며 test 분포를 보고 라벨이나 피처 규칙을 조정하지
않는다. 다음에는 coarse bin을 EXP-047 기준에서 독립적으로 검증한다.

## 재현 상태

clean source commit `64f1a4c7d948c3951e88c9d80caf47fd2a5fd07b`에서 실행했다.

- 원본·재생성 submission SHA-256:
  `d39a589c88e7e8d4aabe93a980c5ff53729be4478f51f8767641ef3feb5ed9f6`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.9658508315932863e-08`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다.

## 관련 파일

- Config: `configs/exp065_xgb_residue_exclude_complex.yaml`
- Resolved config:
  `reproducibility/exp065_xgb_residue_exclude_complex/config.resolved.yaml`
- Metrics: `reports/exp065_xgb_residue_exclude_complex/metrics.json`
- OOF: `oof/exp065_xgb_residue_exclude_complex.csv` (로컬·재현 번들 대상)
- Test probability: `preds/exp065_xgb_residue_exclude_complex_test_proba.csv`
- Submission: `submissions/exp065_xgb_residue_exclude_complex.csv` (미제출)
- Reproduction: `reproducibility/exp065_xgb_residue_exclude_complex/`
