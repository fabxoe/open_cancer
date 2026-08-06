# EXP-563: Fold-safe residue-event concentration

EXP-527의 parser-v4·class-cosine 기준선에 outer-train에서만 학습한 유전자별
residue 위치 집중도 요약 4개를 추가한 canonical 5-fold 실험이다.

## 변경 내용

- parser-v4에서 위치 사용이 가능한 양의 residue만 사용
- residue를 50-aa 고정 bin으로 변환
- 한 환자의 같은 유전자·같은 bin은 한 번만 집계
- outer-train의 patient-gene-bin support가 20 이상이고 관측 bin이 2개 이상인
  유전자만 profile 생성
- validation·test에는 동결된 outer-train profile만 적용

추가한 피처는 다음 네 개다.

1. `sample__residue_concentration_top_bin_hit_fraction`
2. `sample__residue_concentration_mean_observed_bin_share`
3. `sample__residue_concentration_mean_gene_hhi`
4. `sample__residue_concentration_mean_gene_normalized_entropy`

## 결과

| 항목 | EXP-527 | EXP-563 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4468722707 | 0.4398386191 | -0.0070336516 |
| Fold 표준편차 | 0.0063793185 | 0.0074499693 | +0.0010706508 |
| Log Loss | 2.0274887085 | 2.0543270111 | +0.0268383026 |

Fold별 Macro F1은 `0.4367913`, `0.4437515`, `0.4518220`, `0.4310623`,
`0.4341083`이다. Macro F1과 Log Loss가 모두 악화되어 네 개의 평균 집중도
피처 조합은 **ARCHIVE**한다.

이 결과는 Hotspot-12, 상대 길이 Concentration, Green's contagion 또는
저-entropy 유전자 개수 규칙을 검증한 결과가 아니다. 평균 entropy·HHI가 강한
유전자별 집중 신호를 희석할 수 있으므로, 이진 hotspot 규칙은 별도 Task와
Experiment Issue에서 독립적으로 검증한다.

## 재현성

- Config: `configs/exp563_residue_event_concentration.yaml`
- Runner: `scripts/run_exp563_residue_event_concentration.py`
- Metrics: `reports/exp563_residue_event_concentration/metrics.json`
- Submission: `submissions/exp563_residue_event_concentration.csv`
- Submission SHA-256:
  `bc3803528e1953622df99800367182c2ad8e750120b312422714e309f31141bd`
- checkpoint 재추론 라벨 일치율: 100%
- test 확률 최대 절대 차이: `1.4016495e-7`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출

