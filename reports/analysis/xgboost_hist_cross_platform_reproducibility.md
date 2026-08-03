# XGBoost `hist` 교차 플랫폼 재현성 감사

## 결론

EXP-219의 저장 checkpoint 추론 재현은 유효하다. 반면 같은 config, seed와 패키지
버전으로 macOS arm64와 Windows x86_64에서 XGBoost `tree_method=hist`를 처음부터
다시 학습하면 동일 모델이 만들어진다고 보장할 수 없다. 따라서 이 프로젝트는
다음 두 주장을 분리한다.

1. `INFERENCE_VERIFIED`: 저장 checkpoint로 원 제출을 허용 오차 안에서 재생성함
2. `TRAINING_VERIFIED`: 명시한 환경 범위에서 처음부터 재학습해 엄격한 기존 통과
   조건을 만족함

플랫폼 간 재학습 차이를 이유로 기존 checkpoint 추론 증빙을 삭제하지 않는다.
반대로 같은 플랫폼의 추론 성공을 교차 플랫폼 재학습 결정론으로 확대하지 않는다.

## EXP-219에서 관측한 사실

| 항목 | 원 실행 | 독립 재학습 시도 |
|---|---|---|
| 플랫폼 | macOS 26.2 arm64, Clang | Windows 10 x86_64, MSVC |
| XGBoost | 3.2.0 | 3.2.0 |
| NumPy / pandas / scikit-learn | 동일 버전 | 동일 버전 |
| split / seed / resolved config | canonical split, seed 42 | 동일 |
| OOF Macro F1 | 0.4222321460 | 0.4209755511 |
| Macro F1 차이 | 기준 | -0.0012566 |
| submission·OOF SHA-256 | 원본 manifest 값 | 불일치 |

패키지와 데이터 계약은 같고 플랫폼이 달랐지만, 이것만으로 플랫폼이 유일한
인과 원인이라고 증명된 것은 아니다. 히스토그램 집계 순서, compiler, CPU 명령,
thread scheduling과 부동소수점 연산 차이가 함께 작용했을 가능성이 있다. 따라서
원인은 `cross-platform training nondeterminism observed`로 기록하며 특정 내부
원리 하나로 단정하지 않는다.

EXP-219 원본 artifact는 이후 Issue #258·PR #259에서 source Mac에 남아 있던 파일을
기존 manifest SHA-256과 대조해 복구했다. Windows 재학습 산출물은 원본 대체물로
사용하지 않았다.

## 기존 기록의 영향 범위

2026-08-03 감사 시점의 artifact manifest 55개를 조사했다.

- `INFERENCE_VERIFIED`: 46개
- `TRAINING_VERIFIED`: 0개
- `MANIFEST_COMPLETE`: 8개
- `FAILED`: 1개

verified 46개의 기록 환경은 macOS 40개, Windows 2개, Linux 4개다. 이 결과는
서로 다른 플랫폼에서 같은 실험을 재학습했다는 뜻이 아니라 각 실험의 checkpoint
추론 검증이 수행된 환경 분포다. 현재 `TRAINING_VERIFIED`로 잘못 승격된 실험은
없으므로 기존 46개 inference 검증을 일괄 강등할 근거도 없다.

## 채택한 완화책

### 1. 검증 범위를 manifest에 구조화

`TRAINING_VERIFIED` manifest는 다음 `verification_scope`를 필수로 기록한다.

```json
{
  "verification_scope": {
    "operation": "training_reproduction",
    "environment_relation": "same_platform",
    "claim": "tolerance_verified",
    "original_platform": "macOS-arm64",
    "reproduction_platform": "macOS-arm64"
  }
}
```

`environment_relation`은 `same_environment`, `same_platform`,
`cross_platform` 중 하나여야 한다. `unknown`인 상태에서
`TRAINING_VERIFIED`로 승격할 수 없다. 기존 확률 `atol=1e-6`, `rtol=1e-6`,
OOF·test 라벨 100%, OOF Macro F1 차이 `1e-6` 이하 조건은 완화하지 않는다.

### 2. 최종 후보는 원 실행 플랫폼을 우선

최종 수상 후보의 첫 독립 재학습은 가능한 한 원 실행과 같은 OS·아키텍처·모델
library build에서 수행한다. 다른 플랫폼에서 수행하면 `cross_platform`으로
명시하고 기존 엄격 조건을 그대로 적용한다. 실패는 환경 범위와 차이를 기록하되
저장 checkpoint inference 상태를 자동으로 실패로 바꾸지 않는다.

### 3. XGBoost 실행 파라미터 기록

공식 XGBoost 실험은 resolved config에 `tree_method`, `device`, `n_jobs` 또는
`nthread`, predictor를 명시적으로 사용했다면 그 값을 기록한다. `nthread=1`은
thread scheduling 차이를 줄일 수 있는 후속 통제 실험 후보지만, 이번 관측만으로
플랫폼 간 동일성을 보장하지 않으므로 프로젝트 기본값으로 강제하지 않는다.
Docker도 software stack을 고정할 수 있지만 CPU 아키텍처와 부동소수점 집계 차이를
자동 제거하지 않으므로 단독 해결책으로 간주하지 않는다.

## #233과의 관계

#233 nested decision offset은 EXP-219 모델을 다시 학습하지 않고, 복구된 원본
OOF·test 확률을 입력으로 사용한다. 따라서 #238의 교차 플랫폼 재학습 문제 때문에
#233을 중단하지 않는다. #233은 train-only nested fitting과 기존 누수 방지 계약을
그대로 따라 독립적으로 진행한다.

## 후속 확인

- 최종 후보의 비작성자 재학습 때 `verification_scope`와 두 환경을 모두 기록한다.
- XGBoost `hist`의 `n_jobs=1` 통제는 필요하면 별도 Task/Experiment Issue에서 같은
  플랫폼과 교차 플랫폼을 나눠 측정한다.
- 확률 허용치를 Public 점수나 재현 실패 결과에 맞춰 사후 확대하지 않는다.
