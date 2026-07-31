# 암종 분류 실험 기록

> 실제로 실행하거나 제출한 내용만 기록합니다.
> 작성 규칙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)를 따릅니다.
> 긴 개념 설명과 분석은 [reports 작성 안내](reports/README.md)에 따라 실험별
> `README.md`에 기록하고 이 파일에는 링크만 둡니다.

## 현재 상태

- 실제 실험 수: 12
- 실험 ID 규칙: GitHub Experiment Issue #N → EXP-NNN
- 다음 실험: Experiment Issue를 먼저 생성하고 발급된 번호를 사용
- 최고 Local OOF Macro F1: 0.4101842357 (`EXP-058`)
- 최고 Public LB Macro F1: 0.2987843366 (`EXP-005`)
- 최고 재현 검증 모델: `EXP-058` (`INFERENCE_VERIFIED`)
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
| EXP-043 | COMPLETED | 2heej | #43 | EXP-005 + 샘플 변이분포 확장 피처 28종 | 0.3989124897 | 미제출 | INFERENCE_VERIFIED | fold 변동성은 감소했지만 EXP-005·033 대비 OOF 하락 | [보고서](reports/exp043_xgb_sample_distribution/README.md) |
| EXP-045 | COMPLETED | 2heej | #45 | EXP-043 후보 28종 nested 그룹·개별 선택 | 0.3999980235 | 미제출 | INFERENCE_VERIFIED | EXP-043 대비 소폭 개선, EXP-005·033보다 낮아 고정 후보 2종을 후속 검증 | [보고서](reports/exp045_xgb_nested_feature_selection/README.md) |
| EXP-047 | COMPLETED | fabxoe | #47 | EXP-033 + 유전자별 최소 단백질 잔기 위치 | 0.4088132438 | 미제출 | INFERENCE_VERIFIED | Local OOF 개선·fold 변동성 감소, 위치 family 후속 검증 채택 | [보고서](reports/exp047_xgb_min_residue_position/README.md) |
| EXP-052 | COMPLETED | Kangho-Park | #52 | EXP-047 + Feature Factory family 7(co-mutation, 문헌 근거 유전자 쌍 3개) | 0.4095069739 | 미제출 | INFERENCE_VERIFIED | OOF 소폭 개선·fold 표준편차 대폭 감소로 채택, pair 확장 검토 | [보고서](reports/exp052_hotspot_cooccurrence/README.md) |
| EXP-058 | COMPLETED | Kangho-Park | #58 | EXP-052에서 SHAP 근거로 APC/CTNNB1 제거(쌍 3개→2개) | 0.4101842357 | 미제출 | INFERENCE_VERIFIED | 채택(팀 최고), COAD 개선으로 SHAP 가설 직접 검증 | [보고서](reports/exp058_cooccurrence_pair_ablation/README.md) |

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
| 2026-07-31T04:44:40.761953+00:00 | EXP-005 | fabxoe | `4e5533a80ef093ef4a9b76a039f5f1ee6b1cf365` / [`exp-005-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-005-repro-v1) | SHA-256 일치 | SHA-256 일치, 라벨 100%, 확률 오차 2.98e-08 | 독립 재학습으로 OOF Macro F1 동일·제출 및 checkpoint 해시 일치, fresh clone 비작성자 검증 전 | INFERENCE_VERIFIED | [comparison](reproducibility/exp005_xgb_mutation_features/comparison.json) |
| 2026-07-31T02:30:08.486372+00:00 | EXP-029 | 2heej | `1f06b4ee1bc098bd23d4c673e290da87638fb25d` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp029_xgb_log_burden_ratios/comparison.json) |
| 2026-07-31T05:05:48.760675+00:00 | EXP-043 | 2heej | `c35cbce90415ae73a66718c47759a7c7a7e851a0` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp043_xgb_sample_distribution/comparison.json) |
| 2026-07-31T04:12:34.945706+00:00 | EXP-033 | 2heej | `80a1684e0167f221e225460eaae9f0a649ab7e37` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp033_xgb_log_burden_ablation/comparison.json) |
| 2026-07-31T07:05:20.802427+00:00 | EXP-045 | 2heej | `a854d8bd626c425363c58fa7658e236220b14c3d` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100% | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp045_xgb_nested_feature_selection/comparison.json) |
| 2026-07-31T07:44:24.403725+00:00 | EXP-047 | fabxoe | `78c52694163c8b3f8e76557a93d271843b1627fa` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp047_xgb_min_residue_position/comparison.json) |
| 2026-07-31T09:24:31.209567+00:00 | EXP-052 | Kangho-Park | `6865fd5accf4fbf7090dc39ecc4a27f9b611adf7` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp052_hotspot_cooccurrence/comparison.json) |
| 2026-07-31T10:18:14.298161+00:00 | EXP-058 | Kangho-Park | `45b353ce4073e4a9bad0c0866f4cb84ac5a53fe7` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp058_cooccurrence_pair_ablation/comparison.json) |

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

### [EXP-052] Feature Factory + Hotspot 연관 유전자 Co-mutation

- 상태: COMPLETED
- 실행자: Kangho Park
- Issue/브랜치: #52 / issue-52-hotspot-cooccurrence
- 소스 commit: `6865fd5accf4fbf7090dc39ecc4a27f9b611adf7`
- 시작/종료: 2026-07-31 (단일 실행)

#### 실행

Feature Factory에 family 7(co-mutation)을 새로 구현해 EXP-047 피처에
문헌 근거 유전자 쌍 3개(IDH1/IDH2 상호배타성, APC/CTNNB1 상호배타성,
PIK3CA/PTEN 동시발생)의 co-mutation indicator 4개(쌍별 3개 + 총합 1개)를
추가했다. 쌍 목록은 EXP-031(#31)의 hotspot 관련 유전자 중 문헌으로 확인된
것만 고정 사용했으며, 이 데이터의 빈도로 마이닝하거나 fold별로 다시
선정하지 않았다(외부 지식 고정, target/fold fitting 없음).

- Config: `reproducibility/exp052_hotspot_cooccurrence/config.resolved.yaml`
- Metrics: `reports/exp052_hotspot_cooccurrence/metrics.json`
- Report: `reports/exp052_hotspot_cooccurrence/README.md`

#### 결과

- Fold Macro F1: 0.4106308554, 0.4136261798, 0.4002611603,
  0.4051305971, 0.4138423476
- OOF Macro F1: 0.4095069739
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp052_hotspot_cooccurrence/metrics.json` /
  `reports/exp052_hotspot_cooccurrence/README.md` /
  `reproducibility/exp052_hotspot_cooccurrence/`
- 결론: EXP-047 대비 OOF Macro F1이 `+0.0006937301`로 소폭 개선됐지만
  fold 표준편차는 `0.0085063656 → 0.0052610612`(약 38% 감소)로 뚜렷하게
  좋아졌다. 26개 클래스 중 17개 개선(PAAD +0.0405, LUAD +0.0309 등), 9개
  하락(BLCA -0.0425 등)으로 순개선. IDH1/IDH2 co-mutation이 문헌과 달리
  train 3건·test 2건 관측됐으나 극소수라 상호배타성 전제를 무효화하지
  않는다. APC/CTNNB1은 원래 대장암 한정 상호배타성 지식인데 26개 암종
  전체에 동일 적용해 완전 배타적이지 않았다(train 33건·test 44건) — 암종별
  조건부 적용이 다음 개선 후보다. 저장 checkpoint 재추론으로 제출
  SHA-256과 라벨 100% 일치를 확인해 `INFERENCE_VERIFIED`로 자동 승격됐다.
  아직 리더보드에는 제출하지 않았다.

### [EXP-058] Co-mutation Pair Ablation — SHAP 근거로 APC/CTNNB1 제거

- 상태: COMPLETED
- 실행자: Kangho Park
- Issue/브랜치: #58 / issue-58-cooccurrence-pair-ablation
- 소스 commit: `45b353ce4073e4a9bad0c0866f4cb84ac5a53fe7`
- 시작/종료: 2026-07-31 (단일 실행)

#### 실행

EXP-052(#52)의 "암종별 조건부 적용" 후속 계획은 test에서 알 수 없는
SUBCLASS를 게이팅 조건으로 써야 해서 target leakage로 구현 전에 폐기했다.
대신 EXP-052의 저장 checkpoint에 TreeSHAP(`xgboost.Booster.predict(pred_contribs=True)`)을
적용해, 각 co-mutation 피처가 활성화된 샘플에서 26개 클래스별 평균 기여도를
계산했다. PIK3CA/PTEN은 UCEC가 1/26위(0.042, 나머지 평균 -0.006)로 트리가
이미 정확히 학습한 반면, APC/CTNNB1은 COAD가 26/26위(꼴찌)에 기여도가
음수(-0.005)로 가설과 반대였다. IDH1/IDH2는 활성 샘플 3건뿐이라 판단
보류. 이 증거에 따라 APC/CTNNB1만 제거하고 나머지 2개 쌍은 유지하는
config 변경만으로 재실행했다(Feature Factory 코드 변경 없음).

- Config: `reproducibility/exp058_cooccurrence_pair_ablation/config.resolved.yaml`
- Metrics: `reports/exp058_cooccurrence_pair_ablation/metrics.json`
- Report: `reports/exp058_cooccurrence_pair_ablation/README.md`

#### 결과

- Fold Macro F1: 0.4100673176, 0.4143098302, 0.4046742555,
  0.4023218460, 0.4160092186
- OOF Macro F1: 0.4101842357
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp058_cooccurrence_pair_ablation/metrics.json` /
  `reports/exp058_cooccurrence_pair_ablation/README.md` /
  `reproducibility/exp058_cooccurrence_pair_ablation/`
- 결론: EXP-052 대비 OOF Macro F1이 `+0.0006772617`(EXP-047 대비 누적
  `+0.0013709918`) 추가 개선돼 팀 최고 기록을 갱신했다. 26개 클래스 중
  13개 개선(BLCA +0.0265, LUSC +0.0197, DLBC +0.0196 등), 13개 하락(PAAD
  -0.0230, THYM -0.0204 등)이었다. 가장 중요한 확인은 **COAD가 SHAP
  예측대로 실제 개선**됐다는 점(0.7126 → 0.7187, `+0.0061`) — APC/CTNNB1
  제거가 COAD 예측에 도움이 될 것이라는 가설이 실행 결과로 직접 검증됐다.
  저장 checkpoint 재추론으로 제출 SHA-256과 라벨 100% 일치를 확인해
  `INFERENCE_VERIFIED`로 자동 승격됐다. 아직 리더보드에는 제출하지 않았다.
