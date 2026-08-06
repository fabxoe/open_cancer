# EXP-496 EXP-374 + robust non-simple event gene count (complex_count 재평가)

## 결론

**REJECTED.** `sample__complex_count`(raw token count, #292 shift-AUC
진단 1위 feature)를 EXP-355의 `sample__robust_non_simple_event_gene_count`
(gene-level count, 이미 구현된 코드 재사용)로 교체해 EXP-374 기준으로
재평가했다. 전체 OOF는 소폭 개선(+0.0006052921, 게이트 `+0.001` 미달)됐지만,
**핵심 판정 기준인 test-like 서브셋에서는 오히려 -0.0035398863로 악화**됐다.
Log Loss도 +0.0475932367로 뚜렷이 나빠졌다. EXP-355(부모 EXP-229, Local
전용 판정)의 REJECT를 test-like 기준으로도 재확인한 셈이다.

## 실험 설계

- Issue: [#496](https://github.com/fabxoe/open_cancer/issues/496)
- 부모: EXP-374(현재 확정 legacy parent)
- 단일 변경: `sample__complex_count` 제거, `sample__robust_non_simple_event_gene_count`
  1개 컬럼 추가 — `RobustNonSimpleGeneCountFamily`(EXP-355에서 이미 구현·
  테스트된 코드를 그대로 재사용, 새 feature 엔지니어링 없음)
- 나머지 전부 EXP-374와 동일: stop-notation-invariant v2.1.0 파서, Ensembl
  isoform residue mask, fold-safe pathway burden/composition family,
  hotspot-34, `macro_f1_validation` checkpoint 선택, canonical 5-fold
  seed 42, XGBoost 하이퍼파라미터
- EXP-355와 차이점: (1) parent를 EXP-229가 아닌 EXP-374로 맞춤, (2)
  `train_domain_propensity.csv`(#292) 기준 test-like 서브셋 검증을 완료
  조건에 필수 포함(EXP-355는 Local OOF만으로 판정했었음)

## 결과

| 지표 | EXP-496 | EXP-374 | 변화 | 게이트 |
|---|---:|---:|---:|---|
| OOF Macro F1(전체) | 0.4273962190 | 0.4267909268 | +0.0006052921 | 미달(`+0.001` 필요, 방향은 긍정적) |
| Fold 표준편차 | 0.0087833910 | 0.0085032169 | +0.0002801741 | 통과(`<0.002`) |
| Log Loss | 1.8916580677 | 1.8440648317 | +0.0475932367 | 악화 |
| Accuracy | 0.4159006612 | (참고, 표에 미기재) | — | — |
| **test-like 서브셋(n=1,666) Macro F1** | **0.4248387105** | **0.4283785968** | **-0.0035398863** | **미달 — 핵심 실패 신호** |
| worst-class delta | BLCA `-0.0327144120` | — | — | 통과(`-0.05` 이내) |

주요 하락 클래스: BLCA(-0.0327), UCEC(-0.0252), LUAD(-0.0246), GBMLGG
(-0.0236), THYM(-0.0179). 개선 클래스: LGG(+0.0347), KIRC(+0.0336),
LIHC(+0.0229), PAAD(+0.0177) — KIRC는 #382에서 구조적으로 어려운 클래스로
규명된 것 중 하나라 흥미롭지만, test-like 전체 판정을 뒤집을 정도는 아니다.

## 판단

- EXP-355는 부모 EXP-229 기준으로 Local Macro F1 -0.0053542926로 크게
  하락했지만, EXP-374를 부모로 맞추자 전체 OOF는 오히려 소폭 개선됐다 —
  parser·isoform mask·hotspot이 누적된 현재 feature set에서는 이 교체의
  Local 손실이 훨씬 작아졌다는 뜻이다.
- 하지만 **test-like 서브셋에서는 방향이 반대로 뒤집혔다** — 전체에서는
  이겼는데 test 분포에 가까운 샘플에서는 졌다. 이는 `sample__complex_count`의
  raw-token-count 표현이 shift에 취약하다는 원래 가설과, 그걸 gene-level
  count로 "안정화"하면 나아질 거라는 기대가 **부분적으로만 맞았다**는
  뜻으로 해석한다: shift-AUC 상 가장 강한 단일 discriminator를 제거하긴
  했지만, 대체 표현(gene count) 자체도 여전히 "indel형 이벤트가 있었는가"
  라는 동일한 근본 신호(즉, train에는 거의 없고 test에는 흔한 이벤트의
  존재 여부)에 의존하기 때문에, granularity를 바꾼 것만으로는 근본적인
  분포 차이 자체를 없애지 못한 것으로 보인다.
- 즉 이 shift는 "표현 방식(raw count vs gene count)"의 문제가 아니라
  "이 정보를 모델에 넣을지 말지" 자체의 문제에 가깝다는 재확인이다.
  완전히 drop하는 방향(신호 자체를 포기)은 이번 실험에서 다루지 않았고,
  EXP-355 R1이 이미 근접한 시도였다는 점(gene count 1개 컬럼은 raw count
  대비 정보량이 크게 줄어든 근사)을 고려하면 추가 조정으로 살릴 여지는
  낮아 보인다.
- 재시도(예: threshold 조정, event family별 세분화 재도입)는 진행하지
  않는다 — EXP-359가 이미 event-family 세분화를 시도해 REJECTED됐고, 이번
  test-like 결과까지 더하면 `sample__complex_count` 계열 feature 재설계는
  이 세 번의 독립 시도(EXP-355/359/496)로 충분히 탐색됐다고 판단한다.

## 재현성

- Config: `configs/exp496_robust_complex_count_exp374.yaml`
- Runner: `scripts/run_exp496_robust_complex_count_exp374.py`
- Test-like 체크: `scripts/check_exp496_test_like_subset.py`
- 재현 상태: `INFERENCE_VERIFIED`
- Public LB: 미제출(게이트 미달)
