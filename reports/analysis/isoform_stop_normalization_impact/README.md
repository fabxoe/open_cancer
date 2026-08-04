# Stop 표기 정규화 전후 MANE·isoform 의미 분포 재감사

> Issue #375의 target-independent 로컬 의미 감사다. Ensembl release 116,
> 전체 token denominator와 기존 category 우선순위를 고정하고 simple stop
> alternate `*`, `X`, `Ter`의 표기만 통일했다.

## 결론

기존 Track B 감사에서 MANE_MATCH는 train `88.5035%`, test `53.4591%`였다.
EXP-369의 stop 정규화 계약을 적용하면 train은 그대로이고 test는 `55.2520%`로
`+1.7928%p` 회복된다. 따라서 train-test MANE 격차는 `35.0443%p`에서
`33.2515%p`로 `1.7928%p` 줄었다.

stop 정규화는 MANE 격차 전체를 설명하지 않는다. 다만 test에서 기존
`COMPLEX_OR_UNMAPPABLE`이던 14,332개 token을 알려진 isoform 대조 범주로
복구했고, 이 범주의 비율을 `13.4351%`에서 `9.1887%`로 `4.2464%p`
낮췄다. EXP-369 Public 상승과 함께 보면 전체 coverage보다 암종 판별력이 강한
stop-gain token의 의미 복구가 중요했다는 증거다.

## 감사 계약

- Ensembl snapshot: GRCh38 release 116
- annotation cache:
  `data/external/ensembl_release_116/competition_gene_isoform_index.json`
- 입력 token table:
  - `data/processed/isoform_residue_semantics/train_token_semantics.csv`
  - `data/processed/isoform_residue_semantics/test_token_semantics.csv`
- denominator 고정: train 255,164개, test 337,512개 token
- category 우선순위와 reference residue 대조 규칙 고정
- 유일한 변경: simple stop alternate `X`, `Ter`를 `*`로 canonicalize
- SUBCLASS 미사용
- Public LB는 규칙·threshold 정의에 미사용
- isoform을 실제 발현 transcript의 정답으로 간주하지 않음

## MANE_MATCH 변화

| 구분 | Train | Test | Train-test 격차 |
|---|---:|---:|---:|
| v1 parser | 88.5035% | 53.4591% | 35.0443%p |
| stop 정규화 후 | 88.5035% | 55.2520% | 33.2515%p |
| 변화 | 0.0000%p | +1.7928%p | -1.7928%p |

train에는 정규화 대상 simple `X/Ter` stop token이 없었으므로 분포가 바뀌지
않았다. test에서는 14,355개 token의 표기가 정규화됐다.

## Test category 변화

| 범주 | 정규화 전 | 정규화 후 | 변화 |
|---|---:|---:|---:|
| MANE_MATCH | 53.4591% | 55.2520% | +1.7928%p |
| CANONICAL_MATCH | 0.1304% | 0.1333% | +0.0030%p |
| OTHER_ISOFORM_MATCH | 26.6862% | 28.3670% | +1.6808%p |
| POSITION_VALID_REF_MISMATCH | 6.1660% | 6.9316% | +0.7656%p |
| OUTSIDE_ALL_KNOWN_ISOFORMS | 0.1233% | 0.1274% | +0.0041%p |
| COMPLEX_OR_UNMAPPABLE | 13.4351% | 9.1887% | -4.2464%p |

## 기존 complex token의 전이

| 정규화 후 범주 | token 수 |
|---|---:|
| MANE_MATCH | 6,051 |
| OTHER_ISOFORM_MATCH | 5,673 |
| POSITION_VALID_REF_MISMATCH | 2,584 |
| OUTSIDE_ALL_KNOWN_ISOFORMS | 14 |
| CANONICAL_MATCH | 10 |
| 여전히 COMPLEX_OR_UNMAPPABLE | 23 |

14,355개 정규화 대상 중 14,332개가 단일 위치·reference residue를 가진
해석 가능한 범주로 이동했다. 그중 MANE 일치는 42.15%이고, 다른 isoform 일치는
39.52%였다. `X` stop을 무조건 MANE라고 가정한 것이 아니라, 표기만 정규화한 뒤
각 gene의 실제 Ensembl protein sequence와 다시 대조한 결과다.

## 해석

1. **stop parser는 중요한 병목이었다.** EXP-229와 EXP-369의 OOF가 완전히
   같고 Public만 `+0.0204345510` 상승했으므로 annotation notation shift에 대한
   강한 인과 증거가 있다.
2. **MANE 격차 대부분은 남아 있다.** stop 정규화가 회복한 것은 1.7928%p이며,
   남은 33.2515%p에는 alternative isoform, reference mismatch, annotation
   release·pipeline 차이와 다른 복합 표기가 포함된다.
3. **MANE 비율 자체를 최적화하지 않는다.** transcript ID가 없는 데이터에서
   MANE를 실제 발현 transcript의 정답으로 단정할 수 없다. 확실한 표기 동등성만
   parser contract로 승격하고, 나머지는 독립 ablation으로 검증한다.
4. **다음 parser 작업은 분리한다.** 음수 위치·부분 표기 sanitation, frameshift,
   deletion/insertion/delins와 synonymous 처리는 stop 규칙과 섞지 않는다.

## 재현

```bash
uv run python scripts/audit_isoform_stop_normalization_impact.py
```

Machine-readable 결과는 [audit.json](audit.json)에 저장한다. 원본 Ensembl
snapshot과 전체 token table은 저장소에 커밋하지 않는다.
