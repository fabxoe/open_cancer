# ElasticNet shift-robustness 진단

> Task Issue: [#384](https://github.com/fabxoe/open_cancer/issues/384)
>
> `record_role: diagnostic` — **official EXP 아님.** `EXPERIMENT_HISTORY.md`에
> 등록하지 않으며, `reports/exp*/` 공식 실험 산출물과 구분한다.

## 결론

**"단순 선형모델(ElasticNet)이 XGBoost보다 train/test 분포 shift에 더
강건하다"는 가설을 기각한다.** 이 feature set·설정에서 XGBoost가 정확도와
shift 강건성 둘 다에서 우위다.

## 배경

#292(adversarial validation)에서 확인된 train/test 분포 shift 맥락에서,
XGBoost 같은 복잡한 트리 모델보다 ElasticNet/L1 로지스틱 같은 단순 선형
모델이 shift에 덜 취약할 수 있다는 가설을 진단했다.

## 방법

- **Feature set**: EXP-334와 동일 — `base_mutation_type` + `hotspot_34` +
  `fixed_pathway_burden` + `pathway_mutation_type_composition`, fold-safe
  (`PathwayMutationTypeFoldBuilder`로 outer-train에만 fit).
- **모델**: `sklearn.LogisticRegression(penalty="elasticnet", solver="saga",
  l1_ratio=0.5)`, `MaxAbsScaler` 적용, canonical stratified 5-fold seed 42.
- **정규화 강도**: `C ∈ {0.01, 1.0}` 2개만 검증 — 정밀 최적화가 아니라
  "정규화를 세게/중간으로 줬을 때 대략 어느 수준인지" 방향성 확인이 목적.
- **shift 강건성 지표**: `train_domain_propensity.csv`(#292 adversarial
  validation OOF)의 `oof_test_domain_probability` 상위 25%("test-like"
  서브셋)에서 Macro F1을 XGBoost(EXP-334)와 비교. 이 propensity는 읽기
  전용 진단 지표로만 사용했으며, 학습 입력·feature 선택·threshold 결정에는
  사용하지 않았다(EXP-351 finalization과 동일한 경계).

## 결과

| | OOF Macro F1 | vs EXP-334(XGB, 0.4351340093) | fold std | test-like Macro F1(n=1,666) | vs EXP-334 test-like(0.4328693332) |
|---|---:|---:|---:|---:|---:|
| C=0.01 | 0.1511874986 | **-0.2839465106** | 0.0110321787 | 0.1336205558 | **-0.2992487774** |
| C=1.0 | 0.3820918144 | -0.0530421949 | 0.0055375881 | 0.3510155362 | -0.0818537970 |

- **C=0.01**: 과도한 정규화로 26개 클래스 중 11개(BLCA/CESC/GBMLGG/HNSC/
  KIPAN/LIHC/PAAD/PRAD/SARC/STES/THYM) F1이 0.0으로 붕괴. Log Loss
  3.0580으로 사실상 학습 실패에 가깝다.
- **C=1.0**: 정상 작동하는 구간이지만 여전히 XGBoost 전 지표 열세.
- **핵심 비교**: XGBoost는 전체 OOF(0.4351340093) → test-like(0.4328693332)
  하락폭이 `-0.0022646761`로 거의 무변화인 반면, ElasticNet(C=1.0)은 전체
  (0.3820918144) → test-like(0.3510155362) 하락폭이 `-0.0310762782`로
  **XGBoost보다 절대적으로도 상대적으로도 더 크게 무너진다.** "단순 모델일수록
  shift에 안 흔들린다"는 가설과 정반대 방향의 증거다.

## 판단

- 가설 기각. 추가 선형모델 튜닝(C 세분화, l1_ratio 스윕, C=0.1/10 추가 등)을
  진행하지 않는다.
- 이 결과는 진단용이며 `EXPERIMENT_HISTORY.md`에 등록하지 않는다. 공식 모델
  후보나 앙상블 구성 요소로 채택하지 않는다.

## 재현

```bash
uv run python scripts/diagnose_elasticnet_shift_robustness.py
```

- 스크립트: `scripts/diagnose_elasticnet_shift_robustness.py`
- 산출물: `reports/analysis/elasticnet_shift_robustness_diagnostic/diagnostic_report.json`,
  `oof_elasticnet_C0.01.csv`, `oof_elasticnet_C1.0.csv`(본 디렉터리)
- 베이스라인: `reports/exp334_exp285_isoform_residue_mask/metrics.json`
- propensity: `reports/analysis/adversarial_validation/train_domain_propensity.csv`
