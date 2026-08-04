# EXP-219 재현 절차

원본 checkpoint·OOF·test 확률이 필요하면 GitHub Release 번들을 내려받습니다.

```bash
gh release download exp-219-repro-v1 \
  --repo fabxoe/open_cancer \
  --pattern exp219_macro_f1_checkpoint_selection_repro.tar.gz
tar -xzf exp219_macro_f1_checkpoint_selection_repro.tar.gz
```

번들 SHA-256은
`fa293ed92a21508e0752890ca407c6e55cbc8794688262bacff471fd6739bf25`입니다.

원본 CSV를 `data/raw/`에 배치하고 다음 명령을 실행합니다.

```bash
uv sync --frozen
uv run python scripts/run_exp219_macro_f1_checkpoint_selection.py
uv run python scripts/validate_experiment.py
```

실험 실행 마지막 단계에서 저장 checkpoint 추론과 제출 SHA-256 일치 검증이 자동 수행됩니다.
