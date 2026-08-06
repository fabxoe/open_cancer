# Parser v4 hierarchical event-token fallback 감사

Issue #537에서 Issue #533 tokenizer와 Issue #535 support 감사 결과를 이용해
gene-specific detail과 gene-agnostic global fallback을 결합한 sparse adapter를
검증했습니다. 모델·label·OOF·Public LB는 사용하지 않았습니다.

## 고정 설정

- detail 최소 outer-train 환자 support: 2
- global 최소 outer-train 환자 support: 1
- feature order: detail 사전순 → global 사전순
- canonical fold마다 vocabulary를 다시 fit
- validation/test는 transform-only

## 전체 train fit 결과

| 항목 | 값 |
|---|---:|
| detail 차원 | 100,451 |
| global 차원 | 459 |
| 전체 차원 | 100,910 |
| test detail occurrence OOV | 26.52% |
| OOV detail의 global 복구율 | 75.06% |
| 최종 global occurrence OOV | 5.51% |
| global로도 복구되지 않은 test occurrence | 95,751 |
| global 미복구가 하나라도 있는 test 환자 | 1,022 / 2,546 |

test-only deletion·insertion·delins annotation과 blank provenance처럼 train에서
배울 수 없는 의미는 global에서도 일부 OOV로 남습니다. 이를 임의의 다른
family로 합치거나 0이 아닌 coefficient를 부여하지 않습니다.

## canonical fold 결과

| fold | detail 차원 | global 차원 | detail OOV | global 복구율 | 최종 global OOV |
|---:|---:|---:|---:|---:|---:|
| 0 | 87,090 | 451 | 18.32% | 99.98% | 0.003% |
| 1 | 86,205 | 449 | 18.01% | 99.97% | 0.004% |
| 2 | 86,139 | 449 | 18.83% | 99.98% | 0.004% |
| 3 | 89,427 | 455 | 17.66% | 99.97% | 0.004% |
| 4 | 87,382 | 450 | 18.36% | 99.97% | 0.004% |

canonical validation에서는 detail OOV가 사실상 모두 train에서 관찰된 global
의미로 후퇴합니다. 따라서 공식 row normalization 비교에 사용할 기반 입력
계층으로는 충분합니다.

## 해석 제한

- global fallback은 새 생물학적 사실을 추가하지 않습니다.
- test-only 의미를 학습 가능한 의미로 위장하지 않습니다.
- 높은 복구율은 점수 개선을 보장하지 않습니다.
- test의 global OOV 5.51%와 사건 수 shift는 여전히 남아 있습니다.
- raw count와 row-L2 중 어느 쪽이 좋은지는 canonical 5-fold Macro F1으로만
  결정합니다.

## 다음 단계

별도 Experiment Issue에서 동일 vocabulary와 동일 선형 분류기를 사용해 다음
두 arm만 비교합니다.

1. hierarchical raw count
2. hierarchical row-L2

row-L2가 채택된 뒤에만 TF-IDF+row-L2를 별도 실험으로 진행합니다.

재실행:

```bash
uv run python scripts/audit_hierarchical_event_adapter.py
```

원본 데이터와 환자별 전체 token 행렬은 Git에 저장하지 않습니다.
