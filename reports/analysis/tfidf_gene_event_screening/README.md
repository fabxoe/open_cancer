# Parser v4 gene-event TF-IDF 단일-fold screening

> Issue #498의 분석 전용 결과입니다. 공식 5-fold 실험이나 제출 결과가 아닙니다.

## 설계

- canonical validation fold: `0`
- 행: train `4960`, validation `1241`
- parser-v4 native gene-event 피처: `30,688`개
- sample aggregate 제외, validation/test IDF fit 금지
- 공통 모델: `LinearSVC(C=1.0, class_weight=balanced)`

## 결과

| arm | Macro F1 | raw 대비 | Accuracy | 시간(초) |
|---|---:|---:|---:|---:|
| raw_binary | 0.2682291001 | +0.0000000000 | 0.2892828364 | 0.62 |
| row_l2_only | 0.3156477366 | +0.0474186366 | 0.3311845286 | 0.26 |
| tfidf_row_l2 | 0.3101838942 | +0.0419547941 | 0.3190975020 | 0.27 |

## 해석 제한

- 이 fold에서 최고 arm은 `row_l2_only`입니다.
- 단일 fold screening이므로 채택·기각 또는 EXPERIMENT_HISTORY 갱신에 사용하지 않습니다.
- TF-IDF 효과와 행 정규화 효과를 분리하기 위해 row-L2-only arm을 함께 두었습니다.
- 유망하면 새 Experiment Issue에서 canonical 5-fold로 재검증해야 합니다.

## 재실행

```bash
uv run python scripts/screen_parser_v4_gene_event_tfidf.py --fold 0
```
