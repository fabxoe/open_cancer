# ABC 신호 포트폴리오·스태킹 로드맵

> 영문명 **ABC Signal Portfolio & Stacking Roadmap**, 약칭 **ABC-Stack
> Roadmap**. 이 문서는 Issue #98에서 중반 A/B/C 파생변수 탐색부터 후반 모델
> 다양화, 앙상블과 최종 재현 검증까지 관리하는 단일 실행 계획입니다. 실제 점수는
> `EXPERIMENT_HISTORY.md`와 각 실험의 `metrics.json`만을 원본으로 사용하며
> 예상 점수나 가상 결과를 기록하지 않습니다.

## 현재 기준

- 관리 Task: [Issue #98](https://github.com/fabxoe/open_cancer/issues/98)
- 관리 PR: [PR #99](https://github.com/fabxoe/open_cancer/pull/99) (`MERGED`)
- 기준 Feature Spec: EXP-094, SHA-256
  `1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`
- 기준 XGBoost OOF Macro F1: `0.4168865739`
- 기준 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출
- 고정 평가: canonical 5-fold, 고정 26개 클래스 순서, Macro F1
- 파생변수 탐색 동결: 2026-08-03 저녁
- 모델·가중치 동결: 2026-08-06 저녁
- 2026-08-07: 재현·Release·최종 제출 복구 버퍼
- 다음 행동: G4 OOF 다양성·확률 품질 감사 결과를 반영하고 G5 고정 blend를
  별도 Issue로 진행

## 이름과 목표

- **A:** 사건·위치·hotspot 신호
- **B:** 변이 스펙트럼·과정 proxy
- **C:** 기능·pathway 그룹 신호
- **Signal Portfolio:** 단일 점수로 조기에 폐기하지 않고 모든 공식 OOF·test
  확률을 후반 앙상블 자산으로 보존
- **Stacking:** 서로 다른 신호와 모델의 장점을 누수 없는 cross-fitting으로 결합

EXP-094는 Feature Spec v1으로 보존합니다. 이후 family는 v2 후보로만 추가하며,
과거 EXP-033·069가 아니라 EXP-094에 정확히 한 family만 추가한 canonical
5-fold ablation으로 비교합니다. 8월 3일 저녁 이후 신규 family 탐색을 멈추고
모델 다양화로 전환합니다.

## 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | 판단 기준 | 다음 행동 |
|---|---|---:|---|---:|---|---|---|
| P0 | ABC-Stack 계획 동결 | #98 | 해당 없음 | #99 | MERGED | 공식 이름·경로·일정 확정 | 완료 |
| G0 | 공통 Feature Factory·모델 산출물 계약 | #100 | 해당 없음 | #101 | MERGED | 기존 EXP-094 불변·공통 assert | 완료 |
| A | exact-token·amino-acid family | #102 | #106·#107 | #105 | COMPLETED | 두 공식 OOF·test 확률 보존 | 포트폴리오 감사에서 비교 |
| B | morphology·frequency-tier spectrum | #103 | #109·#110 | #108 | COMPLETED | 두 공식 OOF·test 확률 보존 | 포트폴리오 감사에서 비교 |
| C | pathway·functional-role burden | #104 | #96(C-1) | #111 | COMPLETED | EXP-096 PERFORMANCE·OOF/test 보존 | v2-performance 후보로 감사 |
| F | v2-performance·v2-diversity 동결 | #119 | 해당 없음 | - | COMPLETED | canonical OOF·test 계약 감사 | 모델 다양화 Issue 발급 |
| M0 | 동결 Feature Spec·공통 모델 runner | #121 | 해당 없음 | #122 | COMPLETED | 세 spec 실물 해시·공통 artifact 계약 | 완료 |
| G1 | 희소 선형 모델 공식 5-fold | #123 | EXP-123 | #124 | COMPLETED | 다양성 통과·품질 gate 실패 | stacking 후보 미채택 |
| G2 | LightGBM 공식 5-fold | #125 | EXP-125 | #126 | COMPLETED | 신규 Local 최고·모든 gate 통과 | G3와 독립 비교 후 G4 감사 |
| G3 | CatBoost 공식 5-fold | #127 | EXP-127 | - | PAUSED_RUNPOD | 로컬 CPU fold당 약 19분·1/5 후 중단 | RunPod GPU 설정 검증 후 전체 재실행 |
| G3-1 | CatBoost v1 extended training | #131 | EXP-131 | #132 | COMPLETED | OOF 0.4222392962로 개선했지만 fold·Log Loss 악화, 추가 iteration 확장 중단 | G4 감사 완료 |
| G4 | OOF 다양성·확률 품질 감사 | #133 | explore | #134 | COMPLETED | EXP-125만 품질·다양성 gate 통과, EXP-127·131은 Log Loss gate 실패 | EXP-135 결과 반영 |
| G5 | 고정 가중 확률 blend | #135 | EXP-135 | #136 | COMPLETED | Log Loss는 개선했지만 EXP-131 대비 Macro F1·fold gate 실패 | G6 결과 반영 |
| G6 | cross-fitted stacking | #137 | EXP-137 | #138 | COMPLETED | 소수 클래스 F1 붕괴·최고 단일 대비 -0.0153766511로 기각 | G7 최종 후보 검증 |
| G7 | 최종 후보 재현·제출 준비 | #139 | 해당 없음 | 미발급 | IN_PROGRESS | EXP-131·125를 후보로 유지, 아직 TRAINING_VERIFIED·Release asset 미완료 | 독립 팀원 재학습·asset 보관 |

상태는 `PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED`를 사용하고,
중단하면 `BLOCKED` 또는 `REJECTED`로 기록합니다.

### M0 — 동결 Feature Spec·공통 모델 runner

모델 다양화 전에 `v1`, `v2-performance`, `v2-diversity`를 같은 코드로
materialize하고, Logistic Regression·XGBoost·LightGBM·CatBoost가 같은 5-fold와
확률 산출물 계약을 사용하도록 고정합니다. Issue #121은 일반 Task이므로 공식
OOF 점수나 EXP-ID를 만들지 않습니다. 실제 모델 비교는 M0가 병합된 뒤 모델별
Experiment Issue에서 수행합니다.

## A/B/C 구현·실험 포트폴리오

공통 구현은 일반 Task Issue, 실제 canonical 5-fold는 별도 Experiment Issue로
분리합니다. smoke는 실행과 메모리 확인에만 사용하고 성능 탈락 근거로 쓰지
않습니다.

### A — 사건·위치·hotspot

`A-1 recurrent exact-token`은 `(gene, raw token)`을 fold-train에서만 집계하며
최소 support 5, 최대 512개, 동률은 `(gene, token)` 사전순으로 고정합니다.
validation/test의 미등록 token은 OOV로 처리합니다.

`A-2 amino-acid change`는 단순 missense를 보존적/비보존적, charge·polarity
변화와 stop gain으로 고정 분류합니다. 표준 아미노산 물성표의 출처·버전·해시를
기록하고 기존 missense·nonsense와 같은 열은 추가하지 않습니다.

### B — 변이 스펙트럼·과정 proxy

Vera의 원 제안 중 전역 mutation-type count·fraction은 Factory와
EXP-029·033·043·045·050에서 이미 검증했으므로 반복하지 않습니다. 상위 50개
유전자×type도 EXP-005와 중복되고 fold별 의미가 달라져 제외합니다. 실제 COSMIC
signature로 오해하지 않도록 `protein-level functional mutation spectrum proxy`로
명명합니다.

`B-1 complex morphology`는 기존 `complex`를 `multi_position_complex`,
`inframe_or_delins`, `other_complex`로 고정 분리하고 신규 subtype count·fraction,
truncating fraction과 안정화된 nonsynonymous/synonymous ratio만 추가합니다.
semantic-equivalence 검사를 거쳐 약 8~12차원으로 제한합니다.

`B-2 frequency-tier spectrum`은 outer fold-train 유전자 변이 빈도의 quartile
4개 tier×5 mutation type count·fraction을 만듭니다. 출력 열은 고정하고 유전자
tier 소속만 fold별 fit하며 최대 40차원입니다.

### C — 기능·pathway 그룹

`C-1 mutation-only fixed pathway burden`은 TCGA PanCancer Atlas의 Cell cycle,
Hippo, MYC, Notch, NRF2, PI3K/AKT, RTK-RAS, TGFβ, TP53, WNT/β-catenin 10개
고정 pathway에서 `mutated_gene_count`, `lof_gene_count`만 계산해 총 20차원으로
제한합니다. boolean, token count와 weight는 제외합니다.

`C-2 functional-role burden`은 oncogene, tumor suppressor, DNA repair 등 소수
고정 그룹의 mutated-gene·LOF-gene count를 계산합니다. EXP-021과 동일성·상관을
먼저 검사하며 PPI, embedding과 외부 연속 weight는 사용하지 않습니다.

### 도메인 지식과 누수 체크리스트

- 대회 데이터의 관측 빈도로 찾는 hotspot·vocabulary는 fold-train에서만 fit
- 실행 전에 문헌으로 고정한 hotspot은 동일 목록을 사용하되 OOF·test·Public
  LB를 보고 추가·삭제 금지
- 외부 지식은 그룹·관계·계산 규칙만 정의하고 환자별 값은 제공 CSV에서 계산
- 고정 목록도 출처, Supplementary Table, 버전, 다운로드 일자, 라이선스,
  원본·정제 SHA-256과 4,384개 유전자 교집합 기록
- 22만 개 전체 exact-token one-hot 금지; vocabulary 상한·support·bin은 실행
  전에 config로 고정

### 외부 지식 경계

외부 TCGA/ICGC 환자 행, 외부 환자별 multi-omics·signature exposure·예측값,
외부 분류기와 환자 embedding은 사용하지 않습니다. pretrained gene/PPI embedding,
TCGA 학습 중요도, COSMIC 연속 weight와 외부 driver 확률은 주최측의 명시적 허용
전까지 보류합니다. 문헌 기반 hotspot·driver·pathway membership과 일반 분류
규칙도 자동 허용으로 간주하지 않고 provenance와 규정 근거를 남깁니다.

문헌은 왜 피처를 시험하는지 설명할 뿐 이 대회에서의 효과, 최적 weight 또는 규정
허용을 증명하지 않습니다. 채택은 canonical OOF로 결정합니다.

## 8월 3일 탐색 동결과 보존 등급

- `PERFORMANCE`: EXP-094 대비 OOF `+0.001` 이상, fold 표준편차 악화
  `0.002` 미만, log loss·저빈도 클래스 다수 붕괴 없음
- `DIVERSITY`: EXP-094 대비 OOF `-0.010` 이내이며 라벨 불일치 10% 이상,
  낮은 오류 상관, 저빈도 클래스 F1 `+0.015` 이상 또는 반복 오류 다수 보완
- `ARCHIVE`: 두 gate를 통과하지 못해도 실제 OOF·test 확률과 보고서·manifest 보존

8월 3일 저녁 EXP-094 v1, PERFORMANCE family의 사전 정의 union인
v2-performance, 가장 낮은 오류 상관 또는 가장 강한 저빈도 클래스 보완 family
하나인 v2-diversity를 고정합니다. 동일 family의 세부 파라미터 반복 탐색은 하지
않고 공식 조합은 두 v2 사양으로 제한합니다.

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

| 모델 | v1 | v2-performance | v2-diversity |
|---|---|---|---|
| XGBoost | 기존 EXP-094 | 실행 | 실행 |
| 희소 Logistic Regression | 실행 | 실행 | 생략 |
| LightGBM | 실행 | 실행 | 실행 |
| CatBoost | 실행 | PERFORMANCE·DIVERSITY 중 유망한 하나 | 생략 |

첫 설정은 Logistic Regression `saga`·L2·`C=1`·`max_iter=2000`, LightGBM
multiclass·1,000 trees·learning rate 0.05·31 leaves·feature/bagging 0.8·early
stopping 50, CatBoost MultiClass·1,000 iterations·depth 8·learning rate
0.05·L2 3·early stopping 50으로 고정합니다. XGBoost는 EXP-094 설정을
유지합니다. 모두 balanced class weight 정책을 우선합니다.

각 모델 보고서에는 다음을 기록합니다.

- 전체·fold별 Macro F1, fold 표준편차, accuracy, log loss
- 클래스별 F1과 confusion matrix
- 학습 시간, peak memory, checkpoint 크기와 추론 시간
- EXP-094와 OOF 라벨 일치율, 오류 상관, 확률 상관
- checkpoint 기반 `INFERENCE_VERIFIED`

단일 모델은 EXP-094보다 낮다는 이유만으로 즉시 폐기하지 않습니다. 기본 앙상블
품질 하한은 `-0.004`지만 최대 한 개 wildcard는 `-0.010`까지 허용합니다.
wildcard는 라벨 불일치 12% 이상 또는 명확한 저빈도 클래스 개선을 증명해야
합니다. 최선 단일 모델 대비 log loss가 `0.01` 이상 악화된 모델은 확률
앙상블 후보에서 제외합니다.

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

1. EXP-094와 OOF 오류 상관이 `0.92` 이하이거나 예측 라벨 불일치율이 `10%`
   이상인 모델이 하나 이상 존재
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

세 모델 평균은 사전 고정 `1/3`씩 한 번만 비교합니다.

채택 조건은 최고 단일 모델 대비 다음을 모두 만족하는 것입니다.

- OOF Macro F1 `+0.001` 이상
- fold 표준편차 악화 `0.002` 미만
- log loss의 명백한 악화 없음
- 저빈도 클래스 다수의 동시 붕괴 없음
- `INFERENCE_VERIFIED` 통과

## G6 — cross-fitted stacking

단순 blend가 충분하지 않고 G4의 다양성 gate를 통과했을 때만 수행합니다.

- meta learner의 각 OOF 행은 해당 행을 보지 않은 base-model 예측만 사용
- meta learner 자체의 OOF 평가도 canonical fold로 다시 cross-fitting한다. 전체
  base OOF를 한 번에 학습한 meta learner의 in-sample 점수는 채택 근거로 쓰지 않는다.
- 클래스별 가중치는 shrinkage를 적용하고 자유 파라미터 수를 제한
- Public LB와 test label surrogate를 선택 기준으로 사용하지 않음
- 새 base 모델 하나를 추가했을 때 cross-fitted stack 개선이 `+0.001` 미만이고
  저빈도 클래스 하위 quartile 평균 F1도 개선되지 않으면 해당 모델 추가를 중단
- 최종 stack은 최고 단일 모델 또는 고정 blend 대비 OOF Macro F1 `+0.002`
  이상일 때만 채택
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
- 각 모델은 5% subsample·1-fold smoke로 캐시 로드부터 checkpoint 재추론,
  OOF·submission 저장까지 end-to-end로 먼저 확인
- smoke 결과는 공식 점수로 History에 기록하지 않음
- OOM 발생 시 데이터나 fold를 임의 축소하지 않고 sparse 형식, dtype, thread와
  cache 방식을 수정한 뒤 같은 config를 재실행
- 같은 모델 family의 무제한 하이퍼파라미터 탐색 금지
- 모델 다양성 gate 실패 시 stacking 중단
- 최종 후보가 정해지면 Feature Spec v1과 모델 목록을 동결

## Feature Spec v2 운영 원칙

A/B/C family는 8월 3일까지 각각 독립 Experiment Issue에서 단 한 번씩 공식
ablation합니다. 결과를 보고 Feature Spec v1을 수정하지 않으며 PERFORMANCE와
DIVERSITY 후보를 v2로 별도 동결합니다. PPI·외부 embedding·고자유도 signature
extraction은 이 중반 로드맵에서 제외합니다.

과거 A/B/C 적용 현황과 분류 근거는
[Vera EXP-094 후속 검토의 저장소 검증 매핑](../analysis/vera_exp094_followup.md#저장소-검증-기준-abc-매핑)을
따릅니다. 핵심은 A가 EXP-094에서 동결됐고, B는 광범위한 확장이 대체로 실패한
뒤 일부 log burden만 남았으며, C는 EXP-012·021에서 초기 분석·실험은 했지만
pathway·hallmark·PPI는 아직 미착수라는 점입니다.

## Vera 권고 반영 상태

기존 Vera 검토와 Codex 판단이 공통으로 강조한 OOF 우선, 누수 방지, 고정 산출물
계약, Public LB 역튜닝 금지와 종료 조건을 위 단계에 반영했습니다. EXP-094 결과를
전달한 2026-08-01 후속 검토에서 Vera는 다음을 추가 권고했습니다.

- 희소 선형 모델 → LightGBM → 필요 시 CatBoost 순서
- 기준 대비 `-0.004` 품질 하한
- 오류 상관 `0.92` 이하 또는 라벨 불일치 `10%` 이상의 다양성 gate
- 최선 단일 모델보다 log loss `+0.01` 이상 악화된 확률 모델 제외
- calibration은 최종 후보에서만 검토
- B-1/C-1은 기존 중복을 제거한 저차원 v2 단일 ablation으로 제한

Vera는 base OOF 전체로 meta learner를 학습하는 표준 test 생성 절차를 설명했지만,
그 방식의 학습 점수는 meta-level in-sample입니다. 저장소는 더 엄격하게 meta
learner 자체도 canonical fold로 cross-fitting하여 stack OOF를 평가합니다.

상세 비교는 [Vera EXP-094 후속 검토](../analysis/vera_exp094_followup.md)를
따릅니다.

## 결정 변경 이력

| 일자 | 변경 | 근거 |
|---|---|---|
| 2026-08-01 | EXP-094를 Feature Spec v1과 XGBoost 기준으로 동결 | OOF 0.4168865739, 부모 대비 개선, INFERENCE_VERIFIED |
| 2026-08-01 | 단일 모델 → 다양성 감사 → 고정 blend → stacking 순서 확정 | 복잡한 앙상블 전에 독립 확률 품질과 보완성을 검증하기 위함 |
| 2026-08-01 | Vera EXP-094 후속 검토로 모델 품질·다양성 gate 강화 | 품질 하한 -0.004, 오류 상관 0.92 또는 라벨 불일치 10%, log loss 악화 0.01 적용 |
| 2026-08-01 | ABC-Stack으로 확장하고 8월 3일까지 세 family 작업선을 병렬화 | 단일 점수로 조기 포기하지 않고 후반 앙상블 신호 포트폴리오 확보 |
| 2026-08-01 | B-1 morphology·C-1 mutation-only pathway로 수정 | 기존 피처 중복, multi-omics·외부 weight와 과도한 자유도 방지 |
| 2026-08-01 | PERFORMANCE·DIVERSITY·ARCHIVE 등급 도입 | 단독 점수가 낮아도 보완 OOF 자산을 보존 |

## 연결 문서

- [EXP-094 보고서](../exp094_feature_spec_v1/README.md)
- [Residue-position·Hotspot 로드맵](residue_position_hotspot_roadmap.md)
- [Feature Factory 운영 계약](../../docs/FEATURE_FACTORY.md)
- [Vera 검토 대화](https://www.verahealth.ai/search/22adc84e-7e57-4766-945f-a21fa795db24)
