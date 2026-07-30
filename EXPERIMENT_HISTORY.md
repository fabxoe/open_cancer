# 암종 분류 실험 기록

> 실제로 실행하거나 제출한 내용만 기록합니다.
> 작성 규칙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)를 따릅니다.

## 현재 상태

- 실제 실험 수: 1
- 실험 ID 규칙: GitHub Experiment Issue #N → EXP-NNN
- 다음 실험: Experiment Issue를 먼저 생성하고 발급된 번호를 사용
- 최고 Local OOF Macro F1: 0.4043796587000222 (`EXP-005`)
- 최고 Public LB Macro F1: N/A
- 최고 재현 검증 모델: N/A
- 최종 갱신일: 2026-07-30

## 실험 요약

| ID | 상태 | 실행자 | Issue | 모델·메모(선택) | OOF Macro F1 | Public LB | 재현 상태 | 판단 | 상세 기록 |
|---|---|---|---|---|---:|---:|---|---|---|
| EXP-005 | COMPLETED | 2heej | #5 | XGBoost + 유전자×변이유형 희소 피처 | 0.4043796587000222 | 미제출 | NOT_STARTED | 기준 결과로 보관 | [상세](#exp-005-xgboost--유전자변이유형-희소-피처) |

## 리더보드 제출 이력

| 제출 시각 | 실험 ID | Issue | 제출 파일 | SHA-256 | Public 점수 | 순위 | 재현 상태 |
|---|---|---|---|---|---:|---:|---|

## 재현성 검증 이력

| 검증 시각 | 실험 ID | 검증자 | 소스 커밋·태그 | 데이터 일치 | 제출 재생성 | 재학습 검증 | 결과 | 증빙 |
|---|---|---|---|---|---|---|---|---|

## 상세 실험 로그

<!-- 실제 실험 로그는 이 줄 아래에 시간순으로 추가합니다. -->

### [EXP-005] XGBoost + 유전자×변이유형 희소 피처

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #5 / issue-5-hgvs-protein-normalization
- 소스 commit: 816d0a5e070c29d2f549e4fb25b81ec5c0ad5f7b
- 시작/종료: 2026-07-30T09:13:28.135923+00:00 / 2026-07-30T09:18:18.616817+00:00

#### 실행
- Config: `reproducibility/exp005_xgb_mutation_features/config.resolved.yaml`
- Metrics: `reports/exp005_xgb_mutation_features/metrics.json`

#### 결과
- Fold Macro F1: [0.3957389475242374, 0.41264527023707276, 0.4011635978874454, 0.39173710435471243, 0.4130462426049025]
- OOF Macro F1: 0.4043796587000222
- Public LB: 미제출
- 재현 상태: NOT_STARTED

#### 산출물과 결론
- Metrics/Report/Reproduction: `reports/exp005_xgb_mutation_features/metrics.json` / N/A (별도 분석 report 미작성) / NOT_STARTED (`reproducibility/exp005_xgb_mutation_features/config.resolved.yaml`만 저장)
- 결론: 첫 공식 유전자×변이유형 피처 기준 결과로 보관. 이전 공식 실험이 없어 상대 성능 비교는 확인 필요.
