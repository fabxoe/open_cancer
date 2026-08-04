# Annotation-invariant mutation parser v2 감사

> Issue #352의 target-independent parser QC다. 암종 정답과 Public LB를 사용하지
> 않았으며, 이 결과만으로 parser v2를 공식 Feature Spec에 채택하지 않는다.

## 핵심 결과

기존 parser v1은 단일 치환·`*` stop·`fs` 이외 형식을 모두 `complex`로 묶었다.
parser v2로 의미를 다시 분류하자 test의 v1 complex 19,070개 중 14,355개
(`75.28%`)가 `R213X` 같은 **X 표기 stop-gain**으로 확인됐다.

| v1 complex의 v2 재분류 | Train | Test |
|---|---:|---:|
| stop gain (`X` → `*`) | 0 | 14,355 |
| in-frame deletion | 3 | 2,583 |
| in-frame insertion | 0 | 1,142 |
| delins | 0 | 545 |
| range replacement | 230 | 40 |
| duplication | 0 | 0 |
| frameshift 표기 변형 | 3 | 0 |
| other/unmappable | 89 | 405 |

따라서 기존 `sample__complex_count` shift의 큰 부분은 복잡한 생물학적 사건의
증가가 아니라 stop codon을 train은 주로 `*`, test는 주로 `X`로 기록한 annotation
표기 차이다. 그러나 stop-gain을 제외해도 test에는 indel·delins·기타 사건
4,715개가 남으므로 표기 정규화 하나로 모든 domain shift가 해소되지는 않는다.

## 전체 canonicalization QC

| 항목 | Train | Test |
|---|---:|---:|
| 원본 token | 255,164 | 337,512 |
| canonical token | 249,064 | 337,294 |
| 제거된 의미상 중복 token | 6,100 | 218 |
| missense | 161,051 | 201,807 |
| synonymous | 64,844 | 88,678 |
| stop gain | 13,080 | 16,299 |
| frameshift | 9,766 | 25,795 |
| other/unmappable | 89 | 405 |

중복 제거는 같은 gene-cell 안에서 정규화 후 완전히 같은 token에만 적용한다.
서로 다른 위치나 서로 다른 사건은 합치지 않는다.

## 해석과 제한

1. `X` alternate와 `*` alternate는 단순 치환 형식에서만 stop-gain으로 통합한다.
   `X127C`처럼 reference가 `X`인 token은 reference amino acid를 알 수 없어
   `other_unmappable`로 남긴다.
2. insertion·deletion·delins를 단순히 damaging 또는 driver라고 해석하지 않는다.
3. test에서 많이 보였다는 이유로 family를 삭제하거나 threshold를 만들지 않는다.
4. EXP-109는 morphology aggregate를 기존 피처에 추가해 실패했다. 후속 실험은
   새 피처를 무작정 추가하지 않고 raw complex 표현을 robust 표현으로 **교체**한다.
5. 모델 채택은 별도 Experiment Issue의 canonical 5-fold 결과로만 판단한다.

## 재현

```bash
uv run python scripts/audit_robust_mutation_parser.py
```

- 원본 수치: [`audit.json`](audit.json)
- parser 계약: [`docs/annotation_invariant_mutation_parser.md`](../../../docs/annotation_invariant_mutation_parser.md)
- parser 구현: [`src/open_cancer/robust_mutation_parser.py`](../../../src/open_cancer/robust_mutation_parser.py)
