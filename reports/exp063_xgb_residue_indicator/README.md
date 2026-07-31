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
| 판단 | OOF 개선으로 채택 후보, fold 변동성과 Log Loss는 소폭 악화 |

## 무엇을 비교했나

EXP-047은 각 유전자의 최소 단백질 잔기 위치를 사용하고, 위치를 읽을 수 없는
유전자는 위치 피처를 `0`으로 남겼다. EXP-063은 모델·split·seed·다른 피처를
그대로 유지하고 다음 indicator만 추가했다.

```text
residue_position_observed = 위치를 읽었으면 1, 아니면 0
```

| 상황 | `min_residue_position` | `residue_position_observed` |
|---|---:|---:|
| 위치 132를 읽음 | 132 | 1 |
| WT·빈값·위치 없는 토큰 | 0 | 0 |

따라서 모델은 위치값 `0`이 실제 단백질 위치가 아니라 “위치를 관측하지 못함”을
나타낸다는 사실을 별도 피처로 알 수 있다.

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

공식 지표인 전체 OOF Macro F1이 약 `+0.00422` 개선돼 위치 관측 indicator는
채택 후보로 남긴다. 특히 일부 소수 클래스의 F1이 크게 개선됐다.

다만 fold 표준편차와 Log Loss는 소폭 증가했다. 즉 indicator가 모든 fold와
확률 품질을 일관되게 개선한 것은 아니다. 다음 위치 옵션을 단독으로 검증한 뒤
indicator와의 조합은 별도 Experiment Issue에서 확인해야 한다.

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
