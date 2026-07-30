# Open Cancer

암환자의 4,384개 유전자 변이 정보를 이용해 26개 암종(`SUBCLASS`)을 분류하는
해커톤 프로젝트입니다. 공식 평가지표는 **Macro F1**입니다.

## 시작하기

```bash
uv sync --frozen
uv run python scripts/validate_data.py
uv run pytest
```

대회에서 받은 파일은 Git에 커밋하지 않고 다음 위치에 둡니다.

```text
data/raw/train.csv
data/raw/test.csv
data/raw/sample_submission.csv
```

데이터 파일과 현재 로컬 파일의 해시는 [data/README.md](data/README.md)에서 확인합니다.

## 작업 전 반드시 읽을 문서

1. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md): 데이터, 실험, 재현성, GitHub 작업 규칙
2. [EXPERIMENT_HISTORY.md](EXPERIMENT_HISTORY.md): 실제 실험과 제출 결과 장부

모든 작업은 GitHub Issue에서 시작하며 `issue-<번호>-<설명>` 브랜치와 PR을 통해
`main`에 반영합니다. 상세 절차는 `PROJECT_CONTEXT.md`를 따릅니다.
