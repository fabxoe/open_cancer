# Parser native v3 일반화 진단

이 분석은 EXP-479의 비튜닝 HGVS-informed semantic baseline을 설명하기 위한
QC다. test는 train/test shift 진단에만 사용했으며 feature 삭제·가중치·threshold
선택에는 사용하지 않았다. TreeSHAP은 canonical fold의 validation 행만 사용했다.

## 핵심 결과

- 최종 feature 수: `39,467`
- 전체 train/test domain OOF AUC: `0.714585`
- TreeSHAP 표본: `260`행

| family | 열 수 | train row prevalence | test row prevalence | standalone AUC | leave-one-out AUC | SHAP share |
|---|---:|---:|---:|---:|---:|---:|
| base_sample_aggregate | 4 | 98.48% | 98.78% | 0.720289 | 0.714201 | 27.41% |
| gene_mutation_presence | 4384 | 98.48% | 98.78% | 0.704736 | 0.717101 | 32.46% |
| missingness | 4384 | 0.00% | 5.03% | 0.522061 | 0.724436 | 0.00% |
| native_frameshift | 4385 | 52.80% | 64.49% | 0.631894 | 0.721353 | 4.17% |
| native_missense | 4385 | 97.03% | 97.60% | 0.694332 | 0.718339 | 22.56% |
| native_no_change | 4385 | 84.68% | 90.49% | 0.682752 | 0.719005 | 10.21% |
| native_nonsense | 4385 | 52.67% | 61.23% | 0.613953 | 0.715769 | 3.12% |
| native_range_no_change | 4385 | 0.76% | 0.35% | 0.502212 | 0.718186 | 0.05% |
| native_range_replacement | 4385 | 1.63% | 0.63% | 0.505247 | 0.718770 | 0.02% |
| native_range_stop | 4385 | 0.90% | 0.43% | 0.502594 | 0.718186 | 0.01% |

| range family | 열 수 | train row prevalence | test row prevalence | standalone domain AUC | SHAP share |
|---|---:|---:|---:|---:|---:|
| native_range_replacement | 4385 | 1.6288% | 0.6284% | 0.505247 | 0.0153% |
| native_range_stop | 4385 | 0.9031% | 0.4321% | 0.502594 | 0.0076% |
| native_range_no_change | 4385 | 0.7579% | 0.3535% | 0.502212 | 0.0491% |

## EXP-469 → EXP-479 OOF 변화

- 전체 6,201행 중 예측 라벨 변경: `603`행
  (`9.72%`)
- EXP-469만 정답: `142`행
- EXP-479만 정답: `122`행
- range 의미가 하나라도 있는 `182`행의 accuracy 변화:
  `0.5769 → 0.5989`
  (`+0.0220`)
- range 의미가 없는 `6,019`행의 accuracy 변화:
  `0.3986 → 0.3946`
  (`-0.0040`)

새 range family는 희소하지만 트리 구조와 boosting 경로를 바꾸므로 range가 없는
행의 예측도 달라질 수 있다. 따라서 fixed XGBoost 점수 하락을 range 보유 행의
직접 효과로만 해석하지 않는다.

## 주요 해석

1. 새 range 의미는 **해당 행에서 유효했다**. `any_range` 집합에서는 EXP-479가
   EXP-469보다 정답 4개를 순증가시켰다. 의미를 다시 합치거나 삭제할 근거가 없다.
2. 세 range family는 합계 13,155열이지만 매우 희소하고 validation TreeSHAP 합계는
   약 0.07%다. 고정 XGBoost가 이 차원을 효율적으로 다루지 못해, range가 없는
   다수 행까지 분할 경로가 바뀐 것이 전체 하락의 더 그럴듯한 설명이다.
3. `base_sample_aggregate` 4열만으로 domain AUC가 0.720289이며 SHAP share도
   27.41%다. 특히 mutated-gene count와 total-variant count의 Spearman 상관은
   0.996089다. 이는 암종 신호와 dataset acquisition shift가 같은 burden 축에서
   경쟁한다는 경고다.
4. 전체 AUC보다 family 제외 AUC가 오르는 경우가 많다. 이는 제거 family가 무가치하다는
   뜻이 아니라, 중복된 희소 피처 사이에서 domain classifier도 feature competition을
   겪는다는 뜻이다. leave-one-out 수치를 additive 기여도로 해석하지 않는다.

## 다음 native v3 튜닝 설계

다음 공식 Experiment Issue는 EXP-479를 부모로 하고 parser·semantic schema·피처
집계는 고정한다. outer validation·test·Public을 탐색에 사용하지 않는 nested
XGBoost tuning만 수행한다.

- `max_depth`: 3–7
- `min_child_weight`: 2–20
- `learning_rate`: 0.02–0.08
- `subsample`: 0.60–0.90
- `colsample_bytree`: 0.25–0.75
- `reg_alpha`: 0–2
- `reg_lambda`: 1–12
- `gamma`: 0–0.5
- outer fold 내부 3-fold, seed `42+outer_fold`, 최대 30 trials
- 목적값: inner OOF Macro F1; 동률이면 fold 표준편차가 낮은 후보

특히 낮은 `colsample_bytree`, 얕은 depth와 더 강한 child/leaf 규제로 39,467개
중복·희소 열의 분할 경쟁을 억제한다. range 의미나 parser taxonomy 자체는 탐색
대상이 아니다.

`standalone AUC`는 해당 family만으로 train/test를 구분한 정도다. 높을수록 shift가
크다는 뜻이지 암종 예측력이 높다는 뜻이 아니다. leave-one-out AUC와 SHAP 역시
상관된 피처 사이의 competition 때문에 additive 기여도로 해석하지 않는다.

## 해석 원칙

1. `range_replacement`, `range_stop`, `range_no_change` 의미는 점수나 shift로
   삭제하지 않는다.
2. SHAP 0은 저장된 트리가 표본에서 해당 열을 사용하지 않았다는 뜻이며 의미가
   없다는 증명이 아니다.
3. test prevalence와 adversarial AUC는 모델 규칙을 고르는 데 사용하지 않는다.
4. 다음 nested tuning 범위는 train OOF와 validation-only SHAP에서 관찰한
   희소성·feature competition을 바탕으로 사전 고정한다.

## 산출물

- `summary.json`: 입력 해시·핵심 결과
- `family_support.csv`: family별 차원·nnz·prevalence·row-sum quantile
- `sample_feature_correlations.csv`: sample aggregate Spearman 상관
- `range_cooccurrence.csv`: 세 range 의미의 sample 동시 출현
- `exp469_exp479_oof_comparison.json`,
  `exp469_exp479_oof_comparison_groups.csv`: 부모 대비 오류 전환
- `adversarial_auc.json`: 전체·family standalone·leave-one-out domain AUC
- `top_shift_distributions.csv`: gain 상위 shift 피처 train/test 분포
- `tree_shap_global_top500.csv`, `tree_shap_class_top20.csv`,
  `tree_shap_family_importance.csv`: validation-only TreeSHAP

재실행:

```bash
uv run python scripts/analyze_parser_native_v3_generalization.py
```
