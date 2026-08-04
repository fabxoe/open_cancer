# EXP-369 stop 표기 정규화 단독 ablation

## 결론

`R213*`, `R213X`, `R213Ter`처럼 같은 stop-gain을 나타내는 세 표기를 모든
EXP-229 피처 경로에서 동일한 `nonsense` 의미로 정규화했다. OOF Macro F1은
`0.4229885745`로 EXP-229와 정확히 같았다. 이는 train의 기존 `*` 표기 의미와
모델 학습 결과를 보존했다는 강한 양성 대조다.

반면 test에서는 2,546행 중 875행의 확률이 바뀌었고 347행(13.63%)의 최종
예측 라벨이 달라졌다. 따라서 이 수정은 사소한 문자열 정리가 아니라, train에는
주로 `*`, test에는 주로 `X`로 기록된 동일 생물학적 사건을 같은 피처 공간으로
복원한 의미 있는 분포 보정이다. Public Macro F1은 `0.3407944343`으로
EXP-229보다 `+0.0204345510`, 기존 팀 최고 EXP-223보다 `+0.0175509093`
상승해 팀 최고를 갱신했다.

## 실험 계약

- Issue/브랜치: #369 / `issue-369-exp-stop-notation-normalization`
- 부모: EXP-229
- canonical stratified 5-fold, seed 42와 26개 클래스 순서 고정
- 모델·하이퍼파라미터·balanced sample weight·Macro-F1 checkpoint 정책 고정
- pathway·hotspot 목록과 전체 feature 이름·차원 고정
- 유일한 변경: simple stop alternate `*`, `X`, `Ter`를 stop-gain/nonsense로 통일
- 적용 경로: base mutation type, hotspot, pathway LoF, pathway mutation type
- 보존: token multiplicity와 stop 이외의 모든 v1 parser 규칙
- 제외: 음수 위치 sanitation, 부분·비표준 표기 일반화, synonymous 제거
- SUBCLASS·test 분포·Public LB는 규칙 정의나 모델 선택에 사용하지 않음

## 결과

| 지표 | EXP-369 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4229885745 | 0.4229885745 | 0.0000000000 |
| Fold 평균 | 0.4232332489 | 0.4232332489 | 0.0000000000 |
| Fold 표준편차 | 0.0098679649 | 0.0098679649 | 0.0000000000 |
| Accuracy | 0.4125141106 | 0.4125141106 | 0.0000000000 |
| Log Loss | 1.8509613276 | 1.8509613276 | 0.0000000000 |

Fold Macro F1은 `0.4125154 / 0.4227303 / 0.4172366 / 0.4221575 /
0.4415264`이며 선택 iteration은 `208 / 194 / 261 / 94 / 161`이다.
OOF 예측과 클래스별 F1도 EXP-229와 동일하다.

## Test 영향 감사

EXP-229와 EXP-369의 test 확률을 ID·26개 클래스 고정 순서로 직접 비교했다.

- 확률이 `1e-6`보다 크게 바뀐 행: 875 / 2,546 (34.37%)
- argmax·submission 라벨이 바뀐 행: 347 / 2,546 (13.63%)
- 전체 확률 원소 평균 절대 차이: `0.0067740004`
- 최대 절대 확률 차이: `0.8442194160`

이 수치는 정규화가 test 예측을 크게 바꾼다는 사실만 보여준다. 정답이 없는
test에서 어느 방향이 맞는지는 알 수 없으며, Public 점수를 이용해 규칙을 다시
조정하지 않는다.

## Public LB 결과

- 제출 시각: 2026-08-04 17:49:07 KST
- 제출 ID: `1510848`
- Public Macro F1: `0.3407944343`
- EXP-229 Public `0.3203598833` 대비: `+0.0204345510`
- 기존 팀 최고 EXP-223 `0.323243525` 대비: `+0.0175509093`
- 확인 당시 참가 4팀 중 4위, 팀 제출 23회

모델·fold·seed·피처 이름·OOF가 같은 상태에서 stop 표기 해석만 달랐으므로,
이 큰 Public 상승은 parser 정규화 효과에 대한 강한 인과 증거다. 다만 과거의
모든 실패 실험이 parser 하나로 설명된다는 뜻은 아니다. train/test annotation
shift가 컸던 stop 계열에서 parser가 가장 큰 Public 병목이었다고 해석한다.

## 재현성

- 소스 commit: `f49bf2209b22492d11bc5c31ab76de9af3946b59`
- Config: `configs/exp369_stop_notation_normalization.yaml`
- Runner: `scripts/run_exp369_stop_notation_normalization.py`
- Metrics: `reports/exp369_stop_notation_normalization/metrics.json`
- OOF: `oof/exp369_stop_notation_normalization.csv`
- test 확률: `preds/exp369_stop_notation_normalization_test_proba.csv`
- submission: `submissions/exp369_stop_notation_normalization.csv`
- submission SHA-256:
  `9c1fad8c118928f23157b7558a1b73fa16af22a34966a244841ac539fed5bdd3`
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [exp-369-repro-v1](https://github.com/fabxoe/open_cancer/releases/tag/exp-369-repro-v1)
- Release bundle SHA-256:
  `17a307d755099bfb474ed61eb225a57bc63148095fd0c083f09201de967452cf`
- checkpoint 재추론: submission SHA-256 byte-level 일치, test 라벨 100%,
  확률 최대 차이 `1.40e-7`

## 판단과 다음 행동

parser 의미 계약과 train 불변성, Public 전이가 모두 확인됐다. EXP-369의 stop
정규화는 후속 모델의 기본 parser contract로 승격한다. 위치 sanitation과
synonymous 처리는 효과를 섞지 않도록 각각 별도 Issue·EXP-ID로만 평가한다.
