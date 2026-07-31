# EXP-063 Residue-position 관측 indicator 단독 검증

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-063 / #63 |
| 부모 실험 | EXP-047 |
| 유일한 입력 변경 | 위치 관측 여부 `residue_position_observed` 4,384개 추가 |
| 모델 | XGBoost, EXP-047과 동일 설정 |
| 전체 피처 수 | 39,468 |
| Local OOF Macro F1 | 0.4130329102 |
| Public LB | 미제출 |
| 당시 판단 | OOF 개선으로 채택 후보, fold 변동성과 Log Loss는 소폭 악화 |
| Issue #80 의미 감사 | 기존 mutation-presence의 완전 중복으로 확인 |

## 무엇을 비교했나

EXP-047은 각 유전자의 최소 단백질 잔기 위치를 사용하고, 위치를 읽을 수 없는
유전자는 위치 피처를 `0`으로 남기는 구현이다. EXP-063은 모델·split·seed·다른
피처를 그대로 유지하고 다음 indicator를 추가하려는 실험이었다.

```text
residue_position_observed = 위치를 읽었으면 1, 아니면 0
```

| 상황 | `min_residue_position` | `residue_position_observed` |
|---|---:|---:|
| 위치 132를 읽음 | 132 | 1 |
| WT·빈값 | 0 | 0 |

그러나 Issue #80에서 실제 sparse 산출물을 다시 검사한 결과, 현재 train/test의
모든 non-WT 토큰에서 양의 residue 위치가 파싱됐다. 따라서 이 데이터에서
`residue_position_observed`는 기존 `mutation_presence`와 완전히 동일하다.

| 의미 감사 항목 | Train | Test |
|---|---:|---:|
| mutation-presence와 indicator 불일치 | 0 | 0 |
| 위치 없는 변이 토큰 | 0 | 0 |
| `P(position=0 \| observed=1)` | 0 | 0 |

즉 EXP-063은 4,384개의 새로운 결측 정보를 추가한 실험이 아니라 기존
mutation-presence 열 4,384개를 복제한 실험이다.

## 검증 계약

- 공용 split: `data/splits/stratified_5fold_seed42.csv`
- 비교 기준: EXP-047
- 유지한 설정: `min + complex include + raw`
- 유일한 변경: `missing_policy: zero → indicator`
- 모델: EXP-047과 동일한 XGBoost와 balanced sample weight
- Feature Factory: `1.1.0`
- Feature Spec SHA-256:
  `c3b987785b397328dfaa9649ddd53ba78e737f77d01d9a1360b94a1e130c83e9`

## 실제 결과

| 항목 | EXP-047 zero | EXP-063 indicator | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4088132438 | 0.4130329102 | +0.0042196664 |
| fold 평균 | 0.4084268650 | 0.4124796619 | +0.0040527969 |
| fold 표준편차 | 0.0085063656 | 0.0097258347 | +0.0012194691 |
| Accuracy | 0.4031607805 | 0.4039671021 | +0.0008063216 |
| Log Loss | 1.8519974947 | 1.8523116112 | +0.0003141165 |

fold별 Macro F1은 다음과 같다.

| fold | Macro F1 | best iteration |
|---:|---:|---:|
| 0 | 0.4176226929 | 182 |
| 1 | 0.4112943222 | 223 |
| 2 | 0.3950600489 | 236 |
| 3 | 0.4141584489 | 226 |
| 4 | 0.4242627965 | 216 |

가장 크게 개선된 클래스는 DLBC `+0.0495`, LUAD `+0.0459`, PAAD
`+0.0302`, ACC `+0.0296`였다. 가장 크게 하락한 클래스는 UCEC
`-0.0176`, CESC `-0.0142`, PCPG `-0.0131`이었다.

## 해석과 판단

공식 지표인 전체 OOF Macro F1이 약 `+0.00422` 개선된 실제 결과는 변경하지
않는다. 다만 이 개선을 위치 결측 ambiguity 해소나 생물학적 위치 신호의 근거로
사용하지 않는다.

중복 열은 XGBoost의 `colsample_bytree=0.8` 환경에서 mutation-presence 계열이
split 후보로 선택될 상대 확률을 바꿀 수 있다. 따라서 EXP-063은 사후적으로
**중복 피처 weighting perturbation** 결과로 해석한다. fold 표준편차와 Log Loss도
소폭 증가했으므로 indicator 자체를 Feature Spec에 채택하지 않는다.

실제 QC 원본은
[`reports/analysis/residue_position_semantics_qc.json`](../analysis/residue_position_semantics_qc.json)과
[해석 보고서](../analysis/residue_position_semantics_qc.md)에 기록한다.

## 재현 상태

clean source commit `7265bf6c6fc166cf7f30ef07f41ed2c641a3fb56`에서 실행했다.
저장한 5개 checkpoint를 다시 불러와 test 예측을 재생성한 결과:

- 원본·재생성 submission SHA-256:
  `8b38546a4565a61970f49b6a2f1eb71b12127073c9981bf7afe6deeff7b0800b`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.972030643810797e-08`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다.

## 관련 파일

- Config: `configs/exp063_xgb_residue_indicator.yaml`
- Resolved config:
  `reproducibility/exp063_xgb_residue_indicator/config.resolved.yaml`
- Metrics: `reports/exp063_xgb_residue_indicator/metrics.json`
- OOF: `oof/exp063_xgb_residue_indicator.csv` (로컬·재현 번들 대상)
- Test probability: `preds/exp063_xgb_residue_indicator_test_proba.csv`
- Submission: `submissions/exp063_xgb_residue_indicator.csv` (미제출)
- Reproduction: `reproducibility/exp063_xgb_residue_indicator/`
