# Residue-position indicator 의미 감사

> 일반 Task Issue [#80](https://github.com/fabxoe/open_cancer/issues/80)의
> target-independent QC 결과입니다. 새로운 모델 실험이나 점수를 만들지 않습니다.

## 결론

현재 데이터와 Feature Factory v1.1.0에서 `residue_position_observed`는 기존
유전자별 `mutation_presence`와 완전히 같습니다.

| 항목 | Train | Test |
|---|---:|---:|
| 샘플 | 6,201 | 2,546 |
| mutated gene-cell | 218,893 | 198,930 |
| position-observed gene-cell | 218,893 | 198,930 |
| presence와 observed 불일치 | **0** | **0** |
| 위치 없는 변이 토큰 | **0** | **0** |
| 위치 파싱률 | 100% | 100% |

따라서 EXP-063과 EXP-078의 indicator 추가는 결측 의미를 새로 전달한 것이 아니라
mutation-presence 4,384개 열을 복제한 것이다. 두 실험의 실제 점수와 재현 상태는
그대로 두되, 점수 변화를 결측 ambiguity 해소나 생물학적 위치 신호로 해석하지
않는다.

## 왜 점수가 달라질 수 있나

EXP-047·069의 피처 수는 35,084개이고 EXP-063·078은 39,468개다. 추가된
4,384개 indicator는 기존 mutation-presence와 같지만 XGBoost는
`colsample_bytree=0.8`을 사용한다. 중복 열은 presence 정보가 split 후보에
포함될 상대 확률을 바꾸므로 완전한 no-op이 아니다.

- EXP-063의 개선: 결측 indicator 효과가 아니라 중복 피처 weighting perturbation
- EXP-078의 하락: indicator의 결측 표현 실패가 아니라 같은 perturbation의 다른 결과
- 두 결과 모두 실제 OOF 기록은 유지
- indicator-only 후속 공식 실험은 생물학적 가설을 검증하지 않으므로 중단

## 실제 위치와 표기 분포 QC

양의 max-residue 위치 분포는 다음과 같다.

| 지표 | Train | Test |
|---|---:|---:|
| 최소 | 2 | 1 |
| 중앙값 | 339 | 307 |
| 90% 분위수 | 1,277 | 1,138 |
| 99% 분위수 | 3,629 | 3,066.42 |
| 평균 | 560.90 | 499.24 |

전역 train/test KS statistic은 약 `0.04285`다. 이는 gene·암종 구성 차이까지
섞인 QC 값이므로 생물학적 차이나 성능 개선의 직접 근거로 사용하지 않는다.

표기 형태의 shift는 더 크다.

| 항목 | Train | Test |
|---|---:|---:|
| complex token | 341 / 255,164 (`0.1336%`) | 19,070 / 337,512 (`5.6502%`) |
| multi-position token | 239 (`0.0937%`) | 2,456 (`0.7277%`) |

이 값은 parser OOD와 robustness를 점검하는 자료다. test 분포를 보고 complex
제외, hotspot, threshold나 제출 후보를 선택하는 데 사용하면 안 된다.

## Vera 코드 검토

Vera의 진단 축 분리와 표 구성은 유용하지만 제공 코드는 그대로 사용하지 않았다.

- 저장소에 없는 `factory_long_train.parquet`과 3,800만 행 long table을 가정
- 프로젝트의 sparse CSR 캐시를 재사용하지 않음
- 예시 수치를 실제 데이터 결과처럼 오인할 위험
- NaN이 `pos == 0`, `pos > 0` 양쪽에서 제외되는 계산 문제
- 짧게 자른 DataFrame hash는 프로젝트의 파일 SHA-256 계약과 다름
- `0.01`, `0.02` 판정선은 검증된 기준이 아닌 휴리스틱

대신 `scripts/diagnose_residue_position.py`가 기존 CSR·feature names·parsing QC의
전체 SHA-256을 기록하고 target이나 label을 읽지 않은 채 이 JSON을 생성한다.

## 후속 negative control 계약

위치 숫자 자체의 추가 정보를 검증할 때는 다음을 지킨다.

1. 각 outer fold의 train 부분에서만 gene별 위치를 섞는다.
2. validation 위치와 mutation-presence는 원본 그대로 유지한다.
3. test 데이터는 생성·선택·판정에 사용하지 않는다.
4. 가능하면 mutation type·token-count strata 안에서 섞는다.
5. seed 42 한 번이 아니라 여러 고정 seed로 반복하고 paired fold 차이를 기록한다.

이 검증 전에는 residue-position 실험의 OOF 개선을 생물학적 hotspot이나 기능부위
효과로 단정하지 않는다.

## 후속 negative control 실행 결과 (EXP-160, 계약 종료)

위 "후속 negative control 계약"을 [EXP-160](../exp160_residue_position_negative_control/README.md)에서
실행했다. 각 outer fold의 train 부분에서만 유전자별 `max_residue_position` 값을
mutation-type strata 안에서 무작위 재배치하고(validation·test는 원본 유지),
5개 고정 seed로 반복해 EXP-069와 짝지어 비교했다.

- 원본(EXP-069) OOF Macro F1 `0.4131007993` → permuted 평균 `0.3987413040`
  (차이 `-0.0143594953`)
- 5개 fold 전부 하락, 25개 (seed, fold) 조합 중 24개가 원본보다 낮음
- 상세: `reports/exp160_residue_position_negative_control/metrics.json`,
  `reports/exp160_residue_position_negative_control/permutation_detail.json`

**결론(계약 종료)**: `max_residue_position`은 gene×mutation-type 소속 정보만으로
설명되지 않는, fold를 넘어 일반화되는 실제 신호를 담고 있다. 노이즈 가설은
기각한다. Feature Spec v1의 `max_residue_position` 컴포넌트를 그대로 유지한다.
단, 이 결과는 신호의 존재만 확인하며 생물학적 hotspot·기능부위 효과로의 해석은
별도 검증 없이 단정하지 않는다.

## 관련 파일

- Machine-readable QC: `reports/analysis/residue_position_semantics_qc.json`
- 실행기: `scripts/diagnose_residue_position.py`
- 진단 모듈: `src/open_cancer/position_diagnostics.py`
- EXP-063 보고서: `reports/exp063_xgb_residue_indicator/README.md`
- EXP-078 보고서: `reports/exp078_xgb_max_residue_indicator/README.md`
- EXP-160 보고서(negative control 실행): `reports/exp160_residue_position_negative_control/README.md`
