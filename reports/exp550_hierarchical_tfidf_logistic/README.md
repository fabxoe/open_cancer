# EXP-550 hierarchical TF-IDF multinomial Logistic Regression

EXP-545와 같은 parser-v4 hierarchical TF-IDF 입력에서 확률을 직접 학습합니다.

- OOF Macro F1: `0.4324730859`
- Fold 표준편차: `0.0145722806`
- Accuracy: `0.4191259474`
- predict_proba Log Loss: `2.3007948399`
- Submission SHA-256: `7c7ca53c77d83d17475bacc6955e9fc6339863f3363da3f782c540f9e952b210`

LinearSVC decision-score softmax가 아니라 Logistic Regression의 predict_proba입니다.

## 비교와 판단

- EXP-545 대비 Macro F1: `-0.0072044413`
- EXP-527 대비 Macro F1: `-0.0143991848`
- EXP-527 대비 Log Loss: `+0.2733061607`(악화)
- 모든 fold가 31~34 iteration에서 수렴

적법한 확률을 산출했지만 EXP-545의 hard-label 성능과 EXP-527의 Log Loss를
동시에 유지하지 못해 단독 모델은 `ARCHIVE`합니다. 동일 TF-IDF 표현은 유지하고,
다음 후보는 EXP-545 LinearSVC의 결정 경계를 outer-train 내부에서만 sigmoid
calibration하는 방식으로 제한합니다.
