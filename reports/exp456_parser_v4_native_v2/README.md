# EXP-456 — Parser v4 native semantic adapter v2 baseline

> Issue: [#456](https://github.com/fabxoe/open_cancer/issues/456)  
> 구현: [#453](https://github.com/fabxoe/open_cancer/issues/453)  
> 상태: `COMPLETED` / 판단: `ARCHIVE` / Public: 미제출

## 무엇을 검증했나

Parser v4가 구조화한 모든 사건을 exclusive primary family와 raw provenance로
보존하되, train과 canonical fold 지원 gate를 통과한 다음 consequence만 모델에
사용했다.

- `missense`
- `no_change`
- `nonsense`
- `frameshift`
- `range_replacement`

deletion·insertion·duplication candidate·delins·range stop/no-change·start-codon·
unresolved는 parser에서 제거하거나 `complex`로 합치지 않았지만, 현재 train/fold
지원 미달이므로 모델 열에서는 제외했다. 기존 mutation-presence와 missing 열은
유지했다.

모델·fold·seed·balanced weight·Macro F1 checkpoint는 EXP-433·444·448과
동일하며 hotspot·position·pathway·isoform·driver·추가 aggregate·Optuna는 없다.

## 실행

```bash
uv run python scripts/run_exp456_parser_v4_native_v2.py
```

- 소스 commit: `3c30825a9c9e0f310b44692f543963fbe4610dd8`
- Config: `configs/exp456_parser_v4_native_v2.yaml`
- Resolved config: `reproducibility/exp456_parser_v4_native_v2/config.resolved.yaml`
- Metrics: `reports/exp456_parser_v4_native_v2/metrics.json`
- OOF: `oof/exp456_parser_v4_native_v2.csv`
- Test probability: `preds/exp456_parser_v4_native_v2_test_proba.csv`
- Submission: `submissions/exp456_parser_v4_native_v2.csv`
- Submission SHA-256: `a86ab98ff610a4f8b7c89f00b9bb9f1ab0f3404e0f6195e52a8ee558d83fa7c9`
- 실행 시간: 613.37초

## 결과

| 지표 | EXP-456 | EXP-433 대비 | EXP-444 대비 | EXP-448 대비 |
|---|---:|---:|---:|---:|
| OOF Macro F1 | 0.4111053102 | -0.0021709797 | -0.0016148804 | +0.0006514778 |
| Fold 표준편차 | 0.0080878031 | -0.0014464004 | -0.0016926194 | -0.0010483080 |
| Accuracy | 0.4042896307 | +0.0012901145 | +0.0008063216 | +0.0027414933 |
| Log Loss | 1.9309408665 | -0.0226448774 | +0.0541576147 | +0.0450983047 |

Fold Macro F1:

```text
0.4047467936, 0.4209757834, 0.4065389233, 0.4012972365, 0.4196621128
```

Legacy L 대비 가장 큰 클래스 하락은 PAAD `-0.0628456511`이었다. 따라서 fold
안정성·Accuracy·Log Loss가 일부 개선됐어도 사전 고정 허용 gate의 Macro F1과
클래스 붕괴 조건을 통과하지 못했다.

## 해석

- v2는 EXP-448 native v1 no-provenance보다 Macro F1과 fold 안정성을 개선했다.
  `non_simple_or_unresolved` 같은 coarse 모델 열을 제거한 방향은 타당하다.
- 그러나 supported native consequence만으로 legacy 5-family를 완전히 교체하면
  PAAD를 포함한 일부 클래스 신호가 손실된다.
- 이는 Parser v4 correctness의 실패가 아니라 feature adapter의 성능 실패다.
  Parser v4 의미와 raw provenance는 유지한다.
- deletion·insertion·duplication·delins를 train 지원 없이 억지로 모델 열에 넣지
  않았으므로, 이 결과가 그 family 자체의 유용성을 기각하지는 않는다.

## 결정

EXP-456은 `ARCHIVE`이며 제출하지 않는다. Parser-native Baseline v1 동결은 계속
보류한다. 후속은 EXP-444에서 확인된 compatibility + supported native family
구조를 기준으로, support가 있는 의미 family만 하나씩 독립 additive ablation한다.

재현 상태는 `NOT_STARTED`다. 저장 checkpoint에서 submission을 재생성하는 별도
검증은 아직 수행하지 않았다.
