# EXP-476 config 기반 Feature Pipeline 검증

## 목적과 범위

YAML config로 데이터·피처·nested Optuna·class weight·XGBoost 설정을 외부화한
파이프라인을 공식 canonical 5-fold에서 검증했다. 각 outer fold의 recurrent gene
mask와 26개 class panel은 해당 outer-train에서만 fit했고, Optuna 탐색과 class
weight power 선택도 inner fold 안에서만 수행했다. test는 transform-only로
사용했으며 oversampling과 SMOTE는 사용하지 않았다.

## 실행 결과

실행 명령:

```bash
uv run python scripts/run_exp476_config_feature_pipeline.py
```

| 지표 | 결과 |
|---|---:|
| OOF Macro F1 | 0.4223302641 |
| Fold 평균 | 0.4221662638 |
| Fold 표준편차 | 0.0063798943 |
| OOF Accuracy | 0.4117077891 |
| OOF Log Loss | 1.8164755106 |
| 실행 시간 | 1,456.53초 |

Fold Macro F1:

```text
0.4223615311 / 0.4194144480 / 0.4117593358 / 0.4299849068 / 0.4273110972
```

참고 기준인 EXP-374와 비교하면 OOF Macro F1은 `-0.0044606627` 낮다. 다만
EXP-476의 fold 표준편차는 `0.0063798943`으로 EXP-374의 `0.0085032169`보다
낮아 fold 간 변동성은 작았다.

## Public leaderboard

- 제출 ID: `1512307`
- 제출 시각: 2026-08-05 19:05:30 KST
- Public Macro F1: `0.3223948042`
- 팀 최고 EXP-374(`0.346215922`) 대비: `-0.0238211178`
- 확인 당시 팀 순위: 4위
- 확인 당시 팀 제출 수: 25회
- 대표 제출: EXP-374 유지

Public 결과는 사용자가 제공한 DACON 제출·리더보드 스크린샷에서 확인했다.
EXP-476은 Local과 Public 모두 현재 대표 모델을 넘지 못했으므로 최종 선택
제출에는 반영하지 않는다.

## 재현성

재현 상태는 `INFERENCE_VERIFIED`다. 저장된 5개 XGBoost checkpoint를 fold별
고정 recurrent gene mask와 class panel로 다시 추론해 다음을 확인했다.

- 입력 데이터와 canonical split SHA-256 일치
- OOF·test label agreement 100%
- OOF·test 확률 allclose 통과
- 최대 확률 차이 `2.9772949e-08` (`atol=rtol=1e-6`)
- 제출 CSV SHA-256 byte-level 일치:
  `0501cbcc23999d31fe428d8c9030e6a8895a9e8433e8ba438e81f635e22847cb`

재현 번들은
[`exp-476-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-476-repro-v1)에
보관했다(bundle SHA-256
`689e04f32a45c3ea2809ba1098fc671a2183614f13448638a08488b6cd0e423b`).

## 산출물과 판단

- Config: `configs/exp476_config_feature_pipeline.yaml`
- Runner: `scripts/run_exp476_config_feature_pipeline.py`
- Metrics: `reports/exp476_config_feature_pipeline/metrics.json`
- Fold feature/search: `reports/exp476_config_feature_pipeline/fold_feature_and_search.json`
- Reproduction: `reproducibility/exp476_config_feature_pipeline/`
- Submission: `submissions/exp476_config_feature_pipeline.csv`

결론은 `ARCHIVE`다. Config 기반 fold-safe 구조와 검증 코드는 보존하지만, 현재
성능으로는 EXP-374를 대체하지 않는다. Public 결과에 맞춰 panel, 탐색 공간이나
class weight를 사후 조정하지 않으며 다른 예측을 만드는 변경은 새 Experiment
Issue로 분리한다.
