# EXP-652 ordinary range_replacement gene indicator on EXP-527

## 결론

EXP-527(class-cosine leave-one-out XGBoost)을 고정 부모로 두고, 이미
EXP-409에서 구현된 fold-safe `gene__<gene>__range_replacement_any`
indicator(`src/open_cancer/range_replacement_features.py`, 코드 변경 없음)를
그대로 추가했다. OOF Macro F1은 `0.4481375742`로 부모보다
`+0.0012653035` 개선돼 채택 gate(`≥0.001`)를 통과했다. fold 표준편차는
`0.0028157608`로 부모(`0.0063793185`)보다 크게 개선됐고 어떤 클래스도
`-0.05` 붕괴가 없었다(최대 하락 PAAD `-0.0392`, HNSC `-0.0374`). Log Loss는
`+0.0177605152` 소폭 악화했다. 종합적으로 `ADOPT_WITH_CAUTION`으로 보존하고,
Public 제출 여부는 test-like subset 점검 후 별도 결정한다.

같은 feature family를 더 약한 부모 EXP-369(isoform mask·class-cosine
이전)에 얹은 EXP-409는 Macro F1 `+0.0019418`이지만 Log Loss
`+0.1327703`(큰 악화)로 ARCHIVE됐다. EXP-527을 부모로 하면 Log Loss 악화가
`+0.0178`로 EXP-409의 약 7분의 1 수준으로 훨씬 작아졌다 — class-cosine
26-feature가 이미 있는 상태에서는 같은 feature가 다르게(더 안정적으로)
상호작용한다는 뜻이다.

## 실험 계약

- Issue/브랜치: #652 / `issue-652-range-replacement-any-exp527`
- 부모: EXP-527
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 부모의 parser·isoform mask·class-cosine·XGBoost 설정 고정
- 유일한 변경: outer-train에서 관측한 ordinary `range_replacement`
  (train 101 samples, #410 subtype correction 반영) gene indicator 추가,
  구현은 EXP-409와 완전히 동일(재사용, 신규 코드 없음)
- stop-containing/synonymous/stop_gain range, deletion/insertion/delins는
  포함하지 않음(train 지원 부족으로 `ANALYSIS_ONLY`, 별도 계약)
- SUBCLASS·test 분포·Public LB는 feature 정의에 사용하지 않음

## 결과

| 지표 | EXP-652 | EXP-527 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4481375742 | 0.4468722707 | +0.0012653035 |
| Fold 평균 | 0.4485303544 | 0.4469900880 | +0.0015402665 |
| Fold 표준편차 | 0.0028157608 | 0.0063793185 | -0.0035635578 |
| Accuracy | 0.4342847928 | 0.4339622642 | +0.0003225286 |
| Log Loss | 2.0452492237 | 2.0274887085 | +0.0177605152 |

Fold Macro F1은 `0.4430446 / 0.4493344 / 0.4492650 / 0.4499687 /
0.4510391`이다. fold별 선택 iteration은 `220 / 92 / 19 / 32 / 21`로,
fold 2는 iteration 19에서 조기 수렴해 log loss(`2.2886`)가 다른 fold보다
뚜렷이 높다 — checkpoint 선택이 macro F1 기준이라 log loss 악화 일부는
이 fold의 조기 수렴에서 온다.

fold-safe 후보 유전자 수는 `87 / 81 / 75 / 75 / 79`개였다(전체 train
기준으로는 98개).

클래스별 최대 개선은 ACC `+0.0730`, LUAD `+0.0398`, LIHC `+0.0383`이며
최대 하락은 PAAD `-0.0392`, HNSC `-0.0374`, PCPG `-0.0259`다. 개선·하락이
섞여 있고 어느 방향도 `-0.05`를 넘지 않는다.

## Test 영향

EXP-527 대비 2,546개 test 행 전부에서 적어도 하나의 확률이 `1e-6`보다
크게 바뀌었고, argmax는 `281/2,546`행(11.0%)에서 바뀌었다. 평균 절대
확률 차이는 `0.0036632862`, 최대 차이는 `0.13092174`, 전체 확률 상관은
`0.99194`다.

## 재현성

- Config: `configs/exp652_range_replacement_any_exp527.yaml`
- Runner: `scripts/run_exp652_range_replacement_any_exp527.py`
- Metrics: `reports/exp652_range_replacement_any_exp527/metrics.json`
- OOF: `oof/exp652_range_replacement_any_exp527.csv`
- test 확률: `preds/exp652_range_replacement_any_exp527_test_proba.csv`
- submission: `submissions/exp652_range_replacement_any_exp527.csv`
- submission SHA-256:
  `b24b3c81ed0771be682952000bd700e892aa0d96202cf94c81d96459e6495a1f`
- 재현 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론: submission byte-level 일치, test 라벨 100%, 확률 최대
  차이 `1.23e-7`

## 판단과 다음 행동

- Macro F1 gate·fold 안정성 gate·클래스 안정성 gate 통과, Log Loss만 소폭
  악화: `ADOPT_WITH_CAUTION`.
- 최근 Local-Public 격차 조사(EXP-628 Public 제출 실패 사례) 이후 팀은
  Local gate 통과만으로 바로 제출하지 않기로 했다. Public 제출 전
  `reports/analysis/adversarial_validation/train_domain_propensity.csv`
  기반 test-like subset 점수를 별도로 확인한다.
- EXP-527을 폐기하지 않고 두 후보를 함께 보존한다.
- Public 결과를 보고 parser 의미나 feature 범위를 역조정하지 않는다.
