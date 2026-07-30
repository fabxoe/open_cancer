# Open Cancer

암환자의 4,384개 유전자 변이 정보를 이용해 26개 암종(`SUBCLASS`)을 분류하는
해커톤 프로젝트입니다. 공식 평가지표는 **Macro F1**입니다.

> **2026-07-30 이전에 clone한 팀원:** 원본 데이터 제거를 위해 Git history가
> 재작성되었습니다. 기존 clone에서 pull·merge·push하지 말고
> [재clone 안내](docs/TEAM_RECLONE_AFTER_HISTORY_REWRITE.md)를 따르세요.

## 시작하기

처음 clone한 팀원은 [VS Code + uv 초기 설정](docs/VSCODE_SETUP.md)을 순서대로
따릅니다.

```bash
uv sync --frozen
uv run python scripts/validate_data.py
uv run pytest
```

대회 원본 데이터는 주최측 정책에 따라 GitHub에 포함하지 않습니다. 주최측 공식
다운로드 또는 팀에서 승인한 비공개 전달 방법으로 다음 파일을 받은 뒤 로컬에
배치합니다.

```text
data/raw/train.csv
data/raw/test.csv
data/raw/sample_submission.csv
```

`data/raw/*`는 `.gitignore`로 제외되며 Issue, PR, commit, Release asset에도
업로드하지 않습니다. 원본 CSV를 직접 수정하지 말고, 파일 배치와 무결성 확인은
[data/README.md](data/README.md)를 따릅니다.

## 작업 전 반드시 읽을 문서

1. [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md): 데이터, 실험, 재현성, GitHub 작업 규칙
2. [EXPERIMENT_HISTORY.md](EXPERIMENT_HISTORY.md): 실제 실험과 제출 결과 장부

Codex의 `AGENTS.md`와 Claude Code의 `CLAUDE.md`는 위 두 문서를 먼저 읽도록
연결되어 있습니다. 새 AI 대화를 시작할 때도 두 문서를 읽었는지 먼저 확인합니다.

모든 작업은 GitHub Issue에서 시작하며 `번호`, `번호-설명`, `issue-번호` 또는
`issue-번호-설명` 브랜치와 PR을 통해 `main`에 반영합니다. 공식 실험 ID는 Issue
#N에서 `EXP-NNN`으로 자동 파생합니다. 모델 실험 Issue는 제목만 작성해도 되며
가설·부모 실험·변경 메모는 선택 사항입니다. 상세 절차와 기본값은
`PROJECT_CONTEXT.md`를 따릅니다.
