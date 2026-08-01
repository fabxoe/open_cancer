# 동결 Feature Spec·공통 모델 runner 계약

> 일반 Task Issue #121의 구현·검증 기록이다. 공식 실험, Local OOF 점수 또는
> 리더보드 결과가 아니다.

## 목적

ABC-Stack의 모델 다양화 단계에서 모델마다 다른 피처 생성 코드와 확률 파일
형식을 사용하지 않도록 하나의 실행 경계를 제공한다. Feature Spec은 이름으로만
선택하며, 모델 adapter는 동일한 canonical 5-fold와 26개 클래스 순서를 사용한다.

## 동결 Feature Spec

| 이름 | 구성 | 실제 train shape | 실제 test shape |
|---|---|---:|---:|
| `v1` | EXP-094 | `(6201, 35119)` | `(2546, 35119)` |
| `v2-performance` | EXP-094 + fixed pathway burden 20개 | `(6201, 35139)` | `(2546, 35139)` |
| `v2-diversity` | EXP-094 + amino-acid change 4개 | `(6201, 35123)` | `(2546, 35123)` |

세 구성 모두 EXP-094 base Feature Spec SHA-256
`1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3`을
확인했다. 결합 과정에서 기존 피처와 의미가 같은 추가 열은 발견되지 않았다.

## 모델·산출물 계약

- 지원 adapter: Logistic Regression, XGBoost, LightGBM, CatBoost
- 공용 split: fold `0..4`
- 클래스 순서: `open_cancer.constants.CLASS_LABELS`
- OOF: `(6201, 26)` 확률과 ID·정답·예측·fold
- test: `(2546, 26)` 확률과 ID
- 저장 파일: `oof_predictions.csv`, `test_probabilities.csv`, `metrics.json`,
  fold별 checkpoint
- LightGBM·CatBoost는 선택한 실험에서만 experiment dependency group을 설치

## 운영 경계

이 Task에서는 실데이터 matrix identity만 검증하고 모델은 synthetic fixture로만
smoke했다. 따라서 EXP-ID를 발급하거나 `EXPERIMENT_HISTORY.md`에 점수 행을
추가하지 않는다. 다음 공식 비교는 별도 Experiment Issue에서 동결 spec 하나와
모델 하나를 선택해 수행하고, resolved config와 OOF/test 확률을 모두 보존한다.
