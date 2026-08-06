# EXP-558 parser-v4 compact clinical XGBoost baseline

## 한 줄 결론

다른 고득점 팀이 공유한 compact clinical feature architecture를 parser v4로 재구현한 결과, EXP-005보다 Macro F1이 `+0.0089429523` 개선됐습니다. 구조의 독립 가치는 확인했지만 최근 parser-v4 강한 모델보다 낮아 즉시 제출 후보로 채택하지 않습니다.

## 입력 피처

각 outer fold의 train에서만 다음 vocabulary를 fit했습니다.

- `mutated__GENE`: non-WT 사건이 있는 유전자
- `truncating__GENE`: nonsense·frameshift·stop 포함 range 사건이 있는 유전자
- `recurrent_missense__GENE`: 동일한 gene/ref/position/alt missense가 환자 5명 이상에서 관측
- `summary__*`: 14개 환자 단위 사건·유전자 수 요약

validation과 test는 fold-train에서 확정한 feature map으로 transform만 했습니다. fold별 최종 차원은 `7,785~7,851`입니다. 공통 runner가 만든 역사적 base feature는 모델 학습 직전에 모두 제거했으므로 이 점수는 compact 구조만의 성능입니다.

## 결과

| 지표 | EXP-558 | EXP-005 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4133226110 | 0.4043796587 | +0.0089429523 |
| Fold 표준편차 | 0.0060589651 | 0.0086812077 | -0.0026222426 |
| Accuracy | 0.4033220448 | - | - |
| Log Loss | 1.9797550440 | 1.8632071018 | +0.1165479422 |

Fold Macro F1:

```text
0.4111242643
0.4175693659
0.4009731443
0.4133951038
0.4173161316
```

Macro-F1 checkpoint 선택은 training-metric checkpoint의 OOF `0.4076253653`보다 `+0.0056972457` 높았습니다. 그러나 fold 2는 iteration 19의 순간 최고점을 선택해 Log Loss가 `2.38936`까지 나빠졌습니다. 따라서 compact 피처의 방향성 개선과 checkpoint 정책의 낙관 편향을 구분해야 합니다.

## 비교 해석

- EXP-003 mutation presence(`0.3349302814`)보다 크게 높아 truncating·recurrent·summary 압축은 유효합니다.
- EXP-005(`0.4043796587`)보다 높고 fold 변동성도 낮아 새로운 독립 베이스로 보존할 가치가 있습니다.
- parser-v4 native EXP-438(`0.4102050373`)보다 `+0.0031175738` 높습니다.
- 환자 semantic count를 강한 기존 Feature Spec에 추가한 EXP-512(`0.4258183004`)보다는 낮습니다. compact 구조가 기존의 모든 고해상도 정보보다 우수하다는 뜻은 아닙니다.
- Public LB는 미제출이며, 공유 문서 자체에도 통제된 모델 성능은 없으므로 그 팀의 고득점 원인을 입증한 결과는 아닙니다.

## 판단과 다음 단계

`BASELINE_ACCEPTED`, 단독 제출 후보는 보류합니다.

다음 실험은 한꺼번에 튜닝하지 않고 다음 순서의 ablation으로 분리합니다.

1. mutated only
2. mutated + truncating
3. 위 조합 + summary
4. 위 조합 + fold-train recurrent missense
5. ref-AA × consequence 저차원 count

가장 먼저 mutated-only와 complete compact의 차이를 확인해야 실제 개선이 truncating, summary, recurrent 중 어디서 왔는지 알 수 있습니다.

## 재현

```bash
uv sync --frozen
uv run python scripts/run_exp558_compact_clinical_xgb.py
```

- Source commit: `704d7d4df868b487bf52033b38abe2bb855d02ad`
- Submission SHA-256: `c2c4128c7b50db68a5d0e298f2d78cc1eb94a4d75c43bfde90821ab516dbe0c2`
- 재현 상태: `INFERENCE_VERIFIED`
