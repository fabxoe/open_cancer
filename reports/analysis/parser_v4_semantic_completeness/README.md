# Parser v4 semantic completeness·support·collision 감사

> Issue: [#424](https://github.com/fabxoe/open_cancer/issues/424)
>
> 모델 학습이나 점수 생성 없이 parser-native baseline의 입력 schema를
> 고정하기 위한 의미·지원량 감사입니다.

## 결론

- train token `255,164`개와 test token `337,512`개를 하나도 버리지 않고 route했습니다.
- raw-token semantic collision: train `0` / test `0`
- normalized semantic collision: train `0` / test `0`
- canonical support gate 통과 family: `5`개, QC-only family: `12`개
- support가 부족한 올바른 사건은 parser에서 삭제하지 않고 native model의
  세부 피처만 QC-only 또는 상위 family 집계로 제한합니다.

## Family 지원량

| Route | Event | Train token | Train sample | Fold sample | Test token | 판단 |
|---|---|---:|---:|---|---:|---|
| `deletion` | `deletion` | 3 | 3 | `[1, 0, 0, 1, 1]` | 2,583 | `ANALYSIS_ONLY` |
| `delins` | `delins` | 0 | 0 | `[0, 0, 0, 0, 0]` | 511 | `ANALYSIS_ONLY` |
| `delins` | `nonsense` | 0 | 0 | `[0, 0, 0, 0, 0]` | 30 | `ANALYSIS_ONLY` |
| `delins` | `unresolved` | 0 | 0 | `[0, 0, 0, 0, 0]` | 3 | `ANALYSIS_ONLY` |
| `frameshift` | `frameshift` | 9,833 | 3,274 | `[644, 651, 666, 647, 666]` | 25,813 | `EXPERIMENT_ELIGIBLE` |
| `insertion` | `insertion` | 0 | 0 | `[0, 0, 0, 0, 0]` | 1,142 | `ANALYSIS_ONLY` |
| `range_replacement` | `range_replacement` | 109 | 101 | `[11, 22, 23, 24, 21]` | 20 | `EXPERIMENT_ELIGIBLE` |
| `range_replacement` | `stop_containing` | 39 | 34 | `[9, 7, 8, 2, 8]` | 9 | `ANALYSIS_ONLY` |
| `range_replacement` | `stop_gain` | 24 | 23 | `[3, 6, 7, 3, 4]` | 2 | `ANALYSIS_ONLY` |
| `range_replacement` | `synonymous` | 67 | 47 | `[5, 9, 15, 6, 12]` | 9 | `ANALYSIS_ONLY` |
| `substitution` | `missense` | 164,740 | 6,017 | `[1210, 1208, 1200, 1201, 1198]` | 201,353 | `EXPERIMENT_ELIGIBLE` |
| `substitution` | `no_change` | 66,883 | 5,251 | `[1049, 1044, 1034, 1057, 1067]` | 88,724 | `EXPERIMENT_ELIGIBLE` |
| `substitution` | `nonsense` | 13,289 | 3,266 | `[684, 662, 632, 634, 654]` | 16,316 | `EXPERIMENT_ELIGIBLE` |
| `substitution` | `start_codon_affected` | 0 | 0 | `[0, 0, 0, 0, 0]` | 572 | `ANALYSIS_ONLY` |
| `substitution` | `unknown_reference_substitution` | 0 | 0 | `[0, 0, 0, 0, 0]` | 390 | `ANALYSIS_ONLY` |
| `unresolved` | `frameshift` | 3 | 3 | `[0, 0, 0, 3, 0]` | 1 | `UNRESOLVED_ONLY` |
| `unresolved` | `other_unmappable` | 174 | 149 | `[31, 33, 25, 33, 27]` | 34 | `UNRESOLVED_ONLY` |

## Parse 상태

- train: `{'complete': 245152, 'partial': 9835, 'unresolved': 177}`
- test: `{'complete': 311176, 'partial': 25878, 'unresolved': 458}`

## 장문 sequence 길이

원문 sequence를 고차원 vocabulary로 만들지 않고 길이·stop·구조 같은
compact 의미만 native schema 후보로 사용합니다.

- train: `{'alternate_translated': {'count': 239, 'min': 0, 'p50': 2, 'p90': 2, 'p99': 2, 'max': 2}, 'first_new_candidate': {'count': 1217, 'min': 1, 'p50': 1, 'p90': 4, 'p99': 9, 'max': 13}}`
- test: `{'alternate_raw': {'count': 544, 'min': 1, 'p50': 1, 'p90': 61, 'p99': 794, 'max': 1148}, 'alternate_translated': {'count': 584, 'min': 0, 'p50': 1, 'p90': 47, 'p99': 794, 'max': 1148}, 'first_new_candidate': {'count': 22476, 'min': 1, 'p50': 1, 'p90': 1, 'p99': 1, 'max': 11}, 'inserted': {'count': 1142, 'min': 1, 'p50': 2, 'p90': 12, 'p99': 309, 'max': 309}}`

## 기존 5-family와의 관계

`missense/synonymous/nonsense/frameshift/complex`는 과거 호환용 lexical
bucket입니다. `complex`에 섞였던 deletion·insertion·delins·range와
unresolved 사건은 native schema에서 분리합니다. 전체 crosswalk 원본은
[`audit.json`](audit.json)의 `legacy_crosswalk`에 있습니다.

## 해석 제한

- `SUBCLASS`와 Public LB는 사용하지 않았습니다.
- test 집계는 coverage QC이며 feature 채택·threshold 선택에 사용하지 않았습니다.
- partial/unresolved 표기를 특정 생물학적 사건으로 강제 승격하지 않았습니다.
- 이 결과는 성능 결과가 아니며 실제 채택은 후속 canonical 5-fold에서 판단합니다.

## 다음 단계

이 감사 결과와 field coverage를 바탕으로 N2 unified parser-native feature
schema·adapter를 구현합니다. isoform·driver·pathway·Optuna는 아직 연결하지
않습니다.
