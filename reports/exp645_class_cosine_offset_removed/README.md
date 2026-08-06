# EXP-645 EXP-527 class-cosine 공통 offset 제거 (row-mean centering)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-645 / #645 |
| 목적 | Issue #530의 EXP-527 일반화 감사가 발견한 "26개 class-cosine 점수 전부가 test에서 공통 상승"(domain AUC 0.647) 현상에 대한 단일변수 대응 |
| 방법 | EXP-527과 완전히 동일한 조건 + row별(환자별) 26개 cosine 점수의 평균을 빼는 fold-safe centering만 추가 |
| Local OOF Macro F1 | 0.4385364091 (EXP-527 대비 -0.0083358616) |
| Public LB | 미제출 |
| 판단 | canonical OOF 기준 채택 기준 미달 — `ARCHIVE`. 다만 fold std·Log Loss는 개선돼 공통 offset이 순수 노이즈가 아니라 판별 신호도 포함하고 있었음을 시사 |

## 배경

Issue #530의 EXP-527 일반화 감사(`reports/analysis/exp527_generalization_audit/README.md`)는
26개 class-cosine 점수 전부가 test에서 공통적으로 상승한다는 것을
발견했다(domain classifier OOF AUC 0.647015, 26개 클래스 평균 전부
+0.015~+0.046 상승). PROJECT_CONTEXT에 이미 기록된 사실(train 환자당
평균 non-WT 35.30개 vs test 78.13개, 약 2.2배 차이)과 결합하면, semantic
token 밀도·구성 차이가 26개 cosine 점수에 공통 offset을 만드는 것으로
추정됐다. 이 실험은 그 가설을 단일변수 ablation으로 검증한다.

## 핵심 개념과 방법

fold-train으로 fit한 26개 class centroid에 대한 cosine 유사도는 EXP-527과
완전히 동일하게 계산한다(train은 leave-one-out, validation/test는 전체
outer-train centroid). 유일한 차이는, 이 26개 원점수를 모델에 넣기 전에
**그 행(환자) 자신의 26개 값 평균을 빼는 것**이다. 이 연산은 그 행 자신의
값만 사용하므로 다른 행이나 fold 통계를 전혀 참조하지 않아 fold-safe하며
leakage 위험이 없다. 다른 모든 조건(feature parent, XGBoost
하이퍼파라미터, split)은 EXP-527과 완전히 동일하게 고정했다.

## 검증 방법

공용 fold(`data/splits/stratified_5fold_seed42.csv`)로 canonical 5-fold를
재학습했다. 채택 여부는 canonical OOF Macro F1로만 판단하며, test AUC나
Public LB는 채택 근거로 쓰지 않는다(#530 보고서의 명시적 지침).

## 실제 결과

| 지표 | EXP-527(parent) | EXP-645(offset 제거) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4468722707 | 0.4385364091 | -0.0083358616(악화) |
| Fold 표준편차 | 0.0063793185 | 0.0052434504 | -0.0011358681(개선) |
| Accuracy | 0.4339622642 | 0.4273504274 | -0.0066118368 |
| Log Loss | 2.0274887085 | 2.0054650307 | -0.0220236778(개선) |

Fold별 Macro F1(EXP-527 → EXP-645): fold0 `0.4343→0.4380`, fold1
`0.4506→0.4291`, fold2 `0.4487→0.4392`, fold3 `0.4501→0.4452`, fold4
`0.4512→0.4354`. fold0만 개선했고 나머지 4개 fold는 모두 하락했다.

### 클래스별 비교(EXP-527 대비)

| 방향 | 클래스(델타) |
|---|---|
| 큰 하락 | LGG `-0.1235`, KIRC `-0.0550`, BLCA `-0.0493`, LAML `-0.0323`, THCA `-0.0304` |
| 큰 개선 | LUAD `+0.0783`, TGCT `+0.0441`, BRCA `+0.0315`, KIPAN `+0.0205`, LIHC `+0.0192` |

`-0.05` 붕괴 기준을 넘는 클래스가 2개(LGG, KIRC)다. 이 둘은 이 저장소에서
반복적으로 문제가 됐던 KIPAN/KIRC·GBMLGG/LGG 계보 혼동 축의 클래스와
정확히 겹친다([[project_parser_v4_baseline_reset]] 로드맵 참고) — 공통
offset이 이 두 클래스에서는 순수 노이즈가 아니라 실제 구분에 쓰이던
신호였을 가능성을 시사한다.

## 해석과 한계

- **가설이 부분적으로만 맞았다.** "공통 offset은 test 분포 아티팩트일
  뿐 순수 노이즈"라는 원가설이라면 제거 시 Macro F1도 개선돼야 했지만
  실제로는 악화됐다. 대신 fold std와 Log Loss는 개선됐다 — 이는 공통
  offset이 신호와 노이즈가 섞인 성분이었고, 이번 단순 row-mean centering이
  둘을 함께 제거해 순 손실이 났다는 뜻이다.
- LGG·KIRC 붕괴는 우연이 아닐 가능성이 높다. 이 두 클래스는 저burden
  프로파일이나 형제 클래스(GBMLGG·KIPAN)와의 경계가 원래 얇아서, 공통
  offset의 절대적 위치 정보(예: 전체적으로 얼마나 많은 유전자에 변이가
  있는지와 관련된 성분)가 이 클래스들의 구분에 특히 중요했을 수 있다.
- fold0만 유일하게 개선한 것도 흥미롭다 — offset의 유용성이 fold마다
  다르다는 뜻이며, 이 역시 EXP-642에서 관찰한 "이 종류의 fold-level
  이질성"과 같은 계열의 현상일 수 있다.
- **채택 기준(canonical OOF Macro F1)에 따라 `ARCHIVE`.** test-like
  propensity 같은 domain-shift 진단으로 이 결과를 재평가하지 않는다 —
  이는 블렌드 가중치 선택과 달리 parser/feature 의미 결정이라
  PROJECT_CONTEXT가 test 분포 기반 선택을 명시적으로 금지하는 영역이다.

## 다음 실험 후보

- EXP-567(LightGBM, 같은 parser-v4 parent + class-cosine)에서 같은
  ablation을 재확인해, 트리 성장 방식이 다른 모델에서도 같은 패턴이
  나타나는지 확인한다(EXP-647 진행 중).
- 두 모델 모두에서 같은 방향(악화)이 나오면, "공통 offset 제거"라는
  단순한 접근 자체를 더 이상 추진하지 않고 원인 규명은 #502 로드맵의
  더 깊은 분석으로 넘긴다.

## 재현과 관련 파일

- Config: `configs/exp645_class_cosine_offset_removed.yaml`
- Runner: `scripts/run_exp645_class_cosine_offset_removed.py`
- Resolved config: `reproducibility/exp645_class_cosine_offset_removed/config.resolved.yaml`
- Metrics: `reports/exp645_class_cosine_offset_removed/metrics.json`
- Submission: `submissions/exp645_class_cosine_offset_removed.csv`(DACON 미제출, ARCHIVE)
- Reproduction status: `INFERENCE_VERIFIED`
