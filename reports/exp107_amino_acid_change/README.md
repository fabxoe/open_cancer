# EXP-107 amino-acid change 단독 검증

## 결론

동결된 EXP-094 Feature Spec v1에 네 개의 샘플 단위 아미노산 물성 변화
카운트를 추가했습니다. 공식 공용 5-fold OOF Macro F1은
**0.4131379001**로 EXP-094보다 `-0.0037486737` 낮고, fold 편차와 Log Loss도
악화되어 **v2-performance 후보로는 채택하지 않습니다**.

반면 EXP-094와 OOF 예측 라벨 일치율은 `0.84712`, 전체 확률 상관은
`0.98175`로 EXP-106보다 다른 예측을 더 많이 만들었습니다. 따라서 단독
Feature Spec에는 넣지 않되 OOF·test 확률을 **v2-diversity 관찰 후보**로
보존하고, 후속 고정 가중 blend에서 실제 보완 이득이 있는지 별도 실험합니다.

## 피처 정의

CSV의 단순 아미노산 치환 토큰에서 reference와 alternate를 읽어 다음 네 값을
샘플별로 계산했습니다.

- 같은 5개 물성 그룹 안에서 바뀐 보수적 치환 수
- 다른 그룹으로 바뀐 비보수적 치환 수
- 전하가 달라진 치환 수
- 극성이 달라진 치환 수

Stop gain, frameshift, complex 토큰은 기존 EXP-094 mutation-type 피처와의 의미
중복을 피하기 위해 추가 집계하지 않았습니다. 물성 분류는
`knowledge/amino_acid_properties_v1.json`에 고정했으며, source·version·license와
파일 SHA-256은 resolved config의 family registry에 기록했습니다. 외부 환자별
값이나 외부 학습 결과는 사용하지 않았습니다.

## 결과

| 항목 | EXP-107 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4131379001 | 0.4168865739 | -0.0037486737 |
| fold 평균 | 0.4128774704 | 0.4162108011 | -0.0033333307 |
| fold 표준편차 | 0.0096630017 | 0.0078842521 | +0.0017787496 |
| Accuracy | 0.4031607805 | 0.4071923883 | -0.0040316078 |
| Log Loss | 1.8461304903 | 1.8399373293 | +0.0061931610 |

| Fold | Macro F1 | Best iteration |
|---:|---:|---:|
| 0 | 0.4060877214 | 182 |
| 1 | 0.4050910239 | 208 |
| 2 | 0.4109500185 | 220 |
| 3 | 0.4106355266 | 171 |
| 4 | 0.4316230615 | 212 |

단독 성능은 기준보다 일관되게 좋지 않았고 fold 4의 상승이 전체 하락을 상쇄하지
못했습니다. 네 개의 저차원 요약만으로는 암종별 유전자 위치 정보를 충분히
보완하지 못한 것으로 판단합니다.

## 다양성 관찰

| 비교 항목(EXP-094 대비) | 값 |
|---|---:|
| OOF 예측 라벨 일치율 | 0.8471214320 |
| 정답/오답 상태 일치율 | 0.9369456539 |
| 전체 OOF 확률 Pearson 상관 | 0.9817471367 |

예측 차이는 EXP-106보다 크지만 오류 상태는 여전히 높은 비율로 일치합니다.
따라서 이 수치만으로 stacking 채택을 결정하지 않고, 모델 다양화 결과와 함께
사전 고정 가중 blend 또는 cross-fitted meta learner에서만 평가합니다.

## 재현성과 산출물

- Issue: [#107](https://github.com/fabxoe/open_cancer/issues/107)
- 실행 소스 commit: `efe36044e117df9e8d9e821e19e092e75844d966`
- resolved config: `reproducibility/exp107_amino_acid_change/config.resolved.yaml`
- metrics: `reports/exp107_amino_acid_change/metrics.json`
- submission: `submissions/exp107_amino_acid_change.csv`
- submission SHA-256: `705ed0a838e223ea80cb2e657782d9569740d20bbc7a16abf787569d69ca4ff8`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 재생성: byte-level SHA-256 일치
- test 라벨 일치율: 100%
- test 확률 최대 절대 오차: `2.9796600298226394e-08`
- Public LB: 미제출

## 다음 결정

- EXP-094 Feature Spec v1은 유지합니다.
- amino-acid change 4개는 v2-performance에 채택하지 않습니다.
- OOF·test 확률은 v2-diversity 관찰 후보로 보존합니다.
- 다음 B-family 실험인 EXP-109 complex morphology로 진행합니다.
- 아미노산 피처의 gene-tier 확장은 B-family 결과를 확인한 뒤 별도 Issue에서만
  검토합니다.
