# Protein substitution semantic parser v4 감사

## 목적

Issue [#393](https://github.com/fabxoe/open_cancer/issues/393)의 Task 결과다.
대회식 1-letter protein token에서 단일 치환의 문법과 단백질 의미를 분리하고,
기존 parser·공식 실험 결과를 소급 변경하지 않는 선택형 semantic parser와 feature
adapter를 구현했다. 이번 작업은 모델 학습·OOF·Public LB를 수행하지 않았다.

## 실행

```bash
uv run python scripts/audit_protein_substitution_semantics.py
uv run pytest -q tests/test_protein_substitution_semantics.py \
  tests/test_robust_mutation_parser.py \
  tests/test_mutation_notation_invariance.py
```

원본 입력 SHA-256:

- train: `92418b8441d058cfc68e939dd88725610750be4bc8edc51253cffc72fc4fc0ab`
- test: `e7e7f29a9b6251308e470ae3fb040a6da0cd8fcb0adb87e67f7761631c6a1ef0`

compact 원본 결과는 [`audit.json`](audit.json)에 있다. 환자 ID와 원본 행은
저장하지 않았다.

## 핵심 결과

| 의미 family | train occurrence | test occurrence | 해석 |
|---|---:|---:|---|
| ordinary missense | 164,740 | 201,353 | 표준 AA 1개가 다른 표준 AA 1개로 치환 |
| same-AA/no-change | 66,883 | 88,724 | `D623D`형; WT와 동일시하지 않음 |
| nonsense | 13,289 | 16,316 | alternate `*`, `X`, `Ter`를 `*`로 통합 |
| start codon affected | 0 | 572 | `M1T` 등; ordinary missense에서 격리 |
| unknown reference | 0 | 390 | `X127C`형; stop-loss로 추정하지 않음 |
| nonstandard leading stop | 99 | 13 | `*261*`형; unresolved 유지 |

사전 감사에서 “test simple missense 모양 201,925건”이라고 표현한 값은 ordinary
missense 201,353건과 `M1<AA>` 572건의 합이다. v4는 이 둘을 분리한다.

## 의미 계약

### Ordinary missense

`R132H`처럼 reference·alternate가 모두 표준 20개 amino acid이며 서로 다른
단일 위치 사건만 missense다. 전하·소수성·분자량 등 physicochemical delta도
이 경우에만 계산할 수 있다.

### Same-AA/no-change

`D623D`는 protein no-change annotation이다. 해당 셀에 변이 annotation이 없다는
뜻의 `WT`와 같지 않으며, parser가 삭제하거나 missense로 세지 않는다.

### Nonsense

`E237*`, `E237X`, `E237Ter`는 모두 같은 immediate stop-gain이다. canonical
alternate는 `*`이며 deletion·frameshift로 재해석하지 않는다. train의 `A숫자*`
13,289건을 각각 `X`, `Ter`로 바꾼 전수 metamorphic 검사에서 canonical
equivalence 실패는 모두 0건이었다.

### Translation-initiation site

`M1T`, `M1I`, `M1R`, `M1L`, `M1V`, `M1K`는 start codon 영향 표기다. 단백질
간이표기만으로 p.0, downstream/upstream alternative initiation 또는 실제
ordinary missense를 결정할 수 없으므로 `start_codon_affected`, consequence
unknown으로 보존한다.

### Leading X와 leading stop

`Y204X`의 alternate X는 stop이지만 `X127C`의 reference X는 unknown reference
residue다. 후자를 stop-loss/extension으로 바꾸지 않는다. `*261*`도 정상
nonsense가 아니라 비표준·부분 표기로 unresolved 상태를 보존한다.

## Parser와 feature adapter

- 구현: `src/open_cancer/protein_substitution_semantics.py`
- definition version: `4.0.0`
- raw token과 normalized semantic token을 동시에 보존
- range replacement·deletion·insertion·delins·frameshift는 anchored grammar에서
  소비하지 않고 전용 parser로 넘김
- sample token count와 unique-gene count를 분리
- per-gene family `any/count`는 선택형 adapter로만 제공
- 기존 Feature Spec과 공식 실험의 기본 출력은 변경하지 않음

후속 공식 실험은 별도 Experiment Issue에서 기존 피처를 유지한 채 substitution
semantic family 하나만 추가해 canonical 5-fold로 평가한다. test prevalence와
Public LB를 규칙·threshold·weight 선택에 사용하지 않는다.

## 제한

- DNA/RNA 원인, transcript phase와 experimentally confirmed 여부를 추정하지 않음
- driver/passenger, pathogenicity, germline/somatic, actionability를 판정하지 않음
- mosaic, uncertain, splicing, extension 등 원본에 없는 HGVS 문법을 구현하지 않음
- leading X를 reference annotation 없이 임의 보정하지 않음
