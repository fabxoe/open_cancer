# Parser v4-native semantic baseline 재정립 로드맵

> 현재 상위 Roadmap Issue: [#422](https://github.com/fabxoe/open_cancer/issues/422)
>
> 이전 계획 Issue [#417](https://github.com/fabxoe/open_cancer/issues/417)과
> compatibility Task [#419](https://github.com/fabxoe/open_cancer/issues/419)는
> 문제 정의가 너무 좁아 이 계획으로 대체됐다. #417은 결정 이력으로 보존하고,
> 구현 전이던 #419는 `not planned`로 종료했다.
>
> 이 문서는 현재 프로젝트의 최우선 모델 개발 계획이다. 실제 실행 점수의 원본은
> `EXPERIMENT_HISTORY.md`와 실험별 `metrics.json`이며 예상 점수나 가상 결과를
> 기록하지 않는다.

## 1. 사용자가 정의한 출발점

앞으로 사용할 실제 기준선은 단순히 새 parser를 기존 5개 lexical family에 끼워
넣은 모델이 아니다. 원본 아미노산 변이 표기에서 parser v4가 결정적으로 판정할 수
있는 HGVS-derived 의미를 compact model feature로 재정립하고 통합한 모델이다.

포함 범위는 다음과 같다.

- substitution: ordinary missense, no-change, immediate nonsense, start-site와
  unresolved reference 상태
- frameshift: source grammar, affected position, fixed reference, first-new peptide
  candidate, termination-distance availability, compact·signed·partial 상태
- deletion: 단일·범위, endpoint, span, deleted length
- insertion: 두 flanking boundary, adjacency, inserted length와 stop 포함 상태
- duplication: 단일·범위 tandem event, insertion 표기와의 canonical equivalence,
  duplication confidence
- delins: removed range, replacement length, length delta, stop·frameshift precedence
- range: replacement, no-change, immediate/later stop
- 공통 품질: parse status, HGVS conformance, unresolved reason, raw provenance

이 단계에는 isoform 선택, driver 지식, pathway·hotspot 신규 지식, Optuna와 Public
기반 조정을 넣지 않는다. 즉 **원본 변이 문자열과 고정 의미 규칙만으로 계산되는
parser-native semantic representation**이 새 모델 계보의 출발점이다.

## 2. 두 종류의 parser 평가를 분리한다

“parser만의 효과”라는 표현은 두 질문을 섞으므로 앞으로 단독으로 사용하지 않는다.

### 2.1 Compatibility audit

```text
raw token
→ parser v4 canonical event
→ 기존 missense/synonymous/nonsense/frameshift/complex 5-family로 재투영
→ 기존과 같은 feature 이름·차원
```

이 감사는 다음 질문에만 답한다.

> 옛 표현 공간을 고정했을 때 notation normalization·routing·position eligibility를
> 바로잡은 효과는 무엇인가?

이는 회귀 검사와 과거 계보 연결에는 필요하지만, deletion·insertion·duplication·
delins·range 의미를 다시 `complex`로 뭉개므로 최종 Parser Baseline이 아니다.

### 2.2 Parser-native baseline

```text
raw token
→ parser v4 canonical event와 semantic payload
→ compact native feature adapter
→ 고정 native feature schema
→ canonical 5-fold model
```

이 모델은 다음 질문에 답한다.

> 완성된 parser가 원본 표기에서 확정할 수 있는 의미를 온전히 전달했을 때의 실제
> 기준 성능은 무엇인가?

피처 차원이 달라지므로 lexical parser 교체만의 인과효과라고 부르지 않고
`parser-native semantic representation 효과`라고 기록한다. 앞으로의 isoform,
driver, pathway, Optuna 실험은 이 모델만 부모로 삼는다.

## 3. 기존 5-family의 지위

기존 family는 다음 다섯 개다.

```text
missense / synonymous / nonsense / frameshift / complex
```

이는 HGVS 사건 ontology가 아니라 초기 희소 XGBoost 입력을 위한 lexical bucket이다.
특히 `complex`에는 deletion, insertion, duplication, delins, range replacement,
range no-change, range stop과 unresolved 표기가 함께 들어 있다.

따라서 다음 원칙을 적용한다.

- mutation presence와 기존 5-family 결과는 과거 계보 비교·호환 감사용으로 보존한다.
- native baseline은 기존 mutation presence를 삭제하지 않는다.
- `complex`를 그대로 삭제하지 않고, native family를 additive하게 추가한 첫 기준선을
  만든다. 완전 중복이나 명시적 replacement는 별도 semantic-equivalence 감사 후에만
  허용한다.
- 옛 5-family compatibility 점수가 좋아도 native baseline을 대신할 수 없다.

## 4. 기존 semantic roadmap과 통합 관계

다음 작업은 native baseline의 직접적인 의미 원본이다.

| 의미 영역 | 주요 Issue | native baseline 역할 |
|---|---:|---|
| frameshift | #383, #403 | compact·multi-letter·signed·partial grammar와 근거 수준 |
| substitution | #393 | missense·no-change·nonsense·range substitution 의미 |
| deletion | #394 | single/range deletion 구조 |
| insertion·duplication | #395 | boundary·adjacency·tandem duplication 의미 |
| delins | #399 | removed/replacement 구조와 stop·frameshift precedence |
| 통합 parser contract | #360, #387, #388 | canonical event·fixture·consumer contract |

개별 parser와 fixture가 존재하는 것만으로 모델이 이 의미를 사용했다고 보지 않는다.
다음 연결이 하나의 고정 manifest로 증명되어야 한다.

```text
semantic parser
→ unified canonical event
→ native feature adapter
→ stable feature names/order/schema hash
→ model runner/resolved config
```

## 5. 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | OOF Macro F1 | 판단 | 다음 행동 |
|---|---|---:|---|---:|---|---:|---|---|
| H0 | 이전 호환 중심 계획 | #417 | 해당 없음 | #418 | SUPERSEDED | N/A | 결정 이력 보존 | #422 따름 |
| N0 | native 기준선 최상위 계획·운영 계약 | #422 | 해당 없음 | #423 | MERGED | N/A | 새 정의·운영 계약 병합 완료 | N1 진행 |
| N1 | semantic completeness·support·collision 감사 | #424 | 해당 없음 | #425 | MERGED | N/A | token 전수 route·collision 0·support 5 family 확인 | N2 진행 |
| N2 | unified native feature schema·adapter 구현 | #427 | 해당 없음 | #428 | MERGED | N/A | native schema·presence 보존 검증 완료 | N3 진행 |
| N3 | cross-path consistency·compatibility audit 구현 | #429 | 해당 없음 | #430 | MERGED | N/A | identity collision 0·legacy diff 감사 완료 | N4 runner 구현 |
| N4-R | L/C/N 통제 runner 구현 | #431 | 해당 없음 | #432 | MERGED | N/A | 표현 외 confounder 차단 | N4-L/C/N 실행 |
| N4-L | 현재 환경 legacy control | #433 | EXP-433 | 미발급 | COMPLETED | 0.4132762899 | 동일 환경 control 확정 | N4-C 실행 |
| N4-C | v4 compatibility audit arm | #435 | EXP-435 | 미발급 | COMPLETED | 0.4111034467 | L 대비 -0.0021728433; baseline 아님 | N4-N 실행 |
| N4-N | v4-native semantic treatment | #438 | EXP-438 | 미발급 | IN_PROGRESS | N/A | 실제 baseline 후보 | EXP-433/435 paired 실행 |
| N5 | Parser-native Baseline v1 동결 | 미발급 | explore | 미발급 | PLANNED | N/A | - | N4 3-arm 감사 |
| N6 | isoform 독립 재검증 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | N5 완료 대기 |
| N7 | driver 독립 재검증 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | N5 완료 대기 |
| N8 | pathway·hotspot 재검증·Feature Spec 동결 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | N6·N7 판단 |
| N9 | nested Optuna | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | N8 동결 대기 |
| N10 | 모델 다양화·앙상블·최종 재현 | 미발급 | 미발급 | 미발급 | PLANNED | N/A | - | N9 완료 대기 |

작업 상태는 다음을 사용한다.

```text
PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED
                                     ↘ BLOCKED
                                     ↘ REJECTED
SUPERSEDED는 과거 계획이 새 계획으로 대체됐을 때만 사용한다.
```

이는 `INFERENCE_VERIFIED`, `TRAINING_VERIFIED` 같은 재현 상태와 구분한다.

## 6. N1 — semantic completeness·support·collision 감사

모델 학습 전에 parser v4의 native payload가 실제 train/test 표기를 얼마나 설명하는지
감사한다. test 결과는 QC와 사전 고정 schema 지원 여부를 확인하는 데만 사용하며,
label·Public 기반 규칙 선택에는 사용하지 않는다.

필수 산출물:

- family·subfamily별 train/test token count와 unique token count
- complete/partial/unresolved 비율과 unresolved reason
- gene·sample·canonical fold별 최소 support
- 동일 raw token이 둘 이상의 primary event로 route되는 collision 0건 증명
- 서로 다른 표기가 같은 canonical event로 정규화되는 equivalence 집계
- raw mutation presence 보존 증명
- 위치 eligibility, reference/alternate, range endpoint, length 필드의 결측 행렬
- 장문 inserted/replacement sequence 길이 분포와 상한 초과 처리
- 기존 5-family와 native family의 confusion/crosswalk 표

지원 수가 적다고 올바른 parser 사건을 삭제하지 않는다. 모델 입력 여부만 다음처럼
결정한다.

- 충분한 support: compact numeric/binary feature 후보
- 희소하지만 의미 확정: 상위 family로 합치거나 QC-only
- partial/unresolved: 별도 provenance summary, 특정 생물학적 사건으로 강제 승격 금지
- 장문 raw sequence: 원문·hash·길이는 보존하되 고차원 범주 one-hot 금지

## 7. N2 — unified parser-native feature adapter

### 7.1 공통 열

- `event_presence`
- primary event one-hot
- `parse_complete`, `parse_partial`, `parse_unresolved`
- `hgvs_conformant`, `source_nonstandard`
- `position_observed`, `range_observed`, `positions_adjacent`
- `start_position`, `end_position`, `span`
- `reference_length`, `alternate_length`, `length_delta`
- `contains_stop`, `immediate_stop`, `later_stop`

### 7.2 family별 compact 의미

**Substitution**

- ordinary missense, no-change, immediate nonsense
- reference·alternate residue와 물성 변화는 고정 표준 20-AA mapping으로만 계산
- range replacement/no-change/stop은 단일 substitution과 분리
- `X`가 stop alias인지 unknown amino acid인지 문맥에 따라 구분

**Frameshift**

- affected position과 fixed reference availability
- first-new residue/peptide는 원문이 지원할 때 candidate로만 기록
- termination distance의 known/unknown과 값
- compact, multi-letter, signed partial, bilateral-stop source grammar
- 원문에 없는 새 reading-frame peptide나 stop distance 추정 금지

**Deletion**

- single/range, endpoint, deleted length와 span
- nonsense·frameshift로 route된 사건을 deletion으로 중복 계수하지 않음
- 3′ rule은 reference sequence 없이 임의 재배치하지 않고 source/canonical 상태로 분리

**Insertion·Duplication**

- 두 flanking residue와 adjacency
- inserted sequence length, stop 포함 여부
- duplication은 원본 copy 바로 C-terminal의 tandem event일 때만 confirmed
- insertion 표기에서 local tandem equivalence가 확인되면 projected confidence로 보존
- 단일 anchor insertion처럼 데이터에 없는 문법을 억지 지원하지 않음

**Delins**

- removed range와 replacement sequence를 별도 저장
- removed/replacement length와 delta
- immediate stop은 nonsense, 이후 frame shift는 frameshift 우선 계약 적용
- 확정할 수 없는 reading-frame 결과는 delins/unresolved로 보존

### 7.3 집계 단위

첫 native baseline은 다음 두 수준만 사용한다.

- 유전자별 family/subfamily 존재 indicator
- 샘플별 family token count, affected-gene count와 parse-status count

raw peptide vocabulary, 암종별 빈도, target encoding, test 기반 threshold는 사용하지
않는다. 기존 `GENE__mutated`와 raw provenance는 항상 유지한다.

## 8. N3 — compatibility·cross-path 감사

Compatibility projection은 N2의 대체물이 아니라 보조 진단 adapter다.

```text
substitution missense → missense
substitution no-change → synonymous
immediate nonsense → nonsense
frameshift → frameshift
deletion/insertion/duplication/delins/ordinary range → complex
partial/unresolved → complex + unresolved provenance
```

다음 소비자는 동일한 canonical event hash를 재사용해야 한다.

1. core gene event feature
2. sample aggregate
3. pathway·hotspot consumer
4. residue-position eligibility
5. parser QC·manifest

legacy regex를 직접 호출하거나 서로 다른 parser identity를 사용하면 validator가
실패한다. 이 단계는 공식 baseline 점수를 만들지 않는 Task/QC다.

## 9. N4 — 현재 환경 3-arm 통제 실험

과거 점수를 그대로 control로 재사용하지 않고 같은 main commit·환경에서 연속 실행한다.

| 항목 | Legacy L | Compatibility C | Native N |
|---|---|---|---|
| parser | 채택한 legacy/stop-v2 | full v4 | full v4 |
| feature representation | 기존 | 기존 5-family 동일 차원 | native semantic schema |
| model/fold/seed | 고정 | L과 동일 | L과 동일 |
| checkpoint | validation Macro F1 | 동일 | 동일 |
| sample weight | 동일 | 동일 | 동일 |
| isoform·driver·새 pathway | 없음 | 없음 | 없음 |
| Optuna | 없음 | 없음 | 없음 |

해석:

- `C - L`: 옛 표현을 고정한 notation/routing/eligibility 교체 효과
- `N - C`: native semantic representation을 노출한 추가 효과
- `N - L`: 사용자가 의도한 완성된 parser 기반 새 출발점의 총 효과

각 arm은 새 Experiment Issue와 EXP-ID를 사용한다. N은 차원이 다르므로 paired
feature byte equality를 요구하지 않고, parser·data·model 통제와 schema hash를
요구한다.

필수 비교:

- 전체·fold별 OOF Macro F1과 fold std
- 클래스별 F1, confusion matrix, Accuracy, Log Loss
- OOF/test argmax 변경, 확률 차이와 오류 상관
- token route·feature diff와 sample별 변경 수
- feature 수, nnz, memory, runtime
- unresolved·partial support와 family별 feature 사용량
- checkpoint·OOF·test 확률·submission·resolved config·repro bundle

## 10. 성능과 correctness 판정

- parser correctness는 점수가 낮다는 이유로 되돌리지 않는다.
- native feature adapter는 성능과 안정성으로 채택·수정한다.
- 첫 N arm이 성능 gate에 실패해도 legacy model을 새 공식 부모로 선언하지 않는다.
  native schema에서 family별 additive feature를 통제 ablation해 표현 문제를 찾는다.
- parser-native baseline은 모든 의미 family가 parser에서 지원되되, train support가
  부족한 세부 열은 QC-only로 남길 수 있다.
- Public은 Local gate와 `INFERENCE_VERIFIED`를 통과한 사전 고정 후보에만 사용한다.

기본 성능 gate:

- Legacy L 대비 OOF Macro F1 `+0.001` 이상: 성능 채택
- 하락 `≤0.001`, fold std 악화 `<0.002`, 클래스 F1 `-0.05` 붕괴 없음:
  정확성 기준선 허용
- 그 외: native feature family별 ablation으로 adapter를 수정하되 parser 의미 계약은 유지

## 11. N5 — Parser-native Baseline v1 동결

다음이 모두 갖춰진 뒤에만 동결한다.

- notation normalizer·semantic router·native adapter version
- fixture catalog 경로·schema·content SHA-256
- semantic family와 feature 계산식 전체
- feature 이름·차원·순서·schema hash
- unresolved·partial·raw provenance 정책
- 모든 consumer identity와 parser contract hash
- canonical data·split·class order
- canonical 5-fold 결과와 재현 bundle
- 채택·제외된 native 세부 열과 근거

이 시점부터 새 공식 실험은 Parser-native Baseline v1을 부모로 삼는다. 기존 parser
계보는 역사적 비교 대상으로만 유지한다.

## 12. N6 이후 재검증 순서

1. isoform mask: frozen Ensembl snapshot, parser v4 position/reference eligibility만 변경
2. driver: canonical event presence와 annotation multiplicity를 분리
3. pathway·hotspot: native event 의미로 재계산하고 하나씩 독립 검증
4. 채택 family만 새 Feature Spec으로 동결
5. 동결 후 nested Optuna를 처음부터 재실행
6. XGBoost·LightGBM·CatBoost·선형 모델 다양화
7. 오류 상관을 감사한 고정 blend/stacking
8. 최종 후보 independent `TRAINING_VERIFIED`

EXP-285 Optuna와 이전 isoform·driver 결과는 해당 legacy feature space에서는 유효하지만
새 parser-native 모델 파라미터로 재사용하지 않는다.

## 13. 필수 테스트

- fixture catalog 전수 route·snapshot
- `X/*/Ter`, 허용 대소문자·공백 표기의 metamorphic equivalence
- family routing precedence와 collision 0건
- mutation presence와 raw token 보존
- train/test transform에 SUBCLASS·Public 미사용
- deterministic feature 이름·순서·schema hash
- sparse/dense 값 범위와 NaN/inf 없음
- 동일 canonical event의 모든 consumer hash 일치
- checkpoint 재추론 시 동일 schema·OOF·test 확률 재생성
- legacy arm 결과·History를 수정하지 않음

## 14. resolved config 계약

```yaml
parser_lineage:
  notation_normalizer_version: ...
  semantic_router_version: ...
  feature_adapter_name: compatibility | native
  feature_adapter_version: ...
  fixture_catalog_path: ...
  fixture_catalog_sha256: ...
  semantic_schema_path: ...
  semantic_schema_sha256: ...
  feature_names_sha256: ...
  consumers:
    core_event: ...
    sample_aggregate: ...
    pathway: ...
    hotspot: ...
    residue_position: ...
```

parser·adapter·schema가 바뀌어 feature vector가 달라지면 새 Experiment Issue와
EXP-ID를 사용한다.

## 15. 기존 실험의 지위

- 기존 실험 ID·점수·resolved config를 수정하지 않는다.
- EXP-369는 stop 표기 병목을 보여준 중요한 인과 증거로 유지한다.
- EXP-229·285·334·374·392 등은 실제 사용한 legacy/stop-v2 lineage로 보존한다.
- 저장소에 parser v4 코드가 있다는 이유로 과거 checkpoint가 v4를 사용했다고
  추정하지 않는다.
- 과거 결과의 결함 가능성은 해당 lineage의 표현 한계로 기록하고 “실험이 없었다”거나
  “점수가 틀렸다”고 소급 변경하지 않는다.

## 16. 문서 갱신 시점

각 단계는 같은 PR에서 다음을 갱신한다.

1. Issue 생성: Issue·EXP-ID·브랜치
2. 구현 시작: `IN_PROGRESS`
3. PR 생성: PR 번호·`PR_OPEN`
4. 병합: `MERGED`
5. 실행 완료: 실제 OOF·report 링크·재현 상태
6. Public 제출: History 제출 행과 제출 ID
7. 판단: `ADOPT`, `ADOPT_WITH_CAUTION`, `ARCHIVE`, `REJECTED`, `BLOCKED`
8. 다음 단계 또는 중단 조건

## 17. 즉시 다음 행동

1. 이 계획과 운영 계약을 #422 PR로 병합한다.
2. N1 일반 Task Issue `Parser v4 semantic completeness·support·collision audit`을
   새로 발급한다.
3. N1 결과로 native schema 후보의 실제 support를 고정한다.
4. N2 통합 adapter가 병합되기 전에는 새 isoform·driver·pathway·Optuna 실험을
   시작하지 않는다.
