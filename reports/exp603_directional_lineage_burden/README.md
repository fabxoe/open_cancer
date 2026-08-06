# EXP-603 KIRC/KIPAN·GBMLGG/LGG lineage burden 방향성 분리 리페어

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-603 / #603 |
| 목적 | EXP-514(ARCHIVE)의 두 pooled 그룹(kidney, glioma)이 GBMLGG를 상쇄시킨 원인이 그룹 내부에 방향이 반대인 유전자가 섞여 있었기 때문이라는 가설을 검증. 같은 14개 유전자를 방향 일치 4개 그룹으로 재분리해 GBMLGG 상쇄가 해소되는지 확인 |
| 핵심 입력 | EXP-374의 mutation-type/hotspot-34/residue-position(Ensembl mask)/pathway-20/pathway 변이유형 조성 50열은 그대로, `knowledge/kirc_kidney_glioma_directional_lineage_v1.json`의 `kirc_lineage`(VHL,MTOR)·`kipan_nonccrcc_lineage`(TSC1,TSC2,MET)·`lgg_idh_lineage`(IDH1,IDH2,ATRX,TP53)·`gbm_idh_wildtype_lineage`(NF1,PTEN,EGFR) 4개 그룹에서 계산한 `mutated_gene_count`/`lof_gene_count` 8열 추가 (EXP-514의 4열은 재사용하지 않음, EXP-374에 대한 독립 ablation) |
| 모델 | XGBoost `multi:softprob`, EXP-374와 동일 하이퍼파라미터·balanced sample weight·Macro-F1 checkpoint 정책 |
| Local OOF Macro F1 | 0.4249849883 (EXP-374 대비 **-0.0018059386**, EXP-514 대비 -0.0019815379) |
| Public LB | 미제출 |
| 판단 | **ARCHIVE** — OOF Macro F1이 EXP-374 대비 오히려 하락. 가설(방향 일치 재분리로 GBMLGG 상쇄 해소)이 반증됨 |

## 원본 데이터와 입력

한 환자는 4,384개 유전자 열의 변이 문자열(`WT` 또는 변이 토큰) 한 행으로 표현된다.
이번 실험은 EXP-514와 같은 14개 유전자를, 그룹 내부의 방향이 섞이지 않도록
4개 그룹으로 다시 나눠 요약한다.

- `kirc_lineage`: `VHL, MTOR` (ccRCC/KIRC를 정의하는 VHL-HIF-mTOR 축 driver)
- `kipan_nonccrcc_lineage`: `TSC1, TSC2, MET` (유두상신세포암 등 KIPAN의
  non-ccRCC 구성요소와 연관된 driver, MET는 papillary RCC의 정의적 driver)
- `lgg_idh_lineage`: `IDH1, IDH2, ATRX, TP53` (WHO CNS5 IDH-mutant
  astrocytoma 공동변이 signature)
- `gbm_idh_wildtype_lineage`: `NF1, PTEN, EGFR` (WHO CNS5/cIMPACT-NOW
  IDH-wildtype GBM 분자 signature)

`FH`는 이 데이터에서 KIPAN·KIRC 모두 변이 0건(zero-variance)으로 확인되어
완전히 제외했다. kidney 맥락의 `PTEN`은 KIPAN 0.0369 대 KIRC 0.0359로 차이가
noise 수준(0.0010)이라 kidney 두 그룹 어디에도 넣지 않았고, glioma 맥락에서만
`gbm_idh_wildtype_lineage`에 유지했다(방향이 GBMLGG +0.128로 뚜렷함).

### 이 방향성은 데이터 마이닝이 아니라 문헌 검증이다

그룹 배정은 독립적인 신경병리/신장병리 문헌(WHO CNS5 IDH-based glioma
classification, WHO 신장종양 분류의 VHL-ccRCC/MET-papillary RCC driver
association)에서 먼저 정했다. `data/raw/train.csv`의 클래스별 변이율은 "이
알려진 생물학이 실제로 이 대회 패널에 반영되는가"를 확인하는 용도로만 썼고,
문헌이 예측한 방향과 어긋난다는 이유로 유전자를 다른 그룹으로 옮기거나
추가·삭제하지 않았다. 아래 표는 재확인한 실제 수치다(`uv run python` 1회
실행, 코드는 `reports/exp603_directional_lineage_burden/semantic_redundancy_precheck.txt`에
전체 출력 보존).

| 그룹 | 유전자 | KIPAN | KIRC | KIRC-KIPAN |
|---|---|---:|---:|---:|
| kirc_lineage | VHL | 0.2990 | 0.4521 | +0.1531 |
| kirc_lineage | MTOR | 0.0485 | 0.0569 | +0.0083 |
| kipan_nonccrcc_lineage | TSC1 | 0.0078 | 0.0030 | -0.0048 |
| kipan_nonccrcc_lineage | TSC2 | 0.0136 | 0.0090 | -0.0046 |
| kipan_nonccrcc_lineage | MET | 0.0369 | 0.0150 | -0.0219 |
| (제외) | PTEN | 0.0369 | 0.0359 | -0.0010 (noise) |
| (제외) | FH | 0.0000 | 0.0000 | 0.0000 (zero-variance) |

| 그룹 | 유전자 | GBMLGG | LGG | LGG-GBMLGG |
|---|---|---:|---:|---:|
| lgg_idh_lineage | IDH1 | 0.4100 | 0.7860 | +0.3760 |
| lgg_idh_lineage | IDH2 | 0.0195 | 0.0393 | +0.0198 |
| lgg_idh_lineage | ATRX | 0.2148 | 0.3624 | +0.1477 |
| lgg_idh_lineage | TP53 | 0.3666 | 0.5066 | +0.1400 |
| gbm_idh_wildtype_lineage | NF1 | 0.0781 | 0.0524 | -0.0257 |
| gbm_idh_wildtype_lineage | PTEN | 0.1627 | 0.0349 | -0.1278 |
| gbm_idh_wildtype_lineage | EGFR | 0.1453 | 0.0349 | -0.1104 |

이 재확인 수치는 Issue #603과 config `notes`에 기재된 값과 정확히 일치한다.

## 핵심 개념과 피처

각 그룹마다 두 값을 계산한다(4 그룹 × 2 값 = 8열). EXP-514와 완전히 같은
계산 로직(`open_cancer.abc_c_features.fixed_pathway_burden_family`)을 새
지식 파일 경로로만 다시 호출해 재사용했다.

- `mutated_gene_count`: 그룹 내 유전자 중 `WT`가 아닌 유전자 개수
- `lof_gene_count`: 그룹 내 유전자 중 nonsense 또는 frameshift 변이가 있는
  유전자 개수(loss-of-function 근사)

### 의미 중복 사전점검 (기존 pathway family 대비)

전체 6,201개 train 행에서 신규 8열과 기존 pathway-burden 20열 + 조성 50열
(총 70열)을 byte-level로 전수 비교한 결과, **완전히 동일한 열은 하나도
없었다**. 전체 출력은
`reports/exp603_directional_lineage_burden/semantic_redundancy_precheck.txt`에
보존했다.

| 열 | 양성 표본 수(6,201건 중) | 최댓값 | 합계 |
|---|---:|---:|---:|
| `kirc_lineage__mutated_gene_count` | 520 | 2 | 547 |
| `kirc_lineage__lof_gene_count` | 181 | 1 | 181 |
| `kipan_nonccrcc_lineage__mutated_gene_count` | 313 | 3 | 354 |
| `kipan_nonccrcc_lineage__lof_gene_count` | 43 | 2 | 44 |
| `lgg_idh_lineage__mutated_gene_count` | 2,143 | 4 | 2,668 |
| `lgg_idh_lineage__lof_gene_count` | 687 | 2 | 726 |
| `gbm_idh_wildtype_lineage__mutated_gene_count` | 801 | 3 | 919 |
| `gbm_idh_wildtype_lineage__lof_gene_count` | 360 | 3 | 376 |

## 모델이 학습하는 정보

EXP-374의 전체 feature 파이프라인(stop 표기 무관 파서, Ensembl release 116
residue-position semantic mask, hotspot-34, canonical pathway-20 burden,
pathway 변이유형 조성 50열 후보 중 base와 중복되지 않는 열)을 그대로 유지하고,
그 위에 이번 8개 lineage burden 열만 `sparse.hstack`으로 추가했다. 모델
하이퍼파라미터, balanced sample weight, Macro-F1 validation checkpoint 선택
정책은 EXP-374와 완전히 동일하다. EXP-514의 4열은 이 실험에 재사용하지
않았다(EXP-514 위에 쌓는 것이 아니라 EXP-374에 대한 독립적인 새 ablation).

## 검증 방법

`data/splits/stratified_5fold_seed42.csv` 공용 5-fold, seed 42, 26개 클래스
고정 순서를 사용했다. `fixed_pathway_burden_family`는 `fit_scope: stateless`
(target을 보지 않고 gene-group 정의만으로 계산)이므로 fold마다 다시 fit할
필요가 없어 전체 train/test에 한 번만 materialize한 뒤 fold ID로 슬라이싱했다.
매 fold마다 새 8열(및 pathway-20/조성 50열)을 base feature와
`remove_semantically_equivalent_features`로 비교해 완전히 같은 열이 있으면
자동 제거하도록 되어 있다(이번 실행에서는 제거된 열 없음). test/validation의
target·분포 정보는 학습 전처리에 사용하지 않았다.

## 실제 결과

| 지표 | EXP-374 | EXP-514 | EXP-603 | 603-374 |
|---|---:|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4269665262 | 0.4249849883 | **-0.0018059386** |
| Fold 평균 | 0.4266436967 | 0.4265025256 | 0.4252759451 | -0.0013677516 |
| Fold 표준편차 | 0.0085032169 | 0.0108901206 | 0.0090872147 | +0.0005839979 |
| Accuracy | 0.4128366393 | 0.4126753749 | 0.4112239961 | -0.0016126432 |
| Log Loss | 1.8440648317 | 1.8722743988 | 1.8725479841 | +0.0284831524 |

Fold Macro F1(EXP-603): `0.4232310016 / 0.4188328455 / 0.4190743900 /
0.4221126377 / 0.4431288505`. 선택 iteration: `220 / 228 / 67 / 159 / 156`.

### 가설 타겟 4개 클래스 F1 (실험의 실제 목표)

| 클래스 | EXP-374 | EXP-514(pooled) | EXP-603(방향 분리) | 603-374 | 514-374 |
|---|---:|---:|---:|---:|---:|
| KIPAN | 0.2214983713 | 0.2252252253 | 0.2234513274 | +0.0019529561 | +0.0037268539 |
| KIRC | 0.1759530792 | 0.2037037037 | 0.1990811639 | +0.0231280847 | +0.0277506245 |
| GBMLGG | 0.3197831978 | 0.3031123139 | 0.3045822102 | **-0.0152009876** | -0.0166708839 |
| LGG | 0.4186046512 | 0.4358523726 | 0.4330985915 | +0.0144939404 | +0.0172477214 |

**가설이 반증됐다.** KIRC/KIPAN/LGG는 EXP-514와 같은 방향으로 개선됐지만
(개선폭은 EXP-514보다 소폭 줄어듦), **GBMLGG는 방향이 완전히 일치하는
유전자만으로 재구성했음에도 -0.0152로 EXP-514의 -0.0167과 거의 같은 폭으로
여전히 악화됐다.** "그룹 내 반대 방향 유전자가 상쇄시킨다"는 원 가설이
맞다면 방향 분리 후 GBMLGG 악화가 크게 줄거나 사라져야 하는데, 실제로는
악화 폭이 거의 그대로 유지됐다. 게다가 전체 OOF Macro F1은 EXP-514보다도
더 낮아졌다(EXP-514 +0.0001756 대비 EXP-603은 -0.0018059로, 오히려 방향
분리가 순효과를 악화시켰다).

### 클래스 F1 붕괴 점검 (전체 26개 클래스)

가장 크게 하락한 클래스는 `PAAD -0.0482`, `BLCA -0.0362`, `THYM -0.0308`,
`OV -0.0228`, `LUAD -0.0225`, `GBMLGG -0.0152`였다. `-0.05` 이상 붕괴한
클래스는 없었지만 `PAAD -0.0482`는 게이트 임계값(-0.05)에 근접했다. 가장
크게 개선된 클래스는 `DLBC +0.0714`, `LAML +0.0362`, `KIRC +0.0231`이었다.

## 해석과 한계

- **게이트 판정**: PROJECT_CONTEXT.md 고정 게이트(OOF Macro F1 ≥+0.001,
  fold 표준편차 악화 <0.002, 클래스 F1 붕괴 없음) 중 fold 표준편차
  (+0.0005839979, 기준 이내)와 클래스 붕괴(없음, `-0.05` 미만) 조건은
  통과했지만, 핵심 지표인 OOF Macro F1이 개선은커녕 EXP-374 대비 **하락**
  (-0.0018059386)해 결정적으로 실패했다.
- **원 가설의 반증**: EXP-603 Issue의 가설은 "EXP-514 pooled 그룹 안에
  방향이 반대인 유전자가 섞여 GBMLGG를 상쇄시켰으므로, 방향이 일치하는
  4개 그룹으로 분리하면 GBMLGG 상쇄가 해소돼 순효과가 개선된다"였다. 실제
  결과는 그 반대를 보여준다. `lgg_idh_lineage`(IDH1/IDH2/ATRX/TP53, 방향
  100% LGG favoring)와 `gbm_idh_wildtype_lineage`(NF1/PTEN/EGFR, 방향 100%
  GBMLGG favoring)로 완전히 분리했는데도 GBMLGG F1은 EXP-514(혼합 그룹)와
  거의 같은 폭(-0.0152 대 -0.0167)으로 악화됐다. 즉 "그룹 내 방향 상쇄"는
  GBMLGG 악화의 실제 원인이 아니었거나, 원인의 일부에 불과했다.
- **제안(다음에 검증해볼 가설, 확정적 결론 아님)**: GBMLGG 악화가 방향
  분리로도 해소되지 않는다는 사실은 "신호 상쇄"보다 다른 메커니즘을
  시사할 수 있다. 예를 들어 이미 4,400개 이상의 feature가 있는 상태에서
  `colsample_bytree=0.8`인 XGBoost가 매 트리마다 80% feature만 무작위로
  샘플링하는데, 새 열을 추가하는 행위 자체가 기존 feature들이 각 분기에서
  선택될 확률을 미세하게 희석시켜 GBMLGG의 결정 경계에 우연히 불리하게
  작용했을 가능성이 있다. 이는 이번 실험에서 직접 검증하지 않은 추측이며,
  검증하려면 (a) 같은 8열을 무작위 노이즈로 치환한 placebo ablation으로
  OOF/GBMLGG F1이 비슷한 폭으로 떨어지는지, (b) `colsample_bytree=1.0`으로
  고정한 통제 비교에서 GBMLGG 악화가 사라지는지 등을 별도 Experiment
  Issue에서 확인해야 한다. 다른 가능성(예: GBMLGG의 실제 결정 경계가
  단순 gene-count burden보다 세밀한 위치/조성 정보에 의존해, 상위 레벨
  burden 열이 트리 분기 우선순위만 바꿔 오히려 방해했을 가능성)도 배제하지
  않는다.
- Log Loss는 EXP-374 대비 소폭 악화(+0.0284831524, 약 1.5%)했고 EXP-514와
  비슷한 수준이다. 단독 기각 조건은 아니지만 방향은 OOF 악화와 일관된다.
- fold 표준편차는 EXP-514(+0.0023869, 게이트 초과)보다 개선됐지만
  (+0.0005839979, 게이트 이내), OOF Macro F1 자체가 하락했으므로 안정성
  개선이 성능 개선을 의미하지 않는다.

## 다음 실험 후보

- 위 "제안" 항목의 placebo ablation(무작위 노이즈 8열)과
  `colsample_bytree=1.0` 통제 비교로 GBMLGG 악화 메커니즘을 실제로 분리
  확인.
- EXP-514/EXP-603 두 번의 연속 ARCHIVE로, 이 14개 유전자를 burden 열로
  추가하는 접근 자체(pooled든 방향 분리든)가 이 모델·feature 조합에서는
  순효과가 없거나 해롭다는 증거가 쌓였다. 같은 설계 방향(고정 유전자 그룹
  단순 합산)의 추가 변형 실험은 우선순위를 낮추고, GBMLGG/LGG·KIPAN/KIRC
  혼동은 다른 종류의 신호(예: 세밀한 위치 기반 피처, 모델 하이퍼파라미터
  조정)로 접근하는 편이 나을 수 있다.

## 재현과 관련 파일

- 소스 commit: `ae30cd03e1b17178fb705091e00c1138a57db236`
- Config: `configs/exp603_directional_lineage_burden.yaml`
- Resolved config: `reproducibility/exp603_directional_lineage_burden/config.resolved.yaml`
- Runner: `scripts/run_exp603_directional_lineage_burden.py`
- 지식 파일: `knowledge/kirc_kidney_glioma_directional_lineage_v1.json`
- Pathway/lineage membership 감사: `reports/exp603_directional_lineage_burden/pathway_membership.json`
- 의미 중복 사전점검 전체 출력: `reports/exp603_directional_lineage_burden/semantic_redundancy_precheck.txt`
- Metrics: `reports/exp603_directional_lineage_burden/metrics.json`
- OOF: `oof/exp603_directional_lineage_burden.csv`
- test 확률: `preds/exp603_directional_lineage_burden_test_proba.csv`
- submission: `submissions/exp603_directional_lineage_burden.csv`
- submission SHA-256: `c4b103e989f20943cd7a1cb36632b93d00227d4b4d2dcfd4ba5c6be6df5f4dee`
- 재현 상태: `INFERENCE_VERIFIED` (checkpoint 재추론 submission SHA-256
  byte-level 일치, test 라벨 100% 일치, 확률 최대 차이 `1.46e-7`,
  `reproducibility/exp603_directional_lineage_burden/comparison.json`)
- Public 리더보드: 미제출 (ARCHIVE 판정이므로 리더보드에 제출하지 않음)

## 판단과 다음 행동

- `ARCHIVE`: OOF Macro F1이 EXP-374 대비 하락(-0.0018059386)해 gate
  기준(+0.001 이상 개선)을 충족하지 못했다. fold 표준편차와 클래스 붕괴
  조건은 개별적으로는 통과했지만 핵심 지표 실패로 전체 판정은 ARCHIVE다.
- 원 가설("그룹 내 방향 반대 유전자가 GBMLGG를 상쇄시킨다")은 방향
  100% 일치 재구성에서도 GBMLGG가 거의 같은 폭으로 악화되어 반증됐다.
- Public LB에는 제출하지 않았다.
