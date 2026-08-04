# EXP-253 LightGBM·XGBoost 고정 확률 평균

## 결론

EXP-209 LightGBM과 EXP-229 XGBoost의 예측 확률을 `0.5/0.5`로 평균한 결과,
OOF Macro F1은 **0.4254998819**로 현재 Local 최고를 갱신했습니다. EXP-229보다
`+0.0025113074` 높고 Log Loss도 `-0.0406361619` 개선됐습니다.

Fold 표준편차는 `+0.0019120085` 증가했지만 사전 허용 기준 `0.002` 이내였습니다.
그러나 Public Macro F1은 **0.3054410279**로 EXP-223의 `0.323243525`보다
`-0.0178024971` 낮았습니다. Local 개선이 Public으로 전이되지 않아 최종 제출
후보에서는 제외합니다.

## 무엇을 결합했나

- EXP-209: fixed pathway burden을 사용하는 LightGBM
- EXP-229: pathway별 변이 종류 유전자 수를 사용하는 XGBoost
- 각 클래스 확률을 정확히 `0.5 × EXP-209 + 0.5 × EXP-229`로 평균
- 고정 26개 클래스 순서에서 평균 확률이 가장 큰 암종을 최종 예측

두 부모의 OOF는 같은 ID·정답·canonical fold·클래스 순서로 정렬됐고 test 확률도
같은 ID 순서임을 runner가 검사했습니다. 모델 재학습, 다른 가중치 탐색, test 분포
및 Public LB 기반 선택은 수행하지 않았습니다.

## 실제 결과

| 항목 | EXP-253 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4254998819 | 0.4229885745 | +0.0025113074 |
| Fold 표준편차 | 0.0117799734 | 0.0098679649 | +0.0019120085 |
| Accuracy | 0.4136429608 | 0.4125141106 | +0.0011288502 |
| Log Loss | 1.8103251656 | 1.8509613276 | -0.0406361619 |

### Public 제출

- 제출 ID: `1509964`
- 제출 시각: 2026-08-03 23:32:05 KST
- Public Macro F1: `0.3054410279`
- EXP-223 Public 대비: `-0.0178024971`
- 확인 당시: 참가 4팀 중 4위, 팀 제출 18회
- 팀 선택 제출: EXP-223 유지

| Fold | Macro F1 |
|---:|---:|
| 0 | 0.4204437403 |
| 1 | 0.4242324556 |
| 2 | 0.4163290146 |
| 3 | 0.4179312082 |
| 4 | 0.4484189232 |

EXP-229 대비 큰 개선은 TGCT `+0.0837`, DLBC `+0.0259`, PRAD `+0.0166`,
LIHC `+0.0149`, PCPG `+0.0144`, UCEC `+0.0140`입니다. 큰 하락은 ACC
`-0.0311`, LUAD `-0.0298`입니다. 여러 클래스에서 이득과 손실이 함께 나타나므로
모든 암종에 일괄적으로 좋아졌다고 해석하지 않습니다.

## 해석과 한계

서로 다른 tree model과 피처 구성이 같은 샘플에서 완전히 동일한 오류를 내지 않아,
확률 평균이 일부 과신과 오류를 상쇄한 것으로 해석할 수 있습니다. Log Loss의 큰
개선도 평균 확률이 단일 모델보다 안정적이라는 설명과 일치합니다.

Fold 안정성 기준을 `0.000088` 차이로 근소하게 통과했지만 Public에서는 큰 폭으로
하락했습니다. 원인은 test 정답이 없어 확인할 수 없으며 LightGBM 성분, 데이터
분포 차이 또는 Public 표본 변동 중 무엇이 원인인지는 단정하지 않습니다. 같은
OOF와 Public 결과를 본 뒤 세밀한 가중치 grid search를 수행하면 역튜닝 위험이
있으므로 EXP-253에는 추가하지 않습니다.

## 다음 단계

- EXP-253은 Local 분석 자산으로 보존하되 추가 Public 제출 후보에서는 제외합니다.
- Local–Public 괴리는 별도 분석 Task에서 기존 제출 전체를 대상으로 검토합니다.
- Issue #233의 class-wise decision offset과 구현·결과를 섞지 않습니다.

## 재현과 관련 파일

- Issue: [#253](https://github.com/fabxoe/open_cancer/issues/253)
- 실행 source commit: `b9d296ea164beb4b33e5797b7b1b08eee45f54f9`
- Config: `configs/exp253_lightgbm_xgboost_blend.yaml`
- Resolved config: `reproducibility/exp253_lightgbm_xgboost_blend/config.resolved.yaml`
- Metrics: `reports/exp253_lightgbm_xgboost_blend/metrics.json`
- 제출 파일: `submissions/exp253_lightgbm_xgboost_blend.csv` (제출 ID `1509964`)
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [`exp-253-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-253-repro-v1)

저장된 부모 확률에서 OOF·test 라벨이 100% 일치하고 확률 최대 차이 0,
제출 CSV SHA-256 일치를 확인했습니다. Issue #260에서 EXP-209·229 부모 checkpoint
10개와 component OOF/test/config를 함께 deterministic bundle로 보존하고 원격
재다운로드 SHA-256 일치를 확인했습니다.
