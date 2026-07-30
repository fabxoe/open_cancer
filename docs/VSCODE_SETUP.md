# VS Code + uv 초기 설정

이 문서는 저장소를 처음 clone한 macOS·Windows 팀원이 같은 Python 환경과 검증
조건을 준비하고, OpenAI Codex 또는 Claude Code로 안전하게 첫 작업을 시작하는
과정을 설명합니다. 명령어는 저장소 루트(`open_cancer`)에서 실행합니다.

## 0. 이 설정이 끝나면

- 팀과 같은 Python 3.11.10 및 패키지 버전을 사용합니다.
- VS Code가 저장소의 `.venv`를 Python 환경으로 사용합니다.
- 원본 데이터가 팀 기준 파일과 같은지 확인합니다.
- 공용 5-fold split의 의미와 사용법을 이해합니다.
- Codex와 Claude Code가 같은 프로젝트·실험·Git 규칙을 읽습니다.

프로젝트 운영 규칙의 단일 원본은 `PROJECT_CONTEXT.md`이고, 실제로 수행한 실험과
제출의 사실 장부는 `EXPERIMENT_HISTORY.md`입니다.

## 1. 준비 프로그램

다음 프로그램을 먼저 설치합니다.

1. [Git](https://git-scm.com/downloads)
2. [Visual Studio Code](https://code.visualstudio.com/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/)

### macOS에서 uv 설치

Homebrew를 사용한다면 다음 명령을 권장합니다.

```bash
brew install uv
```

Homebrew가 없다면 공식 설치 스크립트를 사용합니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
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
clone한 `open_cancer` 폴더를 엽니다. 상위 폴더가 아니라 `open_cancer` 자체를
열어야 AI 도구와 Python 확장이 저장소 루트를 올바르게 찾습니다.

VS Code가 권장 확장 설치를 묻는다면 **Install**을 누릅니다. 직접 확인하려면
Extensions 화면에서 `@recommended`를 검색합니다.

- Python, Pylance, Python Environments
- Jupyter
- OpenAI Codex
- Claude Code

Codex만 사용하는 팀원도 Claude Code 확장을 반드시 사용할 필요는 없으며, 반대도
마찬가지입니다.

## 3. 고정된 Python 환경 만들기

VS Code에서 **Terminal → New Terminal**을 열고 실행합니다.

```bash
uv sync --frozen
```

`uv`는 `.python-version`의 Python 3.11.10을 확인하고, 컴퓨터에 없으면 자동으로
다운로드합니다. 이어서 저장소의 `.venv` 가상환경을 만들고 `uv.lock`에 기록된
정확한 패키지 버전을 설치합니다. 기본 `dev` 그룹도 자동으로 포함됩니다.
`--frozen`은 초기 설정 중 팀 공통 lock 파일을 임의로 바꾸지 않게 합니다.

설치를 확인합니다.

```bash
uv run python --version
uv run python -c "import open_cancer; print('환경 설정 완료')"
```

## 4. VS Code Python 인터프리터 선택

1. `Cmd+Shift+P`(macOS) 또는 `Ctrl+Shift+P`(Windows)를 누릅니다.
2. **Python: Select Interpreter**를 검색해 실행합니다.
3. 저장소 안의 `.venv`를 선택합니다.

표시되는 실제 경로는 다음과 같습니다.

```text
macOS:   <저장소>/.venv/bin/python
Windows: <저장소>\.venv\Scripts\python.exe
```

목록에 `.venv`가 보이지 않으면 **Developer: Reload Window**를 실행한 뒤 다시
선택합니다. 노트북에서는 우측 상단 **Select Kernel**을 눌러 같은 `.venv`
인터프리터를 선택합니다.

## 5. 대회 데이터 배치와 검증

Dacon에서 받은 파일을 다음 위치에 직접 복사합니다.

```text
data/raw/train.csv
data/raw/test.csv
data/raw/sample_submission.csv
```

원본 CSV는 GitHub에 올라가지 않으며 `.gitignore`로 제외되어 있습니다. 파일명,
행·열 수, ID 순서, 클래스, 유전자 컬럼과 SHA-256을 한 번에 확인합니다.

```bash
uv run python scripts/validate_data.py
```

검증에 실패하면 CSV를 수정하지 말고 `data/README.md`의 SHA-256과 자신의 파일을
비교합니다. 팀 데이터와 다른 상태에서는 모델 실험을 시작하지 않습니다.

## 6. 공용 split이란?

### 먼저 알아둘 용어

- **split**: train 데이터를 학습용과 검증용으로 나누는 규칙입니다.
- **fold**: 교차 검증에서 나눈 조각 하나입니다.
- **5-fold**: train을 5조각으로 나누고, 한 조각씩 번갈아 검증용으로 사용하는
  방식입니다.
- **OOF(Out-of-Fold) 예측**: 각 샘플이 학습에서 제외되어 검증용이었을 때 얻은
  예측입니다.

이 저장소의 공용 split 파일은 다음 두 개입니다.

```text
data/splits/stratified_5fold_seed42.csv
data/splits/stratified_5fold_seed42.meta.json
```

CSV에는 다음처럼 `ID`와 `fold`만 있습니다.

```text
ID,fold
TRAIN_0000,2
TRAIN_0001,4
TRAIN_0002,1
```

`TRAIN_0000,2`는 이 샘플을 fold 2 차례에 **검증 데이터**로 사용한다는 뜻입니다.
fold 2 모델을 학습할 때는 fold가 2가 아닌 샘플을 학습용으로 사용합니다.

### 실험하지 않았는데 왜 이미 있나요?

공용 split은 모델이나 실험 결과가 아니라 **검증 문제지 배정표**입니다.

원본 train의 `ID`와 정답 `SUBCLASS`만 이용해
`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`로 만들었습니다.
모델을 학습하거나 예측·점수를 계산하지 않았으므로 실험 0건인 초기 저장소에
미리 준비할 수 있습니다.

`stratified`는 26개 암종의 비율이 각 fold에 최대한 비슷하게 들어가도록 나눈다는
뜻입니다. 이 대회처럼 클래스 수가 불균형하고 적은 클래스가 있는 경우, 단순
무작위 분할보다 각 fold가 전체 데이터를 더 잘 대표하게 해줍니다.

현재 배정은 train 6,201개 전체를 정확히 한 번씩 포함합니다.

| fold | 검증 샘플 수 |
|---:|---:|
| 0 | 1,241 |
| 1 | 1,240 |
| 2 | 1,240 |
| 3 | 1,240 |
| 4 | 1,240 |

`meta.json`에는 fold 수, seed, 원본 train SHA-256, split CSV SHA-256이 들어 있어
다른 팀원이 정확히 같은 배정표를 썼는지 확인할 수 있습니다.

### 공용 split을 사용하면 좋은 이유

1. **모델을 공정하게 비교할 수 있습니다.** 팀원마다 다른 검증 데이터를 쓰면
   모델이 좋아진 것인지 우연히 쉬운 데이터가 들어간 것인지 구분하기 어렵습니다.
2. **모든 train 샘플을 검증할 수 있습니다.** 5번 학습하면 각 샘플이 한 번씩
   검증용이 되고, 전체 OOF Macro F1을 계산할 수 있습니다.
3. **재현이 쉬워집니다.** 모델, seed, 환경과 함께 split 해시를 기록하면 다른
   팀원이 같은 검증 조건을 복원할 수 있습니다.
4. **앙상블 판단이 쉬워집니다.** 같은 ID·fold 순서의 OOF 확률을 저장하면 서로
   다른 모델의 오류와 확률을 같은 기준으로 비교할 수 있습니다.

공용 split이 미래의 모든 검증 방식에 항상 최선이라는 뜻은 아닙니다. 다만 팀의
기본 비교 기준을 하나로 고정해 실험 초기의 혼란을 줄이는 역할을 합니다.

### 코드에서 불러오는 방법

먼저 train과 split을 `ID`로 안전하게 연결합니다.

```python
from pathlib import Path

import pandas as pd

project_root = Path.cwd()
if project_root.name == "notebooks":
    project_root = project_root.parent

train = pd.read_csv(
    project_root / "data/raw/train.csv",
    dtype=str,
    keep_default_na=False,
)
folds = pd.read_csv(
    project_root / "data/splits/stratified_5fold_seed42.csv",
    dtype={"ID": str, "fold": int},
)

train = train.merge(folds, on="ID", how="left", validate="one_to_one")

assert len(train) == 6201
assert train["fold"].notna().all()
assert set(train["fold"]) == {0, 1, 2, 3, 4}
```

fold 0부터 4까지 반복하면서 해당 fold만 검증용으로 선택합니다.

```python
gene_columns = [column for column in train.columns if column not in {"ID", "SUBCLASS", "fold"}]

for fold in range(5):
    fold_train = train.loc[train["fold"] != fold].copy()
    fold_valid = train.loc[train["fold"] == fold].copy()

    X_train = fold_train[gene_columns]
    y_train = fold_train["SUBCLASS"]
    X_valid = fold_valid[gene_columns]
    y_valid = fold_valid["SUBCLASS"]

    # 1. 인코더·결측 처리·feature selection은 X_train으로만 fit
    # 2. X_train과 X_valid를 각각 transform
    # 3. 모델은 X_train, y_train으로 학습
    # 4. X_valid 예측을 해당 ID의 OOF 위치에 저장
```

이 과정을 5번 수행하면 모든 train ID의 OOF 예측이 한 번씩 채워집니다. test는
각 fold 모델로 예측한 확률 5개를 평균내는 것이 기본 방식입니다.

### 공용 split 사용 규칙

- 기본 비교 실험에서는 현재 CSV를 그대로 읽기만 합니다.
- 개인 노트북에서 `train_test_split`이나 새 `KFold`를 즉석 생성하지 않습니다.
- `fold` 값을 수정하거나 CSV를 덮어쓰지 않습니다.
- `scripts/create_folds.py`는 공용 split 유지보수용입니다. 일반 실험 시작 때마다
  실행하는 스크립트가 아닙니다.
- 다른 seed, fold 수, group split 등을 검증하려면 별도 GitHub Issue와 새
  EXP-ID를 만들고 기존 파일을 덮어쓰지 않는 새 이름으로 저장합니다.
- 실험의 resolved config와 재현성 manifest에는 split 경로와 SHA-256을 기록합니다.

현재 split을 연결하는 실행 가능한 예시는
`notebooks/XGB를 활용한 암종분류.ipynb`에 있습니다. 이 노트북도 아직 모델 학습이나
점수 계산을 수행하지 않습니다.

## 7. Codex와 Claude Code의 공통 사용법

### 도구별 프로젝트 지시 파일

| 도구 | 자동으로 읽는 저장소 파일 |
|---|---|
| OpenAI Codex | `AGENTS.md` |
| Claude Code | `CLAUDE.md` → `AGENTS.md` 가져오기 |

두 도구는 다음과 같은 하나의 공통 지침 흐름을 사용합니다.

```text
Codex: AGENTS.md
Claude Code: CLAUDE.md → AGENTS.md
        ↓
PROJECT_CONTEXT.md 전체 읽기
        ↓
EXPERIMENT_HISTORY.md 전체 읽기
        ↓
Issue·브랜치·실험 상태 확인 후 작업
```

Codex는 저장소의 `AGENTS.md`를 작업 지침으로 읽습니다. Claude Code는 저장소의
`CLAUDE.md`를 세션 컨텍스트로 읽고, 그 파일의 `@AGENTS.md` 지시로 같은
`AGENTS.md`를 가져옵니다. 상세 규칙은 공통 문서인 `PROJECT_CONTEXT.md` 한
곳에서 관리합니다.

### VS Code에서 시작

**Codex 사용자**

1. Extensions에서 **Codex – OpenAI's coding agent**를 설치합니다.
2. OpenAI 계정으로 로그인합니다.
3. `open_cancer` 폴더를 연 VS Code 창에서 Codex 사이드바를 엽니다.
4. 새 작업은 새 채팅으로 시작합니다.

**Claude Code 사용자**

1. Extensions에서 **Claude Code**를 설치합니다.
2. Anthropic 계정으로 로그인합니다.
3. Activity Bar의 Claude 아이콘 또는 Command Palette의
   **Claude Code: Open in New Tab**으로 엽니다.
4. 새 작업은 새 대화로 시작합니다.

### 두 도구에 똑같이 보내는 첫 메시지

```text
저장소 루트의 PROJECT_CONTEXT.md와 EXPERIMENT_HISTORY.md를 처음부터 끝까지
읽어줘. 현재 실제 실험 수, 다음 EXP-ID, 현재 Git 브랜치와 연결된 Issue,
이번 작업 후 실행할 검증 명령을 먼저 요약해줘.

문서에 없는 실험 결과·점수·산출물은 만들지 말고, 공용 split은 별도 실험
Issue가 없는 한 변경하지 마.
```

AI가 다음 네 가지를 정확히 답했는지 확인한 뒤 작업을 요청합니다.

- 실제 실험 수와 다음 EXP-ID
- 현재 브랜치
- 연결된 GitHub Issue 번호
- 작업 후 실행할 테스트·검증 명령

### 실제 작업 요청 방식

첫 확인이 끝나면 Issue 번호와 완료 조건을 구체적으로 전달합니다.

```text
Issue #12 작업이야.
목표: EXP-001 XGBoost baseline을 공용 5-fold split으로 구현해줘.
완료 조건: config, OOF, fold/전체 Macro F1, 재현성 manifest, History 갱신,
pytest와 실험 기록 검증 통과.
작업 전 변경 범위를 설명하고, 끝나면 실제 실행 결과만 보고해줘.
```

Codex와 Claude Code 중 어느 도구를 쓰더라도 다음 원칙은 같습니다.

1. Issue 없는 작업을 시작하지 않습니다.
2. AI가 파일을 수정하기 전 현재 브랜치를 확인합니다.
3. diff와 실행 명령을 사람이 검토합니다.
4. Local 점수는 실제 실행 결과만 기록합니다.
5. Public LB 점수는 사람이 실제 제출 화면에서 확인한 값만 전달합니다.
6. 작업 종료 시 테스트 결과와 `git status`를 확인합니다.
7. PR은 팀 리뷰와 CI 통과 후 merge합니다.

한 작업 브랜치를 Codex와 Claude가 동시에 수정하게 두지 않습니다. 도구를 바꿀
때는 기존 작업을 커밋하거나 변경 상태를 명확히 남기고, 새 대화에서 두 핵심
문서와 `git diff`를 다시 읽게 합니다.

## 8. 초기 검증

아래 명령이 모두 통과하면 개발 준비가 끝난 것입니다.

```bash
uv run pytest
uv run python scripts/validate_experiment.py
```

`validate_experiment.py` 결과의 실험 수가 초기에는 0으로 나오는 것이 정상입니다.
공용 split 파일이 있어도 실제 모델 실험을 수행한 것은 아닙니다.

## 9. 첫 GitHub 작업 시작

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
팀원 확인, 비작성자 승인, CI 통과 후에만 merge합니다.

## 10. 자주 생기는 문제

### `uv: command not found`

터미널과 VS Code를 다시 시작합니다. 계속 실패하면
[uv 설치 문서](https://docs.astral.sh/uv/getting-started/installation/)의 PATH
설명을 확인합니다.

### `.venv`가 인터프리터 목록에 없음

저장소 루트에서 `uv sync --frozen`을 다시 실행하고 VS Code의
**Developer: Reload Window** 후 **Python: Select Interpreter**를 실행합니다.

### `uv.lock`이 바뀜

단순 초기 설정 중에는 `uv.lock`을 변경하면 안 됩니다. 패키지 변경이 필요한 별도
Issue가 아니라면 변경 원인을 확인하고 작업 브랜치에 포함하지 않습니다.

### 데이터 검증 실패

파일 경로와 이름을 먼저 확인합니다. 같은 이름이라도 파일 버전이 다를 수 있으므로
`data/README.md`의 SHA-256과 비교합니다. 원본 데이터를 직접 편집하지 않습니다.

### 공용 split을 다시 만들어야 하나요?

아닙니다. 정상 clone에서는 split CSV와 메타데이터가 이미 Git으로 내려옵니다.
기본 실험에서는 그대로 읽습니다. 파일이 변경된 것처럼 보이면 새로 만들기 전에
`git status`와 팀 저장소의 원본을 비교합니다.

### AI가 PROJECT_CONTEXT.md를 읽지 않은 것 같음

새 채팅을 열고 7절의 공통 첫 메시지를 다시 보냅니다. Codex는 `AGENTS.md`,
Claude Code는 `CLAUDE.md`가 저장소 루트에 있는지 확인합니다. VS Code에서
상위 폴더가 아니라 `open_cancer` 폴더 자체를 열었는지도 확인합니다.

## 11. 공식 참고 문서

- [uv 설치](https://docs.astral.sh/uv/getting-started/installation/)
- [uv 프로젝트 환경](https://docs.astral.sh/uv/guides/projects/)
- [VS Code Python 환경](https://code.visualstudio.com/docs/python/environments)
- [OpenAI Codex IDE 확장](https://learn.chatgpt.com/docs/codex/ide)
- [OpenAI Codex의 AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Claude Code VS Code 확장](https://code.claude.com/docs/en/vs-code)
- [Claude Code의 CLAUDE.md](https://code.claude.com/docs/en/memory)
