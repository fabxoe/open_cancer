# G7 최종 후보 재현·제출 준비 감사

> Issue #139의 task audit입니다. 새 학습과 Public LB 기반 선택을 수행하지 않았습니다.

## 최종 후보

최대 2개 제한에 따라 EXP-131과 EXP-125를 최종 독립 재현 검증 후보로 남깁니다. EXP-131은 Local Macro F1 최고 후보이고, EXP-125는 G4 품질·다양성 gate와 Public 결과가 있는 보수적 후보입니다.

| 실험 | OOF Macro F1 | Fold std | Log Loss | Public | 재현 상태 | 산출물 |
|---|---:|---:|---:|---:|---|---|
| EXP-131 | 0.4222392962 | 0.0140119367 | 1.8665114104 | 미제출 | INFERENCE_VERIFIED | 확인 필요 |
| EXP-125 | 0.4189078364 | 0.0081051732 | 1.8227982418 | 미제출 | INFERENCE_VERIFIED | 확인 필요 |

## 현재 제한

두 후보 모두 현재 `INFERENCE_VERIFIED`이며 `TRAINING_VERIFIED`가 아닙니다. 따라서 수상 후보로 확정하거나 최종 제출하지 않습니다. 다른 팀원이 fresh clone에서 `uv sync --frozen` 후 재학습·checkpoint 추론까지 검증해야 합니다.

## 다음 작업

1. 두 후보의 Release asset과 SHA-256을 보관합니다.
2. 작성자가 아닌 팀원이 독립 환경에서 재학습합니다.
3. OOF/test 라벨 100%, 확률 허용범위, 제출 SHA-256을 확인합니다.
4. `TRAINING_VERIFIED` 승격 후에만 리더보드 제출 후보로 확정합니다.
