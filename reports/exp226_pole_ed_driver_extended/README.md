# EXP-226 POLE ED hotspot features — E: driver_extended (D의 COAD 신호 확증)

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-226 / #226 |
| 목적 | D(EXP-181)의 COAD 신호가 표본 증가(22→28건)에서도 재현되는지 확인하는 확증 실험 |
| 핵심 입력 | EXP-094 Feature Spec v1 + `pole__ed_driver_extended` (1개 컬럼, 21개 ED driver substitution) |
| 모델 | XGBoost, EXP-094와 동일 하이퍼파라미터, official seed 42 단일 실행(3-seed stability check 생략) |
| Local OOF Macro F1 | 0.4141560542 (EXP-094 대비 `-0.0027305197`) |
| Public LB | 미제출 |
| 판단 | **최종 기각(NOT ADOPTED)** — mlogloss-checkpoint와 macro-f1-checkpoint 재평가 모두에서 기각 확정. POLE pilot 트랙 종료 |

## 배경 및 스코프

D(EXP-181, `POLE_hotspot5`)는 전체 Macro F1 기준 기각됐으나, 4-seed
stability 검증에서 COAD F1 delta가 4/4 seed 전부 일관되게 양의 방향으로
나타났다(UCEC/DLBC는 비일관). 같은 시기 팀의 EXP-219(checkpoint 선택
기준 교체, feature 변경 없음)가 `+0.0053`을 기록하며 decision-level
개입이 feature engineering보다 leverage가 클 수 있음을 시사했다. 이에
따라 본 실험은 **성능 개선 시도가 아니라 D의 COAD 신호가 재현되는지
확인하는 확증 실험**으로 스코프를 좁혔다. 새 feature 코드는 없으며
`src/open_cancer/pole_ed_features.py`의 `pole_ed_driver_extended_family()`
(EXP-181/PR #225에서 이미 구현·테스트 완료)를 그대로 재사용했다.

## 사전 검증 (실제 train.csv)

| Feature | train 양성 건수 | 양성률 |
|---|---:|---:|
| `POLE_ED_driver_extended` | 28 | 0.452% |

fold별 분포: `{0:8, 1:5, 2:5, 3:2, 4:8}` — D의 `{0:8, 1:5, 2:5, 3:1, 4:3}`
보다 fold 3 쏠림이 완화됐다(1→2건).

## 결과 1 — COAD 방향성 확인 (핵심 질문)

**COAD delta: `+0.005080180477105012`** — D(seed 42, `+0.0051`)와 정확히
동일한 부호(양수), 그리고 정확히 동일한 숫자값이다. row-level로 대조한
결과(EXP-170/181 DLBC 대조와 동일 방식), COAD로 "예측"된 샘플 집합 자체가
D→E 확장에도 전혀 바뀌지 않았다 — 즉 "재현"이라기보다 **"COAD의 결정
경계가 D→E 확장에도 흔들리지 않고 그대로 유지됐다"**는 더 정확한 안정성
확인이다.

## 결과 2 — 전체 성능 (참고)

| 지표 | EXP-094 | EXP-226 | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4168865739 | 0.4141560542 | -0.0027305197 |
| Fold 표준편차 | 0.0078842521 | - | +0.0003478711(게이트 통과) |
| Log Loss | - | - | -0.0016359968(개선) |

- Watch class(EXP-094 대비): COAD `+0.0051`, UCEC `-0.0087`, DLBC
  `-0.0501`(D의 seed 42와 완전 동일 — DLBC 예측 집합도 불변)
- 승격 기준: Macro F1 gate 실패, 클래스별 F1 gate 실패(DLBC) → 기각

## 결과 3 — Macro-F1-checkpoint 재평가 (post-hoc, 재학습 없음)

D와 함께 재평가한 결과는
[`pole_cellcycle_macro_f1_checkpoint_reevaluation.md`](../analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md)에
전체 정리했다. 요약:

- 이미 저장된 fold checkpoint에서 macro-f1-best iteration을 재선택(재학습
  없음). checkpoint 정책 전환만으로 OOF가 `+0.0041` 개선됐지만, 올바른
  비교 대상인 **EXP-219(같은 정책의 EXP-094)와 비교하면 여전히
  `-0.0040`으로 순손실**이다.
- COAD는 EXP-219 대비로도 `+0.0078`로 여전히 양의 방향, DLBC는
  `-0.0582`로 오히려 더 크게 하락.
- **게이트는 뒤집히지 않는다** — mlogloss-checkpoint와 macro-f1-checkpoint
  두 정책 모두에서 기각이 확정된다.

COAD가 Cell Cycle(EXP-170/173)과 POLE(EXP-181/226)이라는 서로 무관한
gene-set, 그리고 두 checkpoint 정책 모두에서 공통으로 양의 방향을
보인다는 점에 대해서는, 실제 feature 신호일 가능성과 "COAD 클래스 자체가
sparse 컬럼 추가·checkpoint 선택 메커니즘과 구조적으로 상호작용하는
특성"일 가능성 두 가설을 판단 보류 상태로 분석 문서에 남겼다.

## 결론

D와 E 모두 mlogloss-checkpoint 기준 기각, macro-f1-checkpoint 재평가로도
기각이 유지됐다. 게이트가 발동하지 않았으므로 #174 정책 문서의 결론(단일
유전자 위치 정밀화 포함 pathway 계열 feature 우선순위를 낮춘 판단)을
재검토할 근거도 발생하지 않는다. **POLE pilot 트랙(D/E)을 이걸로 최종
종료한다.** F(`POLE_ED_any_missense`)는 진행하지 않는다.

## 재현과 관련 파일

- Config: `configs/exp226_pole_ed_driver_extended.yaml`
- Resolved config: `reproducibility/exp226_pole_ed_driver_extended/config.resolved.yaml`
- Metrics: `reports/exp226_pole_ed_driver_extended/metrics.json`
- Verdict 상세: `reports/exp226_pole_ed_driver_extended/verdict.json`
- Macro-F1-checkpoint 재평가(D 포함 공유 분석):
  `reports/analysis/pole_cellcycle_macro_f1_checkpoint_reevaluation.md`
- Feature 모듈: `src/open_cancer/pole_ed_features.py`(신규 코드 없음, D에서
  구현된 `pole_ed_driver_extended_family()` 재사용)
- Submission: `submissions/exp226_pole_ed_driver_extended.csv`(미제출, 로컬 보관)
- Reproduction status: `NOT_STARTED`(일반 Local 실험, 리더보드 미제출)
