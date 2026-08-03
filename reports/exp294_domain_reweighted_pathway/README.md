# EXP-294 EXP-223 pathway 모델의 domain propensity 재가중 재학습

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-294 / #294 |
| 목적 | Issue #292 adversarial validation이 확인한 train/test 분포 차이가, 여러 실험에서 반복 관측된 약 0.10의 Local-Public Macro F1 격차의 원인 중 하나인지 검증 |
| 핵심 입력 | EXP-223과 동일한 동결 Feature Spec v1 + 고정 pathway burden 20열 |
| 모델 | XGBoost (EXP-223과 동일 파라미터·macro-f1 checkpoint 선택 정책) |
| Local OOF Macro F1 | 0.4255217902 (EXP-223 대비 +0.0041478426, 현재 Local 최고) |
| Public LB | 미제출(팀 제출 예산 협의 후 진행) |
| 판단 | Local 채택 후보 — Public 검증 전까지 최종 판단 보류 |

## 원본 데이터와 입력

train/test 입력과 유전자 변이 인코딩은 EXP-223(`reports/exp223_pathway_macro_f1_checkpoint/README.md`)과 동일하다. 이 실험이 바꾼 것은 피처가 아니라, 각 fold-train 행을 XGBoost에 얼마나 "중요하게" 반영할지를 정하는 sample weight뿐이다.

## 핵심 개념과 피처

Issue #292는 `SUBCLASS`를 전혀 쓰지 않고, train 행(도메인 라벨 0)과 test 행(도메인 라벨 1)을 구분하는 별도의 이진 분류기를 동결 Feature Spec v1 행렬로 학습했다. 결과:

- 전체 OOF AUC 0.7210 — train과 test가 이 피처 표현에서 상당히 구분 가능함을 확인(완전히 같지도, 완전히 다르지도 않음)
- 가장 크게 기여한 feature는 `sample__complex_count`(2위 대비 gain 4배), 그다음이 `mutated_gene_count`/`total_variant_count`/`missense_count`/`nonsense_count` 등 burden 집계 — `reports/analysis/eda_violin`, `reports/analysis/tokenization_ood`가 이미 지목한 batch-effect 후보와 정확히 겹침

이 진단에서 각 train 행에 대해 "test처럼 보이는 정도"를 OOF 확률로 얻었고, `p/(1-p)`로 변환한 뒤 99th percentile로 clip한 값을 `train_domain_propensity.csv`에 저장했다(자세한 내용은 `reports/analysis/adversarial_validation/README.md`).

## 모델이 학습하는 정보

EXP-294는 EXP-223의 fold-train sample weight 계산에서 딱 한 줄만 바꿨다.

```
sample_weight = balanced_class_weight(y_train) * domain_propensity_weight(train_rows)
```

`domain_propensity_weight`는 전체 train 평균이 1.0이 되도록 재정규화했다 — "test와 비슷한 행에 더 집중한다"는 방향만 살리고, 학습 신호의 전체 크기(총 가중치 합)는 EXP-223과 같게 유지하기 위해서다. 피처, 모델 하이퍼파라미터, checkpoint 선택 정책(validation Macro-F1-best), seed, 공용 5-fold는 전부 EXP-223과 동일하다.

## 검증 방법

`data/splits/stratified_5fold_seed42.csv` 공용 5-fold를 그대로 사용했다. `train_domain_propensity.csv`는 `SUBCLASS`나 test 라벨을 전혀 쓰지 않고 train/test 피처 분포만 비교해 계산했으므로, 이 재가중 자체가 test 타깃 정보를 학습에 누출시키지는 않는다. 다만 이 판단(test 피처 분포 정보를 학습 전처리에 쓰는 것이 프로젝트의 "test 분포로 전처리 금지" 원칙과 충돌하지 않는지)은 이번 실험 자체가 검증 대상이며, Issue #292/#294에 그 취지를 명시했다.

## 실제 결과

Fold Macro F1: 0.4147483429 / 0.4332525456 / 0.4201834703 / 0.4229755514 / 0.4388678683

| 지표 | EXP-223 (baseline) | EXP-294 (domain reweighted) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4213739476 | 0.4255217902 | +0.0041478 |
| Fold 표준편차 | 0.0092340053 | 0.0088063658 | 개선 |
| Accuracy | - | 0.4167069827 | - |
| Log Loss | 1.8441621065 | 1.9123604298 | 악화(+0.0682, gate 아님) |
| 최저 클래스 F1 | - | 0.2105263158 (KIPAN) | 붕괴 없음 |

Issue #294에 사전 등록한 두 판단 기준(①Macro F1 `0.004` 이내 하락 ②fold 표준편차 크게 악화 없음)을 모두 통과했고, 실제로는 하락이 아니라 개선이었다. 특정 클래스가 붕괴하면서 평균만 오른 형태가 아니라 대체로 고르게 개선된 패턴이다.

## 해석과 한계

- 이 OOF는 여전히 train 분포 내부의 validation fold로 계산한 값이다. domain reweighting이 "test와 비슷한 행"에 더 집중하게 만들었는데도 OOF가 개선된 것은 정규화 효과(다수인 저정보 WT-heavy 행의 과도한 영향을 줄임)일 수도 있고, 실제 분포 적응 효과일 수도 있다 — 이 실험만으로는 구분할 수 없다.
- Log Loss가 눈에 띄게 악화됐다(+0.068). 프로젝트 기준상 단독 기각 사유는 아니지만, 확률 보정 품질이 나빠졌을 가능성은 남겨둔다.
- **가장 중요한 한계**: 이 실험의 진짜 목적(약 0.10의 Local-Public 격차가 실제로 좁혀지는지)은 Public 제출로만 확인할 수 있다. 로컬 결과만으로 "성공"이라 결론 내리지 않는다.

## 다음 실험 후보

- 리더보드 제출 예산에 여유가 생기면 이 checkpoint를 제출해 EXP-223과 Public 점수를 직접 비교
- Public에서도 격차가 좁혀진다면, 같은 재가중을 다른 채택 후보(EXP-096, EXP-229 등)에도 적용해 일반화되는지 확인
- Log Loss 악화 원인을 propensity weight 분포(클리핑 범위, 정규화 방식)를 바꿔가며 분리 검증

## 재현과 관련 파일

- Config: `configs/exp294_domain_reweighted_pathway.yaml`
- Resolved config: `reproducibility/exp294_domain_reweighted_pathway/config.resolved.yaml`
- Metrics: `reports/exp294_domain_reweighted_pathway/metrics.json`
- Submission: `submissions/exp294_domain_reweighted_pathway.csv` (미제출 상태로 보관)
- Source commit: `2fd2aa34551ffa77f3668b2b0a738ca914af7fad`
- Reproduction status: `INFERENCE_VERIFIED` (제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.45e-07 — `reproducibility/exp294_domain_reweighted_pathway/comparison.json`)
