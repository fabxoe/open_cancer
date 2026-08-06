# Parser-v4 fold-safe Hotspot-12 로드맵

> GitHub 상위 Task: [#632](https://github.com/fabxoe/open_cancer/issues/632)
>
> 실제 점수의 원본은 `EXPERIMENT_HISTORY.md`와 실험별 `metrics.json`입니다. 이 문서에는 예상 점수나 가상 결과를 기록하지 않습니다.

## 목적

Parser v4가 확정한 missense residue 사건에서 유전자별로 좁은 12-residue 구간에 반복 변이가 모이는지를 outer-train에서만 학습하고, 이를 안정된 저차원 피처로 모델에 전달합니다.

EXP-563은 50-aa bin의 평균 HHI·normalized entropy 등 연속형 집중도 4개를 추가했으나 EXP-527 대비 OOF Macro F1이 `-0.0070336516` 낮아 기각됐습니다. Hotspot-12는 평균 집중도가 아니라 **사전 고정된 좁은 창 규칙을 통과한 반복 사건의 존재**를 표현하므로 별도로 검증합니다.

## 진행 상태

| 단계 | 작업 | Issue | EXP | PR | 상태 | 결과 | 다음 행동 |
|---|---|---:|---|---:|---|---|---|
| A | Parser-v4 support audit | #632 | 해당 없음 | - | COMPLETED | fold당 223~241 genes, 평균 Jaccard 0.3237 | [감사 보고서](../analysis/parser_v4_hotspot12_support_audit/README.md) |
| B | Fold-safe Hotspot-12 transformer | #632 | 해당 없음 | #638 | COMPLETED | 652 tests passed | 구현 완료 |
| C | 공용 구현 병합 | #632 | 해당 없음 | #638 | MERGED | CI 통과 | 공식 실험 진행 |
| D | EXP-527 + Hotspot-12 공식 5-fold | #639 | EXP-639 | - | IN_PROGRESS | N/A | canonical 5-fold 실행 |
| E | 채택·기각 및 후속 family 결정 | 미발급 | 미발급 | - | PLANNED | N/A | D의 실제 결과로 판단 |

작업 상태는 `PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED`를 사용하며, 중단 시 `BLOCKED` 또는 `REJECTED`로 기록합니다. 이는 실험 재현 상태와 구분합니다.

## A. Support audit

### 입력

- parser v4 canonical event
- 1차 대상은 `route=substitution`, `event_type=missense`
- positive residue index만 사용
- unresolved·not-applicable·position-ineligible 사건 제외 및 사유 기록
- isoform multiplicity 방지를 위해 `patient × gene × residue_position` 단위로 중복 제거
- label·validation·test·Public LB를 창 선택에 사용하지 않음

### 사전 고정 규칙

각 outer-train partition에서 유전자별로 다음을 계산합니다.

1. 고유 patient-position 사건이 5개 이상인 유전자만 후보로 둡니다.
2. 폭 12의 inclusive 창 `[start, start + 11]`을 이동합니다.
3. 한 창에 전체 eligible 사건의 40% 이상이 모이면 통과합니다.
4. 유전자당 대표 창 하나만 저장합니다.
5. 동률은 `창 사건 수 내림차순 → 비율 내림차순 → start 오름차순 → gene 오름차순`으로 결정합니다.

fold별 후보·통과 유전자, 창 경계, 전체/창 사건 수, 비율, 제외 사유, fold 간 Jaccard 및 경계 안정성을 저장합니다.

### 중단 조건

support가 사실상 없거나 fold별 창이 전혀 안정되지 않으면 공식 실험으로 넘어가지 않습니다. 임계값을 사후에 낮춰 결과를 만드는 탐색은 하지 않습니다.

## B. Fold-safe transformer

- `fit`: outer-train에서만 대표 창 확정
- `transform`: validation/test에는 저장된 창만 적용
- checkpoint 재추론에서 fold별 manifest를 다시 읽어 같은 피처를 생성
- 원 mutation presence와 부모 피처는 유지

출력:

- 안정된 유전자 registry의 `gene__hotspot12_hit`
- `sample__hotspot12_gene_count`
- `sample__hotspot12_event_count`
- `sample__hotspot12_fraction`

선택되지 않은 유전자는 해당 registry 위치에 0을 출력해 fold별 피처 이름·순서·차원을 동일하게 유지합니다.

## C. 공식 실험

공용 구현이 병합되고 support audit가 통과한 뒤 별도 Experiment Issue에서 실행합니다.

- 부모: EXP-527
- canonical stratified 5-fold, seed 42
- 부모와 동일한 모델·seed·weight·checkpoint 정책
- 유일한 변경: Hotspot-12 family 추가

채택 조건:

- OOF Macro F1 `+0.001` 이상
- fold 표준편차 악화 `<0.002`
- Log Loss 명백한 악화 없음
- 클래스 F1 최대 하락이 `-0.05`보다 크지 않음
- `INFERENCE_VERIFIED`

## 후속 분리 실험

다음은 Hotspot-12와 한 번에 섞지 않습니다.

1. entropy/Gini 임계치 이하 유전자 개수
2. Concentration 70/40 규칙
3. Green's contagion/dispersion
4. 채택된 저차원 family 조합

## 갱신 규칙

Issue 생성, 구현 시작, PR 생성, merge, 공식 실험 완료, 재현 검증, 채택·기각 시 이 표를 같은 PR에서 갱신합니다.
