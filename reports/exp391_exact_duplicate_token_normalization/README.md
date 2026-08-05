# EXP-391 exact duplicate mutation-token 정규화

## 목적

부모 EXP-374의 stop 표기 정규화, Ensembl release 116 isoform semantic mask,
pathway·hotspot 정의, XGBoost 설정, canonical 5-fold와 Macro-F1 checkpoint 선택을
고정하고, 각 non-WT 유전자 cell에서 stop 정규화 후 완전히 같은 token만 한 번
사용하도록 변경했다. token 순서는 정렬해 입력 순서에 무관하게 만들었고, 서로
다른 위치나 변이 유형은 합치지 않았다.

이 규칙은 target, test 분포나 Public LB를 사용하지 않고 사전에 고정했다. 아래
train/test 중복 수는 규칙 선택이 아니라 영향 범위를 설명하기 위한 label-free
감사 결과다.

## 중복 token 감사

실행 명령:

```bash
uv run python scripts/audit_exp391_exact_duplicate_tokens.py
```

| 구분 | Train | Test |
|---|---:|---:|
| 샘플 수 | 6,201 | 2,546 |
| 영향받은 샘플 | 144 | 35 |
| 영향받은 cell | 3,068 | 209 |
| 전체 mutation token | 255,164 | 337,512 |
| 제거 대상 exact duplicate | 6,100 | 218 |
| stop 정규화로 새로 생긴 duplicate | 0 | 0 |

따라서 exact duplicate는 실제로 존재해 사전 실행 중단 조건에는 해당하지 않았다.
동시에 stop 표기 정규화가 별개의 token을 새 중복으로 만든 사례는 없었다.

## 실행 결과

공식 실행은 `uv run python scripts/run_exp391_exact_duplicate_token_normalization.py`로
수행했다.

| 지표 | EXP-391 | EXP-374 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4251053830 | 0.4267909268 | -0.0016855438 |
| Fold 표준편차 | 0.0091632140 | 0.0085032169 | +0.0006599971 |
| Accuracy | 0.4088050314 | 0.4128366393 | -0.0040316078 |
| Log Loss | 1.8562457561 | 1.8440648317 | +0.0121809244 |

Fold Macro F1은 다음과 같다.

```text
0.4261550774 / 0.4189377298 / 0.4122109136 / 0.4286879972 / 0.4393035840
```

클래스별 F1 변화는 LAML `+0.03337`, CESC `+0.01659`, HNSC `+0.01447` 등이
개선됐지만, LUSC `-0.02488`, BRCA `-0.02408`, LUAD `-0.02355` 등이 하락했다.
단일 클래스 `-0.05` 붕괴는 없었다.

EXP-374 제출과 ID·순서를 맞춰 비교하면 예측 라벨은 229/2,546건(8.99%) 바뀌었다.
EXP-374 test 확률 파일은 로컬에 없어 부모와의 확률 차이는 계산하지 않았다.
EXP-391 제출 SHA-256은
`2a835f6532945d6613115db1877a7ebfe466e669adfc067e8c8d13ba1a048df8`이다.

## 재현성

재현 상태는 `INFERENCE_VERIFIED`다. 저장 checkpoint 재추론에서 데이터 해시와
제출 SHA-256이 일치했고, test label agreement는 100%, test 확률 최대 절대 차이는
`1.2409241e-07`로 허용치 `1e-6` 이내였다.

- Metrics: `reports/exp391_exact_duplicate_token_normalization/metrics.json`
- Resolved config: `reproducibility/exp391_exact_duplicate_token_normalization/config.resolved.yaml`
- Comparison: `reproducibility/exp391_exact_duplicate_token_normalization/comparison.json`

## 결론

exact duplicate 제거는 annotation 순서와 중복 표기에 대한 결정성을 높였지만,
부모 EXP-374 대비 공식 OOF Macro F1, Accuracy, Log Loss가 모두 악화됐다. Public
LB에는 제출하지 않고 현재 모델에는 채택하지 않는다. parser 구현과 감사 코드는
입력 정규화·QC 자산으로 보존하되, 이 결과를 근거로 다른 token을 합치거나 규칙을
추가 조정하지 않는다.

이 PR을 최신 `main`에 통합할 때 EXP-391 구현은 역사적 독립 adapter인
`exact_duplicate_mutation_parser.py`로만 보존했다. 현재 parser v4의 HGVS-informed
semantic router와 feature adapter를 덮어쓰거나 기본 parser로 승격하지 않는다.
따라서 이 결과는 EXP-374 계보에서 exact duplicate 제거 하나를 시험한 과거
ablation으로만 해석한다.
