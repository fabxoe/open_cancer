# 암종 분류 실험 기록

> 실제로 실행하거나 제출한 내용만 기록합니다.
> 작성 규칙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)를 따릅니다.
> 긴 개념 설명과 분석은 [reports 작성 안내](reports/README.md)에 따라 실험별
> `README.md`에 기록하고 이 파일에는 링크만 둡니다.

## 현재 상태

- 실제 실험 수: 10
- 실험 ID 규칙: GitHub Experiment Issue #N → EXP-NNN
- 다음 실험: Experiment Issue를 먼저 생성하고 발급된 번호를 사용
- 최고 Local OOF Macro F1: 0.4088132438271497 (`EXP-047`)
- 최고 Public LB Macro F1: 0.2987843366 (`EXP-005`)
- 최고 재현 검증 모델: `EXP-047` (`INFERENCE_VERIFIED`)
- 최종 갱신일: 2026-07-31

## 실험 요약

| ID | 상태 | 실행자 | Issue | 모델·메모(선택) | OOF Macro F1 | Public LB | 재현 상태 | 판단 | 상세 기록 |
|---|---|---|---|---|---:|---:|---|---|---|
| EXP-003 | COMPLETED | fabxoe | #3 | XGBoost mutation-presence baseline | 0.334930 | 0.228167518 | INFERENCE_VERIFIED | 비교 기준 | [보고서](reports/exp003_xgb_baseline/README.md) |
| EXP-005 | COMPLETED | 2heej | #5 | XGBoost + 유전자×변이유형 희소 피처 | 0.4043796587000222 | 0.2987843366 | INFERENCE_VERIFIED | 제출·체크포인트 재생성 및 Release 보관 완료 | [보고서](reports/exp005_xgb_mutation_features/README.md) |
| EXP-012 | COMPLETED | Kangho-Park | #12 | COSMIC 보호 유전자 기반 feature 보호 전략 분석 (모델 학습 없음) | N/A (분석 전용) | 미제출 | NOT_STARTED | 채택 | [상세](#exp-012-cosmic-보호-유전자-기반-feature-보호-전략-분석) |
| EXP-021 | COMPLETED | Kangho-Park | #21 | XGBoost, 전체 4,384 피처 + COSMIC 가중 burden 파생 컬럼 1개 (attempt 3, 4개 시도 중 최고) | 0.349410 | 0.2544194867 | NOT_STARTED | 채택(EXP-003 대비 개선, EXP-005엔 못 미침) | [상세](#exp-021-cosmic-보호-유전자-기반-피처-선택-및-파생변수-xgboost-baseline) |
| EXP-026 | COMPLETED | fabxoe | #26 | XGBoost mutation-presence + mutated-gene count | 0.3817476632 | 0.2575936484 | NOT_STARTED | EXP-003 대비 개선, EXP-005보다 낮음 | [보고서](reports/exp026_mutation_burden/README.md) |
| EXP-029 | COMPLETED | 2heej | #29 | EXP-005 + 변이유형 구성비·log burden 피처 | 0.3988980085 | 미제출 | INFERENCE_VERIFIED | EXP-005 대비 OOF 하락·fold 변동성 증가로 현 구성 미채택 | [보고서](reports/exp029_xgb_log_burden_ratios/README.md) |
| EXP-033 | COMPLETED | 2heej | #33 | EXP-005 + log burden 3종 단독 ablation | 0.4057244634 | 미제출 | INFERENCE_VERIFIED | EXP-005 대비 소폭 개선·추가 분리 검증 필요 | [보고서](reports/exp033_xgb_log_burden_ablation/README.md) |
| EXP-031 | COMPLETED | Kangho-Park | #31 | EXP-005 변이유형 피처 + 알려진 cancer hotspot 위치 피처 (attempt 5, hotspot 19→34개 확장이 팀 최고) | 0.4135846695 | 0.3170803849 | NOT_STARTED | attempt 5 채택(팀 최고 Local·Public LB), INFERENCE_VERIFIED 검증 필요 | [보고서](reports/exp031_hotspot_extended/README.md) |
| EXP-043 | COMPLETED | 2heej | #43 | EXP-005 + 샘플 변이분포 확장 피처 28종 | 0.3989124897 | 미제출 | INFERENCE_VERIFIED | fold 변동성은 감소했지만 EXP-005·033 대비 OOF 하락 | [보고서](reports/exp043_xgb_sample_distribution/README.md) |
| EXP-045 | COMPLETED | 2heej | #45 | EXP-043 후보 28종 nested 그룹·개별 선택 | 0.3999980235 | 미제출 | INFERENCE_VERIFIED | EXP-043 대비 소폭 개선, EXP-005·033보다 낮아 고정 후보 2종을 후속 검증 | [보고서](reports/exp045_xgb_nested_feature_selection/README.md) |
| EXP-047 | COMPLETED | fabxoe | #47 | EXP-033 + 유전자별 최소 단백질 잔기 위치 | 0.4088132438 | 미제출 | INFERENCE_VERIFIED | Local OOF 개선·fold 변동성 감소, 위치 family 후속 검증 채택 | [보고서](reports/exp047_xgb_min_residue_position/README.md) |

## 리더보드 제출 이력

| 제출 시각 | 실험 ID | Issue | 제출 파일 | SHA-256 | Public 점수 | 순위 | 재현 상태 |
|---|---|---|---|---|---:|---:|---|
| 2026-07-30T18:20:48+09:00 | EXP-003 | #3 | `submissions/exp003_xgb_baseline.csv` (제출 ID `1506230`) | `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5` | 0.228167518 | 3 (확인 당시) | INFERENCE_VERIFIED |
| 2026-07-30T18:26:30+09:00 | EXP-005 | #5 | `submissions/exp005_xgb_mutation_features.csv` | `7bc3e64e1904d9b4007bc141dde771a39e7527172f3cd24c25c408000103183c` | 0.2987843366 | 제출 시점 1위 → 2026-07-30 23:13 KST 기준 2위 | INFERENCE_VERIFIED |
| 2026-07-30T23:28:27+09:00 | EXP-021 | #21 | `submissions/exp021_cosmic_weighted_burden_baseline.csv` (제출 ID `1506440`) | `cb75da2609631bc86310a637e2d4f2e244bfe85dac71da4f154559ebf19a07b0` | 0.2544194867 | 미확인(Dacon 제출 화면에 순위 미표시) | NOT_STARTED |
| 2026-07-30T23:56:29+09:00 | EXP-026 | #26 | `submissions/exp026_mutation_burden.csv` (제출 ID `1506469`) | `53d835335d6d23945c80acef4b70d0112f14abdaf1b5d504a63fd1ea7b16ef00` | 0.2575936484 | 미선택·개별 순위 미확인 | NOT_STARTED |
| 2026-07-31T15:50:02+09:00 | EXP-031 | #31 | `submissions/exp031_hotspot_extended.csv` (제출 ID `1506950`, attempt 5) | `54de49396b8910fd8134b5a854beed344e369a9a791c67c6c9caf0da38cec27d` | 0.3170803849 | 확인 당시 전체 2위(1위 6조 0.37149) | NOT_STARTED |

## 재현성 검증 이력

| 검증 시각 | 실험 ID | 검증자 | 소스 커밋·태그 | 데이터 일치 | 제출 재생성 | 재학습 검증 | 결과 | 증빙 |
|---|---|---|---|---|---|---|---|---|
| 2026-07-30T09:14:20Z | EXP-003 | fabxoe | `7306182669c3676e7b17024d3cf1f821131d909b` / [`exp-003-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-003-repro-v1) | SHA-256 일치 | byte-level SHA-256 일치 | 미수행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp003_xgb_baseline/comparison.json) |
| 2026-07-31T04:44:40.761953+00:00 | EXP-005 | fabxoe | `4e5533a80ef093ef4a9b76a039f5f1ee6b1cf365` / [`exp-005-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-005-repro-v1) | SHA-256 일치 | SHA-256 일치, 라벨 100%, 확률 오차 2.98e-08 | 독립 재학습으로 OOF Macro F1 동일·제출 및 checkpoint 해시 일치, fresh clone 비작성자 검증 전 | INFERENCE_VERIFIED | [comparison](reproducibility/exp005_xgb_mutation_features/comparison.json) |
| 2026-07-31T02:30:08.486372+00:00 | EXP-029 | 2heej | `1f06b4ee1bc098bd23d4c673e290da87638fb25d` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp029_xgb_log_burden_ratios/comparison.json) |
| 2026-07-31T05:05:48.760675+00:00 | EXP-043 | 2heej | `c35cbce90415ae73a66718c47759a7c7a7e851a0` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp043_xgb_sample_distribution/comparison.json) |
| 2026-07-31T04:12:34.945706+00:00 | EXP-033 | 2heej | `80a1684e0167f221e225460eaae9f0a649ab7e37` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp033_xgb_log_burden_ablation/comparison.json) |
| 2026-07-31T07:05:20.802427+00:00 | EXP-045 | 2heej | `a854d8bd626c425363c58fa7658e236220b14c3d` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp045_xgb_nested_feature_selection/comparison.json) |
| 2026-07-31T07:44:24.403725+00:00 | EXP-047 | fabxoe | `78c52694163c8b3f8e76557a93d271843b1627fa` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp047_xgb_min_residue_position/comparison.json) |

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

### [EXP-029] EXP-005 + 변이유형 구성비·log burden 피처

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #29 / issue-29-exp-log-burden-ratios
- 소스 commit: `1f06b4ee1bc098bd23d4c673e290da87638fb25d`
- 시작/종료: 2026-07-31T02:25:47.987668+00:00 /
  2026-07-31T02:30:06.305518+00:00

#### 실행

- Config: `reproducibility/exp029_xgb_log_burden_ratios/config.resolved.yaml`
- Metrics: `reports/exp029_xgb_log_burden_ratios/metrics.json`
- Report: `reports/exp029_xgb_log_burden_ratios/README.md`

#### 결과

- Fold Macro F1: 0.4050881006, 0.3992122410, 0.3830162610,
  0.3837339691, 0.4139561300
- OOF Macro F1: 0.3988980085
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp029_xgb_log_burden_ratios/metrics.json` /
  `reports/exp029_xgb_log_burden_ratios/README.md` /
  `reproducibility/exp029_xgb_log_burden_ratios/config.resolved.yaml`
- 결론: EXP-005 OOF 0.4043796587보다 0.0054816502 낮고 fold 표준편차도
  0.0086812077에서 0.0120777005로 증가해 현 피처 묶음은 미채택. 구성비와
  log burden 피처를 분리한 후속 ablation 후보로 보류함.
- 재현 메모: clean commit에서 동일 config로 재실행했으며, 저장 checkpoint
  재추론 결과 제출 SHA-256과 test 라벨이 100% 일치했다. test 확률 최대 절대
  차이는 약 2.98e-08로 허용치 1e-6 이내였다.

### [EXP-033] EXP-005 + log burden 3종 단독 ablation

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #33 / issue-33-exp-log-burden-ablation
- 소스 commit: `80a1684e0167f221e225460eaae9f0a649ab7e37`
- 시작/종료: 2026-07-31T04:07:46.390492+00:00 /
  2026-07-31T04:12:32.390885+00:00

#### 실행

- Config: `reproducibility/exp033_xgb_log_burden_ablation/config.resolved.yaml`
- Metrics: `reports/exp033_xgb_log_burden_ablation/metrics.json`
- Report: `reports/exp033_xgb_log_burden_ablation/README.md`

#### 결과

- Fold Macro F1: 0.3950183806, 0.4156681449, 0.4003213356,
  0.3925146044, 0.4195470889
- OOF Macro F1: 0.4057244634
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp033_xgb_log_burden_ablation/metrics.json` /
  `reports/exp033_xgb_log_burden_ablation/README.md` /
  `reproducibility/exp033_xgb_log_burden_ablation/`
- 결론: EXP-005보다 OOF `+0.0013448047`, EXP-029보다
  `+0.0068264548` 개선했다. 다만 EXP-005 대비 fold 표준편차가
  `+0.0022923015` 증가해 개선의 안정성을 추가 ablation으로 확인해야 한다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시, 제출 SHA-256과 test
  라벨이 일치해 `INFERENCE_VERIFIED`를 통과했다.
### [EXP-031] EXP-005 변이유형 피처 + COSMIC 보호유전자 교차 피처

- 상태: COMPLETED
- 실행자: Kangho Park
- Issue/브랜치: #31 / issue-31-cosmic-mutation-type-cross
- 소스 commit: `25c8434cfe19ecb8943aeec02e91c25f8ca38862`
- 시작/종료: 2026-07-31 (아래 attempt 1·2 모두 이 실험 세션에서 순서대로 실행)

#### 실행

EXP-005(#5)의 유전자×변이유형 희소 피처(30,697개)를 그대로 재현하고, 세
가지 구성을 순서대로 비교했다. attempt 1·2는 EXP-012(#12)의 COSMIC 보호
유전자 화이트리스트(361개)를 "보호 유전자 × 변이유형" 교차 파생변수로
추가하는 방식으로, 이미 유전자 단위에 존재하는 정보를 재집계하는 접근이었다.
두 attempt 모두 EXP-005보다 낮게 나오자, "유전자 단위 재집계는 구조적으로
새 정보가 아니다"라는 판단 아래 attempt 3에서는 개별 유전자 컬럼에 존재하지
않는 정보, 즉 **특정 코돈(hotspot) 단위 변이 여부**로 방향을 전환했다.
`scripts/explore_hotspot_numbering_consistency.py`(RUN_MODE=explore, 외부
transcript 데이터 없이 train/test 자체의 내부 일관성만 검사)로 BRAF 600,
IDH1 132, PIK3CA 545/1047 등 잘 알려진 driver hotspot 위치의 reference
amino acid가 이 패널 전체에서 문헌값과 정확히 일치·일관됨을 먼저 확인한 뒤,
검증된 9개 유전자·19개 위치만 hotspot 피처로 사용했다(KRAS/NRAS는 패널에
없어 제외). 세 attempt 모두 fold 분할과 무관하게 train/test 전체에서
계산되는 결정적 피처라 leakage 위험이 없다(PROJECT_CONTEXT.md 5절).

| 시도 | 피처 구성 | 피처 수 | Config | Metrics |
|---|---|---:|---|---|
| attempt 1 | EXP-005 전체 + 보호유전자 교차 8개(mutated/missense/synonymous/nonsense/frameshift/complex/missing count + LOF count) | 30,705 | `configs/exp031_cosmic_mutation_type_cross.yaml` | `reports/exp031_cosmic_mutation_type_cross/metrics.json` |
| attempt 2 | EXP-005 전체 + 보호유전자 LOF(nonsense+frameshift) count 1개만 | 30,698 | `configs/exp031_cosmic_lof_only_cross.yaml` | `reports/exp031_cosmic_lof_only_cross/metrics.json` |
| attempt 3 | EXP-005 전체 + 검증된 hotspot 19개 individual indicator + 총 hotspot count 1개 | 30,717 | `configs/exp031_hotspot_cross.yaml` | `reports/exp031_hotspot_cross/metrics.json` |
| attempt 4 | EXP-005 전체 + attempt 2의 LOF count 1개 + attempt 3의 hotspot 20개(결합) | 30,718 | `configs/exp031_lof_hotspot_combined.yaml` | `reports/exp031_lof_hotspot_combined/metrics.json` |
| **attempt 5(채택)** | EXP-005 전체 + hotspot 19개(attempt 3) + 신규 발굴 15개 individual indicator + 총 hotspot count 1개(34개 hotspot) | 30,732 | `configs/exp031_hotspot_extended.yaml` | `reports/exp031_hotspot_extended/metrics.json` |

attempt 5는 `scripts/explore_hotspot_candidate_mining.py`(RUN_MODE=explore)로
EXP-012 COSMIC 보호유전자 화이트리스트(361개) 전체를 대상으로 attempt 3의
검증 로직을 확장해 만들었다. 이 과정에서 중요한 **데이터 아티팩트**를
발견했다: 일부 유전자에서 특정 위치 조합이 서로 다른 환자 다수에서 정확히
동일하게(예: BRAF 600+512+548+563+566+578+603+640이 정확히 같은 39개 행에서,
TP53 16+43+136+175가 61개 행에서) 반복되는데, 이는 한 환자가 한 유전자
안에서 여러 코돈에 동시에 독립적인 점돌연변이를 얻는 실제 종양 생물학으로
설명할 수 없어 데이터 생성/전처리 과정의 인공물로 판단했다(상세는
`reports/exp012_feature_analysis/hotspot_artifact_clusters.csv`). "동일 유전자
내 위치 조합이 5회 이상 반복"을 아티팩트로 정의해 제외한 뒤(임계값은 결과를
보기 전에 고정) 482개 후보가 남았고, 이 중 개별적으로 문헌에 확실히
검증되는 10개 유전자·15개 위치만 사람이 선별해 채택했다(PIK3CA
E542K/Q546/N345, PTEN R130/R233, FBXW7 R505, AKT1 E17K, U2AF1 S34, APC
R1450/R876, POLE P286R/V411L, KIT D816, FGFR3 S249C, RAC1 P29S). HLA-A(생식계열
다형성), PABPC1/SIRPA/ATP1A1(확립된 driver 유전자 아님), TP53 확장 세트(약
50개, 생물학적 개연성은 높으나 개별 코돈 검증에 자신 없음), KMT2D/PLEC 등은
의도적으로 제외했다.

- Report: [`reports/exp031_hotspot_extended/README.md`](reports/exp031_hotspot_extended/README.md)
  (attempt 5 기준, 전체 5개 시도 요약 포함)
- 재현성 manifest: `reproducibility/exp031_cosmic_mutation_type_cross/config.resolved.yaml`,
  `reproducibility/exp031_cosmic_lof_only_cross/config.resolved.yaml`,
  `reproducibility/exp031_hotspot_cross/config.resolved.yaml`,
  `reproducibility/exp031_lof_hotspot_combined/config.resolved.yaml`,
  `reproducibility/exp031_hotspot_extended/config.resolved.yaml`

#### 결과

| 시도 | OOF Macro F1 | Accuracy | Log Loss |
|---|---:|---:|---:|
| EXP-005(부모, 비교 기준) | 0.4043796587 | 0.396549 | 1.863207 |
| attempt 1(교차 8개) | 0.3956074120 | 0.388486 | 1.875899 |
| attempt 2(LOF count만) | 0.4017847879 | 0.393969 | 1.864124 |
| attempt 3(hotspot 19개) | 0.4120236288 | 0.403322 | 1.835079 |
| attempt 4(LOF+hotspot 결합) | 0.4057616458 | 0.398645 | 1.835519 |
| **attempt 5(hotspot 34개, 팀 최고)** | **0.4135846695** | 0.406225 | 1.831068 |

- Fold Macro F1(attempt 1): 0.386807, 0.398357, 0.385085, 0.388885, 0.411211
- Fold Macro F1(attempt 2): 0.403056, 0.411966, 0.390054, 0.387770, 0.409737
- Fold Macro F1(attempt 3): 0.413077, 0.420928, 0.399671, 0.403889, 0.418962
- Fold Macro F1(attempt 4): 0.406582, 0.415506, 0.387467, 0.398288, 0.414055
- Fold Macro F1(attempt 5): 0.415084, 0.415961, 0.400686, 0.406536, 0.424850
- Public LB: **0.3170803849**(attempt 5, 제출 ID `1506950`, 2026-07-31
  15:50:02 KST, 확인 당시 전체 2위). EXP-005(0.2987843366) 대비
  +0.0182960483로 팀 최고 Public LB도 갱신했다. Local OOF 개선폭
  (+0.0092, EXP-005 대비)보다 LB 개선폭이 더 커서, hotspot 방향이 로컬
  검증뿐 아니라 실제 제출 성능에서도 유효함을 확인했다.
- 재현 상태: NOT_STARTED (제출은 완료했으나 체크포인트 추론 검증은 아직
  수행하지 않음, EXP-021/EXP-026과 동일한 순서)

클래스별로는 attempt 2에서 ACC(+0.0205), LAML(+0.0182), SARC(+0.0168),
KIPAN(+0.0124), SKCM(+0.0081) 등 일부(주로 중간 규모) 클래스가 EXP-005보다
개선됐지만, PAAD(-0.0432), LUSC(-0.0378), LIHC(-0.0245), GBMLGG(-0.0145)의
하락폭이 더 커서 전체 OOF는 소폭 낮았다. attempt 1은 거의 모든 클래스에서
attempt 2보다 나빴다(전체 OOF 기준 -0.0062p 추가 하락).

attempt 3(hotspot)은 26개 클래스 중 19개가 EXP-005보다 개선됐다. 특히
**SKCM(흑색종) +0.0443**로 가장 크게 개선됐는데, SKCM은 BRAF V600E가 대표
드라이버 변이인 암종이라 이 피처가 실제 생물학적 신호를 포착했다는 정황
증거로 볼 수 있다. UCEC(+0.0342), PAAD(+0.0279), LUAD(+0.0249),
DLBC(+0.0223), SARC(+0.0217), STES(+0.0209), ACC(+0.0178), COAD(+0.0164)도
개선됐다. 하락한 쪽은 LIHC(-0.0329), LUSC(-0.0242), TGCT(-0.0153),
BLCA(-0.0110), PCPG(-0.0101), GBMLGG(-0.0083), THCA(-0.0033) 7개로,
전체적으로 개선폭이 하락폭을 크게 앞섰다.

attempt 4(LOF+hotspot 결합)는 EXP-005보다는 근소하게 높았지만(+0.0014p)
attempt 3(hotspot 단독)보다는 뚜렷하게 낮았다(-0.0063p). attempt 3 대비
클래스별 비교에서 18개 클래스가 하락하고 8개만 개선됐으며, LUAD(-0.0446),
PAAD(-0.0433), DLBC(-0.0223)의 하락폭이 LAML(+0.0162), LGG(+0.0123) 같은
개선폭보다 컸다. 즉 attempt 2의 LOF count는 attempt 3의 hotspot 신호와
"더해지는" 관계가 아니라 오히려 그 효과를 갉아먹었다 — attempt 2가
EXP-005 단독 대비로도 net negative였던 것과 일관된 결과다.

attempt 5(hotspot 34개)는 attempt 3 대비 14개 클래스가 개선되고 12개가
하락했다. PCPG(+0.0229), CESC(+0.0219), UCEC(+0.0209), THYM(+0.0201),
LIHC(+0.0168), PRAD(+0.0154), KIPAN(+0.0153)이 크게 개선된 반면
PAAD(-0.0370), BLCA(-0.0247), DLBC(-0.0156), COAD(-0.0139), OV(-0.0100)가
하락했다. 개선폭 합이 하락폭 합보다 커서 전체 OOF가 attempt 3보다
+0.0016p 더 높아졌다.

#### 산출물과 결론

- Metrics/Reproduction: 위 표의 시도별 경로
- 코드: `src/open_cancer/cosmic_mutation_features.py`
  (`build_cosmic_mutation_features`, `build_cosmic_cross_matrix`),
  `src/open_cancer/hotspot_features.py`
  (`build_hotspot_augmented_features`, `build_hotspot_matrix`, `KNOWN_HOTSPOTS`,
  `ADDITIONAL_HOTSPOTS`, `EXTENDED_HOTSPOTS`),
  `src/open_cancer/combined_mutation_features.py` (`build_lof_hotspot_features`),
  `scripts/run_exp031_cosmic_mutation_type_cross.py`,
  `scripts/run_exp031_cosmic_lof_only_cross.py`,
  `scripts/run_exp031_hotspot_cross.py`,
  `scripts/run_exp031_lof_hotspot_combined.py`,
  `scripts/run_exp031_hotspot_extended.py`,
  `scripts/explore_hotspot_numbering_consistency.py`(RUN_MODE=explore, 검증용),
  `scripts/explore_hotspot_candidate_mining.py`(RUN_MODE=explore, 후보 발굴·
  아티팩트 클러스터 탐지)
- 결론: **attempt 5(hotspot 34개) 최종 채택 — 팀 최고 Local·Public LB 기록
  갱신** (Local: EXP-005 대비 +0.0092p, attempt 3 대비 +0.0016p; Public LB:
  EXP-005 대비 +0.0182960483). attempt 1·2("COSMIC 보호 유전자 정보를
  유전자 단위로 재집계")는 EXP-005를 넘지 못했고, attempt 3·5("개별
  유전자 컬럼에는 없는 코돈 단위 정보를 추가")는 넘었다. attempt 4는
  attempt 2와 3을 결합하면 더 나아질지 확인했지만 오히려 attempt 3보다
  낮아, 두 신호가 단순히 합산되지 않으며 LOF count 쪽이 순손실 요인임을
  재확인했다. attempt 5는 "새 정보 추가"라는 같은 원칙을 화이트리스트
  361개 전체로 확장해 재확인한 결과로, "정보가 이미 유전자×변이유형
  단위에 존재해 재집계는 net negative, 코돈 단위의 진짜 새 정보만 net
  positive"라는 가설을 다시 한번 뒷받침한다. Local과 Public LB 모두에서
  일관되게 개선돼, hotspot 아티팩트 조사(선택 메모 참고)로 확인한 CV
  신뢰성과도 부합하는 결과다. 리더보드 제출은 완료했으나 체크포인트
  추론 검증(`INFERENCE_VERIFIED`)은 아직 수행하지 않았다.

#### 선택 메모

- COSMIC CGC v104 화이트리스트와 EXP-012 산출물(`protected_genes_final.csv`)은
  라이선스 확인 전까지 Git 미포함 — `reproducibility/exp031_cosmic_*/config.resolved.yaml`의
  `features.protect_gene_whitelist_sha256`으로 사용 파일을 고정했다.
- **hotspot 좌표 검증의 한계**: `KNOWN_HOTSPOTS`(9개 유전자, 19개 위치)와
  `ADDITIONAL_HOTSPOTS`(10개 유전자, 15개 위치)는 외부 정준(canonical)
  transcript 서열과 대조한 것이 아니라, (1) 이 데이터셋 자체의 train+test
  전체에서 reference amino acid가 내부적으로 일관되는지, (2) 그 값이
  문헌에 알려진 hotspot residue와 일치하는지만 확인한 것이다. 즉 "이
  데이터가 자기모순이 없고 통용되는 임상 넘버링과 결과가 같다"는 정황
  증거이지, 이 패널이 실제로 어떤 transcript를 썼는지 확인된 것은 아니다.
  UniProt/RefSeq 정준 서열(FASTA)과 검증된 hotspot 좌표표(cancerhotspots.org
  등, 라이선스 확인 필요)가 확보되면 검증 범위를 넓힐 수 있다.
- **데이터 아티팩트 발견 및 CV 영향 조사** (attempt 5 과정에서 발견,
  `scripts/explore_duplicate_row_investigation.py`로 후속 검증): BRAF/RXRA/
  CD209/MUC1/TP53 등 일부 유전자에서 특정 위치 조합이 서로 다른 환자들에게서
  정확히 동일하게 반복 등장한다(`reports/exp012_feature_analysis/hotspot_artifact_clusters.csv`,
  131개 클러스터). 예: BRAF 600+512+548+563+566+578+603+640이 39개 행에서,
  TP53 16+43+136+175가 61개 행에서 항상 함께 나타남. 실제 종양이 한 유전자
  안에서 이렇게 많은 코돈에 동시에 독립적인 점돌연변이를 얻을 가능성은
  매우 낮아 인공적 패턴으로 판단했다. 이 발견이 "지금까지의 모든 OOF
  Macro F1 비교(EXP-003~EXP-031)의 CV 신뢰도 자체를 훼손하는가"를 다음 4가지로
  확인했다.
  1. **train/test 분포**: 위 5개 클러스터(BRAF, TP53 5종, RXRA, CD209, MUC1)
     전부 **test에만 존재하고 train에는 0건**이다. 5-fold CV는 train만으로
     계산되므로 이 현상이 CV를 직접 왜곡할 수 없다.
  2. **행 단위 동일성**: BRAF 클러스터의 test 39개 행은 전체 4,384개 유전자
     컬럼 기준으로 서로 완전히 다른 39개의 서로 다른 패턴이었다(같은 환자
     복제가 아니라, 이 유전자 하나에서만 특이한 패턴을 공유하는 별개
     환자들). train의 어떤 행과도 일치하지 않았다.
  3. **현재 hotspot 피처에 대한 실질적 영향**: `KNOWN_HOTSPOTS`/
     `EXTENDED_HOTSPOTS`는 검증된 개별 위치(예: BRAF 600, TP53 175)만
     인코딩하고 클러스터의 동반 위치(512, 16, 43 등)는 애초에 포함하지
     않으므로, 이 환자들은 여전히 "진짜" hotspot 보유자로 올바르게
     표시된다 — 잘못된 신호를 만들지 않는다.
  4. **별개로 발견한 전체 행(4,384개 컬럼 전부) 완전 중복**: train
     6,201개 중 1,016개(16.4%)가 451개 중복 그룹에 속했다. 이 중 447개
     그룹은 SUBCLASS가 서로 다른 그룹이라(변이가 거의 없는 희소 프로필이
     우연히 겹친 것, ~99% WT라는 데이터 특성상 자연스러움) leakage와
     무관하다. **완전 중복 + 같은 SUBCLASS인 그룹은 4개뿐**(LAML 3개,
     KIPAN 1개, 총 11개 행)이며 이 중 3개가 여러 fold에 걸쳐 분산돼 있어
     이론적으로는 미세한 CV 낙관 편향 요인이지만, 전체 6,201개 대비
     11개 수준이라 소수점 4자리 Macro F1 비교에 미치는 실질적 영향은
     무시할 만하다고 판단했다. train-test 간에도 229개 완전 일치 패턴이
     있었으나 마찬가지로 대부분 희소 프로필이며, 이를 직접 활용(test ID를
     train 라벨에 매칭)하지 않으므로 우리 파이프라인이 이를 부정하게
     활용하는 것은 아니다.
  - **결론**: 이 조사로 EXP-003~EXP-031의 OOF Macro F1 비교는 두 현상
    모두로부터 실질적으로 훼손되지 않았다고 판단한다. test-only 위치
    클러스터의 정확한 발생 원인(생성/전처리 과정의 특이 패턴으로 추정)은
    여전히 밝혀지지 않았으므로 참고 사항으로 남긴다.
- HLA-A(생식계열 다형성), PABPC1/SIRPA/ATP1A1(확립된 point-mutation driver
  유전자 아님)은 필터를 통과했지만 의도적으로 제외했다. TP53 확장 세트
  (약 50개 코돈)는 생물학적 개연성은 높지만 개별 검증에 자신이 없어 이번
  attempt 5에는 포함하지 않았다.
- KRAS/NRAS hotspot(G12/G13/Q61)은 두 유전자 모두 이 패널의 컬럼에 없어
  (EXP-012에서 이미 확인된 한계) 포함하지 못했다.
- **리더보드 제출 완료**: 2026-07-31 15:50:02 KST, 제출 ID `1506950`,
  Public LB `0.3170803849`(EXP-005 대비 +0.0182960483, 확인 당시 전체
  2위). 위 CV 유효성 조사 결과를 신뢰해 제출을 진행했고, Local과 LB
  모두 일관되게 개선돼 판단이 맞았음을 확인했다.
- 다음 행동 후보: (a) attempt 5의 `INFERENCE_VERIFIED` 체크포인트 검증
  (EXP-003/EXP-005 방식)을 진행해 재현성 계약을 사후 충족, (b) 외부 정준
  서열과 검증된 hotspot 좌표표를 확보해 TP53 확장 세트와 나머지 protect
  유전자로 검증 범위를 넓히는 것 검토(낮은 우선순위, 개선폭 체감 곡선이
  이미 뚜렷함), (c) attempt 2(LOF count)는 단독·결합(attempt 4) 모두
  net negative로 재확인됐으므로 이 방향은 더 탐색하지 않는다.

### [EXP-043] EXP-005 + 샘플 변이분포 확장 피처

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #43 / issue-43-exp-sample-mutation-distribution
- 소스 commit: `c35cbce90415ae73a66718c47759a7c7a7e851a0`
- 시작/종료: 2026-07-31T05:01:31.130770+00:00 /
  2026-07-31T05:05:46.708076+00:00

#### 실행

- Config: `reproducibility/exp043_xgb_sample_distribution/config.resolved.yaml`
- Metrics: `reports/exp043_xgb_sample_distribution/metrics.json`
- Report: `reports/exp043_xgb_sample_distribution/README.md`

#### 결과

- Fold Macro F1: 0.3974793185, 0.4002075346, 0.3939432879,
  0.3934503403, 0.4044457914
- OOF Macro F1: 0.3989124897
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp043_xgb_sample_distribution/metrics.json` /
  `reports/exp043_xgb_sample_distribution/README.md` /
  `reproducibility/exp043_xgb_sample_distribution/`
- 결론: EXP-033보다 OOF `-0.0068119737`, EXP-005보다
  `-0.0054671690` 하락했다. fold 표준편차는 `0.0040939951`로 낮아졌지만,
  확장 피처 28개를 전부 사용하는 구성은 미채택하고 fold-train 내부의 안정성
  기반 피처 선택 실험으로 넘긴다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시, 제출 SHA-256과 test
  라벨이 일치했고 확률 최대 절대 차이는 약 2.98e-08로 허용치 이내여서
  `INFERENCE_VERIFIED`를 통과했다.

### [EXP-045] EXP-043 파생변수 단계별 선택

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #45 / issue-45-exp-nested-feature-selection
- 소스 commit: `a854d8bd626c425363c58fa7658e236220b14c3d`
- 시작/종료: 2026-07-31T06:39:19.308528+00:00 /
  2026-07-31T07:05:20.802427+00:00

#### 실행

- Config: `reproducibility/exp045_xgb_nested_feature_selection/config.resolved.yaml`
- Metrics: `reports/exp045_xgb_nested_feature_selection/metrics.json`
- Report: `reports/exp045_xgb_nested_feature_selection/README.md`

#### 결과

- Fold Macro F1: 0.3988827522, 0.3974133932, 0.3915761757,
  0.3915046058, 0.4142175906
- OOF Macro F1: 0.3999980235
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp045_xgb_nested_feature_selection/metrics.json` /
  `reports/exp045_xgb_nested_feature_selection/README.md` /
  `reproducibility/exp045_xgb_nested_feature_selection/`
- 결론: EXP-043보다 OOF `+0.0010855338` 개선했지만 EXP-005보다
  `-0.0043816352`, EXP-033보다 `-0.0057264399` 낮았다. 모든 outer fold에서
  반복 선택되고 permutation 평균 하락 폭도 비교적 컸던
  `sample__synonymous_gene_count`와
  `sample__variants_per_mutated_gene_mean`을 별도 고정 피처 후속 실험 후보로
  남긴다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시, 제출 SHA-256과 test
  라벨이 일치해 `INFERENCE_VERIFIED`를 통과했다.

### [EXP-047] Feature Factory + 유전자별 최소 단백질 잔기 위치

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #47 / issue-47-exp-min-residue-position
- 소스 commit: `78c52694163c8b3f8e76557a93d271843b1627fa`
- 시작/종료: 2026-07-31T07:32:46.567840+00:00 /
  2026-07-31T07:44:21.394289+00:00

#### 실행

- Config: `reproducibility/exp047_xgb_min_residue_position/config.resolved.yaml`
- Metrics: `reports/exp047_xgb_min_residue_position/metrics.json`
- Report: `reports/exp047_xgb_min_residue_position/README.md`

#### 결과

- Fold Macro F1: 0.4113274860, 0.4106448428, 0.3941926672,
  0.4057632107, 0.4202061182
- OOF Macro F1: 0.4088132438
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp047_xgb_min_residue_position/metrics.json` /
  `reports/exp047_xgb_min_residue_position/README.md` /
  `reproducibility/exp047_xgb_min_residue_position/`
- 결론: EXP-033보다 OOF Macro F1이 `+0.0030887804` 개선되고 fold 표준편차가
  `-0.0024671436` 감소해 유전자별 최소 잔기 위치를 후속 위치 family 후보로
  채택한다. 저장 checkpoint 재추론은 제출 SHA-256과 라벨 100% 일치를 확인했다.
