# EXP-156: 유전자별 변이 효과 압축 XGBoost

## 실험 요약

- Parent: EXP-094 / Feature Spec v1
- 변경: 유전자별 변이 유형 indicator를 4개 compact descriptor로 교체
- Split: canonical stratified 5-fold seed 42
- Test 사용: 학습 완료 후 추론에만 사용
- 데이콘 Public 점수: 미제출

## 결과

- OOF Macro F1: 0.4148494335
- Fold mean: 0.4145860750
- Fold std: 0.0125687084
- Accuracy: 0.4063860668
- Log Loss: 1.8308399556
- 최종 특징 수: 30735

| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.416716 | 0.406124 | 1.868203 | 214 |
| 1 | 0.424557 | 0.400806 | 1.850635 | 205 |
| 2 | 0.396860 | 0.392742 | 1.807795 | 237 |
| 3 | 0.404059 | 0.408871 | 1.825286 | 226 |
| 4 | 0.430738 | 0.423387 | 1.802251 | 212 |
