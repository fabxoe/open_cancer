# 실험 보고서 사용법

`EXPERIMENT_HISTORY.md`는 전체 실험의 점수, 상태와 판단을 빠르게 찾는 단일
색인입니다. 피처 개념, 변환 예시, 상세 해석과 긴 분석은 이 폴더의 실험별
보고서에 작성합니다.

## 경로

Experiment Issue #12에서 파생된 `EXP-012` 보고서는 다음 형식을 사용합니다.

```text
reports/exp012_<slug>/
├── README.md
├── metrics.json
└── class_f1.csv
```

GitHub는 폴더의 `README.md`를 자동으로 화면에 표시합니다.

## 작성 순서

1. [`EXPERIMENT_REPORT_TEMPLATE.md`](EXPERIMENT_REPORT_TEMPLATE.md)를
   `reports/expNNN_<slug>/README.md`로 복사합니다.
2. 실제 실행값으로 자리표시자를 교체합니다.
3. 측정하지 않았거나 사용하지 않은 내용은 만들지 말고 `미측정`, `미사용` 또는
   `미제출`로 명확히 표시합니다.
4. `EXPERIMENT_HISTORY.md`의 요약표와 상세 로그에 보고서 상대경로를 연결합니다.
5. PR 본문에도 같은 보고서 링크를 추가합니다.

## 언제 작성하나?

다음 실험은 사람이 이해할 수 있는 README 작성을 권장합니다.

- 팀의 첫 베이스라인
- 새로운 데이터 처리 또는 피처를 처음 도입한 실험
- 리더보드에 제출한 실험
- 현재 최고 모델과 최종 수상 후보
- 팀원이 재사용하거나 설명을 자주 확인할 실험

seed나 단일 하이퍼파라미터만 바꾼 작은 비교 실험은 장문 보고서를 강제하지 않습니다.
그 경우 `EXPERIMENT_HISTORY.md`, resolved config와 metrics만으로 충분합니다.

## 장기 실행 계획

여러 Issue와 실험에 걸친 장기 계획은 `reports/plans/`에 둡니다. 로드맵에는
확정된 작업 순서, 중단 조건, 단계별 Issue·EXP·PR과 다음 행동을 기록하고, 실제
점수와 결론은 `EXPERIMENT_HISTORY.md`와 실험별 `metrics.json`을 원본으로
사용합니다.

로드맵을 사용하는 작업은 시작할 때 `PROJECT_CONTEXT.md`,
`EXPERIMENT_HISTORY.md`와 해당 로드맵을 함께 읽습니다. 실행하지 않은 단계에는
예상 점수나 가상 결과를 적지 않고 `N/A`, `미발급` 또는 `PLANNED`로 표시합니다.

현재 장기 계획:

- [최우선: Full parser v4 기반 모델 기준선 재정립 로드맵](plans/parser_v4_baseline_reset_roadmap.md)
- [Annotation-invariant parser·robust representation 로드맵](plans/annotation_invariant_parser_roadmap.md)
- [고정 암종 표지 패널·isoform 의미 검증 로드맵](plans/domain_marker_isoform_semantics_roadmap.md)
- [Residue-position·Hotspot 개발 로드맵](plans/residue_position_hotspot_roadmap.md)
- [ABC 신호 포트폴리오·스태킹 로드맵](plans/abc_signal_portfolio_stacking_roadmap.md)
- [오리엔테이션 기반 상관 삭제·피처 선택 로드맵](plans/orientation_correlation_feature_selection_roadmap.md)

현재 동결된 ABC Feature Spec v2와 선택 근거:

- [Feature Spec v2 명세](../configs/abc_stack_feature_spec_v2.yaml)
- [ABC-Stack OOF 포트폴리오 감사](analysis/abc_oof_portfolio_audit.md)
- [G4 모델 OOF 다양성·확률 품질 감사](analysis/g4_model_portfolio_audit.md)
- [G7 최종 후보 재현·제출 준비 감사](analysis/g7_final_candidate_audit.md)
- [최종 후보 제출·재현 체크리스트](final_candidate_checklist.md)

원본 변이 분포를 암종별로 확인하는 탐색용 EDA:

- [Train mutation violin EDA](analysis/eda_violin/README.md)
- [Train/Test tokenization OOD QC](analysis/tokenization_ood/README.md)
- [동결 Feature Spec·공통 모델 runner 계약](analysis/frozen_feature_model_runner_contract.md)

프로젝트 전체에 영향을 주는 target-independent QC와 의미 감사는
`reports/analysis/`에 둡니다. 이는 새 실험 점수를 만드는 폴더가 아니며 실제
입력·산출물 해시와 해석 한계를 함께 기록합니다.

- [Residue-position indicator 의미 감사](analysis/residue_position_semantics_qc.md)
- [Vera EXP-094 후속 검토](analysis/vera_exp094_followup.md)
- [ABC-Stack OOF 포트폴리오 감사](analysis/abc_oof_portfolio_audit.md)
- [외부 생물학 지식·아미노산 피처 확장 검토](analysis/external_biological_knowledge_feature_review.md)
- [채택 XGBoost 모델 validation-only TreeSHAP 감사·시각화 노트북](analysis/adopted_model_tree_shap/README.md)
- [고정 암종 표지 mutation-proxy 의미 감사](analysis/observable_marker_semantic_audit/README.md)
- [Track B isoform·잔기 의미 QC](analysis/isoform_residue_semantics/README.md)
- [Stop 표기 정규화 전후 MANE·isoform 의미 분포 재감사](analysis/isoform_stop_normalization_impact/README.md)
- [Annotation-invariant mutation parser v2 감사](analysis/robust_mutation_parser_v2/README.md)
- [변이 표기 정규화·의미 동등성 계약 감사](analysis/mutation_notation_semantic_contract/README.md)
- [Stop 표기 교란 parser·feature 불변성 감사](analysis/stop_notation_invariance/README.md)

## 역할 구분

| 파일 | 역할 |
|---|---|
| `EXPERIMENT_HISTORY.md` | 전체 실험 색인, 핵심 점수, 상태와 판단 |
| 실험별 `README.md` | 사람이 읽는 개념 설명, 해석, 한계와 다음 단계 |
| `metrics.json` | 프로그램이 읽는 실제 평가값 |
| `config.resolved.yaml` | 기본값까지 포함한 실제 실행 설정 |
| `reports/plans/*.md` | 여러 Issue에 걸친 작업 순서, 중단 조건과 진행 상태 |
| `reports/analysis/*` | 실험이 아닌 공통 QC, 의미 감사와 해석 한계 |

`EXPERIMENT_HISTORY_1.md`, `EXPERIMENT_HISTORY_2.md`처럼 History를 번호로 나누지
않습니다. 실험별 README를 연결하면 History를 짧게 유지하면서도 상세 정보를
잃지 않을 수 있습니다.
