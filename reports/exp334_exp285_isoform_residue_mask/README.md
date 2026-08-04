# EXP-334 EXP-285 고정 fold 파라미터 + Ensembl semantic residue mask

## 결론

EXP-285의 fold별 Optuna 최종 파라미터와 나머지 feature family를 그대로 고정하고,
EXP-313에서 검증한 Ensembl release 116 semantic mask를 residue-position 집계에만
적용했다. OOF Macro F1은 `0.4351340093`으로 EXP-285보다 `+0.0036630549`
개선되어 현재 Local 최고를 갱신했다.

Accuracy와 fold 안정성도 함께 개선됐다. Log Loss는 `+0.0010001659`로 아주 조금
악화됐지만 사전 허용 범위 `+0.01` 이내이며, 어떤 클래스도 F1이 `-0.05` 이상
붕괴하지 않았다. 따라서 EXP-334를 새 제출 후보로 채택해 Public LB에 제출했다.
Public Macro F1은 `0.3150635813`으로 팀 최고 EXP-223의 `0.323243525`보다
`-0.0081799437` 낮았다. Local 개선이 Public으로 전이되지 않았으므로 최종 선택
제출은 EXP-223을 유지한다. EXP-334의 의미 감사 결과는 보존하지만 Public 대표
후보에서는 후순위로 내리며, 최종 후보 지정에는 여전히 독립 재학습 검증이 필요하다.

## 통제 실험 계약

- Issue/브랜치: #334 / `issue-334-exp285-semantic-residue-mask`
- 부모: EXP-285; semantic mask 정의 출처: EXP-313
- canonical stratified 5-fold, seed 42와 26개 클래스 순서 고정
- EXP-285의 각 outer fold Optuna 최종 JSON과 SHA-256을 config에 동결
- 현재 masked feature에서 Optuna를 다시 실행하지 않음
- 유지: mutation presence/type, sample aggregate, hotspot, pathway family,
  balanced sample weight, Macro-F1 checkpoint 정책
- 유일한 변경: residue-position 집계 token 범위
  - 유지: `MANE_MATCH`, `CANONICAL_MATCH`, `OTHER_ISOFORM_MATCH`
  - 제외: `POSITION_VALID_REF_MISMATCH`, `OUTSIDE_ALL_KNOWN_ISOFORMS`,
    `COMPLEX_OR_UNMAPPABLE`
- SUBCLASS·test 분포·Public LB는 mask나 파라미터 선택에 사용하지 않음

## 결과

| 지표 | EXP-334 | EXP-285 | 변화 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4351340093 | 0.4314709544 | +0.0036630549 |
| Fold 평균 | 0.4353424231 | 0.4318801637 | +0.0034622594 |
| Fold 표준편차 | 0.0106544650 | 0.0117209428 | -0.0010664778 |
| Accuracy | 0.4238026125 | 0.4221899694 | +0.0016126431 |
| Log Loss | 1.8419390917 | 1.8409389257 | +0.0010001659 |

Fold Macro F1은 `0.4293405 / 0.4420335 / 0.4226493 / 0.4300833 /
0.4526057`이고, 선택 iteration은 `131 / 356 / 460 / 256 / 489`다.

클래스별 가장 큰 개선은 BLCA `+0.03573`, DLBC `+0.03448`, KIRC
`+0.02699`, LIHC `+0.02339`였다. 가장 큰 하락은 LUAD `-0.01587`, HNSC
`-0.01478`, UCEC `-0.01391`, PCPG `-0.01264`로, 사전 붕괴 한계
`-0.05`를 넘은 클래스는 없었다.

## MANE coverage 구간 OOF 진단

모델 선택과 무관한 사후 안전성 진단으로 train token의 sample별 MANE_MATCH
비율을 계산했다. 변이 token이 존재하는 6,107개 sample의 target-independent
quartile 경계는 `0.81818 / 0.88889 / 0.95`였다. 각 subset에서도 26개 고정
클래스 순서로 Macro F1을 계산했다.

| 구간 | 행 수 | MANE 비율 범위 | EXP-285 | EXP-334 | 변화 |
|---|---:|---:|---:|---:|---:|
| Q1 low | 1,566 | 0.0000–0.8182 | 0.38038 | 0.38417 | +0.00378 |
| Q2 | 1,500 | 0.8196–0.8889 | 0.40063 | 0.40646 | +0.00583 |
| Q3 | 1,525 | 0.8893–0.9500 | 0.39109 | 0.38857 | -0.00252 |
| Q4 high | 1,516 | 0.9508–1.0000 | 0.36596 | 0.37196 | +0.00601 |

변이 token이 없던 94개 sample은 두 모델의 예측과 점수가 동일했다. 가장 낮은
MANE 구간에서도 성능이 하락하지 않았으므로, mask가 high-MANE sample에만
의존한다는 뚜렷한 증거는 관찰되지 않았다. 다만 이 subset 점수는 표본 수와
클래스 구성이 서로 달라 전체 OOF 점수와 직접 비교하지 않으며, threshold나
추가 피처 선택에 사용하지 않는다.

## 실행 환경과 재현성

- 공식 source commit: `cf0bc5382b067b3dad63f3253b4b724cdcbdec28`
- 실행 환경: RunPod Secure Cloud NVIDIA A40 46GB, XGBoost 3.2.0
- EXP-285 원 실행 RTX 4090과 GPU 기종이 다르므로 작은 차이를 완전한
  feature-only 결정론으로 확대 해석하지 않음
- Config: `configs/exp334_exp285_isoform_residue_mask.yaml`
- Runner: `scripts/run_exp334_exp285_isoform_residue_mask.py`
- Metrics: `reports/exp334_exp285_isoform_residue_mask/metrics.json`
- OOF: `oof/exp334_exp285_isoform_residue_mask.csv`
- test 확률: `preds/exp334_exp285_isoform_residue_mask_test_proba.csv`
- submission: `submissions/exp334_exp285_isoform_residue_mask.csv`
- submission SHA-256:
  `b7b57180ac686553c9f2c65c5634043e756fa8988df9d01e5f441edc485f3918`
- 재현 상태: `INFERENCE_VERIFIED`
- Release: [exp-334-repro-v1](https://github.com/fabxoe/open_cancer/releases/tag/exp-334-repro-v1)
- Release bundle SHA-256:
  `78ee11a6a47f1a5acb2f9e9312ece44193974c5820774ce89d97beac070237f7`
- checkpoint 추론: 제출 SHA-256 일치, test label 100%, 확률 최대 차이
  `1.4582672e-7`

첫 두 RTX 4090 할당은 컨테이너가 `uptime 0`에서 시작되지 않아 삭제했고, A40
Pod에서 공식 실행했다. 첫 A40 시도는 원격 `git user.name` 누락, 두 번째는
저장소 밖 raw symlink의 상대경로 manifest 제약으로 학습 전에 중단됐다. 두 문제를
해결한 뒤 같은 clean source commit에서 수행한 세 번째 실행만 공식 결과로 썼다.

## 판단과 다음 행동

M1 Local gate는 통과했지만 Public `0.3150635813`은 EXP-223보다 낮아 EXP-334를
대표 제출 후보로 승격하지 않는다. 고순도 `MANE_MATCH only` ablation을 진행한다면
이번 Public 결과로 mask나 threshold를 역조정하지 않고, 별도 Experiment Issue에서
이미 사전 정의한 frozen parameter 계약을 한 번만 검증한다. EXP-334를 최종 후보로
다시 검토하려면 다른 팀원이 fresh clone에서 `TRAINING_VERIFIED`를 완료하고 Public
전이 실패 가능성까지 함께 감사해야 한다.
