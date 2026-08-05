# Multi-letter frameshift·range replacement parser 감사

> Task Issue: [#378](https://github.com/fabxoe/open_cancer/issues/378)
>
> 역할: target-independent parser semantics audit
>
> Parser definition: `annotation_invariant_mutation_parser_v3` (`3.0.0`)

## 목적

기존 parser의 substring 판정은 아미노산 서열에 포함된 `DEL`·`FS`를 event keyword로
오인할 수 있다. 또한 `숫자_숫자REF>ALT` 표기를 모두 generic complex로 합치면 일반
구간 치환, protein no-change, 번역 가능한 prefix 뒤 stop, immediate stop이 한 범주에
섞인다.

이번 Task는 모델 점수를 만들지 않고 다음을 고정했다.

- complete grammar가 일치한 뒤에만 `del`·`ins`·`fs` 의미를 부여한다.
- source structure와 protein consequence를 별도 필드로 보존한다.
- stop 이후 문자는 raw provenance에는 남기되 번역된 alternate sequence에서 제외한다.
- multi-letter frameshift prefix는 source-format 근거 없이 reference·alternate 의미를
  추정하지 않는다.
- parser v1과 기존 공식 실험 결과는 변경하지 않는다.

## 팀장 제공 실제 사례

| 원문 token | 유전자(train) | v3 해석 |
|---|---|---|
| `1436_1437SI>RF` | `CREBBP` | 일반 2-residue range replacement |
| `59_60HY>QH` | `CRLF2` | 일반 2-residue range replacement |
| `300_301LE>F*` | `HGF` | `F` 번역 후 position 301 stop |
| `2126_2127WE>*K` | `SPTB` | position 2126 immediate stop, 뒤 `K` 미번역 |
| `236_237LL>LL` | `SLAMF7` | protein no-change/synonymous range |
| `197_198YQ>**` | `CTCF` | position 197 immediate stop, 두 번째 `*` 미도달 |
| `SDEL133fs` | `ELF3` | position 133 frameshift, `SDEL` prefix 의미는 unresolved |

각 사례는 train에서 1회씩 존재했고 test에는 동일 exact token이 없었다. 이는 fixture를
선정하기 위한 사실일 뿐 feature threshold나 제출 설정에 사용하지 않았다.

## 전체 감사 결과

### Multi-letter-prefix frameshift

| 항목 | train | test |
|---|---:|---:|
| 발생 수 | 1,218 | 254 |
| 고유 token | 999 | 239 |
| 영향받은 유전자 | 663 | 201 |

- v1은 전부 frameshift로 분류한다.
- v3도 anchored `...숫자fs` grammar가 일치한 1,472건을 전부 frameshift로 분류한다.
- `SDEL133fs`의 `DEL`은 deletion keyword로 해석하지 않는다.
- `SDEL`, `WQ`, `LGKSSSVTRLYK` 같은 prefix의 내부 의미는 transcript/source-format
  증거 없이 분해하지 않고 `unresolved_multiletter_prefix`로 남긴다.
- 명시된 frameshift coordinate는 보존하지만 prefix 전체를 reference sequence라고
  주장하지 않는다.

### Range replacement

| 의미 | train | test |
|---|---:|---:|
| 일반 아미노산 구간 치환 | 109 | 20 |
| reference=alternate protein no-change | 67 | 9 |
| 번역 가능한 prefix 뒤 stop | 39 | 9 |
| 첫 alternate 위치 immediate stop | 24 | 2 |
| reference 길이와 coordinate span 불일치 | 0 | 0 |
| 전체 | 239 | 40 |

파서 v3은 다음 직교 의미를 보존한다.

```text
source_structure
reference_sequence / alternate_sequence
translated_alternate_sequence
contains_stop / first_stop_offset / first_stop_position
post_stop_sequence
protein_no_change / protein_truncating
range_reference_span_valid
```

`721_722LA>FS`의 alternate `FS`는 Phe-Ser이며 frameshift suffix가 아니다. 반대로
`SDEL133fs`는 token 전체가 anchored frameshift grammar와 일치하므로 frameshift다.

## 모델 활용 원칙

이번 PR은 parser·감사만 구현하고 공식 Feature Spec을 변경하지 않는다. 후속 공식
실험은 새 Experiment Issue에서 한 변수씩 검증한다.

1. 기존 complex·mutation-presence를 유지한 채 `range_stop`/`range_no_change`
   직교 indicator만 추가한다.
2. 효과가 확인되면 pathway truncating 집계에 range stop을 포함하는 별도 ablation을
   수행한다.
3. multi-letter frameshift prefix는 의미가 확정되기 전 exact alternate peptide나
   reference residue 피처로 사용하지 않는다.
4. raw token 수 대신 unique-gene count를 우선하며 같은 사건을 구조·결과 양쪽에서
   셀 때 weighting 변화임을 명시한다.

## 해석 제한

- `fs` 표기만으로 실제 새 reading-frame peptide나 stop까지의 거리를 복원하지 않는다.
- immediate stop 뒤 문자열은 실제 번역 잔기로 사용하지 않는다.
- protein no-change는 DNA 변이가 없다는 뜻이 아니다.
- Ensembl annotation은 Issue #378 범위에서 사용하지 않았다.
- train/test prevalence·SUBCLASS·Public LB를 grammar 결정에 사용하지 않았다.
- 이 감사만으로 성능 향상을 주장하지 않는다.

## 재실행

```bash
uv run python scripts/audit_multiletter_frameshift_range_parser.py
uv run pytest -q tests/test_robust_mutation_parser.py \
  tests/test_mutation_notation_invariance.py
```

Compact 원본 결과는 [`audit.json`](audit.json)에 있다. 환자 ID와 행별 값은 저장하지
않았다.
