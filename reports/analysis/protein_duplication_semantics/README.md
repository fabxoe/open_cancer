# Protein tandem duplication semantic parser v4 감사

> Task Issue: [#395](https://github.com/fabxoe/open_cancer/issues/395)
>
> Parent parser roadmap: [#360](https://github.com/fabxoe/open_cancer/issues/360)
>
> 역할: target-independent insertion/duplication semantic QC
>
> Parser definition: `protein_duplication_semantics_v4` (`4.0.0`)

## 결론

대회 원문에는 literal `dup`가 한 건도 없지만, test의 `ins` 표기 상당수는
reference protein 바로 앞 서열을 다시 삽입한 **tandem duplication**이었다.

| 판정 | train | test | 의미 |
|---|---:|---:|---|
| 순수 insertion 전체 | 0 | 1,142 | `delins` 제외 |
| `REFERENCE_CONFIRMED` | 0 | 753 | 고정 reference에서 직접 N-terminal copy 확인 |
| `REJECTED` | 0 | 265 | 인접 경계지만 바로 앞 reference copy가 아님 |
| `UNRESOLVED_ISOFORM` | 0 | 121 | flanking/isoform 의미를 하나로 확정할 수 없음 |
| `STRONG_TOKEN_CANDIDATE` | 0 | 3 | 단일 left-copy이나 annotation 없음 |

`REFERENCE_CONFIRMED` 753건은 고유 판정 386개·178개 유전자에 해당한다.

- 단일 잔기 duplication: 385 occurrences / 196 unique records
- 범위 duplication: 368 occurrences / 190 unique records
- 3' rule로 원문 위치보다 오른쪽으로 이동한 관측 사례: 0

따라서 구형 parser의 `literal dup`와 generic `inframe_insertion` 분류만으로는
실제 duplication 의미를 복구할 수 없다. 반대로 모든 `ins`를 duplication으로
보아도 265건의 일반 insertion과 121건의 불확실 사례를 잘못 합치게 된다.

## 실제 데이터 문법

### 완전한 양쪽 경계 표기

test 1,092건은 다음 형태다.

```text
Q80_E81insQ
K745_E746insIPVAIK
```

양쪽 reference residue와 위치, inserted sequence를 모두 구조화할 수 있다.

### 오른쪽 residue가 생략된 부분 경계 표기

test 50건은 모두 `CPEB2`이며 다음 형태다.

```text
G679_680ins<sequence>
G682_683ins<sequence>
G709_710ins<sequence>
```

오른쪽 위치는 있지만 reference residue가 없다. parser는 이를 버리지 않고
`parse_status=partial`, `boundary_residues_complete=false`로 보존한다. fixed
reference에서 오른쪽 residue를 복원할 수 있지만, 50건 모두 삽입 서열이 바로
앞 reference copy와 같지 않아 duplication은 `REJECTED`됐다.

## Reference-confirmed 예시

### `AR Q80_E81insQ`

```text
raw syntax: Q80_E81insQ
source:     Q80
semantic:   Q80dup
status:     REFERENCE_CONFIRMED
isoform:    MANE Select
occurrences: 5
```

### `EGFR K745_E746insIPVAIK`

```text
raw syntax: K745_E746insIPVAIK
source:     I740_K745 = IPVAIK
semantic:   I740_K745dup
status:     REFERENCE_CONFIRMED
isoform:    MANE Select
occurrences: 1
```

### `MADCAM1 S261_P262insQEPPDTTS`

초기 수동 검토에서는 일반 insertion 가능성을 열어 두었으나, fixed Ensembl
reference의 `Q254_S261`이 정확히 `QEPPDTTS`여서 range duplication으로 확인됐다.

```text
semantic: Q254_S261dup
status: REFERENCE_CONFIRMED
occurrences: 2
```

## 손실 없는 두 계층

원문 insertion을 canonical duplication 문자열로 덮어쓰지 않는다.

```yaml
raw_token: K745_E746insIPVAIK
syntax_event_type: insertion
semantic_event_type: tandem_duplication
duplication_status: REFERENCE_CONFIRMED
duplication_source_start: 740
duplication_source_end: 745
```

이 구조는 annotation release나 isoform 선택이 바뀌어도 원문 provenance를
유지한다.

## 판정 순서

1. `delins`를 제외한 anchored insertion grammar를 파싱한다.
2. 양쪽 위치가 인접한지 확인한다.
3. stop 포함 insertion은 duplication 판정에서 제외한다.
4. 삽입 길이 `k`만큼 왼쪽 reference 서열을 추출한다.
5. 삽입 서열과 reference source가 완전히 같을 때만 tandem candidate로 둔다.
6. flanking residue를 reference와 대조한다.
7. MANE Select → Ensembl canonical → other isoform 순으로 판정한다.
8. 같은 우선순위 isoform끼리 canonical source가 다르면 확정하지 않는다.
9. 가능한 동등 표현을 모두 재생성하고 가장 C-terminal인 표현을 선택한다.

## 3' rule 결과

실제 test에서 reference-confirmed된 753건은 모두 원문 source 위치가 이미 가장
C-terminal인 동등 표현이었다. 따라서 실제 이동 사례는 0건이었다. 이는 규칙이
불필요하다는 뜻이 아니다. homopolymer synthetic fixture에서 raw `A2_A3insA`를
`A4dup`으로 이동시키는 결정적 테스트를 유지한다.

## 해석 제한

- train에는 순수 `ins`가 0건이므로 이 의미 family의 supervised 효과를 현재
  train에서 직접 학습할 수 없다.
- test의 753건을 확인했다는 사실은 parser completeness QC이며, test prevalence를
  이용한 feature 선택이나 threshold 조정이 아니다.
- sequence match는 해당 isoform이 사건을 설명할 수 있다는 뜻이지 실제 종양에서
  그 transcript가 발현됐다는 증거가 아니다.
- DNA/exon duplication 원인, allele, mosaic, total repeat copy number를 역추론하지
  않는다.
- stop·frameshift·extension·delins는 duplication보다 각자의 protein consequence를
  우선한다.
- `UNRESOLVED_ISOFORM`을 다수결로 확정하지 않는다.

## 고정 reference 계약

- Assembly/release: GRCh38 / Ensembl 116
- Manifest: `knowledge/ensembl_protein_duplication_semantics_v1.json`
- Compact index: `data/external/ensembl_release_116/competition_gene_isoform_index.json`
- Compact index SHA-256:
  `b9565339f1755d5b07e782c39064207310fa6c254b2e915a15492f4f38903daa`
- GTF SHA-256: `ed992f0eac7197d9627bda618f8f831ba355c95bd5d0796af785387d462828b6`
- peptide FASTA SHA-256: `9b43da92651b35814597af6a8b18f500b768679a49fa4678224f384917ce7668`

compact sequence index 자체는 Git에 커밋하지 않으며 manifest와 audit에 index
SHA-256을 기록한다.

## 산출물

- [`vocabulary_audit.json`](vocabulary_audit.json): train/test 전체 문법·상태 집계
- [`single_residue_candidates.json`](single_residue_candidates.json): 단일 삽입 의미 결과
- [`multi_residue_candidates.json`](multi_residue_candidates.json): 다중 삽입 의미 결과
- [`reference_validation.json`](reference_validation.json): 고정 snapshot·확정 판정
- [`three_prime_rule_audit.json`](three_prime_rule_audit.json): 실제 3' 이동 감사

환자 ID와 SUBCLASS는 저장하지 않았다.

## 재실행

```bash
uv run python scripts/audit_protein_duplication_semantics.py
uv run pytest -q tests/test_protein_duplication_semantics.py
```

## 모델 적용 결정

이번 Task에서는 공식 Feature Spec이나 기존 실험을 변경하지 않는다. train에서
duplication feature가 전부 0이므로 현재 상태에서는 별도 공식 모델 실험을
강행하지 않고, parser·OOD 진단 자산으로 보존한다. 향후 train과 test가 같은
annotation 문법으로 재구축되거나 train에도 해당 사건이 확보되면 별도 Experiment
Issue에서 한 family씩 canonical OOF Macro F1로 검증한다.

## 근거

- [HGVS Protein Duplication](https://hgvs-nomenclature.org/stable/recommendations/protein/duplication/)
- [EGFR exon 20 insertion/duplication 표기 참고](https://pmc.ncbi.nlm.nih.gov/articles/PMC10330422/)
