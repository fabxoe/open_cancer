# EXP-154: EXP-094 + `log1p(total_variant_count)`

## 목적

EXP-094 Feature Spec v1에 샘플별 전체 변이 토큰 수(`total_variant_count`)의
`log1p` 변환 피처 하나만 추가해 incremental OOF ablation을 수행했다.
변환과 모델 학습에는 test 라벨을 사용하지 않았다.

## 실행 조건

- Issue: [#154](https://github.com/fabxoe/open_cancer/issues/154)
- 부모 실험: EXP-094
- 분할: canonical `stratified_5fold_seed42.csv`
- 모델: XGBoost, 설정은 `configs/exp154_total_variant_burden.yaml`
- 실행 환경: RunPod Secure Cloud RTX 4090, CUDA
- 산출 metrics: [`metrics.json`](metrics.json)

## 결과

| 지표 | EXP-154 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4183986443 | 0.4168865739 | +0.0015120704 |
| Fold 표준편차 | 0.0135326743 | 0.0078842521 | +0.0056484223 |
| Log Loss | 1.8371068695 | 1.8399373293 | -0.0028304598 |

실행 시간은 약 228.8초였다. OOF Macro F1과 Log Loss는 개선됐지만 fold 변동성
악화가 사전 기준(표준편차 악화 < 0.002)을 초과했다.

## 판단

성능 개선 가능성은 확인했으나 안정성 gate를 통과하지 못했다. 따라서 이 피처를
Feature Spec v1 또는 공식 Public 제출 후보로 채택하지 않고, OOD가 큰 burden
피처의 보조 분석 결과로 보존한다. EXP-151과 마찬가지로 추가 burden 피처를
무조건 확장하지 않으며, 필요하면 fold별 안정성과 train/test shift를 함께 검증한다.

## 산출물

- 제출 파일: [`submissions/exp154_total_variant_burden.csv`](../../submissions/exp154_total_variant_burden.csv)
- OOF 확률: `oof/exp154_total_variant_burden.csv`
- Test 확률: `preds/exp154_total_variant_burden_test_proba.csv`
- Checkpoint: `models/exp154_total_variant_burden/`

재현성 상태는 현재 `NOT_STARTED`이다. 원본 실행의 checkpoint 추론과 독립 재학습
검증 번들을 아직 완성하지 않았다.
