# Vera EXP-094 후속 검토

## 목적

EXP-094로 Feature Spec v1을 동결한 뒤, 기존 모델 다양화·stacking 로드맵을
Vera의 후속 권고와 비교했습니다. 원 대화는
[Vera Health](https://www.verahealth.ai/search/22adc84e-7e57-4766-945f-a21fa795db24)에
있으며, 이 문서는 답변을 그대로 복사하지 않고 프로젝트에 필요한 결정만
요약합니다.

## 수집 방법

전체 DOM snapshot은 사용하지 않았습니다. 실제 스크롤 컨테이너의 60.03%부터
99.999%까지 viewport 높이 1,402px에서 최대 980px씩 이동해 약 30%가 겹치는
41개 프레임을 임시 디스크에 저장했습니다. 프레임 간 최대 이동량이 viewport보다
작아 60~100% 구간에 빈 화면 영역이 없음을 manifest로 확인했습니다.

EXP-094 결과를 Vera에 전달한 뒤 새 답변은 하단부터 질문 경계까지 7개 겹침
프레임으로 별도 저장했습니다. 임시 원본은 저장소에 커밋하지 않습니다.

## 일치한 판단

- EXP-094는 F1, fold 안정성, log loss와 재현성을 함께 개선해 최종 후보 자격이
  있습니다.
- Feature Spec v1은 다시 열지 않고 동일 피처·fold로 모델 다양화를 먼저
  확보합니다.
- 실행 순서는 희소 선형 모델, LightGBM, 필요 시 CatBoost가 안전합니다.
- calibration과 class-wise threshold는 최종 후보 전까지 보류합니다.
- OOF 또는 Public LB를 보며 가중치와 피처를 반복 수정하지 않습니다.
- 최종 후보는 EXP-094 단일 모델과 검증된 ensemble/stack 최대 2개로 제한합니다.

## 강화한 기준

| 항목 | 기존 PR #99 초안 | 후속 확정 |
|---|---:|---:|
| base 모델 품질 하한 | EXP-094 대비 -0.020 | EXP-094 대비 -0.004 |
| 오류 상관 gate | 0.95 미만 | 0.92 이하 또는 라벨 불일치 10% 이상 |
| log loss gate | 명백한 악화 없음 | 최선 단일 대비 +0.01 미만 |
| 새 base 추가 중단 | 미정 | stack +0.001 미만이며 저빈도 클래스도 미개선 |
| 최종 stack 채택 | 최고 단일 대비 +0.002 | 최고 단일 또는 고정 blend 대비 +0.002 |

## Codex가 더 엄격하게 유지한 부분

Base 모델의 OOF를 모아 meta learner를 한 번 학습하면 test 예측은 만들 수 있지만,
그 meta learner의 학습 점수를 stack OOF로 사용할 수는 없습니다. 최종 로드맵은
meta learner도 canonical fold 안에서 다시 cross-fitting해 각 행을 보지 않은
meta 모델의 예측으로 stack OOF를 만듭니다.

또한 EXP-094 구성요소 제거 ablation은 해석에는 도움이 되지만 Feature Spec v1을
다시 여는 선택 편향 위험이 있습니다. 현재는 모델 다양화를 지연시키지 않고,
필요할 때만 `explore` 진단으로 분리합니다.

## B-1·C-1 결정

- B-1 functional spectrum은 모델 다양화 이후 예산이 남으면 v2 단일 ablation
  1회만 허용합니다. `+0.001` 미만 또는 저빈도 클래스 악화 시 중단합니다.
- C-1 fixed pathway burden은 출처·버전·라이선스·해시와 규정 허용성이 먼저
  확인돼야 합니다. `+0.002` 이상이 아니면 문서화·규정 비용을 감수하지 않습니다.
- 두 결과 모두 Feature Spec v1을 수정하지 않으며, 채택되면 v2로 별도 관리합니다.

## 확정 실행 순서

1. 공통 runner와 feature/fold/class/probability assert 완성
2. 희소 선형 모델 공식 5-fold
3. LightGBM 공식 5-fold
4. 다양성·확률 품질 감사
5. 필요할 때만 CatBoost 공식 5-fold
6. 사전 고정 단순 blend
7. gate 통과 시 meta-level cross-fitted stacking 1개
8. 최종 후보 최대 2개를 다른 팀원이 `TRAINING_VERIFIED`
9. 예산이 남을 때만 B-1, 이후 규정 확인된 C-1을 v2로 평가
