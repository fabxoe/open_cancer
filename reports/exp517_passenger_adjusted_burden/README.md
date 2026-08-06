# EXP-517 장(長)유전자 passenger 다운웨이트 파생 burden 추가

## 결론

EXP-374(현재 팀 대표/최고 Public 모델)의 모든 피처와 설정을 그대로 두고,
"passenger-like"로 추정되는 15개 장(長)유전자 목록(EXP-374 오답노트에서
여러 무관한 혼동쌍에 반복 등장) 기반의 파생 burden 컬럼 2개만 **추가**했다.
기존 `GENE__mutated` 컬럼은 하나도 제거·대체하지 않았다(순수 additive).

결과는 **ARCHIVE**다. OOF Macro F1이 `0.4239028776`으로 EXP-374
(`0.4267909268`) 대비 `-0.0028880493`로, 사전에 고정한 게이트(+0.001 이상
개선)를 통과하지 못했다. fold 표준편차와 Log Loss도 소폭 악화됐다. 이번
실험은 이 저장소에서 5번 REJECTED된 "컬럼 제거/가지치기" 계열과는 다른
메커니즘(정보 손실이 아니라 순수 추가)이었지만, 그럼에도 OOF 성능이 개선되지
않았다. 원래 가설의 대상이었던 LUSC F1은 오히려 `-0.0175` 악화됐고, STES는
`+0.0034`로 소폭 개선에 그쳤다.

## 실험 계약

- Issue/브랜치: #517 / `issue-517-passenger-adjusted-burden`
- 부모: EXP-374 (component: EXP-374)
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 모델·하이퍼파라미터·balanced sample weight·Macro-F1 checkpoint 정책 고정
  (EXP-374와 완전히 동일)
- EXP-374의 stop 정규화 parser, hotspot, Ensembl residue-position mask, 고정
  Sanchez-Vega pathway family(`fixed_pathway_burden`,
  `pathway_mutation_type_composition`)를 모두 그대로 유지
- 유일한 변경: 아래 2개 파생 컬럼 추가 (기존 컬럼 제거·대체 없음)
- SUBCLASS·test 분포·Public LB는 유전자 목록이나 공식 정의에 사용하지 않음

### 배경: 이전 컬럼 제거 계열 5연속 REJECTED

이 저장소에서 컬럼 제거/가지치기 계열 실험은 5번 모두 REJECTED됐다.

| EXP | 변경 | 결과 |
|---|---|---|
| EXP-188/189/190 | fold-local Phi/Jaccard 상관 기반 열 삭제(C1/C2/C3) | fold std 또는 클래스 F1 붕괴로 ARCHIVE |
| EXP-192 | fold-local 양성 수 `<5` mutation-presence 열 제거 | Macro F1은 소폭 개선했으나 fold std `+0.0073553`로 gate 실패 |
| EXP-355/359 | complex token count/indicator 표현 교체(제거+대체) | Macro F1 하락·Log Loss 상승으로 기각 |
| EXP-496 | EXP-355/359 계열 robust complex-count 재평가 | REJECTED (재확인) |

이 5건은 공통적으로 **정보 손실**(기존 열 삭제 또는 값 대체)이 실패 원인으로
의심됐다. EXP-517은 그 가설을 검증하기 위해 **어떤 기존 열도 삭제하지 않고**
파생 열만 추가하는 additive-only 설계로 진행했다. 그 결과 이번 실패는
fold-std/Log Loss 붕괴가 아니라 **OOF Macro F1 자체가 개선되지 않음**(오히려
소폭 하락)이라는, 이전 5건과는 다른 메커니즘의 실패였다 — 정보 손실이 아니라
파생 신호 자체가 이 모델·피처 조합에서 추가 예측력을 주지 못한 것으로
해석된다.

## 원본 데이터와 입력

한 환자는 4,384개 유전자 열로 표현되며 각 셀은 `WT` 또는 변이 문자열이다.
EXP-374까지의 모든 피처(원본 유전자별 mutation presence/type/위치, hotspot,
pathway burden 등)는 그대로 입력에 남아 있다. 이번 실험은 그 위에 샘플
단위 파생 숫자 2개만 얹는다.

## 핵심 개념과 피처

15개 "장유전자 passenger 후보" 목록은
`knowledge/long_gene_passenger_candidates_v1.json`에 고정했다.

```text
RYR2, SYNE1, PCLO, DST, SPTA1, DMD, PKHD1, COL11A1, COL6A3,
COL12A1, MYH2, RYR1, AHNAK, VWF, PDE4DIP
```

이 15개는 EXP-374 OOF 오답노트에서 LUSC↔STES 등 서로 무관한 여러 혼동쌍에
반복 등장했고, 동시에 일반 분자생물학 지식상 매우 긴 유전자/거대 단백질로
알려져 있다(DMD는 인간에서 가장 긴 유전자, RYR2/SYNE1/PCLO/AHNAK는 매우 큰
단백질을 암호화). 이는 Lawrence MS et al. 2013(Nature)이 기술한 "긴 유전자일수록
배경/passenger 변이가 더 많이 관찰된다"는 현상과 일치한다. 목록은 유전자
길이라는 target-독립적 속성으로 고정했으며, SUBCLASS나 test 데이터를 보고
고르지 않았다(정확한 DOI는 확인하지 못해 임의로 기재하지 않았다).

새 파생 컬럼 2개:

- `sample__mutated_gene_count_excl_passenger` = 기존
  `sample__mutated_gene_count`(샘플의 전체 변이 유전자 수) − 이 샘플에서
  변이가 있는 15개 passenger 후보 유전자 수
- `sample__passenger_gene_fraction` = (이 샘플에서 변이가 있는 15개
  passenger 후보 유전자 수) / 15

두 값 모두 `src/open_cancer/abc_c_features.py`의 기존
`fixed_pathway_burden_family`(단일 그룹으로 passenger 목록을 넣어 재사용)로
얻은 `mutated_gene_count`와, 항상 base feature에 존재하는 기존
`sample__mutated_gene_count` 열을 조합해 계산했다(새 raw counting 코드를
작성하지 않음). 구현은
`scripts/run_exp517_passenger_adjusted_burden.py`의
`PassengerAdjustedBurdenFoldBuilder`이며,
`scripts/run_exp229_pathway_mutation_types.py`의
`PathwayMutationTypeFoldBuilder`를 내부에서 그대로 호출해 EXP-374의 pathway
family 출력을 손대지 않고 그 위에 2개 열만 `hstack`한다.

## 모델이 학습하는 정보

모델은 EXP-374와 완전히 동일한 XGBoost(`multi:softprob`, `n_estimators=500`,
`max_depth=6`, `learning_rate=0.05` 등)이며, 입력 피처는 EXP-374의 전체
피처(약 4,470여 개) + 새 파생 2개 열이다. 타깃은 26개 `SUBCLASS`이고,
checkpoint는 validation fold Macro F1 기준으로 선택했다(EXP-374와 동일 정책).

## 검증 방법

공용 `data/splits/stratified_5fold_seed42.csv`(seed 42, 5-fold)를 사용했고,
파생 열은 fold와 무관한 stateless 계산(모든 유전자 컬럼과 15개 목록이 fold
train/valid/test 어디서나 동일하게 대회 CSV에서만 계산됨)이라 fold-train
전용 fit이 필요 없다. test·validation 라벨이나 분포는 목록·공식 정의에
사용하지 않았다.

## 사전 점검 (Required pre-check)

- **유전자 존재 확인**: `data/raw/train.csv`에서 15개 유전자 모두 실제
  컬럼으로 존재했고 zero-variance가 아니었다(각 254~643개 샘플에서 변이
  관찰). 상세는 아래 표.
- **의미 중복 확인**: 실행 중 fold 0에서
  `find_semantically_equivalent_features`로 새 2개 열을 base feature 전체 +
  EXP-374 pathway family 출력 전체와 비교했다. 결과: **중복 없음**
  (`[EXP-517 semantic-duplication check] fold=0 duplicates found: none`).
  두 파생 열은 기존 어떤 열과도 byte-level로 같지 않았다.

| 유전자 | train 변이 샘플 수 | WT | missing |
|---|---:|---:|---:|
| RYR2 | 643 | 5558 | 0 |
| SYNE1 | 642 | 5559 | 0 |
| PCLO | 593 | 5608 | 0 |
| DST | 393 | 5808 | 0 |
| SPTA1 | 461 | 5740 | 0 |
| DMD | 406 | 5795 | 0 |
| PKHD1 | 360 | 5841 | 0 |
| COL11A1 | 292 | 5909 | 0 |
| COL6A3 | 347 | 5854 | 0 |
| COL12A1 | 271 | 5930 | 0 |
| MYH2 | 296 | 5905 | 0 |
| RYR1 | 473 | 5728 | 0 |
| AHNAK | 349 | 5852 | 0 |
| VWF | 255 | 5946 | 0 |
| PDE4DIP | 275 | 5926 | 0 |

## 실제 결과

| 지표 | EXP-517 | EXP-374 | 변화 | 게이트 |
|---|---:|---:|---:|---|
| OOF Macro F1 | 0.4239028776 | 0.4267909268 | **-0.0028880493** | ≥+0.001 필요 → **미달** |
| Fold 평균 | 0.4236451946 | 0.4266436967 | -0.0029985021 | - |
| Fold 표준편차 | 0.0095581646 | 0.0085032169 | +0.0010549477 | <+0.002 악화 → 통과 |
| Accuracy | 0.4110627318 | 0.4128366393 | -0.0017739074 | - |
| Log Loss | 1.8482506275 | 1.8440648317 | +0.0041857958 | 소폭 악화, "크게 악화"는 아님 |

Fold Macro F1: `0.4219458 / 0.4218129 / 0.4102359 / 0.4241395 / 0.4400919`
(EXP-374: `0.4243902 / 0.4214467 / 0.4201172 / 0.4239069 / 0.4433575`) — 5개
fold 중 3개(fold 0, 2, 4)에서 EXP-374보다 낮고 2개(fold 1, 3)에서 근소하게
높거나 비슷했다. 선택 iteration: `205 / 190 / 135 / 166 / 183`.

### 클래스별 F1 변화 (EXP-517 − EXP-374)

가장 크게 악화된 클래스: BLCA `-0.0362`, DLBC `-0.0357`, PAAD `-0.0194`,
OV `-0.0194`, **LUSC `-0.0175`**, SARC `-0.0174`. `-0.05` 이상 붕괴한 클래스는
없었다(gate 통과). 가장 크게 개선된 클래스: LAML `+0.0303`, LIHC `+0.0260`,
PCPG `+0.0115`, TGCT `+0.0105`, THCA `+0.0097`.

### LUSC/STES (원래 가설 대상 혼동쌍)

| 클래스 | EXP-374 F1 | EXP-517 F1 | 변화 |
|---|---:|---:|---:|
| LUSC | 0.4752 | 0.4577 | **-0.0175** |
| STES | 0.4270 | 0.4304 | **+0.0034** |

가설은 이 15개 장유전자의 passenger 신호를 분리하면 LUSC↔STES 같은 무관한
혼동쌍의 잡음이 줄어 두 클래스 F1이 함께 개선될 것으로 예상했다. 실제로는
STES만 미미하게 개선됐고 LUSC는 오히려 악화됐다 — 두 클래스가 함께
좋아지는 패턴은 관측되지 않았다.

## 해석과 한계

- 이번 실패는 이전 5건(EXP-188/189/190/192/355/359/496)과 실패 메커니즘이
  다르다. 기존 열을 전혀 삭제하지 않았는데도 OOF Macro F1이 개선되지
  않았다는 점에서, "컬럼 제거로 인한 정보 손실"이 이전 실패들의 유일한
  원인이 아니었거나, 최소한 이번에 시도한 passenger burden 신호 자체가
  현재 XGBoost + EXP-374 피처 조합에서는 추가 예측력을 주지 못한다는 것을
  보여준다.
- 두 파생 열은 기존 `sample__mutated_gene_count_log1p` 등 burden 계열
  피처와 상관이 높을 가능성이 있다(둘 다 "총 변이 유전자 수"에서 파생).
  트리 기반 모델에서 상관된 파생 신호가 오히려 분할 경쟁을 늘려 과적합
  경향을 소폭 키웠을 가능성을 배제할 수 없다(Log Loss·fold std 소폭 악화와
  일치하는 방향).
- 15개 유전자는 여전히 원본 `GENE__mutated` 컬럼으로 각각 남아 있어 모델이
  그 정보를 잃지는 않았다. 이번 실험은 "그 정보를 요약한 새 신호"가
  독립적으로 도움이 되는지를 검증했고, 이번 모델·설정에서는 도움이 되지
  않는다는 결론이다.

## 다음 실험 후보

- 이 저장소는 이미 컬럼 제거/대체 계열(5건)과 순수 추가 계열(EXP-517, 이번
  실험)에서 모두 이 특정 방향(장유전자 passenger burden 요약)의 개선을
  확인하지 못했다. 같은 15개 유전자 목록을 다른 방식(예: 개별 GENE 열의
  가중치를 낮추는 학습 단계 조정, 또는 모델 자체의 정규화)으로 다루는 실험은
  새 Issue에서 가설을 분명히 하고 시도해야 한다.
- 파생 burden 신호 자체가 도움이 되는지 더 알고 싶다면, LightGBM/CatBoost 등
  트리 분할 방식이 다른 모델에서 같은 2개 열을 다양성 컴포넌트로 재평가하는
  것도 고려할 수 있다(단독 채택이 아니라 EXP-449/459 스타일의 블렌드 후보
  탐색용).

## 재현과 관련 파일

- Config: `configs/exp517_passenger_adjusted_burden.yaml`
- Resolved config: `reproducibility/exp517_passenger_adjusted_burden/config.resolved.yaml`
- Runner: `scripts/run_exp517_passenger_adjusted_burden.py`
- Knowledge: `knowledge/long_gene_passenger_candidates_v1.json`
- Metrics: `reports/exp517_passenger_adjusted_burden/metrics.json`
- Passenger group membership manifest:
  `reports/exp517_passenger_adjusted_burden/passenger_group_membership.json`
- OOF: `oof/exp517_passenger_adjusted_burden.csv`
- Test 확률: `preds/exp517_passenger_adjusted_burden_test_proba.csv`
- Submission: `submissions/exp517_passenger_adjusted_burden.csv` (Public 제출 안 함)
- Source commit: `2734a27c236ce9b16962792ea056a1b7e4426e05`
- 재현 상태: `INFERENCE_VERIFIED` — checkpoint 재추론으로 submission SHA-256
  byte-level 일치(`66467087bb1462533dc3918b3c3042ab72e67b216a8e3843b58f138fb936fa33`),
  test 라벨 100% 일치, 확률 최대 차이 `1.49e-07`
  (`reproducibility/exp517_passenger_adjusted_burden/comparison.json`)

## 판단과 다음 행동

- 사전에 고정한 게이트(OOF Macro F1 +0.001 이상 개선) 미달로 **ARCHIVE**.
- fold std·클래스 붕괴 gate는 통과했지만 주 지표(OOF Macro F1)가 이미
  실패했으므로 채택하지 않는다.
- Public 제출은 하지 않았다(Local gate 미통과 시 제출하지 않는 이 저장소의
  일반적 관례를 따름).
- 이 실험 결과를 본 뒤 유전자 목록이나 파생 공식을 사후에 조정하지 않는다.
