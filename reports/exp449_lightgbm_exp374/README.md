# EXP-449 LightGBM on EXP-374 feature set

## 결론

EXP-374의 정확히 동일한 feature set 위에서 LightGBM(EXP-209 고정 하이퍼파라미터,
재튜닝 없음)을 학습했다. **단독 OOF는 EXP-374(XGBoost)보다 낮지만
(-0.0047359353), 이는 예상된 결과다** — 이 실험의 목적은 XGBoost를
이기는 게 아니라 블렌드용 다양성 있는 모델을 확보하는 것이다.

## 실험 설계

- Issue: [#449](https://github.com/fabxoe/open_cancer/issues/449)
- 부모: EXP-374(feature set), EXP-209(LightGBM 하이퍼파라미터, 재사용만)
- `run_exp374_stop_isoform_residue_mask.build_fold_features()`를 그대로
  재사용해 stop-notation parser·Ensembl isoform mask·pathway family·
  hotspot-34가 EXP-374와 완전히 동일
- Optuna 미사용(시간 제약, EXP-285 전례 Public 미전이)
- #342(2heej, 24시간+ 미착수, EXP-334 기반이라 구식) 대체

## 결과

| 지표 | EXP-449(LightGBM) | EXP-374(XGBoost) | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4220549915 | 0.4267909268 | -0.0047359353 |
| Fold 표준편차 | 0.0165060943 | 0.0085032169 | +0.0080028774(LightGBM이 fold 변동성 더 큼) |
| Log Loss | 1.8184868005 | 1.8440648317 | **-0.0255780313(개선)** |
| Runtime | 279.35초 | ~565초 | LightGBM이 더 빠름 |

## 다양성 사전 확인 (블렌드 #450 진행 근거)

- OOF 확률 상관: **0.9578921078**(PROJECT_CONTEXT.md 기준 0.92 초과)
- **라벨 불일치율: 23.1%**(기준 10% 크게 초과)
- OR 조건(상관≤0.92 또는 불일치율≥10%) 충족 — 블렌드 시도 가치 있는
  다양성으로 판단, [#450](https://github.com/fabxoe/open_cancer/issues/450)로 진행

## 재현성

- Config: `configs/exp449_lightgbm_exp374.yaml`
- Runner: `scripts/run_exp449_lightgbm_exp374.py`
- 재현 상태: `INFERENCE_VERIFIED`(LightGBM `deterministic: true` +
  `force_col_wise: true`로 확률 최대 차이 0.0)
- Public LB: 미제출(구성요소 실험, 블렌드 결과 확인 후 판단)
