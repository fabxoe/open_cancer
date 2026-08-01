# EXP-135: EXP-094 + EXP-125 fixed probability blend

## 목적

G4 감사에서 품질·다양성 gate를 통과한 EXP-125와 기준 EXP-094의 예측 확률을
학습 없이 사전 고정한 `0.5/0.5`로 평균했습니다. OOF 또는 Public LB를 확인한
뒤 가중치를 조정하지 않았습니다.

## 결과

| 항목 | EXP-135 | EXP-094 | EXP-125 | EXP-131 최고 단일 |
|---|---:|---:|---:|---:|
| OOF Macro F1 | 0.4201772665 | 0.4168865739 | 0.4189078364 | 0.4222392962 |
| Fold 표준편차 | 0.0126953092 | 0.0078842521 | 0.0081051732 | 0.0140119367 |
| Log Loss | 1.8083444812 | 1.8399371814 | 1.8227982412 | 1.8665114104 |

EXP-094와 EXP-125의 평균은 Log Loss를 크게 낮췄지만, 현재 최고 단일 모델
EXP-131보다 Macro F1이 `0.0020620298` 낮고 G5의 fold 안정성 기준을 충족하지
못했습니다. 따라서 리더보드에는 제출하지 않고, 추가 가중치 탐색도 보류합니다.

## 재현성

- Issue: [#135](https://github.com/fabxoe/open_cancer/issues/135)
- Branch: `issue-135-exp-fixed-blend`
- Config: `configs/exp135_fixed_probability_blend.yaml`
- Resolved config: `reproducibility/exp135_fixed_probability_blend/config.resolved.yaml`
- OOF: `oof/exp135_fixed_probability_blend.csv`
- Test probability: `preds/exp135_fixed_probability_blend_test_proba.csv`
- Submission: `submissions/exp135_fixed_probability_blend.csv`
- Reproducibility: `INFERENCE_VERIFIED`

재실행에서 OOF·test 확률, 예측 라벨과 제출 CSV SHA-256이 일치했습니다. 이
실험은 부모 확률을 결합하는 inference-only 실험이므로 새 checkpoint는 만들지
않았습니다.
