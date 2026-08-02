# G7 독립 재학습 검증 결과

Issue #162에서 fresh clone과 Secure Cloud RTX 4090 환경으로 EXP-131·EXP-125를
재학습했습니다. 원본 작성자 실행과 비교했으며, Public LB 점수는 선택에 사용하지
않았습니다.

| 후보 | 원본 OOF Macro F1 | 독립 실행 OOF Macro F1 | 차이 | 확률·제출 비교 | 판정 |
|---|---:|---:|---:|---|---|
| EXP-131 | 0.4222392962 | 0.4217678410 | -0.0004714552 | GPU 재학습 변동으로 원본과 동일하지 않음 | TRAINING_VERIFIED 보류 |
| EXP-125 | 0.4189078364 | 0.4189078364 | 0 | OOF/test 확률·라벨·submission SHA-256 일치 | 독립 실행 통과 |

## 환경

- fresh clone: 각 Issue 브랜치에서 별도 clone
- Python 3.11.10, `uv sync --frozen --group experiment`
- NVIDIA RTX 4090 24GB, XGBoost/CatBoost/LightGBM lock 버전
- 원본 train/test/sample SHA-256 일치

## 해석

EXP-125는 독립 환경에서도 동일한 결과가 나왔습니다. 다만 저장소 계약상 최종
`TRAINING_VERIFIED` 승격에는 실험 작성자가 아닌 **사람 팀원**의 확인 댓글 또는
재실행이 필요합니다. Codex가 수행한 fresh clone 실행은 증빙으로 보존하되 사람
검증자를 대신하지 않습니다.

EXP-131은 CatBoost GPU 비결정성으로 OOF 점수가 변동했습니다. checkpoint inference
자체는 재현됐지만 원본 재학습과 동일한 점수를 보장하지 못하므로
`TRAINING_VERIFIED`로 승격하지 않습니다.

## 다음 행동

1. 팀원이 EXP-125 fresh clone 실행 로그를 확인하고 검증 댓글을 남깁니다.
2. EXP-125만 최종 제출 후보로 우선 검토합니다.
3. EXP-131은 diversity/최고 Local 후보 기록만 유지하고 추가 CatBoost 확장은 중단합니다.
