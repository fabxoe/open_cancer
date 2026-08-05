# Legacy(EXP-374/459/484) × Native(EXP-479) 블렌드 사전 스크리닝 (#292 test-like propensity 게이트)

`analysis_only` — Task #489. 새 모델 학습 없음(EXP-479 재현은 로컬에
checkpoint/확률이 없어 기존 기록값을 재현하는 목적, EXP-459가 EXP-374에 대해
했던 방식과 동일), EXP-ID 없음. 재실행:

```bash
uv run python scripts/audit_exp479_legacy_native_diversity.py
uv run python scripts/screen_exp479_legacy_native_blend_propensity.py
```

## 배경

Model-diversity/ensemble 트랙(EXP-449→459→484)은 legacy parser(stop 표기
정규화 + Ensembl isoform mask) 기반 EXP-374 위에서 진행됐다. 별도로 진행된
parser v4-native baseline reset 로드맵(#422)은 N5(EXP-479, native semantic
parser 기준선)까지 동결을 완료했고, 팀 전체 신규 모델 실험 금지가 풀렸다. 두
트랙이 서로 다른 parser lineage로 병렬 진행된 만큼, 확률 블렌드로 다양성을
얻을 수 있는지 정식 Experiment Issue를 열기 전에 먼저 확인한다.

EXP-479(native, parent EXP-469)는 OOF `0.4087566023`로 legacy 트랙(EXP-374
`0.4267909268`, EXP-484 `0.4320213767`)보다 낮고, hotspot·pathway·
residue-position 등 추가 피처가 아직 없는 가벼운 기준선이다(N8 단계
PLANNED) — EXP-465(hotspot-only/pathway-only subset 블렌드가 feature-poor
parent라 REJECTED된 사례)와 유사한 실패 위험을 사전에 염두에 두고
스크리닝했다.

## 1단계 — EXP-479 재현 검증

Release checkpoint가 없어(EXP-374와 동일 상황) 별도 git worktree(source
commit `8a6010d`, `scripts/run_exp479_parser_v4_native_semantic_range.py`)에서
재실행했다. 재현 OOF Macro F1 `0.40875660230173333`가 기록값
`0.4087566023`과 byte-level로 일치했다(fold별 값도 전부 일치, fold0
`0.3984987531132906` 등).

## 2단계 — 다양성 게이트

`scripts/audit_exp479_legacy_native_diversity.py` 결과
(`diversity_gate.json`), 기준은 PROJECT_CONTEXT.md 스태킹 조건(오류 상관
≤0.92 또는 라벨 불일치 ≥10%):

| 비교 | OOF 오류 상관 | 예측 라벨 불일치율 | gate |
|---|---:|---:|---|
| EXP-479 vs EXP-374 | 0.7877601378 | 22.8350266086% | PASS |
| EXP-479 vs EXP-459 | 0.7061507568 | 29.8661506209% | PASS |
| EXP-479 vs EXP-484 | 0.8028822386 | 21.2546363490% | PASS |

세 비교 모두 통과했다.

## 3단계 — test-like propensity 블렌드 스크리닝

`scripts/screen_exp479_legacy_native_blend_propensity.py` 결과
(`screening.json`). 방법:

- test-like subset: `train_domain_propensity.csv`(#292)의
  `oof_test_domain_probability` 상위 25%(quantile 0.75 threshold
  `0.2500581443`, #450/457/464/465/482와 동일 정의) — 1,666/6,201행.
- 블렌드: `w * EXP-484 확률 + (1-w) * EXP-479 확률`의 argmax, `w ∈
  {0.9, 0.8, 0.7, 0.6, 0.5}`.
- 기준선: EXP-484 단독 Macro F1(전체 `0.4320213767`, test-like subset
  `0.4306738997`).

| EXP-484 weight | 전체 OOF Macro F1 | 전체 delta | test-like Macro F1 | test-like delta | gate |
|---:|---:|---:|---:|---:|---|
| 0.9 | 0.4323111090 | +0.0002897324 | 0.4273567042 | -0.0033171955 | FAIL |
| 0.8 | 0.4268757373 | -0.0051456394 | 0.4223079622 | -0.0083659375 | FAIL |
| 0.7 | 0.4235780892 | -0.0084432875 | 0.4174023166 | -0.0132715831 | FAIL |
| 0.6 | 0.4197329630 | -0.0122884137 | 0.4139301493 | -0.0167437504 | FAIL |
| 0.5 | 0.4196721106 | -0.0123492661 | 0.4101923201 | -0.0204815796 | FAIL |

## 해석

다섯 비율 전부 test-like gate에 실패했다. 0.9/0.1에서만 전체 OOF가 미세하게
개선(+0.0003)했지만 test-like subset은 이미 악화(-0.0033)했고, native 비중이
늘어날수록 전체·test-like 두 지표 모두 계속 나빠진다. EXP-459(CatBoost)
블렌드 때와 달리 "parent와 오류 상관이 충분히 낮으면 다양성 이득이 생긴다"는
패턴이 재현되지 않았다 — EXP-479가 legacy 트랙과 오류 상관은 낮지만(0.71~0.80,
EXP-459의 0.66과 비슷한 수준), **단독 성능 자체가 legacy 트랙보다 크게 낮고
(hotspot·pathway·residue-position 미포함) feature 차원이 훨씬 작아서**, 다른
parser를 쓴다는 이점보다 정보 손실이 더 크게 작용한 것으로 보인다. 이는
EXP-465(hotspot-only/pathway-only subset 블렌드가 "가설 설계 결함"으로
REJECTED된 사례)와 같은 실패 메커니즘이다.

## Go/No-Go

**NO-GO** — 어떤 비율도 test-like gate를 통과하지 못해, 이 조합의 블렌드는
정식 Experiment Issue로 진행하지 않는다. Legacy×Native 교차 블렌드를 다시
시도하려면 native 트랙이 N8(pathway·hotspot 재검증·Feature Spec 동결) 이후
더 완전한 피처셋을 갖춘 뒤가 적절해 보인다.

## 제약

- SUBCLASS는 Macro F1 계산에만 사용했고 학습 전처리에는 사용하지 않았다.
- `train_domain_propensity.csv`는 기존에 팀장 검토로 analysis-only 승인된
  자산을 재사용했을 뿐 test 데이터를 새로 참조하지 않았다.
- Public LB는 사용하지 않았다.
- `EXPERIMENT_HISTORY.md`는 변경하지 않았다(Task, EXP-ID 없음).
