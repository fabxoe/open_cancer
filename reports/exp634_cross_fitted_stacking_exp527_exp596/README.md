# EXP-634 EXP-527+EXP-596 cross-fitted L2 Logistic Regression 스태킹

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-634 / #634 |
| 목적 | #505 Cross-fitted Stacking 로드맵 S2 단계. EXP-628(전역 스칼라 가중치 하나)보다 클래스별로 다른 가중치를 학습하는 메타모델이 더 나은지 확인 |
| 방법 | 재학습 없음, base(EXP-527, EXP-596) OOF만 사용. Outer 5-fold cross-fitted L2 Multinomial Logistic Regression(`C=0.2, class_weight=null`) |
| Local OOF Macro F1 | 0.3274295444 (EXP-628 대비 -0.1373184 폭락) |
| Public LB | 미제출 |
| 판단 | 소수 클래스 6개 심각 붕괴(3개는 F1=0)로 `ARCHIVE`. EXP-137에서 이미 관측된 실패 패턴이 훨씬 더 심하게 재현됨 |

## 배경

#505 로드맵이 정의한 S2 단계 첫 시도. base 확률만 입력받는 강하게 규제된
선형 메타모델(`C=0.2` L2 Logistic Regression)을 EXP-527+EXP-596 위에
`scripts/run_exp137_cross_fitted_stacking.py`와 동일한 canonical 5-fold
cross-fitting 패턴으로 실행했다. EXP-137(EXP-094+EXP-125, 같은
하이퍼파라미터)이 이미 "소수 클래스 F1 붕괴"로 기각된 전례가 있어 위험은
알려져 있었지만, #505가 첫 메타모델로 이 설정을 명시적으로 지정했기 때문에
그대로 먼저 실행했다.

## 실제 결과

| 지표 | EXP-634(스태킹) | EXP-628(비교 기준) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.3274295444 | 0.4647479423 | -0.1373183979 |
| Fold 평균 | 0.3206732559 | 0.4654638314 | -0.1447905755 |
| Fold 표준편차 | 0.0427117754 | 0.0093589481 | +0.0333528273(대폭 악화) |
| Accuracy | 0.4296081277 | 0.4486373166 | -0.0190291889 |
| Log Loss | 1.9979459458 | 1.9979672657 | -0.0000213199(사실상 동일) |

fold별 Macro F1: fold0 `0.2918`, fold1 `0.3734`, fold2 `0.2856`, fold3
`0.3722`, fold4 `0.2805`(EXP-628은 전부 `0.45~0.48`대).

### 클래스별 붕괴

| 클래스 | F1 |
|---|---:|
| DLBC | 0.0000 |
| SARC | 0.0000 |
| THYM | 0.0000 |
| PAAD | 0.0164 |
| LGG | 0.0173 |
| PCPG | 0.0267 |

`-0.05` 붕괴 기준을 압도적으로 넘는 클래스가 6개다. 반면 다수 클래스
(SKCM 0.8795, ACC 0.7833, COAD 0.7550)는 오히려 EXP-628과 큰 차이가 없어,
메타모델이 다수 클래스 판별에는 문제가 없고 소수 클래스 신호만 체계적으로
무시했다.

### 진단: 왜 이렇게 붕괴했나

- fold별 계수는 안정적이었다(`coef_abs_max` 5.24~5.47, fold 간 편차
  작음). **극단적 계수나 발산이 원인이 아니다.**
- `class_weight=null`로 학습한 다항 로지스틱 회귀가 불균형 클래스
  (`DLBC` 38개/6,201개 ≈ 0.6%, `BRCA` 786개 ≈ 12.7%, 약 20배 차이)에서
  L2 규제와 결합해 소수 클래스 방향의 계수를 체계적으로 축소시켰다.
  EXP-137도 같은 설정에서 같은 방향(DLBC·PAAD·SARC 붕괴)의 실패를
  보였지만 이번엔 훨씬 심각하다 — EXP-527/EXP-596의 확률이 EXP-094/EXP-125
  조합보다 다수 클래스에 더 확신 있게(peaked) 몰려 있어서, 메타모델이
  소수 클래스 구분 신호를 학습할 유인이 더 적었던 것으로 추정된다.
- **Log Loss는 거의 변하지 않았다**(`-0.00002`). 다수 클래스가 표본의
  대부분을 차지해 평균 손실에는 소수 클래스 붕괴가 거의 드러나지 않는다.
  Macro F1을 1차 지표로 쓰는 PROJECT_CONTEXT 정책이 정확히 이런 실패를
  잡아내기 위한 것임을 보여주는 사례다.

## 해석과 한계

- `+0.002` 이상 개선이라는 #505 학습형 메타모델 채택 기준에 압도적으로
  미달해 `ARCHIVE`. base 모델(EXP-527, EXP-596) 또는 고정/nested 블렌드
  (EXP-628)보다도 훨씬 나쁘다 — 스태킹이 항상 블렌드보다 나은 것은 아니라는
  #505 로드맵의 경고("단일 OOF 최고점만으로 채택하지 않는다")가 그대로
  적중했다.
- 근본 원인은 클래스 불균형이지 cross-fitting 구현 결함이 아니다(재현성
  검증 `INFERENCE_VERIFIED` 통과, 결정론적).
- 프로젝트 기본 정책(`balanced_sample_weight` 기본 사용, PROJECT_CONTEXT
  §3 클래스 불균형·resampling 절)과 달리 이 메타모델은 `class_weight=null`을
  썼다. `class_weight="balanced"`로 재시도하면 붕괴가 해소될 가능성이
  높지만, 예측이 달라지므로 이 EXP-ID를 재사용하지 않고 별도 Experiment
  Issue가 필요하다.

## 다음 실험 후보

- `class_weight="balanced"` L2 Logistic Regression 메타모델을 별도
  Experiment Issue로 재시도(가장 유력한 다음 수).
- 그래도 실패하면 #505가 예정한 다음 후보(depth가 매우 작은
  LightGBM/XGBoost meta, 강한 규제의 작은 MLP)로 넘어간다.
- SAINT·TF-IDF 기반 base 모델(#504/#498)이 준비되면 3+ base로 확장.

## 재현과 관련 파일

- Config: `configs/exp634_cross_fitted_stacking_exp527_exp596.yaml`
- Runner: `scripts/run_exp634_cross_fitted_stacking_exp527_exp596.py`
- Resolved config: `reproducibility/exp634_cross_fitted_stacking_exp527_exp596/config.resolved.yaml`
- Metrics: `reports/exp634_cross_fitted_stacking_exp527_exp596/metrics.json`
- Submission: `submissions/exp634_cross_fitted_stacking_exp527_exp596.csv`(DACON 미제출, ARCHIVE)
- Reproduction status: `INFERENCE_VERIFIED`(저장 checkpoint 추론으로 제출 SHA-256·라벨·확률 완전 일치)
