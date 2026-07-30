# Experiment configurations

Issue를 만들 때 모든 하이퍼파라미터를 작성할 필요는 없습니다. 실험별 override가
있을 때만 `exp012_<slug>.yaml` 형식으로 저장합니다. override가 없으면 모델 코드의
기본값을 그대로 사용합니다.

실행 코드는 기본값과 override를 병합한 실제 값을
`reproducibility/exp012_<slug>/config.resolved.yaml`에 기록해야 합니다. 이 resolved
config가 실제 파라미터의 단일 원본이므로 Issue나 History에 같은 값을 다시 적지
않습니다.

공통 기본값과 선택 항목은 `PROJECT_CONTEXT.md`의 “실험 설정 계약”을 따릅니다.
