# EXP-123 동결 Feature Spec v1 희소 Logistic Regression

## 결론

동결된 EXP-094 Feature Spec v1은 그대로 두고 모델만 XGBoost에서 희소 다항
Logistic Regression으로 바꿨습니다. 공식 canonical 5-fold OOF Macro F1은
**0.3763324825**로 EXP-094보다 `-0.0405540914` 낮았습니다. 예측 다양성은 컸지만
품질 하한과 wildcard gate를 모두 통과하지 못해 **현재 stacking 후보로
채택하지 않습니다**. OOF와 test 확률은 모델 다양화 연구 자산으로 보존합니다.

## 초보자를 위한 모델 설명

Logistic Regression은 각 피처에 클래스별 가중치를 붙이고, 그 합을 26개 암종의
확률로 바꾸는 선형 모델입니다. XGBoost처럼 피처 사이의 복잡한 조건 조합을
나무로 학습하지 않기 때문에 단일 성능은 낮을 수 있지만, 다른 방식으로 틀린다면
앙상블에서 보완 역할을 할 가능성이 있습니다.

Feature Spec v1에는 0/1 희소 피처와 큰 숫자의 residue position이 함께 있습니다.
숫자 단위 때문에 선형 모델이 한 종류의 피처에 끌리지 않도록 각 outer fold의
train에서만 `MaxAbsScaler`를 fit했습니다. validation과 test는 해당 fold scaler로
transform했으며 정답이나 validation 분포는 scaling에 사용하지 않았습니다.

## 고정 조건

- Feature Spec: `v1` = EXP-094, 35,119개 피처
- Feature Spec SHA-256:
  `1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`
- Split: `data/splits/stratified_5fold_seed42.csv`, canonical 5-fold
- 모델: multinomial Logistic Regression, `solver=saga`, `C=1.0`
- scaling: fold-train `MaxAbsScaler`
- class-balanced sample weight 사용
- Public LB: 미제출

## 결과

| 항목 | EXP-123 | EXP-094 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.3763324825 | 0.4168865739 | -0.0405540914 |
| Fold 표준편차 | 0.0042109416 | 0.0078842521 | -0.0036733105 |
| Accuracy | 0.3712304467 | 0.4071923883 | -0.0359619416 |
| Log Loss | 2.1261745525 | 1.8399371814 | +0.2862373711 |

| Fold | Macro F1 | Accuracy | Log Loss |
|---:|---:|---:|---:|
| 0 | 0.3701706160 | 0.3803384367 | 2.1302706833 |
| 1 | 0.3754824506 | 0.3629032258 | 2.1648812636 |
| 2 | 0.3798275842 | 0.3685483871 | 2.1265881660 |
| 3 | 0.3691361071 | 0.3741935484 | 2.1079683405 |
| 4 | 0.3779347342 | 0.3701612903 | 2.1011610056 |

EXP-094보다 클래스 F1이 개선된 암종은 7개입니다. 비교적 큰 개선은 TGCT
`+0.0491`, PAAD `+0.0295`, LGG `+0.0137`, LAML `+0.0092`였습니다. 반면 BLCA,
LUSC, CESC, UCEC 등 다수 클래스가 크게 하락해 전체 성능 손실을 상쇄하지
못했습니다.

## 다양성·채택 gate

| EXP-094 대비 항목 | 값 |
|---|---:|
| 예측 라벨 불일치율 | 0.4616997259 |
| 정답/오답 상태 상관 | 0.5962549057 |
| 전체 확률 Pearson 상관 | 0.7767793880 |
| 전체 확률 Spearman 상관 | 0.6442813438 |

- 다양성 gate: 통과
- 품질 gate: 실패 (`-0.004` 하한보다 크게 낮음)
- wildcard gate: 실패 (Macro F1 하락과 Log Loss 악화가 큼)
- ensemble quality eligible: 아니오

즉 “XGBoost와 다르게 예측한다”는 사실만으로는 충분하지 않습니다. 너무 약한
모델을 섞으면 오히려 좋은 모델의 확률을 희석하므로 현재 고정 blend나 stacking
입력에는 넣지 않습니다.

## 재현성과 산출물

- Issue: [#123](https://github.com/fabxoe/open_cancer/issues/123)
- 실행 source commit: `63637a3e67733909bee21f6b9a072db7a42cdb68`
- Config: `configs/exp123_sparse_logistic_v1.yaml`
- Resolved config: `reproducibility/exp123_sparse_logistic_v1/config.resolved.yaml`
- Metrics: `reports/exp123_sparse_logistic_v1/metrics.json`
- OOF: `oof/exp123_sparse_logistic_v1.csv`
- Test probability: `preds/exp123_sparse_logistic_v1_test_proba.csv`
- 제출 후보: `submissions/exp123_sparse_logistic_v1.csv` (DACON 미제출)
- 제출 SHA-256:
  `7947df0753ed4237a5f3967bd1e3bc8f4da7a2d6626feef935489e5e6aae81e0`
- 재현 상태: `INFERENCE_VERIFIED`

저장한 다섯 checkpoint로 OOF와 test를 다시 추론했으며 라벨 일치율 100%, 확률
최대 절대 차이 0, 제출 CSV byte-level SHA-256 일치를 확인했습니다.

## 다음 결정

EXP-123은 선형 diversity 참고 자산으로 보존하되 현재 앙상블 후보에서는
제외합니다. 로드맵의 다음 독립 모델인 LightGBM을 새 Experiment Issue에서 같은
동결 Feature Spec으로 검증합니다.
