# Parser v4 canonical event-token support·OOV 감사

Issue #535에서 모델이나 정답 label을 사용하지 않고 Issue #533 tokenizer를
train 6,201명, test 2,546명과 canonical 5-fold에 적용했습니다.

## 결론

canonical tokenizer는 원문 보존과 의미 분해 계약을 지켰지만, 모든
gene×detail token을 그대로 학습 vocabulary로 쓰는 것은 안전하지 않습니다.

- train vocabulary: 201,247개
- 전체 train vocabulary 기준 test occurrence OOV: 21.13%
- test 환자 중 하나 이상의 OOV가 있는 비율: 87.31%
- canonical fold에서 min support 1의 validation occurrence OOV: 11.01~11.86%
- min support를 2로 높이면 validation OOV가 17.66~18.83%, test OOV가
  26.52%로 증가
- exact peptide는 feature 이름으로 유출되지 않았고 최대 token 길이는 65자

따라서 min support만 높여 희귀 token을 제거하는 방식은 정보 손실을 크게
늘립니다. 다음 모델 실험 전에 **gene-specific detail과 저차원 hierarchical
fallback을 함께 제공하는 adapter**가 필요합니다.

## 데이터 규모와 shift

| 항목 | train | test |
|---|---:|---:|
| source event | 255,164 | 337,512 |
| token occurrence | 1,032,917 | 1,447,794 |
| unique token | 201,247 | 189,729 |
| partial event | 9,835 | 25,878 |
| unresolved event | 177 | 458 |
| blank gene cell | 0 | 237 |

환자별 source event 중앙값은 train 14, test 34이고 p95는 train 129,
test 640.75입니다. token occurrence 중앙값도 train 57, test 138.5로
차이가 큽니다. row normalization을 별도 공식 실험으로 검증해야 하는 직접적
근거입니다.

특히 train에는 거의 없거나 없는 deletion·insertion·delins detail이 test에는
상당수 존재합니다. 이는 parser 오류가 아니라 제공 데이터의 annotation
coverage shift입니다. test에만 있는 세부 의미를 supervised coefficient로
학습할 수는 없으므로 coarse fallback이 반드시 필요합니다.

## support threshold 결과

| 최소 train 환자 support | vocabulary | train occurrence OOV | test occurrence OOV |
|---:|---:|---:|---:|
| 1 | 201,247 | 0.00% | 21.13% |
| 2 | 100,451 | 9.97% | 26.52% |
| 5 | 46,521 | 23.78% | 35.81% |
| 10 | 24,101 | 39.04% | 50.31% |
| 20 | 8,542 | 59.88% | 66.92% |
| 50 | 1,955 | 80.12% | 84.67% |

## 다음 adapter의 사전 고정안

1. gene×family 같은 coarse token은 fold-train support 1부터 유지합니다.
2. gene×AA transition·position bin 같은 detail token은 fold-train에서만
   vocabulary를 만들고 support threshold를 resolved config에 고정합니다.
3. 모든 사건에 gene을 제거한 global family/transition/length fallback을 함께
   만들어 validation/test OOV가 의미 소실로 이어지지 않게 합니다.
4. unseen detail은 임의의 새 생물학 의미로 바꾸지 않고 `OOV detail → known
   coarse family`로만 후퇴합니다.
5. blank provenance는 WT와 합치지 않되, train support 0이므로 모델 입력
   활성화 여부는 별도 ablation으로 검증합니다.
6. 환자별 사건 수 shift 때문에 raw count와 row-L2를 같은 canonical 5-fold로
   비교합니다. TF-IDF는 outer-train에서만 fit하는 별도 arm입니다.

첫 공식 실험 전에 위 hierarchical adapter를 일반 Task로 구현합니다. 그 후
row-L2 sparse linear와 TF-IDF+row-L2를 각각 별도 Experiment Issue로 비교합니다.

## 산출물

- `audit.json`: 입력·split SHA-256, 전체/threshold/fold OOV, 길이와 key 통계
- `token_support_top5000.csv`: train/test document frequency 상위 5,000 token
- 재실행: `uv run python scripts/audit_canonical_event_tokens.py`

환자별 전체 token dump와 원본 CSV는 Git에 저장하지 않습니다.
