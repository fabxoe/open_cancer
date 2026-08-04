# EXP-285 EXP-229 nested Optuna XGBoost

## 결론

EXP-229의 피처 정책을 고정한 채 각 outer-train 내부 3-fold에서만 XGBoost
하이퍼파라미터를 탐색한 결과, OOF Macro F1은 **0.4314709544**로 현재 Local
최고를 갱신했다. EXP-229보다 `+0.0084823799`, 이전 최고 EXP-313보다
`+0.0046800275` 높다. Log Loss도 EXP-229 대비 `-0.0100224018` 개선됐다.

다만 fold 표준편차는 `0.0117209428`로 EXP-229보다 `+0.0018529779`,
EXP-313보다 `+0.0032177259` 높다. 따라서 **성능 채택 후보**로 보존하되,
canonical OOF에 대한 반복 탐색과 fold 변동성 때문에 Public 제출·독립 seed 또는
재학습 검증 전에는 최종 모델로 확정하지 않는다.

이후 Public LB에 제출한 결과는 `0.320174485`(제출 ID `1510681`)였다.
EXP-229의 `0.3203598833`보다 `-0.0001853983`, 팀 최고 EXP-223의
`0.323243525`보다 `-0.003069040` 낮았다. nested Optuna의 큰 Local 개선이
Public에서는 재현되지 않았으므로 최종 선택 제출은 EXP-223을 유지한다.

## 실험 설계

- Issue: [#285](https://github.com/fabxoe/open_cancer/issues/285)
- 부모: EXP-229
- split: canonical stratified 5-fold, seed 42
- 피처·전처리·balanced sample weight·Macro-F1 checkpoint 정책: EXP-229 고정
- 각 outer fold의 학습 행에서만 3-fold inner CV 수행
- outer fold당 완료 trial 30개, 총 150개
- sampler: TPE, seed `42 + outer_fold`
- objective: inner-fold Macro F1 평균 최대화
- outer validation, test, Public LB는 trial 선택에 사용하지 않음
- 실행 환경: RunPod Secure Cloud RTX 4090

탐색 범위는 실행 전에 다음으로 고정했다.

| 파라미터 | 범위 |
|---|---|
| `max_depth` | 4–8 |
| `min_child_weight` | 1–10 |
| `subsample` | 0.5–0.9 |
| `colsample_bytree` | 0.5–0.9 |
| `reg_alpha` | 0–1 |
| `reg_lambda` | 0.5–5 |
| `learning_rate` | 0.02–0.08, log scale |

## 결과

| 지표 | EXP-285 | EXP-229 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4314709544 | 0.4229885745 | +0.0084823799 |
| Fold 평균 | 0.4318801637 | 0.4232332489 | +0.0086469148 |
| Fold 표준편차 | 0.0117209428 | 0.0098679649 | +0.0018529779 |
| Accuracy | 0.4221899694 | 0.4125141106 | +0.0096758587 |
| Log Loss | 1.8409389257 | 1.8509613276 | -0.0100224018 |

| Outer fold | Macro F1 | 선택 iteration | best inner trial | inner Macro F1 |
|---:|---:|---:|---:|---:|
| 0 | 0.4252500505 | 175 | 4 | 0.4125366955 |
| 1 | 0.4380602207 | 305 | 24 | 0.4113670011 |
| 2 | 0.4149180217 | 468 | 20 | 0.4061449195 |
| 3 | 0.4314910879 | 260 | 24 | 0.4182224705 |
| 4 | 0.4496814376 | 450 | 26 | 0.3952140088 |

EXP-229 대비 클래스별 큰 개선은 KIRC `+0.08024`, LGG `+0.05674`, DLBC
`+0.04087`, HNSC `+0.03392`, LIHC `+0.03355`다. 큰 하락은 BLCA
`-0.03497`, ACC `-0.03355`, STES `-0.02856`이며, 어떤 클래스도 `-0.05`
이상 붕괴하지 않았다.

## 실행 복구 기록

첫 장시간 실행은 150개 trial과 최종 5개 모델을 모두 만든 뒤, 당시 Pod의 오래된
metrics schema가 fold의 `model_parameters`와 `nested_tuning` 필드를 허용하지 않아
마지막 검증에서 종료 코드 1을 반환했다. 모델 학습이나 OOM 실패는 아니었다.

실패 시점 전체 payload를 Mac으로 먼저 회수한 뒤, Issue #285 브랜치에 최신 main의
PR #298 schema/finalize 수정을 반영했다. 같은 SQLite study를 재사용해 새 trial 없이
최종 outer 모델과 검증 단계만 다시 실행했다. 복구 실행 결과는 실패 전 OOF 지표와
submission SHA-256이 정확히 같았고 종료 코드 0으로 완료됐다.

## 재현성과 산출물

- Config: `configs/exp285_exp229_nested_optuna_xgb.yaml`
- Runner: `scripts/run_exp285_exp229_nested_optuna_xgb.py`
- Metrics: `reports/exp285_exp229_nested_optuna_xgb/metrics.json`
- Optuna 요약: `reports/exp285_exp229_nested_optuna_xgb/optuna_outer_00.json` 등 5개
- Optuna DB: `models/exp285_exp229_nested_optuna_xgb/optuna/outer_00.sqlite3` 등 5개
- OOF: `oof/exp285_exp229_nested_optuna_xgb.csv`
- test 확률: `preds/exp285_exp229_nested_optuna_xgb_test_proba.csv`
- submission: `submissions/exp285_exp229_nested_optuna_xgb.csv`
- reproducibility: `reproducibility/exp285_exp229_nested_optuna_xgb/`
- Release: [`exp-285-repro-v1`](https://github.com/fabxoe/open_cancer/releases/tag/exp-285-repro-v1)
- 실행 source commit: `893f0be9c82442bf5e3940848578dc7a73677af4`
- 재현 상태: `INFERENCE_VERIFIED`
- submission SHA-256:
  `6291e67c9a4ea4dfe34b294ed6ea9fa0f8e94708cc156f95566292655937145a`

저장 checkpoint 재추론 결과 test 라벨은 100% 일치했고 확률 최대 절대 차이는
`2.01e-7`로 `atol=1e-6`, `rtol=1e-6` 범위 안이다. 제출 CSV SHA-256도
byte-level로 일치했다. 다른 팀원의 fresh-clone 재학습 검증인
`TRAINING_VERIFIED`는 아직 수행하지 않았다.

RunPod 종료 전 다음 로컬 보관본을 SHA-256 검증했다.

- 공유용 archive: `exp285_shareable_repro_v1.tar.gz`, 약 24MB
- private forensic archive: `exp285_private_forensic_v1.tar.gz`, 약 1.5GB
  - raw·processed data, 전체 Git 이력, `.venv`, uv cache, 실패 전 백업 포함
  - SSH 키·토큰·shell history 제외

## 판단과 다음 단계

1. EXP-285는 Local 성능 연구와 앙상블 자산으로 보존하되 Public 대표 후보에서는
   후순위로 내린다.
2. Public 결과를 보고 같은 OOF에서 Optuna 범위나 파라미터를 다시 조정하지 않는다.
3. EXP-313과의 고정 0.5/0.5 blend는 EXP-323에서 이미 기각했으며 추가 가중치
   탐색을 하지 않는다.
4. 최종 수상 후보로 다시 검토하려면 다른 팀원이 clean 환경에서 재학습해
   `TRAINING_VERIFIED`까지 확인한다.
