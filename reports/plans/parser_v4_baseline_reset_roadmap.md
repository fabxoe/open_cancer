# Full parser v4 기반 모델 기준선 재정립 로드맵

> 상위 Roadmap Issue: [#417](https://github.com/fabxoe/open_cancer/issues/417)
>
> 이 문서는 현재 프로젝트의 최우선 모델 개발 계획이다. 실제 실행 점수의 원본은
> `EXPERIMENT_HISTORY.md`와 실험별 `metrics.json`이며, 실행 전 예상 점수나
> 가상 결과를 기록하지 않는다.

## 1. 배경과 문제 정의

parser v4 이전에 생성된 고득점·Optuna·isoform·driver 계보는 당시의 parser와
피처 표현을 정확히 재현한다. 따라서 과거 결과는 삭제하거나 잘못된 실험으로
소급 변경하지 않는다. 그러나 이 결과를 full parser v4 기준 모델의 성능으로
해석할 수도 없다.

코드 감사에서 다음이 확인됐다.

- parser v4 contract는 `notation 4.0.0 / semantic router 4.0.0 /
  feature adapter 4.0.0-opt-in`이며 기존 Feature Spec에 자동 적용되지 않는다.
- EXP-285 Optuna는 구형 EXP-229 피처 공간에서 파라미터를 탐색했다.
- EXP-334는 구형 Feature Spec, EXP-285 fold 파라미터와 isoform mask를 조합했다.
- EXP-369·374·392의 핵심 mutation/pathway/hotspot 경로는 full v4가 아니라
  `stop_notation_invariant_v2`를 사용한다.
- parser v4 기반 driver·isoform 작업은 의미 감사와 일부 opt-in adapter였으며,
  전체 모델 입력 경로가 v4로 교체된 공식 모델은 아직 없다.
- `X = * = Ter` 정규화만 적용한 EXP-369가 OOF 동일 통제에서 Public을 크게
  개선했다. 이는 parser 표기·의미 오류가 실제 전이 병목이었다는 강한 근거다.

따라서 현재 최고 모델을 계속 증축하지 않고, **full parser v4만의 효과가 분리된
새 기준선**을 먼저 만든다.

## 2. 목표

1. stop-v2와 full parser-v4를 같은 코드·환경·피처 차원·모델 조건에서 비교한다.
2. 모든 모델 입력 경로가 동일한 parser contract와 canonical event를 사용하도록
   강제한다.
3. parser correctness와 모델 feature representation의 성능 채택을 분리한다.
4. v4 Parser Baseline v1을 동결한 뒤 isoform·driver·pathway·Optuna를 순차적으로
   다시 검증한다.
5. 과거 실험은 parser lineage가 명시된 legacy evidence로 계속 보존한다.

## 3. 비범위

- 기존 실험 ID·점수·resolved config를 수정하지 않는다.
- pure parser A/B에 isoform mask, driver 피처, 새 pathway, Optuna 파라미터,
  앙상블 또는 후처리를 섞지 않는다.
- test prevalence, adversarial AUC 또는 Public LB로 parser 규칙과 의미 mapping을
  선택하지 않는다.
- transcript·DNA/RNA 원자료가 없을 때 불완전 표기를 HGVS로 억지 복원하지 않는다.
- parser가 생물학적으로 올바르다는 이유만으로 모든 v4-native 피처를 한 번에
  모델에 넣지 않는다.

## 4. 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | OOF Macro F1 | 판단 | 다음 행동 |
|---|---|---:|---|---:|---|---:|---|---|
| R0 | 최상위 로드맵·운영 계약 | #417 | 해당 없음 | #418 | PR_OPEN | N/A | 계획·운영 계약 작성 완료 | PR 병합 |
| R1 | v4 compatibility projection·경로 일관성 validator | 미발급 | 해당 없음 | 미발급 | PLANNED | N/A | - | R0 병합 대기 |
| R2 | 현재 환경 stop-v2 paired control 재실행 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R1 병합 대기 |
| R3 | full parser-v4 compatibility treatment | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R2 완료 대기 |
| R4 | paired diff 감사·Parser Baseline v1 동결 | 미발급 | explore | 미발급 | PLANNED | N/A | - | R2·R3 완료 대기 |
| R5 | v4-native semantic representation 실험 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R4 완료 대기 |
| R6 | v4 기준 isoform mask 독립 재검증 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R4 완료 대기 |
| R7 | v4 기준 driver representation 독립 재검증 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R4 완료 대기 |
| R8 | pathway·hotspot 재검증과 Feature Spec 동결 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R5~R7 결과 판단 |
| R9 | 새 Feature Spec nested Optuna | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R8 동결 대기 |
| R10 | 모델 다양화·앙상블·최종 재현 검증 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | R9 완료 대기 |

작업 상태는 다음 값만 사용한다.

```text
PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED
                                     ↘ BLOCKED
                                     ↘ REJECTED
```

이는 `INFERENCE_VERIFIED`, `TRAINING_VERIFIED` 같은 재현 상태와 구분한다.

## 5. R1 — parser v4 compatibility projection

### 목적

full parser v4가 만든 canonical event를 기존 고정 피처 스키마에 투영한다. 피처
수를 늘리지 않고 parser만 교체할 수 있어야 R2/R3가 순수 A/B가 된다.

### 고정 출력 스키마

기존 control과 동일한 다음 축을 유지한다.

- 유전자 mutation presence
- 유전자별 `missense / synonymous / nonsense / frameshift / complex`
- sample mutation-type·burden aggregate
- pathway mutation-type composition
- hotspot match
- residue-position lexical aggregate
- missing indicator

v4의 deletion·insertion·duplication·delins·range 같은 세부 사건은 이 단계에서
새 열로 추가하지 않고, 사전 고정 compatibility mapping을 통해 기존 5개 범주에
투영한다. v4-native 세부 피처는 R5에서 별도로 검증한다.

### 전체 입력 경로 일관성

다음 소비자가 같은 `RoutedProteinMutation`을 사용해야 한다.

1. core gene×mutation-type
2. sample aggregate
3. pathway burden·mutation-type
4. hotspot normalization·matching
5. residue-position eligibility·position extraction
6. parser QC·manifest

한 경로라도 legacy regex를 직접 호출하면 validator가 실패해야 한다. token은 한 번
route하고 canonical event를 여러 소비자가 재사용한다. raw token은 provenance로
항상 보존한다.

### compatibility mapping 계약

- substitution missense → `missense`
- substitution no-change → `synonymous`
- immediate stop / nonsense → `nonsense`
- frameshift → `frameshift`
- deletion·insertion·duplication·delins·ordinary range → `complex`
- range immediate/later stop → `nonsense` 또는 사전 명시된 truncating mapping
- 불완전·비표준·근거 부족 → `complex`와 `unresolved=true`, raw 보존
- `X`, `*`, `Ter` stop은 동일 canonical event
- `X/Xaa`가 unknown amino acid인 문맥과 stop 기호 문맥을 구분
- signed partial, bilateral stop, compact frameshift는 근거 이상으로 추정하지 않음

정확한 range truncation mapping은 구현 전 fixture와 현재 v4 semantic payload를
기준으로 문서·테스트에 고정하며 실행 결과를 보고 변경하지 않는다.

### 테스트

- 실제 fixture catalog 전수 route·snapshot
- 표기 불변성: `X/*/Ter`, 대소문자, 공백 등 허용된 동치 표기
- substitution·frameshift·deletion·insertion·duplication·delins·range·unresolved
- 동일 token의 모든 소비자 canonical event hash 일치
- train/test 독립 변환과 target 미사용
- mutation presence 완전 보존
- control과 treatment feature 이름·차원·순서 일치
- parser 변경 대상이 아닌 token의 feature vector byte-level 일치
- resolved config에 parser·projection·fixture hash 저장

## 6. R2/R3 — 순수 paired parser A/B

### 공통 조건

두 실험은 같은 main commit 계열과 환경에서 연속 실행한다.

| 항목 | Control R2 | Treatment R3 |
|---|---|---|
| 기준 계보 | EXP-369 구조 | 동일 |
| parser | stop-v2 | full parser-v4 compatibility projection |
| model | 고정 기본 XGBoost | 동일 |
| fold/seed | canonical 5-fold / 42 | 동일 |
| checkpoint | validation Macro F1 | 동일 |
| sample weight | 동일 | 동일 |
| feature 이름·차원·순서 | 고정 | 완전 동일 |
| isoform mask | 사용 안 함 | 사용 안 함 |
| driver 신규 피처 | 사용 안 함 | 사용 안 함 |
| Optuna | 사용 안 함 | 사용 안 함 |
| Public 기반 조정 | 금지 | 금지 |

과거 EXP-369 점수만 control로 재사용하지 않는다. 라이브러리·코드·환경 차이를
제거하기 위해 stop-v2 control도 새 Issue와 새 EXP-ID로 현재 환경에서 재실행한다.

### 비교 산출물

- fold별·전체 OOF Macro F1, fold std, Accuracy, Log Loss
- 클래스별 F1과 confusion matrix
- OOF/test 확률 차이, argmax 변경, 오류 상관
- token별 v2→v4 route·family·position 변경 목록과 집계
- sample별 feature vector 변경 여부와 family별 변경 수
- unresolved·partial·complete 비율
- train/test 집계는 진단으로 기록하되 규칙 선택에는 사용하지 않음
- runtime, feature nnz, cache·feature·parser contract SHA-256
- checkpoint·OOF·test 확률·submission·재현 bundle

### 판정

parser correctness와 compatibility projection 성능을 따로 판정한다.

- parser v4 의미 계약은 점수가 낮아도 되돌리지 않는다.
- compatibility projection 성능 채택 기준:
  - Control 대비 OOF Macro F1 `+0.001` 이상이면 성능 채택
  - Macro F1 하락 `≤0.001`, fold std 악화 `<0.002`, Log Loss의 명백한 악화와
    클래스 F1 `-0.05` 붕괴가 없으면 새 정확성 기준선으로 허용
  - 그 외에는 projection을 `REJECTED`로 기록하고 family별 mapping을 독립
    ablation한다. legacy parser로 의미 계약을 되돌리지 않는다.
- Public 제출은 Local gate와 inference 검증을 통과한 사전 고정 treatment에 한한다.

## 7. R4 — Parser Baseline v1 동결

R2/R3 완료 후 다음을 하나의 명세로 고정한다.

- notation normalizer version
- semantic router version
- compatibility/native feature adapter version
- fixture catalog 경로·schema·content SHA-256
- compatibility mapping 전체
- 모든 소비자 경로와 parser contract hash
- feature 이름·차원·순서 hash
- unresolved 처리와 raw provenance 정책
- canonical data·split·class order
- 채택 모델 config와 결과 report

이 명세 이후 새 공식 실험은 parser lineage를 생략할 수 없다. 과거 실험에는 새
parser를 소급 적용하지 않고 별도 lineage audit에서 실제 사용 버전을 기록한다.

## 8. R5 — v4-native semantic representation

pure A/B 이후에만 v4의 풍부한 의미를 모델에 노출한다. 한 번에 전부 넣지 않고
support gate를 통과한 family를 별도 Experiment Issue로 검증한다.

우선순위:

1. substitution 의미(no-change·nonsense 포함)
2. frameshift
3. deletion
4. insertion·duplication
5. delins
6. range replacement·range stop·range no-change
7. unresolved provenance summary

각 family는 mutation presence를 제거하지 않고 additive 또는 명시적 replacement
중 하나만 사전 고정한다. train support가 0이거나 canonical fold 최소 지원을
통과하지 못하면 모델 실험이 아니라 QC 자산으로만 보존한다.

## 9. R6/R7 — isoform·driver 재검증

### Isoform

- Parser Baseline v1을 부모로 한다.
- frozen Ensembl release·manifest·cache를 유지한다.
- parser v4 position eligibility와 reference residue 일치가 반영된 새 mask를 사용한다.
- mask 외 모델·피처·fold는 변경하지 않는다.
- 과거 EXP-334의 Optuna 파라미터를 재사용하지 않는다.

### Driver

- Parser Baseline v1을 부모로 한다.
- raw annotation multiplicity와 canonical event presence를 분리한다.
- transcript/genomic event ID 없이 `likely` equivalence를 confirmed로 승격하지 않는다.
- driver presence를 보존하면서 isoform-projected 중복을 과대계수하지 않는다.
- 외부 지식 출처·버전·라이선스·해시를 고정한다.

isoform과 driver를 한 Experiment에서 동시에 추가하지 않는다.

## 10. R8/R9 — Feature Spec 동결과 Optuna 재실행

R5~R7 결과가 끝나면 채택 family만 Feature Spec v4-baseline에 동결한다. 그전에는
Optuna를 실행하지 않는다.

기존 EXP-285 Optuna 결과는 legacy parser feature space의 증거로 보존하되 새
모델 파라미터로 재사용하지 않는다. 새 Optuna는 다음 계약을 사용한다.

- 동결된 v4 Feature Spec
- outer canonical 5-fold
- outer-train 내부 nested CV
- primary metric Macro F1
- trial·study DB, sampler seed, pruner, 전체 파라미터 범위 저장
- checkpoint·study DB·best trial·전체 trials CSV 회수
- Public·test 성능을 objective 또는 trial 선택에 사용하지 않음

## 11. 기존 실험의 지위

- EXP-229·285·334 등은 삭제하지 않는다.
- EXP-369는 stop parser 병목을 입증한 중요한 인과 실험으로 유지한다.
- EXP-374·392는 stop-v2 계보의 후보로 유지한다.
- 이전 isoform·driver 결과는 해당 parser lineage 안에서 유효한 결과다.
- 새 v4 baseline과 직접 비교할 때는 parser·feature·parameter 차이를 명시한다.
- “현재 코드에 parser v4가 존재한다”는 이유로 과거 checkpoint가 v4를 사용했다고
  추정하지 않는다.

## 12. 필수 운영·재현 계약

새 공식 config와 resolved config에는 다음을 필수로 저장한다.

```yaml
parser_lineage:
  notation_normalizer_version: ...
  semantic_router_version: ...
  feature_adapter_version: ...
  fixture_catalog_path: ...
  fixture_catalog_sha256: ...
  projection_name: ...
  projection_version: ...
  projection_sha256: ...
  consumers:
    core_mutation_type: ...
    sample_aggregate: ...
    pathway: ...
    hotspot: ...
    residue_position: ...
```

한 소비자가 다른 parser를 사용하면 공식 실행 전에 실패한다. parser·projection
변경은 모델·feature 변경과 마찬가지로 새 Experiment Issue·EXP-ID를 사용한다.

## 13. 문서 갱신 시점

각 단계는 같은 PR에서 다음을 갱신한다.

1. Issue 생성: Issue·EXP-ID·브랜치
2. 구현 시작: `IN_PROGRESS`
3. PR 생성: PR 번호·`PR_OPEN`
4. 병합: `MERGED`
5. 실행 완료: 실제 OOF·report 링크·재현 상태
6. Public 제출: History 제출 행과 제출 ID
7. 판단: `ADOPT`, `ADOPT_WITH_CAUTION`, `ARCHIVE`, `REJECTED`, `BLOCKED`
8. 다음 단계 또는 중단 조건

## 14. 즉시 다음 행동

R0 PR이 병합되면 일반 Task Issue
`Parser v4 compatibility projection·cross-path consistency validator 구현`을
생성한다. 이 Task가 병합되기 전에는 새 isoform·driver·Optuna 실험을 시작하지
않는다.
