# EXP-516 burden 기반 sample weight 보강 (저burden 오분류 완화)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-516 / #516 |
| 목적 | EXP-374 OOF 오류 분석에서 확인된 "burden(변이 유전자 수)이 적을수록 오분류가 늘어난다"는 패턴(맞춘 샘플 평균 burden 44.8 vs 틀린 샘플 28.6, 클래스별 burden-recall 상관 +0.38)을 fold-safe 학습 가중치 조정으로 완화할 수 있는지 검증 |
| 핵심 입력 | EXP-374와 동일한 feature set(stop 정규화 mutation type, Ensembl residue-position mask, pathway burden/composition, hotspot 34개) |
| 모델 | XGBoost, EXP-374와 동일한 하이퍼파라미터·checkpoint 정책 |
| 유일한 변경 | fold-train에서 계산한 `sample__mutated_gene_count` 하위 25% quantile 샘플에 `balanced_sample_weight`를 1.5배 추가 곱함 |
| Local OOF Macro F1 | 0.4221650046 (EXP-374 대비 **-0.0046259222**) |
| Public LB | 미제출 |
| 판단 | **ARCHIVE** — 게이트 미달 |

## 원본 데이터와 입력

한 환자는 4,384개 유전자 각각에 대해 `WT`(변이 없음) 또는 변이 표기 문자열을 가진
행 하나로 표현된다. `sample__mutated_gene_count`("burden")는 그 환자의 행에서
`WT`가 아닌 유전자 셀의 개수다 — 변이가 많을수록 모델이 활용할 신호가 많고,
변이가 적을수록(burden이 낮을수록) 정보가 희소해 분류가 어려워진다는 것이
Issue #516의 출발 가설이다.

## 핵심 개념과 피처

- **burden 정의**: `src/open_cancer/mutation_features.py`의
  `sample__mutated_gene_count`와 완전히 같은 정의(공백으로 분리한 토큰 중
  대소문자 무관 `WT`가 아닌 것이 하나라도 있으면 그 유전자 셀은 "mutated")를
  `scripts/run_exp516_burden_weighted_sample_weight.py`의
  `load_train_mutated_gene_count()`가 `data/raw/train.csv`를 직접 streaming
  파싱해 재계산한다. EXP-374가 이미 `mutation_cell_parser`로
  stop-notation-invariant parser를 쓰므로 정의가 완전히 일치한다.
- **fold-safe 가중치 배율**: `scripts/run_hotspot_xgb.py`에 새로 추가한
  `fold_sample_weight_multiplier` 훅이 매 fold마다
  - 그 fold의 **train 행만**으로 burden 하위 25% quantile 경계값을 계산하고
    (validation·test·전체 train은 절대 보지 않음),
  - burden이 그 경계값 이하인 fold-train 샘플에 `1.5`, 나머지는 `1.0`을 곱해
  - 기존 `balanced_sample_weight`(class-frequency 보정)에 원소별로 곱한다.
- 다른 모든 feature, 모델 하이퍼파라미터, checkpoint 선택 정책(`macro_f1_validation`),
  seed, fold는 EXP-374와 완전히 동일하다.

## 모델이 학습하는 정보

모델 입력은 EXP-374와 동일한 sparse feature matrix(mutation presence + mutation
type + residue-position + hotspot + pathway burden/composition), 타깃은 26개
`SUBCLASS`다. 유일한 차이는 `model.fit(..., sample_weight=...)`에 전달하는
가중치 벡터뿐이다. 실제로 적용된 배율은 resolved config의
`fold_sample_weight_multiplier`에 fold별로 기록되며, fold당 약 1,380~1,420개
샘플(train fold 크기의 약 25%)이 1.5배를, 나머지가 1.0배를 받았다.

| fold | 1.5배 적용 샘플 수 | 평균 배율 |
|---:|---:|---:|
| 0 | 1,420 | 1.1431 |
| 1 | 1,401 | 1.1412 |
| 2 | 1,378 | 1.1389 |
| 3 | 1,393 | 1.1404 |
| 4 | 1,408 | 1.1419 |

## 검증 방법

- `data/splits/stratified_5fold_seed42.csv` 공용 5-fold, seed 42.
- `fold_sample_weight_multiplier` 훅은 각 fold의 quantile 경계를 그 fold의
  train 행에서만 계산하므로 validation·test 정보가 학습 가중치에 유입되지 않는다.
- `fold_sample_weight_multiplier=None`(기본값)일 때 `scripts/run_hotspot_xgb.py`의
  동작이 완전히 그대로임을 `uv run pytest -q`(545 passed, 2 skipped)로 확인했다.
- checkpoint는 EXP-374와 동일하게 validation Macro F1 기준으로 선택한다
  (`checkpoint_selection: macro_f1_validation`).

## 실제 결과

| 지표 | EXP-516 | EXP-374 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4221650046 | 0.4267909268 | **-0.0046259222** |
| Fold 평균 | 0.4220899681 | 0.4266436967 | -0.0045537286 |
| Fold 표준편차 | 0.0095450428 | 0.0085032169 | +0.0010418259 |
| Accuracy | 0.4123528463 | 0.4128366393 | -0.0004837930 |
| Log Loss | 1.8675223589 | 1.8440648317 | +0.0234575272 |

Fold Macro F1은 `0.4169086 / 0.4117151 / 0.4155061 / 0.4291216 / 0.4371984`였다
(선택 iteration `75 / 255 / 285 / 118 / 150`).

### 사전 고정 게이트(Issue #516) 판정

| 게이트 조건 | 기준 | 실측 | 통과 여부 |
|---|---|---:|---|
| OOF Macro F1 개선 | ≥ +0.001 | -0.0046259222 | **실패** |
| Fold 표준편차 악화 | < +0.002 | +0.0010418259 | 통과 |
| 클래스별 F1 붕괴 | -0.05 미만 없어야 함 | LUAD -0.0640, DLBC -0.0505 붕괴 | **실패** |
| Log Loss | 크게 악화되지 않아야 함(보조 지표) | +0.0234575 | 보조 참고, 단독 기각 사유 아님 |

주 지표(OOF Macro F1)와 클래스 붕괴 조건 두 가지 모두 게이트를 통과하지 못했다.
사전에 선언한 대로 1.5배는 이번 결과를 본 뒤 조정하지 않았고, 2.0배 등 추가
배율 비교도 수행하지 않았다(단일 공식 후보만 실행).

### 클래스별 변화 (EXP-516 - EXP-374)

가장 크게 하락한 3개 클래스:

| 클래스 | EXP-374 | EXP-516 | 변화 |
|---|---:|---:|---:|
| LUAD | 0.369231 | 0.305195 | **-0.064036** |
| DLBC | 0.464286 | 0.413793 | **-0.050493** |
| BLCA | 0.494253 | 0.444444 | -0.049808 |

가장 크게 개선된 3개 클래스:

| 클래스 | EXP-374 | EXP-516 | 변화 |
|---|---:|---:|---:|
| LIHC | 0.298305 | 0.325260 | +0.026954 |
| CESC | 0.263666 | 0.289389 | +0.025723 |
| KIRC | 0.175953 | 0.197015 | +0.021062 |

### 저burden 클래스 대상 확인 (가설 직접 검증)

Issue #516의 가설은 burden이 낮은 샘플이 많은 클래스일수록 이 가중치 조정으로
이득을 볼 것이라는 것이었다. EXP-374 OOF 오류 분석에서 저burden 오분류가 특히
두드러졌던 8개 클래스(KIRC, KIPAN, GBMLGG, SARC, PRAD, PCPG, THYM, LAML)만 따로
보면:

| 클래스 | EXP-374 F1 | EXP-516 F1 | 변화 | 방향 |
|---|---:|---:|---:|---|
| KIRC | 0.175953 | 0.197015 | +0.021062 | 개선 |
| LAML | 0.541096 | 0.559140 | +0.018044 | 개선 |
| THYM | 0.314685 | 0.326797 | +0.012112 | 개선 |
| KIPAN | 0.221498 | 0.226919 | +0.005420 | 개선 |
| GBMLGG | 0.319783 | 0.313351 | -0.006432 | 악화 |
| PRAD | 0.310984 | 0.309659 | -0.001325 | 악화 |
| PCPG | 0.298755 | 0.296774 | -0.001981 | 악화 |
| SARC | 0.242280 | 0.212471 | -0.029809 | 악화 |

8개 중 4개(KIRC, LAML, THYM, KIPAN)는 개선됐고 4개(GBMLGG, PRAD, PCPG, SARC)는
악화됐다 — 절반은 가설과 일치하지만 절반은 반대 방향이다. 특히 SARC는 이 그룹
안에서 가장 크게 악화됐다(-0.0298). 즉 저burden 표적 가중치가 저burden 클래스
전체를 일관되게 끌어올리지는 못했고, 부분적·혼재된 효과에 그쳤다.

## 해석과 한계

- **전체 지표는 명확히 악화**됐다. Macro F1 -0.0046, Log Loss +0.0235, fold
  표준편차도 소폭 악화됐다.
- **의도한 저burden 효과는 절반만 나타났다.** 표적 8개 클래스 중 4개는 개선,
  4개는 악화로 가설이 부분적으로만 지지된다. burden과 클래스 사이의 관계가
  단순하지 않다는 뜻이다 — 같은 클래스 안에서도 burden이 넓게 분포하고, 클래스
  경계가 burden만으로 설명되지 않는다.
- **가장 크게 무너진 클래스(LUAD -0.064, DLBC -0.050, BLCA -0.050)는 원래
  가설의 표적이 아니었다.** LUAD·BLCA는 TCGA 코호트에서 전형적으로 변이
  burden이 높은 편에 속하는 암종이다. 저burden 샘플의 상대 가중치를 올리면
  그만큼 나머지 샘플(특히 burden이 높은 클래스에 속한 샘플)의 학습 시 상대적
  기여도가 줄어드는 것이 자연스러운 부작용이며, 이 실험에서 그 부작용이
  의도한 개선보다 크게 나타났다. DLBC는 팀 메모에 이미 기록된 대로
  fold별 F1 표준편차가 큰(약 0.04) 소수 클래스라 가중치 재분배에 특히
  민감했을 수 있다.
- **결론**: 단일 고정 배율(1.5x)·단일 quantile(25%)로는 저burden 오분류
  문제를 해결하지 못했고, 오히려 관련 없는 클래스에 부작용을 일으켰다.
  "새 생물학적 feature" 축(Cell Cycle #170/173, POLE #181/226,
  functional_role_burden #257)에 이어 "학습 가중치" 축도 이번 형태로는
  REJECTED다.

## 다음 실험 후보

- burden이 아니라 클래스별 개별 보정(예: 저 recall 클래스에 별도 가중치)을
  검토하되, 이번 실험처럼 무관한 고burden 클래스에 부작용이 없는지 통제 비교.
- quantile 경계나 배율을 낮춰(예: 하위 10%, 1.2x) 부작용을 줄이는 완화된 버전을
  시도할 수 있으나, 이번 결과를 본 뒤 배율을 역조정하는 것이므로 새 Issue에서
  독립적으로 사전 고정해야 한다.
- burden 자체를 가중치가 아니라 모델 입력 feature로 세분화(예: burden
  구간별 interaction feature)하는 방향은 이미 관련 시도들이 REJECTED됐으므로
  우선순위가 낮다.

## 재현과 관련 파일

- Config: `configs/exp516_burden_weighted_sample_weight.yaml`
- Resolved config: `reproducibility/exp516_burden_weighted_sample_weight/config.resolved.yaml`
- Runner: `scripts/run_exp516_burden_weighted_sample_weight.py`
- 공용 훅: `scripts/run_hotspot_xgb.py`의 `fold_sample_weight_multiplier` 파라미터
  (기본값 `None`이면 기존 모든 실험과 byte-for-byte 동일하게 동작; `uv run pytest -q`
  545 passed로 확인)
- Metrics: `reports/exp516_burden_weighted_sample_weight/metrics.json`
- OOF: `oof/exp516_burden_weighted_sample_weight.csv`
- test 확률: `preds/exp516_burden_weighted_sample_weight_test_proba.csv`
- submission: `submissions/exp516_burden_weighted_sample_weight.csv`
- submission SHA-256: `3fcdf0761a834e01049fe2ca298b4cc905be844ca18c9135eaa13d711da4650e`
- Source commit: `17d36559576286705ef8619ab30b1c5454931886`
- Reproduction status: `INFERENCE_VERIFIED`
  (`reproducibility/exp516_burden_weighted_sample_weight/comparison.json`:
  submission SHA-256 일치, test 라벨 일치율 100%, 확률 최대 차이 `1.82e-7`)
- Public LB: 미제출 (게이트 미달로 제출하지 않음)
