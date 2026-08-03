# EXP-272: EXP-219 고정 5-seed 확률 평균

## 한눈에 보는 결론

EXP-219의 모델·피처·canonical 5-fold·Macro-F1 checkpoint 정책을 그대로 두고,
seed만 `42, 142, 242, 342, 442`로 바꾼 다섯 모델의 확률을 사전에 정한
`0.2`씩 평균했다. OOF 결과는 `0.4208578157`로 EXP-219보다
`0.0013743303` 낮았고, fold 표준편차와 Log Loss도 악화됐다.

따라서 이 구성은 **ARCHIVE**한다. 리더보드에 제출하지 않으며, 결과를 본 뒤
seed를 골라내거나 가중치를 다시 맞추지 않는다.

## 무엇을 확인하려 했나

EXP-219는 validation Macro F1이 가장 높은 iteration을 checkpoint로 선택해
OOF Macro F1 `0.4222321460`을 기록했다. 하지만 같은 validation fold에서
checkpoint를 선택하고 성능을 측정하므로, 특정 seed에서 우연히 나타난 Macro F1
봉우리를 선택했을 가능성이 있다.

EXP-272는 다음 계약을 실행 전에 고정했다.

- 부모: EXP-219
- split: canonical stratified 5-fold seed 42
- 모델·피처·checkpoint 선택 정책: EXP-219와 동일
- 모델 seed: `42, 142, 242, 342, 442`
- 최종 확률: 다섯 seed의 OOF/test 확률을 각각 `0.2`로 평균
- 금지: 실행 결과, test 또는 Public 점수를 보고 seed 제외·가중치 변경

## 실제 결과

| seed | OOF Macro F1 | fold 표준편차 | Log Loss |
|---:|---:|---:|---:|
| 42 | 0.4222321460 | 0.0067203936 | 1.8476127386 |
| 142 | 0.4245190846 | 0.0121255562 | 1.9294005632 |
| 242 | 0.4246887695 | 0.0115814048 | 1.9044134617 |
| 342 | 0.4238191001 | 0.0111731674 | 1.8723708391 |
| 442 | 0.4214180383 | 0.0103619944 | 1.8684573174 |
| **고정 0.2 평균** | **0.4208578157** | **0.0112937018** | **1.8553646704** |

최종 평균의 fold별 Macro F1은 다음과 같다.

```text
0.4170648211, 0.4298147148, 0.4017862524, 0.4211686299, 0.4342485967
```

### EXP-219와 비교

| 지표 | EXP-219 | EXP-272 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4222321460 | 0.4208578157 | -0.0013743303 |
| fold 표준편차 | 0.0067203936 | 0.0112937018 | +0.0045733083 |
| Log Loss | 1.8476127386 | 1.8553646704 | +0.0077519318 |

세 지표가 모두 불리한 방향으로 변했다. 개별 seed 142·242의 전체 OOF Macro F1은
높았지만 fold 변동성과 Log Loss가 크게 나빴으며, 고정 평균으로도 그 불안정성이
사라지지 않았다.

## 새롭게 확인한 점

Macro-F1-best checkpoint가 일부 fold에서 매우 이른 iteration의 일시적 봉우리를
선택했다.

- seed 142, fold 2: best iteration `26`, Log Loss `2.2503359`
- seed 242, fold 2: best iteration `46`, Log Loss `2.0546410`
- seed 442, fold 3: best iteration `57`, Log Loss `1.9837151`

이는 Macro F1을 공식 지표로 우선하는 원칙이 잘못됐다는 뜻이 아니다. 다만
불연속적인 Macro F1 한 시점만으로 checkpoint를 고르면 작은 validation fold의
우연한 변동을 잡을 수 있다는 근거다. 후속 실험이 필요하다면 seed 평균을 다시
조정하기보다, Macro F1 checkpoint의 안정화 규칙을 별도 Experiment Issue에서
사전 고정해 비교하는 편이 타당하다.

## 재현성 검증

- 각 seed의 저장 checkpoint로 OOF/test 확률과 제출 파일을 재생성했다.
- 다섯 seed 모두 `INFERENCE_VERIFIED`를 통과했다.
- 최종 고정 평균도 OOF/test 라벨 일치율 `1.0`, 확률 최대 차이 `0.0`, 제출
  SHA-256 일치를 확인했다.
- seed 42 재실행은 EXP-219 원본과 OOF·test 확률이 byte-level로 동일했다.

따라서 EXP-272의 하락은 실행 경로 오류나 EXP-219 재현 실패로 설명되지 않는다.
비작성자의 독립 재학습은 수행하지 않았으므로 `TRAINING_VERIFIED`로 승격하지
않는다.

## 파일 위치

- Config: `configs/exp272_exp219_multiseed_ensemble.yaml`
- Runner: `scripts/run_exp272_exp219_multiseed_ensemble.py`
- Metrics: `reports/exp272_exp219_multiseed_ensemble/metrics.json`
- seed 감사: `reports/exp272_exp219_multiseed_ensemble/seed_summary.json`
- Reproduction: `reproducibility/exp272_exp219_multiseed_ensemble/`
- Submission: `submissions/exp272_exp219_multiseed_ensemble.csv` (검증용, 미제출)

대형 checkpoint·OOF·test 확률은 Git에 커밋하지 않는다. 이번 실험은 상위 모델이나
리더보드 제출 후보가 아니므로 GitHub Release 번들을 만들지 않는다.
