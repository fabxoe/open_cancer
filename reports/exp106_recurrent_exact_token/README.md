# EXP-106 recurrent exact-token 단독 검증

## 결론

동결된 EXP-094 Feature Spec v1에 fold-train에서 반복 관측된
`(유전자, 원시 변이 토큰)` 이진 피처를 추가했습니다. 공식 공용 5-fold OOF
Macro F1은 **0.4147478922**로 EXP-094보다 `-0.0021386817` 낮아
**v2-performance 후보로는 채택하지 않습니다**.

다만 EXP-094와 OOF 예측 라벨이 8.40% 다르고 확률 상관이 `0.99291`이므로,
OOF·test 확률은 ABC 신호 포트폴리오의 후속 blend/stacking 검토 자산으로
보존합니다. 현재로서는 독립성이 크지 않아 v2-diversity의 우선 후보로도
승격하지 않고, 다른 모델·family와 함께 비교합니다.

## 무엇을 검증했나

- 기준: EXP-094 Feature Spec v1, 35,119개 피처
- 추가 family: `recurrent_exact_token` v1.0.0
- vocabulary 단위: `(gene, raw mutation token)`
- 값: 한 샘플에서 관측되면 1, 아니면 0
- 선택 범위: 각 outer fold의 train 행만 사용
- 최소 support: 5개 fold-train 샘플
- 최대 차원: 512개
- 동률 정렬: support 내림차순 → gene → raw token 사전순
- validation/test에만 나타난 토큰: OOV로 무시

### 기존 피처와 의미 중복 방지

fold-train에서 EXP-094 열과 값이 완전히 같은 exact-token은 자동 제외했습니다.
예를 들어 `EGFR L858R`처럼 기존 hotspot 열과 같은 토큰이나, 특정 유전자의
frameshift 열과 완전히 같은 토큰을 두 번 넣지 않았습니다.

| Fold | 최초 vocabulary | 중복 제외 | 최종 추가 차원 |
|---:|---:|---:|---:|
| 0 | 284 | 12 | 272 |
| 1 | 310 | 13 | 297 |
| 2 | 296 | 11 | 285 |
| 3 | 314 | 13 | 301 |
| 4 | 310 | 11 | 299 |

정확한 vocabulary·support·제외 대응표는
`reports/exp106_recurrent_exact_token/fold_vocabularies/`에 보존했습니다.

## 결과

| 항목 | EXP-106 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4147478922 | 0.4168865739 | -0.0021386817 |
| fold 평균 | 0.4142640562 | 0.4162108011 | -0.0019467449 |
| fold 표준편차 | 0.0081208280 | 0.0078842521 | +0.0002365759 |
| Accuracy | 0.4034833091 | 0.4071923883 | -0.0037090792 |
| Log Loss | 1.8370317221 | 1.8399373293 | -0.0029056072 |

| Fold | Macro F1 | Best iteration |
|---:|---:|---:|
| 0 | 0.4161139855 | 182 |
| 1 | 0.4196788033 | 207 |
| 2 | 0.4006706391 | 245 |
| 3 | 0.4106390952 | 226 |
| 4 | 0.4242177580 | 228 |

Macro F1과 정확도는 하락했고 fold 변동성은 소폭 증가했습니다. 반면 Log Loss는
소폭 좋아져, 정답 라벨 결정은 개선하지 못했지만 일부 확률 보정 신호는 남아
있을 가능성이 있습니다.

## 다양성 관찰

| 비교 항목(EXP-094 대비) | 값 |
|---|---:|
| OOF 예측 라벨 일치율 | 0.9159812933 |
| 정답/오답 상태 일치율 | 0.9633930011 |
| 전체 OOF 확률 Pearson 상관 | 0.9929096377 |

예측 차이는 존재하지만 확률과 오류 구조의 상관이 높습니다. 따라서 단독 성능
하락을 감수할 만큼 강한 다양성이라고 아직 판단하지 않습니다. 후속 모델
다양화 단계에서 고정 가중 blend 또는 stacking을 별도 Experiment Issue로만
평가합니다.

## 재현성과 산출물

- Issue: [#106](https://github.com/fabxoe/open_cancer/issues/106)
- 실행 소스 commit: `8e54d0f48b891bbc8aa99130e1954cf1cb8b6f08`
- resolved config: `reproducibility/exp106_recurrent_exact_token/config.resolved.yaml`
- metrics: `reports/exp106_recurrent_exact_token/metrics.json`
- submission: `submissions/exp106_recurrent_exact_token.csv`
- submission SHA-256: `143cf88a8a285d487f6250d6e8d0158703f0310c29fec7e4ddc864199fe134f0`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 재생성: byte-level SHA-256 일치
- test 라벨 일치율: 100%
- test 확률 최대 절대 오차: `2.972793577971089e-08`
- Public LB: 미제출

## 판단과 다음 단계

- EXP-094 Feature Spec v1은 그대로 유지합니다.
- recurrent exact-token은 v2-performance에 채택하지 않습니다.
- OOF·test 확률은 포트폴리오 비교용으로 보존합니다.
- 다음 독립 A-family인 EXP-107 amino-acid change를 같은 기준에서 실행합니다.
- exact-token 재검증은 support·차원 변경을 한 Issue에서 여러 번 탐색하지 않고,
  필요성이 확인될 때 별도 Experiment Issue로 진행합니다.
