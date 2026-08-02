# EXP-196 — S4 TruncatedSVD 저차원 비교 모델

각 canonical outer-fold의 학습 행에서만 4,384개 mutation-presence 열에
`TruncatedSVD(n_components=256)`를 fit하고, 256개 성분과 기존 sample aggregate,
고정 hotspot만 XGBoost에 전달한 저차원 비교 실험이다. validation과 test는 각
fold에 저장된 projector만 사용했으며 test·Public LB는 선택에 사용하지 않았다.

## 결과

- Fold Macro F1: 0.311846 / 0.351196 / 0.362893 / 0.360420 / 0.354315
- OOF Macro F1: **0.3496748557**
- EXP-094 대비: **-0.0672117181**
- Fold 표준편차: 0.0186183177 (`+0.0107340657`)
- Accuracy: 0.3688114820
- Log Loss: 2.0729362413 (`+0.2329989120`, 보조 지표)
- fold별 설명분산 합: 약 56.2%~57.4%
- 최악 클래스 변화: DLBC `-0.2843352348` (F1 0.0930232558)
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE`

## 판단

256차원 선형 투영은 희소한 유전자별 존재 신호를 지나치게 섞어 Macro F1,
fold 안정성, 다수 소수 클래스 F1을 모두 크게 훼손했다. 따라서 `ARCHIVE`하며
SVD 차원이나 iteration을 결과에 맞춰 재탐색하지 않는다. 해석성이 낮은 독립
앙상블 후보라는 원래 목적도 단독 성능 격차가 너무 커 우선순위를 부여하지 않는다.

이번 결과는 “저차원화 자체가 항상 과적합을 줄인다”는 가정이 이 희소 변이
데이터에는 성립하지 않음을 보여준다. 암종 구분에 필요한 희귀 유전자 신호가
상위 분산 성분에 충분히 보존되지 않은 것으로 해석한다.

## 산출물

- Config: `configs/exp196_s4_truncated_svd.yaml`
- Runner: `scripts/run_exp196_s4_truncated_svd.py`
- Metrics: `reports/exp196_s4_truncated_svd/metrics.json`
- Fold projector·checkpoint: `models/exp196_s4_truncated_svd/`
- OOF: `oof/exp196_s4_truncated_svd.csv`
- Test probability: `preds/exp196_s4_truncated_svd_test_proba.csv`
- Submission: `submissions/exp196_s4_truncated_svd.csv`
- Reproducibility: `reproducibility/exp196_s4_truncated_svd/`

