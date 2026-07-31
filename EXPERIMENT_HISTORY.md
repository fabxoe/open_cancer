# 암종 분류 실험 기록

> 실제로 실행하거나 제출한 내용만 기록합니다.
> 작성 규칙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)를 따릅니다.
> 긴 개념 설명과 분석은 [reports 작성 안내](reports/README.md)에 따라 실험별
> `README.md`에 기록하고 이 파일에는 링크만 둡니다.

## 현재 상태

- 실제 실험 수: 5
- 실험 ID 규칙: GitHub Experiment Issue #N → EXP-NNN
- 다음 실험: Experiment Issue를 먼저 생성하고 발급된 번호를 사용
- 최고 Local OOF Macro F1: 0.4043796587000222 (`EXP-005`)
- 최고 Public LB Macro F1: 0.2987843366 (`EXP-005`)
- 최고 재현 검증 모델: `EXP-005` (`INFERENCE_VERIFIED`)
- 최종 갱신일: 2026-07-30

## 실험 요약

| ID | 상태 | 실행자 | Issue | 모델·메모(선택) | OOF Macro F1 | Public LB | 재현 상태 | 판단 | 상세 기록 |
|---|---|---|---|---|---:|---:|---|---|---|
| EXP-003 | COMPLETED | fabxoe | #3 | XGBoost mutation-presence baseline | 0.334930 | 0.228167518 | INFERENCE_VERIFIED | 비교 기준 | [보고서](reports/exp003_xgb_baseline/README.md) |
| EXP-005 | COMPLETED | 2heej | #5 | XGBoost + 유전자×변이유형 희소 피처 | 0.4043796587000222 | 0.2987843366 | INFERENCE_VERIFIED | 제출 재생성 검증 완료·Release 보관 필요 | [보고서](reports/exp005_xgb_mutation_features/README.md) |
| EXP-012 | COMPLETED | Kangho-Park | #12 | COSMIC 보호 유전자 기반 feature 보호 전략 분석 (모델 학습 없음) | N/A (분석 전용) | 미제출 | NOT_STARTED | 채택 | [상세](#exp-012-cosmic-보호-유전자-기반-feature-보호-전략-분석) |
| EXP-021 | COMPLETED | Kangho-Park | #21 | XGBoost, 전체 4,384 피처 + COSMIC 가중 burden 파생 컬럼 1개 (attempt 3, 4개 시도 중 최고) | 0.349410 | 0.2544194867 | NOT_STARTED | 채택(EXP-003 대비 개선, EXP-005엔 못 미침) | [상세](#exp-021-cosmic-보호-유전자-기반-피처-선택-및-파생변수-xgboost-baseline) |
| EXP-026 | COMPLETED | fabxoe | #26 | XGBoost mutation-presence + mutated-gene count | 0.3817476632 | 0.2575936484 | NOT_STARTED | EXP-003 대비 개선, EXP-005보다 낮음 | [보고서](reports/exp026_mutation_burden/README.md) |

## 리더보드 제출 이력

| 제출 시각 | 실험 ID | Issue | 제출 파일 | SHA-256 | Public 점수 | 순위 | 재현 상태 |
|---|---|---|---|---|---:|---:|---|
| 2026-07-30T18:20:48+09:00 | EXP-003 | #3 | `submissions/exp003_xgb_baseline.csv` (제출 ID `1506230`) | `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5` | 0.228167518 | 3 (확인 당시) | INFERENCE_VERIFIED |
| 2026-07-30T18:26:30+09:00 | EXP-005 | #5 | `submissions/exp005_xgb_mutation_features.csv` | `7bc3e64e1904d9b4007bc141dde771a39e7527172f3cd24c25c408000103183c` | 0.2987843366 | 제출 시점 1위 → 2026-07-30 23:13 KST 기준 2위 | INFERENCE_VERIFIED |
| 2026-07-30T23:28:27+09:00 | EXP-021 | #21 | `submissions/exp021_cosmic_weighted_burden_baseline.csv` (제출 ID `1506440`) | `cb75da2609631bc86310a637e2d4f2e244bfe85dac71da4f154559ebf19a07b0` | 0.2544194867 | 미확인(Dacon 제출 화면에 순위 미표시) | NOT_STARTED |
| 2026-07-30T23:56:29+09:00 | EXP-026 | #26 | `submissions/exp026_mutation_burden.csv` (제출 ID `1506469`) | `53d835335d6d23945c80acef4b70d0112f14abdaf1b5d504a63fd1ea7b16ef00` | 0.2575936484 | 미선택·개별 순위 미확인 | NOT_STARTED |

## 재현성 검증 이력

| 검증 시각 | 실험 ID | 검증자 | 소스 커밋·태그 | 데이터 일치 | 제출 재생성 | 재학습 검증 | 결과 | 증빙 |
|---|---|---|---|---|---|---|---|---|
| 2026-07-30T09:14:20Z | EXP-003 | fabxoe | `7306182669c3676e7b17024d3cf1f821131d909b` / [`exp-003-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-003-repro-v1) | SHA-256 일치 | byte-level SHA-256 일치 | 미수행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp003_xgb_baseline/comparison.json) |
| 2026-07-30T09:38:54.622845+00:00 | EXP-005 | 2heej | `816d0a5e070c29d2f549e4fb25b81ec5c0ad5f7b` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | `reproducibility/exp005_xgb_mutation_features/artifact_manifest.json` |

## 상세 실험 로그

<!-- 실제 실험 로그는 이 줄 아래에 시간순으로 추가합니다. -->

### [EXP-003] XGBoost mutation-presence baseline

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #3 / 3
- 소스 commit: `e58c5f0a02dff92030d4a2363fdf7622eccb5686`
- 시작/종료: 2026-07-30T08:15:12Z / 2026-07-30T08:18:02Z

#### 실행

- Config: `reproducibility/exp003_xgb_baseline/config.resolved.yaml`
- Metrics: `reports/exp003_xgb_baseline/metrics.json`
- Report: `reports/exp003_xgb_baseline/README.md`

#### 결과

- Fold Macro F1: 0.330432, 0.342344, 0.342316, 0.324125, 0.325573
- OOF Macro F1: 0.334930
- Public LB: 0.228167518, 제출 ID `1506230`, 제출 직후 3위
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction: `reports/exp003_xgb_baseline/`,
  `reproducibility/exp003_xgb_baseline/`
- Checkpoint Release:
  [`exp-003-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-003-repro-v1)
- 체크포인트 추론 검증: 원본·재생성 제출 SHA-256
  `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5`,
  test 라벨 일치율 100%, 확률 최대 절대 차이 0
- 결론: 순수 mutation-presence XGBoost의 이후 비교 기준으로 채택

### [EXP-005] XGBoost + 유전자×변이유형 희소 피처

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #5 / issue-5-hgvs-protein-normalization
- 소스 commit: 816d0a5e070c29d2f549e4fb25b81ec5c0ad5f7b
- 시작/종료: 2026-07-30T09:13:28.135923+00:00 / 2026-07-30T09:18:18.616817+00:00

#### 실행
- Config: `reproducibility/exp005_xgb_mutation_features/config.resolved.yaml`
- Metrics: `reports/exp005_xgb_mutation_features/metrics.json`
- Report: `reports/exp005_xgb_mutation_features/README.md`

#### 결과
- Fold Macro F1: [0.3957389475242374, 0.41264527023707276, 0.4011635978874454, 0.39173710435471243, 0.4130462426049025]
- OOF Macro F1: 0.4043796587000222
- Public LB: 0.2987843366 (제출 ID 1506233, 제출 시점 1위,
  2026-07-30 23:13 KST 기준 2위)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론
- Metrics/Report/Reproduction: `reports/exp005_xgb_mutation_features/metrics.json` / `reports/exp005_xgb_mutation_features/README.md` / `reproducibility/exp005_xgb_mutation_features/artifact_manifest.json`
- 결론: Public 0.2987843366으로 제출 시점 1위였으며 2026-07-30 23:13 KST
  기준 2위. 저장 checkpoint 추론으로 제출 SHA-256과 라벨 100% 일치를
  확인해 `INFERENCE_VERIFIED`로 승격함. 비작성자 재학습과 GitHub Release
  보관은 아직 완료하지 않음.
### [EXP-012] COSMIC 보호 유전자 기반 Feature 보호 전략 분석

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #12 / issue-12-cosmic-protected-genes
- 소스 commit: c5460fab46b78f82e40ace9c48acbcd61a19766a
- 시작/종료: 2026-07-30 / 2026-07-30

#### 실행
- Config: N/A (스크립트 상단에 경로·임계값을 직접 명시, 별도 YAML 없음)
- Metrics: `reports/exp012_feature_analysis/*.csv` (로컬 전용, 아래 라이선스 메모 참고)
- Report: N/A

#### 결과
- Fold Macro F1: N/A (모델 학습을 수행하지 않는 feature 분석 실험)
- OOF Macro F1: N/A (사유 상동)
- Public LB: 미제출
- 재현 상태: NOT_STARTED (모델 산출물이 없어 재현성 계약 대상 아님)

실제 실행 수치 (`uv run python scripts/exp012_feature_analysis.py`, train.csv 4,384개 유전자 기준):

- COSMIC CGC v104 화이트리스트 교집합: 361개 / 4,384개 (train 컬럼 전부 매칭)
- 화이트리스트 vs 비화이트리스트 변이율<1% 비율: 54.57% vs 77.85%
- tier1 297개(평균 변이율 1.39%) / tier2 64개(평균 변이율 1.25%)
- 화이트리스트인데 train 변이율 0%: 3개 (NSD2, KNL1, TENT5C) → 팀 판단으로 `protect` 확정
- 비화이트리스트 고변이율(>3%) 유전자: 79개 (long gene bias 의심, 검증 보류)
- 패널에 없는 known driver 유전자: KRAS, NRAS, BAP1, PBRM1, SETD2
- test 결측 25개 컬럼 중 화이트리스트 포함: 1개 (PTCH1)
- 최종 보호 규칙: `protect` 361개 / `drop` 151개 / `keep`(중립) 3,872개

#### 산출물과 결론
- Metrics: `reports/exp012_feature_analysis/protected_dropped_draft.csv`,
  `protected_genes_final.csv`, `dropped_genes_final.csv` 등 (COSMIC CGC v104
  유전자 심볼을 그대로 포함하므로 라이선스 확인 전까지 `.gitignore` 처리,
  로컬에만 보관)
- 결론: 채택. `protect_review` 3건은 train 관측 0건이지만 COSMIC 임상적 중요도를
  우선해 `protect`로 확정. 최종 보호/제거 유전자 목록은 후속 baseline 모델
  Issue의 feature 선택 입력으로 사용.

#### 선택 메모
- COSMIC CGC v104 화이트리스트(`data/external/gene_whitelist_cosmic_v104.csv`,
  라이선스: COSMIC 학술 라이선스, 등록 필요·재배포 금지)는 원본과 파생 산출물
  모두 Public 레포에 커밋하지 않음. `protected_genes_final.csv` /
  `dropped_genes_final.csv` 자체의 COSMIC 재배포 해당 여부는 아직 팀/COSMIC
  약관 확인 전이라 로컬 보관으로 보류.
- 다음 행동: 이 산출물을 입력으로 하는 "COSMIC 보호 유전자 기반 피처 선택
  XGBoost baseline" 작업을 새 GitHub Issue로 분리해 진행.

### [EXP-021] COSMIC 보호 유전자 기반 피처 선택 및 파생변수 XGBoost baseline

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #21 / issue-21-cosmic-feature-xgb-baseline
- 소스 commit: `0cde83c5fe59cf9fab34bf14eb6aacb3168078a7`
- 시작/종료: 2026-07-30T14:45:23Z / 2026-07-30T14:47:04Z (아래 4개 시도 중
  제출한 attempt 3 기준)

#### 실행

EXP-012(#12)의 protect/drop 결정을 입력으로, EXP-003과 동일한 공용 5-fold·
하이퍼파라미터로 4가지 피처 구성을 비교했다. 4개 시도 모두 fold train
구간에서만 상관관계를 재계산해 leakage를 방지했다 (PROJECT_CONTEXT.md 5절).

| 시도 | 피처 구성 | 피처 수 | Config | Metrics |
|---|---|---:|---|---|
| attempt 1 | protect 유전자만 | 361 | `configs/exp021_cosmic_protected_baseline.yaml` | `reports/exp021_cosmic_protected_baseline/metrics.json` |
| attempt 2 | protect + fold별 상관 상위 200 | 561(fold 평균) | `configs/exp021_cosmic_correlated_baseline.yaml` | `reports/exp021_cosmic_correlated_baseline/metrics.json` |
| **attempt 3(제출)** | 전체 4,384 + 가중 burden 통합 컬럼 1개 | 4,385 | `configs/exp021_cosmic_weighted_burden_baseline.yaml` | `reports/exp021_cosmic_weighted_burden_baseline/metrics.json` |
| attempt 4 | 전체 4,384 + protect_burden/correlated_burden 분리 컬럼 2개 | 4,386 | `configs/exp021_cosmic_group_burden_baseline.yaml` | `reports/exp021_cosmic_group_burden_baseline/metrics.json` |

- Report: N/A
- 재현성 manifest: `reproducibility/exp021_cosmic_*_baseline/config.resolved.yaml` (시도별)

#### 결과

| 시도 | OOF Macro F1 | Accuracy | Log Loss |
|---|---:|---:|---:|
| EXP-003(비교 기준, 전체 4,384) | 0.334930 | 0.355749 | 2.003723 |
| attempt 1(protect 361) | 0.301865 | 0.343009 | 2.080349 |
| attempt 2(protect+correlated 561) | 0.314403 | 0.349137 | 2.042861 |
| **attempt 3(전체+통합 burden, 제출)** | **0.349410** | 0.362361 | **1.929987** |
| attempt 4(전체+분리 burden 2개) | 0.344607 | 0.362845 | 1.930189 |

- Fold Macro F1(attempt 3): 0.335138, 0.354049, 0.360881, 0.349334, 0.337361
- Public LB: 0.2544194867 (attempt 3, 제출 ID `1506440`)
- 재현 상태: NOT_STARTED — 리더보드 제출 전 최소 `INFERENCE_VERIFIED` 권장
  기준(PROJECT_CONTEXT.md 8절)을 충족하지 못한 채 탐색적으로 제출함(의도적
  생략, 아래 선택 메모 참고)

#### 산출물과 결론

- Metrics/Reproduction: 위 표의 시도별 경로
- 제출 파일: `submissions/exp021_cosmic_weighted_burden_baseline.csv`
  (SHA-256 `cb75da2609631bc86310a637e2d4f2e244bfe85dac71da4f154559ebf19a07b0`)
- 결론: 채택(attempt 3). COSMIC 지식만으로 피처를 축소하는 attempt 1·2는
  EXP-003(전체 피처)보다 낮았지만, 전체 피처를 유지한 채 COSMIC 가중
  burden을 파생 컬럼으로 "추가"하는 attempt 3·4는 EXP-003을 능가함.
  둘 중에서는 protect/correlated 기여를 하나로 합친 attempt 3이 공식 지표
  (Macro F1)에서 attempt 4(분리 컬럼)보다 우수해 attempt 3을 제출함.
  단, EXP-005(OOF 0.4044, LB 0.2988)에는 아직 못 미쳐 팀 최고 기록은
  아님.

#### 선택 메모

- **Git history 재작성**: 이 실험은 원래 다른 로컬 clone에서 attempt 1~4를
  순서대로 진행했으나, 작업 도중 Issue #22(주최측 지침에 따른 원본 데이터
  Git history 제거, `git-filter-repo`로 전체 commit SHA 변경)가 발생했고
  이 branch는 재작성 이전에 원격에 push된 적이 없었다. 이에
  `docs/TEAM_RECLONE_AFTER_HISTORY_REWRITE.md` 절차대로 새로 clone한
  저장소 위에서 코드를 옮기고 4개 시도를 모두 재실행해 원래와 완전히 동일한
  제출 파일 SHA-256을 재확인한 뒤 커밋했다. 따라서 커밋 구성은 원본 진행
  순서와 다소 다르게(코드 3개 커밋 + 시도별 결과 4개 커밋) 재구성되었다.
- **재현성 계약 의도적 생략**: attempt 3을 Dacon에 제출하기 전 `INFERENCE_VERIFIED`
  체크포인트 검증(EXP-003 방식의 별도 verifier)을 만들지 않고 진행했다.
  탐색적 비교 목적의 1차 제출이라 판단했기 때문이며, 이 실험을 팀 최고
  모델 후보로 승격하려면 검증을 먼저 완료해야 한다.
- COSMIC CGC v104 화이트리스트와 EXP-012 산출물(`protected_genes_final.csv`
  등)은 라이선스 확인 전까지 Git 미포함 — 재현 절차는
  `docs/EXP-012_handoff.md` 4절 참고.
- 다음 행동: (a) attempt 3을 채택할 경우 checkpoint 추론 검증으로
  `INFERENCE_VERIFIED` 승격, (b) `correlated_gene_top_k`(현재 200) 조정이나
  burden 계산 방식 변경으로 추가 개선 여지 탐색, (c) COSMIC 화이트리스트
  재배포 가능 여부를 팀/COSMIC 약관으로 확정.
### [EXP-026] XGBoost mutation-presence + mutated-gene count

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #26 / issue-26-exp-mutation-burden
- 학습 소스 commit: `cb9c19679811104ba83eb2e7ce766166c484589e`
- 시작/종료: 2026-07-30T14:48:49Z / 2026-07-30T14:51:45Z

#### 실행

- Config: `reproducibility/exp026_mutation_burden/config.resolved.yaml`
- Metrics: `reports/exp026_mutation_burden/metrics.json`
- Report: `reports/exp026_mutation_burden/README.md`

#### 결과

- Fold Macro F1: 0.3755728860, 0.3901946095, 0.3852622979,
  0.3863606499, 0.3624281412
- OOF Macro F1: 0.3817476632
- Public LB: 0.2575936484 (제출 ID `1506469`)
- 재현 상태: NOT_STARTED

#### 산출물과 결론

- 입력은 EXP-003의 4,384개 유전자별 mutation-presence 피처와 동일하며,
  환자별 변이 유전자 개수인 `mutated-gene count` 한 개를 추가함.
- `mutated-gene count`는 패널 내 유전자 변이 존재 개수이며 임상적 TMB가 아님.
- EXP-003 대비 OOF `+0.046817` 및 Public LB `+0.0294261304`로 개선됨.
- EXP-005보다 OOF와 Public LB가 모두 낮아 최종 제출 후보로 선택하지 않음.
- 제출 파일 형식과 SHA-256은 확인했지만 저장 체크포인트로 제출 파일을
  독립 재생성하는 검증은 아직 수행하지 않았으므로 `NOT_STARTED`로 기록함.
