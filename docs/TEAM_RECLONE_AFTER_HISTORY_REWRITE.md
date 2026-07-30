# Git history 재작성 후 팀원 재설정

2026-07-30 주최측의 원본 데이터 GitHub 업로드 금지 지침에 따라 저장소의 모든
일반 브랜치와 태그에서 `data/raw/` 원본 CSV와 직접 생성한 PDF를 제거했습니다.
이 과정에서 Git commit SHA가 변경되었습니다.

## 대상

2026-07-30 원본 데이터 제거 전에 이 저장소를 clone한 모든 팀원에게 적용됩니다.

## 기존 clone에서 하지 말아야 할 작업

- `git pull`
- `git merge origin/main`
- 기존 local branch를 원격에 push
- 기존 commit을 새 branch에 merge

위 작업은 제거 전 Git history를 원격에 다시 넣을 수 있습니다.

## 안전한 재설정

1. 기존 clone의 `data/raw/` 원본 CSV와 Git 제외 산출물이 필요하면 저장소 밖의
   개인 로컬 폴더에 복사합니다. GitHub나 공개 링크에는 올리지 않습니다.
2. 작업 중인 코드가 원격 branch에 push됐는지 GitHub에서 확인합니다. 미반영 코드가
   있다면 기존 commit을 merge하지 말고 필요한 소스 파일만 별도로 보관한 뒤
   팀 리더와 새 branch 반영 방법을 확인합니다.
3. 기존 저장소 폴더는 즉시 삭제하기보다 `*_before_history_rewrite`처럼 이름을
   바꿔 격리합니다.
4. 저장소를 새로 clone합니다.

   ```bash
   git clone https://github.com/fabxoe/open_cancer.git
   cd open_cancer
   uv sync --frozen
   ```

5. 주최측 공식 다운로드 또는 팀에서 승인한 비공개 전달 방법으로 받은 파일을
   새 clone의 `data/raw/`에 배치합니다.

   ```text
   data/raw/train.csv
   data/raw/test.csv
   data/raw/sample_submission.csv
   ```

6. 원본 파일이 Git에서 무시되는지 확인합니다.

   ```bash
   git check-ignore data/raw/train.csv
   git ls-files data/raw
   ```

   첫 명령은 `data/raw/train.csv`를 출력해야 하고, 두 번째 명령은
   `data/raw/.gitkeep`만 출력해야 합니다.

7. 데이터 무결성과 환경을 확인합니다.

   ```bash
   uv run python scripts/validate_data.py
   uv run pytest
   ```

## 기존 작업 branch 이어가기

원격 작업 branch도 정리된 history로 갱신되어 있습니다. 반드시 새 clone에서
원격 branch를 받아 이어갑니다.

```bash
git fetch origin
git switch <기존-브랜치명>
```

기존 clone의 local branch와 새 원격 branch를 merge하거나 force push하지 않습니다.
