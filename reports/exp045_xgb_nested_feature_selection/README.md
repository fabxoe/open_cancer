# EXP-045: EXP-043 파생변수 단계별 선택

## 목적

EXP-043에서 추가한 샘플 변이분포 파생변수 28개를 모두 사용하는 대신, 각 outer
fold의 학습 데이터 안에서 피처군을 먼저 고르고 선택된 군 안에서 개별 피처를 다시
선택했다. EXP-005 모델·가중치와 공용 5-fold는 변경하지 않았다.

## 선택 방법

각 outer fold의 검증 데이터는 선택 과정에서 제외했다. 남은 학습 데이터를 inner
3-fold로 나눈 뒤 다음 순서로 평가했다.

1. 정상 피처로 inner 검증 Macro F1을 계산한다.
2. 한 피처군의 값을 검증 샘플 사이에서 섞어 관계를 끊는다.
3. `정상 Macro F1 - 섞은 후 Macro F1`이 양수인 inner fold를 센다.
4. inner 3개 중 2개 이상에서 양수인 피처군을 선택한다.
5. 선택된 피처군 안에서 같은 기준으로 개별 피처를 선택한다.
6. 선택된 피처로 outer fold를 예측한다.

따라서 `5/5 선택`은 다섯 outer fold에서 모두 위 `2/3` 조건을 통과했다는
뜻이다. 성능 향상을 보장하거나 생물학적 인과관계를 증명한다는 의미는 아니다.
이번 구현은 양수 하락 폭의 최소 임계값을 두지 않고 permutation을 한 번만
수행했으므로, 매우 작은 양수도 선택될 수 있다.

## 결과

| 항목 | 값 |
|---|---:|
| OOF Macro F1 | 0.3999980235 |
| fold 평균 | 0.3987189035 |
| fold 표준편차 | 0.0083066859 |
| Accuracy | 0.3941299790 |
| Log Loss | 1.8718678951 |
| Public LB | 미제출 |

Fold Macro F1은 `0.3988827522`, `0.3974133932`, `0.3915761757`,
`0.3915046058`, `0.4142175906`이다.

| 비교 실험 | OOF Macro F1 | EXP-045 차이 |
|---|---:|---:|
| EXP-005 | 0.4043796587 | -0.0043816352 |
| EXP-033 | 0.4057244634 | -0.0057264399 |
| EXP-043 | 0.3989124897 | +0.0010855338 |

28개 전체를 사용한 EXP-043보다는 소폭 개선됐지만 EXP-005와 EXP-033에는
미치지 못했다. fold 표준편차도 EXP-043의 `0.0040939951`보다 커졌다.

## 반복 선택 결과

피처군 기준으로 `mutation_type_affected_gene_counts`와
`per_gene_distribution`은 다섯 outer fold에서 모두 선택됐다. 두 피처군을
섞었을 때의 Macro F1 평균 하락은 각각 `0.0207496074`,
`0.0192753450`이며, 두 피처군 모두 15개 inner fold 전체에서 양수였다.

| 피처 | outer fold 선택 | inner 양수 | 평균 Macro F1 하락 | 판단 |
|---|---:|---:|---:|---|
| `sample__synonymous_gene_count` | 5/5 | 14/15 | 0.0085036093 | 비교적 강하고 안정적 |
| `sample__variants_per_mutated_gene_mean` | 5/5 | 13/15 | 0.0055912798 | 비교적 유의미 |
| `sample__single_variant_gene_count_log1p` | 5/5 | 11/15 | 0.0002870081 | 평균 효과가 매우 작아 불안정 |

핵심 해석은 단순 변이 총량보다 **변이가 몇 개 유전자에 퍼졌는지**와 **한 유전자에
얼마나 집중됐는지**가 더 일관된 후보 신호였다는 것이다. 다만
`single_variant_gene_count_log1p`는 5/5 선택됐어도 평균 하락 폭이 거의 0이므로
강한 후보 두 개와 같은 수준으로 취급하지 않는다.

전체 fold별 선택 목록과 permutation 하락 폭은
[`feature_selection.json`](feature_selection.json)에 있다.

## 결론과 후속 실험

EXP-045의 공식 결론은 nested 선택이 EXP-043보다는 소폭 개선했지만 기존
EXP-005를 넘지 못했다는 것이다. 다음 고정 피처 실험 후보는 결과를 보기 전에
다음 두 개로 사전 확정한다.

- `sample__synonymous_gene_count`
- `sample__variants_per_mutated_gene_mean`

이 두 피처는 EXP-045 결과를 보고 만든 새로운 가설이므로 EXP-045에 소급 적용하지
않고 새 Experiment Issue에서 검증한다. 같은 공용 split을 사용하더라도 새 실험은
피처 목록을 실행 전에 고정하고 EXP-005와 한 번 비교한다.

그 다음 암종 분류 도메인 지식 피처는 또 다른 Issue로 분리한다. driver gene,
pathway, hotspot 또는 변이 조합을 추가할 때는 출처·버전·라이선스를 기록하고,
암종 라벨로부터 규칙을 만들 경우 반드시 fold-train 안에서만 생성한다. 두 피처
고정 검증과 도메인 피처를 한 번에 합치지 않아야 어느 변경이 성능에 기여했는지
구분할 수 있다.

## 재현성

- 실행 소스 commit: `a854d8bd626c425363c58fa7658e236220b14c3d`
- 재현 상태: `INFERENCE_VERIFIED`
- 저장 checkpoint 재추론에서 데이터 해시, 제출 SHA-256과 test 라벨이 일치했다.
- 리더보드에는 제출하지 않았다.

```bash
uv sync --frozen
uv run python scripts/run_exp045_xgb_nested_feature_selection.py
uv run python scripts/validate_experiment.py
```
