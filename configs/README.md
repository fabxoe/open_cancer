# Experiment configurations

실험별 입력 설정은 `exp001_<slug>.yaml` 형식으로 저장합니다. 실행 코드는 설정을
읽고 기본값까지 병합한 실제 값을
`reproducibility/exp001_<slug>/config.resolved.yaml`에 기록해야 합니다.

필수 항목과 작성 규칙은 `PROJECT_CONTEXT.md`의 “실험 설정 계약”을 따릅니다.
