# EXP-370 EXP-223 stop 표기 정규화 이식 검증

## 결론

EXP-223의 피처·모델 설정에 simple stop alternate `*`, `X`, `Ter` 정규화를
이식해 다시 학습했다. EXP-370의 OOF Macro F1은 `0.4195957914`이고 저장된
checkpoint의 재추론은 완전히 검증됐다.

하지만 train.csv에는 정규화 대상인 `X`와 `Ter` simple stop token이 모두
0건이었다. 따라서 정규화는 EXP-370 train 특징을 변경하지 않는다. 현재
source에서 재학습한 EXP-370과 역사적 source에서 실행된 EXP-223의 OOF 차이는
stop 표기 정규화 효과로 해석하지 않는다.

또한 EXP-223 test 확률 원본이 보존되지 않아 두 실험의 test 예측 변화량은
측정하지 못했다. EXP-370 자체의 추론 재현성은 확인했지만, 이것이 EXP-223과
예측이 같다는 뜻은 아니다.

## 실험 계약

- Issue/브랜치: #370 / `issue-370-exp-exp223-stop-normalization`
- 부모: EXP-223
- canonical stratified 5-fold, seed 42와 26개 클래스 순서 고정
- EXP-223 피처 family, XGBoost 파라미터, balanced sample weight와 Macro-F1
  checkpoint 정책 사용
- 변경 의도: simple stop alternate `*`, `X`, `Ter`를 모든 관련 피처 경로에서
  동일한 nonsense 의미로 정규화
- Public LB와 test 분포는 규칙 정의나 모델 선택에 사용하지 않음

## 결과

| 지표 | EXP-370 | 역사적 EXP-223 | 단순 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4195957914 | 0.4213739476 | -0.0017781562 |
| Fold 평균 | 0.4194923535 | 미비교 | 미측정 |
| Fold 표준편차 | 0.0108391780 | 미비교 | 미측정 |
| Accuracy | 0.4100951459 | 미비교 | 미측정 |
| Log Loss | 1.8631492853 | 미비교 | 미측정 |

Fold Macro F1은 `0.4152716087 / 0.4148617360 / 0.4084748563 /
0.4187167281 / 0.4401368382`이며 선택 iteration은 `162 / 219 / 127 / 86 /
144`이다.

표의 OOF 차이는 서로 다른 시점의 source에서 학습된 결과를 단순 병기한
것이다. 정규화의 인과 효과 추정치로 사용하지 않는다.

## Train 불변성 감사

train.csv에서 simple stop alternate 표기인 `X`와 `Ter` token을 검사한 결과
해당 token은 0건이었다. 따라서 stop 표기 정규화 자체는 train 특징을 변경하지
않는다.

다만 EXP-223 실행 이후 공용 runner와 feature 관련 코드가 변경된 현재 source에서
모델을 다시 학습했기 때문에, EXP-370의 OOF 결과는 역사적 EXP-223 결과와
일치하지 않았다. 이 차이를 stop 표기 정규화의 효과로 해석하지 않는다.

## Test 영향 감사 제한

EXP-223의 test 확률 파일이 로컬에 보존되어 있지 않아 EXP-370과의 확률 변화량을
직접 비교하지 못했다. 따라서 test 예측이 변경되지 않았다고 주장하지 않으며,
변경 행 수·평균 확률 차이·최대 확률 차이는 미측정으로 기록한다.

EXP-370 자체의 checkpoint 재추론은 test label 일치율 100%, 확률 allclose 및
submission SHA-256 일치를 통과했다. 이는 EXP-370의 추론 재현성을 의미하며
EXP-223과 예측이 같다는 의미는 아니다.

## 재현성

- 소스 commit: `dbe1e9756b25d348e7e0686f3ef437eb8a982e07`
- Config: `configs/exp370_exp223_stop_notation_normalization.yaml`
- Runner: `scripts/run_exp370_exp223_stop_notation_normalization.py`
- Metrics: `reports/exp370_exp223_stop_notation_normalization/metrics.json`
- Reproduction: `reproducibility/exp370_exp223_stop_notation_normalization/`
- submission: `submissions/exp370_exp223_stop_notation_normalization.csv`
- submission SHA-256:
  `80a8c36182bd3e1812f5707b2d813f0de69fc47722582a00736816bb5d6f5d9f`
- checkpoint 재추론: test label agreement `1.0`, probability allclose,
  최대 절대 차이 `1.720886230183183e-07`, submission SHA-256 일치
- 재현 상태: `INFERENCE_VERIFIED`

## 판단

EXP-370은 실행 및 추론 재현성 기록으로 보존한다. 현재 자료만으로 역사적
EXP-223 대비 stop 정규화의 train 또는 test 효과를 정량화하지 않으며, OOF 차이를
정규화 효과로 홍보하거나 모델 선택 근거로 사용하지 않는다. Public LB에는
제출하지 않았다.
