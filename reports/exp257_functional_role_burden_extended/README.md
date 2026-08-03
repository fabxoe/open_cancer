# EXP-257 functional_role_burden_extended — oncogene/TSG count 세분화

## 결론

baseline **EXP-096**(Feature Spec v1 + fixed_pathway_burden 20개)에 functional
role(oncogene 29개, tumor_suppressor 39개)별 mutated-gene count의 4가지 파생
view(raw/frac/resid/log1p, 최대 8개)를 fold-train 게이팅을 거쳐 추가했습니다.
공식 공용 5-fold OOF Macro F1은 **0.4118051266**으로 EXP-096보다
**-0.0063101814** 하락했고, Log Loss도 `+0.0145742893` 악화됐습니다.
26개 클래스 중 23개가 하락(최대 LAML `-0.0244`)했고 개선은 DLBC/LUSC/STES/UCEC/
BRCA/TGCT 6개뿐이었습니다. **기각(ARCHIVE)합니다.**

## 배경

[#176](https://github.com/fabxoe/open_cancer/issues/176)(functional_role_burden
기본형, 3주 무착수 확인)을 EXP-229(pathway 축 mutated-gene count 세분화로 팀
최고 기록 갱신)와 같은 원리로 functional_role 축에 적용하는 시도였습니다.
raw count 단독 사용 시 그룹 크기(29/39, pathway 평균보다 작음)로 인한 포화·
전역 burden confounding 위험을 Vera Health 자문으로 미리 확인해, 기본형(4개,
mutated+lof × 2 role) 대신 8개 파생 candidate + fold-train 게이팅으로
설계를 확장했습니다.

## Feature 설계

`src/open_cancer/functional_role_extended_features.py`의
`FunctionalRoleBurdenExtendedFamily`. Knowledge:
`knowledge/abc_c_compact_groups_v1.json`의 `functional_roles`
(oncogene 29개, tumor_suppressor 39개, `functional_role_burden_family()`와
동일 출처).

각 role마다 다음 4개 candidate:

- `count_raw`: role 유전자 집합 내 mutated-gene 수
- `count_frac`: `count_raw / role 유전자 수`
- `count_resid`: `count_raw - (slope*T + intercept)`, `T`=전체 mutated-gene
  count(raw), `slope/intercept`는 **fold-train만으로** 단순 선형회귀 적합 후
  validation/test에는 transform만 적용
- `count_log1p`: `log1p(count_raw)`

## 게이팅 (fold-train 통계만 사용)

- 포화: `P(count_raw==0) < 0.05` → `raw`, `log1p` 제외(`frac`, `resid`만 유지)
- 희소: `P(count_raw>0) < 0.01` → 해당 role 전체 제외
- 독점성: nonzero 샘플 중 단일 클래스 비율 `>= 0.8` → `raw`, `frac` 제외
  (`resid`, `log1p`만 유지)

`semantic_equivalence_filter`로 fold-train에서 v1 base + 기존
`fixed_pathway_burden`(20개)과 값이 완전히 같은 열을 제거합니다.

## 게이팅 결과 (5개 fold 전부)

| fold | oncogene 상태 | TSG 상태 | 중복 제거 |
|---:|---|---|---|
| 0~4 | 게이트 미발동, 4개 전부 유지 | 게이트 미발동, 4개 전부 유지 | 0개(pathway/role 모두) |

5개 fold 전부 `p_zero`(oncogene ~0.68, TSG ~0.49)·`p_nonzero`(oncogene ~0.32,
TSG ~0.51)·dominance(oncogene ~0.11~0.16, TSG ~0.10~0.11, 전부 BRCA)가
임계값에서 충분히 여유가 있어 8개 candidate 전부가 매 fold에서 살아남았고,
v1/pathway burden과의 완전 중복도 없었습니다(`reports/exp257_functional_role_burden_extended/fold_gating.json`).
즉 이번 실험은 게이팅이 실제로 후보를 걸러내서가 아니라, **8개 전부를 그대로
투입한 상태에서 성능이 하락**한 결과입니다.

## 결과

| 항목 | EXP-257 | EXP-096 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4118051266 | 0.4181153080 | -0.0063101814 |
| Fold 표준편차 | 0.0090496148 | 0.0094921177 | -0.0004425028 |
| Accuracy | 0.4015481374 | 0.4078374456 | -0.0062893082 |
| Log Loss | 1.8515084982 | 1.8369342089 | +0.0145742893 |

Fold별 Macro F1: 0.4171422593, 0.4104494955, 0.3974636031, 0.4070142779,
0.4241384592 (fold 평균 0.4112416190).

큰 하락: LAML `-0.0244`, GBMLGG `-0.0233`, THYM `-0.0231`, LGG `-0.0226`,
LUAD `-0.0224`, SARC `-0.0220`. 개선: DLBC `+0.0582`(최대), LUSC `+0.0134`,
STES `+0.0126`, SKCM `+0.0111`, UCEC `+0.0062`, BRCA `+0.0009`, TGCT `+0.0000`.

Fold 표준편차만 보면 소폭 개선(-0.0004)이지만 Macro F1·Accuracy·Log Loss가
모두 뚜렷하게 악화돼 채택 기준을 충족하지 못합니다.

## 해석

게이팅이 전혀 발동하지 않았다는 건 이 8개 열 자체가 통계적으로 "위험한" 형태
(포화·희소·독점)는 아니었다는 뜻입니다. 그런데도 성능이 하락한 건, EXP-229의
pathway 세분화가 성공한 것과 달리 **functional role(oncogene/TSG)이라는
그룹 정의 자체가 이 판별 문제에서 pathway 축만큼 유용한 신호를 담고 있지
않을 가능성**을 시사합니다 — pathway는 암종별 특이적 신호 경로(WNT/RTK-RAS
등)를 구분하지만, oncogene/TSG는 26개 암종 전반에 걸쳐 훨씬 넓고 균질하게
퍼진 범주라 암종 판별력이 상대적으로 낮았을 수 있습니다. DLBC만 크게
개선(+0.0582)된 점은 흥미롭지만, 이번 세션에서 반복 확인한 DLBC의 구조적
config-민감성(`reports/analysis/sparse_binary_feature_dlbc_sensitivity.md`)을
고려하면 단일 실험만으로 원인을 특정하지 않습니다.

## 재현성

- Issue: [#257](https://github.com/fabxoe/open_cancer/issues/257)
- Config: `configs/exp257_functional_role_burden_extended.yaml`
- Resolved config: `reproducibility/exp257_functional_role_burden_extended/config.resolved.yaml`
- Metrics: `reports/exp257_functional_role_burden_extended/metrics.json`
- Role membership: `reports/exp257_functional_role_burden_extended/role_membership.json`
- Fold별 게이팅 상세: `reports/exp257_functional_role_burden_extended/fold_gating.json`
- 재현 상태: `INFERENCE_VERIFIED`(저장 checkpoint 재추론으로 라벨 100%, 확률 일치
  확인, `reproducibility/exp257_functional_role_burden_extended/comparison.json`)
- 제출: 미제출(기각된 실험이라 DACON 제출 없음)
