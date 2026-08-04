# 암종 분류 실험 기록

> 실제로 실행하거나 제출한 내용만 기록합니다.
> 작성 규칙은 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)를 따릅니다.
> 긴 개념 설명과 분석은 [reports 작성 안내](reports/README.md)에 따라 실험별
> `README.md`에 기록하고 이 파일에는 링크만 둡니다.

## 현재 상태

- 실제 실험 수: 79
- 실험 ID 규칙: GitHub Experiment Issue #N → EXP-NNN
- 다음 실험: Experiment Issue를 먼저 생성하고 발급된 번호를 사용
- 최고 Local OOF Macro F1: 0.4351340093 (`EXP-334`)
- 최고 Public LB Macro F1: 0.323243525 (`EXP-223`)
- 최고 재현 검증 모델: `EXP-334` (`INFERENCE_VERIFIED`)
- 최종 갱신일: 2026-08-04

## 실험 요약

| ID | 상태 | 실행자 | Issue | 모델·메모(선택) | OOF Macro F1 | Public LB | 재현 상태 | 판단 | 상세 기록 |
|---|---|---|---|---|---:|---:|---|---|---|
| EXP-003 | COMPLETED | fabxoe | #3 | XGBoost mutation-presence baseline | 0.334930 | 0.228167518 | INFERENCE_VERIFIED | 비교 기준 | [보고서](reports/exp003_xgb_baseline/README.md) |
| EXP-005 | COMPLETED | 2heej | #5 | XGBoost + 유전자×변이유형 희소 피처 | 0.4043796587000222 | 0.2987843366 | INFERENCE_VERIFIED | 제출·체크포인트 재생성 및 Release 보관 완료 | [보고서](reports/exp005_xgb_mutation_features/README.md) |
| EXP-012 | COMPLETED | Kangho-Park | #12 | COSMIC 보호 유전자 기반 feature 보호 전략 분석 (모델 학습 없음) | N/A (분석 전용) | 미제출 | NOT_STARTED | 채택 | [보고서](reports/exp012_cosmic_protected_genes/README.md) |
| EXP-021 | COMPLETED | Kangho-Park | #21 | XGBoost, 전체 4,384 피처 + COSMIC 가중 burden 파생 컬럼 1개 (attempt 3, 4개 시도 중 최고) | 0.349410 | 0.2544194867 | NOT_STARTED | 채택(EXP-003 대비 개선, EXP-005엔 못 미침) | [보고서](reports/exp021_cosmic_weighted_burden_baseline/README.md) |
| EXP-026 | COMPLETED | fabxoe | #26 | XGBoost mutation-presence + mutated-gene count | 0.3817476632 | 0.2575936484 | NOT_STARTED | EXP-003 대비 개선, EXP-005보다 낮음 | [보고서](reports/exp026_mutation_burden/README.md) |
| EXP-029 | COMPLETED | 2heej | #29 | EXP-005 + 변이유형 구성비·log burden 피처 | 0.3988980085 | 미제출 | INFERENCE_VERIFIED | EXP-005 대비 OOF 하락·fold 변동성 증가로 현 구성 미채택 | [보고서](reports/exp029_xgb_log_burden_ratios/README.md) |
| EXP-030 | COMPLETED | Gomin-art | #30 | XGBoost + 유전자×변이유형 희소 피처·샘플별 변이 수 | 0.4105408554 | 0.2993610323 | INFERENCE_VERIFIED | EXP-005 Public 소폭 개선·EXP-031보다 낮음 | [보고서](reports/exp030_sparse_variant_xgb/README.md) |
| EXP-033 | COMPLETED | 2heej | #33 | EXP-005 + log burden 3종 단독 ablation | 0.4057244634 | 미제출 | INFERENCE_VERIFIED | EXP-005 대비 소폭 개선·추가 분리 검증 필요 | [보고서](reports/exp033_xgb_log_burden_ablation/README.md) |
| EXP-031 | COMPLETED | Kangho-Park | #31 | EXP-005 변이유형 피처 + 알려진 cancer hotspot 위치 피처 (attempt 5, hotspot 19→34개 확장이 팀 최고) | 0.4135846695 | 0.3170803849 | FAILED | attempt 5 채택; 원 실행 checkpoint 미보관으로 독립 재학습이 원 제출과 불일치 | [보고서](reports/exp031_hotspot_extended/README.md) |
| EXP-043 | COMPLETED | 2heej | #43 | EXP-005 + 샘플 변이분포 확장 피처 28종 | 0.3989124897 | 미제출 | INFERENCE_VERIFIED | fold 변동성은 감소했지만 EXP-005·033 대비 OOF 하락 | [보고서](reports/exp043_xgb_sample_distribution/README.md) |
| EXP-045 | COMPLETED | 2heej | #45 | EXP-043 후보 28종 nested 그룹·개별 선택 | 0.3999980235 | 미제출 | INFERENCE_VERIFIED | EXP-043 대비 소폭 개선, EXP-005·033보다 낮아 고정 후보 2종을 후속 검증 | [보고서](reports/exp045_xgb_nested_feature_selection/README.md) |
| EXP-047 | COMPLETED | fabxoe | #47 | EXP-033 + 유전자별 최소 단백질 잔기 위치 | 0.4088132438 | 미제출 | INFERENCE_VERIFIED | Local OOF 개선·fold 변동성 감소, 위치 family 후속 검증 채택 | [보고서](reports/exp047_xgb_min_residue_position/README.md) |
| EXP-050 | COMPLETED | 2heej | #50 | EXP-005 + EXP-045 반복 선택 파생변수 2종 고정 | 0.4014204930 | 미제출 | INFERENCE_VERIFIED | EXP-043·045보다 높지만 EXP-005보다 낮아 미채택 | [보고서](reports/exp050_xgb_fixed_two_distribution_features/README.md) |
| EXP-052 | COMPLETED | Kangho-Park | #52 | EXP-047 + Feature Factory family 7(co-mutation, 문헌 근거 유전자 쌍 3개) | 0.4095069739 | 미제출 | INFERENCE_VERIFIED | OOF 소폭 개선·fold 표준편차 감소로 채택, pair 확장 검토 | [보고서](reports/exp052_hotspot_cooccurrence/README.md) |
| EXP-058 | COMPLETED | Kangho-Park | #58 | EXP-052에서 SHAP 근거로 APC/CTNNB1 제거(쌍 3개→2개) | 0.4101842357 | 0.3044672015 | INFERENCE_VERIFIED | EXP-052 대비 Local 개선·Public은 EXP-031보다 낮음 | [보고서](reports/exp058_cooccurrence_pair_ablation/README.md) |
| EXP-065 | COMPLETED | fabxoe | #65 | EXP-047 + complex-token residue 위치 제외 | 0.4108923084 | 미제출 | INFERENCE_VERIFIED | OOF 개선·fold 변동성 소폭 감소로 채택 후보 | [보고서](reports/exp065_xgb_residue_exclude_complex/README.md) |
| EXP-063 | COMPLETED | fabxoe | #63 | EXP-047 + residue-position 관측 indicator | 0.4130329102 | 미제출 | INFERENCE_VERIFIED | OOF 개선은 유효하나 Issue #80에서 mutation-presence 완전 중복으로 확인, 결측 신호 해석 기각 | [보고서](reports/exp063_xgb_residue_indicator/README.md) |
| EXP-067 | COMPLETED | fabxoe | #67 | EXP-047 + residue 위치 폭 100 coarse-bin | 0.4124014867 | 미제출 | INFERENCE_VERIFIED | OOF 개선·fold 변동성 감소로 채택 후보 | [보고서](reports/exp067_xgb_residue_coarse_bin/README.md) |
| EXP-069 | COMPLETED | fabxoe | #69 | EXP-047의 min residue 위치를 max로 교체 | 0.4131007993 | 미제출 | INFERENCE_VERIFIED | OOF 개선·fold 변동성 감소로 채택 후보 | [보고서](reports/exp069_xgb_max_residue_position/README.md) |
| EXP-075 | COMPLETED | fabxoe | #75 | EXP-067·069 확률의 사전 고정 0.5/0.5 평균 | 0.4157910775 | 0.31125491 | INFERENCE_VERIFIED | 두 부모 대비 OOF·Log Loss 개선, Public은 EXP-031 미달 | [보고서](reports/exp075_residue_probability_blend/README.md) |
| EXP-078 | COMPLETED | fabxoe | #78 | EXP-069 max residue-position + 관측 indicator | 0.4110815504 | 미제출 | INFERENCE_VERIFIED | OOF 하락·fold 변동성 악화 및 Issue #80 중복 확인으로 기각, EXP-069 max+zero 동결 | [보고서](reports/exp078_xgb_max_residue_indicator/README.md) |
| EXP-085 | COMPLETED | fabxoe | #85 | EXP-005 + reference-aware 고정 문헌 hotspot 34개 | 0.4125795545 | 0.3103760308 | INFERENCE_VERIFIED | clean hotspot 복구·Public은 EXP-031보다 낮음 | [보고서](reports/exp085_hotspot_clean/README.md) |
| EXP-093 | COMPLETED | 2heej | #93 | EXP-005 + max residue-position + clean hotspot 34개 | 0.4157606623 | 미제출 | INFERENCE_VERIFIED | 부모 OOF는 개선했지만 fold 변동성 기준 실패로 조합 동결 보류 | [보고서](reports/exp093_mutation_position_hotspot/README.md) |
| EXP-094 | COMPLETED | fabxoe | #94 | EXP-005 + EXP-069 max residue position + EXP-085 고정 hotspot | 0.4168865739 | 0.311853163 | INFERENCE_VERIFIED | 채택·Feature Spec v1 동결; Public은 EXP-031·096 미달 | [보고서](reports/exp094_feature_spec_v1/README.md) |
| EXP-106 | COMPLETED | fabxoe | #106 | EXP-094 + fold-train recurrent exact-token | 0.4147478922 | 미제출 | INFERENCE_VERIFIED | 성능 후보 미채택·OOF/test 확률은 다양성 비교용 보존 | [보고서](reports/exp106_recurrent_exact_token/README.md) |
| EXP-107 | COMPLETED | fabxoe | #107 | EXP-094 + amino-acid 물성 변화 카운트 4개 | 0.4131379001 | 미제출 | INFERENCE_VERIFIED | 성능 후보 미채택·v2-diversity 관찰 후보로 확률 보존 | [보고서](reports/exp107_amino_acid_change/README.md) |
| EXP-109 | COMPLETED | fabxoe | #109 | EXP-094 + complex morphology·spectrum 요약 8개 | 0.4135182559 | 미제출 | INFERENCE_VERIFIED | 성능 후보 미채택·fold 안정성 및 diversity 관찰 후보 | [보고서](reports/exp109_complex_morphology/README.md) |
| EXP-110 | COMPLETED | fabxoe | #110 | EXP-094 + fold-train 유전자 빈도 tier spectrum 40개 | 0.3963504903 | 미제출 | INFERENCE_VERIFIED | 성능·초기 blend 미채택, 저우선순위 stacking 자산 | [보고서](reports/exp110_frequency_tier_spectrum/README.md) |
| EXP-096 | COMPLETED | fabxoe | #96 | EXP-094 + 고정 canonical pathway 변이·LoF 유전자 수 20개 | 0.4181153080 | 0.3169056749 | INFERENCE_VERIFIED | 재현 가능한 Public 최고·EXP-031 대비 -0.0001747100 | [보고서](reports/exp096_fixed_pathway_burden/README.md) |
| EXP-123 | COMPLETED | fabxoe | #123 | 동결 Feature Spec v1 + 희소 Logistic Regression | 0.3763324825 | 미제출 | INFERENCE_VERIFIED | 단독·wildcard 품질 gate 실패, 다양성만 통과해 stacking 후보 미채택 | [보고서](reports/exp123_sparse_logistic_v1/README.md) |
| EXP-125 | COMPLETED | fabxoe | #125 | 동결 Feature Spec v1 + LightGBM | 0.4189078364 | 0.3075810937 | INFERENCE_VERIFIED | Local gate 통과, Public은 EXP-031·096 미달 | [보고서](reports/exp125_lightgbm_v1/README.md) |
| EXP-127 | COMPLETED | fabxoe | #127 | 동결 Feature Spec v1 + CatBoost GPU | 0.4194572294 | 0.3014741179 | INFERENCE_VERIFIED | Local 최고지만 Public 하락, 단독 후보 제외·diversity 자산 | [보고서](reports/exp127_catboost_v1/README.md) |
| EXP-131 | COMPLETED | fabxoe | #131 | EXP-127 CatBoost v1 extended training | 0.4222392962 | 미제출 | INFERENCE_VERIFIED | OOF는 개선했지만 fold·Log Loss 악화, 추가 CatBoost iteration 확장 중단 | [보고서](reports/exp131_catboost_v1_extended/README.md) |
| EXP-135 | COMPLETED | fabxoe | #135 | EXP-094 + EXP-125 fixed 0.5/0.5 probability blend | 0.4201772665 | 0.3166527939 | INFERENCE_VERIFIED | 재현 가능한 Public 2위·EXP-096 대비 -0.0002528810; 추가 blend 탐색은 보류 | [보고서](reports/exp135_fixed_probability_blend/README.md) |
| EXP-137 | COMPLETED | fabxoe | #137 | EXP-094 + EXP-125 leakage-safe cross-fitted Logistic stacking | 0.4068626451 | 미제출 | INFERENCE_VERIFIED | 소수 클래스 F1 붕괴·최고 단일 대비 -0.0153766511로 stack 기각 | [보고서](reports/exp137_cross_fitted_stacking/README.md) |
| EXP-151 | COMPLETED | fabxoe | #151 | EXP-094 + log1p(mutated_gene_count), Secure RTX 4090 실행 | 0.4188970451 | 0.3125095748 | INFERENCE_VERIFIED | Public은 EXP-094 대비 +0.0006564118이나 EXP-031 최고 미달·burden 피처 미채택 | [보고서](reports/exp151_mutated_gene_burden/README.md) |
| EXP-154 | COMPLETED | fabxoe | #154 | EXP-094 + log1p(total_variant_count), Secure RTX 4090 실행 | 0.4183986443 | 미제출 | NOT_STARTED | Macro F1·Log Loss 개선에도 fold 표준편차 +0.0056484로 기준 실패·미채택 | [보고서](reports/exp154_total_variant_burden/README.md) |
| EXP-156 | COMPLETED | Gomin-art | #156 | EXP-094의 유전자별 변이유형 indicator 5종을 compact effect descriptor 4종으로 압축 | 0.4148494335 | 미제출 | INFERENCE_VERIFIED | 특징 4,384개 감소에도 Macro F1 -0.0020371·fold 표준편차 +0.0046845로 기준 실패, ARCHIVE | [보고서](reports/exp156_gene_variant_effect_compression/README.md) |
| EXP-158 | COMPLETED | fabxoe | #158 | EXP-094 + log1p(missense_count), Secure RTX 4090 실행 | 0.4183327348 | 미제출 | NOT_STARTED | Macro F1·Log Loss 개선에도 fold 표준편차 +0.0032953으로 기준 실패·미채택 | [보고서](reports/exp158_missense_burden/README.md) |
| EXP-160 | COMPLETED | Kangho-Park | #160 | EXP-069 max_residue_position fold-safe permutation negative control (Issue #80 후속) | 0.3987413040(permuted 평균, 원본 0.4131007993) | 미제출(진단 실험) | NOT_STARTED | 25개 (seed, fold) 중 24개에서 하락(delta -0.0143594953)으로 신호 확인, Feature Spec v1 유지·Issue #80 계약 종료 | [보고서](reports/exp160_residue_position_negative_control/README.md) |
| EXP-170 | COMPLETED | Kangho-Park | #170 | EXP-094 + P_any_nonsilent_cellcycle (Cell Cycle pathway, #167 카탈로그 활용 파일럿 A) | 0.4137462167 | 미제출 | NOT_STARTED | Macro F1 -0.0031404, DLBC F1 -0.0500858 급락으로 기준 실패·미채택 | [보고서](reports/exp170_cellcycle_any_nonsilent/README.md) |
| EXP-173 | COMPLETED | Kangho-Park | #173 | EXP-094 + P_lof_in_tsg_cellcycle (Cell Cycle TSG LoF, #170 후속 파일럿 B, baseline=EXP-094) | 0.4135108482 | 미제출 | NOT_STARTED | Macro F1 -0.0033757, LUAD F1 -0.0235652 최대 하락으로 기준 실패·미채택. DLBC/LAML은 양성률 0%인데도 반대 방향으로 움직여 perturbation 해석 뒷받침 | [보고서](reports/exp173_cellcycle_lof_tsg/README.md) |
| EXP-179 | COMPLETED | fabxoe | #179 | EXP-094 Feature Spec v1 + outer-fold train 전용 SMOTE (`k=5`, `not majority`) | 0.4080771375 | 미제출 | INFERENCE_VERIFIED | EXP-094 대비 Macro F1 -0.0088094 및 LGG·BLCA·SARC F1 하락으로 ARCHIVE; 제출·추가 SMOTE tuning 중단 | [보고서](reports/exp179_xgb_feature_spec_v1_smote/README.md) |
| EXP-181 | COMPLETED | Kangho-Park | #181 | EXP-094 + pole__hotspot5 (POLE ED hotspot5, Vera Health 자문 반영 파일럿 D) | 0.4137048981 | 미제출 | NOT_STARTED | Macro F1 -0.0031817, DLBC F1 -0.0500858로 기준 실패·미채택. seed 42가 4-seed 중 뚜렷한 이상치(3개 stability seed는 baseline 근방); COAD는 4개 seed 전부 양의 방향으로 일관, UCEC/DLBC는 비일관. macro-f1-checkpoint 재평가(EXP-219 대비)로도 기각 유지 확정 | [보고서](reports/exp181_pole_hotspot5/README.md) |
| EXP-226 | COMPLETED | Kangho-Park | #226 | EXP-094 + pole__ed_driver_extended (POLE ED driver_extended, D의 COAD 신호 확증 파일럿 E) | 0.4141560542 | 미제출 | NOT_STARTED | Macro F1 -0.0027305, DLBC F1 -0.0500858로 기준 실패·미채택(확증 실험, gate는 참고용). COAD delta가 D와 정확히 동일(결정 경계 불변). macro-f1-checkpoint 재평가(EXP-219 대비)로도 기각 유지 — POLE pilot 트랙 최종 종료 | [보고서](reports/exp226_pole_ed_driver_extended/README.md) |
| EXP-188 | COMPLETED | fabxoe | #188 | EXP-094 + fold-local C1 Phi≥0.30/Jaccard≥0.15 pruning | 0.4179737169 | 0.3140052334 | INFERENCE_VERIFIED | Public은 EXP-094 대비 +0.0021520704이나 EXP-031·096·135 미달, ARCHIVE | [보고서](reports/exp188_c1_phi_jaccard_pruning/README.md) |
| EXP-189 | COMPLETED | fabxoe | #189 | EXP-094 + fold-local C2 Phi≥0.25/Jaccard≥0.15 pruning | 0.4147096714 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.0021769·fold std +0.0027542·최저 클래스 F1 -0.0568182로 gate 실패, ARCHIVE | [보고서](reports/exp189_c2_phi_jaccard_pruning/README.md) |
| EXP-190 | COMPLETED | fabxoe | #190 | EXP-094 + fold-local C3 Phi≥0.20/Jaccard≥0.10 pruning | 0.4157643312 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.0011222·fold std +0.0045573로 gate 실패, ARCHIVE; Phi/Jaccard ladder 종료 | [보고서](reports/exp190_c3_phi_jaccard_pruning/README.md) |
| EXP-191 | COMPLETED | fabxoe | #191 | EXP-094 + fold-local C2-policy pair `only_left/right/both` 요약 | 0.4144744818 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.0024121·fold std +0.0047535로 gate 실패, ARCHIVE | [보고서](reports/exp191_r1_correlation_pair_summary/README.md) |
| EXP-192 | COMPLETED | fabxoe | #192 | EXP-094 + fold-local 양성 수 `<5` mutation-presence 열 제거 | 0.4176058118 | 미제출 | MANIFEST_COMPLETE | Macro F1 +0.0007192지만 fold std +0.0073553으로 gate 실패, ARCHIVE | [보고서](reports/exp192_r2_rare_mutation_presence_filter/README.md) |
| EXP-203 | COMPLETED | fabxoe | #203 | EXP-094 + outer-train Elastic Net stability selection (최대 512 genes) | 0.2996289845 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.1172576·Log Loss +0.3633948; dense selector가 512개 cap을 유발해 ARCHIVE | [보고서](reports/exp203_s1_elastic_net_stability_selection/README.md) |
| EXP-205 | COMPLETED | fabxoe | #205 | EXP-094 + outer-train mRMR-MID top-128 mutation-presence genes | 0.3976963538 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.0191902·Log Loss +0.0426300으로 gate 실패, ARCHIVE | [보고서](reports/exp205_s2_mrmr_feature_selection/README.md) |
| EXP-209 | COMPLETED | 2heej | #209 | EXP-125 LightGBM + 동결 v2-performance pathway burden | 0.4188739423 | 미제출 | INFERENCE_VERIFIED | EXP-125와 F1 동률이나 fold 표준편차 +0.0050816으로 gate 실패, ARCHIVE | [보고서](reports/exp209_lightgbm_v2_performance/README.md) |
| EXP-207 | COMPLETED | fabxoe | #207 | EXP-094 + outer-train Boruta confirmed mutation-presence genes | 0.3484416378 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.0684449·DLBC F1 0으로 붕괴, 재튜닝 없이 ARCHIVE | [보고서](reports/exp207_s3_boruta_feature_selection/README.md) |
| EXP-219 | COMPLETED | fabxoe | #219 | EXP-094 동일 조건 + validation Macro-F1-best checkpoint 선택 | 0.4222321460 | 미제출 | INFERENCE_VERIFIED | 기존 mlogloss-best 대비 +0.0053456·fold std 개선, 향후 XGBoost 정책 채택 | [보고서](reports/exp219_macro_f1_checkpoint_selection/README.md) |
| EXP-196 | COMPLETED | fabxoe | #196 | outer-train raw mutation-presence TruncatedSVD 256 + aggregate·hotspot | 0.3496748557 | 미제출 | MANIFEST_COMPLETE | Macro F1 -0.0672117·fold std와 DLBC F1 붕괴로 ARCHIVE | [보고서](reports/exp196_s4_truncated_svd/README.md) |
| EXP-223 | COMPLETED | 2heej | #223 | EXP-096 pathway XGBoost + validation Macro-F1-best checkpoint | 0.4213739476 | 0.323243525 | INFERENCE_VERIFIED | EXP-096 대비 +0.0032586·Public 팀 최고 갱신으로 채택 | [보고서](reports/exp223_pathway_macro_f1_checkpoint/README.md) |
| EXP-229 | COMPLETED | 2heej | #229 | EXP-223 + pathway별 변이 종류 유전자 수 50개 후보 | 0.4229885745 | 0.3203598833 | INFERENCE_VERIFIED | Local은 EXP-223 대비 +0.0016146이나 Public은 EXP-223 대비 -0.0028836417로 대표 제출 미변경 | [보고서](reports/exp229_pathway_mutation_types/README.md) |
| EXP-232 | COMPLETED | 2heej | #232 | EXP-229 pathway 변이 피처의 nested group permutation 선택 | 0.4214874085 | 미제출 | INFERENCE_VERIFIED | 피처 수는 감소했지만 EXP-229 대비 -0.0015012로 Macro F1 gate 실패, ARCHIVE | [보고서](reports/exp232_pathway_group_selection/README.md) |
| EXP-237 | COMPLETED | 2heej | #237 | EXP-229 pathway 변이종류 raw count를 pathway 내부 fraction으로 교체 | 0.4204138300 | 미제출 | INFERENCE_VERIFIED | EXP-229 대비 -0.0025747·Log Loss 크게 악화로 ARCHIVE | [보고서](reports/exp237_pathway_mutation_fractions/README.md) |
| EXP-240 | COMPLETED | 2heej | #240 | EXP-229 + 문헌 고정 암종별 분자 변이조합 21개 | 0.4189644465 | 미제출 | INFERENCE_VERIFIED | EXP-229 대비 -0.0040241·Log Loss 악화로 ARCHIVE, 일부 클래스 신호만 후속 검토 | [보고서](reports/exp240_molecular_constellations/README.md) |
| EXP-245 | COMPLETED | 2heej | #245 | EXP-229 + 8개 암종 문헌 고정 mutation-mechanism proxy | 0.4213989560 | 미제출 | INFERENCE_VERIFIED | EXP-240 대비 개선했지만 EXP-229 대비 -0.0015896·Log Loss 악화로 ARCHIVE | [보고서](reports/exp245_lineage_mechanism_patterns/README.md) |
| EXP-250 | COMPLETED | 2heej | #250 | EXP-245 암종 모듈의 outer-train nested permutation 선택 | 0.4209182565 | 미제출 | INFERENCE_VERIFIED | 31개 중 fold별 27~31개를 유지하고 EXP-229·245 대비 성능과 안정성이 악화되어 ARCHIVE | [보고서](reports/exp250_lineage_group_selection/README.md) |
| EXP-253 | COMPLETED | 2heej | #253 | EXP-209 LightGBM + EXP-229 XGBoost 고정 0.5/0.5 확률 평균 | 0.4254998819 | 0.3054410279 | INFERENCE_VERIFIED | Local 최고였으나 EXP-223 Public 대비 -0.0178024971로 전이 실패·제출 후보 제외 | [보고서](reports/exp253_lightgbm_xgboost_blend/README.md) |
| EXP-211 | COMPLETED | 2heej | #211 | 동결 v2-performance + 26개 One-vs-Rest binary XGBoost | 0.4112914798 | 미제출 | INFERENCE_VERIFIED | EXP-096 대비 Macro F1 -0.0068238·Log Loss 악화로 ARCHIVE | [보고서](reports/exp211_ovr_xgboost_v2_performance/README.md) |
| EXP-257 | COMPLETED | Kangho-Park | #257 | EXP-096 + functional_role_burden_extended(oncogene/TSG count raw/frac/resid/log1p, fold-train 게이팅, #176 확장) | 0.4118051266 | 미제출 | INFERENCE_VERIFIED | EXP-096 대비 Macro F1 -0.0063102·Log Loss 악화, 26개 중 19개 클래스 하락으로 ARCHIVE | [보고서](reports/exp257_functional_role_burden_extended/README.md) |
| EXP-235 | COMPLETED | Gomin-art | #235 | Feature Spec v1 + outer-train 내부 nested-CV XGBoost·OOF pmax 신뢰도 분석 | 0.4255728433 | 0.302936084 | INFERENCE_VERIFIED | Local 개선에도 Public은 EXP-223 대비 -0.020307441로 낮아 단독 제출·앙상블 후보에서 제외; pmax는 진단 전용 | [보고서](reports/exp235_onconpc_xgb_confidence/README.md) |
| EXP-233 | COMPLETED | Kangho-Park | #233 | EXP-219 OOF + inner cross-fitting(K=3) 기반 class-wise logit offset(post-hoc, 재학습 없음) | 0.4241894920 | 미제출 | NOT_STARTED | Macro F1 +0.0019573이나 DLBC F1 -0.1235·Log Loss/fold 안정성 악화로 ARCHIVE | [보고서](reports/exp233_nested_decision_offset/README.md) |
| EXP-272 | COMPLETED | fabxoe | #272 | EXP-219 고정 5-seed(42·142·242·342·442) 확률 0.2 평균 | 0.4208578157 | 미제출 | INFERENCE_VERIFIED | EXP-219 대비 Macro F1 -0.0013743·fold 표준편차와 Log Loss 악화로 ARCHIVE | [보고서](reports/exp272_exp219_multiseed_ensemble/README.md) |
| EXP-276 | COMPLETED | Kangho-Park | #276 | EXP-233 class-wise logit offset + inner-fold 최소 표본 게이트(15/20/25) | 0.4262111346 | 미제출 | NOT_STARTED | Macro F1 +0.0039790이나 Log Loss·fold 안정성 악화 및 DLBC argmax 경쟁 손실로 ARCHIVE | [보고서](reports/exp276_nested_decision_offset_sample_gate/README.md) |
| EXP-279 | COMPLETED | fabxoe | #279 | EXP-219 동일 조건 + trailing 21-iteration Macro F1 중앙값 checkpoint 선택 | 0.4206209582 | 미제출 | INFERENCE_VERIFIED | EXP-219 대비 Macro F1 -0.0016112로 사전 허용치 초과, Log Loss는 개선됐으나 ARCHIVE | [보고서](reports/exp279_checkpoint_rolling_median/README.md) |
| EXP-285 | COMPLETED | fabxoe | #285 | EXP-229 고정 피처 + outer-train 3-fold nested Optuna XGBoost | 0.4314709544 | 0.320174485 | INFERENCE_VERIFIED | Local 개선이 Public에 일부 전이됐지만 EXP-223 대비 -0.003069040·최종 선택 제출은 EXP-223 유지 | [보고서](reports/exp285_exp229_nested_optuna_xgb/README.md) |
| EXP-296 | COMPLETED | Kangho-Park | #296 | EXP-094 + CTNNB1 D32/S33 hotspot 2개 컬럼(phosphodegron 모티프, hotspot-34 S37/S45와 별도 컬럼) | 0.4172413559 | 미제출 | NOT_STARTED | EXP-094 대비 Macro F1 +0.0003548로 gate 미달, fold 표준편차·클래스별 F1(LUAD -0.0472) gate도 실패로 ARCHIVE | [보고서](reports/exp296_ctnnb1_d32_s33_hotspot/README.md) |
| EXP-302 | COMPLETED | fabxoe | #302 | EXP-229 + 고정 관찰 가능 암종 표지 mutation proxy 17~18개 | 0.4212799841 | 미제출 | INFERENCE_VERIFIED | Macro F1 -0.0017086로 gate 실패, Log Loss·fold 안정성은 개선했으나 ARCHIVE | [보고서](reports/exp302_observable_marker_proxies/README.md) |
| EXP-313 | COMPLETED | fabxoe | #313 | EXP-229 + Ensembl 116 신뢰도 기반 residue-position mask | 0.4267909268 | 미제출 | INFERENCE_VERIFIED | Macro F1 +0.0038024·fold std·Log Loss 동시 개선으로 채택 후보 | [보고서](reports/exp313_isoform_residue_mask/README.md) |
| EXP-317 | COMPLETED | fabxoe | #317 | EXP-229 + Ensembl 의미 범주 sample count/any 12개 | 0.4170163022 | 미제출 | INFERENCE_VERIFIED | Macro F1·fold std·Log Loss·DLBC 모두 악화로 ARCHIVE | [보고서](reports/exp317_isoform_semantic_summary/README.md) |
| EXP-323 | COMPLETED | fabxoe | #323 | EXP-285·EXP-313 고정 0.5/0.5 확률 평균 | 0.4260586706 | 미제출 | INFERENCE_VERIFIED | 오류 다양성은 확인했지만 최고 부모 대비 -0.0054123·fold std 악화로 ARCHIVE, 가중치 추가 탐색 중단 | [보고서](reports/exp323_exp285_exp313_fixed_blend/README.md) |
| EXP-327 | COMPLETED | fabxoe | #327 | EXP-229의 raw max residue-position을 Ensembl 116 isoform-relative 5-bin+observed로 교체 | 0.4266361381 | 미제출 | INFERENCE_VERIFIED | EXP-229 대비 +0.0036476이나 EXP-313보다 F1·fold 안정성·Log Loss 열세로 ARCHIVE | [보고서](reports/exp327_isoform_relative_position_bin/README.md) |
| EXP-334 | COMPLETED | fabxoe | #334 | EXP-285 fold별 고정 파라미터 + EXP-313 Ensembl semantic residue-position mask | 0.4351340093 | 0.3150635813 | INFERENCE_VERIFIED | Local 최고이나 Public은 EXP-223 대비 -0.0081799437로 전이 실패·최종 선택 제출은 EXP-223 유지 | [보고서](reports/exp334_exp285_isoform_residue_mask/README.md) |

## 리더보드 제출 이력

| 제출 시각 | 실험 ID | Issue | 제출 파일 | SHA-256 | Public 점수 | 순위 | 재현 상태 |
|---|---|---|---|---|---:|---:|---|
| 2026-07-30T18:20:48+09:00 | EXP-003 | #3 | `submissions/exp003_xgb_baseline.csv` (제출 ID `1506230`) | `6e8b64726c86b5a6d52ee58f7f042b74b302852aa8a59c9bfe13332bfee424a5` | 0.228167518 | 3 (확인 당시) | INFERENCE_VERIFIED |
| 2026-07-30T18:26:30+09:00 | EXP-005 | #5 | `submissions/exp005_xgb_mutation_features.csv` | `7bc3e64e1904d9b4007bc141dde771a39e7527172f3cd24c25c408000103183c` | 0.2987843366 | 제출 시점 1위 → 2026-07-30 23:13 KST 기준 2위 | INFERENCE_VERIFIED |
| 2026-07-30T23:28:27+09:00 | EXP-021 | #21 | `submissions/exp021_cosmic_weighted_burden_baseline.csv` (제출 ID `1506440`) | `cb75da2609631bc86310a637e2d4f2e244bfe85dac71da4f154559ebf19a07b0` | 0.2544194867 | 당시 팀 최고 EXP-005<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | NOT_STARTED |
| 2026-07-30T23:56:29+09:00 | EXP-026 | #26 | `submissions/exp026_mutation_burden.csv` (제출 ID `1506469`) | `53d835335d6d23945c80acef4b70d0112f14abdaf1b5d504a63fd1ea7b16ef00` | 0.2575936484 | 당시 팀 최고 EXP-005<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | NOT_STARTED |
| 2026-07-31T15:50:02+09:00 | EXP-031 | #31 | `submissions/exp031_hotspot_extended.csv` (제출 ID `1506950`, attempt 5) | `54de49396b8910fd8134b5a854beed344e369a9a791c67c6c9caf0da38cec27d` | 0.3170803849 | 제출 당시 전체 2위 → 2026-08-01 확인 기준 참가 4팀 중 4위 | FAILED |
| 2026-07-31T18:46:30+09:00 | EXP-030 | #30 | `submissions/exp030_sparse_variant_xgb.csv` (제출 ID `1507123`) | `bd523ea4e872301e7d11f44ea375cf16d8c282de549f5f408d67ba3146670cba` | 0.2993610323 | EXP-031 최고 점수<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | INFERENCE_VERIFIED |
| 2026-07-31T22:44:57+09:00 | EXP-058 | #58 | `submissions/exp058_cooccurrence_pair_ablation.csv` (제출 ID `1507272`) | `0a53d0a7aea3b0c34baba586e56175c6bc8df2c738875a2bef30c5ebad905eb3` | 0.3044672015 | EXP-031 최고 점수<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | INFERENCE_VERIFIED |
| 2026-07-31T23:55:33+09:00 | EXP-085 | #85 | `submissions/exp085_hotspot_clean.csv` (제출 ID `1507333`) | `d319c6967ea98b75c158265fe3b46a5ebb12db207a19cd87964476154eecfe5d` | 0.3103760308 | EXP-031 최고 점수<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span><span style="display:block">팀 내부 8개 제출 중 2위</span> | INFERENCE_VERIFIED |
| 2026-08-01T23:36:17+09:00 | EXP-125 | #125 | `submissions/exp125_lightgbm_v1.csv` (제출 ID `1508041`) | `e76cce6d911616930570bcf0c5c1adc8adb045fbd18e3226d5378bda026d5940` | 0.3075810937 | EXP-031 최고 미달·확인 당시 참가 4팀 중 4위 유지 | INFERENCE_VERIFIED |
| 2026-08-01T23:36:59+09:00 | EXP-096 | #96 | `submissions/exp096_fixed_pathway_burden.csv` (제출 ID `1508043`) | `0d6bdaacec8c9853bc44c3d00fa6eec04f4e0b5b2fd583971e4057a2beefaf0d` | 0.3169056749 | EXP-031 대비 -0.0001747100·확인 당시 참가 4팀 중 4위 유지 | INFERENCE_VERIFIED |
| 2026-08-01T23:39:49+09:00 | EXP-075 | #75 | `submissions/exp075_residue_probability_blend.csv` (제출 ID `1508045`) | `25f00f1a97acbd5364df0dd7b391f75a930888fefc887edf696f681d482d7b3e` | 0.31125491 | EXP-031 최고 미달·확인 당시 참가 4팀 중 4위 유지 | INFERENCE_VERIFIED |
| 2026-08-01T23:41:04+09:00 | EXP-127 | #127 | `submissions/exp127_catboost_v1.csv` (제출 ID `1508047`) | `f4fdd043a1875a41d333fa88f34911fd0f6f20758a3bd41deea1288d473cb543` | 0.3014741179 | EXP-031 최고 미달·확인 당시 참가 4팀 중 4위 유지 | INFERENCE_VERIFIED |
| 2026-08-02T23:04:51+09:00 | EXP-094 | #94 | `submissions/exp094_feature_spec_v1.csv` (제출 ID `1508852`) | `89e4ade9df511b49fbf58fc093744417f2980cdd20b4a86849a0c4b93b1c5411` | 0.311853163 | EXP-031 최고 점수<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | INFERENCE_VERIFIED |
| 2026-08-02T23:07:03+09:00 | EXP-135 | #135 | `submissions/exp135_fixed_probability_blend.csv` (제출 ID `1508856`) | `5eef332c50322a8f2be1fb64b15bef49d8f5c91ac6200a7dbc587cebaa75b70a` | 0.3166527939 | EXP-031 최고 대비 -0.0004275910<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span><span style="display:block">재현 가능한 제출 중 2위</span> | INFERENCE_VERIFIED |
| 2026-08-02T23:52:30+09:00 | EXP-151 | #151 | `submissions/exp151_mutated_gene_burden.csv` (제출 ID `1508912`) | `dddaf57cf2c497b08264a2c883223afff0d347edcadb9585783f06e1294e4349` | 0.3125095748 | EXP-031 최고 점수<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | INFERENCE_VERIFIED |
| 2026-08-02T23:53:56+09:00 | EXP-188 | #188 | `submissions/exp188_c1_phi_jaccard_pruning.csv` (제출 ID `1508914`) | `a36bffa5e4d055f99d5fc8584c795a08c9f1b608cc941716d61b5b94428a1d0a` | 0.3140052334 | EXP-031 최고 점수<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span> | INFERENCE_VERIFIED |
| 2026-08-03T10:30:33+09:00 | EXP-223 | #223 | `submissions/exp223_pathway_macro_f1_checkpoint.csv` (제출 ID `1509283`) | `74a23b6337b17fc4ed70ae1e3639331065e0d74432bed6b8fcf9dc9344e6c48c` | 0.323243525 | 팀 Public 최고 갱신<span style="display:block">2026-08-03 19:13 KST 기준 참가 4팀 중 4위·팀 제출 17회</span> | INFERENCE_VERIFIED |
| 2026-08-03T23:45:30+09:00 | EXP-229 | #229 | `submissions/exp229_pathway_mutation_types.csv` (제출 ID `1509990`) | `66f50d7fdd3c0ca65e586f83c4ee4d8cfb3a99d85d03c04ef9b8fbea7b1af61b` | 0.3203598833 | EXP-223 최고 대비 -0.0028836417<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span><span style="display:block">확인 당시 참가 4팀 중 4위·팀 제출 20회</span> | INFERENCE_VERIFIED |
| 2026-08-03T23:32:05+09:00 | EXP-253 | #253 | `submissions/exp253_lightgbm_xgboost_blend.csv` (제출 ID `1509964`) | `c57c06bcfadae47741f9c5392ecf73fc3d16ed36ed410901b73acda81b320f48` | 0.3054410279 | EXP-223 최고 대비 -0.0178024971<span style="display:block">제출 직후 참가 4팀 중 4위·팀 제출 18회·선택 제출은 EXP-223 유지</span> | INFERENCE_VERIFIED |
| 2026-08-03T23:36:42+09:00 | EXP-235 | #235 | `submissions/exp235_onconpc_xgb_confidence.csv` (제출 ID `1509972`) | `5df26dfb604094254074e3ba38c5455d721c6d64973a9cde56a098a17e1b3b48` | 0.302936084 | EXP-223 최고 대비 -0.020307441<span style="display:block;color:#8b949e">미달·단독 제출 및 앙상블 후보 제외</span> | INFERENCE_VERIFIED |
| 2026-08-04T14:29:44+09:00 | EXP-334 | #334 | `submissions/exp334_exp285_isoform_residue_mask.csv` (제출 ID `1510674`) | `b7b57180ac686553c9f2c65c5634043e756fa8988df9d01e5f441edc485f3918` | 0.3150635813 | EXP-223 최고 대비 -0.0081799437<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span><span style="display:block">확인 당시 참가 4팀 중 4위·팀 제출 21회</span> | INFERENCE_VERIFIED |
| 2026-08-04T14:40:15+09:00 | EXP-285 | #285 | `submissions/exp285_exp229_nested_optuna_xgb.csv` (제출 ID `1510681`) | `6291e67c9a4ea4dfe34b294ed6ea9fa0f8e94708cc156f95566292655937145a` | 0.320174485 | EXP-223 최고 대비 -0.003069040<span style="display:block;color:#8b949e">미달·팀 순위 미갱신</span><span style="display:block">확인 당시 참가 4팀 중 4위·팀 제출 22회</span> | INFERENCE_VERIFIED |

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
| 2026-07-31T08:29:17.955451+00:00 | EXP-050 | 2heej | `b7444843245eb1e2a360084e0dfb42653cf6116a` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp050_xgb_fixed_two_distribution_features/comparison.json) |
| 2026-07-31T09:24:31.209567+00:00 | EXP-052 | Kangho-Park | `6865fd5accf4fbf7090dc39ecc4a27f9b611adf7` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp052_hotspot_cooccurrence/comparison.json) |
| 2026-07-31T11:07:03.530920+00:00 | EXP-065 | fabxoe | `64f1a4c7d948c3951e88c9d80caf47fd2a5fd07b` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp065_xgb_residue_exclude_complex/comparison.json) |
| 2026-07-31T10:50:47.543725+00:00 | EXP-063 | fabxoe | `7265bf6c6fc166cf7f30ef07f41ed2c641a3fb56` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp063_xgb_residue_indicator/comparison.json) |
| 2026-07-31T11:19:02.749201+00:00 | EXP-067 | fabxoe | `5846db2f18f610836a38b23cc8c377f9809fe47c` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp067_xgb_residue_coarse_bin/comparison.json) |
| 2026-07-31T11:33:26.265681+00:00 | EXP-069 | fabxoe | `8b603bcf8b03658e54d158b5976df51c90cea5f8` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp069_xgb_max_residue_position/comparison.json) |
| 2026-07-31T12:59:12.117866+00:00 | EXP-075 | fabxoe | `01fb86e27b0ebfd177d4a6e60ac6535a02fcfb3c` / [`exp-075-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-075-repro-v1) | 부모 artifact SHA-256 일치 | byte-level SHA-256 일치, OOF·test 라벨 100%, 확률 최대 차이 0 | 새 학습 없음(inference-only blend) | INFERENCE_VERIFIED | [comparison](reproducibility/exp075_residue_probability_blend/comparison.json) |
| 2026-07-31T14:04:09.991821+00:00 | EXP-078 | fabxoe | `e2a822e576095a25bdf01a46c1bb5e404684f316` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp078_xgb_max_residue_indicator/comparison.json) |
| 2026-07-31T07:58:45.020690+00:00 | EXP-030 | Gomin-art | `64b72df89ee5cf0b66409f494475aca753238184` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 5.83e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp030_sparse_variant_xgb/comparison.json) |
| 2026-07-31T10:18:14.298161+00:00 | EXP-058 | Kangho-Park | `45b353ce4073e4a9bad0c0866f4cb84ac5a53fe7` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp058_cooccurrence_pair_ablation/comparison.json) |
| 2026-07-31T14:54:04.764691+00:00 | EXP-085 | fabxoe | `e329f13f7de85cc34c0e54c85f25f093e2ed0dd1` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp085_hotspot_clean/comparison.json) |
| 2026-08-01T06:21:49.113157+00:00 | EXP-094 | fabxoe | `19d5c067517af42f1b5e353b2106e352bae185df` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp094_feature_spec_v1/comparison.json) |
| 2026-08-01T09:20:01.124960+00:00 | EXP-106 | fabxoe | `8e54d0f48b891bbc8aa99130e1954cf1cb8b6f08` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp106_recurrent_exact_token/comparison.json) |
| 2026-08-01T09:48:14.214888+00:00 | EXP-107 | fabxoe | `efe36044e117df9e8d9e821e19e092e75844d966` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp107_amino_acid_change/comparison.json) |
| 2026-08-01T10:02:39.082057+00:00 | EXP-109 | fabxoe | `2e5882eb9c050292c6167c584cf4977a12c1cdab` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp109_complex_morphology/comparison.json) |
| 2026-08-01T10:19:49.995276+00:00 | EXP-110 | fabxoe | `1c0e835eecb5d5edbffc61c632c583395f698d1b` / 태그 없음 | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.97e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp110_frequency_tier_spectrum/comparison.json) |
| 2026-08-01T10:45:05.297140+00:00 | EXP-096 | fabxoe | `296c39fe9259fd4ee93bd8158aeaecec0c891545` / [`exp-096-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-096-repro-v1) | 일치 | SHA-256 일치, 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp096_fixed_pathway_burden/comparison.json) |
| 2026-08-01T12:24:32.873783+00:00 | EXP-125 | fabxoe | `8d4fe9c99e05306c691f1c4f23903066b92f7ddf` / [`exp-125-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-125-repro-v1) | 일치 | SHA-256 일치, OOF·test 라벨 100%, 확률 최대 차이 0 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp125_lightgbm_v1/comparison.json) |
| 2026-08-01T14:26:44.634572+00:00 | EXP-127 | fabxoe | `03af58890c1cac9d90e61430e550b7ae6cc7060d` / [`exp-127-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-127-repro-v1) | 일치 | SHA-256 일치, OOF·test 라벨 100%, 확률 최대 차이 0 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp127_catboost_v1/comparison.json) |
| 2026-08-02T09:15:19.096281+00:00 | EXP-179 | fabxoe | `704731a20520339e21f4c84eae93708d2e1dfd3e` / 태그 없음 | SHA-256 일치 | SHA-256 일치, OOF·test 라벨 100%, 확률 최대 차이 0 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp179_xgb_feature_spec_v1_smote/comparison.json) |
| 2026-08-02T16:32:46.152425+00:00 | EXP-211 | 2heej | `38955bcb7f1a0e8d72e933fd9fa4d48bd1a7873a` / 태그 없음 | SHA-256 일치 | SHA-256 일치, OOF·test 라벨 100%, 확률 최대 차이 2.12e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp211_ovr_xgboost_v2_performance/comparison.json) |
| 2026-08-02T14:26:22.219111+00:00 | EXP-209 | 2heej | `ec05d217aeed555e3beb18151920a07fe275dd6f` / [`exp-209-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-209-repro-v1) | SHA-256 일치 | SHA-256 일치, OOF·test 라벨 100%, 확률 최대 차이 0; Issue #260에서 원본 Release 복구 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp209_lightgbm_v2_performance/comparison.json) |
| 2026-08-03T09:41:48.286924+00:00 | EXP-257 | Kangho-Park | `56b1b1d3515b9ff09f36fc7ca691ccdeaf53d487` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 2.98e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp257_functional_role_burden_extended/comparison.json) |
| 2026-08-03T13:17:22.042664+00:00 | EXP-272 | fabxoe | `5913bf49e920d5e1ff36e9ff56bf9f16aa90f40b` / 태그 없음 | SHA-256 일치 | 5개 seed checkpoint 검증 통과·고정 평균 제출 SHA-256 일치·라벨 100%·확률 최대 차이 0 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp272_exp219_multiseed_ensemble/comparison.json) |
| 2026-08-03T13:53:13.072581+00:00 | EXP-279 | fabxoe | `e904bc0e9a3e409c5b7884dbe6bf512bf63be1b7` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.43e-07 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp279_checkpoint_rolling_median/comparison.json) |
| 2026-08-03T16:50:07.665158+00:00 | EXP-302 | fabxoe | `6f6094a28fe5f1f6ae0b710df5c3f6b8c8cc3db3` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 byte-level 일치, test 라벨 100%, 확률 최대 차이 1.34e-07 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp302_observable_marker_proxies/comparison.json) |
| 2026-08-03T18:38:55.344594+00:00 | EXP-313 | fabxoe | `f8a9c30c5b2b34014e05b64c61b0eb27fa0e4636` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 byte-level 일치, test 라벨 100%, 확률 최대 차이 1.83e-07 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp313_isoform_residue_mask/comparison.json) |
| 2026-08-03T23:57:10.879539+00:00 | EXP-317 | fabxoe | `8be79a94fb0b5f77f0c97a87ffcc4a6bcbe17196` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 byte-level 일치, test 라벨 100%, 확률 최대 차이 1.49e-07 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp317_isoform_semantic_summary/comparison.json) |
| 2026-08-04T00:33:48.973528+00:00 | EXP-285 | fabxoe | `893f0be9c82442bf5e3940848578dc7a73677af4` / [`exp-285-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-285-repro-v1) | SHA-256 일치 | 제출 SHA-256 byte-level 일치, test 라벨 100%, 확률 최대 차이 2.01e-07 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp285_exp229_nested_optuna_xgb/comparison.json) |
| 2026-08-04T01:01:11.073002+00:00 | EXP-323 | fabxoe | `4f0776175fd935acc4edb435f9e21e426909b23e` / 태그 없음 | 부모 artifact SHA-256 일치 | OOF·test 라벨 100%, 확률 최대 차이 0, 제출 SHA-256 byte-level 일치 | 새 학습 없음(inference-only blend) | INFERENCE_VERIFIED | [comparison](reproducibility/exp323_exp285_exp313_fixed_blend/comparison.json) |
| 2026-08-04T01:42:37.063988+00:00 | EXP-327 | fabxoe | `f3b309170206163aa4adc138fec7513e4bfcd2d7` / 태그 없음 | SHA-256 일치 | test 라벨 100%, 확률 최대 차이 1.48e-07, 제출 SHA-256 byte-level 일치 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp327_isoform_relative_position_bin/comparison.json) |
| 2026-08-04T06:07:52.821402+00:00 | EXP-235 | Gomin-art | `f3efedce60aafebf8831a4f4cbc4a04e413bc6c8` / [`exp-235-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-235-repro-v1) | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 5.58e-08; 원 산출물 SHA-256 재확인 후 Release 복구 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp235_onconpc_xgb_confidence/comparison.json) |

## 상세 실험 로그

<!-- 실제 실험 로그는 이 줄 아래에 시간순으로 추가합니다. -->

### [EXP-334] EXP-285 고정 fold 파라미터 + Ensembl semantic residue mask

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #334 / `issue-334-exp285-semantic-residue-mask`
- 소스 commit: `cf0bc5382b067b3dad63f3253b4b724cdcbdec28`
- 시작/종료: 2026-08-04T04:29:17.146887+00:00 /
  2026-08-04T04:42:29.173934+00:00
- 부모: EXP-285; semantic mask 정의: EXP-313
- 유일한 변경: residue-position 집계에서 Ensembl 116 sequence로 설명되지 않는
  semantic 범주를 제외했다. 나머지 피처와 EXP-285 fold별 파라미터는 해시로
  고정하고 재탐색하지 않았다.
- OOF Macro F1: 0.4351340093 (EXP-285 대비 `+0.0036630549`)
- Fold Macro F1: 0.4293405 / 0.4420335 / 0.4226493 / 0.4300833 /
  0.4526057
- Fold 표준편차: 0.0106544650 (EXP-285 대비 `-0.0010664778`)
- Accuracy: 0.4238026125 (EXP-285 대비 `+0.0016126431`)
- Log Loss: 1.8419390917 (EXP-285 대비 `+0.0010001659`)
- 클래스별 최대 하락: LUAD `-0.01587`; `-0.05` 이상 붕괴 없음
- low-MANE train OOF quartile: Q1 `+0.00378`, Q2 `+0.00583`, Q3
  `-0.00252`, Q4 `+0.00601` (사후 안전성 진단, 선택에 미사용)
- 실행 환경: RunPod Secure Cloud NVIDIA A40 46GB; EXP-285 RTX 4090과 GPU
  기종 차이를 보고서에 명시
- Public LB: `0.3150635813` (제출 ID `1510674`, 2026-08-04 14:29:44 KST)
- 재현 상태: `INFERENCE_VERIFIED`; 제출 SHA-256 일치, test label 100%,
  확률 최대 차이 `1.4582672e-7`
- Release: [`exp-334-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-334-repro-v1),
  bundle SHA-256 `78ee11a6a47f1a5acb2f9e9312ece44193974c5820774ce89d97beac070237f7`
- 결론: M1 Local gate와 재현 검증은 통과했지만 Public은 EXP-223보다
  `-0.0081799437` 낮아 최종 선택 제출을 바꾸지 않는다. Local 의미 감사 결과는
  보존하되 Public 대표 후보에서는 후순위로 내리고, 최종 지정 전 독립 재학습
  검증이 필요하다.
- Report: `reports/exp334_exp285_isoform_residue_mask/README.md`
- Metrics: `reports/exp334_exp285_isoform_residue_mask/metrics.json`

### [EXP-327] Ensembl isoform-relative residue-position 5-bin

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #327 / `issue-327-isoform-relative-position-bin`
- 소스 commit: `f3b309170206163aa4adc138fec7513e4bfcd2d7`
- 시작/종료: 2026-08-04T01:34:19.623302+00:00 /
  2026-08-04T01:42:35.266530+00:00
- 부모: EXP-229
- 유일한 변경: raw max residue-position을 frozen Ensembl 116 sequence 기반
  relative 5-bin으로 교체하고 observed indicator를 추가했다.
- OOF Macro F1: 0.4266361381 (EXP-229 대비 `+0.0036475635`)
- Fold Macro F1: 0.4155225548 / 0.4250140277 / 0.4213012888 /
  0.4215258721 / 0.4485677567
- Fold 표준편차: 0.0115013235 (EXP-229 대비 `+0.0016333586`)
- Log Loss: 1.8585858345 (EXP-229 대비 `+0.0076245070`)
- EXP-313 대비 Macro F1 `-0.0001547888`, fold std `+0.0029981066`,
  Log Loss `+0.0145210028`로 열세다.
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`; test label 100%, 확률 최대 차이
  `1.4829636e-07`, submission SHA-256 일치
- 결론: isoform 의미 기반 위치 정규화 방향은 재확인했지만 EXP-313을 대체하지
  못해 `ARCHIVE`하고 bin·isoform 우선순위 추가 탐색을 중단한다.
- Report: `reports/exp327_isoform_relative_position_bin/README.md`
- Metrics: `reports/exp327_isoform_relative_position_bin/metrics.json`

### [EXP-296] CTNNB1 D32/S33 hotspot 확장 (phosphodegron 모티프 나머지 조각)

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #296 / `issue-296-ctnnb1-d32-s33-hotspot`
- 소스 commit: `a5395390fe724cece6afffd09ae24039c03cc82d`
- 시작/종료: 2026-08-03T15:24:07.542781+00:00 /
  2026-08-03T16:39:06.419383+00:00

#### 배경

- DominoEffect 스타일 panel-wide 스크리닝(#292 백로그)에서 발굴한 CTNNB1
  D32/S33은 기존 hotspot-34의 CTNNB1 S37/S45와 같은 beta-catenin N-terminal
  phosphodegron 모티프의 나머지 조각이다.
- 사전검증에서 Vera 게이트 A/B/C를 5개 fold 모두 통과했고, D32/S33/S37/S45
  표본 교집합은 0이었다. EXP-058의 정보 손실 패턴을 피하기 위해 D32/S33을
  별도 컬럼 2개로 추가했다.

#### 실행과 결과

- 신규 피처: `hotspot__CTNNB1_32`, `hotspot__CTNNB1_33`
- train 양성: 각각 23건, 24건이며 5개 fold에 모두 존재했다.
- Fold Macro F1: 0.4157178019 / 0.4183811139 / 0.3981947711 /
  0.4242935546 / 0.4263623735
- OOF Macro F1: 0.4172413559 (EXP-094 대비 `+0.0003547820`)
- Fold 표준편차: 0.0099719336 (`+0.0020876816`, 악화)
- Log Loss: 1.8386958719 (`-0.0012414574`, 개선)
- UCEC `+0.0003878839`, LIHC `-0.0032803097`; 최악 클래스 LUAD
  `-0.0472178289`
- 3-seed(1001/1002/1003) 안정성 확인 결과 공식 seed 42는 이상치가 아니었다.
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 산출물과 결론

- Config: `configs/exp296_ctnnb1_d32_s33_hotspot.yaml`
- Metrics: `reports/exp296_ctnnb1_d32_s33_hotspot/metrics.json`
- Report: `reports/exp296_ctnnb1_d32_s33_hotspot/README.md`
- Verdict: `reports/exp296_ctnnb1_d32_s33_hotspot/verdict.json`
- Macro F1·fold 안정성·클래스별 F1 gate를 통과하지 못해 `ARCHIVE`하고,
  CTNNB1 phosphodegron 확장 트랙을 종료한다.

### [EXP-323] EXP-285·EXP-313 고정 0.5/0.5 확률 평균

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #323 / `issue-323-exp285-exp313-fixed-blend`
- source commit: `4f0776175fd935acc4edb435f9e21e426909b23e`
- 시작/종료: 2026-08-04T01:01:10.579110+00:00 /
  2026-08-04T01:01:11.073002+00:00
- 사전 다양성 감사: 예측 불일치율 16.76%, 오류 상관 0.8430
- Fold Macro F1: 0.4265049565 / 0.4198154548 / 0.4157122586 /
  0.4175498749 / 0.4486491485
- OOF Macro F1: 0.4260586706 (EXP-285 대비 `-0.0054122838`)
- Fold 표준편차: 0.0120673474 (두 부모 대비 악화)
- Accuracy: 0.4146105467, Log Loss: 1.8292042544
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`
- 결론: 공식 Macro F1과 안정성이 최고 부모보다 낮아 `ARCHIVE`; 추가 가중치
  탐색·Public 제출 중단
- 상세: [보고서](reports/exp323_exp285_exp313_fixed_blend/README.md)

### [EXP-285] EXP-229 nested Optuna XGBoost

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #285 / `issue-285-exp229-nested-optuna-result`
- 실행 source commit: `893f0be9c82442bf5e3940848578dc7a73677af4`
- 시작/종료: 2026-08-04T00:25:41.635305+00:00 /
  2026-08-04T00:33:44.727395+00:00
- 부모 EXP-229의 피처 정책을 고정하고 각 outer-train 내부 3-fold에서만
  TPE 30 trial을 수행(총 150개 완료 trial)
- Fold Macro F1: 0.4252500505 / 0.4380602207 / 0.4149180217 /
  0.4314910879 / 0.4496814376
- OOF Macro F1: 0.4314709544 (EXP-229 대비 `+0.0084823799`, Local 최고)
- Fold 표준편차: 0.0117209428 (EXP-229 대비 `+0.0018529779`, 악화)
- Accuracy: 0.4221899694, Log Loss: 1.8409389257
- Public LB: `0.320174485` (제출 ID `1510681`, 2026-08-04 14:40:15 KST)
- 재현 상태: `INFERENCE_VERIFIED`
- 결론: Public은 EXP-229보다 `-0.0001853983`, EXP-223보다 `-0.003069040`
  낮아 최종 선택 제출을 바꾸지 않는다. nested Optuna의 큰 Local 개선이 Public에
  같은 크기로 전이되지 않았으므로 대표 후보에서는 후순위로 내리고, 독립 재학습
  검증 전 최종 모델 확정은 보류한다.
- 상세: [보고서](reports/exp285_exp229_nested_optuna_xgb/README.md)

### [EXP-317] isoform 의미 범주 sample 요약

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #317 / `issue-317-exp-isoform-summary`
- 실행 source commit: `8be79a94fb0b5f77f0c97a87ffcc4a6bcbe17196`
- 시작/종료: 2026-08-03T23:44:54.309135+00:00 /
  2026-08-03T23:57:09.106596+00:00
- 유일한 변경: Ensembl 116 의미 범주 6개의 count·any indicator 총 12개 추가
- Fold Macro F1: 0.4144549506 / 0.4094846772 / 0.4078213016 /
  0.4168022464 / 0.4391416942
- OOF Macro F1: 0.4170163022 (EXP-229 대비 `-0.0059722724`)
- Fold 표준편차: 0.0112786198 (`+0.0014106548`, 악화)
- Log Loss: 1.9048725367 (`+0.0539112091`, 악화)
- DLBC F1: EXP-229 대비 `-0.06258`
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`
- 결론: 모든 주요 gate를 실패해 `ARCHIVE`; B2-2 추가 튜닝 중단
- 상세: [보고서](reports/exp317_isoform_semantic_summary/README.md)

### [EXP-313] Ensembl 신뢰도 기반 residue-position mask

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #313 / `issue-313-exp-isoform-position-mask`
- 실행 source commit: `f8a9c30c5b2b34014e05b64c61b0eb27fa0e4636`
- 시작/종료: 2026-08-03T18:29:04.354474+00:00 /
  2026-08-03T18:38:53.440510+00:00

#### 실행과 결과

- 부모 EXP-229의 피처·모델·canonical fold·Macro-F1 checkpoint 정책 유지
- 유일한 변경: Ensembl release 116의 알려진 protein isoform sequence와
  reference amino acid가 일치하지 않는 token을 max residue-position에서만 제외
- mutation presence·mutation type 등 원 피처는 유지하고, annotation 범주는
  SUBCLASS·test 분포·Public LB 없이 사전 고정
- Fold Macro F1: 0.4243902236 / 0.4214466890 / 0.4201172029 /
  0.4239068711 / 0.4433574970
- OOF Macro F1: 0.4267909268 (EXP-229 대비 `+0.0038023523`)
- Fold 표준편차: 0.0085032169 (EXP-229 대비 `-0.0013647481`, 개선)
- Accuracy: 0.4128366393, Log Loss: 1.8440648317
  (EXP-229 대비 `-0.0068964958`, 개선)
- 클래스 최대 개선 DLBC `+0.05688`, 최대 하락 CESC `-0.01556`
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- Config: `configs/exp313_isoform_residue_mask.yaml`
- Runner: `scripts/run_exp313_isoform_residue_mask.py`
- Metrics/Report: `reports/exp313_isoform_residue_mask/`
- Reproduction: `reproducibility/exp313_isoform_residue_mask/`
- 저장 checkpoint 재추론으로 test 라벨 100%, 확률 최대 차이 `1.83e-7`,
  submission SHA-256 byte-level 일치를 확인했다.
- Macro F1 +0.001, fold 안정성, Log Loss 사전 gate를 모두 통과해 채택 후보로
  유지한다. 외부 annotation 규정 확인과 독립 재학습 전에는 최종 수상 후보로
  승격하지 않는다.

### [EXP-302] 고정 관찰 가능 암종 표지 mutation proxy

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #302 / `issue-302-observable-marker-proxy`
- PR: #305
- 실행 source commit: `6f6094a28fe5f1f6ae0b710df5c3f6b8c8cc3db3`
- 시작/종료: 2026-08-03T16:28:51.727168+00:00 /
  2026-08-03T16:41:48.426138+00:00

#### 실행과 결과

- 부모 EXP-229의 피처·모델·canonical fold·Macro-F1 checkpoint 정책을 유지하고
  문헌에서 사전 고정한 5개 암종 표지 패널의 관찰 가능한 mutation proxy만 추가
- fusion, amplification, MSI/dMMR, germline 상태와 Public LB는 피처 정의에 미사용
- fold-local 의미 중복 제거 후 marker 피처 `18 / 18 / 17 / 18 / 18`개 유지
- Fold Macro F1: 0.4127412855 / 0.4228720327 / 0.4153153863 /
  0.4167496415 / 0.4389531503
- OOF Macro F1: 0.4212799841 (EXP-229 대비 `-0.0017085904`)
- Fold 표준편차: 0.0094220433 (EXP-229 대비 `-0.0004459216`, 개선)
- Accuracy: 0.4089662958, Log Loss: 1.8409115076
  (EXP-229 대비 `-0.0100498199`, 개선)
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- Config: `configs/exp302_observable_marker_proxies.yaml`
- Runner: `scripts/run_exp302_observable_marker_proxies.py`
- Metrics: `reports/exp302_observable_marker_proxies/metrics.json`
- Report: `reports/exp302_observable_marker_proxies/README.md`
- Reproduction: `reproducibility/exp302_observable_marker_proxies/`
- 결론: 대회 공식 지표 Macro F1의 사전 gate를 통과하지 못해 `ARCHIVE`한다.
  Log Loss와 fold 안정성 개선은 보조 관찰로만 남기고 패널을 Public에 맞춰
  재조정하지 않는다. Track B isoform QC는 독립 분석으로 진행하지만 A+B 조합은
  열지 않는다.

### [EXP-276] nested decision offset 표본 게이트

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #276 / `issue-276-nested-decision-offset-sample-gate`
- 실행 source commit: `4f0b37d4227297b17a1ca0fac7db25e4c1b7fa06`
- 시작/종료: 2026-08-03T13:35:42.558759+00:00 /
  2026-08-03T14:24:01.845355+00:00

#### 실행과 결과

- 부모 EXP-219와 EXP-233의 inner cross-fitting을 유지하고, inner fold별 최소
  표본 수가 15/20/25 미만인 클래스의 offset을 0으로 고정했다.
- 사전 규칙상 대표 threshold는 20이며 DLBC와 ACC를 게이트했다.
- Fold Macro F1: 0.4184928039 / 0.4343256967 / 0.4116218011 /
  0.4253587083 / 0.4363321189
- OOF Macro F1: 0.4262111346 (EXP-219 대비 `+0.0039789886`)
- Fold 표준편차: 0.0093442830 (EXP-219 대비 `+0.0026238894`, 악화)
- Accuracy: 0.4146105467, Log Loss: 1.8718310623
  (EXP-219 대비 `+0.0242183158`, 악화)
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 산출물과 결론

- Config: `configs/exp276_nested_decision_offset_sample_gate.yaml`
- Metrics: `reports/exp276_nested_decision_offset_sample_gate/metrics.json`
- Threshold 비교: `reports/exp276_nested_decision_offset_sample_gate/threshold_comparison.json`
- Report: `reports/exp276_nested_decision_offset_sample_gate/README.md`
- threshold 20/25는 5개 fold 중 4개를 개선했지만 Log Loss와 fold 안정성
  gate를 통과하지 못해 `ARCHIVE`한다. 특정 클래스 offset을 0으로 고정해도
  다른 클래스 offset과의 argmax 경쟁 때문에 그 클래스 F1이 보호되지 않는다는
  한계를 확인했으며, 이 post-hoc offset 계열의 추가 탐색을 중단한다.

### [EXP-279] rolling-median Macro F1 checkpoint 안정화

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #279 / `issue-279-exp-checkpoint-rolling-median`
- 소스 commit: `e904bc0e9a3e409c5b7884dbe6bf512bf63be1b7`
- 시작/종료: 2026-08-03T13:40:16.833115+00:00 /
  2026-08-03T13:53:10.427522+00:00

#### 실행과 결과

- EXP-219의 모델·피처·canonical 5-fold·balanced weight·seed를 유지했다.
- 유일한 변경은 validation Macro F1의 trailing 21-iteration 중앙값이 가장 큰
  window의 마지막 iteration을 고른 것이다. 후보는 iteration 100 이상이고 동률은
  더 이른 iteration을 택하며 fallback은 없다.
- 선택 iteration: 202 / 236 / 253 / 121 / 179
- Fold Macro F1: 0.4185424302 / 0.4224270311 / 0.4093467651 /
  0.4197500569 / 0.4319890962
- OOF Macro F1: 0.4206209582 (EXP-219 대비 `-0.0016111878`)
- Fold 표준편차: 0.0072727214 (`+0.0005523279`)
- Accuracy: 0.4089662958, Log Loss: 1.8463063240 (`-0.0013064146`)
- 최악 클래스 F1 변화: LUAD `-0.0156934520`; `-0.05` 이상 붕괴 없음
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- Config: `configs/exp279_checkpoint_rolling_median.yaml`
- Metrics: `reports/exp279_checkpoint_rolling_median/metrics.json`
- Report: `reports/exp279_checkpoint_rolling_median/README.md`
- Reproduction: `reproducibility/exp279_checkpoint_rolling_median/`
- 저장 checkpoint 재추론에서 submission SHA-256과 test 라벨이 일치했고 확률
  최대 차이는 `1.43e-07`이었다.
- Macro F1 하락이 사전 허용치 `0.001`을 넘어 `ARCHIVE`한다. window나 minimum
  iteration을 같은 OOF에서 다시 탐색하지 않고 제출하지 않는다.

### [EXP-272] EXP-219 고정 5-seed 확률 평균

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #272 / `issue-272-exp219-multiseed-ensemble`
- 학습 소스 commit: `5913bf49e920d5e1ff36e9ff56bf9f16aa90f40b`
- 최종화 소스 commit: `61a1fe7b4864935cbf41a3793bfb0e3c48f67365`
- 시작/종료: 2026-08-03T13:17:21.394000+00:00 /
  2026-08-03T13:17:22.042664+00:00 (최종 고정 평균 생성 시간)

#### 실행과 결과

- 부모 EXP-219의 피처·canonical 5-fold·Macro-F1-best checkpoint 정책을 유지하고
  seed `42, 142, 242, 342, 442`를 각각 독립 학습했다.
- 결과를 보기 전에 고정한 `0.2`씩의 OOF/test 확률 평균만 평가했다.
- seed별 OOF Macro F1: 0.4222321460 / 0.4245190846 / 0.4246887695 /
  0.4238191001 / 0.4214180383
- Fold Macro F1: 0.4170648211 / 0.4298147148 / 0.4017862524 /
  0.4211686299 / 0.4342485967
- OOF Macro F1: 0.4208578157 (EXP-219 대비 `-0.0013743303`)
- Fold 표준편차: 0.0112937018 (EXP-219 대비 `+0.0045733083`)
- Accuracy: 0.4091275601, Log Loss: 1.8553646704
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- Config: `configs/exp272_exp219_multiseed_ensemble.yaml`
- Metrics: `reports/exp272_exp219_multiseed_ensemble/metrics.json`
- Report: `reports/exp272_exp219_multiseed_ensemble/README.md`
- Reproduction: `reproducibility/exp272_exp219_multiseed_ensemble/`
- seed 42는 EXP-219 원본 OOF·test 확률과 byte-level로 일치했다.
- 5-seed 고정 평균은 Macro F1, fold 안정성과 Log Loss가 모두 악화돼
  `ARCHIVE`한다. seed 제외·가중치 재탐색·리더보드 제출은 진행하지 않는다.

### [EXP-233] nested class-wise decision offset

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #233 / `issue-233-nested-decision-offset`
- 실행 source commit: `cfb2859962b62ca0599178d53be6173b035f4afb`
- 시작/종료: 2026-08-03T10:52:47.107640+00:00 /
  2026-08-03T11:36:58.896204+00:00

#### 실행과 결과

- 부모 EXP-219의 저장 OOF 확률에 outer-train 내부 3-fold cross-fitting으로
  학습한 26개 class-wise logit offset만 적용했다. outer validation과 test는
  offset 선택에 사용하지 않았다.
- Fold Macro F1: 0.4214118590 / 0.4250889014 / 0.4102364970 /
  0.4182223664 / 0.4350221884
- OOF Macro F1: 0.4241894920 (EXP-219 대비 `+0.0019573460`)
- Fold 표준편차: 0.0081500315 (EXP-219 대비 `+0.0014296379`, 악화)
- Accuracy: 0.4141267537, Log Loss: 1.8683398093
  (EXP-219 대비 `+0.0207270628`, 악화)
- DLBC F1은 `-0.1235` 하락했고 5개 outer fold 중 2개가 악화했다.
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 산출물과 결론

- Config: `configs/exp233_nested_decision_offset.yaml`
- Metrics: `reports/exp233_nested_decision_offset/metrics.json`
- 탐색 상세: `reports/exp233_nested_decision_offset/offset_search_detail.json`
- Report: `reports/exp233_nested_decision_offset/README.md`
- 전체 Macro F1은 올랐지만 극소수 클래스와 fold 안정성이 무너져 `ARCHIVE`한다.
  다만 DLBC를 제외한 25개 클래스는 모든 fold에서 개선되어, 후속 EXP-276에서
  저표본 클래스에 offset을 적용하지 않는 사전 고정 정책을 별도로 검증한다.

### [EXP-209] LightGBM + 동결 v2-performance

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #209 / `issue-209-exp-lightgbm-v2-performance`
- 소스 commit: `ec05d217aeed555e3beb18151920a07fe275dd6f`
- 시작/종료: 2026-08-02T14:21:59.123191+00:00 /
  2026-08-02T14:26:22.219111+00:00

#### 실행

- 부모: EXP-125
- 유일한 변경: 동결 Feature Spec `v1`을 `v2-performance`로 교체
- EXP-125 LightGBM 설정·balanced sample weight·canonical 5-fold 유지
- Config: `configs/exp209_lightgbm_v2_performance.yaml`
- Metrics: `reports/exp209_lightgbm_v2_performance/metrics.json`
- Report: `reports/exp209_lightgbm_v2_performance/README.md`

#### 결과

- Fold Macro F1: 0.4220673434, 0.4131394762, 0.4010844170,
  0.4139076091, 0.4409491801
- OOF Macro F1: 0.4188739423 (EXP-125 대비 `-0.0000338942`)
- Fold 표준편차: 0.0131867650 (EXP-125 대비 `+0.0050815918`)
- Accuracy: 0.4155781326 (EXP-125 대비 `+0.0012901145`)
- Log Loss: 1.8208257360 (EXP-125 대비 `-0.0019725059`)
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [`exp-209-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-209-repro-v1)

#### 결론

- Macro F1은 EXP-125와 사실상 동률이고 Log Loss는 소폭 개선됐지만, 사전 기준인
  Macro F1 `+0.001`을 넘지 못하고 fold 표준편차가 허용치보다 악화돼 `ARCHIVE`다.
- 저장 checkpoint 재추론에서 OOF·test 라벨 100%, 확률 최대 절대 차이 0,
  제출 CSV SHA-256 일치를 확인했다.
- 이 조합을 추가 튜닝하거나 제출하지 않고, 모델 구조가 다른 OvR XGBoost를 별도
  Experiment Issue에서 검증한다.
| 2026-08-02T15:08:02+00:00 | EXP-151 | fabxoe | `17d433f81cf41fce54045739b0531915cc89b565` / [`exp-151-repro-v2`](https://github.com/fabxoe/open_cancer/releases/tag/exp-151-repro-v2) | SHA-256 일치 | 제출 SHA-256·test 라벨 100% 일치; GPU→CPU 확률 차이와 OOF 라벨 99.9839% 일치 기록 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp151_mutated_gene_burden/comparison.json) |
| 2026-08-02T15:08:02+00:00 | EXP-188 | fabxoe | `1ff0663af2f682229d715136119e8e1db6bace62` / [`exp-188-repro-v2`](https://github.com/fabxoe/open_cancer/releases/tag/exp-188-repro-v2) | SHA-256 일치 | 제출 SHA-256·OOF/test 라벨·확률 100% 일치 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp188_c1_phi_jaccard_pruning/comparison.json) |
| 2026-08-02T15:58:51.992672+00:00 | EXP-219 | fabxoe | `41d07096e1c87eb55e7d7a73645629ea3d0952e3` / [`exp-219-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-219-repro-v1) | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.45e-07; Issue #258에서 원본 Release 복구 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp219_macro_f1_checkpoint_selection/comparison.json) |
| 2026-08-02T17:02:54.418077+00:00 | EXP-223 | 2heej | `41eaafc17f286ebc38568d076df5bf16fd0626ac` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.44e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp223_pathway_macro_f1_checkpoint/comparison.json) |
| 2026-08-03T02:34:48.643447+00:00 | EXP-156 | Gomin-art | `5b1cff179ee68bc8f873f4f9dd4c73305aec3e65` / 태그 없음 | SHA-256 일치 | 제출 SHA-256·test 라벨 100% 일치, 확률 최대 차이 5.93e-08 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp156_gene_variant_effect_compression/comparison.json) |
| 2026-08-03T02:18:40.740535+00:00 | EXP-229 | 2heej | `75977326ab526f0b4c34ad5af90b29fb833c44c6` / [`exp-229-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-229-repro-v1) | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.72e-7; Issue #260에서 원본 Release 복구 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp229_pathway_mutation_types/comparison.json) |
| 2026-08-03T03:06:15.409629+00:00 | EXP-232 | 2heej | `7a940bcaae6cd1bb36f3c9d5e5d3296c8ce1b88c` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.36e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp232_pathway_group_selection/comparison.json) |
| 2026-08-03T05:00:25.503797+00:00 | EXP-237 | 2heej | `bbebdf139bee3002b542015097ce8b2bc46fbe71` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.47e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp237_pathway_mutation_fractions/comparison.json) |
| 2026-08-03T05:39:49.632899+00:00 | EXP-240 | 2heej | `b78e45c959a5f937bae3f7c5a5bc71978c4152fd` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.34e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp240_molecular_constellations/comparison.json) |
| 2026-08-03T06:09:06.168833+00:00 | EXP-245 | 2heej | `7c755756a19eb721cdfe58dfab0798dac3ba9957` / 태그 없음 | SHA-256 일치 | 제출 SHA-256 일치, test 라벨 100%, 확률 최대 차이 1.27e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp245_lineage_mechanism_patterns/comparison.json) |
| 2026-08-03T06:54:33.822207+00:00 | EXP-250 | 2heej | `7f93b2f8be49e3d01cdd6b2442da0a5b6787488c` / 태그 없음 | SHA-256 일치 | 데이터·제출 SHA-256과 test 라벨 일치, 확률 최대 차이 1.20e-7 | 미실행 | INFERENCE_VERIFIED | [comparison](reproducibility/exp250_lineage_group_selection/comparison.json) |
| 2026-08-03T08:18:31+00:00 | EXP-253 | 2heej | `b9d296ea164beb4b33e5797b7b1b08eee45f54f9` / [`exp-253-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-253-repro-v1) | SHA-256 일치 | OOF·test 라벨 100%, 확률 최대 차이 0, 제출 SHA-256 일치; 부모 원본 포함 Release 복구 | 미실행(결정론적 확률 평균) | INFERENCE_VERIFIED | [comparison](reproducibility/exp253_lightgbm_xgboost_blend/comparison.json) |
### [EXP-235] OncoNPC 스타일 nested-CV XGBoost 및 pmax 신뢰도 분석

- 상태: COMPLETED
- 실행자: Gomin-art
- Issue/브랜치: #235 / `issue-235-exp-onconpc-xgb-confidence`
- 소스 commit: `f3efedce60aafebf8831a4f4cbc4a04e413bc6c8`
- 시작/종료: 2026-08-03T10:13:00.992767+00:00 /
  2026-08-03T11:44:37.831205+00:00

#### 실행과 결과

- 부모: EXP-094 / 동결 Feature Spec v1
- 각 canonical outer-train fold 안에서 2-fold·2-trial randomized nested CV를
  수행하고 inner Macro F1로 XGBoost 하이퍼파라미터를 선택했다.
- Fold Macro F1: 0.4194400582 / 0.4311095113 / 0.4268554648 /
  0.4082084479 / 0.4366031080
- OOF Macro F1: 0.4255728433 (EXP-094 대비 `+0.0086862694`, 기존 최고
  EXP-253 대비 `+0.0000729614`)
- Fold 표준편차: 0.0098663133 (EXP-253 대비 `-0.0019136601`)
- Accuracy: 0.4160619255 (EXP-253 대비 `+0.0024189647`)
- Log Loss: 1.8073006993 (EXP-253 대비 `-0.0030244663`)
- pmax 0.5 / 0.7 / 0.9 coverage: 0.3821964199 / 0.1999677471 /
  0.0935333011; 해당 부분집합 Macro F1: 0.6535250009 / 0.6944774203 /
  0.8896281940
- Public LB: `0.302936084` (제출 ID `1509972`,
  2026-08-03T23:36:42+09:00)
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- Config: `configs/exp235_onconpc_xgb_confidence.yaml`
- Metrics: `reports/exp235_onconpc_xgb_confidence/metrics.json`
- Report: `reports/exp235_onconpc_xgb_confidence/README.md`
- Reproduction: `reproducibility/exp235_onconpc_xgb_confidence/`
- Release: [`exp-235-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-235-repro-v1)
- 결론: EXP-253을 근소하게 넘고 fold 변동성과 Log Loss도 개선했지만 Public은
  EXP-223보다 `-0.020307441` 낮았다. 단독 제출 후보와 앙상블 부모에서 제외하고
  Local 진단 결과만 보존한다.
- pmax는 canonical OOF의 사후 진단에만 사용했다. 높은 임계값의 성능 상승은 낮은
  coverage와 클래스 support 감소를 동반하므로 calibration·모델 선택·test 라벨
  후처리나 제출 행 필터링에 사용하지 않는다.
- 저장 checkpoint 재추론에서 제출 SHA-256과 test 라벨이 일치했고 확률 최대 절대
  차이는 `5.58e-08`로 허용치 이내였다.

### [EXP-253] LightGBM·XGBoost 고정 확률 평균

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #253 / `issue-253-exp-lightgbm-xgboost-blend`
- 소스 commit: `b9d296ea164beb4b33e5797b7b1b08eee45f54f9`
- 시작/종료: 2026-08-03T08:18:30.617661+00:00 /
  2026-08-03T08:18:31.143311+00:00

#### 실행과 결과

- 구성: EXP-209 LightGBM과 EXP-229 XGBoost OOF/test 확률의 고정 0.5/0.5 평균
- 공용 split·클래스 순서 유지, 다른 가중치와 Public LB 미탐색
- Fold Macro F1: 0.4204437403 / 0.4242324556 / 0.4163290146 /
  0.4179312082 / 0.4484189232
- OOF Macro F1: 0.4254998819 (EXP-229 대비 `+0.0025113074`)
- Fold 표준편차: 0.0117799734 (EXP-229 대비 `+0.0019120085`)
- Accuracy: 0.4136429608, Log Loss: 1.8103251656
- Public LB: 0.3054410279 (제출 ID `1509964`, 2026-08-03 23:32:05 KST)
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [`exp-253-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-253-repro-v1)

#### 산출물과 결론

- Config: `configs/exp253_lightgbm_xgboost_blend.yaml`
- Metrics: `reports/exp253_lightgbm_xgboost_blend/metrics.json`
- Report: `reports/exp253_lightgbm_xgboost_blend/README.md`
- Reproduction: `reproducibility/exp253_lightgbm_xgboost_blend/`
- 결론: Local 기준은 통과했지만 EXP-223 Public 대비 `-0.0178024971`로 하락해
  최종 제출 후보에서 제외한다. 가중치 grid search는 이 실험에 소급 적용하지 않는다.

### [EXP-250] 암종별 변이 패턴 그룹 선택

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #250 / `issue-250-exp-lineage-group-selection`
- 소스 commit: `7f93b2f8be49e3d01cdd6b2442da0a5b6787488c`
- 시작/종료: 2026-08-03T06:24:59.600090+00:00 /
  2026-08-03T06:54:32.580654+00:00

#### 실행과 결과

- 부모: EXP-245, 성능 비교 기준: EXP-229
- 각 outer-fold train에서만 3개 inner fold permutation importance로 암종 그룹 선택
- Fold Macro F1: 0.4052276412 / 0.4162065321 / 0.4192499206 /
  0.4252393163 / 0.4447121221
- OOF Macro F1: 0.4209182565 (EXP-245 대비 `-0.0004806995`,
  EXP-229 대비 `-0.0020703180`)
- Fold 표준편차: 0.0130283698, Accuracy: 0.4117077891,
  Log Loss: 2.0532255173
- 선택 피처 수: fold별 27 / 27 / 31 / 31 / 27개
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- Config: `configs/exp250_lineage_group_selection.yaml`
- Metrics: `reports/exp250_lineage_group_selection/metrics.json`
- Report: `reports/exp250_lineage_group_selection/README.md`
- Reproduction: `reproducibility/exp250_lineage_group_selection/`
- 결론: 대부분의 그룹을 유지하면서 EXP-245·229 대비 Macro F1, 안정성,
  Log Loss가 모두 악화돼 `ARCHIVE`. 동일 selector 조정은 중단한다.

### [EXP-245] 암종별 핵심 변이 패턴 확장

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #245 / `issue-245-exp-lineage-mechanism-patterns`
- 소스 commit: `7c755756a19eb721cdfe58dfab0798dac3ba9957`
- 시작/종료: 2026-08-03T05:58:26.576286+00:00 /
  2026-08-03T06:09:04.837755+00:00

#### 실행과 결과

- 부모: EXP-229
- EXP-240 단순 조합 피처는 유지하지 않고, 8개 암종 문헌 고정 module의
  missense/LoF/context/mixed mechanism proxy 32개만 추가
- semantic equivalence 검사 후 모든 fold에서 31개 유지
- Fold Macro F1: 0.4161807057 / 0.4129769610 / 0.4192499206 /
  0.4252393163 / 0.4365823625
- OOF Macro F1: 0.4213989560 (EXP-229 대비 `-0.0015896185`,
  EXP-240 대비 `+0.0024345095`)
- Fold 표준편차: 0.0083182968 (EXP-229 대비 `-0.0015496681`, 개선)
- Accuracy: 0.4138042251 (EXP-229 대비 `+0.0012901145`)
- Log Loss: 2.0266003609 (EXP-229 대비 `+0.1756390333`, 악화)
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 결론

- EXP-240보다 개선됐지만 사전 채택 기준인 EXP-229 대비 Macro F1 `+0.001`을
  충족하지 못하고 Log Loss가 크게 악화돼 **ARCHIVE**한다.
- 클래스별 큰 양·음의 변화가 함께 나타났으며, canonical OOF를 보고 유리한
  module만 고정 선택하지 않는다.
- 문헌은 고정 그룹·계산 규칙에만 사용했고 외부 환자 데이터와 SUBCLASS는
  사용하지 않았다.
- 저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이 `1.27e-7`,
  제출 CSV SHA-256 일치를 확인했다.
- Metrics/Report: `reports/exp245_lineage_mechanism_patterns/`

### [EXP-240] 암종별 분자 변이조합 피처

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #240 / `issue-240-exp-molecular-constellations`
- 소스 commit: `b78e45c959a5f937bae3f7c5a5bc71978c4152fd`
- 시작/종료: 2026-08-03T05:30:43.978096+00:00 /
  2026-08-03T05:39:48.243967+00:00

#### 실행과 결과

- 부모: EXP-229
- 유일한 변경: 문헌 고정 암종 관련 유전자 모듈 7개에서 변이 유전자 수,
  2개 이상 변이 indicator, core-partner 동시 변이 indicator 총 21개 추가
- EXP-229 모델·seed·canonical fold·Macro-F1 checkpoint 정책 유지
- Fold Macro F1: 0.4111364436 / 0.4158148112 / 0.4168731475 /
  0.4211156347 / 0.4334184125
- OOF Macro F1: 0.4189644465 (EXP-229 대비 `-0.0040241280`)
- Fold 표준편차: 0.0075711973 (EXP-229 대비 `-0.0022967677`, 개선)
- Accuracy: 0.4097726173 (EXP-229 대비 `-0.0027414933`)
- Log Loss: 1.9418441057 (EXP-229 대비 `+0.0908827782`, 악화)
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 결론

- Macro F1 채택 기준을 충족하지 못하고 Log Loss가 크게 악화돼 **ARCHIVE**한다.
- 일부 클래스의 양의 변화는 관찰됐지만 모든 모듈을 동시에 추가했으므로 개별
  모듈의 효과로 해석하거나 canonical OOF를 보고 고정 선택하지 않는다.
- 외부 환자 데이터와 SUBCLASS는 사용하지 않았으며 문헌은 고정 그룹·관계 정의에만
  사용했다.
- 저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이 `1.34e-7`,
  제출 CSV SHA-256 일치를 확인했다.
- Metrics/Report: `reports/exp240_molecular_constellations/`

### [EXP-237] pathway별 변이 종류 fraction

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #237 / `issue-237-exp-pathway-mutation-fractions`
- 소스 commit: `bbebdf139bee3002b542015097ce8b2bc46fbe71`
- 시작/종료: 2026-08-03T04:50:45.588215+00:00 /
  2026-08-03T05:00:23.952096+00:00

#### 실행과 결과

- 부모: EXP-229
- 유일한 변경: 10개 pathway×5개 변이종류 affected-gene raw count를
  pathway mutated-gene count로 나눈 fraction으로 교체
- 기존 pathway mutated/LoF count 20개, 모델·seed·canonical fold·validation
  Macro-F1-best checkpoint 정책 유지
- semantic equivalence 검사 후 총 pathway 피처 수: 63 / 64 / 64 / 64 / 63개
- Fold Macro F1: 0.4137518575 / 0.4216749790 / 0.4206987516 /
  0.4165303883 / 0.4352217755
- OOF Macro F1: 0.4204138300 (EXP-229 대비 `-0.0025747446`)
- Fold 표준편차: 0.0073981342 (EXP-229 대비 `-0.0024698307`, 개선)
- Accuracy: 0.4110627318 (EXP-229 대비 `-0.0014513788`)
- Log Loss: 1.9345345497 (EXP-229 대비 `+0.0835732222`, 악화)
- 클래스별 최대 개선: KIRC `+0.0673780757`, LGG `+0.0432729610`
- 클래스별 최대 하락: DLBC `-0.0345260515`, STES `-0.0318418212`,
  CESC `-0.0300404514`
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 결론

- Macro F1 `+0.001` 채택 기준을 충족하지 못하고 Log Loss가 크게 악화돼
  **ARCHIVE**한다.
- fold 1과 3의 Macro-F1-best checkpoint가 각각 iteration 32와 59로 매우
  이르게 선택되어 확률 품질이 불안정했다. fraction이 raw count보다 나은 신호를
  제공했다고 해석하지 않는다.
- EXP-232 선택 결과와 Public LB는 피처 정의나 판단에 사용하지 않았다.
- 저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이 `1.47e-7`,
  제출 CSV SHA-256 일치를 확인했다.
- Metrics/Report: `reports/exp237_pathway_mutation_fractions/`

### [EXP-232] nested pathway group permutation 선택

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #232 / `issue-232-exp-pathway-group-selection`
- 소스 commit: `7a940bcaae6cd1bb36f3c9d5e5d3296c8ce1b88c`
- 시작/종료: 2026-08-03T02:38:47.392984+00:00 /
  2026-08-03T03:06:13.825826+00:00

#### 실행과 결과

- 부모: EXP-229
- 각 outer-fold 학습 행 안에서만 3-fold group permutation importance를 계산
- pathway group이 inner fold 3개 중 2개 이상에서 양의 delta이고 평균 delta도
  양수일 때만 해당 pathway의 변이종류 피처를 유지
- 선택 pathway 수: 1 / 4 / 3 / 5 / 3개
- 선택 후보 피처 수: 4 / 18 / 13 / 21 / 12개
- Fold Macro F1: 0.4226803937 / 0.4209928029 / 0.4103250276 /
  0.4141375814 / 0.4366236146
- OOF Macro F1: 0.4214874085 (EXP-229 대비 `-0.0015011660`)
- Fold 표준편차: 0.0090327997 (EXP-229 대비 `-0.0008351652`)
- Accuracy: 0.4109014675 (EXP-229 대비 `-0.0016126431`)
- Log Loss: 1.8429074287 (EXP-229 대비 `-0.0080538988`, 개선)
- EXP-223 대비 OOF Macro F1: `+0.0001134609`(사실상 동률)
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 선택 진단과 결론

- outer fold별 선택 빈도: cell_cycle 4회, notch 3회, nrf2·rtk_ras·tgf_beta
  각 2회, hippo·pi3k·tp53 각 1회
- 피처 압축과 fold 안정성·Log Loss 개선은 확인했지만, 사전 기준인 “EXP-229
  Macro F1 비하락”을 충족하지 못해 **ARCHIVE**한다.
- outer-fold 선택 빈도를 보고 같은 canonical split에서 고정 pathway를 다시
  선택하면 validation 정보가 간접 재사용될 수 있으므로, 이 결과만으로 새 고정
  피처를 채택하지 않는다.
- 저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이 `1.36e-7`,
  제출 CSV SHA-256 일치를 확인했다.
- Metrics/Report: `reports/exp232_pathway_group_selection/`

### [EXP-229] pathway별 변이 종류 유전자 수

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #229 / `issue-229-exp-pathway-mutation-types`
- 소스 commit: `75977326ab526f0b4c34ad5af90b29fb833c44c6`
- 시작/종료: 2026-08-03T02:08:57.156965+00:00 /
  2026-08-03T02:18:38.919954+00:00

#### 실행과 결과

- 부모: EXP-223
- EXP-223의 피처·XGBoost·balanced sample weight·canonical fold·validation
  Macro-F1-best checkpoint 정책 유지
- 유일한 변경: 10개 고정 pathway 각각에 missense·synonymous·nonsense·
  frameshift·complex 변이 유전자 수 50개 후보 추가
- fold-train semantic equivalence 검사 후 총 pathway 피처 수는 fold별
  62 / 63 / 63 / 63 / 62개(부모 20개 포함)
- Fold Macro F1: 0.4125153614 / 0.4227302800 / 0.4172366349 /
  0.4221575240 / 0.4415264445
- OOF Macro F1: 0.4229885745 (EXP-223 대비 `+0.0016146270`)
- Fold 표준편차: 0.0098679649 (EXP-223 대비 `+0.0006339596`)
- Accuracy: 0.4125141106 (EXP-223 대비 `+0.0012901145`)
- Log Loss: 1.8509613276 (EXP-223 대비 `+0.0067992210`, 악화)
- 클래스별 최대 개선: DLBC `+0.0502645503`, LUAD `+0.0340388007`,
  UCEC `+0.0239808153`
- 클래스별 최대 하락: LAML `-0.0422523477`, PAAD `-0.0325077967`,
  TGCT `-0.0196246430`
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [`exp-229-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-229-repro-v1)

#### 결론

- Macro F1 `+0.001` 이상, fold 표준편차 악화 `<0.002`, 클래스별 최대 하락
  `<0.05` 조건을 모두 통과해 **조건부 채택**한다.
- 5개 fold 중 4개가 개선됐지만 fold 2는 약 `-0.000925` 하락했고 Log Loss도
  악화됐다. 따라서 큰 개선으로 단정하지 않고 제출 전 후보로 보존한다.
- 저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이 `1.72e-7`,
  제출 CSV SHA-256 일치를 확인했다.
- Metrics/Report: `reports/exp229_pathway_mutation_types/`

### [EXP-223] pathway XGBoost Macro F1 checkpoint 선택

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #223 / `issue-223-exp-pathway-macro-f1-checkpoint`
- 소스 commit: `41eaafc17f286ebc38568d076df5bf16fd0626ac`
- 시작/종료: 2026-08-02T16:53:36.447851+00:00 /
  2026-08-02T17:02:52.651353+00:00

#### 실행과 결과

- 부모: EXP-096
- EXP-096 피처·모델·seed·canonical fold 유지
- 유일한 변경: validation mlogloss-best 대신 Macro-F1-best checkpoint 저장
- Fold Macro F1: 0.4109700215 / 0.4210640745 / 0.4181611577 /
  0.4172319385 / 0.4384246233
- OOF Macro F1: 0.4213739476 (EXP-096 대비 `+0.0032586396`)
- Fold 표준편차: 0.0092340053 (EXP-096 대비 `-0.0002581124`)
- Accuracy: 0.4112239961 (EXP-096 대비 `+0.0033865506`)
- Log Loss: 1.8441621065 (보조 지표, EXP-096 대비 `+0.0072278976`)
- 클래스별 최악 변화: THYM `-0.0152823920`
- Public LB: `0.323243525` (제출 ID `1509283`, 2026-08-03 10:30:33
  KST). EXP-031 대비 `+0.0061631401`로 팀 최고 Public 점수를 갱신했다.
- 2026-08-03 19:13 KST 재확인: 팀 대표 제출은 계속 EXP-223이며 플랫폼의
  반올림 표시 점수는 `0.32324`, 팀 제출 수는 17회, 공식 팀 순위는 참가
  4팀 중 4위였다. 정확한 제출 점수 `0.323243525`는 변경되지 않았다.
### [EXP-211] One-vs-Rest XGBoost + v2-performance

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #211 / `issue-211-exp-ovr-xgboost-v2-performance`
- 소스 commit: `38955bcb7f1a0e8d72e933fd9fa4d48bd1a7873a`
- 시작/종료: 2026-08-02T14:59:31.061759+00:00 /
  2026-08-02T16:32:46.152425+00:00

#### 실행

- 부모: EXP-096
- Feature Spec `v2-performance`, canonical 5-fold와 tree 설정 유지
- 유일한 변경: multiclass XGBoost를 26개 OvR binary XGBoost로 교체
- binary class weight는 각 outer-fold 학습 행에서만 계산
- Config: `configs/exp211_ovr_xgboost_v2_performance.yaml`
- Metrics: `reports/exp211_ovr_xgboost_v2_performance/metrics.json`
- Report: `reports/exp211_ovr_xgboost_v2_performance/README.md`

#### 결과

- Fold Macro F1: 0.4215797651, 0.4019137795, 0.4006264832,
  0.4160726895, 0.4097042237
- OOF Macro F1: 0.4112914798 (EXP-096 대비 `-0.0068238282`)
- Fold 표준편차: 0.0080536160 (EXP-096 대비 `-0.0014385016`)
- Accuracy: 0.4091275601 (EXP-096 대비 `+0.0012901145`)
- Log Loss: 1.8769391573 (EXP-096 대비 `+0.0400049484`)
- Runtime: 5,595.09초
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 결론

- 사전 성능·안정성·클래스 붕괴 기준을 통과해 채택하고 제출 후보로 보존한다.
- validation checkpoint 선택의 낙관 편향 가능성은 Public 또는 독립 반복에서
  계속 관찰한다.
- 저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이 `1.44e-7`,
  제출 CSV SHA-256 일치를 확인했다.
- 후속은 pathway별 변이 종류 구성 피처를 별도 Experiment Issue에서 검증한다.
- 안정성은 소폭 개선됐지만 Macro F1과 Log Loss가 모두 채택 기준보다 나빠
  `ARCHIVE`한다. 제출과 OvR 추가 튜닝은 진행하지 않는다.
- 저장 checkpoint 재추론에서 OOF·test 라벨 100%, 확률 최대 절대 차이
  `2.12e-7`, 제출 CSV SHA-256 일치를 확인했다.
- 다음 실험은 EXP-219에서 채택된 validation Macro-F1 checkpoint 정책을
  EXP-096 v2-performance에 독립 적용한다.

### [EXP-196] S4 TruncatedSVD 저차원 비교 모델

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #196 / `issue-196-s4-truncated-svd`
- 소스 commit: `eff4538a7c12dc6af465cddcd5f8614a0374d7a6`
- 시작/종료: 2026-08-02T16:05:25.678718+00:00 /
  2026-08-02T16:09:07.810346+00:00

#### 실행과 결과

- Config: `configs/exp196_s4_truncated_svd.yaml`
- Runner: `scripts/run_exp196_s4_truncated_svd.py`
- Metrics: `reports/exp196_s4_truncated_svd/metrics.json`
- 각 outer-train의 4,384개 mutation-presence에만 TruncatedSVD 256차원을
  fit하고 sample aggregate·고정 hotspot을 passthrough했다. validation·test는
  저장된 fold projector만 사용했고 checkpoint는 validation Macro F1로 골랐다.
- Fold Macro F1: 0.311846 / 0.351196 / 0.362893 / 0.360420 / 0.354315
- OOF Macro F1: 0.3496748557 (EXP-094 대비 `-0.0672117181`)
- Fold 표준편차: 0.0186183177 (EXP-094 대비 `+0.0107340657`)
- Log Loss: 2.0729362413 (보조 지표, `+0.2329989120`)
- DLBC F1: 0.0930232558 (클래스별 최악 변화 `-0.2843352348`)
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE`

#### 결론

저차원 선형 투영이 희소한 암종별 유전자 신호를 크게 훼손해 모든 핵심 gate에
실패했다. `ARCHIVE`하며 SVD 차원·iteration을 추가 탐색하거나 제출하지 않는다.
상세 내용은 [보고서](reports/exp196_s4_truncated_svd/README.md)를 참고한다.

### [EXP-219] Macro F1 checkpoint 선택 통제 비교

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #219 / `issue-219-exp094-macro-f1-checkpoint`
- 소스 commit: `41d07096e1c87eb55e7d7a73645629ea3d0952e3`
- 시작/종료: 2026-08-02T15:44:59.717503+00:00 /
  2026-08-02T15:55:32.748276+00:00

#### 실행과 결과

- Config: `configs/exp219_macro_f1_checkpoint_selection.yaml`
- Runner: `scripts/run_exp219_macro_f1_checkpoint_selection.py`
- Metrics: `reports/exp219_macro_f1_checkpoint_selection/metrics.json`
- EXP-094와 feature·canonical fold·seed·XGBoost 설정은 동일하며, 각 fold
  validation에서 checkpoint를 고르는 기준만 mlogloss 최소에서 Macro F1 최대로
  변경했다. test와 Public LB는 선택에 사용하지 않았다.
- 기존 mlogloss-best OOF Macro F1: 0.4168865739
- Macro-F1-best OOF Macro F1: 0.4222321460 (`+0.0053455721`)
- Fold Macro F1: 0.4211513302 / 0.4235533012 / 0.4113978176 /
  0.4214009350 / 0.4324842903
- Fold 표준편차: 0.0067203936 (기존 대비 `-0.0011638585`)
- Log Loss: 1.8476127386 (보조 지표, 기존 대비 `+0.0076756477`)
- 클래스별 최악 변화: HNSC `-0.0103647851`; DLBC는 `+0.0512129380`
- Public LB: 미제출
- 저장 checkpoint 재추론으로 제출 SHA-256 일치, test 라벨 100%, 확률 최대
  차이 1.45e-07을 확인해 `INFERENCE_VERIFIED`다.
- 원본 checkpoint·OOF·test 확률은 Task Issue #258에서 기존 manifest SHA-256과
  다시 대조한 뒤 [`exp-219-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-219-repro-v1)에
  보존했다. 번들 SHA-256은
  `fa293ed92a21508e0752890ca407c6e55cbc8794688262bacff471fd6739bf25`다.
- 다른 플랫폼의 재학습 결과는 원본과 일치하지 않아 이 번들에 포함하지 않았고,
  플랫폼 간 재학습 차이는 Issue #238에서 별도로 추적한다.

#### 결론

공식 지표 정렬 효과가 명확하고 fold 안정성도 개선되어 향후 XGBoost 실험의
기본 checkpoint 선택 후보로 채택한다. 과거 결과를 일괄 재학습하지 않으며,
validation iteration 선택의 낙관 편향 가능성은 후속 독립 실험에서 계속 감시한다.
상세 내용은 [보고서](reports/exp219_macro_f1_checkpoint_selection/README.md)를
참고한다.

### [EXP-207] S3 Boruta feature selection

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #207 / `issue-207-s3-boruta-feature-selection`
- 소스 commit: `ddee2248c9aedaa518fc5e305d1d7f0ba1138f9e`
- 시작/종료: 2026-08-02T14:15:53.550629+00:00 /
  2026-08-02T15:30:46.334105+00:00

#### 실행과 결과

- Config: `configs/exp207_s3_boruta_feature_selection.yaml`
- Runner: `scripts/run_exp207_s3_boruta_feature_selection.py`
- Metrics: `reports/exp207_s3_boruta_feature_selection/metrics.json`
- canonical outer-train에서만 Boruta를 fit했고 fold별 confirmed gene은
  18 / 16 / 15 / 18 / 17개였다.
- Fold Macro F1: 0.3457348416 / 0.3384758616 / 0.3420677438 /
  0.3507670103 / 0.3604855979
- OOF Macro F1: 0.3484416378 (EXP-094 대비 `-0.0684449361`)
- Fold 표준편차: 0.0076597543 (EXP-094 대비 `-0.0002244977`)
- Accuracy: 0.3534913724
- Log Loss: 2.0194741289 (보조 지표, EXP-094 대비 `+0.1795367996`)
- DLBC F1: 0.0, 클래스별 최악 하락: `-0.3773584906`
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE`

#### 결론

안전 종료 하한 10개는 통과했지만 강한 유전자 15~18개만 남겨 26개 암종의
약한 보완 신호를 과도하게 제거했다. 공식 Macro F1과 소수 클래스 F1이 크게
붕괴했으므로 `ARCHIVE`하며 Boruta 설정을 결과에 맞춰 재튜닝하지 않는다.
상세 해석과 산출물은
[보고서](reports/exp207_s3_boruta_feature_selection/README.md)를 참고한다.

### [EXP-205] S2 mRMR feature selection

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #205 / `issue-205-s2-mrmr-feature-selection`
- 소스 commit: `67f89640cde3939141eede151bd3d965e53941c2`
- 시작/종료: 2026-08-02T12:49:23.804304+00:00 /
  2026-08-02T12:51:32.006984+00:00

#### 실행

- Config: `configs/exp205_s2_mrmr_feature_selection.yaml`
- Runner: `scripts/run_exp205_s2_mrmr_feature_selection.py`
- Metrics: `reports/exp205_s2_mrmr_feature_selection/metrics.json`
- Report: `reports/exp205_s2_mrmr_feature_selection/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 각 outer fold의 학습 행에서만 양성 수 5 이상 `GENE__mutated` 열을 후보로 두고,
  target과의 discrete MI relevance에서 이미 선택한 유전자와의 binary normalized MI
  redundancy 평균을 뺀 greedy mRMR-MID로 128개를 골랐다.
- 선택 유전자의 v1 유전자 블록 전체와 sample aggregate·fixed hotspot은 유지했고,
  validation·test에는 저장한 fold별 같은 mask만 적용했다. balanced sample weight는
  유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.4042948622, 0.3988811270, 0.3769138837, 0.3976361619,
  0.4065986888
- OOF Macro F1: 0.3976963538 (EXP-094 대비 `-0.0191902201`)
- Fold 표준편차: 0.0105133634 (EXP-094 대비 `+0.0026291113`)
- Accuracy: 0.3962264151
- Log Loss: 1.8825673362 (EXP-094 대비 `+0.0426300069`)
- fold별 후보 유전자 수: 4,143, 4,119, 4,138, 4,144, 4,129; 선택 수는 모두 128개
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE` — 원 학습 checkpoint·fold별 selection mask·OOF/test
  확률·submission manifest는 저장했으나 독립 checkpoint inference 비교는 아직
  수행하지 않았다.

#### 결론

- mRMR 선택 목록은 생물학적으로 납득 가능한 recurrent gene을 반복 포함했지만,
  128개 유전자로의 압축은 전체 Feature Spec v1보다 Macro F1·안정성·Log Loss가
  모두 나빠 `ARCHIVE`다.
- S2의 사전 고정 규칙은 결과를 보고 재튜닝하지 않는다. 다음 사전 등록 단계인 S3
  Boruta를 독립 Experiment Issue에서 실행한다.

### [EXP-203] S1 Elastic Net stability selection

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #203 / `issue-203-s1-elastic-net-stability-selection`
- 소스 commit: `fb0c25c74339b04f887bea19e307fd5472f8a227`
- 시작/종료: 2026-08-02T11:53:20.641649+00:00 /
  2026-08-02T12:40:59.764236+00:00

#### 실행

- Config: `configs/exp203_s1_elastic_net_stability_selection.yaml`
- Runner: `scripts/run_exp203_s1_elastic_net_stability_selection.py`
- Metrics: `reports/exp203_s1_elastic_net_stability_selection/metrics.json`
- Report: `reports/exp203_s1_elastic_net_stability_selection/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 각 outer fold의 학습 행에서만 `GENE__mutated` 4,384개를 대상으로 3-fold inner
  CV와 one-SE 규칙으로 `C`를 정했다. 이어 75% stratified subsample 20회에서
  `l1_ratio=0.5` Elastic Net을 fit해 16회 이상 선택된 gene을 채택하고 최소 50개,
  최대 512개로 고정했다.
- 선택된 gene의 v1 유전자 블록 전체와 sample aggregate·fixed hotspot은 유지했고,
  validation·test에는 저장한 fold별 동일 mask를 적용했다. balanced sample weight는
  유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.2917453760, 0.3136269311, 0.2967567243, 0.2819547224,
  0.3075216276
- OOF Macro F1: 0.2996289845 (EXP-094 대비 `-0.1172575894`)
- Fold 표준편차: 0.0112469010 (EXP-094 대비 `+0.0033626489`)
- Accuracy: 0.2981777133
- Log Loss: 2.2033321396 (EXP-094 대비 `+0.3633948103`)
- 모든 fold가 `C=1.0`을 선택했고, frequency threshold를 통과한 gene 수는
  4,003~4,038개였다. 최대 512개 상한이 모든 fold에서 작동했다.
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE` — 원 학습 checkpoint·fold별 selection mask·OOF/test
  확률·submission manifest는 저장했으나 독립 checkpoint inference 비교는 아직
  수행하지 않았다.

#### 결론

- 성능·간소화 gate를 모두 크게 벗어나 `ARCHIVE`다. selector가 충분히 희소하지 않아
  cap 기반 절단이 발생했고, 원본 변이 정보 감소가 큰 성능 하락으로 이어졌다.
- S1의 사전 고정 규칙은 결과를 보고 재튜닝하지 않는다. 다음 사전 등록 단계인 S2
  mRMR를 독립 Experiment Issue에서 실행한다.

### [EXP-192] R2 희귀 mutation-presence filter

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #192 / `issue-192-r2-rare-mutation-filter`
- 소스 commit: `e48fdcdc3ee445c2047f729f63c9e128439c48da`
- 시작/종료: 2026-08-02T10:50:11.542188+00:00 /
  2026-08-02T10:58:56.619577+00:00

#### 실행

- Config: `configs/exp192_r2_rare_mutation_presence_filter.yaml`
- Runner: `scripts/run_exp192_r2_rare_mutation_presence_filter.py`
- Metrics: `reports/exp192_r2_rare_mutation_presence_filter/metrics.json`
- Report: `reports/exp192_r2_rare_mutation_presence_filter/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: 각 canonical outer fold의 **학습 행에서만** 양성 수가 5 미만인
  `GENE__mutated` 열을 제거했다. 같은 유전자의 mutation-type, missing,
  residue-position 열과 sample aggregate·hotspot 피처는 유지했고,
  validation·test에는 저장한 fold별 같은 mask만 적용했다.
- balanced sample weight는 유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.4110539119, 0.4251178894, 0.3917771908, 0.4230024391,
  0.4367275115
- OOF Macro F1: 0.4176058118 (EXP-094 대비 `+0.0007192379`)
- Fold 표준편차: 0.0152395199 (EXP-094 대비 `+0.0073552678`)
- Accuracy: 0.4083212385
- Log Loss: 1.8383198541 (EXP-094 대비 `-0.0016174752`)
- fold별 제거 `GENE__mutated` 열 수: 241, 265, 246, 240, 255
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE` — 원 학습 checkpoint·fold별 selection mask·OOF/test
  확률·submission manifest는 저장했으나 독립 checkpoint inference 비교는 아직
  수행하지 않았다.

#### 결론

- Macro F1 개선 폭이 성능 채택 기준 `+0.001`에 못 미쳤고 fold 표준편차가 허용치
  `<0.002`보다 크게 악화돼 `ARCHIVE`다. 간소화 후보의 fold-std 조건도 넘었다.
- C1~C3 상관 삭제, R1 pair 요약, R2 저빈도 presence 삭제가 모두 EXP-094의
  안정성 기준을 통과하지 못했다. R2 threshold 재튜닝이나 제출은 하지 않고, 다음
  사전 등록 단계인 S1 Elastic Net stability selection을 독립적으로 검증한다.

### [EXP-191] R1 상관 pair 범주형 요약 피처

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #191 / `issue-191-r1-correlation-pair-summary`
- 소스 commit: `3e93bb3e6816cc927a7366d23fef1c02dbdbc9de`
- 시작/종료: 2026-08-02T10:29:38.717122+00:00 /
  2026-08-02T10:38:38.015798+00:00

#### 실행

- Config: `configs/exp191_r1_correlation_pair_summary.yaml`
- Runner: `scripts/run_exp191_r1_correlation_pair_summary.py`
- Metrics: `reports/exp191_r1_correlation_pair_summary/metrics.json`
- Report: `reports/exp191_r1_correlation_pair_summary/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: 각 canonical outer fold의 **학습 행에서만** C2 기준
  (Phi≥0.25, Jaccard≥0.15, 공동 변이 수≥20) pair를 정하고, pair당
  `only_left`, `only_right`, `both_mutated` 이진 피처를 추가했다. 기존 v1 열은
  하나도 삭제하지 않았고 validation·test에는 해당 fold의 고정 pair만 적용했다.
- balanced sample weight는 유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.4144638419, 0.4175894181, 0.3968996439, 0.4067781874,
  0.4349998003
- OOF Macro F1: 0.4144744818 (EXP-094 대비 `-0.0024120921`)
- Fold 표준편차: 0.0126377260 (EXP-094 대비 `+0.0047534740`)
- Accuracy: 0.4052572166
- Log Loss: 1.8394420338 (EXP-094 대비 `-0.0004952955`)
- fold별 pair / 추가 열: 58/174, 75/225, 61/183, 109/327, 70/210
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE` — 원 학습 checkpoint·fold pair 명세·OOF/test
  확률·submission manifest는 저장했으나 독립 checkpoint inference 비교는 아직
  수행하지 않았다.

#### 결론

- Macro F1과 fold-std가 성능 채택 gate를 통과하지 못해 `ARCHIVE`다. 기존 열을
  제거하지 않는 피처 추가 정책이므로 간소화 후보에도 해당하지 않는다.
- C1~C3 상관 삭제와 R1 관계 요약은 모두 EXP-094보다 낮았다. 이 pairwise
  Phi/Jaccard family는 재튜닝하지 않고, 다음 사전 등록 정책인 R2 희귀
  mutation-presence filter를 독립적으로 검증한다.

### [EXP-190] C3 넓은 Phi/Jaccard 상관 삭제

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #190 / `issue-190-c3-broad-correlation-pruning`
- 소스 commit: `2c4fb93855e8321ae0afa9a0a7fc038d135e37be`
- 시작/종료: 2026-08-02T10:12:43.407996+00:00 /
  2026-08-02T10:21:48.911070+00:00

#### 실행

- Config: `configs/exp190_c3_phi_jaccard_pruning.yaml`
- Runner: `scripts/run_exp190_c3_phi_jaccard_pruning.py`
- Metrics: `reports/exp190_c3_phi_jaccard_pruning/metrics.json`
- Report: `reports/exp190_c3_phi_jaccard_pruning/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: 각 canonical outer fold의 **학습 행에서만** Phi≥0.20,
  Jaccard≥0.10, 공동 변이 수≥20 기준으로 `GENE__mutated` 열을 greedy
  non-overlap pruning했다. validation·test에는 해당 fold에서 저장한 동일 mask를
  적용했고, mutation-type·missing·position·aggregate·hotspot 열은 보존했다.
- balanced sample weight는 유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.4173643315, 0.4200831742, 0.3963419048, 0.4079365506,
  0.4335616428
- OOF Macro F1: 0.4157643312 (EXP-094 대비 `-0.0011222427`)
- Fold 표준편차: 0.0124415722 (EXP-094 대비 `+0.0045573202`)
- Accuracy: 0.4071923883
- Log Loss: 1.8381019926 (EXP-094 대비 `-0.0018353367`)
- fold별 제거 열: 215 / 213 / 194 / 259 / 226개 (전체 고유 유전자 548개)
- 후보 pair/매칭 pair: fold별 6790/215, 10215/213, 7471/194, 15204/259, 9000/226
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE` — 원 학습 checkpoint·fold mask·OOF/test
  확률·submission manifest는 저장했으나 독립 checkpoint inference 비교는 아직
  수행하지 않았다.

#### 결론

- Macro F1과 fold-std가 성능 채택 gate를 통과하지 못했고, 간소화 후보 기준에서도
  Macro F1 하락과 fold-std 악화가 허용 범위를 넘어 `ARCHIVE`다.
- C1→C3 사전 등록 상관 삭제 ladder를 종료한다. 이후 상관 임계값을 더 낮추거나
  결과에 맞춘 재탐색은 하지 않으며, R1 관계 요약 또는 R2 희귀 유전자 filter를
  독립 정책으로 검증한다.

### [EXP-189] C2 중간 Phi/Jaccard 상관 삭제

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #189 / `issue-189-c2-moderate-correlation-pruning`
- 소스 commit: `b65a6a1a80de3aede79cfa5c5e65a0dba29a237f`
- 시작/종료: 2026-08-02T09:54:55.752486+00:00 /
  2026-08-02T10:04:32.795009+00:00

#### 실행

- Config: `configs/exp189_c2_phi_jaccard_pruning.yaml`
- Runner: `scripts/run_exp189_c2_phi_jaccard_pruning.py`
- Metrics: `reports/exp189_c2_phi_jaccard_pruning/metrics.json`
- Report: `reports/exp189_c2_phi_jaccard_pruning/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: 각 canonical outer fold의 **학습 행에서만** Phi≥0.25,
  Jaccard≥0.15, 공동 변이 수≥20 기준으로 `GENE__mutated` 열을 greedy
  non-overlap pruning했다. validation·test에는 해당 fold에서 저장한 동일 mask를
  적용했고, mutation-type·missing·position·aggregate·hotspot 열은 보존했다.
- balanced sample weight는 유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.4099083059, 0.4192930509, 0.3971748320, 0.4161639077,
  0.4292979573
- OOF Macro F1: 0.4147096714 (EXP-094 대비 `-0.0021769025`)
- Fold 표준편차: 0.0106384109 (EXP-094 대비 `+0.0027541588`)
- Accuracy: 0.4063860668
- Log Loss: 1.8384075392 (EXP-094 대비 `-0.0015297901`)
- fold별 제거 열: 58 / 75 / 61 / 109 / 70개 (전체 고유 유전자 220개)
- 후보 pair/매칭 pair: fold별 209/58, 436/75, 322/61, 699/109, 388/70
- Public LB: 미제출
- 재현 상태: `MANIFEST_COMPLETE` — 원 학습 checkpoint·fold mask·OOF/test
  확률·submission manifest는 저장했으나 독립 checkpoint inference 비교는 아직
  수행하지 않았다.

#### 결론

- Macro F1과 fold-std가 성능 채택 gate를 모두 통과하지 못했다. 간소화 후보
  기준에서도 Macro F1 하락과 최저 클래스 F1 하락(`-0.0568182`)이 허용치를 넘어
  `ARCHIVE`다.
- 첫 학습은 checkpoint와 결과 파일을 모두 만든 뒤 artifact 경로 필드명 오류로
  manifest 기록에서만 중단됐다. 수정 후 저장 checkpoint를 다시 읽어 manifest를
  완성했으며 재학습·설정 변경은 없었다.
- C3은 사전 등록된 별도 threshold 실험으로만 이어가며, C2의 임계값·모델 파라미터는
  결과에 맞춰 튜닝하지 않는다.

### [EXP-096] fixed pathway burden 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #96 / issue-96-exp-fixed-pathway-burden
- 소스 commit: `296c39fe9259fd4ee93bd8158aeaecec0c891545`
- 시작/종료: 2026-08-01T10:33:18.291151+00:00 / 2026-08-01T10:45:02.814952+00:00

#### 실행

- Config: `reproducibility/exp096_fixed_pathway_burden/config.resolved.yaml`
- Metrics: `reports/exp096_fixed_pathway_burden/metrics.json`
- Report: `reports/exp096_fixed_pathway_burden/README.md`
- 기준: 동결된 EXP-094 Feature Spec v1
- 변경: 고정 canonical pathway별 mutated-gene·LoF-gene count 20개

#### 결과

- Fold Macro F1: 0.4086500, 0.4181644, 0.4140262, 0.4133268, 0.4360397
- OOF Macro F1: 0.4181153080
- EXP-094 대비: +0.0012287341
- fold 표준편차: 0.0094921177 (EXP-094 대비 +0.0016078656)
- Log Loss: 1.8369342089 (EXP-094 대비 -0.0030031204)
- OOF 예측 라벨 일치율(EXP-094 대비): 0.8948556684
- Public LB: 0.3169056749 (제출 ID `1508043`, 2026-08-01 23:36:59 KST)
- 재현 상태: INFERENCE_VERIFIED
- 판단: 신규 Local 최고, fixed pathway burden을 v2-performance 후보로 채택

### [EXP-110] frequency-tier spectrum 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #110 / issue-110-exp-frequency-tier-spectrum
- 소스 commit: `1c0e835eecb5d5edbffc61c632c583395f698d1b`
- 시작/종료: 2026-08-01T10:07:30.754000+00:00 / 2026-08-01T10:19:47.723783+00:00

#### 실행

- Config: `reproducibility/exp110_frequency_tier_spectrum/config.resolved.yaml`
- Metrics: `reports/exp110_frequency_tier_spectrum/metrics.json`
- Report: `reports/exp110_frequency_tier_spectrum/README.md`
- 기준: 동결된 EXP-094 Feature Spec v1
- 변경: fold-train 유전자 빈도 tier별 mutation-type count·fraction 40개

#### 결과

- Fold Macro F1: 0.3930559, 0.4006714, 0.3872658, 0.3883149, 0.4072213
- OOF Macro F1: 0.3963504903
- EXP-094 대비: -0.0205360836
- OOF 예측 라벨 일치율(EXP-094 대비): 0.7505241090
- 전체 OOF 확률 상관(EXP-094 대비): 0.9522398631
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED
- 판단: 성능·초기 blend 미채택, 저우선순위 stacking 자산으로 확률 보존

### [EXP-109] complex morphology 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #109 / issue-109-exp-complex-morphology
- 소스 commit: `2e5882eb9c050292c6167c584cf4977a12c1cdab`
- 시작/종료: 2026-08-01T09:52:38.105809+00:00 / 2026-08-01T10:02:36.841068+00:00

#### 실행

- Config: `reproducibility/exp109_complex_morphology/config.resolved.yaml`
- Metrics: `reports/exp109_complex_morphology/metrics.json`
- Report: `reports/exp109_complex_morphology/README.md`
- 기준: 동결된 EXP-094 Feature Spec v1
- 변경: complex morphology·스펙트럼 요약 8개만 추가

#### 결과

- Fold Macro F1: 0.4082243, 0.4153132, 0.4094375, 0.4100378, 0.4209211
- OOF Macro F1: 0.4135182559
- EXP-094 대비: -0.0033683180
- fold 표준편차: 0.0047358437 (EXP-094 대비 -0.0031484084)
- OOF 예측 라벨 일치율(EXP-094 대비): 0.8709885502
- 전체 OOF 확률 상관(EXP-094 대비): 0.9852716978
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED
- 판단: 성능 후보 미채택, fold 안정성 및 diversity 관찰 후보로 확률 보존

### [EXP-107] amino-acid change 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #107 / issue-107-exp-amino-acid-change
- 소스 commit: `efe36044e117df9e8d9e821e19e092e75844d966`
- 시작/종료: 2026-08-01T09:38:39.309403+00:00 / 2026-08-01T09:48:12.149468+00:00

#### 실행

- Config: `reproducibility/exp107_amino_acid_change/config.resolved.yaml`
- Metrics: `reports/exp107_amino_acid_change/metrics.json`
- Report: `reports/exp107_amino_acid_change/README.md`
- 기준: 동결된 EXP-094 Feature Spec v1
- 변경: 보수적·비보수적·전하·극성 변화 카운트 4개만 추가

#### 결과

- Fold Macro F1: 0.4060877, 0.4050910, 0.4109500, 0.4106355, 0.4316231
- OOF Macro F1: 0.4131379001
- EXP-094 대비: -0.0037486737
- OOF 예측 라벨 일치율(EXP-094 대비): 0.8471214320
- 전체 OOF 확률 상관(EXP-094 대비): 0.9817471367
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED
- 판단: 성능 후보 미채택, v2-diversity 관찰 후보로 확률 보존

### [EXP-106] recurrent exact-token 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #106 / issue-106-exp-recurrent-exact-token
- 소스 commit: `8e54d0f48b891bbc8aa99130e1954cf1cb8b6f08`
- 시작/종료: 2026-08-01T09:07:40.300760+00:00 / 2026-08-01T09:19:58.384785+00:00

#### 실행

- Config: `reproducibility/exp106_recurrent_exact_token/config.resolved.yaml`
- Metrics: `reports/exp106_recurrent_exact_token/metrics.json`
- Report: `reports/exp106_recurrent_exact_token/README.md`
- 기준: 동결된 EXP-094 Feature Spec v1
- 변경: fold-train recurrent `(gene, raw token)` 이진 피처만 추가
- 최종 추가 차원: fold별 272, 297, 285, 301, 299

#### 결과

- Fold Macro F1: 0.4161140, 0.4196788, 0.4006706, 0.4106391, 0.4242178
- OOF Macro F1: 0.4147478922
- EXP-094 대비: -0.0021386817
- OOF 예측 라벨 일치율(EXP-094 대비): 0.9159812933
- 전체 OOF 확률 상관(EXP-094 대비): 0.9929096377
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED
- 판단: 성능 후보 미채택, OOF/test 확률은 후속 다양성 비교용 보존

### [EXP-094] Feature Spec v1 조합

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #94 / issue-94-exp-feature-spec-v1
- 소스 commit: `19d5c067517af42f1b5e353b2106e352bae185df`
- 시작/종료: 2026-08-01T06:12:29.883679+00:00 / 2026-08-01T06:21:46.651975+00:00

#### 실행

- Config: `reproducibility/exp094_feature_spec_v1/config.resolved.yaml`
- Metrics: `reports/exp094_feature_spec_v1/metrics.json`
- Report: `reports/exp094_feature_spec_v1/README.md`
- 구성: EXP-005 mutation-type + EXP-069 max residue position + EXP-085 fixed hotspot
- Feature 수: 35,119

#### 결과

- Fold Macro F1: 0.4194967, 0.4180513, 0.4091129, 0.4061445, 0.4282487
- OOF Macro F1: 0.4168865739
- EXP-069 대비: +0.0037857746
- EXP-085 대비: +0.0043070194
- 기존 Local 최고 EXP-075 대비: +0.0010954964
- Public LB: 0.311853163 (제출 ID `1508852`, 2026-08-02 23:04:51 KST)
- 재현 번들: [`exp-094-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-094-repro-v1)
  (`17,832,471` bytes, SHA-256
  `2b0d276dce98ed482a47956a12a1fd90e44223dee651156e8de2ae6d56610633`)
- 재현 상태: INFERENCE_VERIFIED
- 판단: 채택, Feature Spec v1 동결

#### 실행상 주의

- 첫 실행은 학습 완료 후 metrics schema 위반으로 검증 단계에서 실패했습니다.
- 메타데이터 위치만 수정한 clean commit에서 전체 5-fold를 재실행했으며,
  fold 점수가 첫 실행과 정확히 같아 결정론적 재실행을 확인했습니다.

### [EXP-093] 변이 유형·위치·주요 hotspot 조합 검증

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #93 / issue-93-exp-mutation-position-hotspot
- 소스 commit: `62254643cd811ec0249d15456a1ec9b7fe6c328f`
- 시작/종료: 2026-08-01T05:52:43.735321+00:00 /
  2026-08-01T06:01:38.290419+00:00

#### 실행

- Config: `reproducibility/exp093_mutation_position_hotspot/config.resolved.yaml`
- Metrics: `reports/exp093_mutation_position_hotspot/metrics.json`
- Report: `reports/exp093_mutation_position_hotspot/README.md`
- 조합: EXP-005 mutation-type + EXP-069 max residue-position + EXP-085
  reference-aware fixed hotspot 34개

#### 결과

- Fold Macro F1: 0.4094564310, 0.4312411436, 0.3986561217,
  0.4090170143, 0.4292709896
- OOF Macro F1: 0.4157606623
- Fold 표준편차: 0.0126466581
- Accuracy: 0.4059022738
- Log Loss: 1.8402239084
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp093_mutation_position_hotspot/metrics.json` /
  `reports/exp093_mutation_position_hotspot/README.md` /
  `reproducibility/exp093_mutation_position_hotspot/`
- 제출 후보: `submissions/exp093_mutation_position_hotspot.csv`
  (SHA-256 `de3fceb0f8c9d1a0ab6e3d566c7803bd50e95209d662d4a5265f49b425ad9635`,
  DACON 미제출)
- 결론: EXP-069 대비 `+0.0026598630`, EXP-085 대비 `+0.0031811077`
  개선했지만 fold 표준편차가 각각 `+0.0044408013`, `+0.0035200894`
  악화되어 사전 안정성 기준을 통과하지 못했다. 현재 최고 EXP-075보다
  `-0.0000304152` 낮아 Feature Spec 조합 동결을 보류한다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시, 제출 SHA-256과 test
  라벨이 일치했고 확률 최대 절대 차이는 약 2.98e-08로 허용치 이내였다.

### [EXP-085] Clean fixed-hotspot reconstruction

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #85 / issue-85-exp-hotspot-clean
- 소스 commit: `e329f13f7de85cc34c0e54c85f25f093e2ed0dd1`
- 시작/종료: 2026-07-31T14:45:10.739046+00:00 / 2026-07-31T14:53:48.871458+00:00

#### 실행

- Config: `reproducibility/exp085_hotspot_clean/config.resolved.yaml`
- Metrics: `reports/exp085_hotspot_clean/metrics.json`
- Report: `reports/exp085_hotspot_clean/README.md`

#### 결과

- Fold Macro F1: 0.4070290, 0.4219064, 0.4059511, 0.4005702, 0.4232571
- OOF Macro F1: 0.4125795545
- Public LB: 0.3103760308 (제출 ID `1507333`, 2026-07-31 23:55:33 KST)
- 재현 상태: INFERENCE_VERIFIED

#### 리더보드 제출 결과와 순위 해석

- 제출 파일: `submissions/exp085_hotspot_clean.csv`
- 제출 ID: `1507333`
- 제출 시각: 2026-07-31 23:55:33 KST
- 제출 SHA-256:
  `d319c6967ea98b75c158265fe3b46a5ebb12db207a19cd87964476154eecfe5d`
- Public Macro F1: `0.3103760308`
- 팀 내부 제출 점수 순위: 확인 당시 8개 제출 중 2위
  (`EXP-031 0.3170803849 > EXP-085 0.3103760308 > EXP-058 0.3044672015`)
- EXP-031과의 차이: `-0.0067043541`
- EXP-031의 팀 최고 점수를 넘지 못해 리더보드 팀 점수와 순위는 갱신되지
  않았습니다.
- 플랫폼은 선택하지 않은 제출의 공식 전체 개별 순위를 별도로 표시하지
  않으므로 EXP-085의 전체 개별 순위는 확인할 수 없습니다.
- 2026-08-01 확인 당시 팀 대표 제출은 EXP-031이었고, 그 점수를 기준으로
  8조의 공식 팀 순위는 참가 4팀 중 4위였습니다. 이 `4위`를 EXP-085의
  개별 순위로 해석하지 않습니다.

#### 산출물과 결론

- EXP-005 대비 OOF `+0.0081999`, fold 표준편차 악화 `+0.0004454`,
  log loss `-0.0316354`로 단계 D 복구 기준을 통과했습니다.
- 저장 checkpoint 재추론의 test 라벨 100%·제출 SHA-256 일치를 확인했습니다.
- 제출 파일: `submissions/exp085_hotspot_clean.csv`
  (SHA-256 `d319c6967ea98b75c158265fe3b46a5ebb12db207a19cd87964476154eecfe5d`)
- Public LB는 EXP-031보다 `-0.0067043541` 낮아 현재 팀 선택 제출물은
  EXP-031을 유지합니다.
- 고정 hotspot family를 단계 F 조합 후보로 채택합니다.

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
- Report: `reports/exp012_cosmic_protected_genes/README.md`

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

- Report: `reports/exp021_cosmic_weighted_burden_baseline/README.md`
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
### [EXP-031] EXP-005 변이유형 피처 + cancer hotspot 34개

- 상태: COMPLETED
- 실행자: Kangho Park
- Issue/브랜치: #31 / issue-31-cosmic-mutation-type-cross
- 소스 commit: `25c8434cfe19ecb8943aeec02e91c25f8ca38862`
- 시작/종료: 2026-07-31 (아래 attempt 1·2 모두 이 실험 세션에서 순서대로 실행)

#### 실행

EXP-005(#5)의 유전자×변이유형 희소 피처(30,697개)를 그대로 재현하고, 여러
구성을 순서대로 비교했다. attempt 1~4는 같은 Issue에서 수행한 탐색적
ablation이며 별도 공식 EXP-ID로 세지 않는다. attempt 5만 EXP-031의 공식
채택 config와 결과다. attempt 1·2는 EXP-012(#12)의 COSMIC 보호
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
없어 제외). 피처 값 자체는 각 샘플 행에서만 계산하므로 타깃 누출은 없다.
다만 당시 후보 채굴은 train+test 분포를 함께 본 **transductive 탐색**이었다.
이후 공식 runner에는 추가 15개 위치 각각을 train에서만 재검증하고, test는
고정된 목록으로 변환만 하도록 강제했다.

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
의도적으로 제외했다. 이 탐색 스크립트가 test도 참고한 사실은 한계로 남기되,
최종 채택 15개는 공식 runner가 train-only 관측 횟수(각 5회 이상)와 reference
amino acid 일관성을 다시 확인한다. 따라서 test 출현 여부로 최종 목록을
추가하거나 제거하지 않는다.

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
- 재현 상태: FAILED. 원 Windows 실행의 checkpoint와 test 확률이 보관되지 않아
  2026-07-31 macOS에서 같은 코드·설정으로 독립 재학습했다. 재학습 OOF Macro
  F1은 `0.4125795545`로 원 기록 `0.4135846695`와 달랐고, 재학습 test 라벨은
  원 제출과 `93.3621%`만 일치해 2,546개 중 169개가 달랐다. 원 제출을
  `INFERENCE_VERIFIED`로 승격하지 않으며 상세 증빙은
  `reproducibility/exp031_hotspot_extended/comparison.json`에 기록한다.

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

### [EXP-063] Residue-position 관측 indicator 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #63 / issue-63-exp-residue-indicator
- 소스 commit: `7265bf6c6fc166cf7f30ef07f41ed2c641a3fb56`
- 시작/종료: 2026-07-31T10:38:54.284936+00:00 /
  2026-07-31T10:50:45.227346+00:00

#### 실행

- Config: `reproducibility/exp063_xgb_residue_indicator/config.resolved.yaml`
- Metrics: `reports/exp063_xgb_residue_indicator/metrics.json`
- Report: `reports/exp063_xgb_residue_indicator/README.md`

#### 결과

- Fold Macro F1: 0.4176226929, 0.4112943222, 0.3950600489,
  0.4141584489, 0.4242627965
- OOF Macro F1: 0.4130329102
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp063_xgb_residue_indicator/metrics.json` /
  `reports/exp063_xgb_residue_indicator/README.md` /
  `reproducibility/exp063_xgb_residue_indicator/`
- 결론: EXP-047 대비 OOF Macro F1 `+0.0042196664`, fold 표준편차
  `+0.0012194691`, Log Loss `+0.0003141165`의 실제 결과와 재현 검증은
  유지한다. 이후 Issue #80 의미 감사에서 train/test 모두 indicator와 기존
  mutation-presence의 불일치가 0개임을 확인했다. 따라서 개선을 결측 해소나
  생물학적 위치 신호로 해석하지 않고 중복 피처 weighting perturbation으로
  재분류하며 indicator는 채택하지 않는다.

### [EXP-052] Feature Factory + Hotspot 연관 유전자 Co-mutation

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #52 / issue-52-hotspot-cooccurrence
- 소스 commit: `6865fd5accf4fbf7090dc39ecc4a27f9b611adf7`
- 시작/종료: 2026-07-31 (단일 실행)

#### 실행

Feature Factory에 family 7(co-mutation)을 구현해 EXP-047 피처에 문헌 근거
유전자 쌍 3개(IDH1/IDH2, APC/CTNNB1, PIK3CA/PTEN)의 co-mutation indicator
4개(쌍별 3개와 총합 1개)를 추가했다. 쌍은 데이터 빈도나 target으로 선정하지
않은 고정 외부 지식이며 fold fitting을 하지 않는다.

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
- 결론: EXP-047 대비 OOF Macro F1이 `+0.0006937301` 개선됐고 fold
  표준편차는 `0.0085063656 → 0.0052610612`로 감소했다. 쌍별 조건부 적용과
  pair 확장은 후속 검증 대상으로 남긴다. 저장 checkpoint 재추론에서 제출
  SHA-256과 라벨 100% 일치를 확인해 `INFERENCE_VERIFIED`를 통과했다.

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

### [EXP-030] XGBoost + notation 기반 희소 변이 피처

- 상태: COMPLETED
- 실행자: Gomin-art
- Issue/브랜치: #30 / issue-30-exp-sparse-variant-xgb
- 소스 commit: `64b72df89ee5cf0b66409f494475aca753238184`
- 시작/종료: 2026-07-31T07:36:46.248893+00:00 /
  2026-07-31T07:58:41.374756+00:00

#### 실행

- Config: `reproducibility/exp030_sparse_variant_xgb/config.resolved.yaml`
- Metrics: `reports/exp030_sparse_variant_xgb/metrics.json`
- Report: `reports/exp030_sparse_variant_xgb/README.md`

#### 결과

- Fold Macro F1: 0.4075818591, 0.4144161831, 0.3960694066,
  0.3962701409, 0.4315160934
- OOF Macro F1: 0.4105408554
- Public LB: 0.2993610323 (제출 ID `1507123`, 2026-07-31 18:46:30 KST)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp030_sparse_variant_xgb/metrics.json` /
  `reports/exp030_sparse_variant_xgb/README.md` /
  `reproducibility/exp030_sparse_variant_xgb/`
- 제출 파일: `submissions/exp030_sparse_variant_xgb.csv`
  (SHA-256 `bd523ea4e872301e7d11f44ea375cf16d8c282de549f5f408d67ba3146670cba`,
  제출 ID `1507123`)
- 결론: 기존 최고 EXP-047보다 OOF Macro F1이 `+0.0017276116` 높아 Local
  최고 기록을 갱신했다. 다만 fold 표준편차는 EXP-047보다 `+0.0046650006`
  높았다. Public LB는 EXP-005보다 `+0.0005766957` 높고 EXP-031보다
  `-0.0177193526` 낮아 최종 선택 모델로 채택하지 않는다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시와 제출 SHA-256이
  일치하고 test 라벨 일치율 100%, 확률 최대 절대 차이 약 5.83e-08로
  허용치 1e-6 이내여서 `INFERENCE_VERIFIED`를 통과했다.
- 보관 메모: 원 WSL checkpoint·OOF·test 확률이 GitHub Release에 보관되지
  않아 `configs/reproducibility_policy.yaml`에 임시 예외를 기록했다. 원
  실행자가 `exp-030-repro-v1` 번들을 보관하면 예외를 제거한다.

### [EXP-050] EXP-005 + 반복 선택 파생변수 2종 고정 검증

- 상태: COMPLETED
- 실행자: 2heej
- Issue/브랜치: #50 / issue-50-exp-fixed-two-distribution-features
- 소스 commit: `b7444843245eb1e2a360084e0dfb42653cf6116a`
- 시작/종료: 2026-07-31T08:24:22.050749+00:00 /
  2026-07-31T08:29:15.749495+00:00

#### 실행

- Config: `reproducibility/exp050_xgb_fixed_two_distribution_features/config.resolved.yaml`
- Metrics: `reports/exp050_xgb_fixed_two_distribution_features/metrics.json`
- Report: `reports/exp050_xgb_fixed_two_distribution_features/README.md`

#### 결과

- Fold Macro F1: 0.3913709706, 0.4144609929, 0.3900628338,
  0.4032739868, 0.4014631749
- OOF Macro F1: 0.4014204930
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp050_xgb_fixed_two_distribution_features/metrics.json` /
  `reports/exp050_xgb_fixed_two_distribution_features/README.md` /
  `reproducibility/exp050_xgb_fixed_two_distribution_features/`
- 결론: EXP-043보다 OOF `+0.0025080033`, EXP-045보다
  `+0.0014224695` 개선했지만 EXP-005보다 `-0.0029591657`,
  EXP-033보다 `-0.0043039704` 낮았다. 반복 선택된 두 피처의 고정 추가는
  미채택하고, 이후에는 기존 정보를 재집계하는 변이량 요약보다 hotspot·잔기
  위치처럼 새로운 정보 단위를 우선한다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시, 제출 SHA-256과 test
  라벨이 일치했고 확률 최대 절대 차이는 약 2.98e-08로 허용치 이내여서
  `INFERENCE_VERIFIED`를 통과했다.

### [EXP-065] Complex-token residue 위치 제외 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #65 / issue-65-exp-residue-exclude-complex
- 소스 commit: `64f1a4c7d948c3951e88c9d80caf47fd2a5fd07b`
- 시작/종료: 2026-07-31T10:56:44.751792+00:00 /
  2026-07-31T11:07:01.334455+00:00

#### 실행

- Config:
  `reproducibility/exp065_xgb_residue_exclude_complex/config.resolved.yaml`
- Metrics: `reports/exp065_xgb_residue_exclude_complex/metrics.json`
- Report: `reports/exp065_xgb_residue_exclude_complex/README.md`
- 비교 기준: EXP-047의 `min + zero + complex include + raw`
- 유일한 변경: complex token에서 추출한 residue 위치를 aggregate에서 제외

#### 결과

- Fold Macro F1: 0.4092990615, 0.4148643315, 0.3958933689,
  0.4115588463, 0.4215365027
- OOF Macro F1: 0.4108923084
- Fold 표준편차: 0.0084461093
- Accuracy: 0.4036445735
- Log Loss: 1.8529859781
  `reports/exp065_xgb_residue_exclude_complex/metrics.json` /
  `reports/exp065_xgb_residue_exclude_complex/README.md` /
  `reproducibility/exp065_xgb_residue_exclude_complex/`
- 제출 후보 파일: `submissions/exp065_xgb_residue_exclude_complex.csv`
  (SHA-256 `d39a589c88e7e8d4aabe93a980c5ff53729be4478f51f8767641ef3feb5ed9f6`,
  Dacon 미제출)
- 결론: EXP-047보다 OOF Macro F1이 `+0.0020790646` 개선되고 fold
  표준편차가 `-0.0000602563` 감소해 complex 위치 제외를 채택 후보로
  유지한다. Log Loss는 `+0.0009884834` 악화되어 확률 품질 개선으로
  해석하지 않는다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시와 제출 SHA-256이
  일치하고 test 라벨 일치율 100%, 확률 최대 절대 차이 약 2.97e-08로
  허용치 이내여서 `INFERENCE_VERIFIED`를 통과했다.

### [EXP-067] Residue-position coarse-bin 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #67 / issue-67-exp-residue-coarse-bin
- 소스 commit: `5846db2f18f610836a38b23cc8c377f9809fe47c`
- 시작/종료: 2026-07-31T11:11:50.083380+00:00 /
  2026-07-31T11:19:00.378514+00:00

#### 실행

- Config: `reproducibility/exp067_xgb_residue_coarse_bin/config.resolved.yaml`
- Metrics: `reports/exp067_xgb_residue_coarse_bin/metrics.json`
- Report: `reports/exp067_xgb_residue_coarse_bin/README.md`
- 비교 기준: EXP-047의 `min + zero + complex include + raw`
- 유일한 변경: residue 위치를 폭 100의 고정 coarse-bin으로 변환

#### 결과

- Fold Macro F1: 0.4061401833, 0.4242984236, 0.4111564808,
  0.4011949462, 0.4166403104
- OOF Macro F1: 0.4124014867
- Fold 표준편차: 0.0080562642
- Accuracy: 0.4034833091
- Log Loss: 1.8524806499
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp067_xgb_residue_coarse_bin/metrics.json` /
  `reports/exp067_xgb_residue_coarse_bin/README.md` /
  `reproducibility/exp067_xgb_residue_coarse_bin/`
- 제출 후보 파일: `submissions/exp067_xgb_residue_coarse_bin.csv`
  (SHA-256 `dbae8b3c15a35095bf17168862499972441c5143edf48c6dc7558e2eac633148`,
  Dacon 미제출)
- 결론: EXP-047보다 OOF Macro F1이 `+0.0035882429` 개선되고 fold
  표준편차가 `-0.0004501014` 감소해 폭 100 coarse-bin을 채택 후보로
  유지한다. Log Loss는 `+0.0004831553` 악화되어 확률 품질 개선으로
  해석하지 않는다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시와 제출 SHA-256이
  일치하고 test 라벨 일치율 100%, 확률 최대 절대 차이 약 2.97e-08로
  허용치 이내여서 `INFERENCE_VERIFIED`를 통과했다.

### [EXP-069] Maximum residue-position 단독 검증

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #69 / issue-69-exp-max-residue-position
- 소스 commit: `8b603bcf8b03658e54d158b5976df51c90cea5f8`
- 시작/종료: 2026-07-31T11:22:21.571407+00:00 /
  2026-07-31T11:33:23.820781+00:00

#### 실행

- Config: `reproducibility/exp069_xgb_max_residue_position/config.resolved.yaml`
- Metrics: `reports/exp069_xgb_max_residue_position/metrics.json`
- Report: `reports/exp069_xgb_max_residue_position/README.md`
- 비교 기준: EXP-047의 `min + zero + complex include + raw`
- 유일한 변경: residue aggregate `min → max`

#### 결과

- Fold Macro F1: 0.4088270533, 0.4239996903, 0.3999078004,
  0.4129369619, 0.4182072576
- OOF Macro F1: 0.4131007993
- Fold 표준편차: 0.0082058569
- Accuracy: 0.4052572166
- Log Loss: 1.8525067568
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp069_xgb_max_residue_position/metrics.json` /
  `reports/exp069_xgb_max_residue_position/README.md` /
  `reproducibility/exp069_xgb_max_residue_position/`
- 제출 후보 파일: `submissions/exp069_xgb_max_residue_position.csv`
  (SHA-256 `4e0046564d4b291c3f0c12370d3fe542b3faeb3fa2d105d36fe7386bfb7c3f08`,
  Dacon 미제출)
- 결론: EXP-047보다 OOF Macro F1이 `+0.0042875555` 개선되고 fold
  표준편차가 `-0.0003005087` 감소해 max 위치를 채택 후보로 유지한다.
  Log Loss는 `+0.0005092621` 악화되어 확률 품질 개선으로 해석하지 않는다.
- 재현 메모: 저장 checkpoint 재추론에서 데이터 해시와 제출 SHA-256이
  일치하고 test 라벨 일치율 100%, 확률 최대 절대 차이 약 2.97e-08로
  허용치 이내여서 `INFERENCE_VERIFIED`를 통과했다.

### [EXP-075] EXP-067·069 고정 0.5/0.5 확률 Blend

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #75 / issue-75-exp-residue-blend
- 소스 commit: `01fb86e27b0ebfd177d4a6e60ac6535a02fcfb3c`
- 시작/종료: 2026-07-31T12:59:08.935275+00:00 /
  2026-07-31T12:59:09.213986+00:00

#### 실행

- Config: `reproducibility/exp075_residue_probability_blend/config.resolved.yaml`
- Metrics: `reports/exp075_residue_probability_blend/metrics.json`
- Report: `reports/exp075_residue_probability_blend/README.md`
- 부모: EXP-067(coarse-bin), EXP-069(max residue-position)
- 고정 방식: 두 OOF·test 확률의 `0.5/0.5` 산술 평균 후 고정 클래스 순서
  `argmax`

#### 결과

- Fold Macro F1: 0.4129241979, 0.4225703598, 0.4081482976,
  0.4095628288, 0.4234699014
- OOF Macro F1: 0.4157910775
- Fold 표준편차: 0.0064700181
- Accuracy: 0.4073536526
- Log Loss: 1.8446407531
- Public LB: 0.31125491 (제출 ID `1508045`, 2026-08-01 23:39:49 KST)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp075_residue_probability_blend/metrics.json` /
  `reports/exp075_residue_probability_blend/README.md` /
  `reproducibility/exp075_residue_probability_blend/`
- 제출 후보: `submissions/exp075_residue_probability_blend.csv`
  (SHA-256 `25f00f1a97acbd5364df0dd7b391f75a930888fefc887edf696f681d482d7b3e`,
  DACON 미제출)
- 결론: EXP-067보다 OOF `+0.0033895908`, EXP-069보다 `+0.0026902782`
  개선했고 fold 표준편차와 Log Loss도 두 부모보다 낮아 고정 blend를 채택한다.
  EXP-067과 EXP-069의 OOF 라벨 일치율은 약 88.79%로, 서로 다른 오류가
  단순 평균의 개선에 기여한 것으로 해석한다.
- 재현 메모: 동일 부모 확률에서 재계산한 OOF·test 라벨 일치율 100%, 확률
  최대 절대 차이 0, 제출 CSV byte-level SHA-256 일치를 확인했다. 새 모델을
  학습하지 않는 inference-only 실험이며 부모 checkpoint 10개와 입력 확률을
  [`exp-075-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-075-repro-v1)
  번들에 함께 보관했다. 번들 SHA-256은
  `698c29841112ff78e6fe2dcdd1b6b07bd2e7a2db26ef8ec86e625963d8125b33`이다.

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
- Public LB: 0.3044672015 (제출 ID `1507272`, 2026-07-31 22:44:57 KST)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp058_cooccurrence_pair_ablation/metrics.json` /
  `reports/exp058_cooccurrence_pair_ablation/README.md` /
  `reproducibility/exp058_cooccurrence_pair_ablation/`
- 제출 파일: `submissions/exp058_cooccurrence_pair_ablation.csv`
  (SHA-256 `0a53d0a7aea3b0c34baba586e56175c6bc8df2c738875a2bef30c5ebad905eb3`)
- 결론: EXP-052 대비 OOF Macro F1이 `+0.0006772617`(EXP-047 대비 누적
  `+0.0013709918`) 개선됐다. 26개 클래스 중
  13개 개선(BLCA +0.0265, LUSC +0.0197, DLBC +0.0196 등), 13개 하락(PAAD
  -0.0230, THYM -0.0204 등)이었다. 가장 중요한 확인은 **COAD가 SHAP
  진단과 같은 방향으로 개선**됐다는 점(0.7126 → 0.7187, `+0.0061`)이다.
  다만 동일 canonical OOF를 피처 제거 판단과 성능 평가에 사용했으므로
  독립 검증으로 간주하지 않는다. 저장 checkpoint 재추론으로 제출
  SHA-256과 라벨 100% 일치를 확인해 `INFERENCE_VERIFIED`로 자동
  승격됐다. 이후 Public LB `0.3044672015`를 제출 ID `1507272`로
  확인했으며, 이는 EXP-031(hotspot 계열, Local OOF 0.4136·Public LB
  0.3171)보다 Local·LB 모두 낮다 — Local과 LB 순위가 두 계열 사이에서
  일관됐다(EXP-031 > EXP-058, 양쪽 다). 제출 후에도 팀 선택 제출물은
  EXP-031을 유지한다.

#### 선택 메모 (PR #76 리뷰 반영)

- 초기 버전은 SHAP 계산 코드와 원시 결과가 저장소에 보관되지 않아 독립
  재현이 불가능했다(fabxoe 리뷰 지적). `scripts/explore_exp052_cooccurrence_shap.py`
  (RUN_MODE=explore)로 보완하고, 결과를
  `reports/exp052_hotspot_cooccurrence/cooccurrence_shap_diagnostic.json` /
  `.csv`에 저장했다. 재실행 시 본문 표와 동일한 수치가 나온다.
- 리뷰의 핵심 질문("5개 checkpoint 중 어떤 모델로 SHAP을 계산했는가")에
  대한 답: 각 샘플은 **자신이 속한 fold의 checkpoint 하나만**으로
  계산됐다(5개 평균 아님, `fold_map == fold`인 행에만 그 fold의 모델
  적용) — EXP-052의 OOF 예측 방식과 동일해 in-sample 정보가 섞이지
  않았다. 이 사실은 스크립트 코드 자체로 확인 가능하다.
- 여전히 남는 한계(해결되지 않음): 같은 canonical OOF를 "어떤 피처를
  뺄지 결정"과 "뺀 뒤 성능이 좋아졌는지 평가"에 모두 사용했으므로,
  `+0.0006772617` 개선은 완전히 독립적인 검증이 아니라 같은 데이터
  안에서의 일관된 관찰로 취급한다. 다른 seed 또는 별도 확인 실험 전까지
  탐색적 채택 후보로 유지한다.

### [EXP-078] Maximum residue-position + observed indicator

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #78 / issue-78-exp-max-indicator
- 소스 commit: `e2a822e576095a25bdf01a46c1bb5e404684f316`
- 시작/종료: 2026-07-31T13:50:42.711822+00:00 /
  2026-07-31T14:04:07.457479+00:00

#### 실행

- 부모: EXP-069 (`max + zero`)
- 유일한 변경: `missing_policy: indicator`
- 유지: `aggregates: [max]`, complex 포함, raw transform, canonical 5-fold,
  XGBoost 설정과 seed
- Config: `reproducibility/exp078_xgb_max_residue_indicator/config.resolved.yaml`
- Metrics: `reports/exp078_xgb_max_residue_indicator/metrics.json`
- Report: `reports/exp078_xgb_max_residue_indicator/README.md`

#### 결과

- Fold Macro F1: 0.4159950137, 0.4149887889, 0.3869454103,
  0.4115730954, 0.4244276491
- OOF Macro F1: 0.4110815504
- Fold 표준편차: 0.0126482021
- Accuracy: 0.4026769876
- Log Loss: 1.8513578176
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp078_xgb_max_residue_indicator/metrics.json` /
  `reports/exp078_xgb_max_residue_indicator/README.md` /
  `reproducibility/exp078_xgb_max_residue_indicator/`
- 제출 후보: `submissions/exp078_xgb_max_residue_indicator.csv`
  (SHA-256 `deb510b6e23008f536a000f63750039b00ca6ca13cd06bc1a62c751a2b9da91c`,
  DACON 미제출)
- 결론: EXP-069 대비 OOF Macro F1이 `-0.0020192489` 하락했고 fold
  표준편차가 `+0.0044423453` 악화돼 로드맵 채택 조건 두 개를 모두
  통과하지 못했다. `max+indicator`를 기각하고 EXP-069의 `max+zero`를
  Position Feature Spec v1으로 동결한다. Issue #80에서 indicator가 기존
  mutation-presence와 완전히 같은 중복 열임을 추가 확인했으며, 하락을 결측
  표현의 효과로 해석하지 않는다. 위치 옵션 추가 탐색은 종료한다.
- 재현 메모: 저장 checkpoint 재추론에서 제출 SHA-256과 test 라벨 100%,
  확률 최대 절대 차이 약 2.97e-08을 확인해 `INFERENCE_VERIFIED`를 통과했다.

### [EXP-123] 동결 Feature Spec v1 희소 Logistic Regression

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #123 / issue-123-exp-sparse-logistic-v1
- 소스 commit: `63637a3e67733909bee21f6b9a072db7a42cdb68`
- 시작/종료: 2026-08-01T12:06:30.551287+00:00 /
  2026-08-01T12:10:07.890053+00:00

#### 실행

- 부모: EXP-094, 동결 Feature Spec v1과 canonical 5-fold 유지
- 유일한 모델 변경: XGBoost에서 희소 다항 Logistic Regression으로 교체
- 전처리: outer fold-train에서만 MaxAbsScaler fit
- Config: `reproducibility/exp123_sparse_logistic_v1/config.resolved.yaml`
- Metrics: `reports/exp123_sparse_logistic_v1/metrics.json`
- Report: `reports/exp123_sparse_logistic_v1/README.md`

#### 결과

- Fold Macro F1: 0.3701706160, 0.3754824506, 0.3798275842,
  0.3691361071, 0.3779347342
- OOF Macro F1: 0.3763324825
- Fold 표준편차: 0.0042109416
- Accuracy: 0.3712304467
- Log Loss: 2.1261745525
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp123_sparse_logistic_v1/metrics.json` /
  `reports/exp123_sparse_logistic_v1/README.md` /
  `reproducibility/exp123_sparse_logistic_v1/`
- 제출 후보: `submissions/exp123_sparse_logistic_v1.csv`
  (SHA-256 `7947df0753ed4237a5f3967bd1e3bc8f4da7a2d6626feef935489e5e6aae81e0`,
  DACON 미제출)
- 결론: EXP-094 대비 OOF `-0.0405540914`, Log Loss `+0.2862373711`로
  품질·wildcard gate를 실패했다. 라벨 불일치율 46.17%, 정오답 상관
  0.5963으로 다양성 gate는 통과했지만 현재 앙상블 후보에는 넣지 않고 참고
  자산으로만 보존한다.
- 재현 메모: 저장 checkpoint 재추론에서 OOF·test 라벨 100%, 확률 최대 절대
  차이 0, 제출 CSV byte-level SHA-256 일치를 확인했다.

### [EXP-125] 동결 Feature Spec v1 LightGBM

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #125 / issue-125-exp-lightgbm-v1
- 소스 commit: `8d4fe9c99e05306c691f1c4f23903066b92f7ddf`
- 시작/종료: 2026-08-01T12:19:10.781316+00:00 /
  2026-08-01T12:24:32.873783+00:00

#### 실행

- 부모: EXP-094, 동결 Feature Spec v1과 canonical 5-fold 유지
- 유일한 모델 변경: XGBoost에서 LightGBM으로 교체
- early stopping: outer-fold validation만 사용, patience 60
- Config: `reproducibility/exp125_lightgbm_v1/config.resolved.yaml`
- Metrics: `reports/exp125_lightgbm_v1/metrics.json`
- Report: `reports/exp125_lightgbm_v1/README.md`

#### 결과

- Fold Macro F1: 0.4102706033, 0.4263269667, 0.4099375381,
  0.4143081706, 0.4289890827
- OOF Macro F1: 0.4189078364
- Fold 표준편차: 0.0081051732
- Accuracy: 0.4142880181
- Log Loss: 1.8227982418
- Public LB: 0.3075810937 (제출 ID `1508041`, 2026-08-01 23:36:17 KST)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp125_lightgbm_v1/metrics.json` /
  `reports/exp125_lightgbm_v1/README.md` /
  `reproducibility/exp125_lightgbm_v1/`
- 제출 후보: `submissions/exp125_lightgbm_v1.csv`
  (SHA-256 `e76cce6d911616930570bcf0c5c1adc8adb045fbd18e3226d5378bda026d5940`,
  DACON 미제출)
- 결론: EXP-094 대비 OOF `+0.0020212625`, Log Loss `-0.0171389395`,
  라벨 불일치율 23.11%로 품질·wildcard·다양성 gate를 모두 통과했다.
  EXP-096보다도 OOF `+0.0007925284`, Log Loss `-0.0141359972`, fold
  표준편차 `-0.0013869445`로 개선돼 신규 Local 최고이자 후속 앙상블 후보로
  채택한다.
- 재현 메모: 저장 checkpoint 재추론에서 OOF·test 라벨 100%, 확률 최대 절대
  차이 0, 제출 CSV byte-level SHA-256 일치를 확인했다.

### [EXP-127] 동결 Feature Spec v1 CatBoost GPU

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #127 / issue-127-exp-catboost-v1
- 소스 commit: `03af58890c1cac9d90e61430e550b7ae6cc7060d`
- 시작/종료: 2026-08-01T14:19:39.262553+00:00 /
  2026-08-01T14:26:44.634572+00:00

#### 실행

- 부모: EXP-094, 동결 Feature Spec v1과 canonical 5-fold 유지
- 유일한 모델 변경: XGBoost에서 CatBoost GPU로 교체
- 실행 장비: RunPod NVIDIA RTX 4090 24GB
- Config: `reproducibility/exp127_catboost_v1/config.resolved.yaml`
- Metrics: `reports/exp127_catboost_v1/metrics.json`
- Report: `reports/exp127_catboost_v1/README.md`

#### 결과

- Fold Macro F1: 0.4008452894, 0.4405650635, 0.4173173958,
  0.4115121069, 0.4276474855
- OOF Macro F1: 0.4194572294
- Fold 표준편차: 0.0136136464
- Accuracy: 0.4160619255
- Log Loss: 1.8624933825
- Public LB: 0.3014741179 (제출 ID `1508047`, 2026-08-01 23:41:04 KST)
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- Metrics/Report/Reproduction:
  `reports/exp127_catboost_v1/metrics.json` /
  `reports/exp127_catboost_v1/README.md` /
  `reproducibility/exp127_catboost_v1/`
- 제출 후보: `submissions/exp127_catboost_v1.csv`
  (SHA-256 `f4fdd043a1875a41d333fa88f34911fd0f6f20758a3bd41deea1288d473cb543`,
  DACON 미제출)
- 결론: EXP-125 대비 OOF `+0.0005493930`으로 신규 Local 최고다.
  EXP-094 대비 라벨 불일치율 30.54%, 정오답 상관 0.6962로 diversity gate는
  통과했지만 Log Loss `+0.0225562011`과 fold 변동성 `+0.0057293943`으로
  quality·wildcard gate는 실패했다. 단독 최고 후보로 보존하고 가중치 선택은
  후속 OOF blend 검증에서 결정한다.
- 재현 메모: 저장 checkpoint 재추론에서 OOF·test 라벨 100%, 확률 최대 절대
  차이 0, 제출 CSV byte-level SHA-256 일치를 확인했다. GPU 재학습은
  비결정적일 수 있으므로 `TRAINING_VERIFIED`로 승격하지 않는다.

### [EXP-131] CatBoost v1 extended training

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #131 / issue-131-exp-catboost-v1-extended
- 소스 commit: `b331ce88b854bf4b537b31b69da75b405acae7cf`
- 시작/종료: 2026-08-01T16:34:50.074747+00:00 /
  2026-08-01T16:49:11.467020+00:00

#### 실행

- 부모: EXP-127 (Feature Spec 기준 EXP-094)
- 실행 장비: RunPod Secure Cloud NVIDIA RTX 4090 24GB
- Config: `reproducibility/exp131_catboost_v1_extended/config.resolved.yaml`
- Metrics: `reports/exp131_catboost_v1_extended/metrics.json`
- Report: `reports/exp131_catboost_v1_extended/README.md`
- 변경: iterations 2,000, learning rate 0.03, L2 5.0, early stopping 100
- 고정: Feature Spec v1, canonical 5-fold, depth 8, balanced sample weight

#### 결과

- Fold Macro F1: 0.4041809389, 0.4466974492, 0.4151827021,
  0.4209819717, 0.4246988587
- Best iteration: 1998, 1995, 1999, 1999, 1999
- OOF Macro F1: 0.4222392962
- EXP-127 대비: `+0.0027820668`
- EXP-094 대비: `+0.0053527223`
- Fold 표준편차: 0.0140119367 (EXP-094 대비 +0.0061276846)
- Accuracy: 0.4183196259
- Log Loss: 1.8665114104 (EXP-094 대비 +0.0265740811)
- EXP-127 대비 라벨 불일치율: 0.0596677955
- EXP-127 대비 오류 상관: 0.9502667641
- Public LB: 미제출
- 재현 상태: INFERENCE_VERIFIED

#### 산출물과 결론

- OOF: `oof/exp131_catboost_v1_extended.csv`
- Test probability: `preds/exp131_catboost_v1_extended_test_proba.csv`
- Checkpoint: `models/exp131_catboost_v1_extended/`
- Submission: `submissions/exp131_catboost_v1_extended.csv`
  (SHA-256 `e8d0863118f1170fd209d465197871eefcd1c0661bb8792c8bd2af60b7ce35d3`,
  DACON 미제출)
- 결론: 2,000 iteration 확장은 실제로 적용됐지만 EXP-094 대비 fold 변동성과
  Log Loss가 악화됐다. EXP-127과도 높은 오류 상관과 낮은 라벨 불일치를 보여
  새 diversity 자산으로 보존하지 않는다. 추가 CatBoost iteration 확장은
  중단하고 기존 EXP-127은 보조 후보로 유지한다.
- 재현 메모: checkpoint 재추론에서 OOF·test 라벨 100%, 확률 최대 절대 차이 0,
  제출 CSV byte-level SHA-256 일치를 확인했다. 첫 실행은 Git `user.name` 누락으로
  metadata 단계에서 실패했고, Git 신원 설정 후 동일 commit·config로 재실행한
  성공 실행만 공식 기록에 반영했다.

### [EXP-135] EXP-094 + EXP-125 fixed probability blend

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #135 / issue-135-exp-fixed-blend
- Config: `reproducibility/exp135_fixed_probability_blend/config.resolved.yaml`
- Metrics: `reports/exp135_fixed_probability_blend/metrics.json`

#### 실행과 결과

- 학습 없이 EXP-094와 EXP-125의 OOF·test 확률을 각각 0.5로 평균했다.
- 가중치는 실행·평가 전에 고정했으며 OOF·Public 점수로 조정하지 않았다.
- OOF Macro F1: `0.4201772665`
- Fold Macro F1: `0.4195736455, 0.4316004416, 0.4097589534, 0.4013577659, 0.4348436094`
- Fold 표준편차: `0.0126953092`
- Accuracy: `0.4110627318`
- Log Loss: `1.8083444812`
- 제출 파일: `submissions/exp135_fixed_probability_blend.csv`
- Public LB: 0.3166527939 (제출 ID `1508856`, 2026-08-02 23:07:03 KST)
- 재현 번들: [`exp-135-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-135-repro-v1)
  (`44,786,385` bytes, SHA-256
  `d736b48262f51b0521c4db6fcb55a746e13f62fe60f3f984084d8031dc0cb4f7`)
- 재현 상태: `INFERENCE_VERIFIED`

#### 판단

EXP-094와 EXP-125의 평균은 EXP-125보다 Macro F1이 `+0.0012694301`,
Log Loss가 `-0.014454` 개선됐지만, EXP-131 최고 단일 모델보다 Macro F1이
`-0.0020620298` 낮고 fold 표준편차가 더 크다. 이후 사전 생성된 파일을
리더보드에 제출했지만 EXP-096보다 `-0.0002528810`, EXP-031보다
`-0.0004275910` 낮았다. Public 결과를 이용한 추가 blend 탐색은 하지 않는다.
OOF·test 확률과 제출 CSV의 재생성 해시는 일치했다.

### [EXP-137] EXP-094 + EXP-125 leakage-safe cross-fitted Logistic stacking

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #137 / issue-137-exp-cross-fitted-stacking
- Config: `reproducibility/exp137_cross_fitted_stacking/config.resolved.yaml`
- Metrics: `reports/exp137_cross_fitted_stacking/metrics.json`

#### 실행과 결과

- 두 부모의 26개 확률을 연결한 52차원 입력을 사용했다.
- 각 outer fold의 meta learner는 해당 검증 fold를 제외한 네 fold로만 학습했다.
- 설정: multinomial Logistic Regression, `C=0.2`, `max_iter=1000`, `class_weight=None`.
- OOF Macro F1: `0.4068626451`
- Fold 표준편차: `0.0059257501`
- Accuracy: `0.4650862764`
- Log Loss: `1.8272781305`
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 판단

Accuracy와 fold 표준편차는 개선됐지만 Macro F1이 EXP-131보다 `-0.0153766511`
하락했고 DLBC·PAAD·SARC 등 소수 클래스 F1이 붕괴했다. G6의 채택 기준인
최고 단일 또는 고정 blend 대비 `+0.002`를 충족하지 못하므로 stack은 기각하며,
추가 meta learner·C 탐색은 중단한다.

### [EXP-151] EXP-094 + log1p(mutated_gene_count)

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #151 / issue-151-exp-burden-incremental
- Config: `configs/exp151_burden_incremental.yaml`
- Metrics: `reports/exp151_mutated_gene_burden/metrics.json`
- 보고서: [EXP-151 보고서](reports/exp151_mutated_gene_burden/README.md)

#### 실행과 결과

- EXP-094 frozen Feature Spec에 `log1p(mutated_gene_count)` 하나만 추가했다.
- canonical `stratified_5fold_seed42.csv`와 고정 26개 클래스 순서를 사용했다.
- Secure Cloud RTX 4090에서 XGBoost CUDA 설정으로 실행했다.
- OOF Macro F1: `0.4188970451` (EXP-094 대비 `+0.0020104712`)
- Fold 표준편차: `0.0130000285` (EXP-094 대비 `+0.0051157765`)
- Log Loss: `1.8381872786` (EXP-094 대비 `-0.0017500507`)
- Public LB: `0.3125095748` (제출 ID `1508912`)
- 재현 상태: `INFERENCE_VERIFIED`
- 저장 checkpoint 재추론에서 test 라벨 2,546개와 제출 CSV SHA-256이
  byte-level로 일치했다. GPU→CPU 장치 차이로 확률은 완전히 일치하지 않았으며,
  이 차이는 [comparison](reproducibility/exp151_mutated_gene_burden/comparison.json)에
  보존했다. 재학습 검증은 수행하지 않았다.
- Release: [`exp-151-repro-v2`](https://github.com/fabxoe/open_cancer/releases/tag/exp-151-repro-v2)

#### 실행 소스 정합성

- 정식 runner: `scripts/run_exp151_burden_incremental.py`
- Config: `configs/exp151_burden_incremental.yaml`
- 과거 EXP-154·EXP-158 실행에서 같은 runner 경로가 재사용되어, Git 이력
  `17d433f`의 EXP-151 config·source를 복원했다. 결과와 점수는 변경하지 않았다.

#### 판단

Macro F1과 Log Loss는 개선됐지만 fold 표준편차가 사전 기준인 `0.002`보다 크게
악화됐다. 따라서 burden 피처를 Feature Spec이나 Public 제출 후보로 채택하지 않는다.

### [EXP-154] EXP-094 + log1p(total_variant_count)

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #154 / issue-154-exp-total-variant-burden
- Config: `configs/exp154_total_variant_burden.yaml`
- Metrics: `reports/exp154_total_variant_burden/metrics.json`
- 보고서: [EXP-154 보고서](reports/exp154_total_variant_burden/README.md)

#### 실행과 결과

- EXP-094 frozen Feature Spec에 `log1p(total_variant_count)` 하나만 추가했다.
- canonical `stratified_5fold_seed42.csv`와 고정 26개 클래스 순서를 사용했다.
- Secure Cloud RTX 4090에서 XGBoost CUDA 설정으로 실행했다.
- OOF Macro F1: `0.4183986443` (EXP-094 대비 `+0.0015120704`)
- Fold 표준편차: `0.0135326743` (EXP-094 대비 `+0.0056484223`)
- Log Loss: `1.8371068695` (EXP-094 대비 `-0.0028304598`)
- Public LB: 미제출
- 재현 상태: `NOT_STARTED` (checkpoint inference 및 독립 재학습 번들 미완료)

#### 실행 소스 정합성

- 정식 runner: `scripts/run_exp154_total_variant_burden.py`
- Config: `configs/exp154_total_variant_burden.yaml`
- Git 이력 `e610d75`에 보존된 EXP-154 source를 정식 runner 경로로 복원했다.
  결과와 점수는 변경하지 않았다.

#### 판단

Macro F1과 Log Loss는 개선됐지만 fold 표준편차가 사전 기준인 `0.002`보다 크게
악화됐다. 따라서 total variant burden을 Feature Spec이나 Public 제출 후보로
채택하지 않는다. OOF·test 확률과 checkpoint는 후속 안정성·다양성 분석을 위해 보존한다.

### [EXP-156] 유전자별 변이 효과 압축 XGBoost

- 상태: COMPLETED
- 실행자: Gomin-art
- Issue/브랜치: #156 / `issue-156-exp-gene-variant-effect-compression`
- 소스 commit: `5b1cff179ee68bc8f873f4f9dd4c73305aec3e65`
- 시작/종료: 2026-08-03T02:02:48.601660+00:00 /
  2026-08-03T02:34:46.087252+00:00

#### 실행

- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: 유전자별 변이유형 indicator 5종(21,920개)을 severity max,
  variant count 1/2+, effect diversity, complex/unparsed의 compact descriptor
  4종(17,536개)으로 교체했다.
- 최종 특징 수: 30,735개 (EXP-094 대비 4,384개 감소)
- canonical stratified 5-fold seed 42, 고정 클래스 순서, XGBoost 설정과
  balanced sample weight는 유지했다.
- Config: `configs/exp156_gene_variant_effect_compression.yaml`
- Resolved config:
  `reproducibility/exp156_gene_variant_effect_compression/config.resolved.yaml`
- Metrics: `reports/exp156_gene_variant_effect_compression/metrics.json`
- Report: `reports/exp156_gene_variant_effect_compression/README.md`

#### 결과

- Fold Macro F1: 0.4167162891, 0.4245570144, 0.3968599918,
  0.4040592976, 0.4307377819
- OOF Macro F1: 0.4148494335 (EXP-094 대비 `-0.0020371404`)
- Fold 표준편차: 0.0125687084 (EXP-094 대비 `+0.0046844563`)
- Accuracy: 0.4063860668 (EXP-094 대비 `-0.0008063216`)
- Log Loss: 1.8308399556 (EXP-094 대비 `-0.0090973737`)
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

#### 산출물과 결론

- checkpoint 재추론에서 제출 SHA-256과 test 라벨 100%가 일치했고,
  test 확률 최대 절대 차이는 `5.93e-08`이었다.
- 유전자별 효과 피처를 4,384개 줄이고 Log Loss를 개선했지만, 공식 Macro F1이
  하락하고 fold 표준편차가 허용치보다 악화되어 `ARCHIVE`한다. compact effect
  구성을 Feature Spec에 채택하거나 리더보드에 제출하지 않는다.
- Reproduction:
  `reproducibility/exp156_gene_variant_effect_compression/comparison.json`

### [EXP-158] EXP-094 + log1p(missense_count)

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #158 / issue-158-exp-missense-burden
- 부모 실험: EXP-094
- Config: `configs/exp158_missense_burden.yaml`
- Metrics: `reports/exp158_missense_burden/metrics.json`
- 보고서: [EXP-158 보고서](reports/exp158_missense_burden/README.md)

#### 실행과 결과

- EXP-094 frozen Feature Spec에 `log1p(missense_count)` 하나만 추가했다.
- canonical `stratified_5fold_seed42.csv`, seed 42, XGBoost CUDA를 사용했다.
- Secure Cloud RTX 4090에서 171.1666초 동안 5-fold를 실행했다.
- OOF Macro F1: `0.4183327348` (EXP-094 대비 `+0.0014461609`)
- Fold 표준편차: `0.0111795533` (EXP-094 대비 `+0.0032953012`)
- Log Loss: `1.8384449866` (EXP-094 대비 `-0.0014923427`)
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 실행 소스 정합성

- 정식 runner: `scripts/run_exp158_missense_burden.py`
- Config: `configs/exp158_missense_burden.yaml`
- 과거 `scripts/run_exp151_burden_incremental.py`에 있던 EXP-158 source를
  EXP-ID에 맞는 runner 경로로 이동했다. 결과와 점수는 변경하지 않았다.

#### 판단

Macro F1과 Log Loss는 개선됐지만 fold 표준편차가 사전 기준인 `0.002`보다 크게
악화됐다. 따라서 missense burden을 Feature Spec이나 Public 제출 후보로 채택하지
않는다. 저장 checkpoint 재추론 확률도 원본 실행과 정확히 일치하지 않아
`INFERENCE_VERIFIED`로 승격하지 않고, 원본 OOF·test 확률과 checkpoint만 분석용으로 보존한다.

### [EXP-160] Residue-position negative control (Issue #80 후속)

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #160 / issue-160-negative-control-residue-position
- 소스 commit: `53e6233ee533ec20a3dd7acdbeda0c0a607e5eb1`
- 시작/종료: 2026-08-02T03:14:08.927601+00:00 /
  2026-08-02T04:50:34.263043+00:00

#### 실행

- Config: `reproducibility/exp160_residue_position_negative_control/config.resolved.yaml`
- Metrics: `reports/exp160_residue_position_negative_control/metrics.json`
- Permutation 상세: `reports/exp160_residue_position_negative_control/permutation_detail.json`
- Report: `reports/exp160_residue_position_negative_control/README.md`
- 부모 실험: EXP-069 (max residue-position, `transform: raw`)
- 배경: `scripts/explore_hotspot_numbering_consistency.py` 실행 결과 패널 전체
  402,443개 (gene, position) 조합 중 14,685개(3.6490%)가 reference amino acid
  불일치를 보였고, `max_residue_position`은 이 검증을 거치지 않은 원시 값임을
  확인했다. Issue #80의 "후속 negative control 계약"과 `PROJECT_CONTEXT.md`
  §4의 동일 규칙을 실행한다.
- 방법: EXP-069와 동일한 v1 feature matrix를 재사용하고, 각 outer fold의 train
  부분에서만 유전자별로 `max_residue_position` 값을 해당 유전자의
  mutation-type(missense/synonymous/nonsense/frameshift/complex) strata 안에서
  무작위 재배치했다. Validation 위치와 다른 모든 피처는 원본 그대로 유지, test는
  사용하지 않았다. 5개 고정 permutation seed(1001–1005)로 반복했고, 모델
  `random_state`는 EXP-069와 동일하게 `42 + fold`로 고정해 permutation 효과만
  분리했다.

#### 결과

- 원본(EXP-069) OOF Macro F1: `0.4131007993`, fold 표준편차: `0.0082058569`
- Permuted OOF Macro F1(5 seed 평균): `0.3987413040`, seed 간 표준편차:
  `0.0023074239`
- 전체 차이(permuted 평균 - 원본): `-0.0143594953`
- Fold별 차이(permuted 평균 - 원본): fold0 `-0.0110250121`, fold1
  `-0.0196334319`, fold2 `-0.0089344139`, fold3 `-0.0216405424`, fold4
  `-0.0144066194` — 5개 fold 전부 하락
- 25개 (seed, fold) 조합 중 24개가 원본보다 낮았다. 유일한 예외는 seed 1003의
  fold 0(`+0.0012132900`)로 permutation seed 잡음 범위 안이다.
- Public LB: 미제출(진단 실험)
- 재현 상태: `NOT_STARTED` (일반 Local 실험, 리더보드 미제출이라
  `INFERENCE_VERIFIED` manifest 불필요)

#### 산출물과 결론

- Metrics/Report: `reports/exp160_residue_position_negative_control/`
- 결론: gene×mutation-type 소속 정보를 그대로 보존한 채 위치 값만 fold-train
  안에서 재배치했는데도 5개 fold, 25개 조합 중 24개에서 일관되게 성능이
  하락했다. `max_residue_position`은 노이즈가 아니라 fold를 넘어 일반화되는
  실제 예측 신호를 담고 있다고 판단한다. Feature Spec v1을 그대로 유지하고,
  Issue #80의 negative control 계약을 이 결과로 종료 처리한다. 다만 이 결과는
  "신호가 실재한다"만 증명하며, 그 신호가 생물학적 hotspot·기능부위 효과인지
  다른 상관 요인(코호트, transcript 넘버링 관례 등)인지는 별도 분석이 필요하고
  이 실험만으로 단정하지 않는다.

### [EXP-170] Cell Cycle pathway aggregation — A: any-nonsilent

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #170 / issue-170-cellcycle-any-nonsilent
- 소스 commit: `ab45c0df34eea7ae1b5c3fe686b7245fc22aec6b`
- 시작/종료: 2026-08-02T06:07:07.539226+00:00 /
  2026-08-02T06:24:10.011609+00:00

#### 실행

- Config: `configs/exp170_cellcycle_any_nonsilent.yaml`
- Resolved config: `reproducibility/exp170_cellcycle_any_nonsilent/config.resolved.yaml`
  (PR #172 리뷰 반영, 재학습 없음: `pathway__cellcycle_any_nonsilent`을 Feature
  Factory family로 등록하고 KnowledgeProvenance를 연결, 값은 기존과 동일함을
  전체 train/test로 검증)
- Metrics: `reports/exp170_cellcycle_any_nonsilent/metrics.json`
- Verdict 상세: `reports/exp170_cellcycle_any_nonsilent/verdict.json`
- Report: `reports/exp170_cellcycle_any_nonsilent/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 배경: Issue #167/#168 gene→pathway 카탈로그를 이용한 첫 pathway-level
  aggregation feature 파일럿(3단계 계획 중 A). Cell Cycle 15개 유전자
  전부 패널에 존재(커버율 100%), TP53 pathway 시트와 유전자 중복 없음.
  사전 체크: 이 15개 유전자 중 기존 34-position hotspot 리스트
  (`EXTENDED_HOTSPOTS`)에 포함된 유전자는 0개.
- 유일한 변경: EXP-094 Feature Spec v1에 `P_any_nonsilent_cellcycle`
  (Cell Cycle 15개 유전자 중 하나라도 nonsilent 변이 존재 시 1) 1개 컬럼
  추가. `src/open_cancer/pathway_aggregation_features.py`에 하드코딩된
  유전자 목록 사용(원본 카탈로그 CSV는 라이선스상 gitignore).

#### 결과

- Fold Macro F1: 0.4050374712, 0.4114668555, 0.4027850421,
  0.4203272259, 0.4273778799
- OOF Macro F1: 0.4137462167 (EXP-094 대비 `-0.0031403572`)
- Fold 표준편차: 0.0092705323 (EXP-094 대비 `+0.0013862802`)
- Log Loss: 1.8389285166 (EXP-094 대비 `-0.0010088127`)
- Train/Test positive rate: 8.51% / 10.76%
- 클래스별 최악 하락: DLBC `-0.0500857633`(최소 클래스, 38 샘플), LIHC
  `-0.0386`
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 산출물과 결론

- Metrics/Report: `reports/exp170_cellcycle_any_nonsilent/`
- 승격 기준 대조: Macro F1 +0.001 이상 실패, fold-std 악화 0.002 미만 통과,
  Log Loss 악화 없음 통과, 전 클래스 F1 악화 없음 실패(DLBC)
- 결론: Macro F1 gate와 클래스별 F1 gate를 모두 통과하지 못해 기각한다.
  fold-std·log loss가 소폭 개선된 것은 DLBC 등 소수 클래스의 큰 손실을
  상쇄하지 못하며, `colsample_bytree=0.8` 아래에서 새 컬럼이 기존 컬럼들의
  split 후보 선택 확률을 바꾸는 weighting perturbation 효과로 해석하고
  생물학적 신호로 단정하지 않는다(EXP-063/078 semantics QC와 같은 메커니즘).
  Issue #170 계획상 B는 "A 결과가 반영된 baseline"에서 진행하기로 했으나
  A가 기각됐으므로, 후속 B(`P_lof_in_tsg_cellcycle`)는 EXP-094(원본 v1)를
  그대로 baseline으로 사용하는 새 Experiment Issue에서 진행한다.
- **Update(POLE D/E와 함께 완료)**: macro-f1-checkpoint 정책으로 재평가한
  결과(재학습 없음) EXP-219 대비 `-0.0035`로 기각이 유지됐다. 상세:
  `reports/analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md`.

### [EXP-173] Cell Cycle pathway aggregation — B: LoF-in-TSG

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #173 / issue-173-cellcycle-lof-tsg
- 소스 commit: `0974f0cc4daf3ac3f61c21087c25859397a494de`
- 시작/종료: 2026-08-02T06:43:12.981082+00:00 /
  2026-08-02T07:01:29.671269+00:00

#### 실행

- Config: `configs/exp173_cellcycle_lof_tsg.yaml`
- Resolved config: `reproducibility/exp173_cellcycle_lof_tsg/config.resolved.yaml`
  (PR #172 리뷰 패턴을 선제 적용, 재학습 없음)
- Metrics: `reports/exp173_cellcycle_lof_tsg/metrics.json`
- Verdict 상세: `reports/exp173_cellcycle_lof_tsg/verdict.json`
- Report: `reports/exp173_cellcycle_lof_tsg/README.md`
- 부모 실험: EXP-094 (Feature Spec v1) — EXP-170이 아님(기각됨)
- 사전 체크: TSG 6개 유전자(CDKN1A, CDKN1B, CDKN2A, CDKN2B, CDKN2C, RB1)의
  truncating 변이가 train.csv 전체에서 DLBC(38개, 0%), LAML(158개, 0%),
  TGCT(124개, 0%)에 대해 단 한 번도 양성인 적이 없음을 실제 데이터로
  확인했다.
- 유일한 변경: EXP-094 Feature Spec v1에 `P_lof_in_tsg_cellcycle`(TSG 6개
  유전자 중 하나라도 truncating(nonsense/frameshift) 변이 존재 시 1) 1개
  컬럼 추가.

#### 결과

- Fold Macro F1: 실제 fold별 값은 `reports/exp173_cellcycle_lof_tsg/metrics.json` 참고
- OOF Macro F1: 0.4135108482 (EXP-094 대비 `-0.0033757257`)
- Fold 표준편차: 0.0096510379 (EXP-094 대비 `+0.0017667858`)
- Log Loss: 1.8393128496 (EXP-094 대비 `-0.0006244796`)
- Train/Test positive rate: 4.06% / 2.28%
- Watch class(DLBC, LAML) — 둘 다 train 양성률 0%인데 반대 방향으로 하락/개선:
  DLBC F1 `-0.0137221269`, LAML F1 `+0.0237573099`(전체 클래스 중 최고 개선)
- 클래스별 최악 하락: LUAD `-0.0235651625` (EXP-170의 DLBC와 다른 클래스)
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 산출물과 결론

- Metrics/Report: `reports/exp173_cellcycle_lof_tsg/`
- 승격 기준 대조: Macro F1 +0.001 이상 실패, fold-std 악화 0.002 미만 통과,
  Log Loss 악화 없음 통과, 전 클래스 F1 악화 없음 실패(LUAD)
- 결론: Macro F1 gate와 클래스별 F1 gate를 모두 통과하지 못해 기각한다.
  DLBC/LAML은 feature 값이 항상 0인데도 반대 방향(하락/개선)으로 움직여,
  "혈액암 계열에 체계적으로 불리하다"는 가설이 아니라 EXP-170과 같은
  weighting perturbation 해석을 뒷받침한다. 가장 크게 하락한 클래스가
  EXP-170(DLBC)과 EXP-173(LUAD)에서 서로 다르다는 점도 매번 다른 무작위적
  perturbation이라는 해석과 일관된다. TSG 6개로 범위를 좁혔음에도(A의 15개
  대비) 기각된 것은 Cell Cycle pathway aggregation 방향 자체가 이 Feature
  Spec v1 위에서 추가 신호를 주기 어렵다는 신호로 본다. C(`P_hotspot_in_
  oncogene_cellcycle`)는 B도 기각된 점을 고려해 진행 여부를 재검토한다.
- **Update(POLE D/E와 함께 완료)**: macro-f1-checkpoint 정책으로 재평가한
  결과(재학습 없음) EXP-219 대비 `-0.0031`로 기각이 유지됐다. COAD는 여기서도
  `+0.0034`로 여전히 양의 방향(Cell Cycle/POLE 공통 관찰, 판단 보류). 상세:
  `reports/analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md`.

### [EXP-179] Feature Spec v1 + fold-local SMOTE

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #179 / `issue-179-xgb-feature-spec-v1-smote`
- 원 실행 소스 commit: `704731a20520339e21f4c84eae93708d2e1dfd3e`
- 시작/종료: 2026-08-02T07:45:42.682703+00:00 /
  2026-08-02T08:59:03.414230+00:00

#### 실행

- Config: `configs/exp179_xgb_feature_spec_v1_smote.yaml`
- Resolved config: `reproducibility/exp179_xgb_feature_spec_v1_smote/config.resolved.yaml`
- Runner: `scripts/run_exp179_xgb_feature_spec_v1_smote.py`
- Metrics: `reports/exp179_xgb_feature_spec_v1_smote/metrics.json`
- Report: `reports/exp179_xgb_feature_spec_v1_smote/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: canonical 5-fold의 각 outer-fold **학습 행에만** standard SMOTE를
  적용했다. `k_neighbors=5`, `sampling_strategy=not majority`, seed는 fold별
  `42..46`이며 validation·test에는 적용하지 않았다. 이중 보정을 피하기 위해
  `balanced_sample_weight=false`로 고정했다.
- SMOTE 후 fold별 학습 행 수: 16,354 / 16,354 / 16,354 / 16,328 / 16,354
  (원본 outer-train은 4,960 또는 4,961행).

#### 결과

- Fold Macro F1: 0.3974984540, 0.3992874129, 0.4138424225,
  0.4127372064, 0.4123181959
- OOF Macro F1: 0.4080771375 (EXP-094 대비 `-0.0088094364`)
- Fold 표준편차: 0.0071789606 (EXP-094 대비 `-0.0007052914`)
- Accuracy: 0.4046121593 (EXP-094 대비 `-0.0025802290`)
- Log Loss: 1.8043550352 (EXP-094 대비 `-0.0355822941`)
- 크게 개선된 클래스: DLBC `+0.05121`, GBMLGG `+0.04544`, TGCT `+0.04042`
- 크게 하락한 클래스: LGG `-0.11775`, BLCA `-0.10784`, SARC `-0.08514`
- Public LB: 미제출

#### 재현성·결론

- 원 실행은 metrics와 checkpoint를 남긴 뒤 산출물 기록 단계가 중단됐다. 저장된
  5개 checkpoint를 `--replay-checkpoints`로 재추론했으며, 재학습은 하지 않았다.
- OOF·test 라벨은 100% 일치, 확률 최대 차이 0, submission SHA-256은 일치했고
  OOF Macro F1 차이도 0이어서 `INFERENCE_VERIFIED`로 기록한다. 독립 재학습은
  수행하지 않았으므로 `TRAINING_VERIFIED`는 아니다.
- SMOTE는 일부 소수 클래스와 Log Loss에는 이득이 있었지만 Macro F1의 큰 하락과
  다수 클래스 붕괴를 상쇄하지 못했다. EXP-094 Feature Spec v1의 후속 기준에서는
  `ARCHIVE`로 보존하며, 리더보드 제출 및 SMOTE 파라미터 재탐색은 진행하지 않는다.

### [EXP-181] POLE ED hotspot features — D: hotspot5

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #181 / issue-181-pole-hotspot5
- 소스 commit: `baaf99ab5c5cbf6f26c2492f3620a4f425e25b10`
- 시작/종료: 2026-08-02T~ / (공식 seed 42 실행, 전체 4-seed 총 4046.84초)

#### 실행

- Config: `configs/exp181_pole_hotspot5.yaml`
- Resolved config: `reproducibility/exp181_pole_hotspot5/config.resolved.yaml`
- Metrics: `reports/exp181_pole_hotspot5/metrics.json`
- Verdict 상세(stability_check 포함): `reports/exp181_pole_hotspot5/verdict.json`
- UCEC/COAD/DLBC 4-seed per-class 상세: `reports/exp181_pole_hotspot5/watch_class_stability.json`
- Report: `reports/exp181_pole_hotspot5/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 배경: Cell Cycle pathway aggregation(#170 EXP-A, #173 EXP-B)이 연속
  기각되고 #174 정책 문서가 "여러 유전자 OR" 방향의 우선순위를 낮춘 것과
  달리, 이 실험은 단일 유전자(POLE) 기존 컬럼을 위치 특이적으로 정밀화하는
  설계로 팀이 이미 채택한 hotspot-34 방식과 구조적으로 동일하다(Vera
  Health 자문 반영).
- 유일한 변경: `src/open_cancer/pole_ed_features.py`의 `PoleEdFamily`로
  등록한 `pole__hotspot5`(POLE이 P286R/V411L/S297F/A456P/S459F 중 하나를
  가지면 1) 1개 컬럼 추가. Feature Factory family로 처음부터 등록해
  PR #172 리뷰 패턴을 재사용했다(KnowledgeProvenance는 파일이 아니라
  문헌 인용 hardcoded literal, `EXTENDED_HOTSPOTS`와 동일 관례).
- 사전 검증: train.csv에서 양성 22건(0.355%), fold별 분포
  `{0:8, 1:5, 2:5, 3:1, 4:3}`(fold 3에 1건뿐)을 확인해 3-seed
  stability check(1001/1002/1003, model seed만 다르고 나머지는 공식 seed
  42와 동일)를 계획했다.

#### 결과

- OOF Macro F1(공식 seed 42): 0.4137048981 (EXP-094 대비 `-0.0031816758`)
- Fold 표준편차: -0.0000634560(개선), Log Loss: -0.0013797525(개선)
- 최대 하락 클래스: DLBC `-0.0500857633`
- **Seed별 개별 수치**: 42(공식) 0.4137048981(delta -0.0031816758), 1001
  0.4169853250(+0.0000987511), 1002 0.4178158047(+0.0009292308), 1003
  0.4169726284(+0.0000860545). stability 3-seed 표준편차 0.000395로
  baseline 근방에 뭉쳐있고, 공식 seed 42만 4개 중 뚜렷한 이상치(4-seed
  전체 표준편차 약 0.00268)다.
- **UCEC/COAD/DLBC 4-seed per-class 재검증**(재학습 없이 seed 42는 저장된
  OOF 재사용, 1001/1002/1003만 재실행해 기존 fold별 점수와 완전히 일치함을
  먼저 확인): COAD는 4개 seed 전부 양의 delta(+0.0051~+0.0152, 평균
  +0.0076, std 0.0044)로 일관됐다. UCEC(3/4 음수)와 DLBC(2/4 음수, std가
  평균보다 훨씬 큼)는 방향이 일관되지 않았다.
- DLBC row-level 대조(별도 노트
  `reports/analysis/sparse_binary_feature_dlbc_sensitivity.md`): EXP-170과
  DLBC "예측=positive 집합"이 완전히 동일(17개 ID 일치)해 F1이 같았음을
  확인했고, 4-seed 결과는 그 결정 경계 자체가 seed에 따라 다시 흔들린다는
  것을 보여줘 perturbation 해석을 강화한다.
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### 산출물과 결론

- Metrics/Report: `reports/exp181_pole_hotspot5/`
- 승격 기준 대조(공식 seed 42): Macro F1 +0.001 이상 실패, fold-std 통과,
  Log Loss 통과, 전 클래스 F1 악화 없음 실패(DLBC)
- 결론: 공식 판정(seed 42 기준)은 프로젝트 컨벤션대로 **기각**을 유지한다.
  다만 seed 42가 4개 중 뚜렷한 이상치였다는 점, COAD가 4-seed 전부 일관된
  양의 방향을 보였다는 점은 투명하게 기록한다. 다음 후보 E
  (`POLE_ED_driver_extended`)는 baseline을 EXP-094로 유지하고, fold 분포가
  D보다 덜 치우친 점을 활용해 진행 여부를 재판단한다.
- **Update(EXP-226과 함께 완료)**: macro-f1-checkpoint 정책으로 재평가한
  결과(재학습 없음, 저장된 checkpoint 재사용) EXP-219 대비 `-0.0038`로
  기각이 유지됐다. 상세:
  `reports/analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md`.

### [EXP-226] POLE ED hotspot features — E: driver_extended (D의 COAD 신호 확증)

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #226 / issue-226-pole-ed-driver-extended
- 소스 commit: `4a25c17` (prepare 커밋)

#### 실행

- Config: `configs/exp226_pole_ed_driver_extended.yaml`
- Resolved config: `reproducibility/exp226_pole_ed_driver_extended/config.resolved.yaml`
- Metrics: `reports/exp226_pole_ed_driver_extended/metrics.json`
- Verdict 상세: `reports/exp226_pole_ed_driver_extended/verdict.json`
- Report: `reports/exp226_pole_ed_driver_extended/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 배경: D(EXP-181)의 4-seed stability 검증에서 COAD F1 delta가 4/4 seed
  전부 일관되게 양의 방향이었던 것을, 표본이 소폭 늘어난(22→28건) E로
  확증하기 위한 실험. 성능 개선이 아니라 확증이 목적이라 official seed
  42 단일 실행만 하고 3-seed stability check는 생략했다. 새 feature
  코드는 없고 `pole_ed_driver_extended_family()`(EXP-181에서 이미 구현)를
  재사용했다.
- 사전 검증: train.csv에서 양성 28건(0.452%), fold별 분포
  `{0:8, 1:5, 2:5, 3:2, 4:8}`(D의 `{0:8,1:5,2:5,3:1,4:3}`보다 fold 3
  쏠림이 1→2건으로 완화).

#### 결과

- OOF Macro F1: 0.4141560542 (EXP-094 대비 `-0.0027305197`)
- Fold 표준편차: +0.0003478711(게이트 통과), Log Loss: -0.0016359968(개선)
- **COAD delta: +0.005080180477105012** — D(seed 42)와 정확히 동일한
  부호·숫자값. row-level 대조 결과 COAD "예측=positive 집합" 자체가
  D→E 확장에도 불변이었다(결정 경계 유지, 재현이라기보다 안정성 확인).
- UCEC -0.0087, DLBC -0.0501(D의 seed 42와 완전 동일 — DLBC 예측
  집합도 불변)
- Public LB: 미제출
- 재현 상태: `NOT_STARTED`

#### Macro-F1-checkpoint 재평가 (post-hoc, 재학습 없음)

D와 함께 Cell Cycle A/B(EXP-170/173)까지 총 4개 실험을 저장된 checkpoint로
재평가했다(`scripts/verify_macro_f1_checkpoint_reevaluation.py`,
`audit_xgboost_validation_iterations` 재사용). 올바른 비교 대상인
EXP-219(같은 정책의 EXP-094) 기준으로 E는 `-0.0040`, D는 `-0.0038`,
Cell Cycle A/B는 각각 `-0.0035`/`-0.0031`로 **4개 전부 기각이 유지됐다.**
checkpoint 정책 전환 자체는 4개 모두에서 `+0.004~0.006`의 개선을 보였지만,
같은 정책을 쓴 EXP-219와 비교하면 feature 자체의 효과는 여전히 마이너스다.
COAD는 EXP-219 대비로도 4개 전부 양의 방향(`+0.0034`~`+0.0109`)을
유지했다. 전체 방법론·수치·COAD 잔여 신호에 대한 두 가지 대안 가설(생물학적
신호 vs checkpoint-클래스 구조적 상호작용, 판단 보류)은
`reports/analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md`에
정리했다.

#### 산출물과 결론

- Metrics/Report: `reports/exp226_pole_ed_driver_extended/`
- 결론: mlogloss-checkpoint와 macro-f1-checkpoint 재평가 두 정책 모두에서
  기각이 확정됐다. 게이트가 발동하지 않았으므로 #174 정책 문서의 결론을
  재검토할 근거도 없다. **POLE pilot 트랙(D/E)을 최종 종료한다.**
  F(`POLE_ED_any_missense`)는 진행하지 않는다.

### [EXP-188] C1 보수적 Phi/Jaccard 상관 삭제

- 상태: COMPLETED
- 실행자: fabxoe
- Issue/브랜치: #188 / `issue-188-c1-conservative-correlation-pruning`
- 소스 commit: `1ff0663af2f682229d715136119e8e1db6bace62`
- 시작/종료: 2026-08-02T09:37:00.328570+00:00 /
  2026-08-02T09:46:22.197750+00:00

#### 실행

- Config: `configs/exp188_c1_phi_jaccard_pruning.yaml`
- Runner: `scripts/run_exp188_c1_phi_jaccard_pruning.py`
- Metrics: `reports/exp188_c1_phi_jaccard_pruning/metrics.json`
- Report: `reports/exp188_c1_phi_jaccard_pruning/README.md`
- 부모 실험: EXP-094 (Feature Spec v1)
- 유일한 변경: 각 canonical outer fold의 **학습 행에서만** Phi≥0.30,
  Jaccard≥0.15, 공동 변이 수≥20 기준으로 `GENE__mutated` 열을 greedy
  non-overlap pruning했다. validation·test에는 해당 fold에서 저장한 동일 mask를
  적용했고, mutation-type·missing·position·aggregate·hotspot 열은 보존했다.
- balanced sample weight는 유지했고 SMOTE는 적용하지 않았다.

#### 결과

- Fold Macro F1: 0.4135842952, 0.4183324059, 0.4020332026,
  0.4167836837, 0.4366075326
- OOF Macro F1: 0.4179737169 (EXP-094 대비 `+0.0010871430`)
- Fold 표준편차: 0.0111431892 (EXP-094 대비 `+0.0032589371`)
- Accuracy: 0.4075149169
- Log Loss: 1.8403107969 (EXP-094 대비 `+0.0003734676`)
- fold별 제거 열: 6 / 13 / 8 / 13 / 8개 (전체 고유 유전자 32개)
- 후보 pair/매칭 pair: fold별 7/6, 20/13, 9/8, 22/13, 9/8
- Public LB: `0.3140052334` (제출 ID `1508914`)
- 재현 상태: `INFERENCE_VERIFIED` — 저장된 fold별 mask와 checkpoint에서
  재생성한 OOF·test 확률과 submission SHA-256이 원본과 완전히 일치했다.
  재학습 검증은 수행하지 않았다.
- Release: [`exp-188-repro-v2`](https://github.com/fabxoe/open_cancer/releases/tag/exp-188-repro-v2)

#### 결론

- Macro F1만 보면 성능 채택 하한을 간신히 넘었지만, fold-std 악화가 허용치
  0.002를 넘고 Log Loss도 악화됐다. 따라서 사전 고정 성능 gate를 통과하지 못해
  `ARCHIVE`다.
- 이 판단은 threshold를 재조정하거나 Public LB를 본 뒤 내린 것이 아니다. C2와
  C3은 미리 고정된 별도 실험으로만 이어가며, C1 설정을 추가 튜닝하지 않는다.

### [EXP-257] functional_role_burden_extended — oncogene/TSG count 세분화

- 상태: COMPLETED
- 실행자: Kangho-Park
- Issue/브랜치: #257 / `issue-257-functional-role-burden-extended`
- 소스 commit: `56b1b1d3515b9ff09f36fc7ca691ccdeaf53d487`
- 시작/종료: 2026-08-03T09:13:49.069134+00:00 /
  2026-08-03T09:41:42.994083+00:00 (1674.48초)

#### 실행

- 부모: EXP-096(Feature Spec v1 + fixed_pathway_burden 20개), #176(기본형
  4-feature ablation, 3주 무착수)을 EXP-229 패턴(pathway 축 count 세분화
  성공)과 같은 원리로 functional_role 축에 적용
- 유일한 변경: `knowledge/abc_c_compact_groups_v1.json`의 functional_roles
  (oncogene 29개, tumor_suppressor 39개)마다 mutated-gene count의 4가지
  파생 view(`count_raw`, `count_frac`, `count_resid`, `count_log1p`, 최대
  8개)를 fold-train 게이팅(포화 P(raw==0)<0.05, 희소 P(raw>0)<0.01, 독점성
  dominance>=0.8) 후 추가
  - `src/open_cancer/functional_role_extended_features.py`:
    `FunctionalRoleBurdenExtendedFamily`(`fit_scope=fold_train`)
  - `count_resid`는 fold-train만으로 `count_raw ~ 전체 mutated_gene_count`
    선형회귀를 적합하고 validation/test에는 transform만 적용
  - `semantic_equivalence_filter`로 v1 base + 기존 `fixed_pathway_burden`
    20개와 fold-train 값이 완전히 같은 열 제거(5개 fold 전부 0개 제거)
- Config: `configs/exp257_functional_role_burden_extended.yaml`
- Metrics: `reports/exp257_functional_role_burden_extended/metrics.json`
- Report: `reports/exp257_functional_role_burden_extended/README.md`
- 게이팅 상세: `reports/exp257_functional_role_burden_extended/fold_gating.json`

#### 결과

- Fold Macro F1: 0.4171422593, 0.4104494955, 0.3974636031, 0.4070142779,
  0.4241384592
- OOF Macro F1: 0.4118051266 (EXP-096 대비 `-0.0063101814`)
- Fold 표준편차: 0.0090496148 (EXP-096 대비 `-0.0004425028`)
- Accuracy: 0.4015481374 (EXP-096 대비 `-0.0062893082`)
- Log Loss: 1.8515084982 (EXP-096 대비 `+0.0145742893`)
- 클래스별: 26개 중 19개 하락(최대 LAML `-0.0244`), 개선 6개(최대 DLBC
  `+0.0582`), TGCT 변화 없음
- 5개 fold 전부 게이트 미발동, 8개 candidate 전부 유지, v1/pathway burden과
  완전 중복 0개
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED` — 저장 checkpoint 재추론으로 OOF·test
  라벨 100%, 확률 최대 절대 차이 2.98e-08, 제출 CSV SHA-256 일치를 확인했다.

#### 결론

- Macro F1·Accuracy·Log Loss가 모두 뚜렷하게 악화돼 `ARCHIVE`다. fold
  표준편차만 소폭 개선(-0.0004)됐으나 다른 지표 악화를 상쇄하지 못한다.
- 게이팅이 전혀 발동하지 않았다는 건 8개 열 자체가 통계적으로 위험한
  형태(포화·희소·독점)는 아니었다는 뜻이며, 그럼에도 성능이 하락한 건
  functional role(oncogene/TSG) 그룹 정의 자체가 pathway 축만큼 암종
  판별에 유용한 신호를 담고 있지 않을 가능성을 시사한다.
- DLBC만 크게 개선(`+0.0582`)됐으나, 이번 세션에서 반복 확인한 DLBC의
  구조적 config-민감성(`reports/analysis/sparse_binary_feature_dlbc_sensitivity.md`)을
  고려해 단일 실험만으로 원인을 특정하지 않는다.
- #176은 이 결과로 대체·종료하며, 추가 튜닝이나 제출 없이 마무리한다.
