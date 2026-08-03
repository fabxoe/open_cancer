# EXP-173 Cell Cycle pathway aggregation — B: LoF-in-TSG

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-173 / #173 |
| 목적 | EXP-170(기각) 후속. Cell Cycle TSG 유전자의 truncating LoF가 Feature Spec v1에 도움이 되는지 검증 |
| 핵심 입력 | EXP-094 Feature Spec v1 + `P_lof_in_tsg_cellcycle` (1개 컬럼) |
| 모델 | XGBoost, EXP-094와 동일 하이퍼파라미터 |
| Local OOF Macro F1 | 0.4135108482 (EXP-094 대비 `-0.0033757257`) |
| Public LB | 미제출 |
| 판단 | **기각(NOT ADOPTED)** — Macro F1 하락, LUAD F1 `-0.0236` 최대 하락 |

## 배경

EXP-170(`P_any_nonsilent_cellcycle`)은 기각됐다(Macro F1 -0.0031403572,
DLBC -0.0500857633, LIHC -0.0386). 15개 유전자를 단순 OR로 뭉친 설계가
gene×mutation-type 소속 정보를 재집계하는 패턴에 가까웠기 때문으로 해석했다.
본 실험(B)은 변이의 기능적 성격(TSG에서의 LoF)만 구분해 넣는다는 점에서
다른 종류의 정보를 추가하므로 방향을 유지했다.

**baseline은 EXP-170이 아니라 원본 EXP-094(v1)**다 — EXP-170이 기각됐으므로
"A 결과가 반영된 baseline"은 존재하지 않는다.

## 사전 체크 (구현 전 실제 데이터로 확인)

TSG 6개 유전자(CDKN1A, CDKN1B, CDKN2A, CDKN2B, CDKN2C, RB1)의 truncating
(nonsense+frameshift) 변이 존재 여부를 train.csv 전체로 직접 계산했다.

| 클래스 | n | TSG LoF 양성 | 비율 |
|---|---:|---:|---:|
| DLBC | 38 | 0 | 0.00% |
| LAML | 158 | 0 | 0.00% |
| TGCT | 124 | 0 | 0.00% |
| THYM | 98 | 1 | 1.02% |
| 전체 train | 6201 | 254 | 4.06% |

DLBC/LAML/TGCT는 학습 데이터 전체에서 이 feature가 단 한 번도 양성인 적이
없다. 이 두 클래스(특히 DLBC/LAML은 Issue #173에서 관찰 대상으로 지정)의
F1이 하락한다면, feature가 해당 암종에 잘못된 정보를 인코딩해서가 아니라
(애초에 정보가 없음) `colsample_bytree=0.8` 아래의 weighting perturbation
효과일 수밖에 없다.

## 방법

`P_lof_in_tsg_cellcycle`: Cell Cycle TSG 6개 유전자에서 truncating
(nonsense 또는 frameshift) 변이가 하나라도 있으면 1, missense는 포함하지
않는다. `src/open_cancer/pathway_aggregation_features.py`의
`compute_truncating_flag` / `cell_cycle_lof_in_tsg_family`로 구현했다.
EXP-094 frozen Feature Spec v1(`materialize_frozen_feature_spec`)에 이
컬럼 하나만 추가해 XGBoost 5-fold를 재학습했다.

## 실제 결과 — DLBC/LAML 먼저

사전 체크대로 두 클래스 모두 feature 값이 항상 0이었는데, 결과는 **반대
방향**으로 움직였다.

| 클래스 | Train 양성 비율 | F1 변화 |
|---|---:|---:|
| DLBC | 0.00% | **-0.0137** |
| LAML | 0.00% | **+0.0238** (전체 클래스 중 최고 개선폭) |

값이 항상 0인 두 클래스가 서로 반대 방향으로 움직였다는 것은, "이 pathway가
혈액암에 체계적으로 불리하다"는 가설과 맞지 않고 perturbation 잡음 해석을
뒷받침한다.

## 전체 결과

| 지표 | EXP-094(baseline) | EXP-173 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4168865739 | 0.4135108482 | **-0.0033757257** |
| Fold 표준편차 | 0.0078842521 | 0.0096510379 | +0.0017667858 |
| Log Loss | 1.8399373293 | 1.8393128496 | -0.0006244796 |

- Train/Test positive rate: 4.06% / 2.28%
- 클래스별 최악 하락: **LUAD -0.0235651625** (EXP-170의 DLBC와 달리, 이번엔
  전혀 다른 클래스가 최대 하락). CESC(+0.0159), KIPAN(+0.0115), SKCM(+0.0126)
  등은 개선.

## 승격 기준 대조

| 기준 | 결과 | 통과 |
|---|---:|---|
| Macro F1 +0.001 이상 | -0.0034 | ❌ |
| fold-std 악화 0.002 미만 | +0.0018 | ✅ |
| Log Loss 악화 없음 | -0.0006(개선) | ✅ |
| 전 클래스 F1 악화 없음 | LUAD -0.0236 | ❌ |

Macro F1 gate와 클래스별 F1 gate 모두 실패해 **기각**한다.

## 해석과 한계

- EXP-170과 마찬가지로 fold-std·log loss는 소폭 개선됐지만 Macro F1 하락과
  일부 클래스의 손실을 상쇄하지 못한다.
- 가장 크게 하락한 클래스가 EXP-170(DLBC)과 EXP-173(LUAD)에서 서로 다르다는
  점은, 특정 암종에 대한 체계적 편향이 아니라 매번 다른 무작위적
  weighting perturbation 효과라는 해석과 일관된다.
- TSG 6개로 범위를 좁혔음에도(A의 15개 대비) 여전히 기각됐다는 것은, Cell
  Cycle pathway aggregation 방향 자체가 이 Feature Spec v1 위에서 추가
  신호를 주기 어렵다는 신호일 수 있다.

## 다음 실험 후보

- C(`P_hotspot_in_oncogene_cellcycle`, Table S3 자체 hotspot 3개 유전자
  5개 위치)는 B도 기각된 점을 고려해 진행 여부를 재검토한다. 매우 sparse할
  것으로 예상되어 A/B보다도 신호가 약할 가능성이 높다.
- Cell Cycle pathway aggregation 자체보다 다른 pathway(예: PI3K, WNT — 패널
  커버율이 높고 OG/TSG 균형이 다른 pathway)로 방향을 바꾸는 것을 고려할 수
  있다.

## PR 리뷰 반영 (재학습 없음)

EXP-170의 PR #172 리뷰(resolved config, Feature Factory 등록, 외부 출처
provenance)와 동일한 패턴을 이 실험에도 선제적으로 적용했다. 학습된 모델과
위 OOF·기각 결론은 전혀 바뀌지 않았다 — 새 family가 기존 직접 계산 함수와
완전히 동일한 값을 내는지 합성 데이터와 실제 train/test 전체 데이터로 각각
확인했다(`tests/test_pathway_aggregation_features.py::test_cell_cycle_lof_in_tsg_family_matches_direct_compute_function`).

## Update: Macro-F1-checkpoint 재평가 (POLE 트랙과 함께 완료)

이 실험을 포함한 4개 pathway feature 실험(EXP-170/173/181/226)을 재학습
없이 macro-f1-checkpoint 정책으로 재평가했다. 올바른 비교 대상인
EXP-219(같은 정책의 EXP-094) 기준으로도 이 실험은 `-0.0031`로 기각이
유지된다. DLBC/LAML의 seed 비일관 관찰과 마찬가지로, COAD는 여기서도
`+0.0034`로 여전히 양의 방향이었다(Cell Cycle/POLE 두 gene-set 공통 관찰,
판단 보류). 전체 결과는
[`pole_cellcycle_macro_f1_checkpoint_reevaluation.md`](../analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md)에
정리했다.

## 재현과 관련 파일

- Config: `configs/exp173_cellcycle_lof_tsg.yaml`
- Resolved config: `reproducibility/exp173_cellcycle_lof_tsg/config.resolved.yaml`
- Metrics: `reports/exp173_cellcycle_lof_tsg/metrics.json`
- Verdict 상세: `reports/exp173_cellcycle_lof_tsg/verdict.json`
- Feature 모듈: `src/open_cancer/pathway_aggregation_features.py`
- Knowledge 파일(출처·라이선스·해시): `knowledge/tcga_pancanatlas_table_s3_cell_cycle_v1.json`
- Submission: `submissions/exp173_cellcycle_lof_tsg.csv` (미제출, 로컬 보관)
- Source commit: `0974f0cc4daf3ac3f61c21087c25859397a494de`
- Reproduction status: `NOT_STARTED` (일반 Local 실험, 리더보드 미제출)
