# Adversarial validation: train/test 분리 가능성

이 진단은 `SUBCLASS`를 전혀 사용하지 않고, 동결 Feature Spec v1 행렬만으로
train 행(도메인 라벨 0)과 test 행(도메인 라벨 1)을 구분하는 이진 분류기를
학습한다. OOF AUC가 0.5에 가까우면 이 feature 표현에서 두 도메인이 구분
불가능하다는 뜻이고, 1.0에 가까우면 강한 분포 차이(batch effect 후보)가
있다는 뜻이다.

**`analysis_only: true`** — 이 디렉토리의 모든 산출물은 QC·원인 분석
전용이며, 공식 Feature Spec·threshold·제출 후보를 정하는 근거로 쓰지 않는다.

## Canonical full-run 결과

전체 Feature Spec v1의 domain OOF AUC는 **`0.7210227160`**이다. fold별
AUC는 `0.72097`, `0.73409`, `0.74242`, `0.74288`, `0.74171`로 모든 fold에서
0.5보다 충분히 높다. 즉 현재 피처 표현에는 train/test를 안정적으로 구분하는
분포 차이가 있다.

| family | 열 수 | standalone AUC | 해당 family 제외 AUC | full - 제외 |
|---|---:|---:|---:|---:|
| raw mutation-presence | 4,384 | 0.714604764 | 0.724203157 | -0.003180441 |
| gene×mutation-type | 21,920 | 0.713944283 | 0.720502376 | +0.000520340 |
| sample aggregate/burden | 12 | **0.729841834** | 0.721342331 | -0.000319615 |
| residue-position | 4,384 | 0.714134209 | 0.727203079 | -0.006180363 |
| fixed hotspot | 35 | 0.553178332 | 0.732660476 | -0.011637760 |

standalone 결과에서 sample aggregate 12개만으로 전체 모델보다 높은 AUC가
나오므로 전역 burden·tokenization 차이가 domain shift의 가장 압축된 설명이다.
raw presence, mutation-type, residue-position도 각각 약 `0.714`로 독립적인
분리 신호를 가진다. 반면 fixed hotspot 단독 AUC `0.553`은 상대적으로 약하다.

leave-one-out 값은 additive feature importance가 아니다. 일부 family를 제외했을
때 AUC가 오르는 현상은 family 간 중복, 고정 XGBoost 용량에서의 feature
competition, 조기 종료 시점 차이로 발생할 수 있다. 특히 residue-position은
단독으로 shift를 강하게 담지만 제외 시 전체 AUC가 `+0.00618` 오르므로,
다른 burden·mutation-type 신호를 조건으로 하면 추가 분리력보다 중복·노이즈가
큰 것으로 해석한다. 이것은 공식 모델에서 residue를 제거하라는 결론이 아니다.

### 상위 shift 피처 분포

gain 상위 50개는 residue-position 33개, sample aggregate 9개, missense 3개,
mutation-presence 3개, nonsense 1개, synonymous 1개로 구성된다.

- `sample__complex_count`: train nonzero `4.05%`, test `40.89%` — 약 `10.10배`
- `sample__multi_variant_gene_count`: train `33.46%`, test `60.21%`
- `sample__nonsense_count`: train `52.67%`, test `26.87%`
- `TCHH__max_residue_position`: train `3.43%`, test `28.83%`
- `CPEB2__max_residue_position`: train `0.61%`, test `14.61%`
- `CPEB2__missense`: train `0.42%`, test `12.06%`

따라서 Local–Public 격차의 1순위 QC 가설은 특정 hotspot이 아니라 전역 변이
부담, complex token 표기, 그리고 그 차이가 개별 유전자 위치·mutation-type
열로 반복 투영되는 batch/domain shift다. 이 진단은 원인을 좁히지만 test 분포를
사용한 재가중·피처 삭제를 허용하지 않는다.

## 산출물

- `metrics.json`: fold별/전체 OOF AUC(전체 Feature Spec v1 기준), feature 수
- `top_shift_features.csv`: gain 기준 train/test를 가장 잘 구분하는 개별 feature
- `family_shift.csv`: 전체 Feature Spec v1 하나의 모델 안에서, family별로
  gain을 합산한 결과(빠른 스크리닝용)
- `family_auc.json`: family별 **standalone AUC**(그 family만 입력으로 사용)와
  **leave-one-family-out AUC**(전체에서 그 family만 제외) — 동일 domain
  split·seed·모델 조건. standalone은 family 자체의 분리력을,
  leave-one-out은 다른 family를 조건으로 한 추가 기여를 보여준다.
- `family_column_mapping.json`: family → 실제 포함된 feature 이름 목록과
  `feature_name_sha256`(감사용)
- `residue_ablation.json`: 전체 Feature Spec v1 AUC vs residue-position 전체
  제외 AUC, fold별 차이, 제외 전후 상위 shift feature 구성 변화
- `top_shift_distributions.csv`: 상위 feature(기본 50개)의 train/test 분포 —
  presence류(mutation-presence/type/hotspot)는 nonzero 수·prevalence·차이,
  continuous류(sample 집계·residue-position)는 min/p25/median/p75/p90/p95/p99/max
- `train_domain_propensity.csv`: 각 train 행의 "test처럼 보이는" OOF 확률과
  `p/(1-p)` 기반 제안 importance weight(99th percentile로 clip) — 참고용으로만
  보존하며 학습 가중치로 재사용하지 않는다.

여기서 사용한 5-fold는 도메인 분류(train vs test)를 위한 별도 stratified
split이며, 공식 `data/splits/stratified_5fold_seed42.csv`(SUBCLASS 계층화)와
다르다. 두 split을 섞어 쓰지 않는다. `gene_mutation_type_indicators` family는
missense/synonymous/nonsense/frameshift/complex 5종만 포함하며, 같은 코드
경로에서 만들어지는 `missing`(결측 지시자) 열은 이 5개 family 밖에 남아
모든 leave-one-out의 "나머지"에는 포함되지만 별도 family로 단독 평가하지
않는다.

## 해석 순서와 제약

1. 이 결과는 진단(QC)이며 그 자체로 Feature Spec, threshold, 제출 후보를
   바꾸는 근거가 아니다. `PROJECT_CONTEXT.md`의 OOD QC 제약을 따른다.
2. `family_auc.json`의 standalone/leave-one-out과 `family_shift.csv`를 함께
   보고, 어느 family가 shift를 지배하는지 확인한 뒤 `reports/analysis/eda_violin`,
   `reports/analysis/tokenization_ood`에서 이미 확인한 burden/complex 계열과
   겹치는지 대조한다.
3. **`train_domain_propensity.csv`(test feature 분포에서 유도한 weight)를
   학습 sample weight로 재사용하지 않는다.** Issue #294에서 이 방식을
   시도했으나 test feature 분포 정보가 학습 전처리에 직접 들어가
   `PROJECT_CONTEXT.md`의 "test/validation 분포 정보를 학습 전처리에 사용하지
   않는다" 계약과 충돌한다는 팀장 검토로 기각됐다(PR #303 참고).
4. `residue_ablation.json`은 residue-position family가 shift에 얼마나
   기여하는지 보여주는 원인 진단이며, 이 결과만으로 공식 모델에서 해당
   family를 제거하지 않는다.
5. 어느 family를 실제로 검증하려면, **test 데이터를 전혀 참조하지 않는**
   train-only ablation(그 family를 Feature Spec에서 제외하고 기존 canonical
   5-fold로 재학습해 OOF·fold-std 변화만 확인)을 새 Experiment Issue에서
   수행한다.
6. `SUBCLASS`와 Public 점수는 이 스크립트의 어떤 단계에서도 사용하지 않았다.
