# EXP-597 BernoulliNB v1 스태킹 다양성 후보

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-597 / #597 |
| 목적 | #505 스태킹 로드맵 S0 다양성 감사용으로, 지금까지 채택된 모든 Feature Spec v1 모델(XGBoost/LightGBM/CatBoost/Logistic)이 판별형(discriminative)이라 생성형(generative) BernoulliNB로 오류 구조가 가장 이질적인 후보를 만들 수 있는지 확인 |
| 핵심 입력 | 동결 Feature Spec v1 (EXP-094와 동일, EXP-123/125/127과 동일 입력) |
| 모델 | scikit-learn `BernoulliNB` (alpha=1.0, 기본값) |
| Local OOF Macro F1 | 0.1762560191 |
| Public LB | 미제출 |
| 판단 | **ARCHIVE** — 단독 후보·스태킹 입력 모두 기각 |

## 실제 결과

- Fold Macro F1: 0.1826, 0.1833, 0.1785, 0.1693, 0.1629
- OOF Macro F1 / fold std: 0.1762560191 / 0.0079665976
- Accuracy / Log Loss: 0.1825512014 / 18.4437344683
- 클래스별 F1 최저 0.0221 — 0-F1 클래스는 없지만 전 클래스가 v1 계열
  다른 모델(Logistic/LightGBM/CatBoost)의 최저 클래스 F1(0.13~0.21)보다
  낮음
- 동일 v1 계열 비교: EXP-123(Logistic) 0.3763, EXP-125(LightGBM) 0.4189,
  EXP-127(CatBoost) 0.4195 대비 EXP-597은 최저 대비도 절반 이하
- Log Loss 18.44는 v1 계열 다른 모델(1.5~2 수준)과 자릿수가 다르게
  큼 — `BernoulliNB`의 독립성 가정이 ~4,000개 상호 상관된 희소 이진
  피처에서 심하게 깨지면서 확률이 과신(overconfident)된 것으로 보임

## 해석과 한계

생성형 모델이 판별형 모델과 다른 오류를 만든다는 가설은 맞았지만, 절대
성능 격차가 너무 커서(-0.20 이상) 소수 클래스를 특별히 보완하는 신호도
없이 단순히 전반적으로 약합니다. #505 S0 다양성 게이트의 "최고 기준
모델 대비 0.004 이내 하락" 조건은 물론, "소수 클래스 F1을 반복적으로
보완함" 조건도 충족하지 못합니다(전 클래스 최저 수준).

## 다음 실험 후보

이 방향은 추가 튜닝(alpha 조정, feature binarize threshold 변경)으로도
0.20 이상의 격차를 메우기 어렵다고 판단해 더 이상 진행하지 않습니다.
생성형 모델이 필요하다면 Gaussian/Complement 변형보다는 애초에 압축된
저차원 표현(SAINT 등, #504) 위에서 시도하는 편이 나을 것으로 보입니다.

## 재현과 관련 파일

- Config: `configs/exp597_bernoulli_nb_v1.yaml`
- Resolved config: `reproducibility/exp597_bernoulli_nb_v1/config.resolved.yaml`
- Runner: `scripts/run_exp597_bernoulli_nb_v1.py`
- Metrics: `reports/exp597_bernoulli_nb_v1/metrics.json`
- Submission: `submissions/exp597_bernoulli_nb_v1.csv`
- Reproduction status: `INFERENCE_VERIFIED`
