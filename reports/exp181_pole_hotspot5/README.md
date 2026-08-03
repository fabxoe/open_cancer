# EXP-181 POLE ED hotspot features — D: hotspot5

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-181 / #181 |
| 목적 | 단일 유전자(POLE) 위치 특이적 hotspot 정밀화 파일럿(D). Vera Health 자문 반영 |
| 핵심 입력 | EXP-094 Feature Spec v1 + `pole__hotspot5` (1개 컬럼) |
| 모델 | XGBoost, EXP-094와 동일 하이퍼파라미터 |
| Local OOF Macro F1 (seed 42, 공식) | 0.4137048981 (EXP-094 대비 `-0.0031816758`) |
| Public LB | 미제출 |
| 판단 | **기각(NOT ADOPTED)** — 단, seed 민감도가 매우 커서 해석에 주의 필요 |

## 배경

Cell Cycle pathway aggregation(#170 EXP-A, #173 EXP-B)이 연속 기각되고
#174 정책 문서가 "여러 유전자를 OR로 묶는" 방향의 우선순위를 낮춘 것과
달리, 이 실험은 **단일 유전자(POLE)의 기존 범주형 컬럼을 위치 특이적으로
정밀화**하는 설계로, 팀이 이미 채택한 hotspot-34(BRAF V600E 등,
EXP-031→085→094) 방식과 구조적으로 동일하다.

## 도메인 근거와 사전 검증

POLE hypermutator phenotype은 exonuclease domain(ED, codons 268-471)의
특정 missense가 핵심이며, 대표 5대 hotspot(P286R, V411L, S297F, A456P,
S459F)이 문헌에서 반복 확인된다(Vera Health 자문, TCGA/ESMO 가이드라인).
실제 train.csv로 사전 검증한 결과:

- `POLE_hotspot5` 양성: 22건(0.355%)
- `POLE_ED_any_missense=1`인 41건의 SUBCLASS 분포: UCEC 19, COAD 7 압도적
  다수 — 도메인 가설과 일치
- fold별 양성 분포: `{0:8, 1:5, 2:5, 3:1, 4:3}` — **fold 3에 1건뿐**이라
  seed 민감도 위험을 미리 인지하고 3-seed(1001/1002/1003) stability
  check를 계획했다.

## 방법

`src/open_cancer/pole_ed_features.py`의 `PoleEdFamily`(Feature Factory
family로 등록, PR #172 리뷰 패턴을 처음부터 적용)로 `pole__hotspot5`를
계산했다. 공식 기록은 다른 모든 실험과 동일하게 model seed 42를 사용하고,
추가로 seed 1001/1002/1003으로 독립 재학습해 안정성을 확인했다.

## 결과 1 — Seed별 개별 수치

| Seed | OOF Macro F1 | Baseline 대비 delta |
|---|---:|---:|
| **42 (공식 기록)** | 0.4137048981 | **-0.0031816758** |
| 1001 | 0.4169853250 | +0.0000987511 |
| 1002 | 0.4178158047 | +0.0009292308 |
| 1003 | 0.4169726284 | +0.0000860545 |

Baseline(EXP-094) = 0.4168865739. 3개 stability seed의 표준편차는
0.000395로 매우 촘촘하게 뭉쳐 baseline 근방(flat)이지만, 공식 기록에 쓰인
seed 42만 뚜렷한 이상치(outlier)로 낮다. 4개 seed 전체 표준편차는
약 0.00268로, seed 42가 나머지 셋보다 확연히 낮다.

## 결과 2 — UCEC/COAD/DLBC per-class 4-seed 안정성 (재학습 없이 보강 후 재확인)

최초 실행은 stability seed의 OOF를 저장하지 않아, `scripts/verify_exp181_watch_class_stability.py`로
seed 1001/1002/1003을 재실행해(seed 42는 저장된 OOF 재사용) per-class F1을
복구했다. 재현된 fold별 점수는 원래 기록과 완전히 일치했다
(`matches_originally_recorded_fold_scores: true`, 결정론적 재현 확인).

| 클래스 | seed 42 | seed 1001 | seed 1002 | seed 1003 | 방향 일관성 | 평균 delta | std |
|---|---:|---:|---:|---:|---|---:|---:|
| **COAD** | +0.0051 | +0.0051 | +0.0152 | +0.0051 | ✅ 4/4 양수 | +0.0076 | 0.0044 |
| **UCEC** | -0.0072 | -0.0087 | +0.0106 | -0.0189 | ❌ 3/4 음수 | -0.0061 | 0.0106 |
| **DLBC** | -0.0501 | +0.0155 | -0.0312 | +0.0227 | ❌ 2/4 음수, 2/4 양수 | -0.0108 | 0.0307 |

전체 상세: `reports/exp181_pole_hotspot5/watch_class_stability.json`.

## 승격 기준 대조 (공식 seed 42 기준)

| 기준 | 결과 | 통과 |
|---|---:|---|
| Macro F1 +0.001 이상 | -0.0032 | ❌ |
| fold-std 악화 0.002 미만 | -0.0001(개선) | ✅ |
| Log Loss 악화 없음 | -0.0014(개선) | ✅ |
| 전 클래스 F1 악화 없음 | DLBC -0.0501 | ❌ |

Macro F1 gate와 클래스별 F1 gate 모두 실패해 **기각**한다.

## 해석과 한계

- **COAD는 4개 seed 전부 양의 방향으로 일관됐다.** 크기는 작지만(+0.005~
  +0.015), 22건짜리 sparse feature 치고는 흥미로운 국지적 신호다 —
  Vera Health 도메인 가설(POLE-pd가 COAD에서도 나타남)과 부합하는 유일한
  결과다.
- **UCEC는 일관되지 않았다** — 도메인 가설이 예측한 "UCEC도 개선"은
  이번 4-seed로는 확인되지 않는다.
- **DLBC는 seed 간 부호 자체가 뒤집혀** perturbation 잡음 해석을
  뒷받침한다. row-level 대조 결과(별도 노트
  [`sparse_binary_feature_dlbc_sensitivity.md`](../analysis/sparse_binary_feature_dlbc_sensitivity.md)
  참고) EXP-170과 DLBC "positive로 예측된 집합"이 완전히 동일해 F1이
  같았지만, 이는 우연이 아니라 두 실험 모두에서 DLBC 결정 경계가 실제로
  안정적이라는 뜻이었다. 이번 4-seed 결과는 그 결정 경계 자체가 seed에
  따라 다시 흔들린다는 것을 보여줘, DLBC 하락을 생물학적 신호로 해석하지
  않는다는 결론을 강화한다.
- **공식 판정(seed 42 기준 기각)은 그대로 유지한다** — 프로젝트 컨벤션상
  다른 모든 실험과 동일하게 seed 42만 공식 기록으로 삼는다. 다만 seed
  42가 4개 중 뚜렷한 이상치였다는 사실과 COAD의 일관된 신호는 보고서에
  투명하게 남긴다.

## 다음 실험 후보

- E(`POLE_ED_driver_extended`, 21개 위치, 28건)는 fold 분포가 D보다 덜
  치우쳐 있어({8,5,5,2,8}) 다음 후보로 진행할 가치가 있다. baseline은
  EXP-094(D가 기각됐으므로).
- COAD 방향의 일관된 신호가 흥미로우므로, E/F에서도 COAD F1을 최우선
  관찰 항목으로 유지한다.
- F(`POLE_ED_any_missense`, 41건)는 표본이 가장 많아 seed 민감도가 가장
  낮을 것으로 예상되며, D/E보다 안정적인 판정이 가능할 수 있다.

## 재현과 관련 파일

- Config: `configs/exp181_pole_hotspot5.yaml`
- Resolved config: `reproducibility/exp181_pole_hotspot5/config.resolved.yaml`
- Metrics: `reports/exp181_pole_hotspot5/metrics.json`
- Verdict 상세(stability_check 포함): `reports/exp181_pole_hotspot5/verdict.json`
- UCEC/COAD/DLBC 4-seed per-class 상세: `reports/exp181_pole_hotspot5/watch_class_stability.json`
- Feature 모듈: `src/open_cancer/pole_ed_features.py`
- 검증 스크립트(RUN_MODE=explore, EXP-ID 없음): `scripts/verify_exp181_watch_class_stability.py`
- DLBC 패턴 관련 별도 관찰: `reports/analysis/sparse_binary_feature_dlbc_sensitivity.md`
- Submission: `submissions/exp181_pole_hotspot5.csv` (미제출, 로컬 보관)
- Source commit: `baaf99ab5c5cbf6f26c2492f3620a4f425e25b10` (prepare 커밋)
- Reproduction status: `NOT_STARTED` (일반 Local 실험, 리더보드 미제출)
