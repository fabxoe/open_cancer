# EXP-355 normalized non-simple unique-gene count 교체

## 결론

EXP-229의 raw `sample__complex_count` 한 열을 annotation-invariant parser v2로
정규화한 non-simple event의 unique-gene count 한 열로 교체했다. OOF Macro F1은
`0.4176342820`으로 부모보다 `-0.0053542926` 하락했고 Log Loss와 DLBC F1도
악화돼 R1을 기각한다.

이 결과는 **raw complex token multiplicity 한 열을 unique-gene count로 바꾸는
표현이 유효하지 않았다**는 뜻이다. test complex의 75%가 X stop 표기였다는 parser
QC나 X/`*` 의미 통합 자체를 반증하지 않는다. 한 열을 제거하면서 train에서
유용했던 사건 수·표기 정보를 함께 잃었을 가능성도 있으므로, 사전 등록한 R2
gene-level normalized event-family 교체는 별도 실험으로 한 번 평가한다.

## 실험 설계

- Issue: [#355](https://github.com/fabxoe/open_cancer/issues/355)
- 부모: EXP-229
- 유지: canonical 5-fold, seed 42, XGBoost, balanced sample weight,
  Macro-F1 checkpoint, pathway·hotspot·position·나머지 base 피처
- 제거: `sample__complex_count`
- 추가: `sample__robust_non_simple_event_gene_count`
- non-simple family: in-frame deletion/insertion, delins, range replacement,
  duplication, other/unmappable
- `R213X` 같은 X alternate는 stop-gain으로 정규화해 non-simple에서 제외
- 같은 gene-cell의 exact semantic duplicate와 raw token multiplicity는 count를
  늘리지 않음
- SUBCLASS·test prevalence·Public LB는 parser family나 threshold에 미사용

## 결과

| 지표 | EXP-355 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4176342820 | 0.4229885745 | -0.0053542926 |
| Fold 평균 | 0.4184409009 | 0.4232332489 | -0.0047923481 |
| Fold 표준편차 | 0.0112853475 | 0.0098679649 | +0.0014173826 |
| Accuracy | 0.4094500887 | 0.4125141106 | -0.0030640219 |
| Log Loss | 1.8773572445 | 1.8509613276 | +0.0263959169 |

Fold Macro F1은 `0.4077713 / 0.4170402 / 0.4133458 / 0.4138382 /
0.4402090`이다. fold 3은 validation Macro F1 최고가 51 iteration에서 선택돼
Log Loss가 `2.01030`까지 악화됐다.

클래스별 큰 하락은 DLBC `-0.06258`, LUAD `-0.03704`, SARC `-0.01998`,
UCEC `-0.01918`이다. 개선은 LGG `+0.01692`, COAD `+0.01568`, PAAD
`+0.00937` 등에 제한됐다. DLBC 하락이 사전 `-0.05` 붕괴 gate를 넘었다.

## 재현성과 산출물

- Config: `configs/exp355_robust_complex_gene_count.yaml`
- Runner: `scripts/run_exp355_robust_complex_gene_count.py`
- Metrics: `reports/exp355_robust_complex_gene_count/metrics.json`
- OOF: `oof/exp355_robust_complex_gene_count.csv`
- test 확률: `preds/exp355_robust_complex_gene_count_test_proba.csv`
- submission: `submissions/exp355_robust_complex_gene_count.csv`
- reproducibility: `reproducibility/exp355_robust_complex_gene_count/`
- source commit: `b03b9163955a9978736f19925a05d356a3f7a82e`
- 실행시간: 822.20초
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint 재추론에서 test label 100%, 확률 최대 절대차
`1.4761963e-7`, 제출 SHA-256 byte-level 일치를 확인했다.

## 다음 단계

1. EXP-355는 `ARCHIVE`하고 Public에 제출하지 않는다.
2. 결과를 보고 R1 family·threshold를 재조정하지 않는다.
3. 로드맵에 사전 정의된 R2에서 generic gene-level complex indicator만 normalized
   event-family indicator로 교체한다. R1 sample aggregate 교체와 섞지 않는다.
4. R2도 실패하면 parser v2를 QC·표준화 라이브러리로만 보존하고 공식 robust
   representation 탐색을 종료한다.
