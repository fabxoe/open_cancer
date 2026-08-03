# EXP-209 검증된 pathway 피처로 LightGBM 암종 분류

## 결론

EXP-125의 LightGBM 설정은 그대로 두고 Feature Spec만 `v1`에서
`v2-performance`로 교체했습니다. OOF Macro F1은 **0.4188739423**으로
EXP-125보다 `-0.0000338942` 낮아 사실상 동률이었지만, fold 표준편차가
`+0.0050815918` 악화돼 사전 채택 기준을 통과하지 못했습니다.

Log Loss는 `-0.0019725059`, Accuracy는 `+0.0012901145` 개선됐으나 Macro F1
개선 `+0.001`과 안정성 악화 `<0.002` 조건을 만족하지 못해 **ARCHIVE**합니다.

## 무엇이 달라졌나

- 모델·하이퍼파라미터: EXP-125 LightGBM과 동일
- Feature Spec: `v1` → `v2-performance`
- 추가 정보: EXP-096에서 검증한 fixed pathway burden 20개
- split: canonical stratified 5-fold, seed 42 유지
- class-balanced sample weight 유지
- Public LB: 미제출

## 결과

| 항목 | EXP-209 | EXP-125 | EXP-096 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4188739423 | 0.4189078364 | 0.4181153080 |
| Fold 표준편차 | 0.0131867650 | 0.0081051732 | 0.0094921177 |
| Accuracy | 0.4155781326 | 0.4142880181 | 0.4078374456 |
| Log Loss | 1.8208257360 | 1.8227982418 | 1.8369342089 |

| Fold | Macro F1 | Accuracy | Log Loss | best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.4220673434 | 0.4157937147 | 1.8468253179 | 145 |
| 1 | 0.4131394762 | 0.4048387097 | 1.8482715023 | 151 |
| 2 | 0.4010844170 | 0.4040322581 | 1.7930332546 | 144 |
| 3 | 0.4139076091 | 0.4185483871 | 1.8254046347 | 143 |
| 4 | 0.4409491801 | 0.4346774194 | 1.7905730030 | 135 |

## 해석

Pathway burden은 XGBoost 기준 EXP-096에서는 성능 후보였지만, LightGBM에서는
EXP-125 v1이 이미 포착한 정보를 추가로 강화하지 못했습니다. 평균 성능은
유지했으나 fold별 효과 방향이 일정하지 않아 이 조합을 추가 튜닝하거나 제출하지
않습니다.

## 재현성과 산출물

- Issue: [#209](https://github.com/fabxoe/open_cancer/issues/209)
- 실행 source commit: `ec05d217aeed555e3beb18151920a07fe275dd6f`
- Config: `configs/exp209_lightgbm_v2_performance.yaml`
- Resolved config: `reproducibility/exp209_lightgbm_v2_performance/config.resolved.yaml`
- Metrics: `reports/exp209_lightgbm_v2_performance/metrics.json`
- 제출 후보: `submissions/exp209_lightgbm_v2_performance.csv` (DACON 미제출)
- 제출 SHA-256:
  `b4ef2c1339e3c5783dcaa5a7f0882b17e1740de526b7fbd810ae706865eba32f`
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [`exp-209-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-209-repro-v1)

저장 checkpoint로 OOF와 test를 다시 추론해 라벨 100%, 확률 최대 절대 차이 0,
제출 CSV SHA-256 일치를 확인했습니다. Issue #260에서 원본 checkpoint 5개,
feature manifest, OOF/test 확률과 config를 deterministic bundle로 보존하고
원격 재다운로드 SHA-256 일치를 확인했습니다.
