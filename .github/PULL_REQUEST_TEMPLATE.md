Closes #<!-- Issue 번호 -->

## 변경 목적

<!-- Issue의 목적과 이 PR이 해결하는 범위를 작성하세요. -->

## 주요 변경

- <!-- 주요 변경을 작성하세요. -->

## 테스트

```text
uv run pytest
uv run python scripts/validate_experiment.py
```

- 결과:

## 실험 및 재현성

- 관련 Issue 기반 EXP-ID: N/A
- `EXPERIMENT_HISTORY.md` 갱신: N/A
- 재현 상태: N/A
- 재현 증빙/Release:

<!-- 공식 실험이 아니라면 이 절은 N/A 그대로 두어도 됩니다. -->

## 체크리스트

- [ ] 브랜치(`N`, `N-*`, `issue-N`, `issue-N-*`) 번호가 연결된 Issue와 일치합니다.
- [ ] 공식 실험이면 Issue #N과 자동 파생 `EXP-NNN`이 일치합니다.
- [ ] 최신 `origin/main`이 반영되어 있습니다.
- [ ] 테스트와 CI `quality`가 통과했습니다.
- [ ] `data/raw/` 원본을 변경했다면 별도 데이터 Issue에서 크기·SHA-256·문서를 함께 갱신했습니다.
- [ ] 가공 데이터, 모델, OOF, 비밀 파일을 커밋하지 않았습니다.
- [ ] 실제로 측정하지 않은 실험 결과를 기록하지 않았습니다.
- [ ] 관련 팀원을 reviewer 또는 mention으로 알렸습니다.
- [ ] 모든 리뷰 대화를 해결했습니다.
