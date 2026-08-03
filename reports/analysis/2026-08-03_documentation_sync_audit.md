# 2026-08-03 17:52 KST 이전 문서 동기화 감사

## 범위

- 기준 시각: 2026-08-03 17:52 KST
- 기준 branch: 감사 시작 당시 최신 `origin/main`
- 목적: 오늘 병합된 실험·제출·재현 작업이 사실 장부와 운영 문서에 빠졌는지 확인
- 이 문서는 새 실험 결과를 만들지 않으며 실제 점수의 원본은
  `EXPERIMENT_HISTORY.md`와 각 실험의 `metrics.json`이다.

## 감사 결과

- History의 선언 실험 수, 요약표와 상세 로그는 모두 65건으로 일치했다.
- 최고 Local OOF Macro F1은 EXP-253의 `0.4254998819`다.
- 최고 Public LB Macro F1은 EXP-223의 `0.323243525`다.
- EXP-219·223·229·253의 실제 점수와 재현 상태는 History에 이미 기록돼 있었다.
- EXP-223의 Public 제출 이력도 제출 ID, SHA-256과 함께 기록돼 있었다.
- 따라서 History에 가상 행이나 중복 상세 로그를 추가하지 않았다.

## 오늘 확인된 의사결정

| 구분 | 근거 | 현재 판단 |
|---|---|---|
| checkpoint 기준 | EXP-219 | 대회 지표와 맞춘 validation Macro F1 checkpoint 정책 채택. 같은 validation에서 선택·평가한 낙관 편향 가능성은 별도 표기 |
| Public 기준점 | EXP-223 | Public `0.323243525`로 팀 최고 갱신 |
| 단일 XGBoost 후보 | EXP-229 | OOF `0.4229885745`, 조건부 채택 |
| 고정 모델 blend | EXP-253 | EXP-209·229의 사전 고정 0.5/0.5 평균, OOF `0.4254998819`로 현재 Local 최고 |
| 추가 문헌 피처 | EXP-240·245·250 | EXP-229보다 낮아 현재 family 확장 중단 근거로 사용 |

## 동기화가 필요했던 문서

- ABC-Stack 로드맵이 EXP-125와 G5 이전 상태를 현재 후보처럼 표시하고 있었다.
- 최종 후보 체크리스트가 EXP-125만 가리켜 EXP-223·229·253과 연결되지 않았다.
- checkpoint 선택과 재현 검증의 플랫폼 범위를 팀 공통 규칙으로 더 명확히 할
  필요가 있었다.

이 세 항목을 Issue #261에서 갱신한다. EXP-209·229·253의 Release asset은 감사
도중 원격에 생성된 것을 확인했지만, Issue #260의 manifest 갱신·remote-storage
검증과 PR이 끝나기 전에는 복구 완료로 기록하지 않는다.

## 이어지는 작업

- [Issue #233](https://github.com/fabxoe/open_cancer/issues/233): EXP-219 기반
  nested class-wise decision offset
- [Issue #238](https://github.com/fabxoe/open_cancer/issues/238): 플랫폼 간
  XGBoost 재현성 계약
- [Issue #254](https://github.com/fabxoe/open_cancer/issues/254): DLBC 소수 클래스
  gate의 seed 변동성 검토
- [Issue #260](https://github.com/fabxoe/open_cancer/issues/260): EXP-209·229·253
  원본 artifact와 Release manifest 복구

## 검증 원칙

- #260이 닫히기 전 EXP-253의 Release 준비를 완료로 표시하지 않는다.
- PR #255의 seed별 원본 결과와 실행 명령이 저장되기 전 DLBC gate를 바꾸지 않는다.
- Public 점수를 보고 blend 가중치나 피처 규칙을 다시 맞추지 않는다.
