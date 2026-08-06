# EXP-514 KIRC/KIPAN·GBMLGG/LGG 계통 특이 driver 유전자 고정 패널

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-514 / #514 |
| 목적 | EXP-374 OOF 오답노트 최대 혼동쌍인 KIPAN↔KIRC(390건), GBMLGG↔LGG(288건)를 문헌 근거 계통 driver 유전자 burden 4열로 완화할 수 있는지 단일 family ablation으로 검증 |
| 핵심 입력 | EXP-374의 mutation-type/hotspot-34/residue-position(Ensembl mask)/pathway-20/pathway 변이유형 조성 50열은 그대로, `knowledge/kirc_kidney_glioma_lineage_v1.json`의 kidney/VHL-mTOR·glioma/WHO-IDH 2개 계통 그룹에서 계산한 `mutated_gene_count`/`lof_gene_count` 4열 추가 |
| 모델 | XGBoost `multi:softprob`, EXP-374와 동일 하이퍼파라미터·balanced sample weight·Macro-F1 checkpoint 정책 |
| Local OOF Macro F1 | 0.4269665262 (EXP-374 대비 +0.0001756) |
| Public LB | 미제출 |
| 판단 | **ARCHIVE** — OOF 개선폭(+0.0001756)이 gate 기준(+0.001) 미달, fold 표준편차도 +0.0023869 악화(gate 기준 0.002 초과) |

## 원본 데이터와 입력

한 환자는 4,384개 유전자 열의 변이 문자열(`WT` 또는 변이 토큰) 한 행으로 표현된다.
이번 실험은 그 원본 셀에서 두 개의 고정 유전자 그룹만 다시 요약한다.

- `kidney_vhl_mtor`: `VHL, MTOR, TSC1, TSC2, PTEN, MET, FH` (ccRCC/KIRC의
  VHL-HIF-mTOR 축 driver 유전자)
- `glioma_who_idh`: `IDH1, IDH2, ATRX, TP53, NF1, PTEN, EGFR` (WHO CNS5
  IDH-기반 glioma 분류 driver 유전자)

두 목록은 이 대회의 SUBCLASS 분포나 OOF 성능이 아니라 독립적인 암유전체
문헌에서 먼저 정했다. `PBRM1/SETD2/BAP1/KDM5C/TFE3/TERT/CIC/FUBP1` 같은
교과서적 driver 유전자는 실제 대회 4,384개 패널에 컬럼으로 존재하지 않아
제외했다(사전에 `data/raw/train.csv` 컬럼과 직접 대조해 확인). `PTEN`은
두 그룹에 모두 등장하는데, 두 경로 모두에서 실제로 공유되는 종양억제유전자이기
때문에 의도적으로 유지했다(중복 제거하지 않음).

## 핵심 개념과 피처

각 그룹마다 두 값을 계산한다(총 2 그룹 × 2 값 = 4열).

- `mutated_gene_count`: 그룹 내 유전자 중 `WT`가 아닌 유전자 개수
- `lof_gene_count`: 그룹 내 유전자 중 nonsense 또는 frameshift 변이가 있는
  유전자 개수(loss-of-function 근사)

기존 `fixed_pathway_burden` family(EXP-096/EXP-374, 10개 canonical pathway ×
2값 = 20열)와 완전히 같은 계산 로직(`open_cancer.abc_c_features.
fixed_pathway_burden_family`)을 새 지식 파일 경로로만 다시 호출해 재사용했다.
새 코드를 작성하지 않고 기존 family class를 config 레벨에서만 재사용했다.

## 모델이 학습하는 정보

EXP-374의 전체 feature 파이프라인(stop 표기 무관 파서, Ensembl release 116
residue-position semantic mask, hotspot-34, canonical pathway-20 burden,
pathway 변이유형 조성 50열 후보 중 base와 중복되지 않는 열)을 그대로 유지하고,
그 위에 이번 4개 lineage burden 열만 `sparse.hstack`으로 추가했다. 모델 하이퍼
파라미터, balanced sample weight, Macro-F1 validation checkpoint 선택 정책은
EXP-374와 완전히 동일하다. 유일한 변경은 새 4열의 추가이므로 단일 family
ablation이다.

## 검증 방법

`data/splits/stratified_5fold_seed42.csv` 공용 5-fold, seed 42, 26개 클래스
고정 순서를 사용했다. `fixed_pathway_burden_family`는 `fit_scope: stateless`
(target을 보지 않고 gene-group 정의만으로 계산)이므로 fold 마다 다시 fit할
필요가 없어 전체 train/test에 한 번만 materialize한 뒤 fold ID로 슬라이싱했다.
그럼에도 기존 `run_hotspot_xgb.main`의 `fold_feature_builder` 계약에 따라
매 fold마다 새 4열(및 pathway-20/조성 50열)을 base feature(mutation-type/
hotspot/residue-position 등)와 `remove_semantically_equivalent_features`로
비교해 완전히 같은 열이 있으면 자동 제거하도록 되어 있다(이번 실행에서는
제거된 열 없음). test/validation의 target·분포 정보는 학습 전처리에 사용하지
않았다.

### 의미 중복 사전점검 (기존 pathway family 대비)

`fixed_pathway_burden`(20열, cell_cycle/pi3k/rtk_ras/tp53 등 10개 canonical
pathway)에는 이미 `MTOR, PTEN, TSC1, TSC2`(pi3k), `MET, EGFR, NF1`(rtk_ras),
`TP53`(cell_cycle, tp53)이 부분적으로 포함되어 있어, 신규 lineage 유전자
목록과 유전자 수준에서 부분적으로 겹친다. 하지만 그룹 구성 자체가 다르므로
(`kidney_vhl_mtor` 7개 vs `pi3k` 12개 panel 교집합, `glioma_who_idh` 7개 vs
`rtk_ras` 23개/`tp53` 5개 panel 교집합) 합산 카운트 값이 우연히 같을 가능성만
남는다. `VHL, FH, IDH1, IDH2, ATRX`는 기존 어떤 canonical pathway에도 없는
완전히 새로운 유전자다.

전체 6,201개 train 행에서 신규 4열과 기존 pathway-burden 20열 + 조성 50열
(총 70열)을 byte-level로 전수 비교한 결과, **완전히 동일한 열은 하나도
없었다**(코드: fold-safe 실행 전 throwaway pandas/numpy 비교, 각 열의 6,201개
값을 pairwise `np.array_equal`로 검사). 즉 부분적 유전자 중복은 있지만 값은
완전히 새로운 정보다.

| 열 | 양성 표본 수(6,201건 중) | 최댓값 | 합계 |
|---|---:|---:|---:|
| `kidney_vhl_mtor__mutated_gene_count` | 1,085 | 5 | 1,297 |
| `kidney_vhl_mtor__lof_gene_count` | 424 | 3 | 436 |
| `glioma_who_idh__mutated_gene_count` | 2,649 | 6 | 3,587 |
| `glioma_who_idh__lof_gene_count` | 1,015 | 4 | 1,102 |

## 실제 결과

| 지표 | EXP-514 | EXP-374 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4269665262 | 0.4267909268 | +0.0001755994 |
| Fold 평균 | 0.4265025256 | 0.4266436967 | -0.0001411711 |
| Fold 표준편차 | 0.0108901206 | 0.0085032169 | +0.0023869037 |
| Accuracy | 0.4126753749 | 0.4128366393 | -0.0001612643 |
| Log Loss | 1.8722743988 | 1.8440648317 | +0.0282095671 |

Fold Macro F1: `0.4225165 / 0.4239416 / 0.4144611 / 0.4245547 / 0.4470387`
(EXP-374: `0.4243902 / 0.4214467 / 0.4201172 / 0.4239069 / 0.4433575`). 선택
iteration은 `191 / 195 / 78 / 116 / 116`.

### 가설 타겟 4개 클래스 F1 (실험의 실제 목표)

| 클래스 | EXP-374 | EXP-514 | 변화 |
|---|---:|---:|---:|
| KIPAN | 0.2214983713 | 0.2252252252 | +0.0037268539 |
| KIRC | 0.1759530792 | 0.2037037037 | +0.0277506245 |
| GBMLGG | 0.3197831978 | 0.3031123139 | -0.0166708839 |
| LGG | 0.4186046512 | 0.4358523726 | +0.0172477214 |

KIRC/KIPAN 혼동쌍은 가설 방향대로 뚜렷하게 개선됐다(KIRC +0.0278은 실험
전체에서 두 번째로 큰 양의 변화). LGG도 개선됐다. 그러나 GBMLGG는 오히려
악화되어(-0.0167) 두 혼동쌍의 순효과가 서로 상쇄되면서 전체 OOF Macro F1
개선폭이 gate 기준에 못 미치는 수준(+0.0001756)으로 줄었다.

### 클래스 F1 붕괴 점검 (전체 26개 클래스)

가장 크게 하락한 클래스는 `BLCA` `-0.0362`, `LUAD` `-0.0287`,
`PAAD` `-0.0231`이었고, `-0.05` 이상 붕괴한 클래스는 없었다. 가장 크게
개선된 클래스는 `DLBC` `+0.0620`, `KIRC` `+0.0278`, `LGG` `+0.0172`였다.

## 해석과 한계

- **게이트 판정**: PROJECT_CONTEXT.md 고정 게이트(OOF Macro F1 ≥+0.001,
  fold 표준편차 악화 <0.002, 클래스 F1 붕괴 없음, Log Loss 크게 악화되지
  않음) 중 OOF 개선폭과 fold 표준편차 두 조건에서 실패했다. 클래스 붕괴
  조건은 통과했다.
- 가설이 겨냥한 두 혼동쌍 중 KIPAN/KIRC 방향은 뚜렷이 검증됐지만, GBMLGG/LGG
  방향은 LGG만 개선되고 GBMLGG는 악화되어 순효과가 상쇄됐다. 4개 열 추가로
  fold 표준편차가 커진 것은 표본이 작은 클래스(DLBC 등)에 대한 트리 분기
  변화가 fold마다 다르게 작용했을 가능성을 시사하지만, 이번 실험은 이를
  분리해서 확인하지 않았다.
- Log Loss는 소폭 악화(+0.0282, 약 1.5%)했다. 단독 기각 조건은 아니지만
  방향은 OOF/fold-std 악화와 일관된다.
- `VHL, FH, IDH1, IDH2, ATRX` 5개 유전자는 기존 canonical pathway family에
  전혀 없던 새 정보였음에도 불구하고 실제 게이트를 통과하지 못했다. 즉
  "완전히 새로운 정보"라는 사실 자체가 성능 개선을 보장하지 않는다는 사례로
  기록한다.

## 다음 실험 후보

- KIPAN/KIRC 그룹만 단독으로 추가하는 ablation(글리오마 그룹 제외)으로
  GBMLGG 악화가 glioma 그룹 때문인지 분리 확인.
- GBMLGG/LGG 혼동은 여전히 두 번째로 큰 잔여 오류로 남아 있으므로, WHO grade
  기반 별도 신호(예: 1p/19q 등 이 패널에 없는 정보 대신 사용 가능한 다른
  literature 근거) 탐색이 필요할 수 있다.
- 이번 실험은 fold 표준편차 악화가 gate 실패의 핵심 원인이었으므로, seed를
  바꾼 반복 실행으로 fold 변동성이 이 4열 자체의 재현 가능한 특성인지
  확인하는 후속 진단이 유용할 수 있다.

## 재현과 관련 파일

- 소스 commit: `e56228401be0f50116d67a8154e1fb243ebd0891`
- Config: `configs/exp514_kidney_glioma_lineage_burden.yaml`
- Resolved config: `reproducibility/exp514_kidney_glioma_lineage_burden/config.resolved.yaml`
- Runner: `scripts/run_exp514_kidney_glioma_lineage_burden.py`
- 지식 파일: `knowledge/kirc_kidney_glioma_lineage_v1.json`
- Pathway/lineage membership 감사: `reports/exp514_kidney_glioma_lineage_burden/pathway_membership.json`
- Metrics: `reports/exp514_kidney_glioma_lineage_burden/metrics.json`
- OOF: `oof/exp514_kidney_glioma_lineage_burden.csv`
- test 확률: `preds/exp514_kidney_glioma_lineage_burden_test_proba.csv`
- submission: `submissions/exp514_kidney_glioma_lineage_burden.csv`
- submission SHA-256: `3adefbc57b6b6afb353fe5e7129a52f4fe8cabc283c50fca73ce5e83fa92652d`
- 재현 상태: `INFERENCE_VERIFIED` (checkpoint 재추론 submission SHA-256
  byte-level 일치, test 라벨 100% 일치, 확률 최대 차이 `1.39e-7`)
- Public 리더보드: 미제출 (ARCHIVE 판정이므로 리더보드에 제출하지 않음)

## 판단과 다음 행동

- `ARCHIVE`: OOF Macro F1 개선폭(+0.0001756)이 gate 기준(+0.001) 미달이고
  fold 표준편차도 gate 기준(0.002)을 넘겨 악화(+0.0023869)됐다.
- 클래스 F1 붕괴는 없어 안전성 자체는 확인됐지만, 성능 채택 기준을
  통과하지 못해 EXP-374를 대표 실험으로 유지한다.
- Public LB에는 제출하지 않았다.
