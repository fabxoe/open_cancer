# Isoform annotation multiplicity·독립 사건 grouping 감사

> Task Issue: #389 · grouper `1.0.0`

## 목적과 세 가지 count

한 genomic event가 여러 transcript/isoform protein 좌표로 반복 기록될 가능성을
조사한다. 정보 손실을 피하기 위해 다음 값을 함께 보존한다.

```text
raw_annotation_count
strict_event_count       # exact normalized token만 중복 제거
likely_event_count       # gene+family+ref/alt signature 후보 grouping
```

원본에는 transcript/genomic event ID가 없으므로 **confirmed group은 0개**다.
likely group은 모델 입력이 아니라 감사 후보이며 raw token·position을 모두 보존한다.

## 전체 결과

| 항목 | train | test |
|---|---:|---:|
| non-WT gene cell | 218,893 | 198,930 |
| likely multiplicity cell | 0 | 4,666 |
| exact duplicate 감소 가능 수 | 6,100 | 218 |
| 추가 likely 감소 가능 수 | 0 | 12,178 |

train에 likely multiplicity가 0이고 test에만 대규모로 존재한다. 이는 label이나 Public
LB와 무관한 annotation-format OOD 현상이며, canonical OOF만으로 collapse 효과를
학습·검증할 수 없다. 따라서 이 Task에서 기본 burden·mutation-type·position 피처를
변경하지 않는다.

## 팀 사례

### IARS1 / TEST_0063

`Y→C frameshift` 12개 좌표는 strict 12개, likely signature 1개다. 하나의 사건으로
확정하지 않고 `likely`, raw multiplicity 12를 함께 기록한다.

### CPEB2 / TEST_0027

5개 insertion과 별도 frameshift 1개가 있다. 삽입서열이 같은 3개와 같은 2개가
각각 likely group을 이루므로 strict 6개에서 likely 3개가 된다. 서로 다른 두 삽입
서열은 합치지 않는다.

### EGFR / TEST_2438

같은 `IPVAIK` insertion이 네 protein 좌표에 존재해 strict 4개, likely 1개다.
driver presence 보존과 reference-aware equivalence 확정은 후속 #390의 책임이다.

### TMEM97

동일 장문 delins가 여러 test 환자에서 반복되는 것은 한 환자 안의 annotation
multiplicity와 다르다. cross-sample recurrence로만 기록하고 환자 사이에서 절대
collapse하지 않는다. Compact audit에는 원문 대신 prefix·길이·SHA-256·occurrence를
남긴다.

## 안전 계약

- raw annotation과 위치를 삭제하지 않는다.
- exact/likely/confirmed를 구분하며 confirmed는 만들지 않는다.
- 서로 다른 inserted sequence와 unrelated substitution은 합치지 않는다.
- train/test prevalence를 grouping rule 또는 모델 weight 선택에 사용하지 않는다.
- 모델 변경이 필요하면 별도 Experiment Issue에서 representation 하나만 비교한다.
- known driver presence 보존 검증 전에는 likely count로 기본 피처를 대체하지 않는다.

## 재실행

```bash
uv run python scripts/audit_isoform_annotation_multiplicity.py
uv run pytest -q tests/test_isoform_annotation_multiplicity.py
```

Compact 결과는 [`audit.json`](audit.json)에 기록한다.
