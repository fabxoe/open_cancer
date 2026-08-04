# EXP-392 range stop/no-change gene indicators

## 결론

EXP-374의 stop 정규화·Ensembl residue mask·모델 설정을 고정하고,
`range_stop`과 `range_no_change`의 유전자별 presence indicator만 추가했다.
OOF Macro F1은 `0.4290431888`로 부모보다 `+0.0022522620` 개선됐다.
fold 표준편차 증가는 `+0.0007432961`로 제한 이내이고 어떤 클래스도
`-0.05` 붕괴가 없었다. Log Loss는 `+0.0032364130` 소폭 악화했으나 명백한
붕괴로 보기는 어렵다. 따라서 `ADOPT_WITH_CAUTION`으로 보존하며 Public 제출은
팀 후보·남은 횟수를 확인한 뒤 수동 결정한다.

## 실험 계약

- Issue/브랜치: #392 / `issue-392-exp-range-stop-no-change`
- 부모: EXP-374
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 부모의 stop parser·Ensembl release 116 mask·pathway·hotspot·XGBoost 고정
- 유일한 변경: outer-train에서 관측한 `gene__*__range_stop_any`와
  `gene__*__range_no_change_any` 후보 추가
- 기존 피처와 outer-train 값이 완전히 같은 후보는 제거
- SUBCLASS·test prevalence·Public LB는 feature 정의에 사용하지 않음

## 결과

| 지표 | EXP-392 | EXP-374 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4290431888 | 0.4267909268 | +0.0022522620 |
| Fold 평균 | 0.4289791711 | 0.4266436967 | +0.0023354744 |
| Fold 표준편차 | 0.0092465129 | 0.0085032169 | +0.0007432961 |
| Accuracy | 0.4134816965 | 0.4128366393 | +0.0006450572 |
| Log Loss | 1.8473012447 | 1.8440648317 | +0.0032364130 |

Fold Macro F1은 `0.4284993 / 0.4198328 / 0.4238473 / 0.4261512 /
0.4465653`이다. 클래스별 최대 개선은 CESC `+0.02300`, PCPG `+0.02075`,
DLBC `+0.01720`이며 최대 하락은 LUAD `-0.02949`, PAAD `-0.02218`이다.

outer-train semantic-equivalence 제거 후 실제 신규 열은 fold별 `4 / 1 / 2 /
2 / 3`개였다. 제거된 후보는 `90 / 86 / 79 / 97 / 89`개로, 이 결과는
대규모 새 family보다 기존 generic 피처와 겹치지 않는 소수 잔여 신호의 효과다.

## Test 영향

EXP-374 대비 모든 test 행에서 적어도 하나의 확률이 `1e-6`보다 크게 바뀌었고,
argmax는 `121/2,546`행에서 바뀌었다. 평균 절대 확률 차이는
`0.0021866803`, 최대 차이는 `0.10935872`, 전체 확률 상관은 `0.99805`다.

## 재현성

- 소스 commit: `af5a082e709ee5b6ea66befb7710cf18dcedabc6`
- Config: `configs/exp392_range_semantic_indicators.yaml`
- Runner: `scripts/run_exp392_range_semantic_indicators.py`
- Metrics: `reports/exp392_range_semantic_indicators/metrics.json`
- OOF: `oof/exp392_range_semantic_indicators.csv`
- test 확률: `preds/exp392_range_semantic_indicators_test_proba.csv`
- submission: `submissions/exp392_range_semantic_indicators.csv`
- submission SHA-256: `3ee0d16de573a5b25be527e40b8ea5df77ca019618a50584907d339cc17d824d`
- 재현 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론: submission byte-level 일치, test 라벨 100%, 확률 최대
  차이 `1.46e-7`

## 판단

- Macro F1, fold 안정성, 클래스 안정성, inference gate 통과.
- Log Loss가 소폭 악화했으므로 EXP-374를 폐기하지 않고 두 후보를 함께 보존한다.
- 추가 threshold·유전자별 수동 탐색은 하지 않는다.
- Public 결과를 보고 parser 의미나 feature 범위를 역조정하지 않는다.
