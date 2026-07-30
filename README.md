# Open Cancer

암환자의 4,384개 유전자 변이 정보를 이용해 26개 암종(`SUBCLASS`)을 분류하는
해커톤 프로젝트입니다. 공식 평가지표는 **Macro F1**입니다.

## 시작하기

처음 clone한 팀원은 [VS Code + uv 초기 설정](docs/VSCODE_SETUP.md)을 순서대로
따릅니다.

```bash
uv python install 3.11.10
uv sync --frozen --group dev
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

Codex의 `AGENTS.md`와 Claude Code의 `CLAUDE.md`는 위 두 문서를 먼저 읽도록
연결되어 있습니다. 새 AI 대화를 시작할 때도 두 문서를 읽었는지 먼저 확인합니다.

모든 작업은 GitHub Issue에서 시작하며 `issue-<번호>-<설명>` 브랜치와 PR을 통해
`main`에 반영합니다. 상세 절차는 `PROJECT_CONTEXT.md`를 따릅니다.
