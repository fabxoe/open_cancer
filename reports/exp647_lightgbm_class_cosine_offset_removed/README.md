# EXP-647 EXP-567 LightGBM class-cosine 공통 offset 제거 (EXP-645 재확인)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-647 / #647 |
| 목적 | EXP-645(EXP-527/XGBoost)의 class-cosine 공통 offset 제거 ablation을 다른 모델(LightGBM)에서 재확인 |
| 방법 | EXP-567과 완전히 동일한 조건 + row-wise mean centering(EXP-645와 동일 구현) |
| Local OOF Macro F1 | 0.4464076172 (EXP-567 대비 -0.0013340212) |
| Public LB | 미제출 |
| 판단 | canonical OOF·fold std·Log Loss 전부 악화 — `ARCHIVE`. EXP-645(XGBoost)보다 더 명확한 실패로, 두 모델 모두에서 offset 제거가 채택 기준을 못 넘김을 확인 |

## 배경

EXP-645는 EXP-527(XGBoost)에서 26개 class-cosine 점수의 row-mean
offset을 제거했을 때 Macro F1은 악화(-0.0083)했지만 fold std·Log Loss는
개선되는 엇갈린 결과를 냈다. XGBoost(level-wise 트리 성장)와 다른
LightGBM(leaf-wise)에서도 같은 패턴이 나오는지, 아니면 모델마다 다르게
반응하는지 확인하기 위해 EXP-567(LightGBM, EXP-527과 동일한 parser-v4
parent + class-cosine feature 사용)에 같은 ablation을 적용했다.

## 실제 결과

| 지표 | EXP-567(parent) | EXP-647(offset 제거) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4477416384 | 0.4464076172 | -0.0013340212(악화) |
| Fold 표준편차 | 0.0045984625 | 0.0052780570 | +0.0006795945(악화) |
| Accuracy | 0.4363812288 | 0.4342847928 | -0.0020964360 |
| Log Loss | 1.8136045028 | 1.8250550985 | +0.0114505957(악화) |

Fold별 Macro F1(EXP-567 → EXP-647): fold0 `0.4457→0.4492`(개선), fold1
`0.4505→0.4362`(하락), fold2 `0.4448→0.4452`(거의 동일), fold3
`0.4537→0.4517`(소폭 하락), fold4 `0.4406→0.4443`(개선). 3개 fold
개선·2개 하락으로 fold별 방향은 EXP-645보다 덜 일방적이다.

### 클래스별 비교(EXP-567 대비)

| 방향 | 클래스(델타) |
|---|---|
| 큰 하락 | BLCA `-0.0570`, THYM `-0.0273`, KIRC `-0.0254`, CESC `-0.0213` |
| 큰 개선 | LUAD `+0.0586`, LIHC `+0.0425`, PAAD `+0.0214` |

`-0.05` 붕괴 기준을 넘는 클래스는 BLCA 1개뿐이다. 흥미롭게도 EXP-645에서
가장 크게 붕괴했던 LGG는 여기서 거의 영향이 없다(`+0.0045`) — LGG
취약성은 XGBoost 특유의 반응이었다는 뜻이다. 다만 KIRC는 두 모델
모두에서 하락했다(EXP-645 `-0.0550`, EXP-647 `-0.0254`) — KIRC만큼은
모델과 무관하게 공통 offset에서 일부 신호를 얻고 있을 가능성이 있다.

## 해석과 한계

- **EXP-645보다 더 명확한 실패다.** EXP-645는 fold std·Log Loss가
  개선되는 트레이드오프라도 있었지만, EXP-647은 Macro F1·fold std·
  Log Loss **전부 악화**했다. LightGBM은 이 transform에서 어떤 축으로도
  득을 보지 못했다.
- 두 모델 모두 채택 기준(canonical OOF Macro F1)을 넘지 못해, "공통
  offset은 순수 노이즈"라는 가설은 2개 모델에서 연속으로 기각됐다. 이
  라인의 추가 시도(다른 모델·다른 centering 방식)는 낮은 우선순위로
  내린다.
- LGG·KIRC 반응이 모델마다 다르다는 것은, 공통 offset이 모든 클래스에
  균일하게 작용하는 게 아니라 클래스·모델 조합마다 다른 방식으로
  신호/노이즈가 섞여 있다는 뜻이다. 단순 row-mean centering 같은
  전역적 처리로는 이 이질성을 다루기 어렵다.
- 채택 기준에 따라 `ARCHIVE`. test-like propensity 등 domain-shift
  진단으로 재평가하지 않는다(parser/feature 의미 결정 규칙, EXP-645와
  동일 원칙).

## 다음 실험 후보

- class-cosine offset 제거 라인은 여기서 종료. 대신 legacy 계보의
  EXP-484(0.7/0.3 고정 블렌드)가 여전히 Local·안정성 균형이 가장 좋은
  다음 제출 후보로 남는다.
- KIRC가 두 모델 모두에서 일관되게 반응한 것은 별도로 흥미로운 신호라,
  KIRC 단일 클래스에 특화된 후속 분석 후보로 기록해둔다(이 실험만으로
  결론 내리지 않음).

## 재현과 관련 파일

- Config: `configs/exp647_lightgbm_class_cosine_offset_removed.yaml`
- Runner: `scripts/run_exp647_lightgbm_class_cosine_offset_removed.py`
- Metrics: `reports/exp647_lightgbm_class_cosine_offset_removed/metrics.json`
- Submission: `submissions/exp647_lightgbm_class_cosine_offset_removed.csv`(DACON 미제출, ARCHIVE)
- Reproduction status: `INFERENCE_VERIFIED`
