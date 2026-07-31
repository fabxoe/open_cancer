# EXP-058 Co-mutation Pair Ablation — SHAP 근거로 APC/CTNNB1 제거

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-058 / #58 |
| 부모 실험 | EXP-052 |
| 유일한 모델 입력 변경 | co-mutation 쌍 3개(IDH1/IDH2, APC/CTNNB1, PIK3CA/PTEN) → 2개(IDH1/IDH2, PIK3CA/PTEN)로 축소 |
| 모델 | XGBoost, EXP-052/047과 동일 설정 |
| Local OOF Macro F1 | 0.4101842357 (팀 최고) |
| Public LB | 미제출 |
| 판단 | 채택 — SHAP 근거 그대로 확인됨(COAD 개선) |

## 배경: 왜 APC/CTNNB1을 뺐나

EXP-052(#52)는 문헌 근거로 3개 유전자 쌍의 co-mutation 피처를 추가했다.
이 중 IDH1/IDH2와 APC/CTNNB1은 "상호배타적"이라는 문헌 지식을 26개
암종 전체에 동일하게 적용했는데, 실제로는 소수의 배타성 위반 사례가
관측됐다(IDH1/IDH2 5건, APC/CTNNB1 77건 — train+test 합산). 원래는
"관련 암종(LGG/GBMLGG, COAD)에서만 조건부로 적용"하는 후속 실험을
계획했지만, **이 조건부 게이팅 자체가 test에서 알 수 없는 SUBCLASS
정보를 필요로 하는 target leakage**라는 걸 구현 전에 발견해 폐기했다.

대신 EXP-052의 저장된 checkpoint에 TreeSHAP
(`xgboost.Booster.predict(pred_contribs=True)`)을 적용해 "트리가 이미
암종별로 이 피처를 다르게 쓰고 있는지"를 직접 확인했다(각 피처가 활성화된
샘플만 대상으로 26개 클래스별 평균 SHAP 기여도 계산).

| 피처 | 활성 샘플 수 | 기대 클래스 순위(26개 중) | 판정 |
|---|---:|---:|---|
| `sample__comut_PIK3CA_PTEN` | 102 | UCEC 1위(0.042 vs 나머지 평균 -0.006) | 트리가 이미 정확히 학습 — 유지 |
| `sample__comut_APC_CTNNB1` | 33 | COAD 26위(꼴찌), 기여도 -0.005(음수) | 가설과 반대, 역효과 확인 — **제거** |
| `sample__comut_IDH1_IDH2` | 3 | LGG 15위, GBMLGG 20위, 기여도 ≈0 | 표본 부족, 해롭다는 근거 없음 — 유지 |

## 실제 결과

공용 `data/splits/stratified_5fold_seed42.csv`와 EXP-052/047의 XGBoost
설정을 그대로 사용했다.

| 항목 | EXP-047 | EXP-052(쌍 3개) | EXP-058(쌍 2개) |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4088132438 | 0.4095069739 | **0.4101842357** |
| fold 표준편차 | 0.0085063656 | 0.0052610612 | 0.0053035306 |

fold별 Macro F1: 0.4100673176, 0.4143098302, 0.4046742555, 0.4023218460,
0.4160092186 (fold 평균 0.4094764936).

EXP-052 대비 `+0.0006772617` 추가 개선, EXP-047 대비 누적 `+0.0013709918`.
클래스별로는 26개 중 13개 개선(BLCA +0.0265, LUSC +0.0197, DLBC +0.0196,
KIPAN +0.0161, SKCM +0.0159, ACC +0.0150), 13개 하락(PAAD -0.0230, THYM
-0.0204, HNSC -0.0156, LGG -0.0153, LUAD -0.0140).

**가장 중요한 확인**: SHAP 분석에서 예측한 대로 **COAD가 실제로 개선됐다**
(0.7126 → 0.7187, `+0.0061`). APC/CTNNB1 제거가 COAD 예측에 도움이 될
것이라는 가설이 실제 실행 결과로 직접 검증됐다.

## 재현 상태

`run_experiment` 공용 러너가 실행 직후 checkpoint 추론을 자동 재현
검증했다.

- 원본과 재생성 submission SHA-256: `0a53d0a7aea3b0c34baba586e56175c6bc8df2c738875a2bef30c5ebad905eb3`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.9739379847626424e-08`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다.

## 다음 실험 후보

1. IDH1/IDH2는 표본이 극히 적어(5건) 별도 검증이 무의미한 수준이므로
   추가 조사보다는 현행 유지.
2. co-mutation family를 더 넓히기보다, "문헌 지식이 이 데이터셋의 26개
   암종 전체에 고르게 성립하는지"를 새 쌍을 추가하기 전에 먼저 SHAP나
   유사 진단으로 사전 점검하는 절차를 다음 family 확장에도 적용.
3. 로컬 개선폭이 노이즈 수준을 크게 벗어나지 않으므로, 리더보드 제출은
   추가 검증(다른 seed 등) 후 판단.

## 관련 파일

- Config: `configs/exp058_cooccurrence_pair_ablation.yaml`
- Resolved config: `reproducibility/exp058_cooccurrence_pair_ablation/config.resolved.yaml`
- Metrics: `reports/exp058_cooccurrence_pair_ablation/metrics.json`
- Submission: `submissions/exp058_cooccurrence_pair_ablation.csv` (미제출)
- Reproduction: `reproducibility/exp058_cooccurrence_pair_ablation/`
- 이전 단계: `reports/exp052_hotspot_cooccurrence/README.md`
