# VS Code + uv 초기 설정

이 문서는 저장소를 처음 clone한 팀원이 VS Code에서 같은 Python 환경을 만들고,
프로젝트 규칙을 AI 도구에 인식시키는 과정을 설명합니다. 명령어는 저장소 루트
(`open_cancer`)에서 실행합니다.

## 0. 먼저 알아둘 것

- Python 패키지와 가상환경은 `uv`로 관리합니다.
- 팀 공통 Python 버전은 `.python-version`, 정확한 패키지 버전은 `uv.lock`에
  고정되어 있습니다.
- 원본 대회 데이터는 GitHub에 올라가지 않습니다. 각자 직접 내려받아 배치해야
  합니다.
- 프로젝트 운영 규칙의 단일 원본은 `PROJECT_CONTEXT.md`입니다.
- 실제로 수행한 실험과 제출만 `EXPERIMENT_HISTORY.md`에 기록합니다.

## 1. 준비 프로그램

다음 프로그램을 먼저 설치합니다.

1. [Git](https://git-scm.com/downloads)
2. [Visual Studio Code](https://code.visualstudio.com/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/)

### macOS 또는 Linux에서 uv 설치

터미널에서 다음 명령을 실행합니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Homebrew를 사용한다면 다음 명령도 가능합니다.

```bash
brew install uv
```

### Windows PowerShell에서 uv 설치

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 터미널을 새로 열고 확인합니다.

```bash
git --version
uv --version
```

`uv`를 찾을 수 없다는 메시지가 나오면 VS Code와 터미널을 완전히 닫았다가 다시
엽니다.

## 2. 저장소 clone과 VS Code 열기

터미널에서 작업할 상위 폴더로 이동한 뒤 실행합니다.

```bash
git clone https://github.com/fabxoe/open_cancer.git
cd open_cancer
code .
```

`code` 명령을 사용할 수 없다면 VS Code에서 **File → Open Folder...**를 눌러
clone한 `open_cancer` 폴더를 엽니다.

VS Code가 권장 확장 설치를 묻는다면 **Install**을 누릅니다. 직접 확인하려면
Extensions 화면에서 `@recommended`를 검색합니다. 주요 확장은 다음과 같습니다.

- Python, Pylance, Python Environments
- Jupyter
- Ruff
- GitHub Copilot과 Copilot Chat(사용하는 팀원만 로그인)

## 3. 고정된 Python 환경 만들기

VS Code에서 **Terminal → New Terminal**을 열고 실행합니다.

```bash
uv python install 3.11.10
uv sync --frozen --group dev
```

이 명령은 저장소의 `.venv` 가상환경을 만들고 `uv.lock`에 기록된 정확한 버전을
설치합니다. `--frozen`은 팀 공통 lock 파일을 실행 중 임의로 바꾸지 않게 합니다.

설치를 확인합니다.

```bash
uv run python --version
uv run python -c "import open_cancer; print('환경 설정 완료')"
```

## 4. VS Code Python 인터프리터 선택

1. `Cmd+Shift+P`(macOS) 또는 `Ctrl+Shift+P`(Windows/Linux)를 누릅니다.
2. **Python: Select Interpreter**를 검색해 실행합니다.
3. 저장소 안의 `.venv`를 선택합니다.

표시되는 실제 경로는 운영체제에 따라 다릅니다.

```text
macOS/Linux: <저장소>/.venv/bin/python
Windows:      <저장소>\.venv\Scripts\python.exe
```

목록에 `.venv`가 보이지 않으면 **Developer: Reload Window**를 실행한 뒤 다시
선택합니다. VS Code는 작업공간의 `.venv`를 자동으로 검색하도록 설정되어 있습니다.

## 5. PROJECT_CONTEXT.md를 AI에 인식시키기

저장소를 clone한 것만으로 모든 AI가 Markdown 문서를 자동으로 읽는 것은 아닙니다.
이 저장소는 각 도구의 저장소 지시 파일이 `PROJECT_CONTEXT.md`와
`EXPERIMENT_HISTORY.md`를 먼저 읽도록 연결되어 있습니다.

| VS Code에서 사용하는 도구 | 연결 파일 |
|---|---|
| GitHub Copilot Chat | `.github/copilot-instructions.md` |
| OpenAI Codex | `AGENTS.md` |
| Claude Code | `CLAUDE.md` |
| Cursor | `.cursor/rules/project-context.mdc` |

새 채팅의 첫 메시지로 아래 문장을 보내면 현재 작업 전에 문서를 실제로 읽었는지
확인하기 쉽습니다.

```text
저장소 루트의 PROJECT_CONTEXT.md와 EXPERIMENT_HISTORY.md를 처음부터 끝까지
읽고, 현재 실험 수·다음 EXP-ID·GitHub 작업 규칙을 요약한 뒤 이 작업을 시작해줘.
문서에 없는 실험 결과나 점수는 만들지 마.
```

AI가 답변에 파일을 첨부할 수 있는 도구라면 두 파일을 명시적으로 context에
추가하는 것도 좋습니다. AI가 제안한 내용은 팀 규칙을 대신하지 않으며, 최종
책임은 작업자와 리뷰어에게 있습니다.

Copilot Chat에서는 답변의 **References** 목록에
`.github/copilot-instructions.md`가 표시되는지 확인할 수 있습니다.

## 6. 대회 데이터 배치

Dacon에서 받은 파일을 다음 위치에 직접 복사합니다.

```text
data/raw/train.csv
data/raw/test.csv
data/raw/sample_submission.csv
```

원본 CSV는 `.gitignore`로 제외되어 있으므로 Git에 추가하지 않습니다. 파일명과
스키마를 확인합니다.

```bash
uv run python scripts/validate_data.py
```

검증에 실패하면 임의로 CSV를 수정하지 말고 `data/README.md`의 크기·SHA-256과
자신의 파일을 먼저 비교합니다.

## 7. 초기 검증

아래 명령이 모두 통과하면 개발 준비가 끝난 것입니다.

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/validate_experiment.py
```

노트북을 열 때는 우측 상단 **Select Kernel**에서 앞서 만든 `.venv` Python
인터프리터를 선택합니다.

## 8. 첫 작업 시작 방법

코드, 문서, 실험, 버그 수정은 모두 GitHub Issue에서 시작합니다.

1. GitHub에서 작업 하나당 Issue 하나를 등록합니다.
2. 최신 `main`을 받은 뒤 Issue 번호가 들어간 브랜치를 만듭니다.

```bash
git switch main
git pull --ff-only origin main
git switch -c issue-<번호>-<짧은설명>
```

예를 들어 Issue #12의 baseline 실험 브랜치는 다음과 같습니다.

```bash
git switch -c issue-12-exp001-baseline
```

작업과 테스트 후 같은 번호를 넣어 커밋하고 push합니다.

```bash
git status
git add <변경한-파일>
git commit -m "exp(#12): EXP-001 baseline"
git push -u origin issue-12-exp001-baseline
```

그다음 `main`을 대상으로 PR을 만들고 본문 첫 부분에 `Closes #12`를 적습니다.
팀원 확인, 비작성자 승인, CI 통과 후에만 merge합니다. 실험을 시작하기 전에는
반드시 `PROJECT_CONTEXT.md`의 전체 실험·재현성 규칙을 다시 확인합니다.

## 9. 자주 생기는 문제

### `uv: command not found`

터미널과 VS Code를 다시 시작합니다. 계속 실패하면
[uv 설치 문서](https://docs.astral.sh/uv/getting-started/installation/)의 PATH
설명을 확인합니다.

### `.venv`가 인터프리터 목록에 없음

저장소 루트에서 `uv sync --frozen --group dev`를 다시 실행하고 VS Code의
**Developer: Reload Window** 후 **Python: Select Interpreter**를 실행합니다.

### `uv.lock`이 바뀜

단순 초기 설정 중에는 `uv.lock`을 변경하면 안 됩니다. 패키지 변경이 필요한 별도
Issue가 아니라면 변경 원인을 확인하고 작업 브랜치에 포함하지 않습니다.

### 데이터 검증 실패

파일 경로와 이름을 먼저 확인합니다. 같은 이름이라도 파일 버전이 다를 수 있으므로
`data/README.md`의 SHA-256과 비교합니다. 원본 데이터를 직접 편집하지 않습니다.

## 10. 공식 참고 문서

- [uv 설치](https://docs.astral.sh/uv/getting-started/installation/)
- [uv 프로젝트 환경](https://docs.astral.sh/uv/guides/projects/)
- [VS Code Python 환경](https://code.visualstudio.com/docs/python/environments)
- [GitHub Copilot 저장소 사용자 지정 지침](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide?tool=vscode)
