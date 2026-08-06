# EXP-664 EXP-374 + EXP-662 fixed 0.5/0.5 blend

Public-validated legacy parser EXP-374와 독립 hierarchical TF-IDF EXP-662의 확률을
평가 전에 고정한 0.5/0.5 비율로 평균했다. 비율 탐색이나 사후 보정은 하지 않았다.

- OOF Macro F1: `0.4699788178` (EXP-662 대비 `+0.0302678344`)
- OOF Log Loss: `1.7522077016` (EXP-662 대비 `-0.1372932688`)
- Fold std: `0.0152820565` (EXP-662 대비 `+0.0108100786`)
- Test-like Macro F1: `0.4540274036` (EXP-662 대비 `+0.0475186340`)
- Parent label disagreement: `0.5279793582`
- Parent correctness Pearson: `0.4639685126`
- 최소 class F1 delta: `-0.1255790015`
- 공동 게이트: `FAIL`
- 판단: `ARCHIVE_AS_PRIMARY / KEEP_GENERALIZATION_CANDIDATE`
- Public LB: 미제출(Issue 범위 밖)
- 재현 상태: `INFERENCE_VERIFIED`

## 게이트

- macro_f1_non_degradation: `True`
- log_loss_non_degradation: `True`
- test_like_macro_f1_non_degradation: `True`
- fold_std_regression_limit: `False`
- per_class_regression_limit: `False`

## 해석

5개 fold가 모두 EXP-662보다 개선됐고 test-like subset도 `+0.0475` 개선돼,
fold std 증가는 fold 붕괴가 아니라 개선폭의 불균등에서 발생했다. 또한 두 부모의
label disagreement가 52.8%, correctness Pearson이 0.464로 실제 독립성이 높아
앙상블 이득이 크게 나타났다.

그럼에도 사전 등록한 fold-std와 class-collapse gate는 변경하지 않는다. 특히
DLBC `-0.1256`, TGCT `-0.0745`, GBMLGG `-0.0534` 하락 때문에 주력 모델로
채택하거나 Public에 제출하지 않는다. 0.5/0.5 비율을 결과를 보고 다시 탐색하거나
클래스별 offset으로 보정하는 후속도 진행하지 않는다.
