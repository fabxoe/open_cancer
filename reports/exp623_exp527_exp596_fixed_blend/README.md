# EXP-623 EXP-527 XGBoost + EXP-596 RandomForest 고정 0.5/0.5 확률 평균

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-623 / #623 |
| 목적 | #505 스태킹 로드맵 S1(사전 고정 단순 평균) 단계. PR #617에서 다양성 게이트를 통과한 EXP-596 RandomForest를 최고 안전 단일 모델 EXP-527(XGBoost, 26-class 전부 예측)과 블렌드 |
| 방법 | 재학습 없음, `0.5 * EXP-527 확률 + 0.5 * EXP-596 확률` 산술 평균(inference-only, EXP-075/135/253/484/579와 동일 패턴) |
| Local OOF Macro F1 | 0.4617833378 (EXP-527 대비 +0.0149110671) |
| Public LB | 미제출(팀 논의 후 진행) |
| 판단 | OOF Macro F1·Accuracy·Log Loss 모두 개선, 클래스 붕괴(-0.05) 없음. fold std는 사전 임계값(+0.002)을 넘지만 fold 붕괴가 아니라 불균등한 개선폭이 원인 — `ADOPT_WITH_CAUTION` |

## 배경

#505 스태킹 로드맵의 S0(다양성 감사) 단계에서, PR #617이 EXP-596
RandomForest의 오류가 CatBoost·LightGBM과 구조적으로 다르다는 것을 확인했다
(correctness_pearson 0.728, label_disagreement 0.309). 반면 S1 단계에서
가장 먼저 시도했던 EXP-579(EXP-527 XGBoost + EXP-567 LightGBM 0.5/0.5)는
두 boosting 모델의 오류 상관이 높아 블렌드가 두 부모보다 낮은 점수로
ARCHIVE됐다. 이 실험은 "다양성이 실제로 확보된 모델을 블렌드하면 단순
평균도 개선되는가"를 확인하기 위해, EXP-579와 동일한 S1 방식으로 EXP-527과
EXP-596을 블렌드한다.

## 핵심 개념과 방법

새 모델을 학습하지 않는다. EXP-527(XGBoost, parser-v4 class-cosine LOO
feature)과 EXP-596(RandomForest, 동결 Feature Spec v1)의 저장된 OOF·test
확률을 `0.5 * EXP-527 + 0.5 * EXP-596` 산술 평균으로 합치고, 그 argmax를
예측 라벨로 쓴다. 가중치 0.5/0.5는 EXP-579·EXP-135와 동일한 S1 규칙(첫
시도는 균등 가중)을 그대로 따랐고, 평가 전에 고정했다.

EXP-527의 OOF/test 확률은 원 실행자(fabxoe)의 로컬 산출물이라 이번
worktree에는 없었다(`oof/`·`preds/`는 Git 비추적 정책). 실행 전
`scripts/run_exp527_parser_v4_class_cosine_loo.py`를 재실행해 결정론적으로
재생성했고, macro F1 `0.4468722707131544`이 History 기록값(`0.4468722707`)과
일치함을 확인했다. 다만 최근 공용 러너(`run_hotspot_xgb.py`)가 EXP-589
이후 오프 파일에 `SUBCLASS_TRUE_MERGED` 열을 추가로 쓰기 시작해서, 이번에
재생성된 CSV가 History 인터페이스 계약(`ID,SUBCLASS_TRUE,SUBCLASS_PRED,FOLD,
PROBA_*`)과 달랐다. 값은 그대로 두고 그 열만 제거한 로컬 사본을 블렌드
입력으로 사용했다(`blend_probability_frames`가 메타데이터 열 집합을 엄격히
검증하기 때문에 필요한 조치였다).

## 검증 방법

공용 fold(`data/splits/stratified_5fold_seed42.csv`)를 따르는 두 parent의
OOF에서 확률 평균만 계산했으므로 별도 학습·검증 절차는 없다. 두 parent
확률을 다시 읽어 블렌드를 재계산해 제출 CSV SHA-256과 라벨·확률 일치를
확인했다(`INFERENCE_VERIFIED`, 결정론적 계산이라 최대 절대 오차 `1e-6`
이내에서 완전 일치).

## 실제 결과

| 지표 | EXP-623 (블렌드) | EXP-527 (parent) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4617833378 | 0.4468722707 | +0.0149110671 |
| Fold 평균 | 0.4621505222 | 0.4469900880 | +0.0151604342 |
| Fold 표준편차 | 0.0120916724 | 0.0063793185 | +0.0057123539 |
| Accuracy | 0.4450895017 | 0.4339622642 | +0.0111272375 |
| Log Loss | 1.9898206493 | 2.0274887085 | -0.0376680592 |

Fold별 Macro F1(EXP-527 → EXP-623):

| Fold | EXP-527 | EXP-623 | 차이 |
|---:|---:|---:|---:|
| 0 | 0.4343333042 | 0.4537973768 | +0.0194640726 |
| 1 | 0.4506124547 | 0.4560116314 | +0.0053991767 |
| 2 | 0.4487400982 | 0.4835674278 | +0.0348273296 |
| 3 | 0.4500989150 | 0.4670821609 | +0.0169832459 |
| 4 | 0.4511656678 | 0.4502940139 | -0.0008716539 |

**fold 표준편차가 늘어난 원인은 악화가 아니라 불균등한 개선이다.** 5개 fold
중 4개는 뚜렷이 개선했고(fold2는 `+0.0348`까지) 나머지 1개(fold4)는
사실상 동일하다(`-0.00087`). 어떤 fold도 실제로 무너지지 않았다는 점에서,
EXP-151/154/158/179 등에서 봤던 전형적인 fold 붕괴형 fold_std 악화와는
다르며, EXP-484(EXP-374+EXP-459 블렌드)에서 확인했던 것과 같은 패턴이다.

### 클래스별 비교(EXP-527 대비)

큰 개선: DLBC `+0.1144`, LGG `+0.0525`, ACC `+0.0410`, SARC `+0.0295`,
BLCA `+0.0297`, PCPG `+0.0210`, LAML `+0.0223`, CESC `+0.0203`.
큰 하락: COAD `-0.0312`, KIPAN `-0.0253`, SKCM `-0.0200`.

`-0.05` 붕괴 기준을 넘는 클래스는 없다. RandomForest가 트리 bagging 구조상
XGBoost와 다르게 반응하는 소수 클래스(DLBC, LGG, SARC)에서 보완 효과가
컸다.

### 참고자료: 가중치 스윕(비공식, RUN_MODE=explore)

EXP-623 채택 여부와 무관하게, 같은 두 OOF로 가중치를 0.1 단위로 스윕해본
결과는 다음과 같다. **이 표는 실행 파일·EXP-ID·History 공식 기록 없이
로컬에서만 계산한 참고 자료이며, 이 값을 보고 사후에 다른 가중치를
공식으로 채택하지 않는다** — PROJECT_CONTEXT의 "동일 OOF를 반복 탐색해
최적 소수점 가중치를 찾지 않는다" 원칙 때문이다. 다른 가중치를 공식으로
쓰려면 그 값을 사전 고정한 별도 Experiment Issue가 필요하다.

| 가중치(527/596) | OOF Macro F1 | fold std |
|---|---:|---:|
| 1.0/0.0(EXP-527) | 0.4468722707 | 0.006379 |
| 0.8/0.2 | 0.4498244621 | 0.007286 |
| 0.7/0.3 | 0.4556128399 | 0.009528 |
| 0.6/0.4 | 0.4579544097 | 0.010240 |
| 0.5/0.5(EXP-623, 공식) | 0.4617833378 | 0.012092 |
| 0.4/0.6 | 0.4639450817 | 0.008534 |
| 0.3/0.7 | 0.4611393694 | 0.007931 |

0.4/0.6 부근이 이 격자에서는 근소하게 더 높지만, 0.5/0.5(EXP-623)도 이미
채택 기준(최소 개선 `0.001`)을 크게 웃돌아 추가 가중치 탐색 없이도 채택
근거는 충분하다고 판단했다.

## 해석과 한계

- OOF Macro F1·Accuracy·Log Loss가 모두 뚜렷이 개선했고 클래스 붕괴도
  없다. EXP-579(boosting+boosting)가 실패했던 것과 대비하면, 이번 결과는
  "모델을 다양화해도 단순 평균이 개선되지 않는다"는 이전 결론이 오류
  다양성이 실제로 부족했던 조합(EXP-527+EXP-567)에서만 성립했고, 진짜
  다양한 모델(RandomForest)을 쓰면 단순 평균도 개선된다는 것을 보여준다.
- fold 표준편차만 사전 설정 임계값(`+0.002`)을 크게 초과했다(`+0.0057`).
  다만 fold별 분해 결과 4개 fold가 개선하고 1개는 사실상 동일했을 뿐,
  악화된 fold는 없어 EXP-484와 동일한 이유로 `ADOPT_WITH_CAUTION`으로
  기록한다.
- EXP-589(0.4533650721)는 이 실험보다 낮지만 KIRC·LGG를 전혀 예측하지
  않는 24-class 병합 모델이라 직접 비교 대상이 아니다. EXP-623은 26-class를
  전부 예측하면서 EXP-589보다도 높은 첫 Local 후보다.
- Public 제출은 이 보고서만으로 진행하지 않으며, Issue #623·팀 논의를
  거친다.

## 다음 실험 후보

- 팀 논의 후 Public 제출 검토(제출 시 별도 리더보드 제출 이력에 기록).
- 0.4/0.6 등 다른 가중치를 공식으로 확정하고 싶다면, 그 값을 사전 고정한
  별도 Experiment Issue로 진행한다(이 보고서의 스윕 결과를 사후 채택
  근거로 쓰지 않는다).
- EXP-567(LightGBM) 등 다른 다양성 후보가 추가로 확보되면 3-way 이상 블렌드
  또는 cross-fitted meta-model(#505 S2)로 확장한다.

## 재현과 관련 파일

- Config: `configs/exp623_exp527_exp596_fixed_blend.yaml`
- Runner: `scripts/run_exp623_exp527_exp596_fixed_blend.py`
- Resolved config: `reproducibility/exp623_exp527_exp596_fixed_blend/config.resolved.yaml`
- Metrics: `reports/exp623_exp527_exp596_fixed_blend/metrics.json`
- OOF: `oof/exp623_exp527_exp596_fixed_blend.csv`
- Test probability: `preds/exp623_exp527_exp596_fixed_blend_test_proba.csv`
- Submission: `submissions/exp623_exp527_exp596_fixed_blend.csv`(DACON 미제출)
- Reproduction status: `INFERENCE_VERIFIED`(결정론적 블렌드 재계산으로 제출 SHA-256·라벨·확률 일치 확인)
