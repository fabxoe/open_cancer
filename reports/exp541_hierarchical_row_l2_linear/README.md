# EXP-541 hierarchical row-L2 LinearSVC

Parser-v4 canonical event의 hierarchical detail/global row-L2 비교입니다.

- OOF Macro F1: `0.3723738759`
- Fold 표준편차: `0.0095691856`
- Accuracy: `0.3868730850`
- decision-score softmax Log Loss: `2.8486547470`
- Submission SHA-256: `c4926d11888db75be5b7511c0c7f8064daa3c4a51df5bbc68674565c5054f7e6`

EXP-539 raw-count 기준선과 비교하여 row-L2 normalization의 단독 효과를 평가합니다.

## EXP-539 대비

| 지표 | EXP-539 raw | EXP-541 row-L2 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.3662402061 | 0.3723738759 | +0.0061336698 |
| Fold 표준편차 | 0.0088579993 | 0.0095691856 | +0.0007111863 |
| Accuracy | 0.3667150460 | 0.3868730850 | +0.0201580390 |
| Log Loss | 2.5453414917 | 2.8486547470 | +0.3033132553 |

row-L2는 Macro F1과 수렴 안정성을 개선했지만 decision score를 softmax한
확률의 Log Loss는 크게 악화했습니다. 따라서 단독 제출 후보로 채택하지 않고,
후속 오류 구조 및 확률 보정 진단용 비교 자산으로 보존합니다.
