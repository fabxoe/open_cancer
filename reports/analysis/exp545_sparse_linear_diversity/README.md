# EXP-545 sparse-linear 다양성·calibration 사전 감사

Canonical OOF만 사용했으며 Public LB와 test label은 사용하지 않았습니다.

## 전체 지표

| 모델 | Macro F1 | Accuracy | OOF probability Log Loss | 평균 confidence |
|---|---:|---:|---:|---:|
| EXP-374 | 0.4267909268 | 0.4128366393 | 1.8440648896 | 0.459967 |
| EXP-527 | 0.4468722707 | 0.4339622642 | 2.0274886792 | 0.318997 |
| EXP-545 | 0.4396775272 | 0.4279954846 | 2.7787079022 | 0.089393 |

## 오류 다양성

| 비교 | 예측 불일치 | 정오답 상관 | 왼쪽만 정답 | 오른쪽만 정답 | 둘 다 오답 |
|---|---:|---:|---:|---:|---:|
| EXP-374 vs EXP-545 | 49.4759% | 0.538416 | 10.4983% | 12.0142% | 46.7021% |
| EXP-527 vs EXP-545 | 50.7983% | 0.487465 | 12.8689% | 12.2722% | 44.3316% |

## EXP-527 대비 클래스별 보완

개선 상위: DLBC +0.2941, TGCT +0.2102, LAML +0.0867, BRCA +0.0834, ACC +0.0619, LIHC +0.0499, LUAD +0.0481, PCPG +0.0410

악화 상위: LGG -0.2486, KIRC -0.2035, CESC -0.1829, SKCM -0.0894, PAAD -0.0822, SARC -0.0812, COAD -0.0708, OV -0.0599

## 결정

- EXP-545는 단독 최고점보다 오류 다양성을 제공하는 후보인지 판정합니다.
- LinearSVC decision score softmax는 보정 확률이 아니므로 평균·stacking 입력으로 확정하지 않습니다.
- 다음 공식 실험은 같은 TF-IDF 입력의 multinomial Logistic Regression을 우선합니다.
- 별도 calibration은 Logistic Regression 결과보다 명확한 필요가 있을 때만 nested 방식으로 진행합니다.
