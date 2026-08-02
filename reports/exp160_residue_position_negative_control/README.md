# EXP-160 Residue-position negative control (Issue #80 후속)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-160 / #160 |
| 목적 | Feature Spec v1에 동결된 `max_residue_position`(transform: raw)이 실제 신호인지, 3.65% reference-AA 충돌률을 가진 원시 코돈 번호의 노이즈인지 확인 |
| 핵심 입력 | EXP-069와 동일한 v1 feature matrix(유전자×변이유형 + max residue position) |
| 모델 | XGBoost, EXP-069와 동일 하이퍼파라미터·fold별 model seed |
| Local OOF Macro F1 | 원본(EXP-069) 0.4131007993 → permuted(5 seed 평균) 0.3987413040 |
| Public LB | 미제출 (진단 실험, 리더보드 제출 대상 아님) |
| 판단 | **신호 확인.** `max_residue_position`은 노이즈가 아니라 fold를 넘어 일반화되는 실제 예측 신호를 담고 있음. Feature Spec v1 유지, Issue #80 계약 종료 |

## 배경

`EXPERIMENT_HISTORY.md`의 EXP-047→067→069→094 경로와 `PR #70`의 config
(`transform: raw`)를 확인한 결과, Feature Spec v1에 동결된
`max_residue_position`은 34개 문헌 검증 hotspot 리스트(EXP-031→085)를 전혀
참조하지 않는, 파싱된 원시 잔기 위치 숫자였다.
`scripts/explore_hotspot_numbering_consistency.py`를 실행하면 패널 전체
402,443개 (gene, position) 조합 중 14,685개(3.6490%)가 같은 위치에서 서로 다른
reference amino acid를 보고해, 위치 숫자 자체의 신뢰도에 의문이 있었다.

`reports/analysis/residue_position_semantics_qc.md`(Issue #80)는 이미
"후속 negative control 계약"을 정의해뒀지만 실행 기록이 없었고, `PROJECT_CONTEXT.md`
§4에도 같은 계약이 프로젝트 규칙으로 명문화돼 있었다. EXP-160은 이 계약을
실제로 실행한 결과다.

## 방법

1. EXP-069와 동일한 feature matrix를 재사용한다 (`data/processed/feature_factory/v1/exp069_max_residue_position`,
   mutation_type + `max_residue_position`, `transform: raw`, `missing_policy: zero`,
   `complex_tokens: include`).
2. 각 outer fold의 **train 부분에서만**, 유전자별로 `max_residue_position` 값이
   0이 아닌 표본을 모아 그 유전자의 (missense, synonymous, nonsense, frameshift,
   complex) indicator 조합으로 strata를 나누고, 같은 strata 안에서만 위치 값을
   무작위로 재배치한다. Validation fold의 위치 값과 다른 모든 피처는 원본 그대로
   유지하며, test는 사용하지 않는다.
3. 이 permutation을 5개 고정 seed(1001–1005)로 반복하고, 모델
   `random_state`는 EXP-069와 동일하게 `42 + fold`로 고정해 permutation 효과만
   분리한다.
4. 각 (seed, fold) 조합마다 XGBoost를 새로 학습해 validation fold의 Macro F1을
   측정하고, EXP-069가 기록한 원본 fold별 점수와 짝지어 비교한다.

전체 구현: `scripts/run_exp160_residue_position_negative_control.py`,
설정: `configs/exp160_residue_position_negative_control.yaml`.

## 실제 결과

전체 OOF Macro F1 (5 seed 평균 vs 원본):

| | 원본(EXP-069) | Permuted(5 seed 평균) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4131007993 | 0.3987413040 | **-0.0143594953** |
| Fold 표준편차 | 0.0082058569 | 0.0057949413 (fold 평균 기준)<br>0.0023074239 (seed 간) | - |

Fold별 비교 (원본 vs permuted 5-seed 평균):

| Fold | 원본 Macro F1 | Permuted 평균 | Permuted seed-간 표준편차 | 차이 |
|---:|---:|---:|---:|---:|
| 0 | 0.4088270533 | 0.3978020411 | 0.0088188732 | -0.0110250121 |
| 1 | 0.4239996903 | 0.4043662584 | 0.0060820599 | -0.0196334319 |
| 2 | 0.3999078004 | 0.3909733865 | 0.0053026668 | -0.0089344139 |
| 3 | 0.4129369619 | 0.3912964196 | 0.0031348371 | -0.0216405424 |
| 4 | 0.4182072576 | 0.4038006382 | 0.0035105880 | -0.0144066194 |

25개 (seed, fold) 조합 중 **24개**가 원본보다 낮았다. 유일한 예외는 seed 1003의
fold 0(+0.0012132900)으로, permutation seed 잡음 안에서 설명 가능한 크기다.
5개 fold 전부에서 방향이 일관되게 하락했고, 하락폭(fold별 -0.009~-0.022)은
permutation seed 간 표준편차(0.003~0.009)보다 대체로 크다.

## 해석과 한계

- **위치 숫자를 완전히 노이즈로 볼 수 없다.** Gene×mutation-type 소속 정보(어떤
  유전자가 어떤 타입으로 변이됐는지)는 permutation 후에도 그대로 보존되는데,
  그럼에도 5개 fold, 5개 seed 거의 전부에서 일관된 하락이 나타났다. 이는
  `max_residue_position`이 gene×mutation-type 소속을 넘어서는, fold를 가로질러
  일반화되는 추가 정보를 담고 있다는 뜻이다.
- **이것이 "생물학적 hotspot 효과"를 증명하지는 않는다.** Issue #80과
  `PROJECT_CONTEXT.md`의 경고대로, 이 negative control은 "신호가 실재하는가"만
  확인한다. 위치 값이 실제로 기능부위 효과를 반영하는지, 아니면 코호트·연구
  배치나 특정 transcript 넘버링 관례와 우연히 상관된 결과인지는 이 실험만으로
  구분할 수 없다.
- **3.65% reference-AA 충돌은 여전히 존재하지만, 이 신호를 무효화할 만큼 크지
  않아 보인다.** 위치 파싱이 부분적으로 부정확하더라도 대다수(약 96.35%)
  (gene, position) 조합은 내부적으로 일관되며, 이번 결과는 그 대다수 신호가
  살아남아 fold 일반화에 기여하고 있음을 시사한다.
- **Strata는 mutation-type까지만 나눴고 token-count strata는 나누지 않았다**
  (재파싱 없이는 캐시된 sparse 행렬만으로 얻기 어려움). `PROJECT_CONTEXT.md`의
  "가능하면 mutation type·token-count strata" 조항 중 일부만 충족한 것으로,
  결과를 재현하거나 확장할 때 참고할 문서화된 단순화다.
- 이 실험은 진단 목적이며 리더보드에 제출하지 않는다. `models/`, `oof/`, `preds/`,
  `submissions/`도 생성하지 않는다(일반 Local 실험 규칙에 따라 resolved config,
  metrics, History만 필요).

## 다음 실험 후보

- Issue #80의 "후속 negative control 계약"을 이 결과로 종료 처리한다
  (`reports/analysis/residue_position_semantics_qc.md`에 결과 추가).
- #158(missense burden ablation), #156(mutation-type 압축) 등 Feature Spec v1
  위에서 진행 중인 실험은 `max_residue_position`을 신뢰 가능한 실제 신호로
  취급해도 된다.
- 위치 신호의 생물학적 해석(hotspot 근접성 vs 다른 상관 요인)을 확인하려면
  별도의 target-independent 분석이 필요하며, 이 EXP-160만으로 단정하지 않는다.

## 재현과 관련 파일

- Config: `reproducibility/exp160_residue_position_negative_control/config.resolved.yaml`
- Metrics: `reports/exp160_residue_position_negative_control/metrics.json`
- Permutation 상세(5 seed × 5 fold 전체 breakdown): `reports/exp160_residue_position_negative_control/permutation_detail.json`
- Submission: 미생성 (진단 실험)
- Source commit: `53e6233ee533ec20a3dd7acdbeda0c0a607e5eb1`
- Reproduction status: `NOT_STARTED` (일반 Local 실험, 리더보드 미제출이라
  `INFERENCE_VERIFIED` manifest는 필요하지 않음)
