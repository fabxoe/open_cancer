# Driver 보존 canonical protein-event signature 감사

> Task Issue: [#390](https://github.com/fabxoe/open_cancer/issues/390)
>
> Parent roadmap: [#360](https://github.com/fabxoe/open_cancer/issues/360)
>
> 역할: annotation multiplicity를 줄일 때 알려진 driver 의미를 잃지 않는지 확인

## 결론

`TEST_2438`의 EGFR cell에는 같은 `IPVAIK` peptide insertion을 서로 다른 protein
좌표로 적은 annotation 네 개가 있다.

```text
K692_E693insIPVAIK
K745_E746insIPVAIK
K478_E479insIPVAIK
K700_E701insIPVAIK
```

이들을 raw driver 네 개로 세어서는 안 되지만, 단순 중복 제거 과정에서 driver가
0개가 되어도 안 된다. 이번 감사 결과는 다음과 같다.

| 값 | 결과 |
|---|---:|
| raw annotation multiplicity | 4 |
| exact canonical match | 1 |
| reference-confirmed isoform projection | 2 |
| family-level only | 1 |
| independent canonical driver signature | 1 |
| driver presence | 1 |

즉, **4 annotation → 1 independent event**로 접으면서도 **driver presence=1**을
보존할 수 있다. 원문 네 token과 evidence tier는 모두 별도로 남는다.

## 세 evidence tier

### `EXACT`

`K745_E746insIPVAIK`는 Ensembl 116의 EGFR MANE Select
`ENST00000275493.7 / ENSP00000275493.2`에서 바로 앞 `I740_K745=IPVAIK`를
복제한다. canonical protein event는 `I740_K745dup`이다.

### `ISOFORM_PROJECTED`

`K692_E693insIPVAIK`와 `K700_E701insIPVAIK`는 각각 다른 Ensembl protein
isoform에서 같은 `IPVAIK` tandem-copy product가 reference-confirmed된다. 원문
좌표를 MANE 좌표라고 주장하지 않고, catalog reference로 projection한 사실을
명시한다.

### `FAMILY_LEVEL`

`K478_E479insIPVAIK`는 고정 reference에서 해당 좌표를 확정하지 못한다. 다만 같은
환자의 EGFR cell에서 gene과 inserted peptide가 고정 EGFR exon-19 IPVAIK family와
일치하므로 presence를 보존한다. 이것은 **exact coordinate equivalence가 아니다**.

## canonical signature

```text
ENSG00000146648.23
|ENST00000275493.7
|I740_K745dup
|EGFR_exon19_IPVAIK_inframe_duplication
```

signature는 raw token을 대체하는 문자열이 아니다. 다음 세 축을 직교 보존한다.

```yaml
driver_presence: 1
annotation_multiplicity: 4
equivalence_confidence: EXACT | ISOFORM_PROJECTED | FAMILY_LEVEL
```

## 문헌·reference 근거

- Ensembl GRCh38 release 116 fixed GTF/peptide snapshot
- [Oncogenic mutations within the β3-αC loop of EGFR/ERBB2/BRAF/MAP2K1](https://pmc.ncbi.nlm.nih.gov/articles/PMC7549570/)
- [EGFR-K745_E746insIPVAIK preclinical/clinical characterization](https://pmc.ncbi.nlm.nih.gov/articles/PMC10330422/)

고정 catalog와 출처·snapshot hash는
[`knowledge/known_driver_protein_events_v1.json`](../../../knowledge/known_driver_protein_events_v1.json)에
기록했다. 이는 포괄적 driver DB가 아니라 Issue #390에서 사전 고정한 한 사건의
semantic preservation catalog다.

## 기존 feature와의 중복

- pathway: EGFR는 기존 `RTK_RAS` pathway에 포함된다. 그러나 gene/pathway
  membership은 네 annotation이 한 `IPVAIK` 사건이라는 의미를 모른다.
- hotspot: 기존 EGFR hotspot은 T790과 L858 point substitution이다. I740-K745
  range duplication과 직접 겹치지 않는다.
- 따라서 signature는 기존 pathway/hotspot과 의미상 일부 연관은 있으나 동일
  feature가 아니다. 실제 모델 추가 여부는 별도 Experiment Issue에서 검증한다.

## 해석 제한

- 암종 label, test prevalence, Public LB로 catalog나 threshold를 고르지 않았다.
- isoform sequence match는 해당 isoform의 종양 발현을 증명하지 않는다.
- driver presence는 암종·치료 반응·actionability를 자동 확정하지 않는다.
- 이번 Task에서는 Feature Spec이나 기존 모델을 변경하지 않는다.
- train에 동일 annotation family가 없어 canonical OOF 성능 개선을 지금 주장하지
  않는다.

## 재실행

```bash
uv run python scripts/audit_driver_event_signature.py
uv run pytest -q tests/test_driver_event_signature.py
```

