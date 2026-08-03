# EXP-302 고정 관찰 가능 암종 표지 mutation proxy

## 결론

일반 임상 문헌에서 자주 언급되는 암종별 표지 유전자 목록을 대회 입력에서
직접 관찰할 수 있는 **단백질 변이 proxy**로만 제한해 EXP-229에 추가했습니다.
OOF Macro F1은 **0.4212799841**로 부모 EXP-229보다 `-0.0017085904`
낮아 사전 채택 기준을 통과하지 못했습니다. 따라서 이 피처 묶음은
`ARCHIVE`하며 Public LB에 제출하지 않습니다.

다만 Log Loss는 `-0.0100498199`, fold 표준편차는 `-0.0004459216`
개선됐습니다. 작은 고정 패널이 확률 분포를 일부 안정화했을 가능성은 있지만,
대회 공식 지표인 Macro F1을 개선했다는 근거는 아닙니다. Public 결과를 보고
패널·임계값·가중치를 다시 조정하지 않습니다.

## 질문과 실험 설계

검증한 질문은 다음 하나입니다.

> 공개 문헌에서 사전에 고정한 암종별 표지 유전자 집합을 작은 이진 mutation
> proxy로 요약하면 EXP-229의 암종 분류 성능을 개선하는가?

부모의 canonical split, XGBoost 하이퍼파라미터, balanced sample weight,
Macro-F1-best checkpoint 정책과 클래스 순서를 유지했습니다. 변경점은 아래
20개 후보 피처뿐입니다.

각 패널마다 다음 네 값을 만들었습니다.

- `any_mutated`
- `any_nonsynonymous`
- `any_lof`
- `multi_gene_mutated`

패널은 lung, breast, colorectal, ovarian, bladder의 다섯 묶음입니다. 실제
4,384개 패널에는 `KRAS`, `NRAS`, `MSH6`가 없어 계산에서 자동 제외됐습니다.
최종 교집합은 다음과 같습니다.

| 패널 | 대회 입력에서 실제 사용된 유전자 |
|---|---|
| lung | `EGFR`, `BRAF` |
| breast | `BRCA1`, `BRCA2`, `ERBB2`, `PIK3CA` |
| colorectal | `BRAF`, `MLH1`, `MSH2`, `PMS2` |
| ovarian | `BRCA1`, `BRCA2` |
| bladder | `FGFR3` |

## 임상적 해석의 경계

이 실험은 임상 바이오마커 판정이 아닙니다. 대회 CSV에는 fusion,
copy-number/amplification, 발현, IHC, MSI assay, germline/somatic 구분과
transcript ID가 없습니다. 따라서 다음을 계산하거나 주장하지 않았습니다.

- `ALK`, `ROS1`, `NTRK` fusion
- HER2 amplification 또는 IHC 상태
- MSI-H 또는 dMMR 진단
- 유전성 암 위험과 germline carrier 상태
- 치료 적응증 또는 약물 반응

`BRCA1/2`, `ERBB2`, MMR gene 등의 이름은 고정 패널의 출처일 뿐이며, 모델
입력은 해당 열에 관찰된 단백질 변이 문자열의 존재·유형을 요약한 proxy입니다.

## fold-safe 중복·희소도 처리

각 outer-fold의 train 행에서만 후보를 기존 EXP-229 피처와 비교했습니다.

- bladder `any_mutated`는 기존 `FGFR3__mutated`와 완전히 같아 모든 fold에서 제거
- bladder `multi_gene_mutated`는 단일 유전자 패널이라 상수 0으로 모든 fold에서 제거
- fold 2에서는 bladder `any_lof`도 기존 `FGFR3__frameshift`와 같아 추가 제거
- 양성 수 5 미만 후보는 없었음
- 최종 유지 후보 수: `18 / 18 / 17 / 18 / 18`

validation과 test는 outer-train에서 결정한 동일 mask만 적용했습니다. 전체
세부 대응 관계와 feature hash는
[`feature_audit.json`](feature_audit.json)에 저장했습니다.

## 결과

| 항목 | EXP-302 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4212799841 | 0.4229885745 | -0.0017085904 |
| Fold 표준편차 | 0.0094220433 | 0.0098679649 | -0.0004459216 |
| Accuracy | 0.4089662958 | 0.4125141106 | -0.0035478149 |
| Log Loss | 1.8409115076 | 1.8509613276 | -0.0100498199 |

| Fold | EXP-302 | EXP-229 | 변화 |
|---:|---:|---:|---:|
| 0 | 0.4127412855 | 0.4125153614 | +0.0002259241 |
| 1 | 0.4228720327 | 0.4227302800 | +0.0001417527 |
| 2 | 0.4153153863 | 0.4172366349 | -0.0019212486 |
| 3 | 0.4167496415 | 0.4221575240 | -0.0054078825 |
| 4 | 0.4389531503 | 0.4415264445 | -0.0025732942 |

클래스별 큰 개선은 BLCA `+0.0398380355`, PCPG `+0.0180412487`, PAAD
`+0.0112517581`이었습니다. 큰 하락은 LUAD `-0.0235035246`, UCEC
`-0.0229704856`, KIRC `-0.0210731639`이었습니다. 어떤 클래스도 사전 붕괴
기준 `-0.05`를 넘지는 않았지만 전체 Macro F1 gate가 실패했습니다.

## 무엇을 새롭게 알았나

1. 캡처 수준의 일반 임상 표지 목록도 관찰 가능한 사건으로 엄격히 번역하면
   누출 없이 실험할 수 있습니다.
2. 하지만 작은 암종 이름 패널을 그대로 집계한 v1은 EXP-229보다 추가적인
   암종 구분 신호를 주지 못했습니다.
3. 단일 유전자 패널은 기존 gene-level 피처와 쉽게 중복됩니다. 앞으로 외부
   지식 피처는 “유명한 유전자 포함”보다 입력에 없는 구조적 의미를 제공하는지
   먼저 감사해야 합니다.
4. Track A가 기각됐으므로 Track B isoform 의미 QC는 독립 분석으로 진행하되,
   두 트랙을 합친 조합 실험은 열지 않습니다.

## 재현성과 산출물

- Issue: [#302](https://github.com/fabxoe/open_cancer/issues/302)
- PR: [#305](https://github.com/fabxoe/open_cancer/pull/305)
- 실행 source commit: `6f6094a28fe5f1f6ae0b710df5c3f6b8c8cc3db3`
- finalize 보강 commit: `f90855d`
- Config: `configs/exp302_observable_marker_proxies.yaml`
- Runner: `scripts/run_exp302_observable_marker_proxies.py`
- Metrics: `reports/exp302_observable_marker_proxies/metrics.json`
- Feature audit: `reports/exp302_observable_marker_proxies/feature_audit.json`
- Reproduction: `reproducibility/exp302_observable_marker_proxies/`
- 실행 시간: 777.12초
- Public LB: 미제출
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint에서 fold별 test 피처를 다시 구성해 제출 파일을 재생성했습니다.
원본과 재생성 submission SHA-256이
`45ee719653d1458f0aa04df37c13c633f19cdf2104860e00a3fe3e92171c9a28`로
byte-level 일치했고, test label 일치율은 100%, 확률 최대 절대 차이는
`1.34e-7`이었습니다.
