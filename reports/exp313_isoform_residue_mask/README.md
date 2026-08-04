# EXP-313 Ensembl 신뢰도 기반 residue-position mask

## 결론

Ensembl release 116의 고정 protein isoform sequence와 reference amino-acid가
일치하지 않는 token을 **residue-position 집계에서만** 제외하자 EXP-229 대비
OOF Macro F1이 `+0.0038023523` 개선됐다. fold 표준편차와 Log Loss도 함께
개선됐고, 저장 checkpoint 추론으로 제출 CSV가 동일하게 재생성됐다.

따라서 이 mask를 residue-position family의 채택 후보로 유지한다. 다만 외부
annotation을 사용하므로 최종 대표 모델에 포함하기 전 대회 규정 확인과 독립
재학습 검증은 별도로 필요하다.

## 실험 설계

- Issue: [#313](https://github.com/fabxoe/open_cancer/issues/313)
- 부모: EXP-229
- split: canonical stratified 5-fold, seed 42
- 모델·가중치·checkpoint 정책·pathway·hotspot: EXP-229와 동일
- 유일한 변경: max residue-position에 포함할 token을 다음처럼 사전 고정
  - 유지: `MANE_MATCH`, `CANONICAL_MATCH`, `OTHER_ISOFORM_MATCH`
  - 제외: `POSITION_VALID_REF_MISMATCH`, `OUTSIDE_ALL_KNOWN_ISOFORMS`,
    `COMPLEX_OR_UNMAPPABLE`
- mutation presence·mutation type·missing·sample aggregate 피처는 그대로 유지
- annotation: Ensembl release 116, GRCh38 GTF와 전체 peptide FASTA
- SUBCLASS, test 분포, Public LB는 범주나 threshold 정의에 사용하지 않음

이 실험은 [Task #311](https://github.com/fabxoe/open_cancer/issues/311)의 팀장
한정 예외 승인을 따른다. snapshot manifest와 compact annotation cache의
SHA-256, 승인 근거 URL은 resolved config와 feature contract에 저장했다.

## 결과

| 지표 | EXP-313 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4267909268 | 0.4229885745 | +0.0038023523 |
| Fold 평균 | 0.4266436967 | 0.4232332489 | +0.0034104477 |
| Fold 표준편차 | 0.0085032169 | 0.0098679649 | -0.0013647481 |
| Accuracy | 0.4128366393 | 0.4125141106 | +0.0003225286 |
| Log Loss | 1.8440648317 | 1.8509613276 | -0.0068964958 |

Fold Macro F1은 `0.4243902 / 0.4214467 / 0.4201172 / 0.4239069 /
0.4433575`다. 가장 큰 클래스 개선은 DLBC `+0.05688`, PAAD `+0.02969`,
BLCA `+0.02834`였고, 가장 큰 하락은 CESC `-0.01556`였다. 단일 소수 클래스의
큰 붕괴는 관찰되지 않았다.

사전 gate인 Macro F1 `+0.001` 이상, fold 표준편차 비악화, Log Loss 비악화를
모두 통과했다. Public LB에는 제출하지 않았다.

## 재현성과 산출물

- Config: `configs/exp313_isoform_residue_mask.yaml`
- Runner: `scripts/run_exp313_isoform_residue_mask.py`
- Metrics: `reports/exp313_isoform_residue_mask/metrics.json`
- OOF: `oof/exp313_isoform_residue_mask.csv`
- test 확률: `preds/exp313_isoform_residue_mask_test_proba.csv`
- submission: `submissions/exp313_isoform_residue_mask.csv`
- reproducibility: `reproducibility/exp313_isoform_residue_mask/`
- 실행 source commit: `f8a9c30c5b2b34014e05b64c61b0eb27fa0e4636`
- 재현 상태: `INFERENCE_VERIFIED`
- 제출 SHA-256: `e04636cc64c56cf7ed2bffea9b93b84305973e8e808ce00f6f022f5bf036761f`

저장 checkpoint 재추론 결과 test label 일치율은 100%, 확률 최대 절대차는
`1.83e-7`, 제출 CSV SHA-256은 원본과 동일했다. `TRAINING_VERIFIED`는 아직
수행하지 않았다.

## 해석과 다음 단계

이 결과는 원시 residue 위치가 모두 같은 의미를 갖는다는 가정보다, 알려진
protein sequence로 설명 가능한 위치만 사용하는 편이 현재 OOF에서 더 안정적임을
보여준다. 그러나 competition token에 transcript ID가 없으므로 실제 종양에서
어떤 isoform이 발현됐는지를 증명한 결과는 아니다.

후속 B2-2 sample 범주 요약과 B2-3 isoform-relative bin은 이 결과와 섞지 않고
각각 별도 Issue·EXP-ID에서 한 변수씩 검증한다. EXP-313의 OOF나 Public 결과를
보고 범주·threshold를 재조정하지 않는다.
