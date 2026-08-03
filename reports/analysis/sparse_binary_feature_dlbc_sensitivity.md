# 희소 이진 feature 추가 시 DLBC 민감도 관찰

> 새 모델 실험이나 점수를 만들지 않는 target-independent 관찰 기록입니다.
> 실제 실험 결과의 단일 원본은 [`EXPERIMENT_HISTORY.md`](../../EXPERIMENT_HISTORY.md)와
> 실험별 `metrics.json`입니다.

## 관찰

서로 완전히 다른 유전자 세트를 대상으로 한 두 개의 독립적인 pilot 실험
([EXP-170](../exp170_cellcycle_any_nonsilent/README.md), Cell Cycle 15개
유전자 OR / [EXP-181](../exp181_pole_hotspot5/README.md), POLE 5개
hotspot substitution)에서, EXP-094 Feature Spec v1에 희소한 이진 컬럼을
하나만 추가했을 때 **DLBC(38 샘플, 최소 클래스)의 OOF F1이 가장 크게
하락**했다.

| 실험 | 추가 feature | Train 양성률 | DLBC OOF F1 | Baseline(EXP-094) 대비 |
|---|---|---:|---:|---:|
| EXP-170 | `pathway__cellcycle_any_nonsilent` | 8.51% | 0.3272727273 | **-0.0500857633** |
| EXP-181 | `pole__hotspot5` | 0.355% | 0.3272727273 | **-0.0500857633** |

두 실험의 DLBC OOF F1 값은 소수점 10자리까지 **완전히 동일**하다
(`0.32727272727272727` = 18/55). DLBC는 38 샘플뿐이라 F1이 취할 수 있는
값 자체가 이산적이므로, 이 일치가 우연한 비율 일치인지 실제로 같은
예측인지 OOF 파일을 row-level로 직접 대조해 확인했다.

**대조 결과**: DLBC로 "예측"된 샘플 집합은 두 실험에서 17개 ID까지
정확히 동일하다(대칭차집합 = 공집합). F1은 (예측=DLBC 집합, 실제=DLBC
집합)의 교집합에만 의존하므로, 이 두 집합이 문자 그대로 같다는 것은
TP/FP/FN이 **필연적으로** 동일하다는 뜻이다 — 우연한 비율 일치가 아니라
DLBC에 대한 두 모델의 판단이 실제로 같았다. 다만 실제 DLBC 38개 중
2개(`TRAIN_2541`, `TRAIN_6051`)는 두 실험에서 각각 다른 클래스로
오분류됐다(둘 다 DLBC로는 예측되지 않았다는 결과는 같지만, 구체적으로
어느 클래스로 갔는지는 다름 — LIHC→STES, LIHC→LUAD). 즉 두 모델이
bit-identical한 것은 아니고, **DLBC를 positive로 판단하는 결정 경계만
정확히 일치**한다.

이는 특정 재현 가능한 메커니즘(예: `colsample_bytree=0.8` 아래에서 어떤
새 희소 컬럼이든 DLBC 관련 초기 split 후보 선택 확률을 비슷한 방향으로
바꾸는 효과)을 시사하며, 우연으로 축소 해석하지 않는다. 두 경우 모두
EXP-063/078 semantics QC에서 확인된 "중복/약한 컬럼의 weighting
perturbation" 메커니즘과 같은 계열로 해석했다.

## 후속 진단: 원인이 특정 hyperparameter인지 확인 (colsample_bytree / n_jobs)

EXP-170(Cell Cycle any-nonsilent)의 DLBC OOF 확률을 baseline(EXP-094)과
대조해 delta 평균/표준편차를 구한 뒤, feature와 fold/split은 그대로 두고
학습 설정 하나씩만 바꾼 진단용 ad-hoc 재학습(EXP-ID 없음, History 미기록)
2건을 추가로 실행했다.

| 설정 | delta 평균 | delta 표준편차 | argmax lost/gained |
|---|---:|---:|---|
| 원래 EXP-170 (`colsample_bytree=0.8`, `n_jobs=8`) | -0.002986 | 0.054009 | 2/1 |
| 진단1 (`colsample_bytree=1.0`, `n_jobs=8`) | +0.003233 | 0.063833 | 3/2 |
| 진단2 (`colsample_bytree=0.8`, `n_jobs=1`) | +0.002293 | 0.059927 | 2/0 |

**결론: 특정 hyperparameter가 원인이 아니다.** `colsample_bytree=1.0`(컬럼
서브샘플링 제거)과 `n_jobs=1`(스레딩 비결정성 제거) 둘 다 delta를 0으로
수렴시키지 못했다 — 오히려 표준편차가 원래보다 커졌고, 부호는 두 진단
모두 원래와 반대(+)로 나타났다. 세 설정이 공통으로 보여주는 건 "특정
원인 하나"가 아니라 **DLBC(38건, 최소 클래스)가 학습 설정의 거의 어떤
변화에도 비슷한 크기(표준편차 0.054~0.064)로, 하지만 방향은 예측 불가능하게
흔들리는 구조적 민감성**이다.

이는 [#238](https://github.com/fabxoe/open_cancer/issues/238)(플랫폼 간
`tree_method=hist` 비결정성으로 EXP-219 재현이 SHA-256/Macro F1 단위로
실패한 문제)과 **메커니즘이 다르다** — #238은 동일 코드·동일 seed에서
플랫폼(OS/컴파일러)만 바꿔도 학습 결과 자체가 갈라지는 문제이고, 이번
관찰은 같은 플랫폼(Windows) 안에서 seed·플랫폼을 전혀 안 바꿔도 학습
설정 하나만 바꾸면 DLBC가 비슷한 크기로 흔들린다는 관찰이다. 두 현상이
"모델 학습이 예민하다"는 상위 주제는 공유하지만, 원인 축(플랫폼/스레딩
비결정성 vs 클래스 자체의 구조적 민감성)은 서로 다르므로 대책도 같이
묶어 설계하지 않는다.

## 권장 사항

향후 유사한 실험(EXP-094 v1에 양성 건수 50건 미만의 희소 이진 컬럼 1개를
추가하는 pilot)을 설계할 때는 사전 체크리스트에 다음을 포함한다.

1. DLBC OOF F1 변화를 결과 표 최상단에 별도로 명시한다(다른 클래스와 묶어서
   보고하지 않는다).
2. 새 feature의 DLBC 샘플 내 양성률을 사전에 확인한다(0%일 수 있음 —
   EXP-173처럼 feature 값이 항상 0이어도 perturbation 효과는 발생할 수
   있다).
3. 소수 클래스는 F1이 이산값이라 다른 실험과 수치가 우연히 같아 보일 수
   있다. F1 값만 비교하지 말고 OOF 예측 파일에서 실제 예측 클래스를
   row-level로 대조해, "판단 근거가 정말 같은지"(예측=positive 집합이
   동일한지) 확인한 뒤 결론을 기록한다.
4. DLBC F1이 크게(대략 -0.03 이상) 하락하면, 이를 "이 feature가 DLBC에
   생물학적으로 해롭다"는 신호가 아니라 우선 perturbation 후보로 취급하고,
   다른 클래스·다른 seed에서의 패턴과 함께 판단한다.

## 관련 실험

- [EXP-170](../exp170_cellcycle_any_nonsilent/README.md) — Cell Cycle
  any-nonsilent, 기각
- [EXP-173](../exp173_cellcycle_lof_tsg/README.md) — Cell Cycle TSG LoF,
  기각(다른 클래스 DLBC/LAML은 양성률 0%인데도 반대 방향으로 움직여 같은
  perturbation 해석을 뒷받침)
- [EXP-181](../exp181_pole_hotspot5/README.md) — POLE ED hotspot5, 기각
