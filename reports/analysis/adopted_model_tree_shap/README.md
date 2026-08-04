# 채택 XGBoost 모델 validation-only TreeSHAP 감사

## 결론

EXP-219와 EXP-229는 같은 핵심 신호를 대부분 유지하면서, EXP-229가 추가한 고정
pathway 요약을 실제 예측에 사용하고 있었습니다. EXP-229의 전역 상위 피처는
EXP-219와 상위 10개 중 9개, 상위 20개 중 16개, 상위 100개 중 85개가
겹쳤습니다. 따라서 EXP-229의 개선을 기존 모델을 완전히 다른 규칙으로 바꾼 결과로
보기보다, 기존 mutation burden·잔기 위치·hotspot 신호에 pathway 요약이 추가된
결과로 해석하는 편이 타당합니다.

이 분석은 **설명용 감사**입니다. SHAP으로 피처를 삭제하거나 새 모델을 선택하지
않았고, OOF·test 확률·리더보드 점수·`EXPERIMENT_HISTORY.md`의 결과도 변경하지
않았습니다.

## 분석 대상과 방법

- Issue: [#281](https://github.com/fabxoe/open_cancer/issues/281)
- 대상: 성능 gate를 통과한 XGBoost 계열 EXP-219와 조건부 채택된 EXP-229
- checkpoint: 각 실험 GitHub Release에서 복원한 원본 fold 5개
- 데이터 범위: canonical fold의 **validation 행만** 사용
- 표본: fold·클래스별 최대 3행, 모델당 총 390행
- seed: 42
- 계산: XGBoost의 exact TreeSHAP인 `pred_contribs=True`
- 메모리 제어: 2행 단위로 계산 후 즉시 절댓값 합계로 축약
- 미사용: test, Public LB, 전체 OOF를 이용한 피처 선택

전역 중요도는 각 표본에서 26개 출력 클래스 전체의 절댓값 SHAP 평균입니다.
클래스별 표는 실제 클래스에 해당하는 출력 logit의 절댓값 SHAP만 평균했습니다.
expected-value bias 열은 제외했습니다.

## 전역 feature family 결과

| family | EXP-219 비중 | EXP-229 비중 | 해석 |
|---|---:|---:|---|
| sample aggregate | 43.92% | 41.92% | 환자별 전체 변이량·변이 종류 요약이 가장 큼 |
| residue max position | 36.33% | 31.85% | 위치 신호가 두 모델 모두에서 큰 축을 유지 |
| fixed pathway | 없음 | 9.68% | EXP-229가 추가한 64개 fold-union 피처 |
| mutation presence | 6.64% | 4.90% | 개별 유전자 변이 존재 신호 |
| fixed hotspot | 6.36% | 6.10% | 소수의 고정 hotspot이 높은 피처당 기여를 보임 |
| missense | 3.99% | 3.34% | 개별 유전자 missense 채널 |

family의 전체 비중은 피처 수 영향을 받으므로 `*_family_importance.csv`에
`mean_per_feature`도 함께 기록했습니다. 예를 들어 hotspot은 35개뿐이지만
피처당 평균 기여가 높습니다. 반대로 residue-position은 4,384개 합계가 큰
family입니다.

## 주요 관찰

두 모델의 전역 상위 신호는 다음과 같이 매우 비슷했습니다.

1. `sample__mutated_gene_count`
2. `sample__total_variant_count`
3. `sample__synonymous_count`
4. `sample__missense_count`
5. `TP53__max_residue_position`

EXP-229에서 가장 높은 새 pathway 피처는 다음과 같습니다.

| 전역 순위 | 피처 | 전체 절댓값 SHAP 비중 |
|---:|---|---:|
| 10 | `sample__pathway_cell_cycle__mutated_gene_count` | 1.97% |
| 14 | `sample__pathway_tp53__mutated_gene_count` | 1.42% |
| 18 | `sample__pathway_pi3k__mutated_gene_count` | 0.96% |
| 20 | `sample__pathway_wnt__mutated_gene_count` | 0.84% |
| 21 | `sample__pathway_rtk_ras__mutated_gene_count` | 0.77% |

EXP-229의 클래스별 상위 20개 안에 pathway 피처가 들어온 클래스는 26개 중
24개였고, 13개 클래스에서는 상위 10개 안에 포함됐습니다. 특히 COAD의 WNT
LoF, UCEC의 PI3K mutation/missense, OV·PAAD의 cell-cycle/TP53 요약처럼 알려진
생물학적 맥락과 방향이 맞는 사례가 보입니다. 그러나 이 일치는 사후 모델 설명이며
임상적 인과나 독립적 생물학 검증을 의미하지 않습니다.

## 중요한 한계

- 클래스당 표본은 전체 fold 합계 최대 15행이므로 클래스별 순위는 예비 설명입니다.
- 상관된 피처 사이에서는 SHAP 기여가 나뉘거나 한쪽으로 몰릴 수 있습니다.
- 절댓값 SHAP은 영향의 크기만 나타내며 증가·감소 방향과 정답 여부를 말하지 않습니다.
- pathway 64개는 fold별 semantic-equivalence 제거 결과의 합집합입니다. 모든
  fold에 같은 64개가 동시에 존재한 것은 아닙니다.
- `complex`와 `missing` family의 기여가 0인 것은 저장된 트리가 해당 열을 split에
  사용하지 않았다는 뜻이며, 데이터 자체에 정보가 없다는 증명은 아닙니다.
- 같은 canonical OOF를 반복 관찰해 새 규칙을 만들면 간접 과적합이 생길 수 있어,
  이 결과를 근거로 SHAP top-k 삭제·추가 또는 Optuna 탐색을 시작하지 않습니다.

## 산출물과 재실행

- [실행 완료 시각화 노트북](../../../notebooks/issue332_adopted_model_tree_shap_visualization.ipynb):
  family 총비중·피처당 평균, 모델 top-k 중복, pathway 전역·클래스별 heatmap,
  COAD/UCEC/OV/PAAD true-class 상위 피처를 그래프로 확인
- [`summary.json`](summary.json): sampling·checkpoint·feature 해시와 핵심 요약
- `*_global_top500.csv`: 모델별 전역 상위 500개
- `*_class_top20.csv`: 실제 클래스 logit 기준 클래스별 상위 20개
- `*_family_importance.csv`: family 합계·비중·피처당 평균
- 실행 코드: `scripts/analyze_adopted_model_tree_shap.py`

fresh clone에서는 원본 CSV를 사용자가 배치하고 EXP-219·229 Release bundle을
저장소 루트에 푼 뒤 실행합니다.

```bash
uv sync --frozen
uv run python scripts/analyze_adopted_model_tree_shap.py \
  --max-per-class 3 \
  --chunk-size 2 \
  --seed 42
```

기본 Feature Spec cache가 없으면 스크립트가 stateless 피처를 다시 생성합니다.
모델 checkpoint는 재학습하지 않으며 Release 원본을 사용해야 합니다.
