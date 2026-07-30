# EXP-026: mutation-presence + mutated-gene count

## 한눈에 보기

EXP-003의 유전자별 변이 존재 여부 4,384개에 환자별 변이 유전자 총개수
한 개를 추가한 XGBoost 실험이다. OOF와 Public LB 모두 EXP-003보다
개선됐지만, 변이 유형까지 사용하는 EXP-005보다 낮았다.

| 항목 | 결과 |
|---|---:|
| OOF Macro F1 | 0.3817476632 |
| Public LB Macro F1 | 0.2575936484 |
| Dacon 제출 ID | 1506469 |
| 제출 시각 | 2026-07-30 23:56:29 KST |
| 재현 상태 | NOT_STARTED |

## 어떤 값을 모델에 넣었나

먼저 각 환자의 4,384개 유전자를 하나씩 확인한다.

- 값이 `WT` 또는 빈값이면 해당 유전자는 `0`
- 변이가 하나라도 기록되어 있으면 해당 유전자는 `1`

이렇게 만든 4,384개의 `mutation-presence` 값에 다음 숫자 하나를 추가했다.

```text
mutated-gene count = 값이 1인 유전자의 개수
```

예를 들어 어떤 환자의 4,384개 유전자 중 17개 유전자에 변이가 있다면
추가 피처의 값은 `17`이다. 이 값은 이 대회 데이터에서 관측된 패널 내
변이 유전자 개수일 뿐, 변이의 종류나 유전자별 임상적 중요도는 구분하지 않는다.

## 임상적 TMB와 다른 이유

TMB(Tumor Mutational Burden)는 보통 검사한 DNA 영역의 크기를 고려해
`메가베이스(Mb)당 체세포 변이 수`로 계산한다. 이 데이터만으로는 검사 영역의
정확한 Mb 크기, 체세포·생식세포 구분, 변이 필터 기준을 모두 알 수 없다.
따라서 이 실험의 `mutated-gene count`를 임상적 TMB라고 부르면 안 된다.

## 비교 결과

| 실험 | 핵심 피처 | OOF Macro F1 | Public LB |
|---|---|---:|---:|
| EXP-003 | mutation-presence | 0.334930 | 0.228167518 |
| EXP-026 | mutation-presence + mutated-gene count | 0.3817476632 | 0.2575936484 |
| EXP-005 | mutation-presence + 변이 유형 및 집계 피처 | 0.4043796587 | 0.2987843366 |

EXP-026은 EXP-003보다 OOF가 약 `0.046817`, Public LB가 약
`0.0294261304` 높다. 즉, 환자마다 변이가 얼마나 넓게 퍼져 있는지를 나타내는
단순한 숫자 하나도 암종 구분에 도움이 됐다고 볼 수 있다. 다만 EXP-005보다
낮으므로 변이 총량만 추가하는 것보다 변이 유형을 함께 표현하는 편이 더
유용했다는 근거가 된다.

## 산출물

- 설정: `configs/exp026_mutation_burden.yaml`
- 실행 설정: `reproducibility/exp026_mutation_burden/config.resolved.yaml`
- 상세 지표: `reports/exp026_mutation_burden/metrics.json`
- 클래스별 F1: `reports/exp026_mutation_burden/class_f1.csv`
- 제출 파일: `submissions/exp026_mutation_burden.csv`
- 제출 SHA-256:
  `53d835335d6d23945c80acef4b70d0112f14abdaf1b5d504a63fd1ea7b16ef00`

## 재현성 상태

제출 CSV의 형식과 SHA-256은 확인했다. 그러나 저장된 체크포인트를 이용해
제출 파일을 독립적으로 다시 생성하고 byte-level SHA-256 일치를 확인하는
절차는 아직 수행하지 않았다. 따라서 현재 상태는 `NOT_STARTED`이며
`INFERENCE_VERIFIED`가 아니다.
