# EXP-656 isolated MMR gene (MLH1/MSH2/PMS2) proxy on EXP-374 (legacy)

## 결론

EXP-653이 EXP-527(class-cosine native) 부모에서 LGG `-0.1304`·KIRC
`-0.1071` 붕괴로 ARCHIVE된 것과 같은 MMR panel(`knowledge/mmr_gene_proxy_v1.json`,
MLH1/MSH2/MSH6/PMS2)을 legacy 부모 EXP-374 위에서 재검증했다.

**클래스 붕괴 가설은 확인됐다** — LGG `-0.0015`, KIRC `-0.0028`로 사실상
변화가 없다(어떤 클래스도 `-0.05` 붕괴 없음, 최대 하락 LUSC `-0.0252`).
canonical OOF Macro F1도 `0.4280917838`로 부모보다 `+0.0013008570`
개선해 aggregate gate(`≥0.001`)를 통과했다.

그러나 **test-like subset(상위 25% domain-propensity quantile) 점검에서는
EXP-374보다 낮다**(`0.4239727456` vs `0.4283785968`, shift_gap
`+0.0041`). 전체 OOF gate 통과와 무관하게 이 저장소는 test-like subset
역전을 `REJECTED` 기준으로 다뤄왔다(EXP-464, EXP-496 선례). 따라서
**`REJECTED`**로 판단한다.

## 해석

이 실험은 두 가지를 분리해서 확인했다.

1. **class-cosine 부모의 fragility 가설은 맞았다.** 같은 feature, 같은
   panel인데 부모만 EXP-527(native)→EXP-374(legacy)로 바꾸자 LGG/KIRC
   붕괴가 사라졌다. KIPAN/KIRC·GBMLGG/LGG 축은 class-cosine이 낀 native
   계보에서만 무관한 feature 추가로 반복 붕괴하는 것으로 보인다(EXP-639,
   EXP-645, EXP-653과 일관).
2. **그러나 MMR panel 자체의 실제 일반화 신호는 약하거나 없다.** 붕괴가
   없어졌다고 해서 이 feature가 Public에 도움이 된다는 뜻은 아니다.
   test-like subset에서는 오히려 EXP-374보다 낮아, 전체 OOF의
   `+0.0013` 개선이 "test와 안 닮은" 75% 구간에서만 나온 것으로 보인다.

## 실험 계약

- Issue/브랜치: #656 / `issue-656-mmr-gene-proxy-exp374`
- 부모: EXP-374
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 부모의 stop parser·Ensembl residue mask·pathway·hotspot·XGBoost 설정 고정
- 유일한 변경: `ObservableMarkerFamily`(EXP-302/653와 동일 구현, 코드 변경
  없음)로 만든 격리 MMR proxy 4개(`any_mutated`, `any_nonsynonymous`,
  `any_lof`, `multi_gene_mutated`) 추가
- fold-safe semantic equivalence 검사(raw base feature reference)에서
  중복 열 0개(4개 전부 생존)
- SUBCLASS·test 분포·Public LB는 panel 정의에 사용하지 않음

## 결과

| 지표 | EXP-656 | EXP-374 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4280917838 | 0.4267909268 | +0.0013008570 |
| Fold 평균 | 0.4276806058 | 0.4266436967 | +0.0010369091 |
| Fold 표준편차 | 0.0075944351 | 0.0085032169 | -0.0009087818 |
| Accuracy | 0.4133204322 | 0.4128366393 | +0.0004837929 |
| Log Loss | 1.8447273970 | 1.8440648317 | +0.0006625653 |

Fold Macro F1은 `0.4272791 / 0.4248413 / 0.4187580 / 0.4258071 /
0.4417174`이다.

클래스별 최대 하락은 LUSC `-0.0252`, LUAD `-0.0227`, GBMLGG `-0.0127`이며
**LGG `-0.0015`, KIRC `-0.0028`로 사실상 무영향**이다(EXP-653의 LGG
`-0.1304`/KIRC `-0.1071`과 뚜렷이 대비). 최대 개선은 LAML `+0.0365`,
PAAD `+0.0238`, STES `+0.0159`다.

## Test-like subset 점검(#292 adversarial validation, 상위 25% quantile)

| 후보 | 전체 OOF | test-like subset | shift_gap |
|---|---:|---:|---:|
| EXP-374 | 0.4268 | 0.4284 | -0.0016 |
| EXP-484 | 0.4320 | 0.4307 | +0.0013 |
| **EXP-656** | **0.4281** | **0.4240** | **+0.0041** |
| EXP-527(참고) | 0.4469 | 0.4374 | +0.0095 |
| EXP-653(참고, ARCHIVE) | 0.4480 | 0.4159 | +0.0321 |

EXP-656의 shift_gap(`+0.0041`)은 native 계보(EXP-527 `+0.0095`, EXP-653
`+0.0321`)보다 훨씬 낮아 붕괴가 사라진 것과 일관되지만, EXP-374
(`-0.0016`)·EXP-484(`+0.0013`)보다는 여전히 높고 test-like subset macro
F1 자체가 EXP-374보다 낮다.

## 재현성

- Config: `configs/exp656_mmr_gene_proxy_exp374.yaml`
- Runner: `scripts/run_exp656_mmr_gene_proxy_exp374.py`
- Metrics: `reports/exp656_mmr_gene_proxy_exp374/metrics.json`
- OOF: `oof/exp656_mmr_gene_proxy_exp374.csv`
- test 확률: `preds/exp656_mmr_gene_proxy_exp374_test_proba.csv`
- submission: `submissions/exp656_mmr_gene_proxy_exp374.csv`
- submission SHA-256:
  `b33b3aedd07ca84b8f05896149d32f75f8a25e77f494e6cbbe27a117c144a482`
- 재현 상태: `INFERENCE_VERIFIED`

## 판단과 다음 행동

- `REJECTED`. 전체 OOF gate는 통과하고 클래스 붕괴도 없지만, test-like
  subset에서 부모 EXP-374보다 낮아 일반화 개선으로 보기 어렵다(EXP-464,
  EXP-496과 동일 기준 적용).
- class-cosine 부모의 fragility 가설은 확인됐으므로, 앞으로 KIPAN/KIRC·
  GBMLGG/LGG 축에 민감한 feature를 검증할 때는 legacy 부모에서 먼저
  안정성을 확인하는 것이 유효한 방법론으로 남는다.
- MMR panel 자체를 이 형태로 추가 탐색하지 않는다(EXP-302, EXP-653에 이어
  세 번째 기각).
