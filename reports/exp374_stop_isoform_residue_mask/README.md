# EXP-374 stop 정규화 + Ensembl isoform residue mask

## 결론

EXP-369의 stop 표기 정규화를 유지한 상태에서 Ensembl release 116 semantic
mask를 residue-position 경로에만 적용했다. OOF Macro F1은
`0.4267909268`로 EXP-369보다 `+0.0038023523` 개선됐고, fold 표준편차와
Log Loss도 함께 개선됐다. 모든 사전 Local gate를 통과했으며
`INFERENCE_VERIFIED`다.

EXP-313과는 train 피처·모델이 같아 OOF 확률이 byte-level로 완전히 같다.
그러나 test에서는 stop 정규화 때문에 EXP-313 대비 875행의 확률과 371행의
argmax가 바뀌었다. Public Macro F1은 `0.346215922`로 EXP-369보다
`+0.0054214877` 개선돼 팀 최고를 갱신했다. 즉 Local에서 검증된 isoform
mask와 Public에서 검증된 stop 정규화의 결합이 실제 일반화 개선으로 이어졌다.

## 실험 계약

- Issue/브랜치: #374 / `issue-374-exp-stop-isoform-mask`
- 부모: EXP-369
- canonical stratified 5-fold, seed 42, 26개 클래스 순서 고정
- 모델·하이퍼파라미터·balanced sample weight·Macro-F1 checkpoint 정책 고정
- EXP-369의 `*`/`X`/`Ter` stop 정규화, pathway·hotspot·mutation type 유지
- 유일한 변경: EXP-313의 Ensembl release 116 residue-position semantic mask
- trusted: `CANONICAL_MATCH`, `MANE_MATCH`, `OTHER_ISOFORM_MATCH`
- masked: `COMPLEX_OR_UNMAPPABLE`, `OUTSIDE_ALL_KNOWN_ISOFORMS`,
  `POSITION_VALID_REF_MISMATCH`
- EXP-285 nested Optuna 파라미터는 사용하지 않음
- SUBCLASS·test 분포·Public LB는 mask나 파라미터 정의에 사용하지 않음

## 결과

| 지표 | EXP-374 | EXP-369 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4229885745 | +0.0038023523 |
| Fold 평균 | 0.4266436967 | 0.4232332489 | +0.0034104477 |
| Fold 표준편차 | 0.0085032169 | 0.0098679649 | -0.0013647481 |
| Accuracy | 0.4128366393 | 0.4125141106 | +0.0003225286 |
| Log Loss | 1.8440648317 | 1.8509613276 | -0.0068964958 |

Fold Macro F1은 `0.4243902 / 0.4214467 / 0.4201172 / 0.4239069 /
0.4433575`였다. 선택 iteration은 `187 / 165 / 284 / 131 / 221`이다.

클래스별 최대 개선은 DLBC `+0.05688`, PAAD `+0.02969`, BLCA
`+0.02834`였다. 최대 하락은 CESC `-0.01556`, STES `-0.01185`, PRAD
`-0.01060`으로 어떤 클래스도 `-0.05` 붕괴가 없었다.

## Test 영향 감사

### EXP-369 대비 — mask 효과

- 확률이 `1e-6`보다 크게 바뀐 행: 2,546 / 2,546
- argmax가 바뀐 행: 228 / 2,546
- 평균 절대 확률 차이: `0.0052520251`
- 최대 절대 확률 차이: `0.41710889`
- 전체 확률 상관: `0.98081`

### EXP-313 대비 — stop 정규화 효과

- OOF 확률 최대 차이: 0, OOF argmax 변경: 0
- 확률이 `1e-6`보다 크게 바뀐 test 행: 875 / 2,546
- test argmax가 바뀐 행: 371 / 2,546
- 평균 절대 확률 차이: `0.0068911959`
- 최대 절대 확률 차이: `0.86635927`

EXP-313 대비 차이는 train이나 mask가 아니라 test의 stop 표기 정규화에서만
생긴다. EXP-369 대비 차이는 mask에서 생긴다. 두 비교가 각각 한 축만 바꾸므로
결합 효과의 출처가 분리된다.

## EXP-334 재해석

EXP-334는 Ensembl mask와 EXP-285 fold별 Optuna 파라미터를 함께 사용했고
stop 표기 오염은 남아 있었다. EXP-374는 기본 EXP-369 파라미터에서 mask만
추가해 Local gate를 모두 통과했다. 따라서 EXP-334의 Public 부진을 “isoform
mask 자체의 실패”로 해석할 수 없다. tuned parameter 상호작용과 stop parser
미적용이 함께 섞인 실험이었다는 해석이 더 타당하다.

## 재현성

- 소스 commit: `4a2dfb685859277bd78746e8ab9578ade51a64a7`
- Config: `configs/exp374_stop_isoform_residue_mask.yaml`
- Runner: `scripts/run_exp374_stop_isoform_residue_mask.py`
- Metrics: `reports/exp374_stop_isoform_residue_mask/metrics.json`
- OOF: `oof/exp374_stop_isoform_residue_mask.csv`
- test 확률: `preds/exp374_stop_isoform_residue_mask_test_proba.csv`
- submission: `submissions/exp374_stop_isoform_residue_mask.csv`
- submission SHA-256:
  `6ebae265d36ce5b87748cdb40c412fc9563e64a69c0194d92b43cc1af4e6d006`
- 재현 상태: `INFERENCE_VERIFIED`
- checkpoint 재추론: submission SHA-256 byte-level 일치, test 라벨 100%,
  확률 최대 차이 `1.83e-7`
- Release: [`exp-374-repro-v2`](https://github.com/fabxoe/open_cancer/releases/tag/exp-374-repro-v2)
  (canonical `exp374_stop_isoform_residue_mask` 경로; 기존 v1 asset 보존)

## Public 리더보드

- 제출 ID: `1510884`
- 제출 시각: `2026-08-04 18:29:26 KST`
- Public Macro F1: `0.346215922`
- EXP-369 대비: `+0.0054214877`
- 제출 당시 팀 Public 최고를 갱신했고 대표 제출로 선택했다.

## 판단과 다음 행동

- Local 성능·fold 안정성·Log Loss·클래스 안정성 gate 모두 통과: `ADOPT`.
- EXP-369보다 Public Macro F1도 개선되어 stop 정규화 이후 isoform mask의
  일반화 기여를 확인했다.
- Public 결과를 본 뒤 mask category나 파라미터를 역조정하지 않는다.
