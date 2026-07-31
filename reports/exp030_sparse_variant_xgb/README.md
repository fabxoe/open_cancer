# EXP-030: XGBoost canonical effects

## 실험 요약

- 입력: 유전자 변이 유무, 유전자×변이 유형, 샘플별 변이 수
- split: `data/splits/stratified_5fold_seed42.csv`
- feature support 선택: 각 fold의 학습 행에서만 계산
- test 사용: fold 모델 학습 완료 후 추론에만 사용
- 후처리: 없음

## 결과

- 전체 OOF Macro F1: 0.4105408554
- Accuracy: 0.3999354943
- Log Loss: 1.8663449287
- Fold 표준편차: 0.0131713661

| Fold | 선택 특징 | Macro F1 | Accuracy | Log Loss | Best iteration |
|---:|---:|---:|---:|---:|---:|
| 0 | 18284 | 0.407582 | 0.390814 | 1.891498 | 392 |
| 1 | 18256 | 0.414416 | 0.395161 | 1.897513 | 392 |
| 2 | 18208 | 0.396069 | 0.387097 | 1.845652 | 414 |
| 3 | 18420 | 0.396270 | 0.402419 | 1.860726 | 395 |
| 4 | 18286 | 0.431516 | 0.424194 | 1.836315 | 474 |

## 재현성

- 저장된 5개 checkpoint를 다시 불러와 test 추론을 반복했습니다.
- 확률 허용 오차와 제출 라벨·SHA-256 일치를 검증했습니다.
- resolved config: `reproducibility/exp030_sparse_variant_xgb/config.resolved.yaml`
- metrics: `reports/exp030_sparse_variant_xgb/metrics.json`
- minimum support: 1
