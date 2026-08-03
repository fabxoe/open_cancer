# PIK3CA helical/kinase 도메인 분리 feature 사전 검증

> 새 모델 실험이나 점수를 만들지 않는 target-independent 사전 검증
> 기록입니다. 실행 전 기각이므로 Experiment Issue와 EXP-ID를 만들지
> 않습니다. 실제 실험 결과의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)입니다.

## 배경

Vera Health 권고: PIK3CA는 helical domain(약 542/545/546)과 kinase
domain(약 1047)에 hotspot이 나뉘어 있고, 도메인별로 암종 특이성이
다르게 나타난다(helical → CESC/BLCA/HNSC 위주, kinase → BRCA 위주
예상). POLE D/E(#181/#226, 기각) 때 썼던 사전 검증 패턴(좌표 정의 →
train 양성 건수 → fold 분포 → 기존 목록과 중복 확인)을 그대로 적용해
착수 전에 실익을 판단했다.

## 1) 기존 상태

`src/open_cancer/hotspot_features.py`의 `EXTENDED_HOTSPOTS`(base v1
feature spec)에 PIK3CA는 이미 5개 개별 position 컬럼으로 들어가 있다.

| 컬럼 | reference AA | 출처 |
|---|---|---|
| `hotspot__PIK3CA_545` | E | 원래 19개(`KNOWN_HOTSPOTS`) |
| `hotspot__PIK3CA_1047` | H | 원래 19개 |
| `hotspot__PIK3CA_542` | E | 후속 15개(`ADDITIONAL_HOTSPOTS`) |
| `hotspot__PIK3CA_546` | Q | 후속 15개 |
| `hotspot__PIK3CA_345` | N | 후속 15개(Vera 목록에 없는 제3 domain, ABD로 추정) |

`build_hotspot_matrix()`는 `(gene, position, reference)`만 확인하고
특정 alternate AA는 확인하지 않는다 — `hotspot__PIK3CA_545`는 이미
E545K/A/G/Q 등 545번 자리의 모든 치환을 포함한다.

`sample__comut_PIK3CA_PTEN`(EXP-052/058)은 유전자 수준 co-mutation(둘
다 변이 여부) 지표로 축이 달라 완전 중복은 아니다.

## 2) 기각 사유별 결론

### kinase(H1047R/L/Y) — 기각: 신규 정보 없음

기존 `hotspot__PIK3CA_1047`과 사실상 동일하다. 차이는 `H1047Q`(train
2건)뿐이며, Vera 정확 alt 버전(170건)과 position-only 버전(172건)의
차집합이 이 2건이다. 모델이 이미 거의 동일한 정보를 갖고 있어 새 열이
줄 수 있는 정보량이 사실상 0에 가깝다.

### helical(E542K/E545K/E545A/E545G/Q546x) OR 집계 — 기각: 과거 실패 패턴과 동일 구조

세 기존 개별 컬럼(542/545/546)을 OR로 합치는 패턴은 EXP-170/173(Cell
Cycle 15/6유전자 OR, 기각)과 구조적으로 동일한
gene/position-group-OR이다. `pole_ed_features.py` docstring이 명시하는
"EXP-021/107/170/173이 정보 없음으로 확인한 gene-group-OR 패턴"에
정확히 해당한다. POLE D/E가 채택 검토까지 간 이유는 "기존에 없던
exact-alt position-specific 신규 컬럼"이었기 때문이지, 기존 컬럼을
합친 게 아니었다 — helical 후보는 이 차이가 없다.

게이트 자체는 통과한다(참고용, 5개 fold 전부):

| | helical (Vera 정확 alt) | kinase (Vera 정확 alt) |
|---|---:|---:|
| 전체 train 양성 | 262 | 170 |
| fold별 support_train | 198~215 | 128~149 |
| fold별 p0_train | 0.9567~0.9601 | 0.9700~0.9742 |
| Gate A/B (5 fold 전부) | 통과 | 통과 |
| Gate C(≥0.8, 차단) | 미발동 | 미발동 |

게이트 통과가 "정보량 있음"을 보장하지 않는다는 점은 EXP-170/173에서도
이미 확인된 바(Gate A/B 전부 통과했음에도 DLBC F1 급락)와 일관된다.

### 3-category(helical-only/kinase-only/both) 설계 — 보류: 전제 소멸

kinase를 후보에서 제외하기로 한 시점에서 이 설계의 전제(두 경쟁 후보가
동시에 활성일 때 중복 2건을 이중계산하지 않기 위한 구분)가 사라진다.
kinase 제외 후 "helical-only"는 겹치는 2건만 제외한 사실상 "helical"과
동일 신호이고(262건→260건), "both" 카테고리는 표본이 1~2건뿐이라
fold-train 기준 Gate B(≥5)를 통과하지 못한다. 설계 자체를 진행할 근거가
없다.

참고로 `src/open_cancer/mutation_features.py:416-423`의
`sample__comut_{gene_a}_{gene_b}`(EXP-052/058)는 "mutual exclusivity"
쌍과 "co-occurrence" 쌍을 구분 없이 동일한 "둘 다 변이면 1" AND
지표로 계산한다 — A-only/B-only/neither를 구분하는 3-category 패턴은
코드베이스에 선례가 없다. 또한 EXP-058은 문헌상 mutual exclusivity
쌍(`APC/CTNNB1`)의 SHAP 기여도가 가설과 반대(COAD에서 음수)로 나와
제거한 전례가 있어, "문헌상 관계"가 자동으로 유효한 신호를 보장하지
않는다는 것도 이미 확인됐다.

### 중복 관측 2건 — 데이터 이상 아님, 조치 불필요

`TRAIN_1540`(STES, 셀 `E545K H1047R`)과 `TRAIN_3326`(BRCA, 셀
`Q546K H1047R`) 두 샘플은 PIK3CA 셀에 helical 토큰과 kinase 토큰이
공백으로 구분되어 각각 하나씩 들어 있다. 파싱 오류가 아니라 같은
샘플에서 PIK3CA 이중(compound) hotspot 변이가 실제로 관측된 것이며,
이 표기법만으로는 cis(같은 대립유전자)/trans(다른 대립유전자) 여부를
구분할 수 없다.

## 결론

Vera Health 1차 답변의 "PIK3CA 도메인 분리" 후보는 기존 position-level
feature(base v1의 개별 hotspot 컬럼 5개)가 이미 이 정보를 담고 있어
실익이 없다고 판단한다. kinase는 기존 컬럼과 사실상 동일, helical OR은
과거 기각 패턴과 동일 구조, 3-category 설계는 kinase 제외로 전제
소멸 — 세 방향 모두 착수를 보류한다.

## 관련

- [EXP-170](../exp170_cellcycle_any_nonsilent/README.md) — Cell Cycle
  any-nonsilent OR 집계, 기각 (같은 구조 패턴)
- [EXP-173](../exp173_cellcycle_lof_tsg/README.md) — Cell Cycle TSG LoF
  OR 집계, 기각 (같은 구조 패턴)
- [EXP-181](../exp181_pole_hotspot5/README.md) — POLE ED hotspot5, 이번
  사전 검증이 따른 패턴의 원본
- [EXP-226](../exp226_pole_ed_driver_extended/README.md) — POLE ED
  driver extended
- [EXP-058](../exp058_cooccurrence_pair_ablation/README.md) —
  mutual-exclusivity 쌍 SHAP 검증 및 제거 사례
