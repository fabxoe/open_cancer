# EXP-476 재현 절차

```bash
uv sync --frozen
uv run python scripts/verify_exp476_inference.py
```

원본 CSV 해시와 canonical split을 확인한 뒤 저장된 fold checkpoint로 OOF/test 추론을 재생성해 확률·라벨·제출 SHA-256을 비교합니다.
