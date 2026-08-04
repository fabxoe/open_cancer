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

## 예비 관찰: feature-독립 노이즈 바닥 (n=5, 예비 신호 — 확정 아님)

위 세 진단은 전부 "새 feature를 추가한 채로 hyperparameter만 바꾼"
경우다. feature 자체를 완전히 빼고(순수 EXP-094 v1 base spec, 추가
컬럼 없음) model seed만 바꿔도 DLBC delta가 얼마나 흔들리는지 별도로
확인했다(진단용 ad-hoc, EXP-ID 없음, `seed_base` 5개: 1001/1002/2001/
2002/2003).

| 설정 | delta 평균 | delta 표준편차 |
|---|---:|---:|
| 노이즈 바닥 (`seed_base=1001`, feature 없음) | +0.003342 | 0.042609 |
| 노이즈 바닥 (`seed_base=1002`, feature 없음) | -0.005885 | 0.033197 |
| 노이즈 바닥 (`seed_base=2001`, feature 없음) | +0.005377 | 0.037117 |
| 노이즈 바닥 (`seed_base=2002`, feature 없음) | +0.004920 | 0.050262 |
| 노이즈 바닥 (`seed_base=2003`, feature 없음) | +0.008505 | 0.039438 |

std 5개: `[0.0332, 0.0371, 0.0394, 0.0426, 0.0503]`, 평균 0.0405.
feature 추가 3건의 std `[0.0540, 0.0599, 0.0638]`(평균 0.0593)는
**5개 노이즈 표본 전부보다 크다** — 노이즈 최댓값(0.0503)이 feature
최솟값(0.0540)에 못 미친다(비율 1.46배, 여백 약 7%).

5-seed 간 pairwise delta 상관의 평균은 0.35다(n=2였을 때의 단일 쌍
0.21보다 높음) — 완전 무작위(상관 0)는 아니며, 일부 DLBC 샘플이 seed와
무관하게 경계선에 있어 방향이 약하게 재현되는 성분이 있을 가능성을
시사한다. 이 상관 구조의 원인은 아직 해석하지 않았다.

**이것은 예비 신호이지 확정된 결론이 아니다.** n=5/n=3 표본으로는
formal 통계 검정(t-test 등)을 신뢰할 수 없고, 5/5 완전 분리라는
패턴 자체는 무시하기 어렵지만 표본을 더 늘리면 뒤집힐 가능성을
배제할 수 없다. "feature 추가 효과가 순수 seed 노이즈보다 크다"는
잠정 결론으로 두고, 확정 여부는 추가 seed 확보 이후로 미룬다.

팀의 "소수 클래스 F1 악화 없음" promotion 게이트가 DLBC 같은 극소수
클래스에서는 단일 실행 노이즈(std ~0.04)를 실제 효과로 오판할 위험이
있다는 점은 이미 무시하기 어려운 수준이라고 판단해, 확정 제안이 아닌
"인지 필요 + 논의 필요" 톤으로 별도 팀 공유용 Task Issue
[#254](https://github.com/fabxoe/open_cancer/issues/254)를 열었다.
이 문서(#251)는 조사 스레드 기록이고, 게이팅 기준 변경 여부의 실제
논의와 결정은 #254에서 진행한다.

### 재현성 (PR #255 리뷰 보완)

fabxoe 리뷰(2026-08-03, `CHANGES_REQUESTED`)가 요구한 4개 항목을 모두
추가했다.

1. **Source commit**: 5개 seed 진단은 `08400ad02579d7ffc8745ba139b64d8eaf480b8b`
   (`docs(#251): finalize 5-seed noise-floor observation, open #254 for
   gating policy`, 이 문서를 처음 완성한 커밋)가 HEAD였던 시점에 이
   브랜치에서 실행했다. 입력(`configs/exp094_feature_spec_v1.yaml`,
   canonical train/test/split)은 2026-08-01 이후 변경되지 않아, 그
   사이 다른 브랜치의 무관한 커밋들은 이 결과에 영향을 주지 않는다 —
   아래 SHA-256이 이를 커밋 해시보다 더 직접적으로 보증한다.
2. **재실행 가능한 스크립트**: `scripts/diag_exp094_seed_variant.py
   <seed_base>`(seed별 OOF 생성, EXP-094와 동일 하이퍼파라미터·frozen
   Feature Spec v1) + `scripts/dlbc_5seed_noise_floor.py`(위 표 전체를
   원본에서 재계산). 후자를 그대로 실행하면 이 섹션의 모든 수치가
   재현된다(직접 확인함 — 아래 SHA-256과 함께 실행 로그 재현 완료).
3. **seed별 원본 결과**: 전체 26클래스 OOF 확률 5개는 Git에 커밋하지
   않고 immutable GitHub Release `issue-251-dlbc-noise-floor-v1`의
   `issue-251-dlbc-noise-floor-oof-v1.tar.gz`에 보관한다. 저장소에는
   `_meta.json`(모델 파라미터), `summary.json`(표·상관의 compact 원본),
   재계산 스크립트와 asset SHA-256만 남긴다. 비교 대상인 EXP-094 공식
   baseline OOF도 `scripts/fetch_experiment_artifacts.py --experiment
   EXP-094`로 해당 실험 Release에서 받는다.
   - Release: https://github.com/fabxoe/open_cancer/releases/tag/issue-251-dlbc-noise-floor-v1
   - Release source commit: `858492dd8c04f59acde1e03127b9e20cea953b33`
4. **재계산 설명**: `dlbc_5seed_noise_floor.py`가 baseline과 5개 seed
   OOF의 DLBC 컬럼만 대조해 delta mean/std, 5-seed 분포, pairwise
   correlation, feature-added 3건과의 백분위 비교를 전부 계산한다 —
   위 표의 모든 숫자가 이 스크립트 출력과 정확히 일치함을 확인했다.

Release 원본 회수와 재계산:

```bash
gh release download issue-251-dlbc-noise-floor-v1 \
  --pattern issue-251-dlbc-noise-floor-oof-v1.tar.gz
tar -xzf issue-251-dlbc-noise-floor-oof-v1.tar.gz
uv run python scripts/fetch_experiment_artifacts.py --experiment EXP-094
uv run python scripts/dlbc_5seed_noise_floor.py
```

- Release asset SHA-256:
  `881c81ca163bf5de49a65ee0aaf9647c0cf937d2db5ec02d3a5c702253b709ca`

**Feature Spec v1 입력 identity(SHA-256, 커밋 해시보다 강한 보증)**:

| 항목 | SHA-256 |
|---|---|
| `base_feature_spec_sha256` | `1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3` |
| `source_config_sha256` | `4282727de03bd0f31989fdcce61d65530ba69e339e6dce1fe7f72fa85ebd57c4` |
| `train_input_sha256` | `92418b8441d058cfc68e939dd88725610750be4bc8edc51253cffc72fc4fc0ab` |
| `test_input_sha256` | `e7e7f29a9b6251308e470ae3fb040a6da0cd8fcb0adb87e67f7761631c6a1ef0` |

이 4개 해시가 일치하면 어느 커밋에서 돌리든 동일한 Feature Spec v1
입력(모델 학습 전 단계)임이 보장된다. 5개 raw OOF 파일에는 이 identity가
기록되지 않았지만(진단 스크립트의 이후 버전에서 추가), 위 표는 지금
저장소의 `configs/exp094_feature_spec_v1.yaml`·canonical 데이터로
`materialize_frozen_feature_spec`을 다시 돌려 확인한 현재 값이며, 해당
파일들이 2026-08-01 이후 변경되지 않았으므로 실행 시점과 동일하다.

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
