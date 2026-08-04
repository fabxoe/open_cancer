# EXP-317 isoform 의미 범주 sample 요약

## 결론

Ensembl release 116의 6개 isoform 의미 범주별 token `count`와 `any` indicator
12개를 EXP-229에 추가했지만 OOF Macro F1, fold 안정성, Log Loss가 모두
악화됐다. B2-2는 `ARCHIVE`하며 비율·threshold 또는 조합을 추가 탐색하지 않는다.

## 설계

- Issue: [#317](https://github.com/fabxoe/open_cancer/issues/317)
- 부모: EXP-229
- canonical stratified 5-fold, seed 42
- EXP-229의 모델·피처·checkpoint 정책 유지
- 유일한 변경: `MANE_MATCH`, `CANONICAL_MATCH`, `OTHER_ISOFORM_MATCH`,
  `POSITION_VALID_REF_MISMATCH`, `OUTSIDE_ALL_KNOWN_ISOFORMS`,
  `COMPLEX_OR_UNMAPPABLE` 각각의 token count와 any 추가
- EXP-313 mask 미적용, target·test 분포·Public LB 미사용

## 결과

| 지표 | EXP-317 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4170163022 | 0.4229885745 | -0.0059722724 |
| Fold 표준편차 | 0.0112786198 | 0.0098679649 | +0.0014106548 |
| Accuracy | 0.4081599742 | 0.4125141106 | -0.0043541364 |
| Log Loss | 1.9048725367 | 1.8509613276 | +0.0539112091 |

Fold Macro F1은 `0.4144550 / 0.4094847 / 0.4078213 / 0.4168022 /
0.4391417`이다. DLBC가 `-0.06258`로 가장 크게 하락해 클래스 안정성 gate도
실패했다. Public LB에는 제출하지 않았다.

## 산출물

- Config: `configs/exp317_isoform_semantic_summary.yaml`
- Runner: `scripts/run_exp317_isoform_semantic_summary.py`
- Metrics: `reports/exp317_isoform_semantic_summary/metrics.json`
- Reproducibility: `reproducibility/exp317_isoform_semantic_summary/`
- Submission: `submissions/exp317_isoform_semantic_summary.csv`
- 실행 source commit: `8be79a94fb0b5f77f0c97a87ffcc4a6bcbe17196`
- 재현 상태: `INFERENCE_VERIFIED`

checkpoint 재추론에서 test label 100%, 확률 최대 차이 `1.49e-7`, submission
SHA-256 byte-level 일치를 확인했다.
