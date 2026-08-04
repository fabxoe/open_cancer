# Protein deletion semantic parser v4 감사

## 목적

Issue [#394](https://github.com/fabxoe/open_cancer/issues/394)의 일반 Task 결과다.
대회식 deletion token을 single/range, residue-aware/position-only로 구분하고,
frameshift·delins·nonsense를 substring 때문에 deletion으로 오분류하지 않는
선택형 semantic parser와 feature adapter를 구현했다. 모델·OOF·Public 점수는
생성하지 않았다.

## 실행

```bash
uv run python scripts/audit_protein_deletion_semantics.py
uv run pytest -q tests/test_protein_deletion_semantics.py \
  tests/test_protein_substitution_semantics.py \
  tests/test_robust_mutation_parser.py
```

compact 결과는 [`audit.json`](audit.json)에 있다. 원본 행과 환자 ID는 저장하지
않았다. 입력 SHA-256은 train
`92418b8441d058cfc68e939dd88725610750be4bc8edc51253cffc72fc4fc0ab`, test
`e7e7f29a9b6251308e470ae3fb040a6da0cd8fcb0adb87e67f7761631c6a1ef0`다.

## 전수 감사 결과

| deletion syntax | train | test |
|---|---:|---:|
| residue-aware single (`R649del`) | 1 | 1,680 |
| position-only single (`249del`) | 2 | 0 |
| residue-aware range (`G235_G238del`) | 0 | 888 |
| position-only proper range (`134_135del`) | 0 | 4 |
| equal-position range (`277_277del`) | 0 | 11 |
| 합계 | 3 | 2,583 |

Issue의 “position-only range 15건”은 proper range 4건과 equal-position 11건의
합이다. 실제 reversed range는 train/test 모두 0건이다. test deleted length는
최소 1, 중앙값 1, 90백분위 5, 최대 859였다.

별도 event routing도 확인했다.

- test `delins`: 545건, deletion에서 제외
- train `SDEL133fs` substring collision: 1건, frameshift로 유지
- unsupported `del` substring: 0건

## 의미 계약

### Single과 range

- `R649del`: reference residue가 있는 single deletion, length 1
- `249del`: position-only single deletion, residue는 `null`
- `G235_G238del`: 235~238 inclusive range deletion, length 4
- `134_135del`: position-only range deletion, length 2

Range endpoint residue만으로 중간 reference sequence를 만들지 않는다. Insertion
boundary와 달리 deletion range endpoint는 인접할 필요가 없다.

### Equal-position range

`277_277del`은 HGVS-conformant range는 아니지만 의미상 277번 single deletion이다.
raw·lexical normalized token은 `277_277DEL`로 보존하고 semantic canonical
token만 `277DEL`로 둔다. source 표기가 비표준이었다는 사실을 지우지 않는다.

### Ordering과 3′ rule

Position은 N-terminal에서 C-terminal 방향으로 증가해야 한다. reversed range는
자동 swap하지 않고 unresolved로 보존한다. 반복 구간의 3′ rule 이동은 fixed
reference sequence 없이 수행하지 않으므로 이번 token-only parser에서는
`three_prime_normalized=unknown`이다.

### Protein consequence 우선순위

`E1117delinsG`, `SDEL133fs`, `Y780*`는 각각 delins, frameshift, nonsense이며
deletion이 아니다. DNA/RNA deletion이 원인일 수 있다는 이유로 protein token을
deletion으로 역추론하지 않는다.

## Feature adapter

기존 4,384개 gene 피처는 그대로 두고 다음 opt-in 후보만 제공한다.

- per gene: deletion/single/range/position-only `any/count`
- per gene: deleted length `sum/max/log1p sum`
- sample: token count, unique-gene count, single/range/position-only gene count,
  length `sum/max/log1p sum`

train deletion이 3건뿐이므로 test 2,583건을 보고 cap·threshold·weight를 정하지
않는다. 공식 모델 평가는 별도 Experiment Issue에서 기존 피처를 유지한 채 이
family 하나만 추가하는 canonical 5-fold ablation으로 분리한다.

## 비범위

- DNA/RNA·exon deletion 원인 및 transcript reconstruction
- start/stop codon deletion consequence, phase·mosaic·zygosity
- driver/pathogenicity/actionability
- 원본에 없는 `R45del6`, `EX17del`, `ΔF508`, `=/del` 문법
- reference 없는 endpoint·중간 sequence·3′ position 추정
