# EXP-660 — Minimal Track A baseline

> Issue: [#660](https://github.com/fabxoe/open_cancer/issues/660)

Issue #658의 raw-first 감사 뒤 처음 실행한 공식 모델이다. 유전자별 mutation
presence·missingness를 보존하고 parser-v4 native v3의 유전자별 consequence와
Ensembl release 116 isoform-eligible max residue position만 사용했다. base와 native
adapter의 모든 `sample__*` 집계, hotspot, pathway, class profile은 제외했다.

## 결과

| 지표 | EXP-660 | EXP-433 대비 |
|---|---:|---:|
| OOF Macro F1 | 0.3627988723 | -0.0504774177 |
| Accuracy | 0.3551040155 | -0.0478955007 |
| Log Loss | 2.1014454365 | +0.1478596926 |
| fold std | 0.0063791542 | -0.0031550493 |

Fold Macro F1은 `0.3677926908`, `0.3596909413`, `0.3698691480`,
`0.3610041063`, `0.3519163174`다. runtime은 `1821.30초`였다.

클래스 붕괴 gate도 실패했다. 큰 하락은 LUSC `-0.2150`, THYM `-0.1512`,
PAAD `-0.1098`, CESC `-0.1087`, LUAD `-0.0891`이다. fold 변동성은 줄었지만
Macro F1과 Log Loss 공동 gate, 클래스 붕괴 gate를 모두 통과하지 못했다.

## 판단

**ARCHIVE. Public 미제출.** sample aggregate를 전부 제거하는 최소화는 domain-shift
노출을 줄이는 대신 암종 분류 신호까지 크게 제거했다. 이는 parser-v4 correctness나
isoform mask를 되돌릴 근거가 아니다. 다음 Track A는 sample aggregate 전체 제거를
반복하지 않고, train-only 통제 ablation으로 mutation-presence에서 결정적으로
계산되는 unique-gene burden과 raw token multiplicity를 분리해야 한다.

재현 상태는 `INFERENCE_VERIFIED`다. 저장 checkpoint 재추론에서 test label agreement
1.0, 확률 최대 절대 오차 `1.484e-7`, submission SHA-256 완전 일치를 확인했다.

