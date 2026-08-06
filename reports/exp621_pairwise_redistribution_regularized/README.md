# EXP-621 쌍 내부 확률 재분배 정규화 강화판 — 기각(ARCHIVE)

## 결론

EXP-604(같은 메커니즘, `regularization_lambda=0.001`, 기각)의 직접 후속이다.
EXP-604는 δ가 grid 경계(`-0.8`~`-1.0`)로 쏠려 Log Loss(`+0.0169`)·fold
표준편차(`+0.0014`)가 악화되고 비대상 22클래스 절대 F1 변화 합이 `0.0223`
(게이트 `1e-6`)까지 벌어졌다. 이 실험은 메커니즘은 그대로 두고
`regularization_lambda`만 `0.001 → 0.02`로 올려 δ 탐색 자체가 더 작은 값을
선호하도록 했다.

의도한 효과는 실제로 나타났다 — δ가 `-0.2`~`0.0` 범위로 크게 줄었고, Log Loss
악화(`+0.0024`)와 fold 표준편차(오히려 **개선** `-0.0005`)는 EXP-604보다 훨씬
안정적이다. 그러나 **여전히 기각(ARCHIVE)한다** — 비대상 22클래스 절대 F1
변화 합이 `0.0173`으로 완화된 게이트(`0.015`)를 `0.0023` 초과했고, Log
Loss도 근소하게나마 계속 악화됐다. Macro F1 개선폭(`+0.0012`)도 게이트
(`+0.001`)를 겨우 넘는 수준으로 EXP-604(`+0.0031`)의 약 39%에 그쳤다.

## 결과

| 지표 | EXP-374 (baseline) | EXP-604 | EXP-621 | EXP-621 변화(vs baseline) |
|---|---:|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4298798238 | 0.4280073811 | **+0.0012164543** |
| Fold 표준편차 | 0.0085032169 | 0.0099186621 | 0.0079831891 | **-0.0005200278(개선)** |
| Log Loss | 1.8440648894 | 1.8609618563 | 1.8464348703 | +0.0023699809(악화, EXP-604의 약 14%) |
| 비대상 22클래스 절대 F1 변화 합 | — | 0.0223279962 | 0.0172821978 | 게이트 `0.015` 대비 **+0.0022822 초과** |

Fold Macro F1: 0.4276003809, 0.4230462101, 0.4202558188, 0.4245067174,
0.4429112596 — 5-fold 전부 baseline 대비 개선(EXP-604와 동일하게 5/5).

표적 4클래스 F1 delta(EXP-374 → EXP-621, EXP-604와 비교):

| 클래스 | EXP-604 delta | EXP-621 delta | EXP-621/EXP-604 비율 |
|---|---:|---:|---:|
| KIRC | +0.0565 | +0.0196 | 35% |
| LGG | +0.0657 | +0.0212 | 32% |
| GBMLGG | -0.0154 | -0.0076 | 50% |
| KIPAN | -0.0253 | -0.0098 | 39% |

정규화가 의도대로 이동량 자체를 EXP-604의 3분의 1~2분의 1 수준으로 줄였다.

비대상 22클래스 중 0이 아닌 delta를 가진 6개(EXP-604는 11개): CESC
`+0.0056`, LIHC `+0.0057`, TGCT `-0.0039`, PRAD `+0.0009`, SARC `+0.0006`,
OV `-0.0006`. 건드린 클래스 수는 절반 가까이 줄었지만, LIHC처럼 EXP-604에서
전혀 안 움직였던 클래스가 새로 `+0.0057`만큼 흔들리는 등 "총합은 줄어도
어떤 클래스가 흔들리는지는 예측 불가능"하다는 EXP-604의 관찰이 이번에도
반복됐다.

Fold별 탐색 δ(참고로 EXP-604는 모두 `-0.8`~`-1.0`이었다):

| outer fold | KIPAN/KIRC δ | GBMLGG/LGG δ |
|---:|---:|---:|
| 0 | -0.2 | -0.2 |
| 1 | 0.0 | -0.1 |
| 2 | -0.1 | 0.0 |
| 3 | 0.0 | -0.1 |
| 4 | -0.1 | 0.0 |

## 오늘 진행한 별도 진단과의 관계

이 실험과 별개로, 같은 날 "δ의 크기를 줄이는 정규화"가 아니라 "δ를 적용하는
**행의 범위**를 줄이는" 게이트(대상 쌍 중 하나가 그 행의 현재 argmax인
행에만 적용) 아이디어를 EXP-604의 저장된 δ에 재적용해 사후 진단했다(재학습
없음, `apply_pairwise_redistribution` 그대로 재사용). 결과: collateral을
`0.0223 → 0.0158`(-29%), Log Loss 악화를 `+0.0169 → +0.0131`(-22%)까지
줄이면서 Macro F1 이득은 거의 유지(`+0.0031 → +0.0029`)했으나, 건드린 행
수를 89% 줄였음에도 collateral은 29%만 줄었다 — **collateral이 무관한
행이 아니라 KIRC/LGG를 살리는 데 필요한 바로 그 행들에서 함께 발생**한다는
뜻이다. 또한 fold 표준편차는 게이트를 걸어도 개선되지 않았다.

즉 "δ 크기 축소"(이 실험)와 "적용 행 범위 축소"(진단)는 서로 다른 축이고
둘 다 단독으로는 4개 게이트를 전부 통과하지 못했다 — 전자는 collateral·fold
표준편차는 잘 억제했지만 F1 이득이 너무 작아졌고, 후자는 collateral·Log
Loss는 더 줄였지만 fold 표준편차는 그대로다. 두 축을 **결합**(게이트 +
완화된 정규화)하면 이 실험 단독보다 나은 트레이드오프가 나올 가능성이
있으나, 사전에 게이트·정규화 값을 함께 고정하는 새 Experiment Issue로
진행해야 한다(이번 실행 결과를 보고 사후에 조정하지 않는다는 원칙).

## 설계

- Issue: [#621](https://github.com/fabxoe/open_cancer/issues/621)
- 부모: EXP-374(재학습 없음, 저장된 OOF `oof/exp374_stop_isoform_residue_mask.csv`
  재사용), 직접 부모는 EXP-604(같은 메커니즘, 정규화만 강화)
- 메커니즘: `src/open_cancer/nested_decision_offset.py`의
  `apply_pairwise_redistribution`/`search_pairwise_delta`를 코드 변경 없이
  재사용, `regularization_lambda`만 `0.001 → 0.02`로 변경
- 근거: EXP-604 리포트의 "다음 시도를 위한 메모"에서 제안한 3가지 방향
  중 (1) 정규화 강화를 택했다. 실행 전 사후 delta scale sweep 진단
  (EXP-604의 실제 δ를 스케일링만 해서 시뮬레이션, 재탐색 아님)으로 25%
  스케일에서 Macro F1 `+0.0016`·Log Loss `+0.0030`·collateral `0.0149`가
  나올 것으로 예측했고, 이번 실제 재탐색 결과(Macro F1 `+0.0012`·Log Loss
  `+0.0024`·collateral `0.0173`)는 그 예측과 대체로 일치하되 collateral만
  게이트를 근소하게 넘었다.
- 채택 규칙(실행 전 고정): OOF Macro F1 `≥+0.001` **AND** Log Loss 비악화
  **AND** fold-std 비악화 **AND** 비대상 22클래스 절대 F1 변화 합
  `≤0.015`. Log Loss·collateral 두 조건 위반으로 ARCHIVE.

## 재현성

- Config: `configs/exp621_pairwise_redistribution_regularized.yaml`
- Runner: `scripts/run_exp621_pairwise_redistribution_regularized.py`
- 공용 함수: `src/open_cancer/nested_decision_offset.py`(EXP-604와 동일,
  코드 변경 없음)
- Metrics: `reports/exp621_pairwise_redistribution_regularized/metrics.json`
- 상세: `reports/exp621_pairwise_redistribution_regularized/pair_offset_detail.json`
- 재현 상태: `NOT_STARTED`(일반 Local 진단 실험, 리더보드 미제출·팀 상위
  모델 아님, PROJECT_CONTEXT.md 8절 기준 재현 번들 불필요)
- 제출: 없음(기각된 실험)
