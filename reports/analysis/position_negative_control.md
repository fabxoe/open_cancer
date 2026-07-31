# Residue-position permutation negative control

> 공식 실험이나 리더보드 제출이 아닌 `RUN_MODE=explore` 분석입니다.

## 질문

EXP-069의 개선이 `max_residue_position` 숫자값 자체에서 나온 것인지,
아니면 mutation-presence와 sparse 구조에서 나온 것인지 확인합니다.

## 누수 방지 설계

- 각 outer fold의 학습 행 안에서만 위치값을 섞었습니다.
- validation 위치값은 원본 그대로 두고 test 데이터는 사용하지 않았습니다.
- 유전자, 위치 관측 mask와 mutation-presence를 유지했습니다.
- 같은 유전자 안에서도 missense·synonymous·nonsense·frameshift·complex
  조합이 같은 행끼리만 위치값을 섞었습니다.
- 모델 seed는 EXP-069와 동일하게 고정하고 permutation seed만 변경했습니다.

## 결과

- EXP-069 원본 OOF Macro F1: `0.4131007993`
- permutation 평균 OOF Macro F1: `0.4058699664`
- 원본 - permutation 평균: `+0.0072308329`
- 판단: `SUPPORTED_NUMERIC_POSITION_SIGNAL`
- 원본보다 낮아진 fold: `13/15`
- fold당 실제로 이동한 위치값: `152,085~158,971`개
- sparse support 변경: `0`건

| permutation seed | OOF Macro F1 | 원본 대비 | fold 표준편차 | Log Loss |
|---:|---:|---:|---:|---:|
| 42 | 0.4064712361 | -0.0066295632 | 0.0069618389 | 1.8658504486 |
| 314 | 0.4091270126 | -0.0039737867 | 0.0076052823 | 1.8595196009 |
| 2718 | 0.4020116503 | -0.0110891490 | 0.0085052952 | 1.8633792400 |

## 해석 기준

- 원본이 permutation 평균보다 `0.002` 이상 높으면 숫자 위치 신호가
  있다는 근거로 봅니다.
- 절대 차이가 `0.001` 이하면 숫자 위치 신호가 명확하지 않은 것으로 봅니다.
- 그 사이는 결론을 보류합니다.

## 다음 결정

EXP-069의 `max+zero`를 Position Feature Spec v1에 포함하고 단계 F 조합 실험으로 진행합니다.

상세 seed·fold 결과와 입력 해시는
[`position_negative_control.json`](position_negative_control.json)에 있습니다.
