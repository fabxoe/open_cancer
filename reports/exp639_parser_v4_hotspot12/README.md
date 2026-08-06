# EXP-639 — Parser-v4 fold-safe Hotspot-12

## 요약

EXP-527에 parser-v4 missense residue Hotspot-12 family만 추가한 canonical 5-fold 실험입니다.

- OOF Macro F1: `0.4546505201`
- EXP-527 대비: `+0.0077782494`
- Log Loss: `2.0274887085 → 1.8732490540`로 개선
- fold std: `0.0063793185 → 0.0112293085`로 `+0.0048499900` 악화
- 최대 클래스 하락: LGG `-0.1122892545`
- 재현 상태: `INFERENCE_VERIFIED`

전체 점수와 확률 품질은 좋아졌지만, 사전 고정 안정성·클래스 붕괴 기준을 통과하지 못했습니다. 따라서 단독 주력 모델로 채택하지 않고 다양성·앙상블 후보로 보존합니다.

## 변경 변수

부모 EXP-527의 split, XGBoost, seed, weight, checkpoint 정책을 그대로 유지했습니다. 유일한 변경은 다음 fold-safe family 추가입니다.

- parser-v4 `substitution:missense`의 resolved positive residue position
- patient-gene-position 중복 제거
- outer-train event support 5 이상
- inclusive width 12
- 대표 창 fraction 40% 이상
- validation/test에는 outer-train에서 확정한 창만 적용

추가 피처:

- 유전자 4,384개의 `gene__<gene>__hotspot12_hit`
- `sample__hotspot12_gene_count`
- `sample__hotspot12_event_count`
- `sample__hotspot12_fraction`

## Support audit

모델 실행 전 #632에서 별도 감사를 수행했습니다.

- fold별 선택 유전자: 223~241개
- 평균 pairwise selected-gene Jaccard: `0.3236954807`
- 5개 fold 공통 선택: 35개
- 5개 fold 동일 정확한 창: 16개

선택 집합은 중간 정도로만 안정적이므로 생물학적 고정 hotspot catalog가 아니라 fold-local 반복 위치 통계로 해석해야 합니다.

## 결과

| fold | Macro F1 | best iteration |
|---:|---:|---:|
| 0 | 0.4385802599 | 117 |
| 1 | 0.4572089860 | 40 |
| 2 | 0.4724204513 | 34 |
| 3 | 0.4476187367 | 196 |
| 4 | 0.4522269760 | 164 |

| 지표 | EXP-527 | EXP-639 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4468722707 | 0.4546505201 | +0.0077782494 |
| fold std | 0.0063793185 | 0.0112293085 | +0.0048499900 |
| Accuracy | 미기재 | 0.4375100790 | - |
| Log Loss | 2.0274887085 | 1.8732490540 | -0.1542396545 |

큰 클래스 하락:

- LGG: `-0.1122892545`
- KIRC: `-0.0512497272`
- PAAD: `-0.0344795082`

## 판정

사전 채택 조건과 비교하면:

- Macro F1 `+0.001`: 통과
- fold std 증가 `<0.002`: 실패
- Log Loss 명백한 악화 없음: 통과, 오히려 개선
- 클래스 F1 하락 `>-0.05`: 실패(LGG, KIRC)
- `INFERENCE_VERIFIED`: 통과

판정은 **`ARCHIVE_AS_PRIMARY / KEEP_ENSEMBLE_CANDIDATE`**입니다.

Hotspot-12는 전역 성능과 Log Loss를 의미 있게 개선했으므로 정보는 있습니다. 그러나 LGG·KIRC를 희생하고 fold 변동성을 키웠기 때문에 단독 채택은 위험합니다. threshold를 OOF/Public에 맞춰 변경하지 않으며, 후속 작업은 EXP-527/EXP-628 등과 OOF 오류 상관을 감사한 뒤 사전 고정 블렌드 후보로만 검토합니다.

## 재현

```bash
uv run python scripts/run_exp639_parser_v4_hotspot12.py
```

- config: `configs/exp639_parser_v4_hotspot12.yaml`
- metrics: `reports/exp639_parser_v4_hotspot12/metrics.json`
- submission: `submissions/exp639_parser_v4_hotspot12.csv`
- comparison: `reproducibility/exp639_parser_v4_hotspot12/comparison.json`

저장 checkpoint 재추론으로 제출 SHA-256, 라벨과 확률이 허용 오차 안에서 일치했습니다.
