# EXP-409 ordinary range-replacement gene indicator

## 결론

EXP-369의 stop 표기 정규화·피처·모델·fold·seed를 유지하고, parser v4가
ordinary range replacement로 확정한 사건의 유전자별 존재 indicator만
추가했다. OOF Macro F1은 `0.4249303829`로 부모보다 `+0.0019418083`
개선됐다. 그러나 fold 표준편차가 `+0.0023141270`, Log Loss가
`+0.1327702999` 악화되어 사전 안정성 gate를 통과하지 못했다.

따라서 ordinary range 의미에는 분별 신호가 있다는 근거는 남았지만 현재의
희소 gene-level adapter는 `ARCHIVE`한다. Public 제출이나 threshold·유전자
재선택은 하지 않는다.

## 실험 계약

- Issue/브랜치: #409 / `issue-409-exp-range-replacement`
- 부모: EXP-369
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 모델·하이퍼파라미터·balanced sample weight·Macro-F1 checkpoint 정책 고정
- 기존 generic complex와 EXP-369의 stop 정규화 피처를 모두 유지
- 유일한 추가: outer-train에서 관측된 유전자별
  `gene__<GENE>__range_replacement_any`
- 포함: ordinary range replacement
- 제외: synonymous range, immediate/non-immediate stop-containing range,
  unresolved route
- 기존 base·pathway 피처와 outer-train 값이 byte-equivalent인 후보는 해당
  fold에서 제거
- target·validation·test·Public LB는 gene 선택과 의미 규칙에 사용하지 않음

## #407·#410 지원도 근거

초기 #407 집계에서 non-immediate stop-containing range가 ordinary와 섞인
문제를 #410에서 먼저 수정했다.

- ordinary: train 101 samples, folds `11/22/23/24/21`
- stop-containing: train 34 samples, folds `9/7/8/2/8` → 분석 전용
- synonymous: train 47 samples → 분석 전용
- immediate stop-gain: train 23 samples → 분석 전용

EXP-409는 ordinary 101명 집합만 의미 adapter에 사용했다.

## 결과

| 지표 | EXP-409 | EXP-369 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4249303829 | 0.4229885745 | +0.0019418083 |
| Fold 평균 | 0.4260754480 | 0.4232332489 | +0.0028421991 |
| Fold 표준편차 | 0.0121820920 | 0.0098679649 | +0.0023141270 |
| Accuracy | 0.4141267537 | 0.4125141106 | +0.0016126431 |
| Log Loss | 1.9837316275 | 1.8509613276 | +0.1327702999 |

Fold Macro F1은 `0.4254629 / 0.4196702 / 0.4140081 / 0.4219639 /
0.4492722`였다. 선택 iteration은 `130 / 54 / 291 / 18 / 146`으로 fold 1과
3에서 매우 이른 checkpoint가 선택됐고, 특히 fold 3 Log Loss가 `2.36138`로
악화됐다.

## 실제 신규 피처와 중복 감사

outer-train에서 관측된 후보 대부분은 기존 유전자별 generic complex와 완전히
같았다. semantic-equivalence filter 후 실제 남은 신규 피처 수는 fold별
`2 / 1 / 3 / 3 / 3`개뿐이었다. 제거된 후보는 `85 / 80 / 72 / 72 / 76`개다.

남은 유전자는 fold에 따라 `CYB5B`, `ICA1`, `RELN`, `EPHA5`, `L3MBTL4`
일부였다. 즉 개선은 range family 전체를 안정적으로 표현했다기보다, fold마다
달라지는 극소수 희소 잔여 열의 영향일 가능성이 높다.

클래스별로 KIRC `+0.08284`, LGG `+0.07096`이 개선됐지만 STES
`-0.04125`, SARC `-0.03238`, LUAD `-0.02134`가 하락했다. 단일 클래스
`-0.05` 붕괴는 없지만 방향이 넓게 일관되지는 않았다.

EXP-369 대비 test argmax는 165/2,546행, OOF argmax는 792/6,201행에서
달랐다. OOF 확률 상관은 `0.95263`이다. 다양성은 있으나 안정성 gate 실패를
뒤집는 채택 근거로 사용하지 않는다.

## 재현성

- 소스 commit: `7519b8e0dfa8e6b2c2e49d1b1ee4e7f54bc0c412`
- Config: `configs/exp409_ordinary_range_replacement_indicator.yaml`
- Runner: `scripts/run_exp409_ordinary_range_replacement_indicator.py`
- Metrics: `reports/exp409_ordinary_range_replacement_indicator/metrics.json`
- OOF: `oof/exp409_ordinary_range_replacement_indicator.csv`
- test 확률: `preds/exp409_ordinary_range_replacement_indicator_test_proba.csv`
- submission: `submissions/exp409_ordinary_range_replacement_indicator.csv`
- submission SHA-256:
  `8b15d5c1d4906e676932e0e59e848f630aaf2530020a41c7e4453e26594eb3ea`
- 재현 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론: submission SHA-256 byte-level 일치, test 라벨 100%,
  확률 최대 차이 `1.48e-7`

## 판단과 다음 행동

- 성능 하한은 통과했지만 fold 표준편차와 Log Loss gate에 실패해 `ARCHIVE`.
- Public 제출 및 ordinary range threshold·gene 재선택은 중단한다.
- parser v4 의미 계약과 ordinary/stop-containing 분리는 유지한다.
- 다음 parser family는 충분한 train support가 새로 확인되기 전까지 모델에
  연결하지 않고 QC·annotation coverage 자산으로만 보존한다.
