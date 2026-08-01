# Feature Factory 운영 안내

Feature Factory는 한 가지 파생변수가 아니라, 모든 모델이 같은 입력 정의를
재사용하게 만드는 공통 생산 기반이다. 파생변수 계산 규칙, 출력 순서, 누수 범위,
외부 지식 출처와 해시를 함께 고정한다.

Residue-position과 문헌 기반 고정 co-mutation pair의 차이, 위치 옵션의
비교 방법은 [팀 공통 개념 안내](RESIDUE_POSITION_AND_CO_MUTATION_GUIDE.md)를
먼저 확인한다.

## 현재 구현 범위

Factory `1.1.0`의 핵심 기반은 다음을 제공한다.

- 원본 CSV의 각 행을 streaming 방식으로 읽는 희소 피처 생성
- 변이 토큰의 유형, 단백질 잔기 위치, reference/alternate 아미노산과 형태 파싱
- family별 정의 버전, 출력 차원, fit 범위와 외부 지식 출처 Registry
- 입력 데이터·유전자 순서·Feature Spec을 결합한 캐시 키
- 캐시 산출물의 SHA-256 검증 후 안전한 재사용
- 위치 family를 끄면 기존 EXP-005 피처 이름과 행렬을 그대로 재생성하는 호환성
- 위치 파싱 성공률, complex token 비율과 형태별 개수를 train/test로 분리한 QC

기존 공식 위치 실험 EXP-047은 유전자마다 다음 값 한 개만 추가했다.

```text
min_residue_position = 그 환자의 해당 유전자 셀에 적힌 모든 변이 위치 중 최솟값
```

예를 들어 한 셀이 `R132H 312_313QY>HH`라면 위치 후보는 `132, 312, 313`이고
값은 `132`다. `WT`, 빈 셀 또는 위치 숫자가 없는 토큰은 위치 피처에 `0`을
기록한다. 기존 mutation-presence와 missing 피처가 있으므로 이 0을 실제
0번 잔기와 혼동하지 않는다.

이 숫자는 입력 문자열에 명시된 **단백질 잔기 위치**다. genomic coordinate,
codon의 nucleotide 위치 또는 특정 transcript의 정규화 좌표로 해석하거나
추정하지 않는다. transcript와 protein length가 없으므로 유전자 간 절대 위치의
생물학적 크기를 직접 비교할 때도 주의한다.

## config에서 family 선택

family는 서로 독립적으로 켜고 끈다. 현재 공통 XGBoost runner는 기존
`mutation_type` core를 항상 사용하고, `residue_position`을 선택적으로 더한다.

```yaml
features:
  mutation_type:
    enabled: true
  residue_position:
    enabled: true
    aggregates:
      - min
```

Factory 1.1에서 다음 ablation과 확장을 선택할 수 있다.

```yaml
  residue_position:
    enabled: true
    aggregates: [min, max, span]
    missing_policy: indicator       # zero | indicator
    complex_tokens: exclude         # include | exclude
    transform: coarse_bin           # raw | coarse_bin
    bin_width: 100
```

- `max`는 해당 유전자 셀의 가장 큰 위치, `span`은 `max-min`이다.
- `indicator`는 위치를 읽은 유전자에 `residue_position_observed=1`을 추가한다.
  일반적으로 위치 파싱 실패와 mutation-presence를 구분하기 위한 옵션이지만,
  현재 데이터에서는 모든 non-WT 토큰의 위치가 파싱되어 기존
  mutation-presence와 완전히 같다. 따라서 EXP-063·078에서는 결측 해소가 아닌
  중복 피처 weighting으로 해석한다.
- `exclude`는 complex 토큰에서 읽은 위치를 aggregate에서 제외한다.
- `coarse_bin`은 고정 폭 구간 번호를 사용한다.
- 유전자별 정규화는 validation fold를 제외한 fold-train에서 분모를 fit해야 한다.
  정적 Factory에서 전체 train 분모를 만들면 validation 분포를 미리 보게 되므로
  현재는 오류로 차단하고 후속 fold transformer로 분리한다.

옵션을 생략한 EXP-047 설정은 Factory 1.1에서도 기존과 같은
`min + zero + complex 포함 + raw`로 해석된다.

실행 후 실제 적용된 family와 기본값은
`reproducibility/expNNN_<slug>/config.resolved.yaml`에 저장된다. 사람이 Issue나
History에 같은 설정을 다시 적지 않는다.

## 생성 파일과 캐시

실험별 `data/processed/feature_factory/` 아래에 다음 파일을 만든다. 이 디렉터리는
로컬 캐시이며 Git에 커밋하지 않는다.

```text
train_features.npz
test_features.npz
train_ids.csv
test_ids.csv
train_labels.csv
feature_names.json
feature_spec.json
feature_registry.json
parsing_qc.json
feature_report.json
```

캐시 키는 Factory 버전, train/test SHA-256과 Feature Spec SHA-256을 결합한다.
키가 같아도 산출물 하나의 해시가 다르면 캐시를 버리고 다시 생성한다. 따라서
파일 이름만 같거나 이전 실행 폴더가 남아 있다는 이유로 오래된 피처를 재사용하지
않는다.

Feature Spec에는 유전자 순서 해시, 전체 피처 이름 순서 해시와 family Registry가
포함된다. 모델의 OOF와 test 확률에는 이 spec 해시가 resolved config를 통해
연결되어야 한다.

## family 확장 순서

핵심 파서와 위치 피처가 검증된 뒤 다음 family를 독립적으로 구현한다.

1. residue position: min/max/span, 고정 bin, fold-train
   정규화와 recurrent hotspot
2. amino-acid change: 제한 vocabulary, 물성 그룹 치환, stop/frameshift 요약
3. pathway·hallmark: pathway별 변이 수와 mutation-type count
4. driver·기능 그룹: oncogene, tumor suppressor, DNA repair burden
5. PPI 정적 요약: 연결 수, degree-normalized 이웃, component와 hub burden
6. long-gene·artifact control: 고정 그룹 burden과 전체 burden 대비 비율
7. co-mutation: 문헌 기반 고정 pair 또는 fold-train에서만 선정한 pair와
   frequency-tier 요약
8. complex-token morphology: 범위, `>`, `*`, prefix/suffix 길이의 저차원 요약

각 family는 별도 단위 테스트와 독립 screening 결과가 있어야 한다. target이나
빈도에서 vocabulary, hotspot, pair를 학습한다면 반드시 fold-train에서만 fit하고
validation/test에는 transform만 수행한다.

외부 pathway, PPI와 COSMIC 원본을 그대로 모델 입력으로 넣지 않는다. 허용되는
경우에도 외부 지식은 고정 그룹·관계·계산 규칙을 정의하는 데만 쓰고, 실제 모델
입력값은 각 환자의 제공된 4,384개 유전자 변이 셀에서 계산한다. 출처, 버전,
라이선스, 원본 SHA-256과 재배포 제한은 manifest에 기록한다.

## screening과 Feature Spec v1 동결

- 빠른 fold는 후보 제거에만 사용하며 공식 채택 점수로 쓰지 않는다.
- 유망 family의 공식 채택은 새 Experiment Issue와 공용 전체 5-fold가 필요하다.
- family별 단독 OOF와 기존 모델의 OOF 오류 상관을 함께 비교한다.
- 8개 family는 구현 완료 또는 근거를 남긴 보류 상태여야 한다.
- 채택 family 조합, 출력 순서와 정의 버전을 `Feature Spec v1`로 동결한다.
- 동결 이후 새 아이디어는 v2 후보로 이동하며 모델 다양화와 스태킹을 막지 않는다.
- Public LB와 test 분포를 보고 파서, hotspot, 유전자 그룹 또는 피처 규칙을
  수정하지 않는다.

## 모델 다양화와 스태킹으로 넘기는 계약

Feature Spec v1 동결 후 XGBoost, LightGBM, CatBoost, 선형 모델, NB와 필요한
경우 얕은 신경망/GNN을 같은 피처와 공용 fold로 학습한다. 각 모델은 다음을
남겨야 한다.

- `(6201, 26)` OOF 확률과 `(2546, 26)` test 확률
- 공용 fold ID와 고정 26개 클래스 순서
- Feature Spec, data와 split 해시
- resolved config, checkpoint와 재추론 결과
- 전체·fold별·클래스별 Macro F1

먼저 단순 평균과 제한된 가중 평균을 평가하고, 그다음 cross-fitted multinomial
logistic meta learner를 평가한다. 전체 OOF에서 가중치를 고른 뒤 같은 OOF로
평가한 값은 공식 성능으로 인정하지 않는다. 모델은 단독 점수만이 아니라
cross-fitted stacking OOF 개선 여부로 채택한다.

동결된 matrix는 다음처럼 이름으로 생성한다. 허용 이름은 `v1`,
`v2-performance`, `v2-diversity`뿐이며 EXP-094 base Feature Spec SHA-256이 다르면
즉시 중단한다.

```bash
uv run python scripts/materialize_frozen_feature_spec.py \
  --spec v2-performance \
  --output data/processed/<issue-or-exp>/v2-performance
```

출력 폴더의 `feature_spec_manifest.json`에는 입력·config·피처 순서·행렬 해시와
family Registry가 기록된다. `data/processed/` 산출물은 Git에 커밋하지 않는다.
