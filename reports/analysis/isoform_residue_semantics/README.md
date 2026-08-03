# Track B isoform·잔기 의미 QC

> 분석 전용 결과입니다. `SUBCLASS`와 Public LB를 사용하지 않았고, 입력에
> transcript ID가 없으므로 어떤 isoform도 개별 변이의 정답이라고 단정하지
> 않습니다.

## 결론

- Ensembl GRCh38 release `116`을 고정 snapshot으로 사용했다.
- 대회 4,384개 gene symbol의 GTF mapping coverage는 `99.7947%`, protein
  sequence coverage는 `99.6807%`로 B1 의미 감사를 수행하기에 충분했다.
- 하지만 token 의미 분포가 train과 test에서 크게 달랐다. `MANE_MATCH`는
  `88.5035% → 53.4591%`로 감소하고, `OTHER_ISOFORM_MATCH`는
  `6.3234% → 26.6862%`, `POSITION_VALID_REF_MISMATCH`는
  `0.8818% → 6.1660%`, `COMPLEX_OR_UNMAPPABLE`은
  `4.1840% → 13.4351%`로 증가했다.
- 현재 max residue-position을 만드는 변이 gene-cell 중 저신뢰 max token 비율도
  train `5.3565%`, test `12.9649%`로 차이가 컸다.
- 이는 isoform 의미 QC가 필요했다는 강한 근거다. 이 차이를 보고 mask나
  threshold를 정하면 test 분포에 맞춘 transductive 최적화가 되므로, B2 정의는
  이 보고서 이전에 정한 세 후보만 유지한다. 2026-08-04 팀장이 Task #311과 그로부터
  파생되는 첫 번째 불확실 위치 마스크 실험에 한해 외부 annotation 사용을
  예외적으로 허용했다. 나머지 후보는 별도 Issue와 범위 확인 없이는 실행하지 않는다.

## 고정 annotation 계약

- Snapshot: `knowledge/ensembl_isoform_annotation_v1.json`
- Assembly/release: GRCh38 / Ensembl 116
- GTF SHA-256:
  `ed992f0eac7197d9627bda618f8f831ba355c95bd5d0796af785387d462828b6`
- peptide FASTA SHA-256:
  `9b43da92651b35814597af6a8b18f500b768679a49fa4678224f384917ce7668`
- GTF·FASTA와 compact sequence cache는 `data/external/`에만 보관하고 Git에
  커밋하지 않는다.
- token-level 결과는 `data/processed/isoform_residue_semantics/`에만 보관한다.

Ensembl은 MANE Select를 NCBI와 Ensembl이 합의한 동일 transcript로 설명하고,
Canonical transcript는 보존 exon, 발현, coding length와 외부 resource 근거를
종합해 선택한다고 설명한다.

- [Ensembl transcript flags](https://www.ensembl.org/info/genome/genebuild/transcript_quality_tags.html)
- [Ensembl Canonical](https://www.ensembl.org/info/genome/genebuild/canonical.html)
- [Ensembl data disclaimer](https://www.ensembl.org/info/about/legal/disclaimer.html)
- [Ensembl REST sequence endpoint](https://rest.ensembl.org/documentation/info/sequence_id)

## 상호 배타 token 범주

| 범주 | train 수 | train 비율 | test 수 | test 비율 | test-train |
|---|---:|---:|---:|---:|---:|
| `MANE_MATCH` | 225,829 | 0.885035 | 180,431 | 0.534591 | -0.350443 |
| `CANONICAL_MATCH` | 192 | 0.000752 | 440 | 0.001304 | +0.000551 |
| `OTHER_ISOFORM_MATCH` | 16,135 | 0.063234 | 90,069 | 0.266862 | +0.203628 |
| `POSITION_VALID_REF_MISMATCH` | 2,250 | 0.008818 | 20,811 | 0.061660 | +0.052842 |
| `OUTSIDE_ALL_KNOWN_ISOFORMS` | 82 | 0.000321 | 416 | 0.001233 | +0.000911 |
| `COMPLEX_OR_UNMAPPABLE` | 10,676 | 0.041840 | 45,345 | 0.134351 | +0.092511 |

전체 token은 train `255,164`, test `337,512`개다. MANE/Canonical 길이를
넘지만 다른 알려진 isoform의 reference residue에는 맞는 token은 train 488개
(`0.1912%`), test 1,414개(`0.4189%`)였다. 따라서 대표 transcript 길이만으로
out-of-range 값을 오류 처리하면 실제 alternative isoform과 부합할 수 있는 일부
token을 잘못 제거한다.

## gene mapping과 non-protein-coding 표기

- GTF symbol 미매핑 9개: `CENPJ`, `CIR1`, `GPR182`, `ILVBL`, `METTL7B`,
  `NDUFA4`, `PRPF4B`, `SLC22A18`, `THEG`
- GTF상 non-protein-coding으로 매핑된 대회 열 7개: `CAST`, `CROCCP2`,
  `HBBP1`, `MALL`, `PTTG3P`, `PVT1`, `XIST`
- 해당 non-protein-coding gene의 변이 gene-cell은 train 62개, test 127개였다.

동일 symbol이 annotation release 사이에서 바뀌거나 pseudogene/lncRNA 열에 단백질
변이가 적힌 현상은 원 데이터가 사용한 annotation pipeline을 알 수 없으므로
오류라고 단정하지 않는다.

## 분류 규칙

simple substitution token(`A123T`, `A123*`, synonymous 포함)의 위치와 reference
amino acid만 대조한다. 우선순위는 다음과 같다.

```text
MANE_MATCH
→ CANONICAL_MATCH
→ OTHER_ISOFORM_MATCH
→ POSITION_VALID_REF_MISMATCH
→ OUTSIDE_ALL_KNOWN_ISOFORMS
→ COMPLEX_OR_UNMAPPABLE
```

frameshift, range change, deletion·insertion 등 복합 token은 reference sequence와
단일 위치를 안정적으로 대조할 수 없으므로 `COMPLEX_OR_UNMAPPABLE`로 둔다.

## 해석 경계와 다음 결정

- sequence match는 해당 token을 설명할 수 있는 알려진 sequence가 존재한다는
  뜻이지 실제 종양에서 그 transcript가 발현됐다는 뜻이 아니다.
- mismatch/outside는 parser 오류, 다른 annotation release, 미수록 isoform 또는
  원 실험의 annotation 차이일 수 있다.
- train/test 분포 차이는 QC로만 기록한다. 이 결과를 보고 범주 정의, mask 또는
  threshold를 조정하지 않는다.
- 첫 B2 후보인 불확실 위치 mask는 EXP-313에서 채택 gate를 통과했다. 이후 팀장
  추가 승인에 따라 B2-2 sample 범주 요약은 별도 manifest revision과 Task #315로
  진행한다. isoform-relative coarse bin은 여전히 별도 범위 검토 후에만 연다.
- 외부 환자 자료나 암종별 빈도 annotation은 여전히 금지하며, test 분포를 보고
  범주·threshold를 변경하지 않는다.

## 재현

```bash
uv run python scripts/audit_isoform_residue_semantics.py --download --rebuild-cache
```

Machine-readable 결과는 [audit.json](audit.json)에 있으며, 전체 token table은
Git에 넣지 않는다.
