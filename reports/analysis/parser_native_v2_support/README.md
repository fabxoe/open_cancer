# Parser v4 native semantic adapter v2 지원 감사

> Issue: [#453](https://github.com/fabxoe/open_cancer/issues/453)
>
> 모델 학습 없이 train과 canonical fold 지원만으로 활성 열을 고정했습니다.

## 모델 활성 consequence

| consequence | route:event | train sample | fold sample |
|---|---|---:|---|
| `missense` | `substitution:missense` | 6,017 | `[1210, 1208, 1200, 1201, 1198]` |
| `no_change` | `substitution:no_change` | 5,251 | `[1049, 1044, 1034, 1057, 1067]` |
| `nonsense` | `substitution:nonsense` | 3,266 | `[684, 662, 632, 634, 654]` |
| `frameshift` | `frameshift:frameshift` | 3,274 | `[644, 651, 666, 647, 666]` |
| `range_replacement` | `range_replacement:range_replacement` | 101 | `[11, 22, 23, 24, 21]` |

## QC-only 원칙

deletion·insertion·duplication candidate·delins·range stop/no-change·
start-codon·unresolved 의미는 parser에서 삭제하거나 complex로 합치지 않습니다.
다만 현재 train/fold 지원 gate를 통과하지 못해 첫 v2 모델 행렬에는 넣지 않고
exclusive primary family와 raw token provenance로 보존합니다.

기존 mutation-presence는 항상 모델에 별도로 유지됩니다. target·test prevalence·
Public LB는 이 결정에 사용하지 않았습니다.
