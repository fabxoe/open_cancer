# EXP-628 EXP-527+EXP-596 블렌드 가중치 nested 선택

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-628 / #628 |
| 목적 | EXP-623(0.5/0.5 고정 블렌드)의 explore-mode 참고 스윕이 사후에 찾은 0.4/0.6이 look-ahead 없이도 재현되는지, leave-one-outer-fold-out nested weight search로 확인 |
| 방법 | 재학습 없음. 각 outer fold의 가중치를 나머지 4개 fold의 OOF만으로 사전 고정 grid(0.00~1.00, 0.05 간격)에서 선택하고, 그 가중치로 해당 fold만 블렌드 |
| Local OOF Macro F1 | 0.4647479423 (EXP-623 대비 +0.0029646045) |
| Public LB | 미제출(팀 논의 후 진행) |
| 판단 | OOF Macro F1·Accuracy 개선, fold std는 오히려 감소, 클래스 붕괴 없음, 5개 fold 전부 동일 가중치(0.35) 선택 — `ADOPT_WITH_CAUTION`, 현재 26-class 전부 예측하는 Local 최고 후보 |

## 배경

EXP-623 보고서에는 `RUN_MODE=explore`로 EXP-527 가중치를 0.3~1.0에서 0.1
단위로 스윕한 참고 결과가 남아 있다. 0.4/0.6이 OOF Macro F1
0.4639450817로 공식 0.5/0.5(0.4617833378)보다 근소하게 높았지만, 이 값은
**같은 OOF에서 사후에** 찾은 것이라 채택 근거로 쓰지 않았고 파일도 저장하지
않았다(PROJECT_CONTEXT.md의 target/test 분포로 가중치를 사후 조정하지
않는다는 원칙, ABC-Stack 로드맵 G5의 "다른 가중치는 별도 Experiment
Issue와 사전 명시된 후보 집합이 필요" 규정).

이 실험은 "0.5/0.5보다 나은 가중치가 실제로 있는가"를 look-ahead 없이
검증한다. 단순히 0.4/0.6을 사전 고정해 재실행하는 대신, 더 엄격한 방법인
leave-one-outer-fold-out nested weight search를 사용해 각 fold의 가중치
선택 과정에서 그 fold의 정답을 전혀 보지 않도록 했다.

## 핵심 개념과 방법

기존 5-fold canonical split(`data/splits/stratified_5fold_seed42.csv`)을
그대로 outer split으로 쓴다. 각 outer fold `i`(0~4)에 대해:

1. **가중치 선택**: fold `i`를 제외한 나머지 4개 fold의 OOF 행(약 4,960~4,961개)만
   사용해, 사전 고정 grid `w ∈ {0.00, 0.05, ..., 1.00}`(EXP-527 가중치,
   EXP-596은 `1-w`) 중 Macro F1이 가장 높은 `w_i`를 고른다. fold `i`의
   라벨은 이 단계에서 전혀 사용하지 않는다.
2. **fold `i` 예측**: 선택된 `w_i`로 fold `i` 행만 `w_i * EXP-527 확률 +
   (1-w_i) * EXP-596 확률`로 블렌드한다.
3. 5개 fold를 이어 붙인 전체가 공식 OOF다 — look-ahead 없이 얻은 진짜
   nested 추정치다.
4. **배포용 최종 가중치**: 5개 fold가 선택한 `w_i`의 평균을 grid에서 가장
   가까운 값으로 스냅한다. 이 집계 규칙(`mean_snap_to_grid`)은 실행 전
   `configs/exp628_nested_blend_weight_exp527_exp596.yaml`에 고정했고,
   결과를 보고 바꾸지 않았다. 이 가중치로 test 확률을 블렌드해 submission을
   만든다.

grid 간격 `0.05`는 EXP-623의 explore 스윕(`0.1` 간격)보다 촘촘해, 원래
스윕이 시도하지 않았던 `0.3`과 `0.4` 사이 값도 탐색한다.

## 검증 방법

두 parent(EXP-527, EXP-596)의 저장된 OOF·test 확률만 읽어 계산하므로 별도
학습·검증 절차는 없다. `open_cancer.probability_blend.blend_probability_frames`로
컴포넌트 정합성(ID·fold·정답 일치, 확률 유효성)을 먼저 검증한 뒤, numpy
배열로 fold별 grid 탐색을 수행했다. 재실행해 가중치 선택·확률·제출 CSV
SHA-256이 모두 일치함을 확인했다(`INFERENCE_VERIFIED`, 결정론적 계산이라
확률 최대 절대 오차 `0.0`).

## 실제 결과

| 지표 | EXP-628(nested) | EXP-623(0.5/0.5) | 차이 |
|---|---:|---:|---:|
| OOF Macro F1 | 0.4647479423 | 0.4617833378 | +0.0029646045 |
| Fold 평균 | 0.4654638314 | 0.4621505222 | +0.0033133092 |
| Fold 표준편차 | 0.0093589481 | 0.0120916724 | -0.0027327243(개선) |
| Accuracy | 0.4486373166 | 0.4450895017 | +0.0035478149 |
| Log Loss | 1.9979672657 | 1.9898206493 | +0.0081466164(소폭 악화) |

### fold별 선택 가중치

| Fold | 선택된 EXP-527 가중치 | inner(4-fold) Macro F1 | fold `i` 자체 Macro F1 |
|---:|---:|---:|---:|
| 0 | 0.35 | 0.4672653202 | 0.4564203442 |
| 1 | 0.35 | 0.4656974861 | 0.4628770827 |
| 2 | 0.35 | 0.4609593361 | 0.4813051358 |
| 3 | 0.35 | 0.4635031716 | 0.4700538237 |
| 4 | 0.35 | 0.4665137554 | 0.4566627707 |

**5개 fold 전부 동일한 가중치(0.35)를 독립적으로 선택했다**(`weight_range_across_folds
= 0.0`, 사전 설정 불안정 임계값 `0.30`을 크게 하회). 어떤 fold의 정답도
그 fold 자신의 가중치 선택에 관여하지 않았는데도 5번 모두 같은 값에
수렴한 것은, 이 가중치가 두 OOF 세트 사이의 우연한 노이즈가 아니라 안정적인
신호라는 강한 증거다. 최종 배포 가중치도 그대로 `0.35/0.65`다.

흥미로운 점은 이 값이 EXP-623의 explore 스윕이 찾은 `0.4/0.6`과 다르다는
것이다. 원래 스윕은 `0.1` 간격이라 `0.3`과 `0.4` 사이를 시도하지 않았고,
`0.05` 간격의 이번 grid가 그 사이의 더 나은 지점(`0.35`)을 찾아냈다. 게다가
nested(정직한) 추정치 `0.4647479423`가 원래 peeking 스윕의 `0.4/0.6` 값
`0.4639450817`보다도 높다 — 사후 peeking이 실제로는 최적점을 과대평가하는
게 아니라, 더 거친 격자 때문에 진짜 최적점을 놓쳤을 뿐이라는 뜻이다.

### 클래스별 비교(EXP-623 대비)

| 방향 | 클래스(델타) |
|---|---|
| 큰 개선 | DLBC `+0.0497`, BLCA `+0.0372`, TGCT `+0.0273`, LGG `+0.0197`, KIRC `+0.0197` |
| 큰 하락 | COAD `-0.0298`, CESC `-0.0272`, SKCM `-0.0269`, ACC `-0.0166` |

`-0.05` 붕괴 기준을 넘는 클래스는 없다(최대 하락 COAD `-0.0298`).

## 해석과 한계

- OOF Macro F1·Accuracy가 개선했고, fold 표준편차는 오히려 **감소**했다
  (EXP-623 채택 시 유일한 우려였던 fold std 증가가 이번엔 없다).
- Log Loss는 `+0.0081` 소폭 악화됐다. ABC-Stack 로드맵 G3의 모델 품질
  하한(단일 모델 대비 log loss `0.01` 이상 악화 시 제외)을 참고 기준으로
  삼으면 이 값은 그 임계값 아래라 "명백한 악화"로 보지 않았다. 다만 EXP-623이
  EXP-527 대비 log loss를 크게 개선했던 것과 달리 이번엔 그 개선분의 일부가
  줄어든 것이므로 투명하게 기록한다.
- 5개 fold가 독립적으로 동일한 가중치(0.35)를 선택한 것은 이례적으로 강한
  안정성 신호이며, fold 하나의 우연에 좌우된 결과가 아니다.
- 이 실험은 EXP-527·EXP-596의 OOF·test 확률을 그대로 재사용하므로, 두
  parent 모델 자체의 한계(KIPAN·SARC·GBMLGG 등 저성능 클래스)는 그대로
  이어받는다.
- Public 제출은 이 보고서만으로 진행하지 않으며, 팀 논의를 거친다.

## 다음 실험 후보

- 팀 논의 후 Public 제출 검토. 제출 시 리더보드 제출 이력에 기록한다.
- EXP-567(LightGBM) 등 추가 다양성 후보가 확보되면 3-way 이상 nested weight
  search 또는 cross-fitted meta-model(#505 S2)로 확장한다.

## 재현과 관련 파일

- Config: `configs/exp628_nested_blend_weight_exp527_exp596.yaml`
- Runner: `scripts/run_exp628_nested_blend_weight_exp527_exp596.py`
- Resolved config: `reproducibility/exp628_nested_blend_weight_exp527_exp596/config.resolved.yaml`
- Metrics: `reports/exp628_nested_blend_weight_exp527_exp596/metrics.json`
- OOF: `oof/exp628_nested_blend_weight_exp527_exp596.csv`
- Test probability: `preds/exp628_nested_blend_weight_exp527_exp596_test_proba.csv`
- Submission: `submissions/exp628_nested_blend_weight_exp527_exp596.csv`(DACON 미제출)
- Reproduction status: `INFERENCE_VERIFIED`(결정론적 재계산으로 가중치 선택·제출 SHA-256·라벨·확률 완전 일치 확인)
