# EXP-515 KIPAN/KIRC·GBMLGG/LGG 한정 post-hoc decision offset — 기각(ARCHIVE)

## 결론

EXP-233(전체 26클래스 offset, 기각)/EXP-276(표본 게이트 추가, 기각) 계열의
후속 실험이다. 이번엔 offset 탐색·적용 범위를 EXP-374 OOF 오답노트에서 가장
큰 두 혼동쌍인 **KIPAN·KIRC**와 **GBMLGG·LGG** 4개 클래스로만 한정하고 나머지
22개 클래스는 offset=0으로 고정해, EXP-276이 확인한 "게이트해도 이웃 클래스가
피해를 준다"는 실패 메커니즘을 구조적으로 차단하려 했다.

전체 OOF Macro F1은 EXP-374 대비 **+0.0028860085**(0.4267909268 →
0.4296769353) 개선됐고 5개 fold 중 4개가 개선됐다. 그러나 **기각(ARCHIVE)한다**
— 사전에 고정한 두 가지 채택 조건을 동시에 위반했다.

1. **Log Loss가 악화**됐다: 1.8440648894 → 1.8725976665 (`+0.0285327771`).
2. **비대상 22개 클래스가 실제로는 전혀 보호되지 않았다**: 22개 클래스의
   절대 F1 변화 합계가 `0.0993875903`로, 사전 설정 허용치(`0.01`)의
   **거의 10배**다. 특히 SARC `-0.0321`, TGCT `+0.0169`, CESC `-0.0085`,
   DLBC `+0.0084`, HNSC `+0.0048`, BRCA `-0.0043`가 크게 움직였다.

## 핵심 발견: "offset 대상만 한정"으로는 다른 클래스를 보호할 수 없다

이 결과는 EXP-276의 발견("게이트로 offset을 0에 고정해도 그 클래스 F1은
보호되지 않는다")을 한 단계 더 일반화한다. `apply_class_offset`은
`softmax(z)·exp(o)`를 계산한 뒤 **행 전체를 재정규화**한다. KIRC/LGG처럼
eligible 클래스의 raw 확률이 최대 `exp(1.0)≈2.72`배까지 커지면, 같은 행의
나머지 22개 클래스는 자기 offset이 정확히 0이어도 **분모가 커지므로 상대
확률이 강제로 줄어든다**. 이 재정규화는 26개 클래스를 하나의 zero-sum
경쟁으로 묶기 때문에, "탐색 대상을 4개로 줄인다"는 이번 설계 변경은
EXP-233/276이 겪은 문제의 **원인(coordinate descent가 무관한 클래스까지
탐색)**을 제거했을 뿐, **결과(재정규화가 무관한 클래스의 확률을 흔든다)**는
막지 못했다.

다만 EXP-233의 가장 심각한 문제였던 **DLBC 붕괴는 이번엔 재현되지 않았고
오히려 DLBC F1이 `+0.0084` 개선**됐다 — 표적 4클래스만 다뤘기 때문에
왜곡의 절대 크기 자체는 EXP-233(26개 클래스 전부 탐색)보다 작아진 것으로
보이지만, SARC처럼 이미 취약한 다른 저성능 클래스(baseline F1 0.242)로
피해가 옮겨갔을 뿐 근본적으로 해결되지는 않았다.

## 결과

| 지표 | EXP-374 (baseline) | EXP-515 (offset 적용) | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4296769353 | **+0.0028860085** |
| Fold 표준편차 | 0.0085032169 | 0.0067862836 | -0.0017169333 (개선) |
| Log Loss | 1.8440648894 | 1.8725976665 | **+0.0285327771 (악화)** |
| 비대상 22클래스 |F1| 변화 합 | — | 0.0993875903 | 허용치(0.01)의 약 9.9배 |

표적 4개 클래스 F1 변화(이번 실험의 실제 목표):

| 클래스 | before | after | delta |
|---|---:|---:|---:|
| KIPAN | 0.2215 | 0.1737 | -0.0478 |
| KIRC | 0.1760 | 0.2684 | **+0.0925** |
| GBMLGG | 0.3198 | 0.2900 | -0.0298 |
| LGG | 0.4186 | 0.5040 | **+0.0854** |

KIRC·LGG는 크게 개선됐지만 KIPAN·GBMLGG는 오히려 하락했다 — offset이 쌍
안에서 한쪽으로 확률 질량을 밀어주는 효과이지, 두 클래스를 동시에 더 잘
구분하게 만드는 효과가 아님을 보여준다(재정규화 zero-sum 구조상 KIPAN이
잃은 만큼 KIRC가 얻는 관계에 가깝다).

Fold별 offset(각 outer fold의 inner cross-fit에서 독립적으로 탐색, 부호와
크기가 fold마다 다름 — EXP-233에서 관측된 DLBC offset 불안정 패턴과 유사):

| outer fold | GBMLGG | KIPAN | KIRC | LGG | validation Macro F1 delta |
|---:|---:|---:|---:|---:|---:|
| 0 | +0.1 | -0.3 | +0.9 | +0.3 | +0.0010 |
| 1 | -0.3 | +0.2 | +0.2 | +0.6 | +0.0013 |
| 2 | -0.5 | -0.5 | +0.3 | +0.8 | +0.0081 |
| 3 | +0.1 | +0.5 | +0.8 | +0.4 | +0.0028 |
| 4 | -0.4 | -0.2 | +0.5 | +1.0 | -0.0012 |

## 설계

- Issue: [#515](https://github.com/fabxoe/open_cancer/issues/515)
- 부모: EXP-374(재학습 없음, 저장된 OOF `oof/exp374_stop_isoform_residue_mask.csv` 재사용)
- 재학습 없음: EXP-233/276과 동일하게 outer 모델은 EXP-374의 저장된 OOF를
  transform만 한다.
- **Inner cross-fit 대상 변경**: EXP-233/276은 baseline(EXP-219)이 frozen
  Feature Spec v1 모델이라 v1 매트릭스를 inner-CV 프록시로 재사용했다.
  EXP-374는 v1이 아닌 별도 feature 공간(stop 정규화 파서 + pathway-20 +
  hotspot-34 + Ensembl isoform residue mask)이므로, 이번 실험은
  `materialize_frozen_feature_spec` 대신 **EXP-374의 실제 feature 파이프라인을
  그대로 재구성**(`build_exp374_train_matrix()`, EXP-374의
  `PathwayMutationTypeFoldBuilder`·stop-notation 파서 재사용)해 inner-CV
  프록시가 실제 baseline과 같은 표현 공간을 쓰도록 했다. 재구성 중
  `materialize_frozen_feature_spec`가 이 실행 환경(Windows)에서 기존에 알려진
  것과 다른 해시 불일치를 냈고(원인 미조사, 팀에 별도 보고 필요), EXP-374
  자체 파이프라인 재사용은 이 문제를 우회했다.
- Offset 탐색 범위: `open_cancer.nested_decision_offset.search_class_offsets`의
  `eligible_classes` 인자를 KIPAN·KIRC·GBMLGG·LGG 4개로만 고정(EXP-276이 도입한
  표본 게이트 메커니즘과 같은 파라미터, 이번엔 표본 수가 아니라 오답노트로
  사전 확정한 혼동쌍 기준). 나머지 22개는 좌표하강 탐색에서 제외, offset=0
  하드 고정.
  Grid `[-1.0, 1.0]` step 0.1, `regularization_lambda=0.001`, 최대 5 pass —
  EXP-233/276과 동일.
- 채택 규칙(실행 전 고정): OOF Macro F1 개선 **AND** Log Loss 악화 없음
  **AND** fold-std 악화 없음 **AND** 비대상 22클래스 절대 F1 변화 합계
  `≤0.01`. 넷 중 하나라도 실패하면 ARCHIVE.

## 다음 시도를 위한 메모

이번 실패로 "탐색 대상 클래스 수를 줄이는" 접근은 한계가 뚜렷해졌다. 진짜로
다른 클래스를 건드리지 않으려면 **행 전체 재정규화가 아니라, 대상 쌍
내부에서만 확률 질량을 재분배**(예: `p_KIPAN + p_KIRC`의 합은 고정하고 그
안에서만 비율 조정, 나머지 24개 클래스의 raw 확률은 완전히 불변)하는 방식이
필요해 보인다. 이번 실험은 그 설계를 시도하지 않았으므로 별도 Issue에서
다뤄야 한다.

## 재현성

- Config: `configs/exp515_scoped_pairwise_decision_offset.yaml`
- Runner: `scripts/run_exp515_scoped_pairwise_decision_offset.py`
- Metrics: `reports/exp515_scoped_pairwise_decision_offset/metrics.json`
- 상세: `reports/exp515_scoped_pairwise_decision_offset/pair_offset_detail.json`
- 재현 상태: `NOT_STARTED`(일반 Local 진단 실험, 리더보드 미제출·팀 상위 모델
  아님, PROJECT_CONTEXT.md 8절 기준 재현 번들 불필요)
- 제출: 없음(기각된 실험)
