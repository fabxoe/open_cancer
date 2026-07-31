# EXP-078: Maximum residue-position + observed indicator

## 한눈에 보기

EXP-078은 EXP-069의 `max residue-position` 표현을 유지하면서, 위치를
파싱할 수 있었는지를 나타내는 `residue_position_observed` 피처를 추가한
로드맵 단계 B의 단일 변수 실험입니다.

Issue #80의 사후 의미 감사에서 현재 데이터의 `residue_position_observed`가
기존 `mutation_presence`와 train/test 모두 완전히 동일함을 확인했습니다.
따라서 아래 점수는 유효하지만, 실험 의미는 결측 구분이 아니라 중복 피처가
XGBoost의 feature sampling에 미친 영향으로 제한해 해석합니다.

| 항목 | EXP-069 `max+zero` | EXP-078 `max+indicator` | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4131007993 | 0.4110815504 | -0.0020192489 |
| Fold 평균 | 0.4127757527 | 0.4107859915 | -0.0019897612 |
| Fold 표준편차 | 0.0082058569 | 0.0126482021 | +0.0044423453 |
| Accuracy | 0.4052572166 | 0.4026769876 | -0.0025802290 |
| Log Loss | 1.8525067568 | 1.8513578176 | -0.0011489391 |

- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`
- 판단: **기각**

## 무엇을 바꿨나

```yaml
position:
  aggregates: [max]
  missing_policy: indicator
  token_scope: include_complex
  transform: raw
```

EXP-069과 비교해 바뀐 값은 `missing_policy: zero → indicator` 하나입니다.
모델, canonical split, seed, 나머지 피처와 학습 파라미터는 유지했습니다.

`indicator` 정책의 일반적인 목적은 유전자별 최대 위치값과 위치 파싱 여부를
분리하는 것이다. 하지만 현재 파서는 양의 residue 위치만 허용하고 모든 non-WT
토큰에서 위치가 파싱됐다. 실제 sparse 행렬에서 indicator와 mutation-presence의
불일치는 train/test 모두 0개였다.

EXP-069의 35,084개 피처에 mutation-presence와 동일한 열 4,384개가 추가되어
EXP-078은 39,468개 피처를 사용했다. 이는 새로운 결측 정보를 추가한 것이 아니다.

## 실제 결과

### Fold별 Macro F1

| Fold | EXP-069 | EXP-078 | 차이 |
|---:|---:|---:|---:|
| 0 | 0.4088270533 | 0.4159950137 | +0.0071679604 |
| 1 | 0.4239996903 | 0.4149887889 | -0.0090109014 |
| 2 | 0.3999078004 | 0.3869454103 | -0.0129623901 |
| 3 | 0.4129369619 | 0.4115730954 | -0.0013638666 |
| 4 | 0.4182072576 | 0.4244276491 | +0.0062203915 |

Fold 0과 4는 개선됐지만 fold 1~3이 하락했고, 특히 fold 2의 하락으로 전체
Macro F1과 안정성이 악화됐습니다.

### 클래스별 변화

26개 클래스 중 8개가 개선되고 16개가 하락했으며 2개는 같았습니다.

- 주요 개선: DLBC `+0.0303`, COAD `+0.0100`, STES `+0.0076`
- 주요 하락: LUAD `-0.0287`, UCEC `-0.0157`, LUSC `-0.0144`

Log Loss는 소폭 좋아졌지만 Macro F1, Accuracy, fold 변동성과 다수 클래스
F1이 악화돼 채택 근거로 충분하지 않습니다.

## 로드맵 채택 조건 판정

| 조건 | 판정 |
|---|---|
| EXP-069 대비 Macro F1 `+0.001` 이상 | 실패: `-0.0020192489` |
| Fold 표준편차 악화 `0.002` 미만 | 실패: `+0.0044423453` |
| Log Loss·소수 클래스의 명백한 붕괴 없음 | Log Loss 개선, 일부 클래스 하락 |
| Checkpoint inference 재현 검증 | 통과 |

핵심 성능 조건 두 개를 모두 통과하지 못했으므로 `max+indicator`를 기각합니다.
로드맵의 중단 조건에 따라 위치 옵션 추가 탐색을 종료하고 EXP-069의
`max+zero`를 **Position Feature Spec v1**으로 동결합니다.

이 기각 판단은 Issue #80 의미 감사 이후에도 유지한다. 다만 EXP-078의 하락을
“indicator가 결측을 잘못 표현했다”는 증거로 해석하지 않는다. 중복된 presence
열이 `colsample_bytree=0.8`의 후보 선택 확률과 tree 학습 경로를 바꾼 결과일 수
있기 때문이다. 같은 이유로 indicator-only 후속 공식 실험은 진행하지 않는다.

실제 의미 감사 결과는
[`reports/analysis/residue_position_semantics_qc.json`](../analysis/residue_position_semantics_qc.json)과
[해석 보고서](../analysis/residue_position_semantics_qc.md)를 따른다.

## 재현과 관련 파일

- Config: `configs/exp078_xgb_max_residue_indicator.yaml`
- Resolved config:
  `reproducibility/exp078_xgb_max_residue_indicator/config.resolved.yaml`
- Metrics: `reports/exp078_xgb_max_residue_indicator/metrics.json`
- OOF: `oof/exp078_xgb_max_residue_indicator.csv` (Git 제외)
- Test 확률: `preds/exp078_xgb_max_residue_indicator_test_proba.csv` (Git 제외)
- 제출 후보: `submissions/exp078_xgb_max_residue_indicator.csv` (미제출)
- 제출 SHA-256:
  `deb510b6e23008f536a000f63750039b00ca6ca13cd06bc1a62c751a2b9da91c`
- 재현 비교:
  `reproducibility/exp078_xgb_max_residue_indicator/comparison.json`

저장 checkpoint로 다시 추론했을 때 test 라벨 일치율 100%, 확률 최대 절대
차이 약 `2.97e-08`, 제출 CSV SHA-256 일치를 확인했습니다.

## 다음 단계

Position Feature Spec v1은 EXP-069의 `max+zero`로 동결합니다. EXP-078은
리더보드에 제출하지 않습니다. 선행 PR이 main에 병합되면 로드맵 단계 C인
hotspot runner 일반화를 일반 Task Issue로 진행합니다.
