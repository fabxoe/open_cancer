# EXP-170 Cell Cycle pathway aggregation — A: any-nonsilent

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-170 / #170 |
| 목적 | #167/#168 gene→pathway 카탈로그를 이용한 첫 pathway-level aggregation feature 검증 |
| 핵심 입력 | EXP-094 Feature Spec v1 + `P_any_nonsilent_cellcycle` (1개 컬럼) |
| 모델 | XGBoost, EXP-094와 동일 하이퍼파라미터 |
| Local OOF Macro F1 | 0.4137462167 (EXP-094 대비 `-0.0031403572`) |
| Public LB | 미제출 |
| 판단 | **기각(NOT ADOPTED)** — Macro F1 하락, DLBC F1 `-0.0501` 급락 |

## 배경

Cell Cycle pathway를 파일럿으로 선택한 이유(카탈로그로 재검증):

- 15개 유전자(CDKN1A, CDKN1B, CDKN2A, CDKN2B, CDKN2C, RB1, CCND1, CCND2,
  CCND3, CCNE1, CDK2, CDK4, CDK6, E2F1, E2F3) 전부 패널에 존재(커버율 100%)
- TP53 pathway 시트(TP53, MDM2, MDM4, ATM, CHEK2, RPS6KA3)와 유전자 중복 없음
- 사전 체크: 이 15개 유전자 중 팀의 기존 34-position hotspot 리스트
  (`EXTENDED_HOTSPOTS`)에 포함된 유전자는 **0개**

## 방법

`P_any_nonsilent_cellcycle`: Cell Cycle 15개 유전자 중 하나라도 nonsilent
변이(missense/nonsense/frameshift/complex, synonymous 제외 — 기존
`classify_mutation_token` 분류 그대로 사용)가 있으면 1, 아니면 0.
`src/open_cancer/pathway_aggregation_features.py::compute_any_nonsilent_flag`로
구현했고, 유전자 목록은 라이선스(CC BY-NC-ND)로 커밋되지 않는
`gene_pathway_mapping.csv` 대신 하드코딩된 리터럴을 사용한다(재현성 확보,
`EXTENDED_HOTSPOTS`와 동일한 관례).

EXP-094 frozen Feature Spec v1(`materialize_frozen_feature_spec`)을 그대로
불러온 뒤 이 컬럼 하나만 hstack해 XGBoost 5-fold를 재학습했다. 모델
하이퍼파라미터와 balanced sample weight, split은 EXP-094와 동일.

## 실제 결과

| 지표 | EXP-094(baseline) | EXP-170(permuted 아님, +feature) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4168865739 | 0.4137462167 | **-0.0031403572** |
| Fold 표준편차 | 0.0078842521 | 0.0092705323 | +0.0013862802 |
| Log Loss | 1.8399373293 | 1.8389285166 | -0.0010088127 |

- Train positive rate(15개 유전자 중 하나라도 nonsilent): 8.51%
- Test positive rate: 10.76%
- 클래스별 F1 변화 중 최악: **DLBC -0.0500857633** (최소 클래스, 38 샘플),
  LIHC -0.0386, OV -0.0153, BLCA -0.0165도 하락. 반대로 CESC +0.0173, LAML
  +0.0227처럼 개선된 클래스도 있어 방향이 일관되지 않음.

## 승격 기준 대조

| 기준 | 결과 | 통과 |
|---|---:|---|
| Macro F1 +0.001 이상 | -0.0031 | ❌ |
| fold-std 악화 0.002 미만 | +0.0014 | ✅ |
| Log Loss 악화 없음 | -0.0010(개선) | ✅ |
| 전 클래스 F1 악화 없음 | DLBC -0.0501 | ❌ |

Macro F1 gate와 클래스별 F1 gate 모두 실패해 **기각**한다.

## 해석과 한계

- fold-std와 log loss는 오히려 소폭 개선됐지만, 이는 우연한 확률 보정 효과로
  보이며 Macro F1 하락과 DLBC 같은 소수 클래스의 큰 손실을 상쇄하지 못한다.
- 8.5%(train)~10.8%(test)라는 낮은 양성률 자체가 문제라기보다, "Cell Cycle
  15개 유전자 중 아무거나 nonsilent"라는 정의가 너무 뭉뚱그려져 있어(OG/TSG
  구분 없음, 변이 유형 구분 없음) 이미 존재하는 gene×mutation-type 개별
  컬럼들이 담고 있는 정보를 단순 OR로 뭉갠 것에 가까울 수 있다. TSG
  truncating(계획된 다음 단계 B)이나 OG hotspot(C)처럼 더 구체적인 정의가
  더 나은 신호일 가능성은 남아있다.
- DLBC(38 샘플)처럼 극소수 클래스에서 큰 변동이 나타난 것은, XGBoost가
  `colsample_bytree=0.8`을 쓰기 때문에 새 컬럼 하나가 다른 컬럼들의 split
  후보 선택 확률을 바꾸는 weighting perturbation 효과일 가능성이 높다
  (EXP-063/078 semantics QC에서 확인된 것과 같은 메커니즘). 즉 이 결과를
  "Cell Cycle 변이가 DLBC 예측에 실제로 해롭다"는 생물학적 신호로 해석하지
  않는다.

## 다음 실험 후보

- Issue #170 계획대로라면 B는 "A 결과가 반영된 baseline" 위에서 진행하기로
  했으나, A가 기각됐으므로 **B는 EXP-094(원본 v1)를 그대로 baseline으로
  사용**해야 한다. 새 Experiment Issue에서 `P_lof_in_tsg_cellcycle`
  (RB1/CDKN1A/CDKN1B/CDKN2A/CDKN2B/CDKN2C truncating)을 별도로 검증한다.
- C(`P_hotspot_in_oncogene_cellcycle`)는 Table S3 자체 hotspot(CCND1
  P287/T286, CDK4 R24/K22, CDK6 L65, 9개 OG 유전자 중 3개만 해당)으로
  재정의가 확정됐다. 매우 sparse할 것으로 예상되므로 B 결과를 본 뒤
  진행 여부를 재판단한다.

## PR #172 리뷰 반영 (재학습 없음)

병합 전 리뷰에서 세 가지를 보완했다. 학습된 모델과 위 OOF·기각 결론은
전혀 바뀌지 않았다 — `pathway__cellcycle_any_nonsilent` 컬럼을 새 Feature
Factory family로 감싼 뒤 실제 train/test 전체 데이터로 기존 직접 계산
함수와 값이 완전히 동일함을 확인했다(`tests/test_pathway_aggregation_features.py`의
`test_cell_cycle_family_matches_direct_compute_function` 및 별도 실행 검증).

1. **resolved config**: `reproducibility/exp170_cellcycle_any_nonsilent/config.resolved.yaml`을
   생성해 실험 identity·데이터/split/base v1 해시·모델 파라미터·환경 정보를
   단일 원본으로 기록했다. `metrics.json`의 `artifacts.resolved_config`에서
   연결된다.
2. **Feature Factory 등록**: 단순 `sparse.hstack` 대신
   `CellCyclePathwayFamily`(`src/open_cancer/pathway_aggregation_features.py`)로
   `FeatureFamilyDescriptor`/`KnowledgeProvenance`를 갖춘 정식 family로
   등록했다. output dimension, feature 이름, fit_scope(`stateless`), 외부
   지식 출처가 이제 `build_family_registry`로 검증 가능하다.
3. **외부 출처 provenance**: 존재하지 않는
   `data/external/gene_pathway_mapping.csv`를 config의 runtime source처럼
   표기하던 부분을 정리했다. 실제 runtime/재현 가능한 출처는 커밋된
   `knowledge/tcga_pancanatlas_table_s3_cell_cycle_v1.json`이며, 이 파일
   자체에 원본 논문 인용·DOI·라이선스·원본 워크북 SHA-256
   (`df722435b7c069b9225c9e4bbef7ab812385bd5e8ab7c415837cde5f2838c640`)이
   기록되어 있다.

## 재현과 관련 파일

- Config: `configs/exp170_cellcycle_any_nonsilent.yaml`
- Resolved config: `reproducibility/exp170_cellcycle_any_nonsilent/config.resolved.yaml`
- Metrics: `reports/exp170_cellcycle_any_nonsilent/metrics.json`
- Verdict 상세: `reports/exp170_cellcycle_any_nonsilent/verdict.json`
- Feature 모듈: `src/open_cancer/pathway_aggregation_features.py`
- Knowledge 파일(출처·라이선스·해시): `knowledge/tcga_pancanatlas_table_s3_cell_cycle_v1.json`
- Submission: `submissions/exp170_cellcycle_any_nonsilent.csv` (미제출, 로컬 보관)
- Source commit: `ab45c0df34eea7ae1b5c3fe686b7245fc22aec6b`
- Reproduction status: `NOT_STARTED` (일반 Local 실험, 리더보드 미제출)
