# EXP-279 — rolling-median Macro F1 checkpoint 안정화

EXP-219의 피처·canonical 5-fold·XGBoost 설정·balanced sample weight·seed를
그대로 유지하고, checkpoint 선택 규칙만 사전 고정된 trailing rolling median으로
바꾼 통제 실험이다. test와 Public LB는 iteration 선택에 사용하지 않았다.

## 선택 규칙

각 outer-fold validation에서 모든 boosting iteration의 Macro F1을 기록한 뒤 다음
규칙을 적용했다.

- trailing window: 21 iteration
- 후보: window 마지막 iteration이 100 이상인 경우만 허용
- 점수: window 안의 validation Macro F1 중앙값
- 선택: 중앙값이 가장 큰 window의 마지막 iteration
- 동률: 더 이른 iteration
- 후보 없음: 다른 기준으로 fallback하지 않고 실행 실패

각 fold의 raw Macro F1·Log Loss curve와 전체 rolling-median history는
`models/exp279_checkpoint_rolling_median/fold_NN_checkpoint_audit.json`에 저장했다.

## 실제 결과

| 지표 | EXP-219 단일점 최고 | EXP-279 rolling median | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4222321460 | 0.4206209582 | **-0.0016111878** |
| Fold 표준편차 | 0.0067203936 | 0.0072727214 | +0.0005523279 |
| Accuracy | 0.4097726173 | 0.4089662958 | -0.0008063216 |
| Log Loss | 1.8476127386 | 1.8463063240 | **-0.0013064146** |

fold별 선택 결과는 다음과 같다.

| Fold | EXP-219 iteration | EXP-279 iteration | EXP-279 Fold Macro F1 |
|---:|---:|---:|---:|
| 0 | 199 | 202 | 0.4185424302 |
| 1 | 218 | 236 | 0.4224270311 |
| 2 | 256 | 253 | 0.4093467651 |
| 3 | 116 | 121 | 0.4197500569 |
| 4 | 168 | 179 | 0.4319890962 |

클래스별 최악 하락은 LUAD `-0.0156934520`였고, 사전 붕괴 기준 `-0.05`를
넘은 클래스는 없었다. Log Loss는 소폭 개선됐지만 이 대회의 공식 지표는 Macro
F1이므로 보조 진단으로만 해석한다.

## 판정

사전 채택 후보 조건 중 fold 표준편차와 클래스별 F1, inference 재현 조건은
통과했다. 그러나 EXP-219 대비 Macro F1 하락 `0.0016111878`이 허용치 `0.001`을
넘었으므로 **ARCHIVE**한다.

window 21이나 minimum iteration 100을 같은 canonical OOF 결과에 맞춰 다시
조정하지 않는다. 이번 결과는 순간 최고점 선택의 변동을 줄이더라도 seed 42에서
Macro F1 손실을 완전히 피하지 못했다는 근거다. 제출하거나 EXP-219 기본 정책을
대체하지 않는다.

## 재현성과 산출물

- Config: `configs/exp279_checkpoint_rolling_median.yaml`
- Runner: `scripts/run_exp279_checkpoint_rolling_median.py`
- Metrics: `reports/exp279_checkpoint_rolling_median/metrics.json`
- OOF: `oof/exp279_checkpoint_rolling_median.csv`
- Test probability: `preds/exp279_checkpoint_rolling_median_test_proba.csv`
- Submission: `submissions/exp279_checkpoint_rolling_median.csv` (검증용, 미제출)
- Reproducibility: `reproducibility/exp279_checkpoint_rolling_median/`
- Source commit: `e904bc0e9a3e409c5b7884dbe6bf512bf63be1b7`

저장 checkpoint로 test 확률과 submission을 다시 생성해 라벨 일치율 100%, 확률
최대 차이 `1.43e-07`, submission SHA-256 일치를 확인했다. 따라서 재현 상태는
`INFERENCE_VERIFIED`다. EXP-219와 test argmax 라벨이 동일해 submission
SHA-256도 같지만, 확률과 OOF 결과는 서로 다른 실험 산출물이다.

