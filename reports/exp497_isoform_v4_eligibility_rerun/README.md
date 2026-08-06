# EXP-497 N6 isoform eligibility 수정 반영 EXP-374/392 재실행

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-497 / #497 |
| 목적 | Issue #493(N6)/PR #495가 isoform substitution eligibility 판정을 legacy 정규식에서 parser v4로 교체(486,399 고유 (gene, token)쌍 중 10,397건(2.14%) 재분류)한 뒤, 이 수정이 EXP-374/392 lineage의 OOF에 실제로 영향을 주는지 측정 |
| 핵심 입력 | EXP-374/EXP-392와 동일 데이터·피처 스펙, isoform 라이브러리 코드만 PR #495 반영 |
| 모델 | XGBoost(EXP-374/392와 동일 하이퍼파라미터, 5-fold seed 42) |
| Local OOF Macro F1 | 0.4267909268459148 (official, EXP-374 재실행) / 0.42904318881178166 (ablation, EXP-392 재실행) — 둘 다 부모와 bit-identical |
| Public LB | 미제출 |
| 판단 | `NULL_RESULT` — correctness 수정은 유효하나 이 lineage 성능엔 영향 없음, EXP-374/392 그대로 유지 |

## 원본 데이터와 입력

train 6,201행·test 2,546행, 유전자 4,384개 mutation 표기. EXP-374/392와 완전히 동일한 원본 CSV·split(`data/splits/stratified_5fold_seed42.csv`)을 사용했다.

## 핵심 개념과 피처

`residue_position` 피처(유전자별 `max` 잔기 위치 집계)는 각 토큰이 Ensembl release 116 isoform 주석과 매칭돼 "trusted"(`CANONICAL_MATCH`/`MANE_MATCH`/`OTHER_ISOFORM_MATCH`)로 분류돼야만 값에 반영되고, "masked"(`COMPLEX_OR_UNMAPPABLE`/`OUTSIDE_ALL_KNOWN_ISOFORMS`/`POSITION_VALID_REF_MISMATCH`)로 분류되면 무시된다. N6은 이 trusted/masked 판정 로직 자체를 legacy 정규식에서 parser v4로 교체했다 — feature config는 한 글자도 바꾸지 않았다.

## 모델이 학습하는 정보

EXP-374/392와 완전히 동일: mutation-type presence, robust aggregates, residue-position(isoform mask 포함), pathway burden/composition, hotspot-34. 유일한 차이는 위 isoform trusted/masked 판정 로직이 실행 시점에 참조하는 라이브러리 코드뿐이다.

## 검증 방법

`configs/exp497_isoform_v4_eligibility_rerun.yaml`(official, EXP-374 파생)과 `configs/exp497_exp392_isoform_v4_rerun.yaml`(exploratory_ablation, EXP-392 파생) 두 config를 각각 실행해 부모의 `metrics.json`을 `comparison_metrics_path`로 지정, 프레임워크 자체 재현성 체크가 OOF·confusion matrix·제출 SHA-256을 부모와 직접 비교하도록 했다.

## 실제 결과

- Official(EXP-374 재실행): fold Macro F1 `0.4243902235533087, 0.4214466889609302, 0.4201172028781823, 0.4239068711010362, 0.4433574969593849` / OOF `0.4267909268459148` / fold std `0.008503216870558973` / Accuracy `0.4128366392517336` / Log Loss `1.8440648317337036` — EXP-374 원본 값과 소수점까지 완전히 동일.
- Ablation(EXP-392 재실행): fold Macro F1 `0.42849928115662944, 0.41983280610483015, 0.42384727637558295, 0.42615124142489225, 0.44656525053560464` / OOF `0.42904318881178166` — EXP-392 원본 값과 완전히 동일.
- 두 실행 모두 confusion matrix, per-class F1, 제출 SHA-256이 부모와 byte-level로 일치(`reproducibility/exp497_*/comparison.json`, `submission_sha256_match: true`).
- 코드가 실제로 수정된 버전을 로드했는지 별도 확인: worktree venv가 `resolve_substitution_eligibility` 함수를 포함한 수정된 `isoform_semantics.py`를 정확히 import함을 확인(캐시/구버전 오독 아님).

## 해석과 한계

10,397건(2.14%) 재분류가 실제 값에 반영되려면 재분류된 토큰이 해당 (sample, gene) 조합에서 다른 trusted 토큰보다 큰 잔기 위치값을 가져야 하는데, 이 데이터셋에는 그런 경우가 하나도 없었던 것으로 보인다(`max` 집계의 특성상 이미 더 큰 값을 가진 trusted 토큰이 같은 유전자에 존재하면 새로 trusted된 토큰은 값을 바꾸지 못한다). 즉 이 결과는 N6 수정이 틀렸다는 뜻이 아니라 **이 특정 집계 방식(gene-level max)이 그 수정의 영향을 표현하지 못한다**는 뜻이다. correctness 관점에서는 N6 수정을 유지해야 한다(감사 결과 자체는 legacy가 `X` stop 표기를 놓치고 있었다는 명백한 버그였음).

## 다음 실험 후보

- `max`가 아닌 다른 집계(`count`, `mean`, presence indicator 등)로 재분류 효과가 드러나는지 별도 ablation
- N7(driver 재검증)로 진행 — 로드맵 §12 순서상 다음 단계이며 이 lineage와는 별개 축

## 재현과 관련 파일

- Config: `reproducibility/exp497_isoform_v4_eligibility_rerun/config.resolved.yaml`
- Metrics: `reports/exp497_isoform_v4_eligibility_rerun/metrics.json`
- Submission: `submissions/exp497_isoform_v4_eligibility_rerun.csv`
- Ablation(EXP-392 재실행) metrics: `reports/exp497_exp392_isoform_v4_rerun/metrics.json`
- Source commit: `16c1e7346af6550c722a971b573a8a775336db58`(official) / `10adb8e4414770ffbcfb58b7b26df01170fd3f9d`(ablation)
- Reproduction status: `INFERENCE_VERIFIED`(둘 다 — `reproducibility/exp497_isoform_v4_eligibility_rerun/comparison.json`, `reproducibility/exp497_exp392_isoform_v4_rerun/comparison.json`)
