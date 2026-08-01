# Residue-position·Hotspot 개발 로드맵

> 이 문서는 후속 작업의 순서와 중단 조건을 관리하는 계획 문서입니다.
> 실제 실행 결과와 점수의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)와 각 실험의
> `metrics.json`입니다. 아직 실행하지 않은 단계에 예상 점수나 가상 결과를
> 기록하지 않습니다.

## 현재 상태

- 로드맵 관리 Task: [Issue #73](https://github.com/fabxoe/open_cancer/issues/73)
- 로드맵 관리 PR: [PR #74](https://github.com/fabxoe/open_cancer/pull/74) (`MERGED`)
- 위치 의미 감사: [Issue #80](https://github.com/fabxoe/open_cancer/issues/80) /
  [PR #82](https://github.com/fabxoe/open_cancer/pull/82) (`MERGED`)
- 위치 negative control: [Issue #91](https://github.com/fabxoe/open_cancer/issues/91)
- 기준일: 2026-08-01
- 실제 완료 실험 수: 23
- 기준 실험:
  - [EXP-067 coarse-bin](../exp067_xgb_residue_coarse_bin/README.md)
  - [EXP-069 max residue-position](../exp069_xgb_max_residue_position/README.md)
  - [EXP-031 hotspot extended](../exp031_hotspot_extended/README.md)
- 확정된 다음 작업: 단계 E 위치 negative control 구현·실행 및 결과에 따른
  Feature Spec v1 위치 피처 포함 여부 결정

## 진행 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | OOF Macro F1 | 재현 상태 | 판단 | 다음 행동 |
|---|---|---:|---|---:|---|---:|---|---|---|
| A | EXP-067+069 고정 blend | [#75](https://github.com/fabxoe/open_cancer/issues/75) | EXP-075 | [#77](https://github.com/fabxoe/open_cancer/pull/77) | COMPLETED | 0.4157910775 | INFERENCE_VERIFIED | 두 부모 대비 개선으로 채택 | 단계 B 진행 |
| B | max+indicator | [#78](https://github.com/fabxoe/open_cancer/issues/78) | EXP-078 | [#79](https://github.com/fabxoe/open_cancer/pull/79) | REJECTED | 0.4110815504 | INFERENCE_VERIFIED | 채택 기준 실패·indicator 완전 중복으로 기각, EXP-069 max+zero 동결 | Issue #80 의미 감사 |
| C | hotspot runner 정리 | [#83](https://github.com/fabxoe/open_cancer/issues/83) | 해당 없음 | [#84](https://github.com/fabxoe/open_cancer/pull/84) | COMPLETED | N/A | 해당 없음 | config 기반 runner·fold-train 근거 검증·재현 산출물 자동화 완료 | 단계 D 진행 |
| D | hotspot clean 실험 | [#85](https://github.com/fabxoe/open_cancer/issues/85) | EXP-085 | [#86](https://github.com/fabxoe/open_cancer/pull/86) | COMPLETED | 0.4125795545 | INFERENCE_VERIFIED | EXP-005 대비 +0.008200으로 복구 성공·채택 | 단계 E 진행 |
| E | 위치 negative control | [#91](https://github.com/fabxoe/open_cancer/issues/91) | explore | [#92](https://github.com/fabxoe/open_cancer/pull/92) | PR_OPEN | 0.4058699664 (3-seed 평균) | 해당 없음 | EXP-069 원본 대비 -0.007231, 숫자 위치 신호 지지 | PR #92 검토·병합 |
| F | Feature Spec v1 조합 | [#93](https://github.com/fabxoe/open_cancer/issues/93) | EXP-093 | 생성 예정 | COMPLETED | 0.4157606623 | INFERENCE_VERIFIED | 부모 OOF는 개선했지만 fold 변동성 기준 실패로 조합 동결 보류 | pathway family를 별도 Issue로 검증 |
| G | 모델 다양화·stacking | 미발급 | 미발급 | - | PLANNED | N/A | NOT_STARTED | - | Feature Spec v1 동결 대기 |

로드맵 작업 상태는 다음 값만 사용합니다.

```text
PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED
                                     ↘ BLOCKED
                                     ↘ REJECTED
```

이 값은 모델 실험의 상태(`PLANNED`, `RUNNING`, `COMPLETED`, `FAILED`,
`ABORTED`)나 재현 상태(`NOT_STARTED`, `INFERENCE_VERIFIED`,
`TRAINING_VERIFIED` 등)와 서로 다른 **로드맵 진행 상태**입니다.

## 권고 검토와 확정 결정

### Vera와 Codex가 일치한 부분

- EXP-067과 EXP-069의 OOF·test 확률을 고정 `0.5/0.5`로 평균하는 실험을
  우선합니다.
- Public LB를 보고 blend 가중치, 클래스별 가중치나 threshold를 역으로
  조정하지 않습니다.
- `max residue-position + observed indicator`를 위치 family의 마지막 조합
  실험으로 검증합니다.
- 재현성 검증에 실패한 EXP-031 산출물을 최종 후보로 사용하지 않고 clean
  환경에서 새 Experiment Issue로 다시 실행합니다.
- calibration, 클래스별 blending과 stacking은 후보 피처와 단일 모델이
  동결된 뒤로 미룹니다.

### 순서에 관한 차이와 최종 선택

Codex는 Public LB 상승 폭이 컸지만 재현 상태가 `FAILED`인 EXP-031의 clean
복구를 blend 직후 처리하는 순서를 선호했습니다. Vera는 위치 family를 먼저
닫기 위해 `blend → max+indicator → hotspot clean` 순서를 권고했습니다.

팀 선택은 Vera의 순서를 따릅니다. 대신 단계 B가 끝나면 bin 폭, min/max/span
조합 등 추가 위치 옵션 탐색을 중단하고 바로 hotspot clean 복구로 이동합니다.

## 단계 A — EXP-067 + EXP-069 고정 Blend

새 Experiment Issue 번호에서 EXP-ID를 자동 파생합니다. 새 모델을 학습하지
않고 다음 확률을 평균하는 inference-only 실험입니다.

```text
blended_probability = 0.5 × EXP-067 + 0.5 × EXP-069
prediction = argmax(blended_probability, fixed_class_order)
```

### 필수 구현과 검증

- EXP-067·069 OOF의 `ID`, 정답, fold와 확률 열 순서가 완전히 같아야 합니다.
- test 확률의 `ID`와 고정 26개 클래스 열 순서가 완전히 같아야 합니다.
- 가중치는 정확히 `0.5/0.5`이며 합이 1이어야 합니다.
- 확률은 유한값, `[0, 1]` 범위이고 각 행 합이 허용 오차 안에서 1이어야 합니다.
- OOF Macro F1, fold별 점수, 클래스별 F1, accuracy와 log loss를 계산합니다.
- resolved config에 부모 EXP, 입력 경로·SHA-256, 가중치, 클래스 순서와 출력
  경로를 저장합니다.
- OOF·test 확률, submission과 재현 문서를 생성합니다.
- 부모 checkpoint와 입력 확률·config를 포함하는 `exp-NNN-repro-v1` GitHub
  Release 번들을 준비합니다.
- 같은 입력에서 제출 CSV가 byte-level SHA-256까지 재생성돼야
  `INFERENCE_VERIFIED`로 승격합니다.
- `INFERENCE_VERIFIED`와 Release 보관이 끝난 뒤에만 사람이 DACON에
  수동 제출합니다.

가중치는 OOF나 Public LB 결과를 본 뒤 변경하지 않습니다. 다른 가중치는 별도
Experiment Issue가 필요하지만 이 로드맵에서는 진행하지 않습니다.

## 단계 B — `max + observed indicator`

[EXP-069](../exp069_xgb_max_residue_position/README.md)의 모델·split·seed를
유지하고 위치 설정만 다음과 같이 바꿉니다.

```yaml
position:
  aggregates: [max]
  missing_policy: indicator
  token_scope: include_complex
  transform: raw
```

다음을 모두 만족하면 Position Feature Spec v1로 채택합니다.

- EXP-069보다 OOF Macro F1이 최소 `+0.001`
- fold 표준편차 악화가 `0.002` 미만
- log loss와 소수 클래스 F1에 명백한 붕괴가 없음
- checkpoint 기반 inference 재현 검증 통과

통과하면 `max+indicator`, 실패하면 EXP-069의 `max+zero`를 Position Feature
Spec v1로 동결합니다. 이 판단 뒤에는 추가 위치 옵션 조합을 만들지 않습니다.

## 단계 C — Hotspot runner 일반화

단계 B 병합 후 Issue #80에서 실제 sparse artifact의 피처 의미를 감사한다.
현재 데이터에서는 `residue_position_observed`와 mutation-presence가 완전히 같아
indicator 실험은 결측 해소가 아닌 중복 피처 weighting으로 재해석한다. 실제
점수와 재현 상태는 바꾸지 않으며
[QC 보고서](../analysis/residue_position_semantics_qc.md)를 팀 공통 근거로 사용한다.

일반 Task Issue에서 다음 코드 정리를 수행하며 EXP-ID를 만들지 않습니다.

- EXP-031, Issue 번호와 산출물 경로 하드코딩 제거
- config 기반 실행과 자동 Issue/EXP-ID 해석 지원
- 고정 hotspot 34개와 참조 아미노산 조건 보존
- 추가 hotspot의 최소 관측 조건을 각 fold의 train 부분에서만 확인
- validation/test에서 목록이나 threshold를 선택하지 않음
- checkpoint, OOF, test 확률, metrics와 manifest 자동 생성

공식 실험 config에는 아래 계약을 명시하고, runner는 현재 Issue 브랜치에서
`EXP-NNN`과 모든 산출물 경로를 자동 파생합니다.

```yaml
hotspots:
  table: extended_34
  evidence_scope: additions_15
  minimum_matching_train_rows: 5
```

```bash
uv run python scripts/run_hotspot_xgb.py --config configs/expNNN_<slug>.yaml
```

최소 관측 수는 전체 train이 아니라 각 fold의 fold-train에서 검사합니다. 고정
목록에 없거나 최소 근거를 통과하지 못한 설정은 학습 전에 실패합니다.

## 단계 D — Hotspot clean 실험

단계 C가 main에 병합된 뒤 새 Experiment Issue와 clean commit에서 canonical
5-fold를 실행합니다. 기존 EXP-031의 결과나 `FAILED` 상태를 덮어쓰지 않습니다.

다음을 만족하면 hotspot family 복구 성공으로 판단합니다.

- EXP-005보다 OOF Macro F1이 최소 `+0.005`
- checkpoint inference 검증 통과
- fold나 소수 클래스 F1에 비정상 붕괴가 없음

원 EXP-031과 점수가 달라도 새 실행의 실제 결과를 그대로 기록합니다.

## 단계 E — 위치 Negative Control

공식 제출 후보가 아닌 `RUN_MODE="explore"` 분석으로 수행합니다.

- 유전자별 mutation-presence는 유지합니다.
- 각 outer fold의 train에서 변이가 있는 행 사이의 residue 위치값만 섞습니다.
- validation은 원본 위치를 유지하고 여러 고정 seed로 반복합니다.
- 가능하면 mutation type·token-count strata 안에서 섞어 위치 외 관계를 유지합니다.
- 정답 라벨과 test 데이터는 피처 생성이나 선택에 사용하지 않습니다.
- 원본 위치 모델과 같은 canonical folds로 OOF를 비교합니다.

### 해석 기준

- 실제 위치 피처보다 `0.002` 이상 하락: 위치값 자체의 정보가 있다는 근거
- 차이가 `0.001` 이하: missingness, scale 또는 분포 안정화 효과일 가능성이 큼
- 그 사이: 결론 보류

이 검증 전에는 residue-position 개선을 생물학적인 위치 효과로 단정하지 않습니다.

Issue #91의 3개 고정 seed × 5-fold 결과에서 permutation 평균 OOF Macro F1은
`0.4058699664`로 EXP-069 원본 `0.4131007993`보다 `0.0072308329` 낮았습니다.
15개 paired fold 중 13개에서 점수가 하락했고 모든 fold에서 sparse support 변경은
0건이었습니다. 사전 기준 `0.002`를 넘어 숫자 위치 신호를 지지하므로 EXP-069의
`max+zero`를 Position Feature Spec v1에 포함합니다. 상세 결과는
[negative-control 보고서](../analysis/position_negative_control.md)를 따릅니다.

## 단계 F — Feature Spec v1 조합

단계 D의 hotspot clean 실험이 통과했을 때만 새 Experiment Issue로 실행합니다.

```text
EXP-005 mutation-type features
+ 확정 Position Feature Spec v1
+ clean hotspot features
```

최고 부모 실험보다 OOF Macro F1이 `+0.001` 이상이고 fold 표준편차 악화가
`0.002` 미만일 때 조합을 채택합니다. 그렇지 않으면 두 family를 분리하고
확률 앙상블 후보로 유지합니다.

## 단계 G — 모델 다양화와 Stacking

Feature Spec v1 동결 후 동일 피처와 canonical folds로 XGBoost, LightGBM,
CatBoost와 선형 모델을 비교합니다. 각 모델은 `(6201, 26)` OOF와
`(2546, 26)` test 확률을 고정 클래스 순서로 저장합니다.

Stacking은 다음을 모두 만족할 때만 진행합니다.

- 기본선에 비해 지나치게 낮지 않은 개별 모델이 둘 이상 존재
- OOF 오류 상관이 `0.95` 미만인 조합 존재
- cross-fitted meta learner가 최고 단일 모델보다 `+0.002` 이상 개선
- 클래스별 가중치는 nested/cross-fitted 방식과 shrinkage 사용

최종 후보 1~2개는 실험 작성자가 아닌 다른 팀원이 fresh clone에서 재학습해
`TRAINING_VERIFIED`까지 검증합니다.

## 단계별 갱신 규칙

각 단계의 같은 PR에서 다음 시점마다 이 문서를 갱신합니다.

1. Issue 생성: Issue, EXP-ID와 브랜치 기록
2. 실행 시작: `IN_PROGRESS`
3. PR 생성: PR 번호와 `PR_OPEN`
4. merge: `MERGED`
5. 실험 완료: 실제 OOF와 실험 보고서 링크 기록
6. 리더보드 제출: History의 제출 이력과 연결
7. 재현 검증: 실제 재현 상태 기록
8. 채택·기각: 판단과 다음 단계 기록

상세한 피처 설명과 결과 분석은 `reports/expNNN_<slug>/README.md`에 쓰고,
로드맵에는 점수와 해당 보고서 링크만 기록합니다.

## 진행 원칙과 중단 조건

- 각 단계는 선행 PR이 main에 병합된 뒤 최신 main에서 시작합니다.
- 모든 단계는 먼저 GitHub Issue를 만들고 Issue 번호가 포함된 브랜치를 사용합니다.
- 공식 EXP-ID는 Experiment Issue 번호에서만 파생합니다.
- Public LB를 보고 파서, 피처 규칙, threshold나 blend 가중치를 조정하지 않습니다.
- 중단 조건을 만족한 family는 추가 탐색 없이 동결합니다.
- 실행하지 않은 실험, 측정하지 않은 점수와 존재하지 않는 산출물을 기록하지
  않습니다.
- 리더보드 제출 모델은 Release 보관과 `INFERENCE_VERIFIED`를 먼저 완료합니다.

## 결정 변경 이력

| 일자 | 변경 | 근거 |
|---|---|---|
| 2026-07-31 | `blend → max+indicator → hotspot clean` 순서 확정 | Vera 권고를 채택하되 단계 B 이후 위치 family를 동결해 탐색 확장을 제한 |
| 2026-07-31 | 첫 blend를 제출 준비 완료 상태까지 구성 | 리더보드 후보의 산출물·해시·Release 보관을 제출 전에 완료하기 위함 |
| 2026-07-31 | 장기 계획과 실제 결과 장부 분리 | 계획 변경이 History의 사실 기록과 섞이는 것을 방지 |
| 2026-07-31 | indicator를 결측 해소가 아닌 중복 피처 weighting으로 재해석 | 실제 sparse train/test에서 mutation-presence와 observed indicator 불일치가 0개였음 |
| 2026-07-31 | 위치 permutation을 fold-train·반복 seed 계약으로 강화 | 전체 OOF 단일 shuffle의 검증 분포 오염과 우연 변동을 방지 |
| 2026-08-01 | 단계 C·D와 위치 의미 감사를 완료 처리하고 단계 E Issue #91 착수 | PR #82·#84·#86·#90 병합과 EXP-085 결과 반영 |
| 2026-08-01 | 단계 E에서 숫자 residue-position 신호를 지지하고 EXP-069 max+zero 채택 | 3-seed permutation 평균이 원본보다 0.007231 낮고 15개 fold 중 13개 하락 |

## 참고

- Vera 검토 대화:
  <https://www.verahealth.ai/search/22adc84e-7e57-4766-945f-a21fa795db24>
- [Feature Factory 운영 계약](../../docs/FEATURE_FACTORY.md)
- [Residue-position과 co-mutation 안내](../../docs/RESIDUE_POSITION_AND_CO_MUTATION_GUIDE.md)
- [실험 보고서 작성법](../README.md)
