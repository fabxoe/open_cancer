# Fold-safe 유전자 residue-event 집중도 피처

Issue [#560](https://github.com/fabxoe/open_cancer/issues/560)의 일반 Task 구현
보고서다. 이 작업은 모델을 학습하거나 새 점수를 만들지 않는다.

## 목적

같은 유전자에서 변이 사건이 단백질 residue의 특정 구간에 반복해서 몰리는지를
outer-train에서만 학습하고, 환자별 네 개의 저차원 값으로 요약한다. 환자 한 명의
유전자 셀 안에서 계산한 entropy는 대부분 0 또는 1로 포화되므로, 여러 학습
환자에서 관측된 유전자별 분포를 고정 lookup으로 사용한다.

## 고정 정의

- 위치: parser-v4가 `unresolved`/`not_applicable`가 아니며 position-eligible인
  양의 residue만 사용한다. 종료 거리를 모르는 `SDEL133fs` 같은 partial
  frameshift도 양의 anchor 위치가 유효하면 포함한다.
- bin: 1번 residue부터 고정 폭 50-aa, `bin=(position-1)//50`
- 중복 제거: 한 환자의 같은 유전자·같은 bin은 사건 수와 관계없이 1회
- gene gate: outer-train의 unique patient-gene-bin support 20 이상, bin 2개 이상
- validation/test: outer-train에서 동결한 gene·bin 분포만 lookup
- unseen validation/test bin: train 분포를 확장하지 않고 share 0
- target, validation 분포, test 분포와 Public LB: fit에 사용하지 않음

## 모델에 내보내는 네 피처

1. `sample__residue_concentration_top_bin_hit_fraction`
2. `sample__residue_concentration_mean_observed_bin_share`
3. `sample__residue_concentration_mean_gene_hhi`
4. `sample__residue_concentration_mean_gene_normalized_entropy`

count, max, top-3 mean과 threshold indicator는 이번 버전에 넣지 않는다. 기존 burden과
높은 상관이 확인된 count를 섞지 않고 집중도 자체만 평가하기 위해서다.

## 재현 메타데이터

각 outer fold에서 fitted family의 `metadata()` 또는 `metadata_json()`을 저장하면
다음이 포함된다.

- gate를 통과한 유전자 목록
- 유전자별 patient support, patient-bin support
- bin별 count·share, top bin, HHI, normalized entropy
- gene profile JSON, gene column 순서와 feature 이름의 SHA-256
- fold-train-only fit 및 target/test 미사용 선언

후속 공식 실험 runner는 이 메타데이터를 fold별 checkpoint/manifest에 저장해야 한다.

## 검증 범위

단위 테스트는 patient-gene-bin dedup, target·validation 미사용, unseen bin, 낮은
지원도와 single-bin gene 제외, unresolved/position-ineligible token 제외, metadata
hash 결정을 검증한다.

후속 모델 실험은 별도 Experiment Issue에서 EXP-527 조건에 이 네 피처만 추가하여
canonical 5-fold Macro F1로 평가한다.
