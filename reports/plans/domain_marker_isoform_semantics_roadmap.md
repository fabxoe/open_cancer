# 고정 암종 표지 패널·isoform 의미 검증 로드맵

> 이 문서는 계획과 진행 상태를 관리합니다. 실제 점수의 원본은
> `EXPERIMENT_HISTORY.md`와 실험별 `metrics.json`입니다. 실행하지 않은 결과나
> 예상 점수는 기록하지 않습니다.

## 1. 목적과 핵심 질문

현재 입력은 환자별 4,384개 유전자 열에 적힌 단백질 변이 문자열입니다. 이
로드맵은 서로 독립적인 두 가설을 검증합니다.

1. **Track A — 고정 암종 표지 패널:** 공개된 일반 암종 표지 유전자 지식을
   작은 범주형·이진 피처로 요약하면 원본 유전자 피처만 사용할 때보다 암종
   구분에 도움이 되는가?
2. **Track B — isoform 의미 검증:** 변이 문자열의 잔기 위치와 reference
   amino acid가 MANE Select, canonical 또는 다른 알려진 protein isoform 중
   어디에 맞는지를 구분하면 위치 피처의 의미와 신뢰도를 개선할 수 있는가?

두 트랙은 각각 별도 Issue·EXP로 평가합니다. 두 트랙이 독립적으로 채택 기준을
통과한 경우에만 조합 실험을 엽니다. 한 트랙의 결과를 보고 다른 트랙의 정의나
임계값을 바꾸지 않습니다.

## 2. 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | OOF Macro F1 | 판단 | 다음 행동 |
|---|---|---:|---|---:|---|---:|---|---|
| A0 | 출처·관찰 가능성 계약 고정 | #299 | 해당 없음 | 미발급 | COMPLETED | N/A | panel에 KRAS·NRAS·MSH6 없음 | 교집합 고정 |
| A1 | 고정 표지 패널 피처 구현 | #299 | 해당 없음 | #301 | COMPLETED | N/A | 20개 후보 구현·테스트 | A3 완료 |
| A2 | Feature Spec v1/EXP-229 대비 의미 중복 감사 | #299 | explore | #301 | COMPLETED | N/A | FGFR3 any·single-panel multi 중복/상수 확인 | fold-local mask 적용 |
| A3 | 고정 표지 패널 canonical 5-fold | #302 | EXP-302 | #305 | REJECTED | 0.4212799841 | EXP-229 대비 -0.0017085904 | [보고서](../exp302_observable_marker_proxies/README.md), Track A 종료 |
| B0 | Ensembl annotation snapshot·허용 범위 확인 | #307 | 해당 없음 | #308 | COMPLETED | N/A | release 116 동결·외부 annotation 허용 미확인 | [manifest](../../knowledge/ensembl_isoform_annotation_v1.json) |
| B1 | isoform token 의미 QC | #307 | explore | #308 | COMPLETED | N/A | coverage 충분·train/test 의미 분포 큰 차이 | [보고서](../analysis/isoform_residue_semantics/README.md) |
| B2-1 | 불확실 residue-position mask | #311(구현) | 미발급 | 미발급 | IN_PROGRESS | N/A | 팀장 예외 허용·정적 Ensembl 116 mask만 구현 | 구현 병합 후 Experiment Issue 발급 |
| B2-2 | sample 범주 요약 | 미발급 | 미발급 | 미발급 | BLOCKED | N/A | #311 예외 범위 밖 | 별도 범위 검토 |
| B2-3 | isoform-relative coarse bin | 미발급 | 미발급 | 미발급 | BLOCKED | N/A | #311 예외 범위 밖 | 별도 범위 검토 |
| C | Track A+B 조건부 조합 | 미발급 | 미발급 | 미발급 | REJECTED | N/A | Track A gate 실패 | 조합 실험을 열지 않음 |

작업 상태는 다음 값만 사용합니다.

```text
PLANNED -> IN_PROGRESS -> PR_OPEN -> MERGED -> COMPLETED
                                      \-> BLOCKED
                                      \-> REJECTED
```

이는 `INFERENCE_VERIFIED`, `TRAINING_VERIFIED` 같은 재현 상태와 별개입니다.

## 3. 공통 누출 방지·해석 계약

- 외부 유전자 목록과 규칙은 실행 전에 파일·버전·출처·SHA-256으로 동결합니다.
- `SUBCLASS`, Public LB, test 분포는 패널 구성, isoform 선택, 임계값 결정에
  사용하지 않습니다.
- 외부 지식은 모든 환자에게 동일한 변환으로 적용합니다. 정답 암종을 이용한
  cancer-specific gating은 금지합니다.
- validation과 test는 outer-train에서 학습된 변환만 적용합니다. Track A v1은
  학습이 없는 `stateless` 변환입니다.
- 현재 데이터에는 fusion, copy-number/amplification, 발현, IHC, MSI assay,
  germline/somatic 구분, transcript ID가 없습니다. 따라서 그러한 임상 사건을
  관찰했다고 표현하지 않습니다.
- feature 이름과 보고서에는 반드시 `proxy` 또는 `observed_tumor_variant`를
  사용합니다. 치료 적응증, 유전성 위험, 진단을 예측한다고 주장하지 않습니다.
- 공식 평가는 canonical 5-fold OOF Macro F1입니다. Log Loss는 확률 품질을
  확인하는 보조 지표입니다.

## 4. Track A — 고정 관찰 가능 표지 패널

### A0. 출처와 관찰 가능성 고정

`knowledge/fixed_observable_cancer_markers_v1.json`에 다음을 저장합니다.

- 지식 파일 버전과 작성일
- 권위 출처 URL과 문헌상 의미
- 포함 panel과 유전자
- 현재 CSV에서 직접 계산하는 사건
- 계산할 수 없어 제외한 임상 사건
- 해석 한계와 라이선스·사용 조건
- 정확한 파일 SHA-256은 Feature Registry에서 자동 기록

초기 panel은 캡처에 나온 내용 중 단백질 변이 문자열로 최소한의 proxy를 만들 수
있는 부분만 사용합니다.

| panel | 포함 유전자 | 계산하는 것 | 계산하지 않는 것 |
|---|---|---|---|
| lung point-mutation proxy | `EGFR`, `KRAS`, `BRAF` | 관찰된 단백질 변이 유형 | `ALK`·`ROS1`·`NTRK` fusion |
| breast tumor-variant proxy | `BRCA1`, `BRCA2`, `ERBB2`, `PIK3CA` | 관찰된 tumor variant | HER2 amplification/IHC, germline status |
| colorectal tumor-variant proxy | `KRAS`, `NRAS`, `BRAF`, `MLH1`, `MSH2`, `MSH6`, `PMS2` | RAS/BRAF/MMR-gene 변이 proxy | MSI-H 또는 dMMR 판정 |
| ovarian BRCA variant proxy | `BRCA1`, `BRCA2` | BRCA 변이 proxy | 유전성 위험·PARP 적응증 판정 |
| bladder FGFR3 variant proxy | `FGFR3` | FGFR3 단백질 변이 proxy | FGFR fusion·과발현 |

캡처의 유전성 암 목록(`NF1`, `NF2`, `VHL`, `MEN1`, `RET`, `TP53` 등)은
germline 상태와 임상 phenotype이 없으므로 v1 모델 피처에서 제외합니다. 별도
고정 somatic mechanism 가설로 재정의할 근거가 생길 때 새 Issue에서 다룹니다.

### A1. 피처 정의

각 panel마다 다음 네 개의 작은 이진 피처를 만듭니다.

```text
any_mutated
any_nonsynonymous
any_lof
multi_gene_mutated
```

- `any_mutated`: panel 유전자 중 하나라도 WT/빈값이 아닌 변이가 있음
- `any_nonsynonymous`: missense, nonsense, frameshift 또는 complex가 하나라도 있음
- `any_lof`: nonsense 또는 frameshift가 하나라도 있음
- `multi_gene_mutated`: 서로 다른 panel 유전자가 둘 이상 변이됨

유전자별 임상 가중치, 암 발생 확률, 치료 evidence level, 외부 환자 빈도는
사용하지 않습니다. panel별 출력 차원은 4개, v1 총 후보는 20개입니다.

### A2. 의미 중복 감사와 중단 조건

공식 학습 전에 fold-train 행에서 EXP-229 base feature와 정확히 같은 후보 열을
제거합니다. 특히 단일 유전자 FGFR3 panel은 기존 `gene__*` 열과 동일할 수
있습니다.

- 후보 20개가 모두 기존 열과 동일하면 A3를 `REJECTED`하고 학습하지 않습니다.
- 고유 후보가 남더라도 상수 열이나 train nonzero 표본이 5개 미만인 열은
  제거하고 사유를 JSON에 기록합니다.
- 제거 후 panel의 임상 이름을 근거로 다시 피처를 추가하지 않습니다.
- audit 산출물에는 후보 이름, 대응 base 피처, prevalence, 유지 여부와 최종
  feature-name hash를 저장합니다.

### A3. 공식 5-fold 실험

새 Experiment Issue 번호에서 EXP-ID를 파생합니다. 부모는 현재 채택 XGBoost
축인 EXP-229로 고정하고 다음만 바꿉니다.

```text
EXP-229 frozen features
+ A2에서 유지된 fixed observable marker proxy features
```

고정 항목:

- canonical stratified 5-fold, seed 42
- balanced sample weight
- validation Macro-F1 checkpoint selection
- XGBoost hyperparameters와 클래스 순서
- test·Public 미사용

채택 기준:

- EXP-229 대비 OOF Macro F1 `+0.001` 이상
- fold 표준편차 악화 `<0.002`
- Log Loss의 명백한 악화 없음
- 어떤 충분한 표본의 클래스도 F1 `-0.05` 이상 붕괴하지 않음
- checkpoint inference 검증 통과

Macro F1 개선은 없지만 오류 상관이 낮은 경우에는 feature spec으로 채택하지 않고
독립 앙상블 후보로만 보존합니다. 기준 미달이면 `ARCHIVE`하고 panel 정의를
Public 결과에 맞춰 반복 조정하지 않습니다.

## 5. Track B — isoform·residue 의미 검증

### B0. 정적 annotation 계약

Ensembl의 고정 release에서 다음 정보를 내려받아 source URL, release, retrieval
date, 라이선스와 SHA-256을 기록합니다.

- MANE Select transcript와 protein sequence
- Ensembl canonical transcript와 protein sequence
- 알려진 모든 protein-coding isoform sequence
- gene symbol/Ensembl gene/transcript/protein 매핑

transcript ID가 입력에 없으므로 특정 isoform을 정답으로 단정하지 않습니다.
annotation은 target-independent 의미 QC와 신뢰도 범주 생성에만 씁니다. 대회
규정상 외부 annotation 사용이 불명확하면 B1까지만 분석하고 B2 공식 실험 전에
주최측 확인을 받습니다.

### B1. token 의미 QC

simple amino-acid token의 위치와 reference amino acid를 각 sequence에 대조해
다음 범주를 상호 배타적으로 부여합니다.

```text
MANE_MATCH
CANONICAL_MATCH
OTHER_ISOFORM_MATCH
POSITION_VALID_REF_MISMATCH
OUTSIDE_ALL_KNOWN_ISOFORMS
COMPLEX_OR_UNMAPPABLE
```

먼저 모델을 학습하지 않고 train/test에서 다음만 보고합니다.

- gene·sample·token별 범주 비율
- canonical 길이를 넘지만 다른 isoform에는 맞는 token 비율
- position은 유효하나 reference amino acid가 맞지 않는 비율
- pseudogene·lncRNA·non-protein-coding gene의 변이 표기
- 현재 max residue-position 피처 중 신뢰도 낮은 값의 비율
- train/test 범주 분포 차이

클래스별 분석은 train에서만 설명용으로 할 수 있지만 규칙이나 범주 정의를
변경하는 데 사용하지 않습니다.

### B2. 독립 ablation

B1과 주최측 허용 범위를 통과하면 다음을 각각 별도 EXP로 실행합니다.

1. 불확실 위치값 mask: `POSITION_VALID_REF_MISMATCH`,
   `OUTSIDE_ALL_KNOWN_ISOFORMS`, `COMPLEX_OR_UNMAPPABLE` 위치를 결측으로 취급
2. 범주형 신뢰도 요약: sample별 여섯 범주의 count/any indicator
3. isoform-relative coarse bin: 일치 가능한 sequence 길이에 대한 상대 위치 bin

세 변형을 한 번에 섞지 않습니다. 각 실험은 EXP-229 또는 당시 동결된 동일
부모를 사용하며 Track A 결과와 독립적으로 판정합니다. 채택 기준은 A3와
동일합니다.

## 6. 조건부 조합과 방향성 판정

| Track A | Track B | 결론 |
|---|---|---|
| 채택 | 채택 | 독립 신호 가능성이 있으므로 A+B 조합 EXP 1회 실행 |
| 채택 | 기각 | 고정 marker proxy만 채택, isoform은 QC 자료로 보존 |
| 기각 | 채택 | isoform 의미 개선만 채택, marker panel 반복 탐색 중단 |
| 기각 | 기각 | 두 방향 모두 archive, 모델 다양성·앙상블 축으로 복귀 |

조합은 두 트랙의 동결 피처를 그대로 합치며 재튜닝하지 않습니다. 조합 채택
기준도 최고 단일 부모 대비 `+0.001`, fold 표준편차 악화 `<0.002`입니다.
두 트랙이 모두 실패해도 도메인 지식 전체가 무효라는 뜻은 아니며, 현재 입력에
대한 이 두 구체적 표현이 유효하지 않았다는 결론만 내립니다.

## 7. 산출물·재현성 계약

Task 단계:

```text
knowledge/fixed_observable_cancer_markers_v1.json
src/open_cancer/observable_marker_features.py
tests/test_observable_marker_features.py
reports/analysis/observable_marker_semantic_audit/
```

공식 실험 단계:

```text
configs/expNNN_<slug>.yaml
scripts/run_expNNN_<slug>.py
reports/expNNN_<slug>/README.md
reports/expNNN_<slug>/metrics.json
oof/expNNN_<slug>.csv
preds/expNNN_<slug>_test_proba.csv
reproducibility/expNNN_<slug>/
```

resolved config, feature registry, knowledge SHA-256, 의미 중복 제거 결과,
fold별 checkpoint, OOF/test 확률을 저장합니다. 리더보드 제출 후보는 최소
`INFERENCE_VERIFIED`, 최종 후보는 다른 팀원의 `TRAINING_VERIFIED`를 목표로
합니다.

## 8. 결정 변경 이력

| 날짜 | 결정 | 근거 |
|---|---|---|
| 2026-08-04 | Track A를 Track B보다 먼저 실행 | 현재 CSV에서 직접 관찰 가능한 작은 고정 패널을 먼저 검증하라는 팀장 결정 |
| 2026-08-04 | fusion·amplification·MSI·germline 주장을 제외 | 입력에 해당 assay·event type·transcript 정보가 없음 |
| 2026-08-04 | 두 트랙 독립 통과 후에만 조합 | 한 결과로 다른 가설을 조정하는 OOF 과적합 방지 |
| 2026-08-04 | KRAS·NRAS·MSH6 누락을 명시하고 실제 panel 교집합만 사용 | 실제 4,384개 train 열 target-independent 감사 |
| 2026-08-04 | Track B B0/B1 완료, B2는 BLOCKED | Ensembl 116 coverage는 충분하나 MANE 일치율이 train 88.50%·test 53.46%로 크게 다르고 외부 annotation 허용 미확인 |
| 2026-08-04 | Task #311과 첫 B2 불확실 위치 mask에 외부 annotation 예외 허용 | 팀장 명시 지시; 고정 Ensembl 116의 정적 sequence 일치 범주만 허용, 외부 환자 데이터·암종 빈도·test 기반 조정은 계속 금지 |
