# PROJECT_CONTEXT: 유전체 변이 기반 암종 분류

이 문서는 팀원과 AI 에이전트가 따라야 하는 프로젝트 운영 규칙의 **단일 원본**이다.
실제 결과 장부는 `EXPERIMENT_HISTORY.md`이며, 이 문서의 예시를 실제 기록으로 간주하지
않는다.

---

## 1. AI 에이전트 시작 지침

처음 clone한 팀원의 VS Code·`uv` 환경 설정은
[`docs/VSCODE_SETUP.md`](docs/VSCODE_SETUP.md)를 따른다.

저장소에는 다음 AI 도구별 연결 파일이 있으며, 모두 이 문서와
`EXPERIMENT_HISTORY.md`를 작업 전에 읽도록 지시한다.

| 도구 | 저장소 지시 파일 |
|---|---|
| OpenAI Codex | `AGENTS.md` |
| Claude Code | `CLAUDE.md`에서 `AGENTS.md` 가져오기 |

도구가 저장소 지시를 지원하더라도 새 대화에서 문서를 읽었는지 확인한다. 단순히
저장소를 clone하거나 파일이 존재하는 것만으로 모든 AI가 자동 인식한다고 가정하지
않는다.

새 대화나 새 작업을 시작할 때 다음 지침을 AI에 전달한다.

```text
저장소 루트의 PROJECT_CONTEXT.md를 처음부터 끝까지 읽고 준수하세요.
이어서 EXPERIMENT_HISTORY.md를 읽어 현재 실험 수, 최고 모델과 진행 중인
실험을 확인하세요.

모든 작업은 GitHub Issue에 연결해야 합니다. 최신 main에서 `N`, `N-<slug>`,
`issue-N` 또는 `issue-N-<slug>` 브랜치를 만든 뒤 작업하고, 테스트와 문서 갱신을
마친 후 PR을 생성하세요. 공식 실험은 Issue #N에서 EXP-NNN을 자동으로 파생하며
별도 EXP-ID를 예약하지 않습니다.

실행하지 않은 실험, 측정하지 않은 점수, 존재하지 않는 산출물을 추정하거나
예시에서 복사하지 마세요. 실험을 수행했다면 성공, 실패, 중단 여부와 관계없이
EXPERIMENT_HISTORY.md와 재현성 파일을 실제 값으로 업데이트하세요.
```

AI는 작업 전에 다음을 확인한다.

1. 현재 브랜치가 해당 Issue 번호를 포함하는가.
2. `main`에서 분기했으며 최신 `origin/main`이 반영되었는가.
3. 현재 브랜치에서 연결된 Issue 번호를 정확히 추출할 수 있는가.
4. 로컬 원본 데이터 해시가 기준과 일치하며, 원본·가공 데이터·모델·비밀 파일과
   승인되지 않은 OOF가 Git에 포함되지 않는가. 팀장 승인 소형 확률 OOF 예외는
   `reports/shared_oof/` manifest와 CI 검증을 반드시 갖춘다.
5. 공식 실험이라면 실행 코드가 기본값까지 포함한 resolved config를 저장하는가.

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
- 모델·피처·checkpoint의 채택 판단은 전체 OOF Macro F1을 최우선으로 하고,
  클래스별 F1 붕괴와 fold 변동성을 안전성 지표로 확인한다. Log Loss는 확률
  품질과 학습 상태를 설명하는 보조 지표이며 단독 기각 조건으로 사용하지 않는다.
- `mlogloss` objective/eval metric을 사용해 학습하더라도 그것이 공식 평가 지표를
  바꾸지는 않는다. checkpoint 선택 기준이 Macro F1과 다르면 validation fold
  안에서 두 기준을 통제 비교해 resolved config와 metrics에 기록한다.
- checkpoint 선택 기준은 resolved config에 명시하고, 기준을 바꾸면 같은 모델의
  단순 재실행이 아니라 별도 Experiment Issue로 통제 비교한다. validation fold의
  Macro F1으로 checkpoint를 고른 뒤 같은 fold 점수를 보고하면 선택 과정에서 생긴
  낙관 편향 가능성을 보고서에 명시한다. 이 결과는 공식 OOF 비교에는 사용할 수
  있지만, 현재 최고·최종 후보는 반복 seed, 독립 재학습 또는 실제 Public 결과로
  안정성을 추가 확인한다.
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

### Track B Ensembl annotation 한정 예외

2026-08-04 팀장 승인에 따라 Task Issue #311과 그 구현에서 파생되는 첫 번째
불확실 residue-position mask 공식 실험에만 Ensembl release 116의 정적
GRCh38 GTF·protein FASTA annotation을 사용할 수 있다.

- 허용: MANE Select, Ensembl canonical, 알려진 protein isoform sequence에 대한
  입력 변이 token의 위치·reference amino-acid 일치 범주
- 허용 목적: `POSITION_VALID_REF_MISMATCH`, `OUTSIDE_ALL_KNOWN_ISOFORMS`,
  `COMPLEX_OR_UNMAPPABLE` token을 residue-position 집계에서 제외하는 사전 고정 mask
- 금지: 외부 환자 자료, 암종별 변이 빈도, 임상 label·위험도·치료 정보, test 분포나
  Public LB를 본 규칙·threshold 조정
- 분리: sample 범주 요약과 isoform-relative bin은 #311 예외에 포함하지 않으며
  별도 Issue와 명시적 범위 검토가 필요하다.

2026-08-04 추가 팀장 승인으로 Task Issue #315와 그 구현에서 파생되는 첫
`sample 범주 요약` 공식 실험에도 같은 Ensembl release 116 snapshot을 사용할 수
있다. EXP-313의 manifest SHA-256을 보존하기 위해 기존 manifest를 수정하지 않고
`knowledge/ensembl_isoform_annotation_b2_summary_v1.json`을 별도 revision으로
사용한다. 허용 피처는 여섯 상호 배타 의미 범주의 token `count`와 `any` indicator
각 1개, 총 12개로 고정한다. ratio, 학습 threshold, 암종별 가중치와 test/Public
기반 변경은 허용하지 않는다. isoform-relative bin은 여전히 별도 Issue 승인이
필요하다.

2026-08-04 Task Issue #307의 팀장 승인 범위를 B2-3까지 명시적으로 확장하고,
구현은 별도 Task Issue #325에서 관리한다. 과거 EXP-313·317 manifest의 해시를
보존하기 위해 `knowledge/ensembl_isoform_relative_bin_v1.json`을 별도 revision으로
사용한다. simple substitution이 일치하는 sequence는 MANE Select → Ensembl
canonical → other protein-coding isoform 순으로 선택하고, 같은 우선순위에서는
transcript ID·protein ID 사전순으로 대표 sequence를 고정한다. 잔기 위치를 대표
protein 길이로 나눈 값은 사전 고정 5개 구간으로 변환한다. 일치하지 않거나 복잡한
token은 값 0과 observed indicator로 구분한다. 이 값은 실제 발현 transcript나
임상적 isoform의 정답으로 해석하지 않는다. SUBCLASS·test 분포·Public LB로
우선순위, bin 경계나 대표 sequence를 변경하지 않는다.

resolved config에는 Ensembl release, assembly, manifest·annotation cache 경로와
SHA-256, 승인 근거 Issue comment URL을 저장한다. 이 예외는 프로젝트의 기본값인
`외부 데이터 사용 안 함`을 일반적으로 변경하지 않는다.

대회 원본 CSV와 여기서 직접 생성한 데이터 리포트는 주최측 정책에 따라 GitHub에
올리지 않는다. 팀원은 주최측 공식 다운로드 또는 팀에서 승인한 비공개 전달
방법으로 원본 CSV 3개를 받은 뒤 로컬 `data/raw/`에 배치한다. `data/raw/*`는
`.gitignore`로 제외하며 commit, Issue, PR, Release asset에도 첨부하지 않는다.
원본은 읽기 전용 입력으로 취급하고 실험이나 EDA 중 직접 수정하지 않는다. 가공
결과는 `data/processed/`에 저장하고 Git에 커밋하지 않는다. 기준 크기와 SHA-256은
`data/README.md`에서 관리한다. 공식 원본이 교체되면 별도 Issue와 PR에서 코드,
해시와 데이터 계약만 갱신하고 원본 파일 자체는 올리지 않는다.

2026-07-30 이전 clone은 raw data 제거를 위한 history 재작성 전 commit을 포함한다.
해당 clone에서 pull, merge 또는 push하지 말고
[`docs/TEAM_RECLONE_AFTER_HISTORY_REWRITE.md`](docs/TEAM_RECLONE_AFTER_HISTORY_REWRITE.md)
에 따라 새로 clone한다.

---

## 4. 폴더 역할과 파일 수명주기

```text
configs/           실험 전 사람이 작성하는 YAML 설정
data/raw/          팀원 로컬 전용 원본 CSV, Git 제외·직접 수정 금지
data/processed/    가공 데이터와 캐시, Git 제외
data/splits/       팀 공용 fold ID와 split 메타데이터, Git 추적
src/open_cancer/   재사용 가능한 로더, 평가, 검증 코드
scripts/           실험·검증용 실행 진입점
notebooks/         EDA와 프로토타입; 운영 실험은 scripts로 이전
models/            fold별 checkpoint, Git 제외
oof/               학습 데이터 OOF 확률, Git 제외
preds/             테스트 확률, Git 제외
reports/           실험별 README, 지표 JSON, 경량 CSV와 분석 자료
reports/shared_oof/ 팀장 승인 소형 OOF 확률의 Git 편의 복제본과 manifest
reports/plans/     여러 Issue에 걸친 장기 실행 계획과 단계별 진행 상태
reproducibility/   재현성 manifest와 비교 증빙; 대형 번들은 Release에 저장
submissions/       검증을 통과한 제출 CSV
schemas/           지표·재현성 JSON Schema
tests/             데이터가 없어도 실행 가능한 단위 테스트
```

### Feature Factory 운영 계약

모든 모델이 같은 파생변수를 재사용하도록 공통 Feature Factory를 사용한다. 구현,
캐시, family Registry, 동결과 스태킹 전환 규칙의 단일 상세 문서는
[`docs/FEATURE_FACTORY.md`](docs/FEATURE_FACTORY.md)다.
Residue-position과 문헌 기반 고정 co-mutation pair의 차이 및 위치 ablation의
쉬운 설명은
[`docs/RESIDUE_POSITION_AND_CO_MUTATION_GUIDE.md`](docs/RESIDUE_POSITION_AND_CO_MUTATION_GUIDE.md)를
따른다.

- Factory는 원본 CSV를 행 단위로 streaming 파싱하고, 파싱한 토큰에서만 피처를
  계산한다.
- 각 family는 정의 버전, 출력 차원, fit 범위와 외부 지식 출처를 Registry에
  기록한다.
- 입력 데이터 해시, 유전자 순서와 Feature Spec 해시가 모두 같고 모든 캐시
  산출물 해시가 일치할 때만 `data/processed/` 캐시를 재사용한다.
- family는 config에서 독립적으로 활성화하고, 실행값은 resolved config에
  자동 저장한다.
- target이나 관측 빈도로 hotspot, vocabulary, co-mutation pair를 고르는 family는
  fold-train에서만 fit한다.
- 공식 family 채택은 새 Experiment Issue와 공용 전체 5-fold를 사용한다. 빠른
  screening fold의 점수를 공식 결과로 기록하지 않는다.
- 외부 pathway, PPI, COSMIC 원본은 모델 입력 행으로 사용하지 않는다. 허용된
  외부 지식은 고정 그룹·관계·계산 규칙만 정의하며 환자별 입력값은 제공된
  4,384개 변이 셀에서 계산한다.
- 외부 지식에는 출처, 버전, 라이선스, 원본 SHA-256과 재배포 제한을 manifest에
  기록한다.
- 공개 문헌의 고정 pathway gene membership을 사용하고 환자별 값은 대회 CSV에서만
  계산하는 방식은 주최측 허용 답변을 받았다. 근거는 Issue #96의 고정 댓글
  <https://github.com/fabxoe/open_cancer/issues/96#issuecomment-5151028180>이며,
  이 허용을 외부 환자 데이터·임베딩·연속 weight 사용 허용으로 확대 해석하지 않는다.
- 위치 숫자는 입력 토큰에 명시된 단백질 잔기 위치다. genomic coordinate,
  codon nucleotide 위치나 transcript 정규화 좌표로 추정하지 않는다.
- 새 indicator나 missingness 피처를 공식 실험에 넣기 전에 기존 피처와 값이 같은지
  target-independent semantic equivalence 검사를 수행한다. 완전히 같은 열이면
  결측 해소 피처로 해석하지 않고 중복 피처 weighting perturbation으로 기록한다.
- 진단 예시나 외부 AI가 제시한 출력값은 실제 캐시에서 재계산하기 전까지
  History·보고서의 사실로 기록하지 않는다. 가능하면 기존 sparse 산출물을
  재사용하고 진단 입력 파일의 전체 SHA-256을 남긴다.
- residue-position의 유전자별 정규화와 recurrent hotspot은 validation fold를
  제외한 fold-train에서만 fit하는 transformer/selector로 분리한다. 정적 Feature
  Factory가 전체 train의 위치 범위나 validation/test 빈도를 미리 보게 만들지
  않는다.
- residue-position permutation negative control은 각 outer fold의 train에서만
  수행하고 validation은 원본으로 둔다. test는 사용하지 않으며 여러 고정 seed의
  paired fold 결과를 기록한다. 가능하면 mutation type·token-count strata를
  유지한다.
- Feature Spec v1을 동결한 뒤 모델 OOF 생산과 스태킹으로 전환한다. 이후 새
  family 아이디어는 v2 후보로 옮겨 현재 스태킹을 지연시키지 않는다.
- 모델 다양화 단계에서는 동결한 Feature Spec의 해시, canonical fold, ID와
  26개 클래스 순서를 모든 runner가 실행 전에 검증한다. 각 모델은 별도
  Experiment Issue에서 동일한 `(6201, 26)` OOF와 `(2546, 26)` test 확률을
  저장하고, 구현만 바꾸는 공통 runner 작업에는 EXP-ID를 만들지 않는다.
- 스태킹은 EXP-094 대비 OOF Macro F1 하락이 `0.004` 이내인 모델 중 OOF 오류
  상관이 `0.92` 이하이거나 예측 라벨 불일치율이 `10%` 이상인 조합이 있을 때만
  진행한다. meta learner는 cross-fitted 예측만 사용하며, 단순 고정 blend보다
  OOF Macro F1이 `0.002` 이상 개선되지 않으면 채택하지 않는다.
- Public LB 또는 test 분포를 보고 파서, 유전자 그룹, hotspot이나 feature 규칙을
  수정하지 않는다.
- mutation parser 변경은 기존 parser를 덮어쓰지 않고 별도 definition version과
  feature contract로 추가한다. token 원문은 provenance로 보존하되 모델 입력은
  공백·순서·대소문자와 의미상 같은 stop 표기(`X`, `*`, `Ter`)에 결정적이어야 한다.
  음수·UTR형 부분 표기나 `*숫자*`처럼 의미가 불명확한 값은 정상 단백질 잔기
  위치로 강제 해석하지 않고 `position-ineligible`로 격리한다.
  raw token multiplicity 대신 unique-gene count를 쓰는 robust 표현은 선택형 family로
  두고 별도 Experiment Issue의 canonical 5-fold를 통과하기 전 기본 Feature Spec으로
  승격하지 않는다. 상세 계약은
  [`docs/annotation_invariant_mutation_parser.md`](docs/annotation_invariant_mutation_parser.md)를
  따른다.
- Feature Factory에서 기본 parser가 아닌 parser adapter를 사용하려면 callable과
  함께 이름·definition version·변경 의미·target/test/Public 미사용 여부가 담긴
  `mutation_parser_contract`를 반드시 전달한다. contract는 Feature Spec과 cache
  key에 포함되어야 하며, 누락한 custom parser 실행은 실패해야 한다.
- 새 통합 parser를 사용하는 공식 runner는 notation normalizer, semantic parser,
  feature adapter의 버전과 fixture catalog SHA-256·schema version을 resolved config의
  `parser_contract`에 모두 기록한다. 누락되거나 저장소 catalog와 hash가 다르면
  실행을 실패시킨다. 역사적 runner와 Feature Spec v1에는 이 계약을 소급 적용하지
  않는다. 통합 계약과 fixture는
  [`reports/analysis/parser_contract_v4/README.md`](reports/analysis/parser_contract_v4/README.md)를
  따른다.
- 같은 생물학적 사건의 표기만 `*`/`X`/`Ter`로 바꾼 metamorphic fixture에서
  canonical feature matrix가 완전히 같아야 한다. 음수 부분 표기와 `*숫자*`는
  mutation presence/type을 임의 삭제하지 않되 residue-position에는 넣지 않는다.
- multi-letter frameshift와 range replacement는 substring이 아니라 complete anchored
  grammar로 판정한다. `SDEL133fs`의 residue `DEL`을 deletion keyword로 보거나,
  `721_722LA>FS`의 alternate Phe-Ser를 frameshift suffix로 보지 않는다. range의
  source structure와 stop/no-change/truncating protein consequence는 직교 속성으로
  보존하고, 첫 stop 뒤 source 문자는 provenance에는 남기되 번역된 alternate
  sequence와 모델 잔기에는 넣지 않는다. multi-letter frameshift prefix는 근거 없이
  reference·alternate peptide로 분해하지 않는다. 상세 계약과 실제 감사는
  [`docs/annotation_invariant_mutation_parser.md`](docs/annotation_invariant_mutation_parser.md)와
  [`reports/analysis/multiletter_frameshift_range_parser/README.md`](reports/analysis/multiletter_frameshift_range_parser/README.md)를
  따른다.
- protein insertion과 tandem duplication은 원문 syntax와 reference-aware 의미를
  분리한다. literal `dup`가 없더라도 `ins` 서열이 삽입 경계 바로 N-terminal의
  reference 서열과 완전히 같고 flanking residue·isoform이 검증된 경우에만
  duplication으로 추가 해석한다. 근처에 같은 서열이 있다는 이유만으로 승격하지
  않으며, 반복 구간은 HGVS 3' rule의 가장 C-terminal인 동등 표현을 사용한다.
  오른쪽 residue가 생략된 부분 경계 표기는 raw를 보존하고 reference 확인 전에는
  확정하지 않는다. stop·frameshift·extension·delins precedence, isoform 불일치와
  reference 누락 상태를 보존하며 DNA/exon 원인·repeat total copy number를 발명하지
  않는다. 상세 계약과 전수 감사는
  [`reports/analysis/protein_duplication_semantics/README.md`](reports/analysis/protein_duplication_semantics/README.md)를
  따른다.
- protein single-position substitution은 표준 amino acid 1개에서 다른 표준
  amino acid 1개로 바뀌는 ordinary missense, same-AA/no-change, immediate
  nonsense, `M1` start-site 영향과 unresolved reference 표기를 서로 구분한다.
  alternate `*`, `X`, `Ter`는 같은 stop 의미로 canonicalize하지만 leading `X`나
  leading `*`는 stop-loss·extension으로 추정하지 않는다. physicochemical delta는
  exact ordinary missense에만 허용하고 range·indel·frameshift는 전용 parser로
  전달한다. 실제 전수 감사와 v4 계약은
  [`reports/analysis/protein_substitution_semantics/README.md`](reports/analysis/protein_substitution_semantics/README.md)를
  따른다.
- protein deletion은 complete anchored grammar로 single/range와
  residue-aware/position-only를 구분한다. Range length는 inclusive하며 endpoint가
  인접할 필요는 없다. equal-position range는 raw를 보존한 semantic single로만
  정규화하고 reversed range는 자동 교환하지 않는다. `delins`, complete
  frameshift와 nonsense는 deletion보다 우선하며, fixed reference 없이 중간
  sequence나 HGVS 3′ 위치를 만들지 않는다. 실제 전수 감사와 v4 계약은
  [`reports/analysis/protein_deletion_semantics/README.md`](reports/analysis/protein_deletion_semantics/README.md)를
  따른다.
- protein delins는 deletion·insertion과 중복 집계하지 않고 raw source structure와
  immediate/later stop consequence를 함께 보존한다. Alternate의 first stop 이후
  sequence는 provenance에만 남기며 DNA frame을 추정하지 않는다. Multi-letter
  one-letter peptide 내부 upper-case `TER`는 Thr-Glu-Arg일 수 있으므로 전역 stop
  치환하지 않고 explicit `Ter` suffix와 `X/*`만 canonicalize한다. 실제 감사와
  v4 계약은
  [`reports/analysis/protein_delins_semantics/README.md`](reports/analysis/protein_delins_semantics/README.md)를
  따른다.
- 상관·희소도 기반 feature selection은 각 outer fold의 **학습 행에서만** fit하고,
  확정한 같은 mask를 validation·test에 적용한다. 상관을 `GENE__mutated`에서
  계산했다면 해당 mutation-presence 열만 제거하며 mutation-type, missing,
  residue-position, sample aggregate와 hotspot 열을 함께 삭제하지 않는다.
- fold별 selector는 candidate pair·prevalence·Phi·Jaccard·공동 변이 수·선택 mask
  및 feature-order hash를 checkpoint와 metrics에 저장한다. checkpoint 추론은 이를
  다시 읽어 같은 입력 열 순서를 재현해야 한다.
- train/test의 complex·위치 분포 차이는 OOD QC로만 기록하며 피처 선택,
  threshold, blend 가중치나 제출 후보를 정하는 근거로 사용하지 않는다.

### 클래스 불균형과 resampling

`StratifiedKFold`는 각 검증 fold의 클래스 비율을 가깝게 유지할 뿐, 학습 행을
복제하거나 합성하지 않는다. 기본값은 resampling 없이 학습 fold의
`balanced_sample_weight`만 사용하는 것이다.

- SMOTE 같은 resampling은 별도 Experiment Issue에서 사전에 method,
  `k_neighbors`, `sampling_strategy`, base seed를 config에 고정한 경우에만 쓴다.
- outer fold의 **학습 행만** resample한다. validation·test의 ID, 행 수, 값, 확률
  산출 순서는 원본 그대로여야 하며 resampler에 전달하지 않는다.
- resampling과 `balanced_sample_weight`를 동시에 쓰지 않는다. 공통 runner가 이를
  오류로 막으며, 실험 config에는 `balanced_sample_weight: false`를 명시한다.
- resolved config와 fold metrics에는 각 fold의 seed, resampling 전후 행 수와
  설정을 남긴다. 표준 SMOTE가 희소 이진 mutation feature 사이에 fractional 값을
  만들 수 있으므로, 점수 개선이 확인되기 전까지 기본 전략으로 채택하지 않는다.

### 파일 명명 규칙

Experiment Issue #12에서 파생된 `EXP-012`의 파일 slug는
`exp012_<short_slug>`로 통일한다.

```text
configs/exp012_<slug>.yaml
scripts/run_exp012_<slug>.py
models/exp012_<slug>/fold_00.<ext>
oof/exp012_<slug>.csv
preds/exp012_<slug>_test_proba.csv
reports/exp012_<slug>/metrics.json
reports/exp012_<slug>/README.md
submissions/exp012_<slug>.csv
reproducibility/exp012_<slug>/
```

공식 실험은 하나의 EXP-ID에 하나의 정식 runner만 둔다. 이미 사용한 runner
파일을 다음 실험의 코드로 덮어쓰지 말고, 변형은 새 Issue·새 파일·새 EXP-ID로
분리한다. 파일명을 고칠 때는 `git mv`와 History·보고서·실행 명령 갱신을 같은
PR에서 처리한다. 과거의 분석 전용 기록, 공용 runner, 보존되지 않은 역사적
runner는 `configs/experiment_source_legacy.yaml`에 실험 ID·예외 유형·대체 경로·
사유를 명시한다. 새 공식 실험은 legacy 예외에 추가하지 않는다.

`uv run python scripts/validate_experiment.py`는 config·runner·metrics·report의
EXP-ID 연결을 검사한다. 이 검사를 통과하지 못하면 점수나 재현 상태를 History에
승격하지 않는다.

### 실험 보고서 구조

`EXPERIMENT_HISTORY.md`는 전체 실험을 한눈에 찾는 단일 색인과 사실 장부로
유지한다. 파일이 길어진다는 이유로 `EXPERIMENT_HISTORY_1.md`,
`EXPERIMENT_HISTORY_2.md`처럼 번호를 붙여 분할하지 않는다.

개념 설명, 피처 변환 예시, 모델 해석과 긴 분석은 다음 파일에 둔다.

```text
reports/exp012_<slug>/README.md
```

GitHub는 폴더 안의 `README.md`를 자동으로 표시하므로 팀원이 reports 폴더에서 바로
읽을 수 있다. 공통 작성법과 복사 가능한 양식은
[`reports/README.md`](reports/README.md)와
[`reports/EXPERIMENT_REPORT_TEMPLATE.md`](reports/EXPERIMENT_REPORT_TEMPLATE.md)를
따른다.

- 베이스라인, 새로운 피처, 리더보드 제출, 현재 최고·최종 후보는 README 작성을
  권장한다.
- 작은 파라미터 변경은 긴 보고서를 만들지 않고 History와 metrics만 남겨도 된다.
- 보고서가 있으면 History 요약표와 상세 로그, PR 본문에서 같은 파일을 연결한다.
- 실제 점수와 산출물이 없는 상태에서 템플릿의 자리표시자를 결과처럼 기록하지 않는다.

여러 Issue와 실험에 걸친 장기 실행 계획은 `reports/plans/`에 둔다. 해당 계획을
사용하는 작업은 시작할 때 이 문서, `EXPERIMENT_HISTORY.md`와 관련 로드맵을 함께
읽는다. 로드맵은 작업 순서와 중단 조건을 관리하며, 실제 점수의 단일 원본은
`EXPERIMENT_HISTORY.md`와 실험별 `metrics.json`이다. 로드맵에는 예상 점수나
실행하지 않은 결과를 기록하지 않는다. 현재 전체 실행 계획의 단일 진입점은
[`ABC 신호 포트폴리오·스태킹 로드맵`](reports/plans/abc_signal_portfolio_stacking_roadmap.md)이다.
완료된 residue-position·hotspot 선행 과정은
[`reports/plans/residue_position_hotspot_roadmap.md`](reports/plans/residue_position_hotspot_roadmap.md)에
보존한다.
오리엔테이션의 중복 제거·관계 요약·지도 피처 선택은
[`오리엔테이션 기반 상관 삭제·피처 선택 로드맵`](reports/plans/orientation_correlation_feature_selection_roadmap.md)에서
별도 관리한다.

Issue #119의 canonical OOF 감사로 Feature Spec v2를 동결했다. 공식 명세는
[`configs/abc_stack_feature_spec_v2.yaml`](configs/abc_stack_feature_spec_v2.yaml),
선택 근거와 모든 입력 확률 해시는
[`ABC-Stack OOF 포트폴리오 감사`](reports/analysis/abc_oof_portfolio_audit.md)에
있다. `v2-performance`는 EXP-094에 fixed pathway burden을, `v2-diversity`는
EXP-094에 amino-acid change를 각각 하나만 추가한다. 후속 model runner는 이
명세를 임의로 바꾸지 않고 별도 Experiment Issue에서 공식 5-fold를 수행한다.

새 ABC family는 `src/open_cancer/feature_family.py`의 fold-train `fit`/`transform`,
family Registry, 외부 지식 provenance와 의미 중복 검사 계약을 사용한다. 모델은
`src/open_cancer/model_artifacts.py`의 고정 클래스 순서 OOF/test 확률 계약과 실행
기록 생성기를 사용한다. 공통 계약을 기존 EXP-094 경로에 소급 적용해 Feature
Spec을 바꾸지 않으며, v2 후보부터 적용한다.

Issue #121의 공통 runner는 동결 이름 `v1`, `v2-performance`, `v2-diversity`만
허용한다. 다음 명령은 모델을 학습하거나 점수를 만들지 않고 sparse matrix와
identity manifest만 생성한다.

```bash
uv run python scripts/materialize_frozen_feature_spec.py \
  --spec v1 \
  --output data/processed/<issue-or-exp>/v1
```

공식 모델 실험은 별도 Experiment Issue에서 `src/open_cancer/model_runner.py`의
공용 5-fold runner와 `write_cross_validation_artifacts`를 사용한다. 이 함수는
`oof_predictions.csv`, `test_probabilities.csv`, `metrics.json`을 고정 26개 클래스
순서로 저장한다. Logistic Regression과 XGBoost는 기본 환경에서 실행 가능하다.
LightGBM·CatBoost를 선택한 실험만 `uv sync --frozen --group experiment`를 먼저
실행한다. 일반 Task의 materialize·synthetic smoke 결과는 실험 History나 Local
OOF 점수로 기록하지 않는다.

### AI에 실험·제출 보고서 요청하기

팀원은 Codex 또는 Claude의 새 채팅에서 Issue 번호만 바꿔 다음 최소 프롬프트를
사용한다.

```text
PROJECT_CONTEXT.md를 먼저 읽고 규칙을 따라줘.
Issue #<번호> 실험의 제출별 보고서를 만들거나 갱신하고
EXPERIMENT_HISTORY.md와 현재 PR에 연결해줘.
실제 파일에 있는 사실만 사용하고, 초보 팀원도 이해할 수 있게 설명해줘.
검증 후 현재 Issue 브랜치에 push하되 merge하지 마.
```

이 요청을 받은 AI는 별도의 상세 프롬프트가 없어도 다음 순서로 처리한다.

1. `PROJECT_CONTEXT.md`, `EXPERIMENT_HISTORY.md`와
   `reports/EXPERIMENT_REPORT_TEMPLATE.md`를 읽는다.
2. 현재 브랜치와 GitHub Issue 번호가 일치하는지 확인한다.
3. config, resolved config, metrics, notebook, 로그와 산출물에서 실제 사실을
   확인한다. 문서 작성을 위해 모델을 임의로 재학습하거나 결과를 새로 만들지 않는다.
4. 확인할 수 없는 값은 추측하지 않고 `N/A` 또는 `미제출`과 그 사유로 기록한다.
5. `reports/expNNN_<slug>/README.md`를 만들거나 기존 보고서를 갱신한다.
6. 원본 데이터가 어떻게 모델 입력으로 바뀌는지, 모델이 무엇을 학습하는지,
   검증 방법과 실제 결과, 한계와 다음 실험 후보를 초보자도 이해할 수 있게 설명한다.
7. `EXPERIMENT_HISTORY.md`에는 긴 설명을 복사하지 않고 결과 요약과 보고서
   상대경로 링크만 기록한다.
8. 현재 PR 본문에도 GitHub에서 열 수 있는 보고서 링크를 추가한다.
9. 관련 테스트와 문서 검증을 실행하고 현재 Issue 브랜치에 push하지만,
   팀원 승인 전에는 merge하지 않는다.

보고서는 실험 Issue에서 파생된 `EXP-NNN` 단위로 관리한다. 같은 실험의 리더보드
제출이 여러 번이면 보고서 안에 제출별 변경점과 점수를 구분하고,
`EXPERIMENT_HISTORY.md`의 리더보드 제출 이력에는 제출 CSV마다 한 행씩 기록한다.

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

이 파일은 모델 결과가 아니라 각 train `ID`가 어느 검증 fold에 들어갈지를 미리
정한 배정표다. 원본 train의 `ID`와 `SUBCLASS`만 사용해 생성했으며 모델 학습,
예측, 점수 계산은 하지 않았다. 따라서 실험이 0건인 초기 저장소에 존재할 수 있는
공용 검증 인프라다. 사전에 고정하면 팀원마다 우연히 쉬운/어려운 검증 표본을
받아서 점수가 달라지는 문제를 줄이고, 모델 변경 효과를 같은 조건에서 비교할 수
있다. 개념과 실제 사용 코드는
[`docs/VSCODE_SETUP.md`](docs/VSCODE_SETUP.md#6-공용-split이란)에 설명한다.

- 생성 방식: `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`
- 저장 컬럼: `ID,fold`
- 모든 비교 실험은 같은 fold ID와 파일 해시를 사용한다.
- 다른 split은 별도 실험으로 간주하고 새 Experiment Issue를 생성한다.
- 전체 OOF를 모두 채운 뒤 `f1_score(y_true, y_pred, average="macro")`를 계산한다.
- fold 평균만 보고하지 말고 전체 OOF 점수, fold별 점수와 표준편차를 함께 기록한다.
- 결측 처리, vocabulary, 인코더, scaler, feature selection은 fold train에서만 fit한다.
- test 또는 validation의 타깃·분포 정보를 학습 전처리에 사용하지 않는다.
- leaderboard 점수를 보고 개별 test 라벨을 수동 수정하지 않는다.

---

## 6. Issue 기반 실험 ID와 상태

### ID 생성

실험 ID는 별도로 예약하지 않고 GitHub Experiment Issue 번호에서 파생한다.

```text
GitHub Experiment Issue #12 → EXP-012 → 파일 prefix exp012
GitHub Experiment Issue #105 → EXP-105 → 파일 prefix exp105
```

1. `.github/ISSUE_TEMPLATE/experiment.yml`로 실험 Issue를 생성한다.
2. GitHub가 부여한 Issue 번호 `N`을 브랜치에 넣는다.
3. 브랜치 형식은 `N`, `N-<slug>`, `issue-N`, `issue-N-<slug>`를 허용한다.
4. 공식 실험은 `RUN_MODE="experiment"`로 실행한다.
5. `open_cancer.experiment`가 현재 브랜치에서 Issue 번호를 읽고 `EXP-NNN`을
   자동 생성한다.
6. 일반 task, bug, 문서 Issue와 `RUN_MODE="explore"`에는 EXP-ID를 만들지 않는다.

Issue 번호는 저장소 전체에서 공유되므로 실험 번호가 연속일 필요가 없다.
`EXP-012` 다음 실험이 `EXP-017`이어도 정상이다. 숫자 전용 브랜치도 허용하지만
사람이 목적을 알아보기 쉬운 `issue-12-exp-xgb-baseline` 형식을 권장한다.

### Issue 번호와 EXP-ID의 역할

두 번호의 숫자는 같지만 역할은 다르다.

| 구분 | 용도 |
|---|---|
| GitHub Issue `#12` | 할 일, 대화, 담당자, 브랜치와 PR을 연결하는 협업 공간 |
| 실험 ID `EXP-012` | 실행 결과, config, OOF, 모델과 제출 파일을 묶는 산출물 키 |

- GitHub가 Issue 번호를 한 번만 발급하므로 팀원끼리 EXP-ID가 겹치지 않는다.
- 같은 실험을 함께 구현하거나 재현하면 같은 Issue와 `EXP-012`를 공유한다.
- 같은 Issue 안에서는 합의한 하나의 config를 공식 결과로 남긴다. 다른 모델이나
  비교 변형을 공식 결과로 남기려면 새 Experiment Issue를 만든다.
- 과거처럼 한 Issue 안에서 여러 구성을 이미 실행한 경우 결과를 삭제하거나
  EXP-ID를 소급 변경하지 않는다. 채택 config에는 `record_role: official`,
  미채택 비교에는 `record_role: exploratory_ablation`을 config, resolved
  config와 metrics에 동일하게 기록한다. 한 EXP-ID에는 `official`이 정확히
  하나만 존재해야 한다.
- 단순 탐색과 임시 Notebook 실행은 `RUN_MODE="explore"`로 수행하며 EXP-ID나
  History 기록을 만들지 않는다.
- EXP-ID는 사람이 입력하는 값이 아니다. 브랜치와 Issue 번호에서 코드가 자동
  생성한다.

### 허용 실험 상태

- `PLANNED`: Experiment Issue를 생성함
- `RUNNING`: 학습 또는 분석 실행 중
- `COMPLETED`: 실행과 필수 기록이 정상 완료됨
- `FAILED`: 오류 또는 검증 실패로 완료하지 못함
- `ABORTED`: 근거를 기록하고 의도적으로 중단함

실패와 중단도 삭제하지 않는다. 동일 설정에서 실행 환경만 복구한 재시도는 같은
Issue/EXP-ID 아래 attempt를 추가한다. 모델, 피처, split, seed, 앙상블,
threshold 또는 후처리가 달라져 예측이 바뀌면 새 Experiment Issue를 생성한다.

---

## 7. 실험 설정 계약

### 기본값 우선 원칙

Issue를 만들 때 하이퍼파라미터를 일일이 작성하지 않는다. 별도 요청이 없으면 다음
프로젝트 기본값을 사용한다.

| 항목 | 기본값 |
|---|---|
| 평가 지표 | 전체 OOF Macro F1 |
| split | `data/splits/stratified_5fold_seed42.csv` |
| fold 수 / seed | 5 / 42 |
| 클래스 순서 | 이 문서의 고정 26개 순서 |
| 재현 상태 | `NOT_STARTED` |
| 부모 실험·가설·사람이 작성한 변경 메모 | 없음 |
| 외부 데이터 | 사용 안 함 |
| 앙상블·TTA·threshold·후처리 | 사용 안 함 |

모델별 기본 하이퍼파라미터는 config 또는 실행 코드에서 제공한다. 사용자가 일부
값만 덮어쓰면 실행 코드가 나머지 기본값을 병합한다. 사람이 Issue와 History에
전체 파라미터를 다시 옮겨 적지 않는다.

실제 공식 실행에서는 코드가 기본값과 사용자 override를 모두 합친
`config.resolved.yaml`을 저장한다. 이 파일이 “실제로 사용한 값”의 단일 원본이다.
하이퍼파라미터를 Issue 본문이나 실행 코드에만 남기지 않는다.

```text
configs/exp012_<slug>.yaml
reproducibility/exp012_<slug>/config.resolved.yaml
```

resolved config에는 실행에 실제 적용된 항목만 기록한다.

- 자동 수집: Issue 번호, 실험 ID, 실행자, commit SHA, dirty worktree 여부
- train/test/sample submission SHA-256
- 유전자 컬럼 목록 또는 목록 파일과 순서 해시
- 클래스 순서
- 외부 데이터를 사용한 경우에만 출처, 버전, 라이선스, 해시
- split 파일, 해시, 방식, fold 수, seed
- 결측, 인코딩, 피처 생성·선택, 스케일링 파라미터
- 모델 클래스, 라이브러리 버전, 전체 모델 파라미터
- objective, eval metric, class/sample weight
- 사용하는 경우에만 early stopping, best iteration, checkpoint 선택 기준
- Python, NumPy, 모델, fold별 seed
- 스레드 수, `PYTHONHASHSEED`, deterministic 옵션
- 해당 모델에서 사용하는 경우에만 epoch, batch size, optimizer, scheduler
- 사용한 경우에만 앙상블 구성, 가중치, threshold, TTA와 후처리
- 학습·추론 명령과 입력·출력 경로

### macOS·Windows 공통 기록 규칙

- config, metrics와 manifest에 저장하는 저장소 내부 경로는 OS와 관계없이 `/`를
  사용하는 상대경로로 기록한다. Windows의 `\` 경로를 그대로 저장하지 않는다.
- Git으로 공유하는 text 파일은 `.gitattributes`의 LF 정책을 따른다.
- 공용 split의 canonical SHA-256은
  `1a99b82e758948fdf70c014b8270b73f0de805cd2450d119fcb20c08a9b169cf`이다.
- 과거 Windows 실행처럼 CRLF 때문에 byte SHA-256이 달라졌다면 실제 실행 해시를
  삭제하지 않고 `canonical_repository_sha256`, 줄바꿈 형식과 논리적 fold 일치
  여부를 함께 기록한다.

부모 실험, 가설, 사람이 설명한 변경점은 선택 정보다. 작성자가 판단하기에 비교나
의사결정에 도움이 될 때만 Issue 또는 config의 `notes`에 기록한다. 변경된 실제
파라미터는 `config.resolved.yaml`과 Git diff로 확인하며 사람이 중복 기록하지 않는다.

---

## 8. 재현성 계약

### 재현 상태

- `NOT_STARTED`: 재현 자료 미작성
- `MANIFEST_COMPLETE`: 설정·환경·데이터·산출물 manifest 완료
- `INFERENCE_VERIFIED`: checkpoint로 제출 CSV를 동일하게 재생성
- `TRAINING_VERIFIED`: 비작성자가 clean 환경에서 재학습까지 검증
- `FAILED`: 재현 검증 실패

재현 상태에는 검증 범위를 함께 기록한다. 저장 checkpoint를 다시 읽어 같은 제출을
만드는 `INFERENCE_VERIFIED`와, 모델을 처음부터 다시 학습하는
`TRAINING_VERIFIED`는 서로 대체하지 않는다. 특히 macOS·Windows·Linux,
CPU·CUDA와 라이브러리 빌드가 달라진 재학습은 다음 항목을 comparison과 환경
manifest에 남긴다.

- 원 실행과 재현 실행의 OS, 아키텍처, CPU/GPU, 모델 라이브러리·compiler 빌드
- thread 수, tree method, deterministic 옵션과 seed
- OOF·test 라벨 일치율, 확률 오차, Macro F1 차이
- 같은 플랫폼 검증인지 교차 플랫폼 검증인지와 통과하지 못한 조건

플랫폼이 달라 checkpoint byte나 재학습 확률이 달라져도 저장 checkpoint 추론으로
원 제출을 재생성한 사실은 삭제하지 않는다. 다만 사전 통과 조건을 만족하지 못한
교차 플랫폼 재학습을 `TRAINING_VERIFIED`로 승격하거나, 같은 플랫폼에서만 확인한
결과를 교차 플랫폼 결정론으로 확대 해석하지 않는다.

`TRAINING_VERIFIED` manifest에는 `verification_scope`를 필수로 저장한다. 검증
operation은 `training_reproduction`, 환경 관계는 `same_environment`,
`same_platform`, `cross_platform` 중 하나이며 claim은 기존 확률·라벨·Macro F1
허용 조건을 통과한 `tolerance_verified`여야 한다. 환경 관계가 `unknown`이면
승격하지 않는다. XGBoost `tree_method=hist`에서 실제로 관측한 플랫폼 차이와
완화책은
[`XGBoost hist 교차 플랫폼 재현성 감사`](reports/analysis/xgboost_hist_cross_platform_reproducibility.md)를
따른다.

리더보드 제출 전 최소 `INFERENCE_VERIFIED`가 필요하다. 현재 최고 모델과 최종 수상
후보는 `TRAINING_VERIFIED`가 아니면 최종 모델로 지정할 수 없다.

History의 “최고 Local/Public 점수”는 과거 관측 최고 기록이고 재현 실패 모델도
사실대로 표시될 수 있다. “최종 제출 후보”와는 다른 개념이다. 최종 후보는 별도로
지정하며 반드시 `TRAINING_VERIFIED`여야 한다. 현재 최고 점수가 `FAILED`라면 새
Experiment Issue에서 clean 실행과 검증을 다시 수행하고, 과거 점수를 최종 후보로
승격하지 않는다.

checkpoint와 제출 파일을 생성하는 공식 실험 runner는 실행 전에 clean worktree를
확인하고, 학습 직후 저장 checkpoint를 다시 불러와 test 추론을 재생성한다. 원본
확률·라벨·제출 SHA-256이 모두 일치하면 재현성 manifest와 증빙 파일을 자동
생성하고 `INFERENCE_VERIFIED`로 기록한다. 검증에 실패하면 성공 상태를 만들지
않고 실행을 실패 처리한다. 비작성자의 독립 재학습이 필요한
`TRAINING_VERIFIED`는 자동 부여하지 않는다.

재현성 파일을 모든 탐색 실험에서 사람이 완성할 필요는 없다.

| 단계 | 기본 재현 상태 | 필요한 기록 |
|---|---|---|
| 탐색 실행 | EXP-ID 없음 | 필요 없음 |
| 공식 Local 실험 | `NOT_STARTED` 허용 | resolved config, metrics, History |
| 리더보드 제출 | `INFERENCE_VERIFIED` 이상 | manifest, checkpoint 추론, 제출 SHA-256 |
| 팀 상위·앙상블 부모 | `INFERENCE_VERIFIED` 권장 | Release bundle, OOF·test 확률, SHA-256 |
| 현재 최고·최종 후보 | `TRAINING_VERIFIED` | 비작성자의 독립 재학습 검증 |

따라서 일반 Local 실험을 시작할 때 manifest 경로, Release, 검증자 등을 미리
작성하지 않는다. 모델이 실제로 제출되거나 팀 상위·앙상블 부모·최종 후보가 되어
다른 팀원이 산출물을 사용해야 할 때 해당 증빙을 추가한다.

### 실험별 증빙 구조

```text
reproducibility/exp012_<slug>/
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

- raw data는 Git commit, 재현 번들과 Release asset에 포함하지 않는다. 재현 시
  주최측 공식 경로로 별도 확보하며, 실험 manifest에는 파일 SHA-256만 기록한다.
- 리더보드 제출 모델뿐 아니라 팀 Local/Public 상위 모델과 앙상블 부모 모델의
  checkpoint·OOF·test 확률·재현 번들은 GitHub Release asset으로 보관한다.
- 재현 번들에는 최소한 fold checkpoint, OOF 확률, test 확률, 제출 CSV와
  `config.resolved.yaml`을 포함한다. 원본 데이터와 가공 데이터 원본은 포함하지
  않는다.
- Release tag는 `exp-012-repro-v1` 형식으로 정확한 실험 commit을 가리킨다.
- asset의 URL, 크기와 SHA-256을 manifest와 History에 기록한다.
- `INFERENCE_VERIFIED`를 유지하려면 다른 팀원이 clone한 뒤 manifest만 읽어도
  번들의 실제 다운로드 위치를 찾을 수 있어야 한다. 제출 후보의 `storage_uri`와
  `release_url`을 `null`로 남기지 않는다.
- 기존 asset을 덮어쓰지 않고 변경 시 `v2`를 만든다.
- asset 하나는 2 GiB 미만이어야 하며, 초과하면 fold별 또는 분할 압축한다.
- 참고: <https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases>

### 리더보드 제출 담당자의 재현 번들 절차

리더보드에 제출한 사람은 같은 Issue 브랜치와 PR에서 재현 번들 보관까지
완료한다. 팀장이나 다른 팀원이 나중에 로컬 산출물을 복구하는 방식으로 미루지
않는다.

1. 제출 전에 아래 공통 파일을 생성한다.

   ```text
   models/expNNN_<slug>/fold_*.json
   oof/expNNN_<slug>.csv
   preds/expNNN_<slug>_test_proba.csv
   submissions/expNNN_<slug>.csv
   reproducibility/expNNN_<slug>/config.resolved.yaml
   reproducibility/expNNN_<slug>/artifact_manifest.json
   ```

2. manifest의 artifact kind는 `checkpoint`, `oof_probability`,
   `test_probability`, `submission`, `resolved_config`를 사용한다. 각 항목에는
   실제 상대경로, 크기와 SHA-256을 기록한다.
3. 정확한 실행 source commit을 가리키는 tag를 만든다.

   ```bash
   git tag -a exp-012-repro-v1 <SOURCE_COMMIT> -m "EXP-012 reproducibility source"
   git push origin exp-012-repro-v1
   ```

4. 공통 스크립트로 OS와 관계없이 같은 구조의 번들을 생성하고 manifest의
   Release URL과 storage URI를 자동으로 채운다.

   ```bash
   uv run python scripts/prepare_reproducibility_bundle.py \
     --slug exp012_<slug> \
     --tag exp-012-repro-v1
   ```

5. 출력된 `dist/reproducibility/*.tar.gz`를 해당 GitHub Release에 업로드한다.
   업로드가 끝난 뒤 출력된 SHA-256과 Release asset을 대조한다. 원본 CSV는
   번들에 넣지 않는다.
6. 리더보드 점수와 제출 시각을 History에 기록하고 다음 검증을 실행한다.

   ```bash
   uv run python scripts/validate_experiment.py --check-remote-storage
   ```

CI는 History의 리더보드 제출 이력을 기준으로 새 제출 모델에 다음 사항을
강제한다.

- `INFERENCE_VERIFIED` 이상의 manifest
- checkpoint, OOF 확률, test 확률, 제출 CSV, resolved config와 release bundle
- 각 필수 artifact의 HTTPS `storage_uri`
- `release_url` 및 실제 Release asset 접근 가능 여부

정책 도입 전에 제출된 예외는 `configs/reproducibility_policy.yaml`에 사유와
후속 작업을 함께 기록한다. 새 실험을 편의상 예외 목록에 추가해서는 안 된다.
현재 예외도 해당 실험의 재현성 복구가 끝나면 즉시 삭제한다.

### 팀 상위 모델 산출물 요청·공유 규칙

이 절은 리더보드 제출 여부와 무관하게 팀 상위 모델, 최종 후보와 앙상블 부모의
OOF·test 확률·checkpoint를 팀원이 안전하게 재사용하기 위한 공통 절차다. 모든
Codex와 Claude Code는 작업 시작 시 이 절을 읽고, 브라우저·메신저로 파일을
개별 전달하는 대신 아래 절차를 사용한다.

1. 산출물이 아직 Release에 없으면 GitHub의 **실험 산출물 공유 요청** Issue Form을
   사용한다. 요청자는 EXP-ID와 필요한 artifact kind만 선택하고, 담당자는 오른쪽
   Assignees에서 지정한다. 별도 EXP-ID는 만들지 않는다.
2. 게시 담당자는 원 실험의 정확한 checkpoint, OOF, test 확률, submission과
   resolved config의 경로·크기·SHA-256을 manifest에 기록한다. 위의
   `prepare_reproducibility_bundle.py`로 새 버전 Release bundle을 만들고, asset을
   업로드한 뒤 manifest와 Release URL을 같은 Task PR에 반영한다.
3. 기존 Release asset을 덮어쓰지 않는다. 내용이 바뀌면 `v2`, `v3`처럼 새 tag와
   asset을 만들고, 원 실험의 점수·재현 상태를 임의로 변경하지 않는다.
4. 수신자는 manifest 반영 PR이 `main`에 병합된 뒤 최신 `main`에서 다음 명령을
   실행한다. 기본값은 checkpoint, OOF 확률, test 확률과 resolved config다.

   ```bash
   uv run python scripts/fetch_experiment_artifacts.py --experiment EXP-253

   # 앙상블에 필요한 확률만 받을 때
   uv run python scripts/fetch_experiment_artifacts.py \
     --experiment EXP-253 \
     --kinds oof_probability test_probability
   ```

5. 수신 스크립트는 EXP-ID로 manifest를 하나만 찾고 Release bundle의 크기와
   SHA-256, 각 파일의 크기·SHA-256, archive 경로 안전성을 검증한다. 해시가 같은
   기존 파일은 재사용하고, 다른 파일은 `--overwrite` 없이는 덮어쓰지 않는다.
6. 복원 위치는 manifest의 표준 상대경로인 `models/`, `oof/`, `preds/`와
   `reproducibility/`이다. `models/`, `oof/`, `preds/`와 다운로드 archive는 기본적으로
   Git 제외 대상이다. 아래의 팀장 승인 소형 OOF 확률 예외만
   `reports/shared_oof/`에 별도 편의 복제본을 둘 수 있다.
7. raw data와 외부 라이선스 데이터는 어떤 팀 공유 bundle에도 포함하지 않는다.
   공개 저장소의 GitHub Release asset은 외부에서도 다운로드할 수 있다. 대회 규정
   또는 라이선스상 공개할 수 없는 산출물은 public Release에 올리지 말고, 팀이
   승인한 비공개 저장소에 보관하되 동일 SHA-256과 접근 URI를 manifest에 기록한다.
8. 현재 Local/Public 최고가 갱신되거나 새 앙상블이 특정 실험을 부모로 채택하면,
   담당자는 수동 요청을 기다리지 않고 해당 모델의 manifest·Release bundle 상태를
   확인한다. 누락됐다면 즉시 일반 Task Issue로 보강한다.

Issue는 책임과 완료 상태를 추적하고, Release는 대형 immutable 파일을 보관하며,
manifest는 파일의 정체성과 해시를 증명한다. 이 세 역할을 하나로 섞지 않는다.

#### 팀장 승인 소형 OOF 확률의 Git 공유 예외

팀원이 자주 비교·검산하는 소형 OOF 확률은 매번 Release를 내려받지 않아도 되도록
일반 Task Issue에서 팀장 승인을 받은 경우에만 Git 편의 복제본을 허용한다. Release와
artifact manifest를 없애는 정책이 아니라 협업 접근성을 위한 제한적 추가 경로다.

- 허용 경로는 `reports/shared_oof/<issue-or-analysis-slug>/`뿐이다. 일반 `oof/`는
  계속 Git 제외 경로로 유지한다.
- CSV에는 `ID`와 위에 고정한 순서의 26개 클래스 OOF 예측 확률만 포함한다.
  `SUBCLASS`, `SUBCLASS_TRUE`, target/label, fold, 원본 변이값, test 확률,
  개인정보와 외부 비공개 데이터는 포함하지 않는다.
- 프로젝트 자체의 파일당 별도 한도는 두지 않는다. 대신 한 승인 Issue/manifest의
  전체 CSV 합계는 25 MiB, 저장소의 tracked shared OOF 누적 합계는 300 MiB 이하로
  유지한다. 이를 넘으면 Release만 사용한다. GitHub 플랫폼의 단일 파일 제한은
  별도로 적용된다.
- 각 디렉터리의 `manifest.json`에는 승인 Issue URL, 원 실행 source commit,
  생성 명령, 고정 클래스 순서, immutable Release URL, 파일 상대경로·크기·행 수·
  SHA-256을 기록한다.
- shared OOF는 immutable Release 원본의 편의 복제본이다. 공식 재현 상태,
  checkpoint, test 확률, submission과 resolved config는 계속 실험별
  artifact manifest·Release bundle로 관리한다.
- 새 shared OOF 추가 PR은 `uv run python scripts/validate_shared_oof.py`를 통과해야
  하며 CI가 schema, ID 고유성, 26개 클래스 순서, 확률 범위·행 합, 크기와 해시를
  검사한다.
- 기존 공유본을 조용히 덮어쓰지 않는다. 내용이 바뀌면 새 Issue 또는 명시적인
  revision 디렉터리를 만들고 Release version과 SHA-256도 함께 갱신한다.

---

## 9. `EXPERIMENT_HISTORY.md` 갱신 규칙

History는 실제 사실만 기록한다. 이 절의 자리표시자를 실제 기록으로 복사할 때는
반드시 실행 결과로 교체한다. History는 여러 번호 파일로 나누지 않고, 긴 설명은
실험별 `reports/expNNN_<slug>/README.md`로 분리해 연결한다.

### 상세 로그 양식

```markdown
### [{EXP_ID}] {실제 실험명}

- 상태: {PLANNED|RUNNING|COMPLETED|FAILED|ABORTED}
- 실행자: {GitHub ID 또는 자동 수집 값}
- Issue/브랜치: #{ISSUE} / {실제 브랜치명}
- 소스 commit: {실제 SHA}
- 시작/종료: {ISO-8601}

#### 실행
- Config: `{실제 경로}`
- Metrics: `{실제 경로}`
- Report: `{reports/expNNN_<slug>/README.md 또는 N/A}`

#### 결과
- Fold Macro F1: {실제 목록 또는 N/A와 사유}
- OOF Macro F1: {실제 값 또는 N/A와 사유}
- Public LB: {사용자가 확인한 실제 값 또는 미제출}
- 재현 상태: {허용 상태}

#### 산출물과 결론
- Metrics/Report/Reproduction: {실제 경로}
- 결론: {채택/보류/실패와 근거}

#### 선택 메모
{가설, 부모 실험, 변경 의도나 다음 행동이 필요할 때만 작성; 없으면 이 절 생략}
```

### 기록 원칙

- 측정하지 않은 값은 `N/A (사유)`로 적는다.
- Public LB는 실제 제출 후 사용자가 확인한 값만 기록한다.
- 제출 CSV마다 제출 이력 행을 별도로 추가한다.
- 재현 검증마다 비작성자와 증빙 경로를 재현성 검증 이력에 추가한다.
- 일반 Local 실험 완료에는 resolved config, metrics와 History만 필요하다.
- report는 분석이 필요할 때 추가한다. 재현 manifest는 리더보드 제출 또는 팀
  상위·앙상블 부모 산출물 공유가 필요할 때 추가한다.
- 보고서가 있으면 History에 내용을 복사하지 않고 상대경로 링크만 추가한다.
- 가설, 부모 실험과 변경 변수 설명은 필수가 아니다. 파라미터 전체를 History에
  복사하지 말고 resolved config를 연결한다.
- AI 또는 실행 코드가 실제 값으로 기록하며, 작성자가 파라미터를 수작업으로
  중복 입력하지 않는다.
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

4. Issue 번호가 일치하는 브랜치를 만든다. 숫자 전용 브랜치도 허용하지만
   설명이 포함된 형식을 권장한다.

   ```bash
   git switch -c issue-<번호>-<짧은설명>
   ```

   허용 예: `12`, `12-xgb-baseline`, `issue-12`, `issue-12-xgb-baseline`

   실험 권장 예: `issue-12-exp-xgb-baseline`

5. 구현과 테스트 후 다음 형식으로 커밋한다.

   ```text
   feat(#12): ...
   fix(#12): ...
   exp(#12): EXP-012 ...
   docs(#12): ...
   ```

6. 작업 브랜치를 push한다.

   ```bash
   git push -u origin issue-12-exp-xgb-baseline
   ```

7. base가 `main`인 PR을 만들고 첫 부분에 `Closes #12`를 작성한다.
8. 관련 팀원을 reviewer 또는 mention으로 알린다.
9. PR 작성자가 아닌 팀원 최소 한 명이 Approve한다.
10. 새 커밋이 추가되면 기존 승인이 취소되므로 다시 검토받는다. 최근 push를
    수행한 사람도 PR 작성자가 아니라면 승인할 수 있다.
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
- PR 작성자가 아닌 팀원 승인 최소 1개
- 새 커밋 push 시 기존 승인 취소 및 재검토
- 최근 push 수행자에 대한 별도 승인 제한은 적용하지 않음
- 모든 대화 해결
- `quality` status check 통과
- merge 전 main 최신 상태
- force push와 branch 삭제 차단
- merge commit만 허용

### GitHub Actions의 역할

이 저장소의 `quality` Action은 배포나 모델 학습을 수행하지 않는다. PR과 main
변경 시 `uv sync --frozen`, 경량 fixture 단위 테스트, History와 재현성 JSON
Schema 검증만 실행한다. 모델 학습이나 배포는 수행하지 않으며 checkpoint 없이도
공유 코드, 제출 검증 함수와 실험 장부 구조가 깨지지 않았는지 확인하는
안전장치다.

참고:
<https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets>

### 최초 저장소 예외

빈 원격에 base branch를 만들기 위한 내용 없는 `--allow-empty` 초기 커밋만 main 직접
push를 허용한다. 실제 프로젝트 파일은 프로젝트 초기화 Issue 브랜치와 PR을 통해
반영하고, 그 이후 예외를 허용하지 않는다.

---

## 11. 작업 체크리스트

### 실험 전

- [ ] `experiment` label이 붙는 GitHub Experiment Issue를 등록했다.
- [ ] 최신 main에서 Issue 브랜치를 만들었다.
- [ ] 브랜치에서 Issue 번호가 추출되고 `EXP-NNN`이 자동 파생되는지 확인했다.
- [ ] 공용 fold 파일과 데이터 hash를 확인했다.
- [ ] 별도 override가 없다면 프로젝트와 모델의 기본값을 사용한다.

### 실험 후

- [ ] 전체 OOF와 Macro F1을 생성했다.
- [ ] resolved config와 metrics를 저장했다.
- [ ] checkpoint 기반 실험은 자동 추론 재현 검증과 manifest 생성을 통과했다.
- [ ] 실패·중단을 포함해 History를 실제 값으로 갱신했다.
- [ ] 테스트와 schema 검증을 통과했다.

리더보드에 제출한 경우에만:

- [ ] 제출 파일 검증과 SHA-256 기록을 완료했다.
- [ ] manifest를 저장하고 checkpoint 추론으로 제출을 재생성했다.

### PR과 merge 전

- [ ] PR 본문에 `Closes #번호`가 있다.
- [ ] 로컬 `data/raw/` 원본의 크기와 해시가 기준과 일치하고 Git에 추적·staged되지
  않았다.
- [ ] 가공 데이터, 모델, 비밀 파일과 승인되지 않은 OOF가 Git에 없다. 승인된 소형
      OOF는 `reports/shared_oof/` manifest와 CI 검증을 갖춘다.
- [ ] CI `quality`가 통과했다.
- [ ] 팀원들이 최신 변경을 확인했다.
- [ ] 현재 최고/최종 후보는 비작성자의 재학습 검증을 통과했다.
