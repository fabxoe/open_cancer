# EXP-179 — Feature Spec v1 + fold-local SMOTE

## 결론

EXP-094 Feature Spec v1 XGBoost의 학습 fold에만 standard SMOTE를 적용한
불균형 처리 ablation이다. OOF Macro F1은 **0.4080771375**로 EXP-094보다
**0.0088094364 하락**했다. 일부 소수 클래스와 Log Loss는 개선됐지만 LGG,
BLCA, SARC의 큰 F1 하락을 상쇄하지 못했으므로 **ARCHIVE**로 보존한다. 이 결과는
리더보드에 제출하지 않으며 SMOTE 파라미터 재탐색도 하지 않는다.

## 무엇을 검증했나

SMOTE는 적은 클래스의 기존 학습 샘플 사이에 인공적인 중간 샘플을 만들어 학습
클래스 수를 늘리는 기법이다. 이번 데이터의 원래 변이 존재 피처는 0/1이지만,
SMOTE가 만든 행은 연속값을 가질 수 있다. 이 차이가 암종 분류에 도움이 되는지
확인하기 위해 standard SMOTE를 한 번만 사전 고정해 비교했다.

변경은 다음 하나뿐이다.

- 각 outer fold의 **학습 행에만** `SMOTE(k_neighbors=5,
  sampling_strategy="not majority")` 적용
- validation 행과 test 행은 절대 resampling하지 않음
- 이중 보정을 피하기 위해 `balanced_sample_weight=false`
- 나머지 Feature Spec v1, canonical stratified 5-fold, XGBoost 설정은 EXP-094와
  동일

각 fold의 원본 학습 행은 4,960 또는 4,961개였고 SMOTE 뒤 16,328~16,354개가 됐다.

## 결과

| 지표 | EXP-179 | EXP-094 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.4080771375 | -0.0088094364 |
| Fold Macro F1 평균 | 0.4071367384 | - |
| Fold 표준편차 | 0.0071789606 | -0.0007052914 |
| Accuracy | 0.4046121593 | -0.0025802290 |
| Log Loss | 1.8043550352 | -0.0355822941 |

Fold Macro F1은 `0.3974984540`, `0.3992874129`, `0.4138424225`,
`0.4127372064`, `0.4123181959`다.

가장 크게 개선된 클래스는 DLBC (`+0.05121`), GBMLGG (`+0.04544`), TGCT
(`+0.04042`)였지만, LGG (`-0.11775`), BLCA (`-0.10784`), SARC (`-0.08514`)의
손실이 더 컸다. 따라서 “평균적으로 더 균형 잡힌 학습”이라는 해석은 Macro F1
기준에서 성립하지 않는다.

## 재현성

원 학습은 checkpoint와 metrics를 생성했으나 산출물 기록 단계가 중단됐다. 저장된
5개 checkpoint로만 추론을 다시 수행하여 OOF·test 확률과 submission을 복구했다.
재학습은 하지 않았다.

- 데이터 해시 일치
- OOF/test 예측 라벨 100% 일치
- 확률 최대 절대 차이 0
- submission SHA-256 일치
- OOF Macro F1 차이 0

따라서 재현 상태는 `INFERENCE_VERIFIED`이다. 독립된 fresh clone 재학습은 아직
수행하지 않았으므로 `TRAINING_VERIFIED`는 아니다.

## 경로와 실행

- Config: `configs/exp179_xgb_feature_spec_v1_smote.yaml`
- Runner: `scripts/run_exp179_xgb_feature_spec_v1_smote.py`
- 원 결과: `reports/exp179_xgb_feature_spec_v1_smote/metrics.json`
- 재현성 비교: `reproducibility/exp179_xgb_feature_spec_v1_smote/comparison.json`

저장 checkpoint가 있는 환경에서 재추론만 하려면 다음을 실행한다.

```bash
uv run python scripts/run_exp179_xgb_feature_spec_v1_smote.py --replay-checkpoints
```

생성되는 checkpoint, OOF/test 확률, submission은 대용량 또는 대회 산출물이므로
Git에 커밋하지 않는다.
