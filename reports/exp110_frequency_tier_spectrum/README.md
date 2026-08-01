# EXP-110 frequency-tier spectrum 단독 검증

## 결론

동결된 EXP-094 Feature Spec v1에 fold-train 유전자 빈도 tier별 mutation-type
count·fraction 40개를 추가했습니다. 공식 공용 5-fold OOF Macro F1은
**0.3963504903**으로 EXP-094보다 `-0.0205360836` 낮고 Log Loss도 크게
악화되어 **v2-performance 후보에서 제외합니다**.

EXP-094와 전체 OOF 확률 상관은 `0.95224`, 예측 라벨 일치율은 `0.75052`로
앞선 ABC 후보보다 독립성은 커졌습니다. 하지만 단독 성능 손실이 너무 크므로
**저우선순위 diversity 연구 자산**으로만 OOF·test 확률을 보존하고, Feature
Spec이나 초기 blend 후보에는 넣지 않습니다.

## 피처 정의와 누수 방지

각 outer fold마다 다음 절차를 독립적으로 수행했습니다.

1. fold-train에서 각 유전자의 변이 존재 샘플 수를 계산합니다.
2. support 오름차순, gene 사전순으로 4,384개 유전자를 정렬합니다.
3. 같은 크기의 tier 4개로 나눕니다.
4. tier별 missense·synonymous·nonsense·frameshift·complex count를 계산합니다.
5. 같은 20개 값을 샘플 전체 토큰 수로 나눈 fraction 20개를 추가합니다.

validation과 test는 support·tier 결정에 사용하지 않았습니다. fold별 전체
gene→tier·support 매핑은 `fold_tier_mappings/`에 저장해 실행 규칙을 재현할 수
있게 했습니다.

## 결과

| 항목 | EXP-110 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.3963504903 | 0.4168865739 | -0.0205360836 |
| fold 평균 | 0.3953058395 | 0.4162108011 | -0.0209049616 |
| fold 표준편차 | 0.0076071528 | 0.0078842521 | -0.0002770993 |
| Accuracy | 0.3930011289 | 0.4071923883 | -0.0141912595 |
| Log Loss | 1.8794993162 | 1.8399373293 | +0.0395619869 |

| Fold | Macro F1 | Best iteration |
|---:|---:|---:|
| 0 | 0.3930559003 | 177 |
| 1 | 0.4006713623 | 208 |
| 2 | 0.3872658175 | 187 |
| 3 | 0.3883148635 | 167 |
| 4 | 0.4072212541 | 184 |

모든 fold에서 기준보다 낮아 우연한 특정 fold 문제가 아니라 현재 tier 표현
자체가 XGBoost의 기존 유전자 단위 신호를 흐린 것으로 판단합니다.

## 다양성 관찰

| 비교 항목 | 값 |
|---|---:|
| EXP-094 OOF 예측 라벨 일치율 | 0.7505241090 |
| EXP-094 정답/오답 상태 일치율 | 0.8945331398 |
| EXP-094 전체 OOF 확률 상관 | 0.9522398631 |
| EXP-106 전체 OOF 확률 상관 | 0.9505043094 |
| EXP-107 전체 OOF 확률 상관 | 0.9468862260 |
| EXP-109 전체 OOF 확률 상관 | 0.9544366126 |

독립성은 가장 크지만 약한 모델의 단순 혼합은 강한 모델을 훼손할 수 있습니다.
따라서 후반 stacking에서 cross-fitted meta learner가 유효한 가중치를 실제로
부여하는 경우에만 사용하고, 수동 blend의 기본 후보에서는 제외합니다.

## 재현성과 산출물

- Issue: [#110](https://github.com/fabxoe/open_cancer/issues/110)
- 실행 소스 commit: `1c0e835eecb5d5edbffc61c632c583395f698d1b`
- resolved config: `reproducibility/exp110_frequency_tier_spectrum/config.resolved.yaml`
- metrics: `reports/exp110_frequency_tier_spectrum/metrics.json`
- fold tier mapping: `reports/exp110_frequency_tier_spectrum/fold_tier_mappings/`
- submission: `submissions/exp110_frequency_tier_spectrum.csv`
- submission SHA-256: `69943c81ba7bf0354e662c5a8177c2a3bbde7a370d623cfd32066d3c3558c0cc`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 재생성: byte-level SHA-256 일치
- test 라벨 일치율: 100%
- test 확률 최대 절대 오차: `2.9739379847626424e-08`
- Public LB: 미제출

## 다음 결정

- frequency-tier spectrum은 v2-performance와 초기 blend 후보에서 제외합니다.
- OOF·test 확률은 저우선순위 stacking 연구 자산으로만 보존합니다.
- A/B 첫 단독 실험 묶음이 끝났으므로 EXP-094, EXP-106, EXP-107, EXP-109,
  EXP-110의 성능·다양성 포트폴리오를 종합해 다음 Issue를 결정합니다.
- C-family는 주최측 허용 확인 후 EXP-096에서 별도 공식 검증했습니다.
