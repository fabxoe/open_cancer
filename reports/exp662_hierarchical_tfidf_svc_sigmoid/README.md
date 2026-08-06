# EXP-662 outer-train calibrated hierarchical TF-IDF LinearSVC

EXP-545의 유일한 변경으로 outer-train 내부 3-fold sigmoid calibration을 적용했다.
Outer validation과 test는 모든 vocabulary, TF-IDF, calibration 학습에서 제외했다.

- OOF Macro F1: `0.4397109834` (Δ `+0.0000334562`)
- OOF Log Loss: `1.8895009704` (Δ `-0.8892080836`)
- Fold 표준편차: `0.0044719779` (Δ `+0.0006569779`)
- 공동 게이트: `FAIL`
- 재현 상태: `INFERENCE_VERIFIED`
- Submission SHA-256: `f4f4f2a20077ca875e5fa6e0473691e21f4ef6530144c0a2c98ffd5d19fe8473`

게이트 세부 결과:

- macro_f1_non_degradation: `True`
- log_loss_non_degradation: `True`
- fold_std_regression_limit: `True`
- per_class_regression_limit: `False`

## 판단

Macro F1 비악화와 Log Loss 개선은 통과했지만 LGG(`-0.2348`),
KIRC(`-0.0742`), CESC(`-0.0662`), BRCA(`-0.0515`)가 사전 등록한
class-collapse 한계를 넘었다. 따라서 단독 모델은 `ARCHIVE_GATE_FAILED`로
보관한다. 반면 Log Loss가 `0.8892` 개선된 확률과 재현 가능한 checkpoint는
후속 사전고정 blend 후보로 유지한다.

EXP-527 OOF 원본은 현재 저장소/worktree에 보존되어 있지 않아 새 pairwise
오류 다양성 수치는 계산하지 않았다. Calibration이 argmax를 바꿨으므로
EXP-545에서 측정한 다양성 수치를 EXP-662에 그대로 전용하지 않는다.
