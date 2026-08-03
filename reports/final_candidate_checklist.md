# 최종 후보 제출·재현 체크리스트

이 문서는 팀원 확인 전까지 가능한 최종 후보 준비를 모아 둔 운영 문서입니다.
리더보드에 이미 제출한 파일을 다시 제출하지 않으며, 실제 점수의 원본은
`EXPERIMENT_HISTORY.md`입니다. Public 결과를 보고 피처·checkpoint 기준이나 blend
가중치를 역으로 조정하지 않습니다.

## 현재 후보

| 우선순위 | 후보 | Local OOF Macro F1 | Public | 재현 상태 | 현재 판단 |
|---:|---|---:|---:|---|---|
| 1 | EXP-253 LightGBM·XGBoost 고정 0.5/0.5 blend | 0.4254998819 | 미제출 | `INFERENCE_VERIFIED` | 현재 Local 최고. #260 원격 manifest 검증 완료 후 제출 후보 |
| 2 | EXP-229 pathway mutation-type XGBoost | 0.4229885745 | 미제출 | `INFERENCE_VERIFIED` | 가장 강한 단일 XGBoost 후보. #260 완료 대기 |
| 3 | EXP-223 pathway Macro-F1 checkpoint XGBoost | 0.4213739476 | 0.323243525 | `INFERENCE_VERIFIED` | 현재 Public 최고 기준점 |
| 4 | EXP-125 LightGBM v1 | 0.4189078364 | 0.3075810937 | `INFERENCE_VERIFIED` | EXP-253의 다양성 부모·기존 제출 기준점으로 보존 |

EXP-253은 EXP-209 LightGBM과 EXP-229 XGBoost의 사전 고정 0.5/0.5 확률 평균이다.
OOF를 본 뒤 다른 가중치를 탐색하지 않았고, EXP-229 대비 Macro F1
`+0.0025113074`, fold 표준편차 `+0.0019120085`로 안정성 허용치 `0.002`를 매우
근소하게 통과했다. 따라서 Local 개선은 인정하되 안정성이 크게 좋아졌다고
해석하지 않는다.

## 완료된 보관과 진행 중인 복구

- EXP-219: [`exp-219-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-219-repro-v1), Issue #258·PR #259에서 복구 완료
- EXP-223: Public 제출과 재현 증빙이 History에 기록됨
- EXP-209·229·253: Issue #260 담당자가 Release asset을 생성했으나 manifest,
  remote-storage 검증과 PR이 끝날 때까지 복구 `IN_PROGRESS`
- EXP-125: [`exp-125-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-125-repro-v1)

Release asset이 보인다는 사실만으로 `TRAINING_VERIFIED`나 복구 완료를 선언하지
않는다. 정확한 source tag, manifest URL·SHA-256, 원격 다운로드 검증과 History
연결이 같은 PR에서 확인돼야 한다.

## 제출 후보 확정 전 필수 순서

1. Issue #260의 EXP-209·229·253 manifest PR과
   `validate_experiment.py --check-remote-storage` 통과를 확인한다.
2. EXP-253 submission의 ID·26개 클래스·행 수·SHA-256을 다시 검증한다.
3. Issue #233의 decision offset 결과가 완료돼 있으면 사전 기준으로만 비교한다.
   미완료라면 EXP-253 제출을 지연시키기 위한 가상 기대값으로 사용하지 않는다.
4. Issue #238에서 같은 플랫폼·교차 플랫폼 검증 범위를 명시한다.
5. 최종 수상 후보는 비작성자가 fresh clone에서 재학습하고
   `TRAINING_VERIFIED` 조건을 통과한 뒤 지정한다.

## 현재 중단한 방향

- EXP-240·245·250의 연속 하락을 근거로 신규 문헌 조합 family 확장을 중단한다.
- EXP-253의 blend 가중치를 Public 또는 test 분포로 다시 탐색하지 않는다.
- PR #255의 seed별 원본 JSON·정확한 실행 명령이 보존되기 전 Issue #254의 DLBC
  gate를 변경하지 않는다.

## 다음 의사결정

- #260 완료 전: #233과 #238처럼 후보 파일을 변경하지 않는 독립 검증을 진행한다.
- #260 완료 후: EXP-253을 첫 미제출 후보로 검증하고 수동 제출 여부를 결정한다.
- Public 확인 후: 점수는 즉시 History에 기록하되 가중치나 피처를 역최적화하지
  않는다.
