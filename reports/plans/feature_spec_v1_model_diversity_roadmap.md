# Feature Spec v1 모델 다양화·스태킹 로드맵

> 이 문서는 EXP-094로 동결한 Feature Spec v1의 모델 다양화, 앙상블과 최종
> 재현 검증 순서를 관리합니다. 실제 점수는 `EXPERIMENT_HISTORY.md`와 각 실험의
> `metrics.json`만을 원본으로 사용하며 예상 점수나 가상 결과를 기록하지 않습니다.

## 현재 기준

- 관리 Task: [Issue #98](https://github.com/fabxoe/open_cancer/issues/98)
- 관리 PR: [PR #99](https://github.com/fabxoe/open_cancer/pull/99) (`PR_OPEN`)
- 기준 Feature Spec: EXP-094, SHA-256
  `1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`
- 기준 XGBoost OOF Macro F1: `0.4168865739`
- 기준 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출
- 고정 평가: canonical 5-fold, 고정 26개 클래스 순서, Macro F1
- 다음 행동: 모델 공통 runner·확률 산출물 계약을 일반 Task로 구현

## 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | 판단 기준 | 다음 행동 |
|---|---|---:|---|---:|---|---|---|
| G0 | 공통 입력·산출물 QC와 runner 계약 | #98 | 해당 없음 | 미발급 | IN_PROGRESS | Feature Spec·fold·클래스 해시 강제 | 구현·테스트 |
| G1 | LightGBM 공식 5-fold | 미발급 | 미발급 | - | PLANNED | 단일 모델 품질·다양성 측정 | G0 병합 대기 |
| G2 | CatBoost 공식 5-fold | 미발급 | 미발급 | - | PLANNED | 단일 모델 품질·다양성 측정 | G1과 독립 실행 |
| G3 | 희소 선형 모델 공식 5-fold | 미발급 | 미발급 | - | PLANNED | 낮은 상관의 보완 후보 확인 | G0 병합 대기 |
| G4 | OOF 다양성·확률 품질 감사 | 미발급 | explore | - | PLANNED | 오류·확률 상관과 클래스 보완성 | 후보 확정 |
| G5 | 고정 가중 확률 blend | 미발급 | 미발급 | - | PLANNED | 사전 고정 가중치로 개선 | G4 통과 대기 |
| G6 | cross-fitted stacking | 미발급 | 미발급 | - | PLANNED | blend보다 추가 개선 시에만 채택 | G5 결과 대기 |
| G7 | 최종 후보 재현·제출 준비 | 미발급 | 해당 없음 | - | PLANNED | 독립 팀원 TRAINING_VERIFIED | 후보 동결 대기 |

상태는 `PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED`를 사용하고,
중단하면 `BLOCKED` 또는 `REJECTED`로 기록합니다.

## G0 — 공통 계약

모든 모델은 동일한 EXP-094 feature matrix와 canonical fold를 사용합니다.
모델별 runner가 다음을 실행 전에 검증해야 합니다.

- Feature Spec SHA-256, 피처 수와 피처 순서 해시
- train/test ID 순서와 fold 파일 SHA-256
- 고정 26개 클래스 순서
- OOF `(6201, 26)`, test `(2546, 26)` 확률 형상
- 확률의 유한값·범위·행 합
- resolved config, environment, checkpoint, OOF, test 확률과 metrics manifest

모델 기본값과 seed까지 병합한 resolved config를 자동 저장합니다. 사람이 Issue나
History에 하이퍼파라미터를 다시 옮겨 적지 않습니다. 피처 생성은 한 번 캐시하고
모델 runner는 캐시를 읽기만 하여 모델별 입력 차이를 막습니다.

## G1–G3 — 단일 모델 생산

LightGBM, CatBoost, 희소 선형 모델은 각각 별도 Experiment Issue와 EXP-ID로
실행합니다. 한 모델의 결과를 보고 다른 모델의 피처나 fold를 바꾸지 않습니다.

각 모델 보고서에는 다음을 기록합니다.

- 전체·fold별 Macro F1, fold 표준편차, accuracy, log loss
- 클래스별 F1과 confusion matrix
- 학습 시간, peak memory, checkpoint 크기와 추론 시간
- EXP-094와 OOF 라벨 일치율, 오류 상관, 확률 상관
- checkpoint 기반 `INFERENCE_VERIFIED`

단일 모델은 EXP-094보다 낮다는 이유만으로 즉시 폐기하지 않습니다. 다만 OOF
Macro F1이 `0.3968865739`보다 낮아 기준 대비 `-0.020`을 넘으면 앙상블 후보에서
제외합니다. 예외는 G4에서 특정 클래스의 반복 오류를 명확히 보완하고 고정 blend가
개선되는 경우뿐입니다.

클래스 가중치는 모델별 기본 비교에서 EXP-094와 같은 정책을 우선 사용합니다.
새 가중치, oversampling이나 threshold는 별도 Experiment Issue로 분리하고 outer
validation 성능을 보며 선택하지 않습니다.

## G4 — 다양성·확률 품질 감사

모든 OOF를 동일 ID·fold·클래스 순서로 정렬한 뒤 다음을 계산합니다.

- 전체 및 fold별 오류 일치율
- 클래스별 오류 상관과 클래스별 F1 차이
- 26차원 확률의 Pearson·Spearman 상관
- log loss, confidence, entropy와 calibration curve
- 저빈도 클래스별 support와 fold 간 변동

Stacking 후보가 되려면 다음을 모두 만족해야 합니다.

1. EXP-094와 OOF 오류 상관이 `0.95` 미만인 모델이 하나 이상 존재
2. 품질 하한을 통과한 모델이 둘 이상 존재
3. 개선이 한 fold 또는 한 클래스에만 의존하지 않음
4. train/test shift는 QC로만 보고 가중치·threshold 선택에 사용하지 않음

조건을 만족하지 않으면 stacking을 중단하고 EXP-094 단일 모델 또는 사전 고정
blend만 유지합니다.

## G5 — 고정 가중 확률 blend

먼저 해석 가능한 단순 평균을 평가합니다. 첫 비교는 최고 단일 모델과 가장 상관이
낮은 품질 통과 모델의 `0.5/0.5` 평균으로 고정합니다. OOF나 Public LB를 본 뒤
가중치를 미세 조정하지 않습니다. 다른 가중치는 별도 Experiment Issue와 사전
명시된 후보 집합이 필요합니다.

채택 조건은 최고 단일 모델 대비 다음을 모두 만족하는 것입니다.

- OOF Macro F1 `+0.001` 이상
- fold 표준편차 악화 `0.002` 미만
- log loss의 명백한 악화 없음
- 저빈도 클래스 다수의 동시 붕괴 없음
- `INFERENCE_VERIFIED` 통과

## G6 — cross-fitted stacking

단순 blend가 충분하지 않고 G4의 다양성 gate를 통과했을 때만 수행합니다.

- meta learner의 각 OOF 행은 해당 행을 보지 않은 base-model 예측만 사용
- meta learner 학습·검증도 canonical outer fold 안에서 cross-fitting
- 클래스별 가중치는 shrinkage를 적용하고 자유 파라미터 수를 제한
- Public LB와 test label surrogate를 선택 기준으로 사용하지 않음
- blend 대비 OOF Macro F1 `+0.002` 이상일 때만 stacking 채택
- fold 표준편차, log loss와 저빈도 클래스 F1이 동시에 붕괴하면 기각

개선 기준을 통과하지 못하면 복잡한 meta learner를 더 탐색하지 않고 G5 blend
또는 최고 단일 모델로 돌아갑니다.

## G7 — 최종 검증과 제출 예산

- 최종 후보는 최대 2개로 제한합니다.
- 리더보드 제출 전 checkpoint, OOF, test 확률, submission, resolved config와
  manifest를 GitHub Release 규칙에 맞게 보관합니다.
- 실험 작성자가 아닌 팀원이 fresh clone과 `uv sync --frozen`에서 재학습하여
  `TRAINING_VERIFIED`를 통과해야 최종 수상 후보로 지정합니다.
- 리더보드 제출은 모델 선택의 확인 수단이며 가중치나 피처 역튜닝에 사용하지
  않습니다.
- 일일 제출 횟수는 탐색에 소진하지 않고 검증 완료 후보에만 사용합니다.

## 계산 예산과 중단 조건

- G0 경량 fixture·단위 테스트가 통과하기 전 전체 5-fold 실행 금지
- 각 모델은 smoke 1-fold로 형상·메모리·산출물 경로를 먼저 확인
- smoke 결과는 공식 점수로 History에 기록하지 않음
- OOM 발생 시 데이터나 fold를 임의 축소하지 않고 sparse 형식, dtype, thread와
  cache 방식을 수정한 뒤 같은 config를 재실행
- 같은 모델 family의 무제한 하이퍼파라미터 탐색 금지
- 모델 다양성 gate 실패 시 stacking 중단
- 최종 후보가 정해지면 Feature Spec v1과 모델 목록을 동결

## Vera 권고 반영 상태

기존 Vera 검토와 Codex 판단이 공통으로 강조한 OOF 우선, 누수 방지, 고정 산출물
계약, Public LB 역튜닝 금지와 종료 조건을 위 단계에 반영했습니다. EXP-094의 새
결과를 Vera에 다시 전달해 받은 추가 권고는 출처와 함께 이 절에 추가하며, 실제로
받지 못한 답변을 추정해 기록하지 않습니다.

## 결정 변경 이력

| 일자 | 변경 | 근거 |
|---|---|---|
| 2026-08-01 | EXP-094를 Feature Spec v1과 XGBoost 기준으로 동결 | OOF 0.4168865739, 부모 대비 개선, INFERENCE_VERIFIED |
| 2026-08-01 | 단일 모델 → 다양성 감사 → 고정 blend → stacking 순서 확정 | 복잡한 앙상블 전에 독립 확률 품질과 보완성을 검증하기 위함 |

## 연결 문서

- [EXP-094 보고서](../exp094_feature_spec_v1/README.md)
- [Residue-position·Hotspot 로드맵](residue_position_hotspot_roadmap.md)
- [Feature Factory 운영 계약](../../docs/FEATURE_FACTORY.md)
- [Vera 검토 대화](https://www.verahealth.ai/search/22adc84e-7e57-4766-945f-a21fa795db24)
