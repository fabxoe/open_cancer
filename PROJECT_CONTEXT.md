# PROJECT_CONTEXT: 유전체 변이 기반 암종 분류

이 문서는 팀원과 AI 에이전트가 따라야 하는 프로젝트 운영 규칙의 **단일 원본**이다.
실제 결과 장부는 `EXPERIMENT_HISTORY.md`이며, 이 문서의 예시를 실제 기록으로 간주하지
않는다.

---

## 1. AI 에이전트 시작 지침

새 대화나 새 작업을 시작할 때 다음 지침을 AI에 전달한다.

```text
저장소 루트의 PROJECT_CONTEXT.md를 처음부터 끝까지 읽고 준수하세요.
이어서 EXPERIMENT_HISTORY.md를 읽어 현재 실험 수, 다음 EXP-ID, 최고 모델과
진행 중인 실험을 확인하세요.

모든 작업은 GitHub Issue에 연결해야 합니다. 최신 main에서 Issue 번호가 포함된
브랜치를 만든 뒤 작업하고, 테스트와 문서 갱신을 마친 후 PR을 생성하세요.

실행하지 않은 실험, 측정하지 않은 점수, 존재하지 않는 산출물을 추정하거나
예시에서 복사하지 마세요. 실험을 수행했다면 성공, 실패, 중단 여부와 관계없이
EXPERIMENT_HISTORY.md와 재현성 파일을 실제 값으로 업데이트하세요.
```

AI는 작업 전에 다음을 확인한다.

1. 현재 브랜치가 해당 Issue 번호를 포함하는가.
2. `main`에서 분기했으며 최신 `origin/main`이 반영되었는가.
3. 다음 EXP-ID가 다른 작업자에게 예약되지 않았는가.
4. 원본 데이터, 모델, OOF, 비밀 파일이 Git에 포함되지 않는가.
5. 작업 후 실행할 검증 명령과 완료 조건이 Issue에 적혀 있는가.

---

## 2. 대회 개요

### 배경

암은 유전자 수준에서 발생하는 다양한 변이에 의해 아형이 결정되며, 아형에 따라
치료 방침과 예후가 크게 달라진다. 방대한 유전자 변이 정보로 정확한 암 아형을
판별하는 것은 전문가에게도 어려운 과제다.

이 프로젝트는 환자별 유전자 변이 프로파일을 이용해 암의 아형(`SUBCLASS`)을
예측하는 다중 분류 모델을 개발한다.

### 주제

유전자 변이 정보 기반 암 아형(서브타입) 예측 AI 알고리즘 개발

### 일정

- 07.30: 대회 시작
- 08.07: 팀 병합 마감
- 08.07: 대회 종료

연도와 세부 시각은 별도 공지가 없는 한 임의로 추정하지 않는다.

### 평가

- 공식 지표: **Macro F1**
- Local primary metric: 전체 OOF Macro F1
- 보조 지표: fold별 Macro F1, 클래스별 F1, Accuracy, Log Loss, Confusion Matrix
- 대회 데이터 안내:
  <https://dacon.io/competitions/official/236355/data>

---

## 3. 실제 데이터 계약

로컬 파일을 직접 검사한 결과를 구현 기준으로 사용한다.

| 파일 | 행 수 | 열 수 | 역할 |
|---|---:|---:|---|
| `data/raw/train.csv` | 6,201 | 4,386 | `ID`, `SUBCLASS`, 유전자 4,384개 |
| `data/raw/test.csv` | 2,546 | 4,385 | `ID`, 유전자 4,384개 |
| `data/raw/sample_submission.csv` | 2,546 | 2 | `ID`, `SUBCLASS` |

안내 이미지에는 6,199개 유전자라는 설명이 있지만 실제 제공 CSV에는 유전자 컬럼이
4,384개다. 모든 코드와 검증은 실제 CSV 스키마를 기준으로 한다.

### 고정 클래스 순서

확률 파일과 모델 출력은 다음 순서를 사용한다.

```text
ACC, BLCA, BRCA, CESC, COAD, DLBC, GBMLGG, HNSC, KIPAN, KIRC,
LAML, LGG, LIHC, LUAD, LUSC, OV, PAAD, PCPG, PRAD, SARC,
SKCM, STES, TGCT, THCA, THYM, UCEC
```

### 데이터 주의사항

- 각 유전자 셀은 수치가 아니라 `WT` 또는 변이 문자열이다.
- 한 셀에 공백으로 구분된 여러 변이가 들어갈 수 있다.
- test에는 빈 셀 237개가 존재하며 결측 정책을 config에 명시해야 한다.
- train의 약 99.19%, test의 약 98.22% 셀이 `WT`로 매우 희소하다.
- 샘플별 평균 비-WT 개수는 train 약 35.30개, test 약 78.13개로 차이가 있다.
- 26개 클래스는 불균형하며 최소 클래스 `DLBC` 38개, 최대 클래스 `BRCA` 786개다.
- `ID`는 모델 입력에서 제외하되 split, OOF, 제출 순서를 연결하는 키로 유지한다.
- train과 test의 유전자 컬럼명과 순서가 완전히 같아야 한다.
- 외부 데이터를 사용할 경우 출처, 버전, 라이선스, 다운로드 일시와 파일 해시를
  반드시 기록한다.

`data/raw/`와 `data/processed/`는 Git에 커밋하지 않는다. 팀원은
`data/README.md`의 SHA-256과 자신의 파일을 비교해 동일한 데이터를 사용해야 한다.

---

## 4. 폴더 역할과 파일 수명주기

```text
configs/           실험 전 사람이 작성하는 YAML 설정
data/raw/          대회 원본 데이터, Git 제외
data/processed/    가공 데이터와 캐시, Git 제외
data/splits/       팀 공용 fold ID와 split 메타데이터, Git 추적
src/open_cancer/   재사용 가능한 로더, 평가, 검증 코드
scripts/           실험·검증용 실행 진입점
notebooks/         EDA와 프로토타입; 운영 실험은 scripts로 이전
models/            fold별 checkpoint, Git 제외
oof/               학습 데이터 OOF 확률, Git 제외
preds/             테스트 확률, Git 제외
reports/           지표 JSON, 경량 CSV, 분석 Markdown
reproducibility/   재현성 manifest와 비교 증빙; 대형 번들은 Release에 저장
submissions/       검증을 통과한 제출 CSV
schemas/           지표·재현성 JSON Schema
tests/             데이터가 없어도 실행 가능한 단위 테스트
```

### 파일 명명 규칙

`EXP-001`의 파일 slug는 `exp001_<short_slug>`로 통일한다.

```text
configs/exp001_<slug>.yaml
scripts/run_exp001_<slug>.py
models/exp001_<slug>/fold_00.<ext>
oof/exp001_<slug>.csv
preds/exp001_<slug>_test_proba.csv
reports/exp001_<slug>/metrics.json
reports/exp001_<slug>/report.md
submissions/exp001_<slug>.csv
reproducibility/exp001_<slug>/
```

### 파일 인터페이스

OOF CSV:

```text
ID,SUBCLASS_TRUE,SUBCLASS_PRED,FOLD,PROBA_ACC,...,PROBA_UCEC
```

테스트 확률 CSV:

```text
ID,PROBA_ACC,...,PROBA_UCEC
```

제출 CSV:

```text
ID,SUBCLASS
```

제출 파일은 test와 ID 개수·값·순서가 같아야 하며, `SUBCLASS`는 고정 26개 클래스
중 하나여야 한다.

---

## 5. 검증 프로토콜

기본 비교 실험은 다음 fold 파일을 사용한다.

```text
data/splits/stratified_5fold_seed42.csv
```

- 생성 방식: `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`
- 저장 컬럼: `ID,fold`
- 모든 비교 실험은 같은 fold ID와 파일 해시를 사용한다.
- 다른 split은 별도 실험으로 간주하고 새 EXP-ID를 발급한다.
- 전체 OOF를 모두 채운 뒤 `f1_score(y_true, y_pred, average="macro")`를 계산한다.
- fold 평균만 보고하지 말고 전체 OOF 점수, fold별 점수와 표준편차를 함께 기록한다.
- 결측 처리, vocabulary, 인코더, scaler, feature selection은 fold train에서만 fit한다.
- test 또는 validation의 타깃·분포 정보를 학습 전처리에 사용하지 않는다.
- leaderboard 점수를 보고 개별 test 라벨을 수동 수정하지 않는다.

---

## 6. 실험 ID와 상태

### ID 예약

1. 최신 `main`의 `EXPERIMENT_HISTORY.md`에서 다음 ID를 확인한다.
2. 실험 실행 전에 요약표에 담당자와 `PLANNED` 상태를 기록한다.
3. `다음 실험 ID`를 다음 번호로 올린다.
4. 해당 변경을 Issue 브랜치에 커밋한 뒤 실행한다.

여러 팀원이 동시에 같은 ID를 예약했다면 먼저 main에 merge된 예약을 우선하고,
나머지는 최신 main을 반영한 뒤 새 ID를 발급한다.

### 허용 실험 상태

- `PLANNED`: 가설과 설정을 정의하고 ID를 예약함
- `RUNNING`: 학습 또는 분석 실행 중
- `COMPLETED`: 실행과 필수 기록이 정상 완료됨
- `FAILED`: 오류 또는 검증 실패로 완료하지 못함
- `ABORTED`: 근거를 기록하고 의도적으로 중단함

실패와 중단도 삭제하지 않는다. 동일 설정에서 실행 환경만 복구한 재시도는 같은
EXP-ID 아래 attempt를 추가한다. 모델, 피처, split, seed, 앙상블, threshold 또는
후처리가 달라져 예측이 바뀌면 새 EXP-ID를 발급한다.

---

## 7. 실험 설정 계약

하이퍼파라미터를 실행 코드에만 하드코딩하지 않는다. 사람이 작성한 config와,
기본값까지 병합된 실제 실행 config를 모두 보존한다.

```text
configs/exp001_<slug>.yaml
reproducibility/exp001_<slug>/config.resolved.yaml
```

resolved config에는 다음 항목이 빠짐없이 들어가야 한다.

- 실험 ID, 담당자, Issue 번호, 부모 실험, 가설
- 소스 commit SHA, dirty worktree 여부
- train/test/sample submission SHA-256
- 유전자 컬럼 목록 또는 목록 파일과 순서 해시
- 클래스 순서
- 외부 데이터 출처, 버전, 라이선스, 해시
- split 파일, 해시, 방식, fold 수, seed
- 결측, 인코딩, 피처 생성·선택, 스케일링 파라미터
- 모델 클래스, 라이브러리 버전, 전체 모델 파라미터
- objective, eval metric, class/sample weight
- early stopping, best iteration, checkpoint 선택 기준
- Python, NumPy, 모델, fold별 seed
- 스레드 수, `PYTHONHASHSEED`, deterministic 옵션
- epoch, batch size, optimizer, scheduler, learning rate
- 앙상블 구성, 가중치, threshold, TTA와 후처리
- 학습·추론 명령과 입력·출력 경로

---

## 8. 재현성 계약

### 재현 상태

- `NOT_STARTED`: 재현 자료 미작성
- `MANIFEST_COMPLETE`: 설정·환경·데이터·산출물 manifest 완료
- `INFERENCE_VERIFIED`: checkpoint로 제출 CSV를 동일하게 재생성
- `TRAINING_VERIFIED`: 비작성자가 clean 환경에서 재학습까지 검증
- `FAILED`: 재현 검증 실패

리더보드 제출 전 최소 `INFERENCE_VERIFIED`가 필요하다. 현재 최고 모델과 최종 수상
후보는 `TRAINING_VERIFIED`가 아니면 최종 모델로 지정할 수 없다.

### 실험별 증빙 구조

```text
reproducibility/exp001_<slug>/
├── REPRODUCE.md
├── config.resolved.yaml
├── environment.json
├── data_manifest.json
├── artifact_manifest.json
├── original_metrics.json
├── reproduction_metrics.json
├── comparison.json
└── checksums.sha256
```

- `environment.json`: OS, 아키텍처, CPU/GPU, Python, uv, 패키지 버전,
  CUDA/MPS, 스레드 설정, `uv.lock` 해시
- `data_manifest.json`: 입력과 feature/fold 파일의 경로, 크기, shape, SHA-256
- `artifact_manifest.json`: checkpoint, OOF, test probability, submission, 로그와
  리포트의 경로, 크기, SHA-256, 보관 URI
- `original_metrics.json`: fold/OOF/클래스별 점수, confusion matrix, 실행 시간
- `reproduction_metrics.json`: 독립 재실행에서 얻은 동일 항목
- `comparison.json`: 점수·확률 차이, 라벨 일치율, 제출 SHA-256 비교
- `REPRODUCE.md`: fresh clone부터 환경 설치, 데이터 배치, 학습, 추론, 검증까지
  순서대로 실행 가능한 명령

### 통과 조건

1. 기록된 commit/tag의 worktree가 clean이다.
2. `uv sync --frozen`으로 환경이 설치된다.
3. 데이터, fold, feature 순서와 클래스 순서 해시가 일치한다.
4. 저장 checkpoint 추론으로 byte-level SHA-256이 같은 제출 CSV가 생성된다.
5. 재학습 OOF 예측 라벨과 test 라벨이 100% 일치한다.
6. 확률은 `atol=1e-6`, `rtol=1e-6` 범위에서 일치한다.
7. OOF Macro F1 차이는 `1e-6` 이하이다.
8. 재학습 검증자는 원 실험 작성자가 아닌 팀원이다.
9. 하나라도 실패하면 원인과 환경 차이를 기록하고 승격하지 않는다.

### 체크포인트 보관

- raw data는 Git 또는 재현 번들에 포함하지 않는다.
- 리더보드 제출 모델의 checkpoint와 재현 번들은 GitHub Release asset으로 보관한다.
- Release tag는 `exp-001-repro-v1` 형식으로 정확한 실험 commit을 가리킨다.
- asset의 URL, 크기와 SHA-256을 manifest와 History에 기록한다.
- 기존 asset을 덮어쓰지 않고 변경 시 `v2`를 만든다.
- asset 하나는 2 GiB 미만이어야 하며, 초과하면 fold별 또는 분할 압축한다.
- 참고: <https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases>

---

## 9. `EXPERIMENT_HISTORY.md` 갱신 규칙

History는 실제 사실만 기록한다. 이 절의 자리표시자를 실제 기록으로 복사할 때는
반드시 실행 결과로 교체한다.

### 상세 로그 양식

```markdown
### [{EXP_ID}] {실제 실험명}

- 상태: {PLANNED|RUNNING|COMPLETED|FAILED|ABORTED}
- 담당자: {GitHub ID}
- Issue/브랜치: #{ISSUE} / issue-{ISSUE}-{slug}
- 부모 실험: {EXP-ID 또는 N/A}
- 소스 commit: {실제 SHA}
- 시작/종료: {ISO-8601}

#### 가설과 변경점
{부모 실험 대비 한 가지 핵심 가설과 실제 변경}

#### 실행
- Config: `{실제 경로}`
- 명령: `{실제 실행 명령}`
- 데이터/split hash: `{실제 SHA-256}`
- 환경: `{environment.json 경로}`

#### 결과
- Fold Macro F1: {실제 목록 또는 N/A와 사유}
- OOF Macro F1: {실제 값 또는 N/A와 사유}
- Public LB: {사용자가 확인한 실제 값 또는 미제출}
- 재현 상태: {허용 상태}

#### 산출물과 결론
- Metrics/Report/Reproduction: {실제 경로}
- 결론: {채택/보류/실패와 근거}
- 다음 행동: {구체적인 다음 실험 또는 종료}
```

### 기록 원칙

- 측정하지 않은 값은 `N/A (사유)`로 적는다.
- Public LB는 실제 제출 후 사용자가 확인한 값만 기록한다.
- 제출 CSV마다 제출 이력 행을 별도로 추가한다.
- 재현 검증마다 비작성자와 증빙 경로를 재현성 검증 이력에 추가한다.
- 실험 완료 커밋에는 config, metrics, report, History와 재현 manifest가 함께 있어야 한다.
- 일별 작업 내역은 중복되는 데일리 로그 대신 Git commit과 Issue/PR에 남긴다.

---

## 10. GitHub Issue, 브랜치와 PR 규칙

### 모든 작업의 표준 흐름

1. 코드, 문서, 실험, 버그, LB 결과 반영을 먼저 GitHub Issue로 등록한다.
2. 한 Issue에는 하나의 독립 작업 또는 실험만 둔다.
3. 최신 main을 받는다.

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

4. Issue 번호가 일치하는 브랜치를 만든다.

   ```bash
   git switch -c issue-<번호>-<짧은설명>
   ```

   예: `issue-12-exp001-xgb-baseline`

5. 구현과 테스트 후 다음 형식으로 커밋한다.

   ```text
   feat(#12): ...
   fix(#12): ...
   exp(#12): EXP-001 ...
   docs(#12): ...
   ```

6. 작업 브랜치를 push한다.

   ```bash
   git push -u origin issue-12-exp001-xgb-baseline
   ```

7. base가 `main`인 PR을 만들고 첫 부분에 `Closes #12`를 작성한다.
8. 모든 현재 팀원을 reviewer 또는 mention으로 알린다.
9. 모든 팀원이 Approve 또는 `확인` 댓글을 남기고, 비작성자 최소 한 명이 Approve한다.
10. 새 커밋이 추가되면 다시 검토받는다.
11. main이 변경되면 `origin/main`을 작업 브랜치에 merge하고 전체 테스트를 재실행한다.
12. CI 통과와 모든 대화 해결 후 GitHub의 merge commit 방식으로 병합한다.
13. main과 공유 브랜치에 force push하지 않는다.

### PR 필수 내용

- `Closes #이슈번호`
- 변경 목적과 범위
- 실행한 테스트 명령과 결과
- 관련 EXP-ID와 History 갱신 여부
- 재현 상태와 증빙·Release 링크
- 데이터 누출 및 대용량 파일 점검
- 리뷰어 확인

### main 보호 규칙

- PR 없이 변경 금지
- 비작성자 승인 최소 1개
- 최신 push에 대한 승인
- 모든 대화 해결
- `quality` status check 통과
- merge 전 main 최신 상태
- force push와 branch 삭제 차단
- merge commit만 허용

참고:
<https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets>

### 최초 저장소 예외

빈 원격에 base branch를 만들기 위한 내용 없는 `--allow-empty` 초기 커밋만 main 직접
push를 허용한다. 실제 프로젝트 파일은 프로젝트 초기화 Issue 브랜치와 PR을 통해
반영하고, 그 이후 예외를 허용하지 않는다.

---

## 11. 작업 체크리스트

### 실험 전

- [ ] GitHub Issue를 등록했다.
- [ ] 최신 main에서 Issue 브랜치를 만들었다.
- [ ] EXP-ID를 중복 없이 예약했다.
- [ ] 부모 실험과 단일 핵심 가설을 정의했다.
- [ ] config에 모든 변경 변수를 명시했다.
- [ ] 공용 fold 파일과 데이터 hash를 확인했다.

### 실험 후

- [ ] 전체 OOF와 Macro F1을 생성했다.
- [ ] resolved config, metrics와 manifest를 저장했다.
- [ ] 실패·중단을 포함해 History를 실제 값으로 갱신했다.
- [ ] 제출 파일 검증을 통과했다.
- [ ] checkpoint 추론으로 제출을 재생성했다.
- [ ] 테스트와 schema 검증을 통과했다.

### PR과 merge 전

- [ ] PR 본문에 `Closes #번호`가 있다.
- [ ] 원본 데이터, 모델, OOF, 비밀 파일이 Git에 없다.
- [ ] CI `quality`가 통과했다.
- [ ] 팀원들이 최신 변경을 확인했다.
- [ ] 현재 최고/최종 후보는 비작성자의 재학습 검증을 통과했다.
