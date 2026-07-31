# EXP-005 추론·재학습 재현 절차

## 저장 체크포인트로 제출 재생성

Release 번들을 저장소 루트에서 내려받아 압축을 풉니다. 원본 CSV는 번들에
포함되지 않으므로 별도로 `data/raw/`에 배치해야 합니다.

```bash
uv sync --frozen
curl -L -o exp005_repro.tar.gz \
  https://github.com/fabxoe/open_cancer/releases/download/exp-005-repro-v1/exp005_xgb_mutation_features_repro_v1.tar.gz
tar -xzf exp005_repro.tar.gz
uv run python scripts/verify_exp005_inference.py
uv run python scripts/validate_submission.py submissions/exp005_xgb_mutation_features.csv
uv run python scripts/validate_experiment.py
```

번들 SHA-256은
`e74907f50b282c306148d2b725cbd7871b435d340f90a3d9c5142481948dc24a`다.
검증 스크립트는 데이터 해시를 확인하고 제출 SHA-256 및 test 라벨·확률을
기존 결과와 비교한다.

## 처음부터 재학습

EXP-005 실행기는 Issue #5 브랜치에서만 실행되도록 보호되어 있다. 다음 명령은
`exp-005-repro-v1` 태그가 가리키는 commit에서 Issue #5 형식의 로컬 브랜치를
만들어 실행한다.

```bash
git switch -c issue-5-exp005-reproduction exp-005-repro-v1
uv sync --frozen
PYTHONHASHSEED=42 uv run python scripts/run_exp005_xgb_mutation_features.py
```

2026-07-31 독립 재학습에서는 기존 OOF Macro F1
`0.4043796587000222`, 제출 SHA-256과 fold checkpoint 5개의 SHA-256이 모두
동일했다. 재학습 검증자는 원 실험 작성자와 동일하지 않지만, 아직 다른 팀원의
fresh clone 검증 전이므로 상태는 `INFERENCE_VERIFIED`로 유지한다.
