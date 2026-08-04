# Annotation-invariant parser·robust representation 로드맵

> 계획과 진행 상태만 관리한다. 실제 실험 점수는 `EXPERIMENT_HISTORY.md`와
> 실험별 `metrics.json`을 원본으로 사용하며 예상 점수를 적지 않는다.

## 목적

동일한 단백질 사건이 `X`/`*`, token 순서, 중복 또는 indel 표기 차이 때문에
서로 다른 모델 피처가 되지 않도록 parser와 feature representation을 버전 관리한다.
mutation presence는 보존하고 raw token multiplicity·불확실 위치가 과대계수되는
경로만 독립적으로 검증한다.

## 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | OOF Macro F1 | 판단 | 다음 행동 |
|---|---|---:|---|---:|---|---:|---|---|
| P0 | parser v2·canonical event contract | #352 | 해당 없음 | #354 | COMPLETED | N/A | 구현·전체 테스트 완료 | R1 완료 |
| P1 | train/test compact parser QC | #352 | explore | #354 | COMPLETED | N/A | X stop 표기 차이 확인 | R1 완료 |
| R1 | raw complex count → unique complex-event gene count | #355 | EXP-355 | #358 | REJECTED | 0.4176342820 | EXP-229 대비 -0.0053543·Log Loss·DLBC 악화 | R2 독립 실행 |
| R2 | generic complex gene signal → normalized event-family indicator | #359 | EXP-359 | #363 | REJECTED | 0.4187813830 | EXP-229 대비 -0.0042072·Log Loss 악화 | 공식 탐색 종료 |
| R3 | 채택 robust representation + EXP-313 mask | 미발급 | 미발급 | 미발급 | REJECTED | N/A | R1·R2 모두 실패해 중단 조건 적용 | 실행하지 않음 |
| P4 | parser v4 family train-support gate | #407 | 해당 없음 | 미발급 | COMPLETED | N/A | 새 후보는 ordinary range replacement | 별도 Experiment Issue |

상태는 `PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED`를 사용하며
실험 재현 상태와 구분한다.

## 고정 의미 계약

parser v2 event family는 Issue #352 구현 전에 다음으로 고정했다.

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

- `R213X`와 `R213*`는 같은 stop-gain으로 정규화한다.
- reference가 `X`인 표기는 알려지지 않은 reference로 취급해 합리화하지 않는다.
- exact semantic duplicate만 제거하고 다른 위치·사건은 합치지 않는다.
- sample 집계는 raw token 수가 아니라 사건군별 unique mutated-gene 수를 사용한다.
- position은 parser상 eligible한 token만 frozen Ensembl mask 단계로 전달한다.
- SUBCLASS·Public·암종별 빈도·test prevalence로 규칙을 변경하지 않는다.

## 실험 계약

### R1: sample aggregate 단일 교체

부모는 EXP-229로 고정한다. 모델·fold·checkpoint·pathway·hotspot·나머지 피처는
유지하고 raw `sample__complex_count` 한 열만 non-simple normalized event가
관찰된 unique-gene count 한 열로 교체한다. stop-gain `X`는 complex가 아니라
stop-gain으로 센다.

### R2: gene-level complex 표현 교체

R1과 별도 EXP로 실행한다. generic `GENE__complex`를 삭제하고 다음 normalized
non-simple event family `any` indicator로 교체한다. raw sample aggregate는 R1과
섞지 않는다.

```text
inframe_deletion / inframe_insertion / delins /
range_replacement / duplication / other_unmappable
```

### R3: annotation semantics 조합

R1 또는 R2가 채택 기준을 통과한 경우에만 동결된 표현을 EXP-313의 Ensembl 116
residue-position mask와 조합한다. parser family와 mask 범주를 다시 조정하지 않는다.

## 공통 판정과 중단 조건

- canonical stratified 5-fold, seed 42
- OOF Macro F1을 공식 지표로 사용
- 부모 대비 Macro F1 `+0.001` 이상
- fold 표준편차 악화 `<0.002`
- Log Loss의 명백한 악화 없음
- 충분한 표본의 어떤 클래스도 F1 `-0.05` 이상 붕괴하지 않음
- checkpoint inference 검증 통과

R1·R2는 사전 정의된 독립 실험으로 각 1회 실행한다. 둘 다 실패하면 parser v2를
QC·파싱 라이브러리로만 보존하고 robust representation 공식 탐색을 종료한다.
Public 결과를 보고 event family나 교체 범위를 수정하지 않는다.

## 최종 결정

- R1 EXP-355와 R2 EXP-359가 모두 부모 EXP-229보다 낮아 공식 표현 교체를
  채택하지 않는다.
- R3은 조건부 단계였으므로 Issue·EXP-ID를 만들지 않고 종료한다.
- parser v2의 X/`*` stop-gain 통합, exact duplicate 제거, 명시적 event semantics는
  향후 QC와 annotation audit에 재사용하되 현재 모델의 base 표현을 바꾸지 않는다.
- 상세 R2 결과는
  [`reports/exp359_robust_event_gene_indicators/README.md`](../exp359_robust_event_gene_indicators/README.md)에 기록한다.

## 실제 QC에서 새로 확인한 점

- test v1 complex 19,070개 중 14,355개(`75.28%`)는 X 표기 stop-gain이었다.
- stop-gain 통합 후에도 test non-simple event 4,715개가 남아 완전한 shift 해소를
  가정하지 않는다.
- EXP-109의 morphology **추가**는 OOF를 악화시켰으므로 이번에는 추가가 아니라
  기존 generic complex 표현의 단일 교체만 검증한다.

상세 수치는
[`reports/analysis/robust_mutation_parser_v2/README.md`](../analysis/robust_mutation_parser_v2/README.md)를
참고한다.
