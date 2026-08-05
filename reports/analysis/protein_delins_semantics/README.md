# Protein delins semantic parser v4 감사

Issue [#399](https://github.com/fabxoe/open_cancer/issues/399)의 일반 Task 결과다.
기존 parser·Feature Spec은 유지하고 raw delins 구조와 stop-aware protein
consequence를 분리하는 opt-in parser/feature adapter를 구현했다.

## 실행과 실제 결과

```bash
uv run python scripts/audit_protein_delins_semantics.py
```

compact 원본은 [`audit.json`](audit.json)이다. train은 0건, test는 545건이며
환자 ID·원본 행·SUBCLASS는 저장하지 않았다.

| 구분 | occurrence | unique token |
|---|---:|---:|
| single-position | 144 | 81 |
| residue-range | 368 | 151 |
| unknown-reference X | 33 | 6 |

- 영향 gene 93개, sample 220개
- no-stop 508건, immediate stop 30건, peptide 뒤 stop 7건
- stop 37건 중 33건은 unknown-reference X 사례이며 표준 reference stop delins는 4건
- alternate length: min 1, median 1, p90 61, max 1,148
- net protein length change: min -4,071, median -1, max 326

초기 수동 정규식 집계의 “stop 9건”은 unknown-reference 33건을 문법 밖으로
분리했고 upper-case `TER`를 모호하게 다룬 예비값이었다. v4는 multi-letter
one-letter peptide 내부의 upper-case `TER`를 Thr-Glu-Arg로 보존하고, explicit
mixed-case suffix `Ter`와 `X/*`만 stop으로 canonicalize해 최종 37건을 확정했다.

## 의미 계약

- `E1117delinsGGRRIIK`: single-position delins, span 1, net +6
- `H1176_W1177delinsQ`: range delins, span 2, net -1
- `X541delinsX`: unknown reference와 immediate stop을 동시에 보존
- `K629delinsKX`: translated peptide `K`, stop offset 1, truncating delins
- first stop 이후 sequence는 provenance에만 남기고 translated peptide에서 제외
- DNA nucleotide frame, exon, allele, driver/pathogenicity를 추정하지 않음
- fixed reference 없이 3′ 위치를 이동하지 않음
- `SDEL133fs`, deletion, pure insertion과 range replacement는 소비하지 않음

Feature adapter는 token/unique-gene count, single/range/stop/unknown-reference gene
count와 reference span·translated alternate·net length 요약을 제공한다. train
feature가 전부 0이므로 이 family만을 위한 공식 5-fold 모델 실험은 강행하지 않고
OOD semantic QC로 종료한다.
