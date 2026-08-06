# EXP-604 KIPAN/KIRC·GBMLGG/LGG 쌍 내부 확률 재분배 — 기각(ARCHIVE)

## 결론

EXP-233(전체 26클래스 offset, 기각)/EXP-276(표본 게이트, 기각)/EXP-515(대상
클래스 4개로 축소, 기각)의 후속이다. 세 실험 모두 `softmax(z)·exp(o)` 후
**행 전체를 재정규화**하는 방식이라 26개 클래스가 zero-sum으로 묶였다.
이번엔 재정규화 방식 자체를 바꿔, 대상 쌍(KIPAN,KIRC)과 (GBMLGG,LGG)의
**확률 합만 고정하고 그 안에서만 비율을 재분배**했다 — 나머지 24개 클래스의
raw 확률 값은 수학적으로 전혀 건드리지 않는다(단위 테스트 7개로 검증 완료).

OOF Macro F1은 **+0.0030888970**(0.4267909268 → 0.4298798238)로 **5-fold
전부 개선**됐다 — EXP-515(4/5 개선)보다 안정적이다. 그러나 **기각(ARCHIVE)한다**
— Log Loss(`+0.0168969669`)와 fold 표준편차(`+0.0014154453`) 둘 다 악화됐고,
비대상 22클래스 절대 F1 변화 합도 `0.0223`으로 사전 게이트(`1e-6`, "구조적으로
0에 가까워야 한다"는 가설)를 통과하지 못했다.

## 핵심 발견: "확률 값이 안 바뀐다"와 "분류 결과가 안 바뀐다"는 다른 명제다

이 실험을 설계할 때 "대상 쌍 외 24개 클래스는 raw 확률이 절대 바뀌지 않으므로
그 클래스들의 F1도 사실상 불변일 것"이라고 기대했다(Issue #604 본문의
"이론상 0에 가까워야 하며"). **이 기대는 절반만 맞았다.**

- **확률 값 자체는 정말 안 바뀐다.** `apply_pairwise_redistribution`은
  대상 쌍의 두 컬럼만 읽고 쓰며, 다른 24개 컬럼은 입력과 byte-level로
  동일하다(`tests/test_nested_decision_offset.py`의
  `test_apply_pairwise_redistribution_never_touches_other_columns` 등
  7개 단위 테스트로 검증, 전부 통과).
- **하지만 argmax(예측 라벨)는 26개 확률의 경쟁이다.** 어떤 행에서 클래스
  C의 확률이 전혀 안 바뀌어도, KIRC나 LGG의 확률이 커지거나 작아지면 그
  경쟁에서 C를 앞지르거나 뒤처질 수 있다 — C 자신의 값은 그대로인데
  **결정 결과(예측 라벨)만 바뀌는** 경우가 생긴다. 이게 비대상 22클래스
  중 11개(ACC, TGCT, PRAD, BRCA, UCEC, SKCM, OV, PAAD, CESC, STES, SARC)에서
  작은 비영(非零) delta로 나타난 원인이다.

즉 "확률 값을 안 건드린다"는 "다른 클래스의 분류 결과를 안 건드린다"를
보장하지 않는다 — 다중 클래스 argmax 구조에서는 어느 한 쌍의 확률만 바꿔도
전체 경쟁 구도가 흔들릴 수 있다. 이는 EXP-515가 발견한 문제(재정규화가
26개를 zero-sum으로 묶는다)와는 다른, **argmax 자체의 근본적 특성**에서
오는 훨씬 약한 형태의 부작용이다.

## 그럼에도 이전 실험들보다 뚜렷이 나아졌다

| 지표 | EXP-233 | EXP-276(threshold 20) | EXP-515 | EXP-604 |
|---|---:|---:|---:|---:|
| 비대상 클래스 손상 | DLBC `-0.1235` 붕괴 | DLBC `-0.0824` | 22클래스 절대합 `0.0994` | 22클래스 절대합 **`0.0223`**(약 4.5배 감소) |
| DLBC 영향 | 붕괴 | 완화됐지만 여전히 악화 | `+0.0084`(우연히 개선) | **`0.0000`**(완전 불변) |
| OOF fold 개선 수 | 3/5 | — | 4/5 | **5/5** |

특히 DLBC(가장 취약했던 클래스)는 이번엔 확률·라벨 모두 단 하나도 안
바뀌었다 — 이 쌍 근처에 경쟁이 발생할 만한 행이 전혀 없었기 때문으로
보인다. 11개 클래스는 delta가 정확히 `0.0000`으로, 재정규화 계열
실험들과 달리 실제로 "손을 안 댄" 클래스가 다수 존재한다.

## 결과

| 지표 | EXP-374 (baseline) | EXP-604 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4298798238 | **+0.0030888970** |
| Fold 표준편차 | 0.0085032169 | 0.0099186621 | +0.0014154453 (악화) |
| Log Loss | 1.8440648894 | 1.8609618563 | +0.0168969669 (악화) |
| 비대상 22클래스 절대 F1 변화 합 | — | 0.0223279962 | 허용치(1e-6)의 약 22,328배 |

표적 4개 클래스 F1 변화(EXP-374 → EXP-604):

| 클래스 | delta | 참고: EXP-515 delta |
|---|---:|---:|
| KIRC | +0.0565 | +0.0925 |
| LGG | +0.0657 | +0.0854 |
| GBMLGG | -0.0154 | -0.0298 |
| KIPAN | -0.0253 | -0.0478 |

EXP-515보다 네 클래스 모두 변화 폭이 절반 가까이 줄었다 — 이번 메커니즘이
"확률 합을 유지한 채 내부 비율만 미는" 더 보수적인 조정이라, 같은 grid에서도
실제 이동량 자체가 작다.

비대상 22클래스 중 0이 아닌 delta를 가진 11개(절대값 순): ACC `+0.0065`,
TGCT `-0.0056`, PRAD `+0.0018`, BRCA `-0.0017`, UCEC `-0.0015`, SKCM
`-0.0013`, OV `-0.0011`, PAAD `+0.0010`, CESC `+0.0009`, STES `-0.0006`,
SARC `+0.0004`. `-0.05` 이상 붕괴는 없다. 나머지 11개(BLCA, COAD, DLBC,
HNSC, LAML, LIHC, LUAD, LUSC, PCPG, THCA, THYM)는 delta 정확히 `0.0000`.

Fold별 탐색 delta(각 outer fold의 inner cross-fit에서 독립적으로 탐색):

| outer fold | KIPAN/KIRC δ | GBMLGG/LGG δ | validation Macro F1 delta |
|---:|---:|---:|---:|
| 0 | -0.8 | -0.2 | +0.003912 |
| 1 | -0.3 | -0.9 | +0.001447 |
| 2 | -0.3 | -0.8 | +0.001114 |
| 3 | +0.1 | -0.3 | +0.002150 |
| 4 | -0.1 | -1.0 | +0.005290 |

음수 δ가 KIPAN/KIRC와 GBMLGG/LGG 양쪽 모두에서 우세하다 — KIRC와 LGG
쪽으로 확률 질량이 밀렸다는 뜻이며, 표 "표적 4개 클래스"의 부호와 일치한다.

## 설계

- Issue: [#604](https://github.com/fabxoe/open_cancer/issues/604)
- 부모: EXP-374(재학습 없음, 저장된 OOF `oof/exp374_stop_isoform_residue_mask.csv` 재사용)
- 신규 공용 함수(`src/open_cancer/nested_decision_offset.py`):
  - `apply_pairwise_redistribution(probabilities, pair_indices, delta)`:
    대상 쌍 `(a, b)`의 확률 합 `s = p_a + p_b`를 고정하고, 내부 비율
    `r = p_a / s`를 logit 공간에서 `r' = sigmoid(logit(r) + delta)`로
    이동시킨다. `p_a' = s·r'`, `p_b' = s - p_a'`이며 다른 24개 클래스는
    입력을 그대로 반환한다(`s ≈ 0`인 행은 재분배할 질량이 없어 원본 유지).
  - `search_pairwise_delta(probabilities, targets, pair_indices, ...)`:
    inner cross-fit 확률에서 `δ ∈ [-1.0, 1.0]`(step 0.1) grid search로
    regularized Macro F1을 최대화하는 `δ`를 찾는다. 두 쌍이 서로 다른
    컬럼만 건드리므로 좌표하강 없이 쌍마다 독립적으로 1차원 탐색한다.
- Inner cross-fit 프록시는 EXP-515와 동일하게 EXP-374 자체 feature
  파이프라인을 재구성(`build_exp374_train_matrix()`)해 사용, 캐시를
  공유해 재계산을 생략했다(`data/processed/exp515_exp374_base_features`).
- 채택 규칙(실행 전 고정): OOF Macro F1 개선 **AND** Log Loss 비악화
  **AND** fold-std 비악화 **AND** 비대상 22클래스 절대 F1 변화 합
  `≤1e-6`(구조적으로 거의 0이어야 한다는 가설의 직접 검증). 넷 중 하나라도
  실패하면 ARCHIVE.

## 다음 시도를 위한 메모

- 주 지표(Macro F1)는 EXP-233/276/515보다 훨씬 안정적으로 개선됐고
  (5/5 fold), 비대상 손상도 4.5배 줄었다 — 메커니즘 자체는 옳은 방향이다.
  다만 Log Loss·fold-std 악화와 11개 클래스의 소폭 간섭이 여전히 채택
  기준을 넘지 못했다.
- 간섭을 더 줄이려면: (1) `regularization_lambda`를 키워 δ가 극단값
  (`-0.8`~`-1.0`)으로 가는 것을 억제, (2) δ 탐색 grid를 더 좁게(예:
  `[-0.5, 0.5]`) 제한, (3) argmax 경쟁이 실제로 발생하는 행(대상 쌍의
  확률이 이미 다른 클래스와 근접한 행)만 별도로 식별해 그 영향을 미리
  계량하는 진단을 추가하는 방향을 고려할 수 있다. 이번 실험 결과를 본
  뒤 사후 조정하지 않으므로, 시도한다면 새 Experiment Issue에서 사전
  고정해야 한다.

## 재현성

- Config: `configs/exp604_pairwise_probability_redistribution.yaml`
- Runner: `scripts/run_exp604_pairwise_probability_redistribution.py`
- 공용 함수: `src/open_cancer/nested_decision_offset.py`의
  `apply_pairwise_redistribution`/`search_pairwise_delta`(단위 테스트
  `tests/test_nested_decision_offset.py`)
- Metrics: `reports/exp604_pairwise_probability_redistribution/metrics.json`
- 상세: `reports/exp604_pairwise_probability_redistribution/pair_offset_detail.json`
- 재현 상태: `NOT_STARTED`(일반 Local 진단 실험, 리더보드 미제출·팀 상위
  모델 아님, PROJECT_CONTEXT.md 8절 기준 재현 번들 불필요)
- 제출: 없음(기각된 실험)
