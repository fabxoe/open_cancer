# Kangho-Park 트랙 결과 요약 (#335 최종 포트폴리오 감사 기여)

> #335(최종 후보 포트폴리오·재현성 감사)를 위한 우리 트랙 결과 정리.
> 발표자료 초안 작성 시 그대로 인용 가능하도록 핵심 수치와 판단만 압축했다.

## 요약표

| Issue/PR | 주제 | 방법 | 핵심 결과 | 판단 |
|---|---|---|---|---|
| [#295](https://github.com/fabxoe/open_cancer/issues/295) / [PR #320](https://github.com/fabxoe/open_cancer/pull/320) | Hotspot burden-confound 방법론 | 240개 DominoEffect 후보를 burden ratio로 스크리닝, target-informed exploratory QC로 재문서화 | PIK3CA 88 burden_confounded_candidate(ratio 3.218) 확인, ACC 클러스터 오염 아님을 재확인 | 방법론 정착, 표준 5단계(Vera→burden→분포→dedup→안정성) 절차의 출처 |
| [#251](https://github.com/fabxoe/open_cancer/issues/251) / [#254](https://github.com/fabxoe/open_cancer/issues/254) | DLBC 극소수 클래스 노이즈 바닥 | feature 무변경 상태로 seed만 바꿔 5회 반복, delta std 분포 확인 | 노이즈 바닥 std 평균 0.0405(n=5) vs feature 추가 3건 std 평균 0.0593 — 마진 7%로 좁음 | 결론 보류(공식 게이팅 임계값 변경까지는 안 감), "DLBC 단일 fold delta 과대해석 금지"라는 세션 전체의 해석 원칙으로 남음 |
| [#296](https://github.com/fabxoe/open_cancer/issues/296) | CTNNB1 D32/S33 hotspot 확장 | EXP-094 + D32/S33 컬럼 2개, 공식 seed + 3-seed 안정성 체크 | OOF 델타 +0.0003548(게이트 미달), fold_std +0.0021(게이트 미달), worst per-class F1 -0.0472 | REJECTED(NOT ADOPTED) — 표준 5단계 파이프라인의 전례로 이후 NPM1 288/#440에 재사용 |
| [#367](https://github.com/fabxoe/open_cancer/issues/367) / [#382](https://github.com/fabxoe/open_cancer/issues/382) | 오답률 상위 8개 클래스(KIRC/KIPAN/GBMLGG/PAAD/SARC/CESC/LIHC/HNSC) 종합 조사 | 문헌 driver 스크리닝 + burden-confound + confusion pair 분석 | KIRC/KIPAN/GBMLGG 3개는 TCGA 라벨 계층 중복(구조적, 해결 불가) 확인; 나머지 5개는 신호가 위치로 안 응축되거나 타 암종이 선점 | 패널 기반 hotspot 확장 트랙 공식 종료 — 명확한 부정 결과, 리소스 낭비 방지 |
| [#421](https://github.com/fabxoe/open_cancer/issues/421) / [PR #426](https://github.com/fabxoe/open_cancer/pull/426) | #292 family-AUC parser v4 오염 여부 재검증 | EXP-392 parser로 5개 family AUC 재계산 + range_stop/no_change 2개 추가 | `sample_aggregate_burden` AUC 0.7298→0.7303(사실상 무변화) — 오염 아니었음 확인 | #351(shift-AUC 재가중) 기각 사유가 오염 때문이 아니었음을 확정, 원 진단(#292) 신뢰도 강화 |
| [#440](https://github.com/fabxoe/open_cancer/issues/440) | EGFR A289/G598 + NFE2L2 E79 hotspot 확장 | EXP-374 + hotspot 3컬럼, burden-clean 확인된 대기열 후보 | Macro F1 +0.0002313605(게이트 미달)·Log Loss +0.0184311867 악화 | REJECTED — CTNNB1 D32/S33(#296)에 이어 두 번째로 기각된 hotspot 확장, burden-clean+문헌 타당성만으로는 모델 게이트 통과를 보장 못 함을 재확인 |
| [#449](https://github.com/fabxoe/open_cancer/issues/449) / [PR #452](https://github.com/fabxoe/open_cancer/pull/452) | LightGBM on EXP-374(모델 다양성, #342 대체) | EXP-374와 동일 feature set, EXP-209 고정 하이퍼파라미터 | OOF 0.4220549915(예상대로 EXP-374보다 낮음), 라벨 불일치율 23.1% | 다양성 게이트 통과 → #450 블렌드로 진행 |
| [#450](https://github.com/fabxoe/open_cancer/issues/450) / [PR #454](https://github.com/fabxoe/open_cancer/pull/454) | EXP-374+EXP-449 0.5/0.5 블렌드 | 고정 산술평균 + `train_domain_propensity.csv` test-like 서브셋 필수 검증 | 전체 OOF +0.0004787061(게이트 미달), **test-like 서브셋 -0.0104454301** | REJECTED — EXP-253과 동일한 Local-pass/test-like-fail 패턴 재현, Public 제출 없이 로컬에서 사전 차단(propensity 체크 설계의 실효성 입증) |
| [#457](https://github.com/fabxoe/open_cancer/issues/457) / [PR #460](https://github.com/fabxoe/open_cancer/pull/460) | EXP-374+EXP-449 outer-fold cross-fitted 로지스틱 회귀 stacking | 52차원(두 모델의 26-class 확률) 입력, `C=0.2` 강한 L2, outer 5-fold cross-fit(EXP-137 전례) + test-like 서브셋 필수 검증 | 전체 OOF -0.0286764512(게이트 대폭 미달), **test-like 서브셋 -0.0472554605**(전체보다 더 악화), LGG/DLBC F1 -0.37~-0.41 붕괴(LGG 228건 중 204건이 GBMLGG로 오분류) | REJECTED — EXP-137과 동일한 메커니즘(강한 L2 다항 로지스틱 stacking의 소수 클래스 붕괴)의 두 번째 독립 확인. 고정 블렌드(#450)에 이어 stacking도 test-like 서브셋에서 실패 — EXP-374+EXP-449 앙상블 트랙 자체를 당분간 보류 |

## 방법론적 기여 (일회성 결과보다 재사용 가치가 큰 것들)

1. **5단계 hotspot 사전검증 표준화**(Vera 게이트 → burden 교란 → 암종 배타성 → semantic dedup → multi-seed 안정성) — #295/#296/#329(NPM1)/#440에서 반복 재사용.
2. **Gate C(dominance≥0.8) 예외 처리 선례** — NPM1 288에서 "dominance=1.0이 위험 신호가 아니라 생물학적으로 정확한 신호일 수 있다"는 반례를 문서화(#254 참고 케이스로 연결).
3. **fold-safe 원칙 위반의 실증 사례**(#392 discrepancy) — 같은 아이디어(range_stop/no_change indicator)를 독립적으로 두 가지 방식으로 구현했을 때, 후보 선정 범위(global vs per-fold outer-train)가 결과 부호를 실제로 뒤집을 수 있음을 보여준 교육적 사례.
4. **propensity 기반 test-like 서브셋 사전 검증의 실효성 입증**(#450, #457) — EXP-253이 Local 게이트를 통과하고도 Public에서 -0.0178 무너졌던 실패를, 이번엔 같은 조합(XGBoost+LightGBM)의 블렌드(#450)와 stacking(#457) 두 시도 모두 Public 제출 없이 로컬 test-like 서브셋 체크만으로 사전 차단. 두 실패는 메커니즘이 다르다(#450: 같은 shift 분포 노출로 bias 증폭, #457: 강한 정규화 stacking의 소수 클래스 붕괴)는 점에서, 이 체크가 특정 실패 유형이 아니라 "test 분포에 가까운 샘플에서의 실제 성능"이라는 일반적 기준으로 유효함을 보여준다. 앞으로 모델 다양성/블렌드/스태킹 시도에 재사용 가능한 완료 조건 템플릿(`scripts/check_exp450_test_like_subset.py`, `scripts/check_exp457_test_like_subset.py`).

## 재현성 상태

- #295/#296/#367/#421/#440/#449/#450/#457: 전부 스크립트+원본 데이터 커밋 완료, 재실행 가능. #440/#449/#450/#457은 INFERENCE_VERIFIED까지 자동 완료.
- #251/#254: 진단 전용(analysis-only), EXPERIMENT_HISTORY 미등록(원래 설계대로).

## 현재 팀 production 계보 상태 (2026-08-05 기준)

N4 3-arm 비교(L=Legacy/C=Compatibility/N=Native, #433/#435/#438)가 완료됐다.
**N(native) OOF 0.4102050373로 L(0.4132763)·C(0.4111034)보다 낮고 PAAD F1
-0.0568로 클래스 붕괴 게이트도 미달 — N5(baseline 동결) 보류.** 즉
**EXP-374/392(legacy/stop-v2 계보)가 현재도, 당분간도 팀의 유효한 parent**다.
이 문서의 모든 결과(#296/#440 포함)는 legacy 계보 기준이며, N5가 나올 때까지
재작업 필요가 없다.

## 참고

- 전체 팀 로드맵 맥락: [`annotation_invariant_parser_roadmap.md`](../plans/annotation_invariant_parser_roadmap.md), [`parser_v4_baseline_reset_roadmap.md`](../plans/parser_v4_baseline_reset_roadmap.md)
- 최종 포트폴리오 감사 상위 Issue: [#335](https://github.com/fabxoe/open_cancer/issues/335)
