# EXP-245 암종별 핵심 변이 패턴 확장

## 결론

EXP-229에 8개 암종의 문헌 고정 mutation-mechanism proxy 32개를 추가한 결과,
OOF Macro F1은 **0.4213989560**입니다. 단순 조합을 사용한 EXP-240보다는
`+0.0024345095` 개선됐지만, 비교 기준 EXP-229보다는 `-0.0015896185`
낮아 **ARCHIVE**합니다.

Accuracy와 fold 안정성은 개선됐지만 Log Loss가 `+0.1756390333` 크게
악화됐습니다. 일부 클래스의 큰 양의 변화와 음의 변화가 동시에 나타나, 전체
제출 후보로 채택하거나 현재 canonical OOF를 보고 유리한 암종 모듈만 고정
선택하지 않습니다.

## 무엇을 추가했나

유방암, 난소암, 전립선암, 갑상선암, 방광암, 간암, 자궁경부암, 두경부암의
TCGA 1차 문헌에서 고정한 유전자 그룹마다 다음 4개 피처를 계산했습니다.

- missense가 관찰된 signal 유전자 수
- nonsense/frameshift가 관찰된 LoF signal 유전자 수
- 문헌 관련 유전자 중 변이된 유전자 수
- missense signal과 LoF signal이 함께 관찰됐는지

이 값은 변이 종류에 따른 **proxy**입니다. 실제 활성화, 병원성, biallelic loss,
발현 변화, 증폭 또는 fusion을 관측했다고 해석하지 않습니다. 모든 샘플 값은
대회 CSV에서만 계산했고 외부 환자 데이터, SUBCLASS, train label, 관측 빈도,
test 분포 및 Public LB는 피처 정의에 사용하지 않았습니다.

32개 후보 중 난소암 missense count는 모든 fold에서 기존 `TP53__missense`와
동일해 제거됐고, 나머지 31개가 유지됐습니다.

## 결과

| 항목 | EXP-245 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4213989560 | 0.4229885745 | -0.0015896185 |
| Fold 표준편차 | 0.0083182968 | 0.0098679649 | -0.0015496681 |
| Accuracy | 0.4138042251 | 0.4125141106 | +0.0012901145 |
| Log Loss | 2.0266003609 | 1.8509613276 | +0.1756390333 |

| Fold | EXP-245 Macro F1 |
|---:|---:|
| 0 | 0.4161807057 |
| 1 | 0.4129769610 |
| 2 | 0.4192499206 |
| 3 | 0.4252393163 |
| 4 | 0.4365823625 |

큰 개선은 KIRC `+0.1060565608`, LGG `+0.0949367089`, LIHC
`+0.0440591560`, LAML `+0.0262176604`였습니다. 큰 하락은 DLBC
`-0.0689458689`, BLCA `-0.0436868687`, BRCA `-0.0314101152`, PRAD
`-0.0298545845`였습니다.

## 해석과 한계

- mutation-mechanism 구분은 EXP-240의 단순 조합보다 나았지만 EXP-229를 넘지 못했습니다.
- 유방암 관련 모듈을 추가했어도 BRCA F1은 하락했으므로, 문헌 관련성과 분류 성능을
  동일시하지 않습니다.
- 8개 모듈을 동시에 추가했기 때문에 클래스별 변화와 특정 모듈의 효과를 직접
  연결할 수 없습니다.
- KIRC·LGG의 큰 개선도 해당 전용 모듈 효과라고 단정하지 않습니다.

## 재현성과 산출물

- Issue: [#245](https://github.com/fabxoe/open_cancer/issues/245)
- 실행 source commit: `7c755756a19eb721cdfe58dfab0798dac3ba9957`
- Config: `configs/exp245_lineage_mechanism_patterns.yaml`
- Metrics: `reports/exp245_lineage_mechanism_patterns/metrics.json`
- 지식·패널 교집합: `reports/exp245_lineage_mechanism_patterns/lineage_mechanism_membership.json`
- 제출 후보: `submissions/exp245_lineage_mechanism_patterns.csv` (DACON 미제출)
- 제출 SHA-256: `7b588c850cdc6257efd55f6f41e8f757647fbac4f6f2da335306160ce7e22760`
- 재현 상태: `INFERENCE_VERIFIED`

저장 checkpoint 재추론에서 test 라벨 100%, 확률 최대 절대 차이
`1.27e-7`, 제출 CSV SHA-256 일치를 확인했습니다.
