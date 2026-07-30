# EXP-003 XGBoost mutation-presence 베이스라인

이 문서는 팀의 첫 공식 비교 기준인 EXP-003이 어떤 데이터를 사용했고, 유전자
문자열을 어떻게 숫자로 바꾸며, 무엇을 사용하지 않았는지 쉽게 설명합니다.

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| Issue / PR | [#3](https://github.com/fabxoe/open_cancer/issues/3) / [#13](https://github.com/fabxoe/open_cancer/pull/13) |
| 입력 | 환자별 4,384개 유전자의 변이 존재 여부 |
| 피처 | WT·빈값=0, 변이 문자열=1인 CSR 희소 행렬 |
| 모델 | XGBoost 다중 분류 |
| 검증 | 팀 공용 Stratified 5-fold |
| OOF Macro F1 | 0.334930 |
| Public LB | 미제출 |
| 재현 상태 | NOT_STARTED |
| 판단 | 이후 실험의 비교 기준으로 채택 |

## 1. 원본 데이터는 어떻게 생겼나?

원본 CSV에서 한 행은 환자 한 명이고, 열에는 유전자 4,384개가 있습니다. 각 유전자
칸에는 다음 값이 들어갑니다.

- `WT`: 해당 유전자에서 변이가 표시되지 않음
- `R175H`, `V600E` 같은 문자열: 변이가 표시됨
- 빈값: 정보가 비어 있음. EXP-003에서는 `WT`와 같이 0으로 처리

유전자가 네 개뿐이라고 가정하면 환자 한 명은 다음처럼 표현될 수 있습니다.

| TP53 | KRAS | EGFR | BRAF |
|---|---|---|---|
| `R175H` | `WT` | `L858R A871T` | 빈값 |

XGBoost가 이 문자열을 그대로 사용하는 대신, EXP-003은 각 유전자에 변이가
있는지만 0과 1로 바꿉니다.

## 2. Mutation presence란?

`Mutation presence`는 **유전자별 변이 존재 여부**입니다.

```text
WT 또는 빈값       → 0
변이가 하나라도 있음 → 1
```

앞의 환자는 다음과 같이 변환됩니다.

```text
TP53=R175H       → 1
KRAS=WT          → 0
EGFR=L858R A871T → 1
BRAF=빈값        → 0

결과: [1, 0, 1, 0]
```

스위치에 비유하면 변이가 없는 유전자는 OFF(0), 변이가 있는 유전자는 ON(1)입니다.
EGFR 칸에 변이 문자열이 두 개 있어도 “EGFR에 변이가 존재한다”는 의미로 값은
1입니다.

실제 모델에는 환자마다 이런 스위치가 4,384개 있습니다.

```text
[TP53 변이 여부, KRAS 변이 여부, EGFR 변이 여부, ..., 4384번째 유전자 변이 여부]
```

이 방식은 변이의 총개수만 보는 것이 아니라 **어떤 유전자에 변이가 있는지**를
보존합니다. XGBoost는 특정 유전자의 변이나 여러 유전자의 변이 조합이 암종과 어떤
관계가 있는지 학습합니다.

`mutation_presence`는 대회가 제공한 원본 컬럼명이 아닙니다. 원본의 `WT`, 빈값,
변이 문자열에서 우리가 만드는 파생 피처를 설명하는 이름입니다.

## 3. Mutation burden과 무엇이 다른가?

이 프로젝트에서 말하는 mutation-burden proxy는 Mutation presence의 0과 1을 모두
더한 값입니다. 더 정확한 이름은 `mutated_gene_count`, 즉 **샘플당 변이 유전자
수**입니다.

```text
Mutation presence = [1, 0, 1, 0]
mutated_gene_count = 1 + 0 + 1 + 0 = 2
```

스위치로 비유하면 차이는 다음과 같습니다.

- Mutation presence: 어떤 스위치가 켜졌는지 전부 보여줌
- mutated-gene count: 켜진 스위치가 몇 개인지만 알려줌

예를 들어 두 환자가 각각 두 유전자에 변이가 있다고 하겠습니다.

```text
환자 A: TP53, EGFR 변이 → 총 2개
환자 B: BRCA1, KRAS 변이 → 총 2개
```

두 환자의 mutated-gene count는 모두 2이지만 변이가 발생한 유전자는 완전히
다릅니다. 합계 하나만 사용하면 이 차이를 알 수 없습니다.

| 구분 | Mutation presence | Mutated-gene count |
|---|---|---|
| 의미 | 유전자별 변이 존재 여부 | 변이가 표시된 유전자 총개수 |
| 환자당 값 | 4,384개의 0과 1 | 숫자 1개 |
| 어떤 유전자가 변이됐는지 | 알 수 있음 | 알 수 없음 |
| EXP-003 사용 여부 | 사용 | 사용하지 않음 |

원본 데이터에는 두 피처가 별도 컬럼으로 들어 있지 않습니다. 둘 다 유전자 문자열로
만들 수 있는 파생 피처이며, EXP-003은 Mutation presence만 사용했습니다.

## 4. TMB란?

TMB는 `Tumor Mutational Burden`, 한국어로 **종양 변이 부담**입니다. 종양 DNA의
일정한 크기 안에서 변이가 얼마나 많이 발견됐는지를 나타내며 일반적으로 다음처럼
계산합니다.

```text
TMB = 기준을 통과한 체세포 변이 수 ÷ 분석한 DNA 영역의 크기(Mb)
단위 = mutations per megabase, mut/Mb
```

책의 오탈자를 세는 것에 비유할 수 있습니다. 오탈자가 100개라는 정보만으로는
10페이지 책인지 1,000페이지 책인지 알 수 없습니다. TMB는 분석한 DNA의 크기를
고려해 변이가 얼마나 자주 나타나는지 계산합니다.

TMB는 일부 암에서 면역항암제 반응 가능성을 판단하는 바이오마커로 쓰일 수 있지만,
TMB가 높다고 반드시 치료 반응이 좋은 것은 아닙니다.

- [미국 국립암연구소(NCI)의 TMB 정의](https://www.cancer.gov/publications/dictionaries/cancer-terms/def/tumor-mutational-burden)
- [precisionFDA의 TMB 설명](https://precision.fda.gov/challenges/18)

### 이 데이터로 임상적 TMB를 계산할 수 있나?

정확한 임상적 TMB는 계산할 수 없습니다. 대회 데이터에는 다음 정보가 충분히
제공되지 않았기 때문입니다.

- 분석한 DNA 영역의 정확한 Mb 크기
- 종양과 정상 조직을 비교해 체세포 변이만 구분한 결과
- TMB 계산에 포함할 변이 필터 기준
- 변이 신뢰도와 allele frequency
- synonymous/non-synonymous 변이 구분

따라서 유전자별 0과 1을 더한 값을 TMB라고 부르면 안 됩니다.

```text
임상적 TMB
= 필터링된 체세포 변이 수 ÷ 분석 영역 Mb

이 프로젝트의 mutated_gene_count
= 변이가 하나라도 표시된 유전자 컬럼의 개수
```

## 5. EXP-003이 실제로 사용한 입력

EXP-003은 가장 단순하고 해석하기 쉬운 비교 기준을 만들기 위해 다음 입력만
사용했습니다.

```yaml
features:
  encoding: mutation_presence
  include_mutation_burden: false

model:
  use_balanced_sample_weight: false
```

- 4,384개 유전자별 Mutation presence 사용
- Mutation burden 또는 mutated-gene count 미사용
- class/sample weight 미사용
- 외부 데이터 미사용
- 변이 문자열의 세부 종류 미사용

Mutation presence 행렬은 대부분 0이므로 CSR 희소 행렬로 저장해 메모리 사용량을
줄였습니다.

## 6. 모델과 검증 방법

모델은 26개 암종의 확률을 출력하는 XGBoost `multi:softprob` 분류기입니다.

| 설정 | 값 |
|---|---:|
| 최대 boosting rounds | 800 |
| Learning rate | 0.05 |
| Max depth | 4 |
| Row sampling | 0.8 |
| Column sampling | 0.2 |
| Early stopping | 50 rounds |
| Tree method / device | hist / CPU |
| Fold seed | 42, 43, 44, 45, 46 |

검증에는 팀 공용 Stratified 5-fold를 사용했습니다. 각 환자는 자신이 학습에
포함되지 않은 fold 모델로 한 번만 예측되며, 6,201명 전체의 OOF 예측을 모아
Macro F1을 계산했습니다. test 확률은 다섯 fold 모델의 확률 평균입니다.

## 7. 실제 결과

| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.330432 | 0.360193 | 1.987545 | 551 |
| 1 | 0.342344 | 0.364516 | 2.023937 | 522 |
| 2 | 0.342316 | 0.351613 | 1.973660 | 600 |
| 3 | 0.324125 | 0.358871 | 2.019798 | 445 |
| 4 | 0.325573 | 0.343548 | 2.013686 | 555 |

전체 결과:

```text
OOF Macro F1: 0.334930
OOF Accuracy: 0.355749
OOF Log Loss: 2.003723
Fold F1 평균 ± 표준편차: 0.332958 ± 0.007932
```

클래스별 F1은 큰 차이를 보였습니다.

- 높은 클래스: ACC 0.829630, SKCM 0.690058, COAD 0.650655
- 낮은 클래스: THYM 0.000000, KIRC 0.057658, CESC 0.093897

이 결과는 Mutation presence만으로도 일부 암종은 구분되지만, 모든 암종을 고르게
맞히기에는 부족하다는 것을 보여줍니다. 특히 Macro F1은 낮은 클래스의 성능도 같은
비중으로 평가하므로 약한 클래스 개선이 중요합니다.

Public LB에는 아직 제출하지 않았습니다. 생성된 CSV는 제출 후보일 뿐이며 실제
리더보드 점수나 순위는 없습니다.

## 8. 한계와 다음 실험 후보

EXP-003은 비교 기준을 만드는 것이 목적이므로 의도적으로 단순합니다.

주요 한계:

- 같은 유전자의 서로 다른 변이 종류를 모두 1로 합침
- 한 유전자에 변이가 여러 개 있어도 개수 차이를 사용하지 않음
- 클래스 불균형을 보정하지 않음
- 임상적 TMB와 mutated-gene count를 사용하지 않음
- 일부 희소 클래스의 F1이 매우 낮음

다음 실험은 한 번에 한 가지 변화만 EXP-003과 비교하는 것이 좋습니다.

1. balanced sample weight만 추가
2. mutated-gene count만 추가
3. 유전자 칸 안의 변이 토큰과 개수 피처 추가
4. 약한 클래스의 confusion matrix를 바탕으로 관련 피처 보강

## 9. 재현과 관련 파일

- 입력 override: [`configs/exp003_xgb_baseline.yaml`](../../configs/exp003_xgb_baseline.yaml)
- 실제 적용 설정: [`config.resolved.yaml`](../../reproducibility/exp003_xgb_baseline/config.resolved.yaml)
- 전체 지표: [`metrics.json`](metrics.json)
- 클래스별 F1: [`class_f1.csv`](class_f1.csv)
- 제출 후보: [`submissions/exp003_xgb_baseline.csv`](../../submissions/exp003_xgb_baseline.csv)
- Source commit: `7306182669c3676e7b17024d3cf1f821131d909b`
- Reproduction status: `NOT_STARTED`

실행 명령:

```bash
PYTHONHASHSEED=42 uv run python scripts/run_xgb_baseline.py \
  --config configs/exp003_xgb_baseline.yaml
```
