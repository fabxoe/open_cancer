# EXP-359 normalized non-simple event-family gene indicator 교체

## 결론

EXP-229의 4,384개 generic `GENE__complex` indicator를 parser v2의 명시적
non-simple event family 6종, 총 26,304개 희소 후보 열로 교체했다. OOF Macro
F1은 `0.4187813830`으로 부모보다 `-0.0042071915` 낮고 Log Loss도 악화돼 R2를
기각한다. Public에는 제출하지 않는다.

R1과 달리 raw `sample__complex_count`는 그대로 유지했다. 따라서 이번 결과는
**generic gene-level complex를 더 세밀한 사건 family로 나누는 표현이 현재
XGBoost와 표본 규모에서 유효하지 않았다**는 뜻이다. parser의 X/`*` stop-gain
통합과 annotation QC 자체가 틀렸다는 결과는 아니다.

## 실험 설계

- Issue: [#359](https://github.com/fabxoe/open_cancer/issues/359)
- 부모: EXP-229
- 유지: canonical 5-fold, seed 42, XGBoost, balanced sample weight,
  Macro-F1 checkpoint, sample aggregate, pathway·hotspot·position 피처
- 제거: 모든 `GENE__complex` 4,384개
- 추가: 유전자별 `inframe_deletion`, `inframe_insertion`, `delins`,
  `range_replacement`, `duplication`, `other_unmappable` any indicator
- 후보 차원: 4,384×6 = 26,304; 실제 관측값만 sparse CSR에 저장
- `R213X` 같은 X alternate는 stop-gain으로 정규화해 신규 non-simple indicator에서 제외
- SUBCLASS·test prevalence·Public LB는 event family나 범위 결정에 미사용

## 결과

| 지표 | EXP-359 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4187813830 | 0.4229885745 | -0.0042071915 |
| Fold 평균 | 0.4192249544 | 0.4232332489 | -0.0040082945 |
| Fold 표준편차 | 0.0092541018 | 0.0098679649 | -0.0006138632 |
| Accuracy | 0.4092888244 | 0.4125141106 | -0.0032252862 |
| Log Loss | 1.8613057137 | 1.8509613276 | +0.0103443861 |

Fold Macro F1은 `0.4176544 / 0.4157306 / 0.4061352 / 0.4220823 /
0.4345223`이다. fold 분산은 소폭 줄었지만 평균 성능과 확률 품질은 함께
악화됐다.

클래스별 큰 하락은 DLBC `-0.03005`, STES `-0.02581`, PAAD `-0.02532`이며,
개선은 ACC `+0.00840`, SARC `+0.00824`, PCPG `+0.00814` 등에 제한됐다.
어떤 클래스도 `-0.05` 붕괴 gate를 넘지는 않았지만 전체 채택 기준을 실패했다.

## 해석

train에는 실제 non-simple 사건 자체가 드물어 26,304개 후보 중 대부분이 매우
희소하다. generic complex 한 열은 표기 차이까지 포함한 넓은 신호를 공유하지만,
이를 사건별로 분해하면 표본 지원이 더 작아지고 tree split 경쟁이 증가할 수 있다.
이는 사후 가설이며, 결과를 보고 family나 threshold를 재조정하지 않는다.

R1 aggregate 교체와 R2 gene-level 교체가 모두 실패했으므로 사전 중단 조건에
따라 R3(채택 표현+EXP-313 mask)는 실행하지 않는다. parser v2는 다음 용도로
남긴다.

- train/test annotation notation shift 감사
- `X`/`*` stop-gain 의미 통합
- exact semantic duplicate 탐지
- indel·delins·range·duplication의 명시적 QC 분류

## 재현성과 산출물

- Config: `configs/exp359_robust_event_gene_indicators.yaml`
- Runner: `scripts/run_exp359_robust_event_gene_indicators.py`
- Metrics: `reports/exp359_robust_event_gene_indicators/metrics.json`
- OOF: `oof/exp359_robust_event_gene_indicators.csv`
- test 확률: `preds/exp359_robust_event_gene_indicators_test_proba.csv`
- submission: `submissions/exp359_robust_event_gene_indicators.csv`
- reproducibility: `reproducibility/exp359_robust_event_gene_indicators/`
- source commit: `4fbd1e267664949b515867c452ffa770405d4884`
- 실행시간: 974.31초
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint 재추론에서 test label 100%, 확률 최대 절대차
`1.4574203e-7`, 제출 SHA-256 byte-level 일치를 확인했다.
