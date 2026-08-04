# Annotation-invariant mutation parser v2/v3/v4

이 문서는 Issue #352에서 구현한 선택형 parser·feature contract를 설명한다. 기존
공식 실험은 `mutation_features.py`의 parser v1을 그대로 사용하며 결과를 다시
해석하거나 변경하지 않는다. parser v2는 별도 Experiment Issue에서 명시적으로
활성화했을 때만 사용한다.

## 왜 별도 parser가 필요한가

기존 parser는 단일 아미노산 치환과 `*` stop 표기, `fs` suffix를 제외한 모든
토큰을 `complex`로 분류한다. 실제 입력 감사에서는 test의 generic complex 토큰
중 `R213X`처럼 `X`로 기록된 stop-gain이 큰 비중을 차지했다. 이는 동일한
stop-gain 의미가 `*`와 `X` 표기 차이 때문에 서로 다른 피처로 들어가는 사례다.

parser v2는 다음 의미 범주를 target·Public·암종 빈도 없이 문자열 자체에서만
결정한다.

```text
missense
synonymous
stop_gain
frameshift
inframe_deletion
inframe_insertion
delins
range_replacement
duplication
other_unmappable
```

`X`, `*`, `Ter`는 단순 치환의 alternate residue일 때만 `stop_gain`으로 통합한다.
`X127C`처럼 reference가 `X`인 표기는 reference amino acid를 알 수 없으므로
`other_unmappable`로 보존한다. transcript나 실제 발현 isoform을 추정하지 않는다.

`-287fs`처럼 음수로 시작하는 부분 표기와 `*261*`처럼 양쪽 별표로 둘러싸인
표기는 정상 단백질 잔기 좌표로 해석하지 않는다. 이들은
`other_unmappable`, `position_eligible=false`, 빈 residue-position으로 격리한다.
사건 의미를 추측해 정상 frameshift나 stop-gain으로 강제 변환하지 않는다.

## Robust representation 계약

- WT·빈값은 사건 없음으로 처리한다.
- token 순서, 공백, 대소문자 차이는 표현을 바꾸지 않는다.
- 의미 정규화 후 같은 exact token이 반복되면 한 번만 센다.
- sample 집계는 raw token 수가 아니라 해당 사건군이 관찰된 **서로 다른 유전자
  수**를 센다.
- 선택적으로 유전자×사건군 `any` indicator를 생성한다.
- position eligibility는 명확한 단일 치환·stop-gain과 시작점이 명시된
  frameshift에만 부여한다. Ensembl sequence 일치 여부는 기존 frozen annotation
  단계에서 별도로 검사한다.

## 해석 제한

- insertion·deletion 표기만으로 임상적 기능 효과를 판정하지 않는다.
- `other_unmappable`을 오류나 passenger mutation이라고 단정하지 않는다.
- train/test prevalence를 보고 범주나 임계값을 변경하지 않는다.
- parser v2는 아직 기본 Feature Spec이 아니다. canonical 5-fold 단일변수
  ablation을 통과해야 채택할 수 있다.

## 후속 실험 순서

1. raw `sample__complex_count` 대신 unique complex-event gene count 사용
2. generic complex gene indicator를 normalized event-family indicator로 교체
3. 채택된 robust representation과 EXP-313 Ensembl mask 조합

각 단계는 별도 Experiment Issue와 EXP-ID를 사용하고, 선행 결과를 보고 parser
범주를 다시 조정하지 않는다.

R1 EXP-355와 R2 EXP-359는 모두 성능 gate를 통과하지 못해 robust feature
representation 교체는 종료했다. parser의 표기 정규화·의미 동등성 자체는 Issue
#364의 fixture와 compact audit로 독립 검증하며, 기존 공식 Feature Spec을
소급 변경하지 않는다.

## Feature Factory adapter 계약

Issue #366에서 기본 v1 동작을 바꾸지 않는 선택형 parser hook을 추가했다.

- `parse_stop_notation_invariant_cell`: token 수와 나머지 v1 의미는 유지하고
  단순 stop alternate `*`, `X`, `Ter`만 `*`로 정규화한다.
- `parse_position_sanitized_cell`: v1 mutation type은 유지하되 `-287fs`,
  `*261*` 같은 불명확 표기의 residue-position만 제거한다.
- custom adapter는 반드시 versioned `mutation_parser_contract`와 함께 사용한다.
- adapter contract는 Feature Spec·cache key에 들어가므로 v1 cache와 섞이지 않는다.

실제 train의 `A숫자*` 13,289건을 각각 `A숫자X`, `A숫자Ter`로 바꾼
metamorphic audit에서 canonical equivalence 실패는 0건이었다. v1에서는 같은
13,289건이 `nonsense`에서 `complex`로 달라졌다. 상세 결과는
[`reports/analysis/stop_notation_invariance/README.md`](../reports/analysis/stop_notation_invariance/README.md)에
기록한다.

## Parser v3: anchored multi-letter frameshift·range grammar

Issue #378에서 robust parser definition을 `3.0.0`으로 올렸다. parser v1과 기존
공식 실험은 변경하지 않으며 v3를 사용하는 후속 실험만 명시적으로 opt-in한다.

- `SDEL133fs`처럼 residue prefix 안에 `DEL`이 있어도 complete token이
  `prefix+position+fs` grammar와 일치하면 frameshift다.
- `721_722LA>FS`의 `FS`는 range alternate의 Phe-Ser이므로 frameshift가 아니다.
- multi-letter frameshift prefix는 source-format 또는 transcript 근거 없이
  reference/alternate peptide로 분해하지 않고 `unresolved_multiletter_prefix`로
  보존한다.
- range token은 reference·alternate sequence와 coordinate span을 검증한다.
- range alternate에서 project stop 표기 `*`, `X`, `Ter`를 canonical `*`로
  정규화한다.
- reference와 alternate가 같으면 protein no-change로, 첫 alternate가 stop이면
  immediate stop-gain으로, 앞선 peptide 뒤 stop이면 truncating range replacement로
  기록한다.
- stop 이후 source 문자는 provenance에는 남지만 translated alternate에는 넣지
  않는다.

실제 compact 감사와 팀장 제공 fixture의 해석은
[`reports/analysis/multiletter_frameshift_range_parser/README.md`](../reports/analysis/multiletter_frameshift_range_parser/README.md)에
기록한다.

## Parser v4: protein tandem duplication semantic adapter

Issue #395는 기존 parser를 덮어쓰지 않고 insertion 원문과 reference-aware
duplication 의미를 분리하는 `protein_duplication_semantics_v4`를 추가한다.

- 대회 원문에는 literal `dup`가 없고, 순수 `ins`는 train 0건·test 1,142건이다.
- `A숫자_B숫자insSEQ`의 양쪽 경계와 inserted sequence를 손실 없이 파싱한다.
- `A숫자_숫자insSEQ`처럼 오른쪽 residue가 생략된 실제 부분 문법도
  `parse_status=partial`로 보존하고 reference 확인 전에는 완전 표기로 취급하지 않는다.
- inserted sequence가 삽입 경계 바로 N-terminal의 reference sequence와 완전히
  같을 때만 tandem duplication으로 확정한다. 근처 다른 위치에 같은 서열이 있는
  경우는 insertion이다.
- fixed Ensembl release 116에서 MANE Select, canonical, other isoform 순으로
  판정하며 같은 우선순위 isoform이 서로 다른 해석을 만들면 unresolved로 남긴다.
- 반복 서열은 최종 protein sequence가 같은 모든 표현을 재생성하고 가장
  C-terminal인 source range를 선택해 HGVS 3' rule을 적용한다.
- raw syntax, semantic event, evidence status와 raw/canonical source range를
  동시에 보존한다.
- stop·frameshift·extension·delins를 duplication으로 승격하지 않으며 DNA/exon
  원인, total repeat copy number, allele·mosaic 상태를 역추론하지 않는다.

전수 감사에서 test insertion 1,142건 중 753건이 reference-confirmed tandem
duplication, 265건이 일반 insertion, 121건이 isoform unresolved, 3건이 annotation
없는 단일 left-copy 후보였다. 상세 계약과 결과는
[`reports/analysis/protein_duplication_semantics/README.md`](../reports/analysis/protein_duplication_semantics/README.md)에
기록한다.

## Parser v4: protein substitution semantic adapter

Issue #393은 단일 위치 substitution의 문법·의미를 별도 v4 adapter로 고정한다.

- 표준 amino acid 1개가 다른 표준 amino acid 1개로 바뀔 때만 ordinary
  missense이며 physicochemical delta도 이 경우에만 허용한다.
- `D623D`형 same-AA는 protein no-change annotation으로 보존하고 `WT`와
  동일시하지 않는다.
- alternate `*`, `X`, `Ter`는 immediate nonsense의 동일 표기로 canonical `*`를
  사용한다.
- `M1<AA>`는 translation-initiation-site 영향으로 분리하고 ordinary missense로
  세지 않는다.
- leading `X`는 unknown reference, leading `*`는 nonstandard unresolved로
  보존하며 stop-loss·extension을 추정하지 않는다.
- range·indel·frameshift grammar는 substitution parser가 소비하지 않는다.

train/test 전수 수치와 해석 제한은
[`reports/analysis/protein_substitution_semantics/README.md`](../reports/analysis/protein_substitution_semantics/README.md)에
기록한다.

## Parser v4: protein deletion semantic adapter

Issue #394는 complete anchored deletion grammar를 별도 v4 adapter로 구현한다.

- single/range와 residue-aware/position-only 표기를 각각 구조화한다.
- range length는 `end - start + 1`의 inclusive 값이며 deletion endpoint는
  insertion boundary와 달리 인접할 필요가 없다.
- `277_277del` 같은 equal-position range는 raw를 보존한 채 semantic single로만
  정규화하고 nonconformant 상태를 남긴다.
- reversed range는 자동 swap하지 않고 unresolved로 보존한다.
- `SDEL133fs`, `delins`, nonsense는 deletion substring보다 우선하는 전용 event다.
- 3′ rule은 fixed reference 없이 적용하지 않는다.

실제 감사에서 true deletion은 train 3건, test 2,583건이었고 test delins 545건과
train `SDEL133fs` 1건은 모두 별도로 유지됐다. 상세 결과는
[`reports/analysis/protein_deletion_semantics/README.md`](../reports/analysis/protein_deletion_semantics/README.md)에
기록한다.

## Parser v4: protein delins semantic adapter

Issue #399는 raw delins source structure와 protein consequence를 직교적으로
보존한다. single/range span, alternate raw/canonical/translated sequence,
immediate/later stop, post-stop provenance, unknown reference와 net protein length
change를 구조화한다. Upper-case `TER`가 multi-letter one-letter peptide 안에 있으면
Thr-Glu-Arg로 보존하고 explicit `Ter` suffix 및 `X/*`만 stop으로 처리한다.
train 0건·test 545건이므로 모델 실험은 강행하지 않고 OOD semantic QC로 종료한다.
상세 결과는
[`reports/analysis/protein_delins_semantics/README.md`](../reports/analysis/protein_delins_semantics/README.md)에
기록한다.

## Parser contract v4: 계층 버전과 통합 router

Issue #387은 notation normalizer, semantic parser, feature adapter를 독립 버전으로
기록하고 실제 원본 사례 fixture catalog를 content-addressed SHA-256으로 고정한다.
통합 router는 `frameshift → delins → deletion → insertion → substitution → range
replacement` 순서로 한 token을 정확히 한 모듈에만 전달한다. 새 공식 runner가 이
contract를 opt-in하면 resolved config의 계약 필드 누락이나 fixture hash 불일치를
실행 오류로 처리한다. 과거 실험과 기본 Feature Spec은 변경하지 않는다. 상세 계약은
[`reports/analysis/parser_contract_v4/README.md`](../reports/analysis/parser_contract_v4/README.md)에
기록한다.

## Parser v4: frameshift compact grammar

Issue #383은 `REF+POSITION+fs`, `REF+ALTSEQ+POSITION+fs`,
`REF+POSITION+ALTSEQ+fs`의 세 관측 문법을 분리한다. 첫 residue와 position은 fixed
Ensembl reference로 검증하고 first-new peptide는 후보로 보존하지만, DNA frame과
종료까지 거리는 원본에 없으므로 추정하지 않는다. `SDEL133fs`의 `DEL`은 deletion
keyword가 아니라 frameshift 새 peptide 후보로 라우팅한다. 상세 결과는
[`reports/analysis/protein_frameshift_semantics/README.md`](../reports/analysis/protein_frameshift_semantics/README.md)에
기록한다.

## Isoform annotation multiplicity

Issue #389는 raw annotation count와 exact-normalized strict event count, 그리고
gene+event+ref/alt 기반 likely event count를 직교 저장한다. transcript/genomic event
ID가 없는 competition input에서는 confirmed group을 만들지 않고, cross-sample
recurrence도 환자 사이에서 합치지 않는다. 상세 계약은
[`reports/analysis/isoform_annotation_multiplicity/README.md`](../reports/analysis/isoform_annotation_multiplicity/README.md)에
기록한다.

## Driver-preserving canonical event signature

Issue #390은 likely multiplicity collapse가 알려진 protein driver를 제거하지 않는지
별도로 감사한다. raw annotation, annotation multiplicity, independent canonical event,
driver presence와 equivalence confidence를 각각 저장한다. `EXACT`, fixed-reference
`ISOFORM_PROJECTED`, `FAMILY_LEVEL`을 구분하고, 마지막 상태를 canonical coordinate
동일성으로 오해하지 않는다. 첫 regression case인 EGFR IPVAIK 네 annotation은 raw
4개를 유지하면서 canonical signature 1개와 driver presence 1을 만든다. 상세 근거와
feature overlap은
[`reports/analysis/driver_event_signature/README.md`](../reports/analysis/driver_event_signature/README.md)에
기록한다.
