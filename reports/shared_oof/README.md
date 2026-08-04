# 팀 공유용 소형 OOF 확률

이 디렉터리는 팀장이 승인한 소형 OOF 확률 CSV의 Git 편의 복제본만 둡니다.
정책의 단일 원본은 `PROJECT_CONTEXT.md`의 **팀 상위 모델 산출물 요청·공유 규칙**입니다.

- 허용: `ID`와 고정 순서의 26개 클래스 예측 확률
- 금지: 정답 라벨, 원본 변이값, fold, test 확률, 개인정보와 외부 비공개 데이터
- 한도: Issue/manifest당 25 MiB, 저장소 전체 100 MiB. 프로젝트 자체의 파일당
  별도 한도는 두지 않으며 GitHub 플랫폼 제한만 적용합니다.
- 각 하위 디렉터리는 `manifest.json`에 승인 Issue, source commit, 생성 명령,
  Release URL, 파일 크기·SHA-256·행 수를 기록합니다.
- checkpoint와 공식 재현성 원본은 계속 GitHub Release에 보관합니다.

검증:

```bash
uv run python scripts/validate_shared_oof.py
```
