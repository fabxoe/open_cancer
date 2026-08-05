# EXP-469 — Parser v4 native v2 token-count aggregation

> Issue: [#469](https://github.com/fabxoe/open_cancer/issues/469)  
> Adapter: [#466](https://github.com/fabxoe/open_cancer/issues/466) / PR #468  
> 후처리 수정: [#471](https://github.com/fabxoe/open_cancer/issues/471) / PR #472  
> 상태: `COMPLETED` / Public: 미제출 / 재현: `INFERENCE_VERIFIED`

## 왜 이 실험을 했나

Issue #462 감사에서 EXP-456과 compatibility의 유전자별 공통 의미 피처는 같지만
샘플 요약 집계 단위가 다르다는 사실을 확인했다.

- compatibility: 환자 안의 해당 변이 **토큰 수**
- EXP-456 native v2: 해당 변이가 하나 이상 있는 **유전자 수**

따라서 EXP-456의 점수 차이를 parser 의미만의 효과라고 볼 수 없었다. EXP-469는
semantic routing, 모델 활성 family, 유전자별 presence, strict range 정의와 모델
설정을 모두 고정하고 샘플 요약 5개만 token count로 바꾼 단일변수 A/B다.

## 고정된 요소와 변경 요소

고정:

- `missense`, `no_change`, `nonsense`, `frameshift`, `range_replacement`
- 유전자별 consequence presence
- mutation presence와 missing 피처
- canonical 5-fold seed 42
- XGBoost·balanced weight·Macro-F1 checkpoint 설정
- hotspot·position·pathway·isoform·driver·Optuna 미사용

변경:

```text
sample affected-gene count → sample active-token count
```

공통 네 family의 token count가 compatibility의 missense·synonymous·nonsense·
frameshift sample count와 동일하고, native v2와 token-count adapter의 유전자별
행렬이 byte-equivalent임을 단위 테스트로 고정했다.

## 실행과 산출물

```bash
uv run python scripts/run_exp469_parser_v4_native_v2_token_count.py
```

- 소스 commit: `9ff694948792b0a32262e2920c9e253ce17391b3`
- Config: `configs/exp469_parser_v4_native_v2_token_count.yaml`
- Resolved config: `reproducibility/exp469_parser_v4_native_v2_token_count/config.resolved.yaml`
- Metrics: `reports/exp469_parser_v4_native_v2_token_count/metrics.json`
- OOF: `oof/exp469_parser_v4_native_v2_token_count.csv`
- Test probability: `preds/exp469_parser_v4_native_v2_token_count_test_proba.csv`
- Submission: `submissions/exp469_parser_v4_native_v2_token_count.csv`
- Submission SHA-256: `5e0d74db25cdadff6914a18d0ed8b50ec1af2abe0e2f083aba4cec00458e22a2`
- 실행 시간: 528.65초

## 결과

| 지표 | EXP-469 | EXP-456 대비 | Legacy EXP-433 대비 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4117817779 | +0.0006764677 | -0.0014945120 |
| Fold 표준편차 | 0.0089091503 | +0.0008213472 | -0.0006250532 |
| Accuracy | 0.4038058378 | -0.0004837929 | +0.0008063216 |
| Log Loss | 1.9220182896 | -0.0089225769 | -0.0315674543 |

Fold Macro F1:

```text
0.4093792507, 0.4213429308, 0.4030457968, 0.4003736138, 0.4215435380
```

EXP-456 대비 최대 클래스 하락은 UCEC `-0.0266540`, 최대 상승은 PAAD
`+0.0249136`이었다. Legacy 대비 최대 하락은 PAAD `-0.0379320`으로 `-0.05`
붕괴 기준 안쪽이지만, 전체 Macro F1 하락이 정확성 허용치 `0.001`을 `0.0004945`
초과했다.

## 해석과 결정

token count는 affected-gene count보다 이번 고정 설정에서 조금 유리했고 Log Loss도
개선했다. 그러나 개선 폭은 작고 fold별 방향이 섞였으며 Legacy gate를 통과하지
못했다. 따라서 현 설정을 제출하거나 Parser-native Baseline v1로 동결하지 않는다.

중요하게도 이 결과는 **native 의미 표현의 잠재력을 기각하지 않는다**. 현재 모델
파라미터는 과거 5-family 표현에서 사용하던 설정이며, 더 세분화된 native 피처의
희소도·상관·feature competition과 규제 요구에 맞춰 최적화한 적이 없다. EXP-469를
비튜닝 native v2 기준점으로 보존하고 다음 순서로 일반화를 검증한다.

1. train/test prevalence·희소도·상관·adversarial AUC 감사
2. fold validation TreeSHAP과 클래스별 기여 분석
3. native v2 전용 nested XGBoost tuning
4. multi-seed 안정성 검증
5. Local gate와 재현 검증을 통과한 사전 고정 후보만 Public 제출

## 재현 검증

저장 checkpoint에서 test 확률과 submission을 다시 생성했다.

- submission SHA-256: 완전 일치
- test label agreement: 100%
- 확률 allclose: 통과 (`atol=1e-6`, `rtol=1e-6`)
- 최대 절대 차이: `1.37e-7`

따라서 재현 상태는 `INFERENCE_VERIFIED`다.
