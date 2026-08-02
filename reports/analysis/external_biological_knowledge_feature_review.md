# 외부 생물학 지식·아미노산 피처 확장 검토

> Issue #174의 일반 Task 문서입니다. 이 문서는 새 모델 결과나 예상 점수를
> 기록하지 않습니다. 실제 실험 결과의 단일 원본은
> [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)와 실험별 `metrics.json`입니다.

## 결론

이 대회에서 사용할 수 있는 입력은 환자별 4,384개 유전자의 변이 문자열뿐이다.
따라서 외부 지식은 **고정된 유전자군 또는 계산 규칙**만 정의할 수 있고, 실제
환자별 피처 값은 반드시 대회 CSV의 변이로 계산해야 한다.

가장 먼저 시도할 수 있는 확장은 이미 저장소에 준비되어 있는 `functional_role_burden`
(oncogene·tumor suppressor의 변이/LoF 유전자 수 4개)이다. OncoKB, 환자별 ECM
상태, SIFT/PolyPhen 점수, 단백질 3차원 구조 영향은 현재 모델 입력으로 사용하지
않는다. ECM 유전자군 집계는 주최측의 **추가 명시 승인**이 있을 때만 별도 후보로
다룬다.

## 실제 데이터와 현재 구현 경계

- 제공 train/test에는 `ID`, train의 `SUBCLASS`, 그리고 유전자별 `WT` 또는 단백질
  변이 문자열만 있다. methylation, RNA/protein expression, 조직 경직도, 면역세포
  침윤도, genomic coordinate, transcript, UniProt isoform은 없다.
- Feature Factory는 문자열에서 mutation type, 단백질 잔기 위치, reference/alternate
  amino acid와 complex 형태를 파싱한다. 단, 위치 숫자를 genome/codon/transcript
  좌표로 추정하지 않는다. 자세한 계약은
  [`FEATURE_FACTORY.md`](../../docs/FEATURE_FACTORY.md)를 따른다.
- 외부 환자 데이터, 환자별 multi-omics, pretrained embedding, 외부 연속 score와
  외부 모델 예측값은 사용하지 않는다. 이 경계는
  [`PROJECT_CONTEXT.md`](../../PROJECT_CONTEXT.md#feature-factory-운영-계약)에 고정돼 있다.

## Google AI 제안별 판정

| 제안 | 판정 | 프로젝트 근거와 처리 |
|---|---|---|
| 아미노산 물성 변화 | 이미 공식 검증 | EXP-107이 charge·polarity 등 4개 요약 피처를 EXP-094에 추가했다. OOF Macro F1은 0.4131379001로 EXP-094(0.4168865739)보다 낮았다. 추가 물성 count를 반복하지 않는다. |
| UniProt 도메인·잔기 주석 | 보류 | UniProt의 site/domain은 protein sequence position을 전제로 한다. 현재 데이터에는 canonical isoform·transcript가 없어 입력 위치를 안전하게 연결할 수 없다. isoform 정합성 없는 domain feature는 만들지 않는다. |
| SIFT·PolyPhen-2 | 제외 | genomic variant, reference genome, transcript 정합성이 없는 현 데이터에서 안정적으로 산출할 수 없다. 외부 연속 예측값도 현재 허용 범위를 넘어선다. |
| OncoKB cancer/actionable annotation | 제외 | OncoKB는 AI/ML 모델 학습에 사용할 수 없다고 명시한다. cancer type을 포함한 actionability는 `SUBCLASS`를 우회해 알려 줄 위험도 있다. |
| OncoKB actionability를 새 target으로 학습 | 부적절 | 대회의 유일한 정답은 26개 `SUBCLASS`다. actionability 정답은 제공되지 않았으며, 별도 문제를 학습하는 것은 대회 목표와 다르다. |
| ECM stiffness·immune exclusion·ECM expression | 제외 | 이러한 값은 expression/proteomics/조직 미세환경 측정값이다. 변이 문자열만으로 환자별 상태를 만들 수 없다. |
| 고정 ECM/matrisome gene membership burden | 추가 승인 후 후보 | 고정 목록과 대회 CSV의 교집합으로 mutation/LoF count만 만든다면 기술적으로 가능하다. 단, Issue #96의 허용 근거를 새 외부 목록까지 확대 해석하지 않고 주최측 승인을 먼저 받는다. |

### 근거 출처

- OncoKB는 cancer-gene 목록과 API를 제공하지만, 라이선스 FAQ에서 AI/ML 학습
  사용을 금지한다. API annotation에는 cancer type을 포함할 수 있다.
  <https://faq.oncokb.org/licensing>, <https://api.oncokb.org/oncokb-website/api>
- UniProt의 sequence annotation은 protein sequence의 위치 구간을 기록한다.
  <https://www.uniprot.org/help/sequence_annotation>
- MatrisomeDB는 정상·질환 조직의 ECM **proteomics**를 통합한 데이터베이스다.
  이는 이 대회의 환자별 mutation-only 행렬과 다른 모달리티다.
  <https://matrisomedb.org/about/>
- Reactome의 ECM organization도 고정 pathway membership으로는 쓸 수 있으나,
  환자별 stiffness 측정값을 제공하지는 않는다.
  <https://reactome.org/content/detail/R-HSA-1474244>

## 기존 실험에서 이미 얻은 신호

| 축 | 대표 실험 | 근거 | 해석 |
|---|---|---|---|
| 아미노산 물성 | EXP-107 | EXP-094 대비 OOF -0.0037486738 | 단독 성능 후보가 아니며 v2-diversity 자산으로만 보존 |
| 고정 pathway burden | EXP-096 | EXP-094 대비 OOF +0.0012287341 | 작은 C-family 보완 신호는 확인했지만 큰 점프 근거는 없음 |
| mutation burden 확장 | EXP-151·154·158 | Macro F1은 소폭 개선했으나 fold 표준편차 gate 실패 | 전역 burden을 더 늘리는 방향은 중단 |
| 현재 최고 Local | EXP-131 | OOF 0.4222392962 | CatBoost extended training이지만 fold·Log Loss 악화로 단독 최종 후보가 아님 |

따라서 생물학적으로 그럴듯한 유전자군을 많이 넣는 것보다, 기존 모델이 헷갈리는
클래스에서 **Macro F1에 맞는 결정 규칙**을 안전하게 검증하는 편이 더 큰 변화를
만들 가능성이 있다. 이 문장은 예상 점수가 아니라 다음 탐색의 우선순위 판단이다.

## 허용 가능한 다음 후보

### 1. C-2 functional-role burden — 첫 공식 후보

이미 `knowledge/abc_c_compact_groups_v1.json`에 oncogene과 tumor suppressor의
고정 membership이 있고, `src/open_cancer/abc_c_features.py`와 단위 테스트도
구현돼 있다. 출력은 아래 네 열뿐이다.

```text
sample__role_oncogene__mutated_gene_count
sample__role_oncogene__lof_gene_count
sample__role_tumor_suppressor__mutated_gene_count
sample__role_tumor_suppressor__lof_gene_count
```

실제 값을 대회 CSV에서만 계산하고, 목록은 실행 전 고정한다. EXP-096의 pathway
피처와 값 중복·높은 상관 여부를 먼저 검사한 뒤, 별도 Experiment Issue에서 EXP-094
대비 canonical 5-fold 단독 ablation으로만 평가한다. Public LB와 test 분포를 보고
목록을 편집하지 않는다.

### 2. Macro F1용 nested decision rule — 외부 지식 없이 우선 검토

클래스 불균형 다중분류에서 `argmax(probability)`가 Macro F1의 최선 결정 규칙이라는
보장은 없다. 이 후보는 피처를 추가하지 않고, 각 outer fold의 train 부분에서만
inner cross-fitting으로 작은 class-wise logit offset 또는 동등한 decision adjustment를
고른 뒤 outer validation에 적용한다.

- 26개 값을 전체 OOF에서 맞추지 않는다.
- offset 범위·regularization·후보 집합을 실행 전 config에 고정한다.
- outer validation과 test에는 fit하지 않고 transform만 한다.
- 기준 XGBoost 확률과 결과를 나란히 보관하며, fold 안정성·log loss·소수 클래스
  붕괴를 함께 판정한다.

이것은 새 모델 또는 새 post-processing이므로 C-2와 섞지 않고 별도 Experiment
Issue에서 실행한다.

### 3. ECM/matrisome fixed membership — 승인 후 단 한 번

주최측이 **새 외부 고정 gene membership**도 허용한다고 명시한 경우에만 일반 Task
Issue에서 다음을 먼저 만든다.

1. 원본 목록의 버전·라이선스·다운로드 시각·SHA-256을 담은 작은 provenance catalog
2. 4,384개 패널과의 교집합, 각 그룹의 커버율과 기존 pathway/role 피처와의 의미 중복 검사
3. core matrisome / ECM-associated / ECM-regulator처럼 사전 고정한 소수 그룹의
   mutated-gene·LoF-gene count

그 뒤에만 별도 Experiment Issue의 5-fold 단독 ablation을 실행한다. expression
signature, stiffness score, cancer-type별 ECM score, 환자별 외부 proteomics는 어느
단계에서도 사용하지 않는다.

## 진행 순서와 중단 규칙

1. **Issue #174 (현재):** 이 문서와 규정 경계를 병합한다. 모델 점수는 만들지 않는다.
2. **새 Experiment Issue:** C-2 functional-role burden의 의미 중복 검사를 통과했을
   때만 canonical 5-fold를 실행한다.
3. **별도 Experiment Issue:** nested decision rule을 기준 모델 확률에만 적용한다.
4. **주최측 추가 승인 후:** ECM catalog Task → ECM 단독 Experiment 순으로 진행한다.

각 후보는 기존 프로젝트 PERFORMANCE 기준을 적용한다. 기준 모델보다 OOF Macro F1
`+0.001` 이상, fold 표준편차 악화 `<0.002`, Log Loss·소수 클래스의 명백한 붕괴가
없을 때만 성능 후보로 채택한다. 어느 하나라도 만족하지 못하면 같은 family의 목록을
사후 조정하지 않고 결과를 ARCHIVE 또는 DIVERSITY로 보존한다.

## 금지·주의 체크리스트

- OncoKB API, annotator, actionability level 또는 variant annotation을 학습 입력으로
  사용하지 않는다.
- `SUBCLASS` 또는 암종별 외부 지식을 feature 생성 조건에 넣지 않는다.
- 외부 gene list를 사용한다는 이유만으로 Issue #96의 pathway 허용 범위를 자동 확대
  해석하지 않는다.
- test의 변이량·ECM token 분포·Public LB 점수로 목록, weight, threshold를 조정하지
  않는다.
- 새 공식 결과는 새 Experiment Issue에서만 만들며, 현재 Task Issue #174에는
  EXP-ID를 만들지 않는다.
