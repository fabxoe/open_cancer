# EXP-512: Parser v4 환자별 semantic count

## 결론

EXP-512는 EXP-374의 모델·canonical 5-fold·seed·checkpoint 선택 정책과 기존
피처를 모두 유지하고, parser v4가 판정한 단백질 변이 의미를 환자별 18개 전역
count로 집계해 추가했다.

- OOF Macro F1: `0.4258183004`
- Public Macro F1: `0.3329881004`
- 재현 상태: `INFERENCE_VERIFIED`
- 판단: `ARCHIVE`

EXP-374와 비교하면 OOF는 `-0.0009726264`, fold 표준편차는
`+0.0014872291`, Log Loss는 `+0.0218627453`, Public은
`-0.0132278216`이다. 따라서 이 **환자 전역 semantic count adapter**는 채택하지
않는다. 이 결과는 parser v4의 정규화·의미 판정 자체나 gene×semantic family처럼
더 세밀한 표현을 기각하는 근거가 아니다.

## 실험 설계

- 부모: EXP-374
- Issue: #512
- Config: `configs/exp512_parser_v4_semantic_counts.yaml`
- Runner: `scripts/run_exp512_parser_v4_semantic_counts.py`
- Metrics: `reports/exp512_parser_v4_semantic_counts/metrics.json`
- Split: canonical Stratified 5-fold, seed 42
- 모델: EXP-374 XGBoost 설정 유지
- checkpoint: validation Macro F1 기준

추가한 18개 피처는 다음 환자별 token count다.

1. 전체 token
2. missense
3. no-change
4. nonsense
5. start-codon affected
6. unknown-reference substitution
7. nonstandard stop-reference
8. frameshift
9. deletion
10. delins
11. insertion
12. duplication candidate
13. ordinary range replacement
14. range stop
15. range no-change
16. unresolved
17. complete parse
18. partial parse

타깃, test 분포, Public 점수는 count schema 정의에 사용하지 않았다.

## 결과

| 항목 | EXP-374 | EXP-512 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4258183004 | -0.0009726264 |
| Fold 표준편차 | 0.0085032169 | 0.0099904460 | +0.0014872291 |
| Log Loss | 1.8440648317 | 1.8659275770 | +0.0218627453 |
| Public Macro F1 | 0.3462159220 | 0.3329881004 | -0.0132278216 |

Fold별 Macro F1은 `0.4252238369`, `0.4225060175`, `0.4120400910`,
`0.4252197776`, `0.4430732916`이다.

## 해석

환자마다 특정 의미의 변이가 몇 개인지를 전역 count로만 추가하면 유전자 정체성과
정확한 사건 구조가 사라진다. 이 데이터에서는 그 압축이 EXP-374의 신호를 보완하지
못했고, train OOF보다 Public 하락이 더 컸다.

후속 실험은 같은 18개 count를 반복 튜닝하지 않는다. parser v4를 사용할 때는
gene×semantic family, reference/alternate amino acid, 위치·범위 구조처럼 의미가
발생한 유전자와 사건을 보존하는 표현을 별도 Issue에서 검증한다.

## 제출·재현

- 제출 파일: `submissions/exp512_parser_v4_semantic_counts.csv`
- 제출 ID: `1512887`
- 제출 시각: `2026-08-05T23:58:45+09:00`
- Public: `0.3329881004`
- SHA-256: `2f1ffc1c6c91535e613e46ea084efcec4a53e9f3a3c5717d7144b2cd2b2f2c21`
- 증빙: `reproducibility/exp512_parser_v4_semantic_counts/`

저장 checkpoint 재추론으로 submission byte-level SHA-256, test label 100%, 확률
`atol=1e-6`, `rtol=1e-6` 일치를 확인했다. 독립 재학습 검증은 수행하지 않았다.
