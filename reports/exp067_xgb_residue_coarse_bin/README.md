# EXP-067 Residue-position coarse-bin 단독 검증

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-067 / #67 |
| 부모 실험 | EXP-047 |
| 유일한 입력 변경 | 원시 residue 위치를 폭 100의 고정 구간 번호로 변환 |
| 모델 | XGBoost, EXP-047과 동일 설정 |
| 전체 피처 수 | 35,084 |
| Local OOF Macro F1 | 0.4124014867 |
| Public LB | 미제출 |
| 판단 | OOF 개선·fold 변동성 감소로 채택 후보 |

## 무엇을 비교했나

EXP-047의 `min + zero + complex include + raw`에서 위치 표현만
`coarse_bin`으로 바꿨다. 구간 폭은 100이며 계산식은 다음과 같다.

```text
coarse_bin = (position - 1) // 100 + 1
```

예를 들어 residue 위치 1~100은 1, 101~200은 2가 된다. 유전자의 정확한
위치 차이를 모두 기억하게 하는 대신 대략적인 단백질 구간 정보를 제공하는
표현이다. 위치가 없는 유전자는 계속 0이고 complex token 위치도 계속 포함한다.

## 검증 계약

- 공용 split: `data/splits/stratified_5fold_seed42.csv`
- 비교 기준: EXP-047
- 유지한 설정: `min + zero + complex include`
- 유일한 변경: `transform: raw → coarse_bin`, 고정 `bin_width: 100`
- 모델: EXP-047과 동일한 XGBoost와 balanced sample weight
- Feature Factory: `1.1.0`
- Feature Spec SHA-256:
  `7e512f2a11263ef2d65adc85170d6717773f1538779298f540c4ccf3a27a144d`

## 실제 결과

| 항목 | EXP-047 raw | EXP-067 coarse-bin | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4088132438 | 0.4124014867 | +0.0035882429 |
| fold 평균 | 0.4084268650 | 0.4118860689 | +0.0034592039 |
| fold 표준편차 | 0.0085063656 | 0.0080562642 | -0.0004501014 |
| Accuracy | 0.4031607805 | 0.4034833091 | +0.0003225286 |
| Log Loss | 1.8519974947 | 1.8524806499 | +0.0004831553 |

| fold | Macro F1 | best iteration |
|---:|---:|---:|
| 0 | 0.4061401833 | 213 |
| 1 | 0.4242984236 | 207 |
| 2 | 0.4111564808 | 270 |
| 3 | 0.4011949462 | 220 |
| 4 | 0.4166403104 | 227 |

크게 개선된 클래스는 DLBC `+0.0697`, LUAD `+0.0385`, KIRC `+0.0342`,
BLCA `+0.0168`이었다. 크게 하락한 클래스는 HNSC `-0.0235`, SARC
`-0.0197`, CESC `-0.0174`, PCPG `-0.0151`이었다.

## 해석과 판단

coarse-bin은 원시 위치보다 OOF Macro F1을 높이고 fold 변동성을 줄였다.
즉 이 데이터에서는 residue 숫자의 아주 작은 차이보다 대략적인 위치 구간이
더 안정적인 신호일 가능성이 있다. 다만 Log Loss가 소폭 악화됐으므로 확률
품질까지 좋아졌다고 해석하지 않는다.

이 실험은 구간 폭 100 하나만 사전에 고정해 평가했다. 결과를 보고 여러 폭을
반복 선택하면 검증 점수에 과적합할 수 있으므로, 폭 변경은 별도 Experiment
Issue에서 독립 검증해야 한다.

## 재현 상태

clean source commit `5846db2f18f610836a38b23cc8c377f9809fe47c`에서 실행했다.

- 원본·재생성 submission SHA-256:
  `dbae8b3c15a35095bf17168862499972441c5143edf48c6dc7558e2eac633148`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.9743957519201558e-08`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다.

## 관련 파일

- Config: `configs/exp067_xgb_residue_coarse_bin.yaml`
- Resolved config:
  `reproducibility/exp067_xgb_residue_coarse_bin/config.resolved.yaml`
- Metrics: `reports/exp067_xgb_residue_coarse_bin/metrics.json`
- OOF: `oof/exp067_xgb_residue_coarse_bin.csv` (로컬·재현 번들 대상)
- Test probability: `preds/exp067_xgb_residue_coarse_bin_test_proba.csv`
- Submission: `submissions/exp067_xgb_residue_coarse_bin.csv` (미제출)
- Reproduction: `reproducibility/exp067_xgb_residue_coarse_bin/`
