# N6 — isoform substitution eligibility: legacy vs parser v4 (Task #493)

`analysis_only`, target-independent. 재실행:

```bash
uv run python scripts/audit_isoform_v4_eligibility_diff.py
```

## 배경

로드맵(#422 §12) N6 이후 재검증 순서 1번: "isoform mask: frozen Ensembl
snapshot, parser v4 position/reference eligibility만 변경". N5(EXP-479)
동결 완료로 착수 조건이 갖춰졌다.

`isoform_relative_position.py`(`IsoformRelativePositionTransformer`)와
`isoform_semantics.py`(`classify_token_semantics`, `isoform_position_mask.py`가
소비)가 substitution 토큰의 position/reference eligibility를 legacy 어휘
정규식(`mutation_features._SUBSTITUTION`)으로 판정해왔다. 이 정규식은 EXP-374
lineage가 사용하는 메인 파이프라인의 stop 표기 정규화(EXP-369, `X`/`*`/`Ter`
동일 의미)와 무관하게 유지된 **별도의, 더 오래된 정규식**이었다.

## 변경 범위

- Ensembl annotation(우선순위 MANE→canonical→other, tie-break, bin 계산)은
  변경하지 않았다.
- isoform 매칭을 substitution 이외 family로 확장하지 않았다.
- `isoform_relative_position.py`·`isoform_semantics.py`에서 legacy
  `parse_mutation_token`/`ParsedMutationToken` 기반 eligibility 판정을
  전부 제거하고 `mutation_parser_contract.route_protein_mutation`으로
  교체했다(타입 전용 import는 공용 `PositionTokenTransformer`/
  `PositionTokenFilter` 인터페이스 계약이라 유지).
- `isoform_position_mask.py`(EXP-313/374/392가 실제로 사용하는 마스크)는
  `classify_token_semantics`를 그대로 호출하므로 별도 수정 없이 이 교체
  효과를 자동으로 물려받는다.
- eligibility 정의: `route == "substitution"`, `parse_status == "complete"`,
  `event_type in {missense, no_change, nonsense}`. legacy에 없던 두 구분을
  명시적으로 배제한다 — `start_codon_affected`(M1), `unknown_reference_substitution`
  (참조가 leading `X`).

## 감사 방법

train+test 전체에서 `WT`가 아닌 모든 (gene, raw token) 고유 쌍을 모아
(고유 486,399쌍, 4,363개 유전자) legacy eligibility와 v4 eligibility를
비교했다. SUBCLASS·Public LB는 사용하지 않았다.

## 결과

| 방향 | 건수 | 전체 대비 비율 | 원인 |
|---|---:|---:|---|
| `v4_only`(legacy는 제외, v4는 포함) | 10,397 | 2.1375% | 전부 `legacy_shape_complex` — legacy 정규식이 alternate에 `X`를 허용하지 않아 `R507X` 같은 stop-as-X 표기를 substitution으로 인식하지 못했다 |
| `legacy_only`(legacy는 포함, v4는 제외) | 336 | 0.0691% | 전부 `start_codon_affected` — M1(개시코돈) 치환을 legacy는 구분 없이 일반 missense로 취급했다 |

### 카테고리 전환 (기존 → 신규)

| 전환 | 건수 |
|---|---:|
| COMPLEX_OR_UNMAPPABLE → MANE_MATCH | 5,034 |
| COMPLEX_OR_UNMAPPABLE → OTHER_ISOFORM_MATCH | 4,018 |
| COMPLEX_OR_UNMAPPABLE → POSITION_VALID_REF_MISMATCH | 1,303 |
| MANE_MATCH → COMPLEX_OR_UNMAPPABLE | 335 |
| COMPLEX_OR_UNMAPPABLE → OUTSIDE_ALL_KNOWN_ISOFORMS | 13 |
| COMPLEX_OR_UNMAPPABLE → CANONICAL_MATCH | 10 |

## 해석

**주된 발견은 M1 문제가 아니라 X-표기 nonsense 토큰 10,397건이 isoform
position 매칭에서 통째로 빠져 있었다는 것**이다. `R507X`처럼 alternate를
`X`로 쓴 stop 표기는 EXP-369가 메인 파이프라인의 mutation-type/presence
피처에서는 이미 정규화했지만, isoform 전용 legacy 정규식은 이 정규화를
전혀 반영하지 않은 채 계속 "complex"로 분류해 `COMPLEX_OR_UNMAPPABLE`(=
position 미신뢰, mask에서 제외)로 취급해왔다. v4로 교체하니 이 중
10,378건이 실제로 유효한 위치로 재분류됐다(대부분 MANE/OTHER/POSITION_VALID
매칭 — 즉 "존재하지만 신뢰 못 함"이 아니라 "애초에 안 보이던" 토큰들이었다).

반대 방향(M1 336건)은 예상했던 대로 legacy가 개시코돈 치환을 구분하지
못해 생긴 과대포함이며, v4가 이를 올바르게 배제한다.

두 diff 모두 로드맵이 말한 "parser v4 position/reference eligibility만
변경"의 정의 그대로다 — Ensembl annotation이나 매칭 로직은 손대지 않았다.

## Go/No-Go — 후속 Experiment 필요성

전체 토큰의 2.14%가 새로 유효해진 것은 **작지 않은 규모**이며, 특히
EXP-313/374/392가 쓰는 `isoform_position_mask`(TRUSTED_POSITION_CATEGORIES
=MANE_MATCH/CANONICAL_MATCH/OTHER_ISOFORM_MATCH 열에만 residue-position을
채움)에 직접 영향을 준다. **후속 Experiment Issue를 열어 EXP-374/392 lineage를
이 수정된 isoform 코드로 재실행하고 canonical 5-fold OOF 변화를 측정할 것을
제안한다.** 이 Task 자체는 코드 교체와 감사까지만 수행하며 재학습·EXP-ID는
포함하지 않는다(`RUN_MODE=explore`).

## 제약

- SUBCLASS·Public LB는 감사에 사용하지 않았다.
- 기존 EXP-313/327/374/392 등 결과와 `EXPERIMENT_HISTORY.md`는 수정하지
  않았다(로드맵 §15).
- Ensembl annotation cache·manifest는 기존 팀장 승인 자산을 그대로
  재사용했다.
