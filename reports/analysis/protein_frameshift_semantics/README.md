# Protein frameshift compact grammar 의미 감사

> Task Issue: #383 · parser definition `4.0.0`

## 결론

원본에는 같은 frameshift family를 나타내는 세 가지 순서가 공존한다.

```text
REF + POSITION + fs          K16fs
REF + ALTSEQ + POSITION + fs WQ288fs, SDEL133fs
REF + POSITION + ALTSEQ + fs P953Hfs
```

고정 Ensembl release 116에서 팀 사례의 첫 residue가 해당 위치 reference와
일치했다.

- `NPM1 WQ288fs`: MANE/canonical position 288 = `W`; first-new peptide 후보 `Q`
- `ELF3 SDEL133fs`: MANE/canonical position 133 = `S`; first-new peptide 후보 `DEL`
- `CLSTN3 P953Hfs`: MANE/canonical position 953 = `P`; first-new peptide 후보 `H`

따라서 `SDEL`의 `DEL`은 deletion keyword로 소비하지 않는다. 다만 token-only
parser는 candidate만 구조화하고 fixed reference 일치 tier를 별도 필드로 보존한다.
DNA frame, 새 peptide 전체와 termination distance는 추정하지 않는다.

## 전체 원본 감사

| 항목 | train | test |
|---|---:|---:|
| frameshift occurrence | 9,833 | 25,813 |
| unique token | 6,546 | 15,035 |
| affected gene | 2,719 | 2,924 |
| `REF+POSITION+fs` | 8,616 | 3,337 |
| `REF+ALTSEQ+POSITION+fs` | 1,217 | 254 |
| `REF+POSITION+ALTSEQ+fs` | 0 | 22,222 |
| MANE/canonical/other isoform reference match | 9,728 (98.93%) | 22,379 (86.70%) |
| position-valid reference mismatch | 87 | 3,384 |

test에서는 train에 없던 `REF+POSITION+ALTSEQ+fs` 순서가 지배적이다. 이것은
SUBCLASS나 Public LB와 무관한 annotation-format shift다. Reference mismatch는
오류로 단정하지 않고 미수록 isoform·source annotation 차이를 포함하는 unresolved
evidence로 남긴다.

## 모델 표현 경계

- 세 문법 모두 `event_type=frameshift` presence에는 사용할 수 있다.
- reference/first-new peptide 피처는 `MANE_MATCH`, `CANONICAL_MATCH`,
  `OTHER_ISOFORM_MATCH`와 unresolved를 분리해야 한다.
- `WQ288fs == W288Qfs`처럼 문자열을 재작성하지 않는다. 구조화 의미 후보가
  같더라도 raw syntax provenance는 유지한다.
- `fs` 뒤 termination distance가 없는 원본에서 `fs*#`를 발명하지 않는다.
- 이번 Task는 parser/QC이며 모델 점수·History 행을 만들지 않는다.

## 재실행

```bash
uv run python scripts/audit_protein_frameshift_semantics.py
uv run pytest -q tests/test_protein_frameshift_semantics.py
```

Compact 원본 수치는 [`audit.json`](audit.json)에 기록한다.
