# 오리엔테이션 기반 상관 삭제·피처 선택 로드맵

> 이 로드맵은 고차원·소표본 변이 데이터에서 중복을 보수적으로 확인하고,
> 해석 가능한 선택 정책을 canonical 5-fold로 검증하기 위한 계획이다. 실제 점수의
> 원본은 항상 `EXPERIMENT_HISTORY.md`와 각 실험의 `metrics.json`이며, 이 문서에는
> 예상 점수나 실행하지 않은 결과를 기록하지 않는다.

## 기준과 원칙

- 기준 모델: EXP-094 Feature Spec v1 XGBoost
- 기준 평가: canonical `stratified_5fold_seed42.csv`, 전체 OOF Macro F1
- Public LB와 test는 selector, 임계값, 가중치 선택에 사용하지 않는다.
- 모든 selector는 각 outer fold의 **학습 행만**으로 fit하고, 같은 mask를 validation·test에 적용한다.
- 상관을 `GENE__mutated`에서 계산했다면 제거도 그 열 하나로 한정한다. 같은 유전자의 mutation-type, missing, residue-position, sample aggregate, hotspot은 보존한다.
- EXP-179 SMOTE 결과는 별도 ablation으로 끝까지 기록한다. 이 로드맵의 기준과 C1~C3·R1·R2의 기본 설정은 SMOTE 없이 balanced sample weight를 사용한다.

## 상태표

| 단계 | 작업 | Issue | EXP | PR | 상태 | OOF Macro F1 | 다음 행동 |
|---|---|---:|---:|---:|---|---:|---|
| T0 | fold-safe selector 공용 기반 | [#183](https://github.com/fabxoe/open_cancer/issues/183) | 해당 없음 | [#184](https://github.com/fabxoe/open_cancer/pull/184) | MERGED | N/A | C0 분석 기록 후 C1 Issue 발급 |
| C0 | 극단 중복 진단 | [#187](https://github.com/fabxoe/open_cancer/issues/187) | explore | [#197](https://github.com/fabxoe/open_cancer/pull/197) | COMPLETED | N/A | 극단 후보 0개 확인, C1 완료 |
| C1 | 보수적 Phi/Jaccard 삭제 | [#188](https://github.com/fabxoe/open_cancer/issues/188) | EXP-188 | [#198](https://github.com/fabxoe/open_cancer/pull/198) | COMPLETED | 0.4179737169 | ARCHIVE; 사전 등록 C2 실행 |
| C2 | 중간 강도 Phi/Jaccard 삭제 | [#189](https://github.com/fabxoe/open_cancer/issues/189) | EXP-189 | [#199](https://github.com/fabxoe/open_cancer/pull/199) | COMPLETED | 0.4147096714 | ARCHIVE; 사전 등록 C3 실행 |
| C3 | 넓은 Phi/Jaccard 삭제 | [#190](https://github.com/fabxoe/open_cancer/issues/190) | EXP-190 | [#200](https://github.com/fabxoe/open_cancer/pull/200) | COMPLETED | 0.4157643312 | ARCHIVE; Phi/Jaccard threshold 탐색 종료 |
| R1 | 상관 pair 범주형 요약 | [#191](https://github.com/fabxoe/open_cancer/issues/191) | EXP-191 | [#201](https://github.com/fabxoe/open_cancer/pull/201) | COMPLETED | 0.4144744818 | ARCHIVE; R2 실행 |
| R2 | 희귀 mutation-presence filter | [#192](https://github.com/fabxoe/open_cancer/issues/192) | EXP-192 | [#202](https://github.com/fabxoe/open_cancer/pull/202) | COMPLETED | 0.4176058118 | ARCHIVE; R1~R2 threshold 재탐색 종료 |
| S1 | Elastic Net stability selection | [#203](https://github.com/fabxoe/open_cancer/issues/203) | EXP-203 | [#204](https://github.com/fabxoe/open_cancer/pull/204) | COMPLETED | 0.2996289845 | ARCHIVE; dense selector가 512-gene cap을 유발, S1 규칙 재튜닝 없이 S2 진행 |
| S2 | mRMR | [#205](https://github.com/fabxoe/open_cancer/issues/205) | EXP-205 | [#206](https://github.com/fabxoe/open_cancer/pull/206) | COMPLETED | 0.3976963538 | ARCHIVE; top-128 압축이 EXP-094보다 크게 하락, S2 규칙 재튜닝 없이 S3 진행 |
| S3 | Boruta | [#207](https://github.com/fabxoe/open_cancer/issues/207) | EXP-207 | [#208](https://github.com/fabxoe/open_cancer/pull/208) | COMPLETED | 0.3484416378 | ARCHIVE; 15~18 confirmed genes로 과도하게 압축되어 Macro F1·DLBC F1 붕괴, 재튜닝 중단 |
| M0 | Macro-F1 checkpoint 감사 기반 | [#217](https://github.com/fabxoe/open_cancer/issues/217) | 해당 없음 | [#218](https://github.com/fabxoe/open_cancer/pull/218) | COMPLETED | N/A | validation-only audit·결정적 tie-break·checkpoint 저장 계약 완료 |
| M1 | Macro-F1 checkpoint 선택 통제 실험 | [#219](https://github.com/fabxoe/open_cancer/issues/219) | EXP-219 | [#220](https://github.com/fabxoe/open_cancer/pull/220) | COMPLETED | 0.4222321460 | EXP-094 대비 +0.0053455721, fold std 개선·INFERENCE_VERIFIED; 정책 채택 |
| S4 | TruncatedSVD 비교 모델 | [#196](https://github.com/fabxoe/open_cancer/issues/196) | EXP-196 | PR 생성 예정 | COMPLETED | 0.3496748557 | Macro F1 -0.0672117·fold std와 DLBC 붕괴로 ARCHIVE; 차원 재탐색 중단 |

상태는 `PLANNED → IN_PROGRESS → PR_OPEN → MERGED → COMPLETED`만 사용하며, 필요하면 `BLOCKED` 또는 `REJECTED`로 종료한다. 이는 실험 재현 상태와 별개다.

## T0 — 공용 fold-safe selector 기반

Issue #183은 일반 Task이며 EXP-ID나 점수를 만들지 않는다. 다음을 공통 runner에 연결한다.

- outer-train만 입력받는 `FoldFeatureSelector` 계약
- fold별 선택 index·이름 해시·근거 JSON 저장
- 저장 mask를 checkpoint inference에서 재사용할 수 있는 load 검증
- 선택 후에만 optional resampling을 적용하는 순서
- selection metadata를 fold metrics에 남기는 계약

첫 구현은 Phi/Jaccard의 target-independent greedy pruner다. pair는 Phi 내림차순, Jaccard 내림차순, 공동 변이 수 내림차순, 유전자명 순으로 정렬한다. 한 유전자가 여러 pair에서 연쇄 삭제되지 않도록 non-overlapping greedy matching을 사용한다. 각 matched pair에서는 mutation prevalence가 더 낮은 유전자의 `__mutated`만 제거하고, 동률이면 사전순 뒤 유전자를 제거한다.

## C0–C3 — 보수적 상관 삭제 ladder

C0은 전체 train의 진단 보고서일 뿐 공식 선택이나 모델 학습에 쓰지 않는다. C1~C3은 별도 Experiment Issue에서 매 fold 다시 pair를 계산한다.

| 단계 | 사전 고정 기준 | 전체-train 진단 참고 | 목적 |
|---|---|---:|---|
| C0 | Phi ≥ 0.50, Jaccard ≥ 0.90, joint ≥ 20 | 후보 0개 | 극단 중복 부재 확인 |
| C1 | Phi ≥ 0.30, Jaccard ≥ 0.15, joint ≥ 20 | 약 4개 열 제거 | 가장 보수적인 삭제 |
| C2 | Phi ≥ 0.25, Jaccard ≥ 0.15, joint ≥ 20 | 약 57개 열 제거 | 중간 강도 삭제 |
| C3 | Phi ≥ 0.20, Jaccard ≥ 0.10, joint ≥ 20 | 약 276개 열 제거 | 넓은 삭제 |

진단의 후보 수는 전체 train에서 계산한 참고값이다. 공식 결과가 아니며 fold별 실제 mask와 수는 달라질 수 있다. C1~C3은 모두 EXP-094 XGBoost 설정과 balanced sample weight를 유지한다.

각 실험의 판정은 다음과 같다.

- **성능 채택:** EXP-094 대비 Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss 악화 없음
- **간소화 후보:** Macro F1 하락 `≤0.001`, fold 표준편차 악화 `<0.002`, Log Loss `+0.01` 이내, 어느 클래스 F1도 `-0.05` 미만 하락하지 않음
- 그 외: `ARCHIVE`로 보존하고 후속 튜닝·제출 후보에서 제외

C3 뒤에는 상관 임계값을 더 낮춰 반복 탐색하지 않는다.

## R1–R2 — 관계·빈도 기반의 해석 가능한 피처

- **R1:** C2 기준 fold별 non-overlapping pair에 `only_left`, `only_right`, `both_mutated`의 세 이진 피처를 더한다. 원래 v1 열은 삭제하지 않는다.
- **R2:** outer-train 양성 수가 5 미만인 `GENE__mutated` 열만 제거한다. 다른 유전자 채널은 유지한다.

단순 burden, 전역 mutation-type count, 고정 pathway burden은 이미 충분히 검증했으므로 반복하지 않는다. 새 그룹 요약은 pair처럼 사전 정의 가능하고 해석 가능한 관계로 제한한다.

## S1–S4 — 지도 선택·저차원 비교

target을 쓰는 selector도 반드시 outer-train 내부에서만 fit한다.

1. **S1 Elastic Net stability selection:** raw 4,384 mutation-presence에 outer train 내부 3-fold CV(`C=0.01, 0.03, 0.1, 0.3, 1.0`, `l1_ratio=0.5`)와 one-SE 규칙을 적용한다. 75% stratified subsample 20회에서 16회 이상 선택된 gene을 채택하고 최소 50·최대 512개로 고정한다.
2. **S2 mRMR:** outer-train 양성 수 5 이상 gene에 multiclass mutual information relevance와 binary normalized MI redundancy를 사용해 128개를 greedy 선택한다.
3. **S3 Boruta:** raw mutation-presence에서 balanced-subset RandomForest 500 trees, max 50 iteration, `perc=100`을 쓴다. confirmed gene이 10개 미만이면 모델을 학습하지 않고 `selector produced insufficient set`으로 기록한다.
4. **S4 TruncatedSVD:** raw presence에 outer-train-only 256 components를 fit하고, sample aggregate·fixed hotspot과 함께 XGBoost에 전달한다. 해석성이 낮으므로 통과해도 독립 비교·앙상블 후보로만 보존한다.

S1~S3은 선택된 유전자의 v1 유전자 블록과 global/hotspot을 유지한다. S4만 저차원 comparator로 원시 유전자 블록을 대체한다.

## 2026-08-02 마감 전 제출 관측과 재개 기준

마감 전 리더보드 제출은 이 로드맵의 selector 정책을 고르기 위한 실험이 아니라,
이미 재현 가능한 미제출 후보의 일반화 관측이다. 이 절은 **계획·재개 기준**이며,
실제 제출 여부·제출 시각·Public 점수는 `EXPERIMENT_HISTORY.md`의 제출 이력에만
사실대로 기록한다.

- 관측 후보: `EXP-135`(EXP-094와 EXP-125의 사전 고정 0.5/0.5 확률 평균),
  `EXP-094`(동결 Feature Spec v1 XGBoost 단독).
- Public 결과를 보고 Boruta 설정, 상관 임계값, feature 정책, 모델
  하이퍼파라미터 또는 blend 가중치를 역으로 바꾸지 않는다.
- 동일 SHA-256의 기존 제출물은 중복 제출하지 않는다.

제출 창이 끝난 뒤에는 다음 순서로 이 로드맵을 재개한다.

1. S3의 `confirmed gene < 10` 안전 종료를 구현한다. 이 경우 XGBoost를 학습하지
   않고 `selector produced insufficient set`으로 기록한다.
2. unit/integration test, History validator, `git diff --check`를 통과시킨다.
3. clean `main` 기반에서 EXP-207 canonical 5-fold를 한 번만 실행하고, 실제
   산출물·OOF 또는 충분하지 않은 selector 결과를 기록한다.
4. S3 결과가 gate를 통과하지 않으면 재튜닝 없이 `ARCHIVE`하고, 사전 등록된
   Macro-F1 checkpoint 선택 감사·통제 실험을 먼저 수행한 뒤 S4 TruncatedSVD
   comparator Issue로 진행한다.

## M0–M1 — Macro F1 checkpoint 선택 감사

S3 종료 후 S4에 앞서 일반 Task M0에서 validation-only iteration audit 기반을
구현한다. 이어지는 M1 통제 실험에서 공식 평가 지표와 XGBoost checkpoint 선택
기준의 정렬을 확인한다. EXP-094의 feature, canonical fold, seed, 모델
하이퍼파라미터를 유지하고 fold validation의 iteration별 Macro F1을 기록한다.
현재 `mlogloss` best iteration과 validation Macro F1 best iteration으로 만든
OOF를 비교하며 test와 Public LB는 iteration 선택에 사용하지 않는다.

판정 우선순위는 전체 OOF Macro F1, 클래스별 F1 붕괴, fold 표준편차 순이다.
Log Loss는 학습 상태와 확률 품질을 설명하는 보조 지표로 기록하며 단독 기각
조건으로 사용하지 않는다. 통제 실험에서 Macro F1이 개선되면 이후 XGBoost
실험의 checkpoint 정책 후보로 채택하고, 그렇지 않으면 기존 학습 방식을
유지한다. 과거 실험 전체를 일괄 재학습하지 않는다.

## 후속 해석·튜닝·모델 비교

- TreeSHAP은 성능 또는 간소화 gate를 통과한 모델의 validation fold에서만 설명용으로 계산한다. 삭제 기준으로 쓰지 않는다.
- Optuna는 채택된 하나의 feature policy에만 적용한다. 각 outer fold의 3-fold inner CV, TPE seed `42+fold`, 30 trials로 제한하며 상관 임계값 재탐색에는 쓰지 않는다.
- 채택 spec만 XGBoost·LightGBM·CatBoost·Elastic Net Logistic Regression에 같은 fold·클래스 순서로 적용하고 OOF 오류 상관·Log Loss·소수 클래스 F1을 감사한다.

## 기록 규칙

각 공식 실행은 resolved config, fold별 selector JSON, metrics, OOF/test 확률, artifact manifest와 필요시 실험 보고서를 생성한다. 실제 실행·제출 결과만 `EXPERIMENT_HISTORY.md`에 기록한다. 새 Issue·EXP-ID·PR과 상태 변경은 같은 PR에서 이 표에 갱신한다.
