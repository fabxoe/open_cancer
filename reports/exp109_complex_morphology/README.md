# EXP-109 complex morphology 단독 검증

## 결론

동결된 EXP-094 Feature Spec v1에 complex-token 형태와 샘플 변이 스펙트럼을
요약한 8개 피처를 추가했습니다. 공식 공용 5-fold OOF Macro F1은
**0.4135182559**로 EXP-094보다 `-0.0033683180` 낮고 Log Loss도 악화되어
**v2-performance 후보로는 채택하지 않습니다**.

반면 fold 표준편차는 `0.0047358437`로 EXP-094보다 `-0.0031484084` 줄어
뚜렷하게 안정적이었습니다. OOF 예측 라벨도 EXP-094와 약 12.9% 달라
OOF·test 확률은 **v2-diversity·stability 관찰 후보**로 보존합니다.

## 피처 정의

CSV 토큰만 사용해 다음 8개 샘플 단위 피처를 결정론적으로 계산했습니다.

- multi-position complex: 개수와 전체 토큰 대비 비율
- inframe/delins 형태: 개수와 전체 토큰 대비 비율
- 그 밖의 complex: 개수와 전체 토큰 대비 비율
- nonsense+frameshift의 전체 토큰 대비 truncating 비율
- `(missense+nonsense+frameshift+complex)/(synonymous+1)` 비율

세 complex 형태는 서로 겹치지 않도록 고정 순서로 분류합니다. 분모는 해당
샘플의 전체 변이 토큰 수이며 변이가 없으면 1을 사용합니다. 외부 데이터나
타깃 기반 선택은 사용하지 않았습니다.

## 결과

| 항목 | EXP-109 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4135182559 | 0.4168865739 | -0.0033683180 |
| fold 평균 | 0.4127867985 | 0.4162108011 | -0.0034240026 |
| fold 표준편차 | 0.0047358437 | 0.0078842521 | -0.0031484084 |
| Accuracy | 0.4026769876 | 0.4071923883 | -0.0045154007 |
| Log Loss | 1.8501107693 | 1.8399373293 | +0.0101734400 |

| Fold | Macro F1 | Best iteration |
|---:|---:|---:|
| 0 | 0.4082242921 | 196 |
| 1 | 0.4153132021 | 205 |
| 2 | 0.4094375458 | 236 |
| 3 | 0.4100378141 | 204 |
| 4 | 0.4209211385 | 207 |

모든 fold가 약 0.408~0.421 범위에 있어 특정 fold 붕괴는 줄었습니다. 그러나
평균 성능과 확률 품질은 기준보다 낮으므로 안정성만으로 Feature Spec에
직접 포함하지 않습니다.

## 다양성 관찰

| 비교 항목 | 값 |
|---|---:|
| EXP-094 OOF 예측 라벨 일치율 | 0.8709885502 |
| EXP-094 정답/오답 상태 일치율 | 0.9464602483 |
| EXP-094 전체 OOF 확률 상관 | 0.9852716978 |
| EXP-106 전체 OOF 확률 상관 | 0.9831656686 |
| EXP-107 전체 OOF 확률 상관 | 0.9743355493 |

EXP-107과 가장 낮은 상관을 보여 A의 물성 변화 신호와 B의 morphology 신호가
완전히 같지는 않습니다. 다만 단독 성능 하락이 있으므로 실제 blend/stacking
이득은 별도 Experiment Issue의 공용 OOF 평가로만 판단합니다.

## 재현성과 산출물

- Issue: [#109](https://github.com/fabxoe/open_cancer/issues/109)
- 실행 소스 commit: `2e5882eb9c050292c6167c584cf4977a12c1cdab`
- resolved config: `reproducibility/exp109_complex_morphology/config.resolved.yaml`
- metrics: `reports/exp109_complex_morphology/metrics.json`
- submission: `submissions/exp109_complex_morphology.csv`
- submission SHA-256: `bb2370b62b6931b89727d5edaef9aab1195d4f585d2b96e86e70f66864ffa121`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 재생성: byte-level SHA-256 일치
- test 라벨 일치율: 100%
- test 확률 최대 절대 오차: `2.9763031039742316e-08`
- Public LB: 미제출

## 다음 결정

- EXP-094 Feature Spec v1은 유지합니다.
- complex morphology 8개는 v2-performance에 채택하지 않습니다.
- OOF·test 확률은 v2-diversity·stability 관찰 후보로 보존합니다.
- 다음 B-family 실험인 EXP-110 frequency-tier spectrum으로 진행합니다.
- B-family 결합은 EXP-110 단독 결과를 확인한 뒤 별도 Experiment Issue에서만
  검토합니다.
