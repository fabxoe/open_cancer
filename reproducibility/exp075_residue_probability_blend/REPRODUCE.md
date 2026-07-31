# EXP-075 재현 절차

Release 번들을 저장소 루트에 풀어 부모 checkpoint·OOF·test 확률을 원래 경로에 배치합니다.

```bash
uv sync --frozen
uv run python scripts/run_exp075_residue_probability_blend.py
uv run python scripts/validate_experiment.py
```

실행기는 두 부모 확률의 ID·fold·클래스 순서·SHA-256 계약을 확인하고 고정 0.5/0.5 평균으로 제출 파일을 재생성합니다.
