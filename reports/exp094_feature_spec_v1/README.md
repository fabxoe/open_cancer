# EXP-094 Feature Spec v1 조합 실험

## 결론

EXP-005의 변이유형 피처, EXP-069의 `max residue position`, EXP-085의
reference-aware 고정 hotspot을 하나의 피처 행렬로 결합했습니다. 공식 공용
5-fold OOF Macro F1은 **0.4168865739**로, EXP-069보다 `+0.0037857746`,
기존 로컬 최고인 EXP-075 blend보다 `+0.0010954964` 높았습니다.

사전 채택 조건인 OOF `+0.001` 이상과 fold 표준편차 악화 `0.002` 미만을
모두 만족했으므로 이 구성을 **Feature Spec v1으로 채택·동결**합니다.

## 사용한 피처

- EXP-005: 유전자별 mutation type 희소 피처와 기본 전역 피처
- EXP-069: 유전자별 `max_residue_position` (`zero`, complex 포함, raw)
- EXP-069 계열의 log burden 3종
- EXP-085: reference-aware 고정 hotspot 34개와 hotspot 합계

최종 입력 차원은 **35,119개**이며, Feature Spec SHA-256은
`1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`입니다.

## 결과

| 항목 | 값 |
|---|---:|
| OOF Macro F1 | 0.4168865739 |
| fold 평균 | 0.4162108011 |
| fold 표준편차 | 0.0078842521 |
| Accuracy | 0.4071923883 |
| Log Loss | 1.8399373293 |

| Fold | Macro F1 | Best iteration |
|---:|---:|---:|
| 0 | 0.4194967149 | 200 |
| 1 | 0.4180512764 | 207 |
| 2 | 0.4091128578 | 245 |
| 3 | 0.4061444684 | 221 |
| 4 | 0.4282486880 | 214 |

| 비교 기준 | Macro F1 차이 | fold 표준편차 차이 | Log Loss 차이 |
|---|---:|---:|---:|
| EXP-069 | +0.0037857746 | -0.0003216048 | -0.0125694275 |
| EXP-085 | +0.0043070194 | -0.0012423167 | +0.0083656311 |
| EXP-075 blend | +0.0010954964 | - | - |

EXP-069 대비 Macro F1, 안정성, Log Loss가 모두 개선됐습니다. EXP-085보다
Log Loss는 다소 높지만 Macro F1과 fold 안정성이 개선됐고 특정 fold의
붕괴는 없었습니다.

## 클래스별 관찰

EXP-069 대비 개선이 큰 클래스는 DLBC `+0.0440`, STES `+0.0260`, SARC
`+0.0199`, HNSC `+0.0163`이었습니다. 하락이 큰 클래스는 CESC `-0.0243`,
LUSC `-0.0189`, GBMLGG `-0.0156`이었습니다. 전체 Macro F1과 fold 안정성이
함께 개선되어 명백한 소수 클래스 붕괴로 판단하지 않았습니다.

## 재현성과 실행 기록

- Issue: [#94](https://github.com/fabxoe/open_cancer/issues/94)
- 실행 소스 commit: `19d5c067517af42f1b5e353b2106e352bae185df`
- resolved config: `reproducibility/exp094_feature_spec_v1/config.resolved.yaml`
- metrics: `reports/exp094_feature_spec_v1/metrics.json`
- submission: `submissions/exp094_feature_spec_v1.csv`
- submission SHA-256: `89e4ade9df511b49fbf58fc093744417f2980cdd20b4a86849a0c4b93b1c5411`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 라벨 일치율: 100%
- test 확률 최대 절대 오차: `2.9776000998182894e-08`
- Public LB: 미제출

첫 공식 실행은 5개 fold 학습을 끝낸 뒤 metrics JSON 최상위에 스키마가
허용하지 않는 `component_experiments`를 기록해 검증 단계에서 실패했습니다.
해당 메타데이터를 resolved config의 `experiment` 아래로 이동한 clean commit에서
전체 5-fold를 다시 실행했고, 모든 fold 점수가 첫 실행과 정확히 같았습니다.
실패 실행은 실제 실험 결과로 채택하지 않았으며 `/tmp`에 격리했습니다.

## 다음 결정

Feature Spec v1은 이 상태로 동결합니다. 다음 단계에서는 피처를 바꾸지 않고
동일 fold·동일 피처로 LightGBM, CatBoost, 선형 모델을 평가하여 XGBoost와
오류 상관이 낮은 앙상블 후보를 찾습니다.
