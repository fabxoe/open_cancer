# EXP-075: EXP-067·069 고정 0.5/0.5 확률 Blend

## 한눈에 보기

EXP-075는 새 모델을 학습하지 않고 두 residue-position 모델이 만든 클래스별
확률을 같은 비율로 평균한 inference-only 앙상블입니다.

```text
최종 확률 = 0.5 × EXP-067 coarse-bin 확률
          + 0.5 × EXP-069 max-position 확률
최종 라벨 = 고정 26개 클래스 중 최종 확률이 가장 큰 클래스
```

가중치 `0.5/0.5`는 결과를 확인하기 전에
[Issue #75](https://github.com/fabxoe/open_cancer/issues/75)에서 고정했으며,
OOF나 Public LB를 보고 조정하지 않았습니다.

| 항목 | 결과 |
|---|---:|
| OOF Macro F1 | **0.4157910775** |
| Fold 평균 | 0.4153351171 |
| Fold 표준편차 | **0.0064700181** |
| Accuracy | 0.4073536526 |
| Log Loss | **1.8446407531** |
| Public LB | 미제출 |
| 재현 상태 | `INFERENCE_VERIFIED` |

## 왜 두 모델을 평균했나?

EXP-067은 residue 위치를 폭 100의 coarse-bin으로 단순화하고, EXP-069는 각
유전자에서 관측된 최대 residue 위치를 사용합니다. 두 모델은 같은 샘플에서도
서로 다른 라벨을 내놓을 수 있습니다. 실제 OOF 예측 라벨 일치율은 약
`88.79%`였습니다.

두 모델이 모두 확신하는 경우에는 평균 확률도 강하게 유지되고, 한 모델만
지나치게 확신하는 경우에는 다른 모델의 확률이 이를 완화합니다. 이 실험은 이런
오류 차이가 전체 26개 암종을 동일하게 보는 Macro F1에 도움이 되는지 검증합니다.

## 입력과 검증 계약

- 부모 모델: [EXP-067](../exp067_xgb_residue_coarse_bin/README.md),
  [EXP-069](../exp069_xgb_max_residue_position/README.md)
- 공용 split: `data/splits/stratified_5fold_seed42.csv`
- 클래스 순서: 프로젝트 고정 26개 순서
- OOF 비교 열: `ID`, `SUBCLASS_TRUE`, `FOLD`
- test 비교 열: `ID`
- 두 입력 모두 확률 열·행 수·ID 순서·확률 범위·행 합을 검사
- 평균 계산: `float64`, 고정 `0.5/0.5`
- threshold, calibration, TTA와 클래스별 가중치: 사용하지 않음

CSV에 저장된 부모 확률은 십진 문자열 반올림 때문에 행 합이 1에서 약간 벗어날
수 있습니다. 실행기는 `atol=1e-5`, `rtol=1e-5` 안에서만 이를 허용합니다.
이는 argmax 라벨이나 고정 가중치를 변경하는 별도 후처리가 아닙니다.

## 실제 결과

### Fold별 Macro F1

| Fold | Macro F1 |
|---:|---:|
| 0 | 0.4129241979 |
| 1 | 0.4225703598 |
| 2 | 0.4081482976 |
| 3 | 0.4095628288 |
| 4 | 0.4234699014 |

### 부모 실험 비교

| 실험 | OOF Macro F1 | Fold 표준편차 | Accuracy | Log Loss |
|---|---:|---:|---:|---:|
| EXP-067 | 0.4124014867 | 0.0080562642 | 0.4034833091 | 1.8524806499 |
| EXP-069 | 0.4131007993 | 0.0082058569 | 0.4052572166 | 1.8525067568 |
| **EXP-075** | **0.4157910775** | **0.0064700181** | **0.4073536526** | **1.8446407531** |

- EXP-067 대비 Macro F1: `+0.0033895908`
- EXP-069 대비 Macro F1: `+0.0026902782`
- EXP-067 대비 fold 표준편차: `-0.0015862461`
- EXP-069 대비 fold 표준편차: `-0.0017358387`

OOF Macro F1, Accuracy와 Log Loss가 두 부모보다 좋아졌고 fold 변동성도
감소했습니다. 사전에 고정한 단순 평균이므로 이번 결과는 로드맵 단계 A의 채택
조건을 충족합니다.

## 해석과 한계

- 개선은 두 위치 표현이 완전히 같은 오류를 만들지 않는다는 점을 뒷받침합니다.
- 이 결과만으로 coarse-bin이나 max 위치가 생물학적 위치 효과를 학습했다고
  결론 내릴 수 없습니다. 로드맵 단계 E의 negative control이 필요합니다.
- EXP-075는 독립 모델이 아니라 두 부모 산출물에 의존합니다. 재현 번들에는 두
  부모의 OOF·test 확률, resolved config와 fold checkpoint 10개가 필요합니다.
- Public LB는 아직 제출하지 않았으므로 리더보드 일반화 성능은 알 수 없습니다.
- 이 결과를 근거로 `0.4/0.6` 같은 다른 비율을 추가 탐색하지 않습니다.

## 재현과 관련 파일

- Config: `configs/exp075_residue_probability_blend.yaml`
- Resolved config:
  `reproducibility/exp075_residue_probability_blend/config.resolved.yaml`
- Metrics: `reports/exp075_residue_probability_blend/metrics.json`
- OOF: `oof/exp075_residue_probability_blend.csv` (Git 제외·Release 보관 대상)
- Test 확률:
  `preds/exp075_residue_probability_blend_test_proba.csv` (Git 제외·Release 보관 대상)
- 제출 후보: `submissions/exp075_residue_probability_blend.csv`
- 제출 SHA-256:
  `25f00f1a97acbd5364df0dd7b391f75a930888fefc887edf696f681d482d7b3e`
- 재현 비교:
  `reproducibility/exp075_residue_probability_blend/comparison.json`
- 재현 Release:
  [`exp-075-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-075-repro-v1)
- Release bundle SHA-256:
  `698c29841112ff78e6fe2dcdd1b6b07bd2e7a2db26ef8ec86e625963d8125b33`

동일 입력으로 다시 평균했을 때 OOF·test 라벨 일치율 100%, 확률 최대 절대
차이 `0`, 제출 CSV SHA-256 byte-level 일치를 확인했습니다.

## 판단과 다음 단계

EXP-075는 현재 최고 재현 가능 Local OOF 모델로 채택합니다. GitHub Release
재현 번들 보관을 완료했으므로 DACON 제출 후보로 사용할 수 있습니다. 실제
제출 결과를 기록하기 전까지 Public LB는 `미제출`로 유지합니다. 그다음 로드맵
단계 B인 `max residue-position + observed indicator` 단일 모델 실험으로
이동합니다.
