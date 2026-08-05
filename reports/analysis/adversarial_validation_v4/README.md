# Adversarial validation: train/test 분리 가능성 (parser v4 재계산, #421)

> **원본 #292 재계산본**입니다. `reports/analysis/adversarial_validation/`(v1
> Feature Spec 기준)과 달리, 이 디렉토리는 EXP-392 parser(stop-notation-
> invariant v2 + Ensembl isoform mask)로 다시 만든 feature 행렬을 쓴다.
> `FAMILY_RULES`에 `range_stop`/`range_no_change`(#392) 2개 family를
> 추가했다. 결론은 `family_auc.json`과 Issue #421 코멘트 참고.

이 진단은 `SUBCLASS`를 전혀 사용하지 않고, 동결 Feature Spec v1 행렬만으로
train 행(도메인 라벨 0)과 test 행(도메인 라벨 1)을 구분하는 이진 분류기를
학습한다. OOF AUC가 0.5에 가까우면 이 feature 표현에서 두 도메인이 구분
불가능하다는 뜻이고, 1.0에 가까우면 강한 분포 차이(batch effect 후보)가
있다는 뜻이다.

**`analysis_only: true`** — 이 디렉토리의 모든 산출물은 QC·원인 분석
전용이며, 공식 Feature Spec·threshold·제출 후보를 정하는 근거로 쓰지 않는다.

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
