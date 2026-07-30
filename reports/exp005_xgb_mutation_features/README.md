# EXP-005 XGBoost + 유전자×변이유형 희소 피처

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-005 / #5 |
| 목적 | 단순 변이 존재 여부보다 세분화된 변이 유형 피처의 암종 분류 성능 검증 |
| 핵심 입력 | 4,384개 유전자의 변이 여부·변이 유형과 샘플 집계 피처 |
| 모델 | XGBoost `XGBClassifier` |
| Local OOF Macro F1 | 0.4043796587000222 |
| Public LB | 0.2987843366 |
| 판단 | 제출 시점 1위, checkpoint 추론 재현 완료 |

## 원본 데이터와 입력

train은 환자 6,201명, test는 2,546명이며 각 환자는 4,384개 유전자 열로
표현된다. 각 유전자 셀은 변이가 관찰되지 않은 `WT`, 빈 값 또는 `S27N`,
`R1538*`, `L1854fs` 같은 변이 문자열이다.

원본 CSV는 수정하지 않았다. 피처 생성 결과는 Git에서 제외되는
`data/processed/mutation_type_features/`에 저장했고, train과 test에 같은 유전자
순서와 같은 변환 규칙을 적용했다.

## 핵심 개념과 피처

기존 mutation-presence 방식은 `WT`를 0, 모든 변이를 1로 표현한다. EXP-005는
변이가 존재한다는 정보에 변이 유형을 추가했다.

| 원본 예시 | 분류 | 의미 |
|---|---|---|
| `S27N` | missense | 표시된 아미노산이 다른 아미노산으로 변경 |
| `R895R` | synonymous | 표시된 기준·변경 아미노산이 동일 |
| `R1538*` | nonsense | 종결 표기 발생 |
| `L1854fs`, `WQ288fs` | frameshift | `fs`로 끝나는 frameshift 표기 |
| 그 밖의 비정형 표기 | complex | 현재 규칙으로 위 유형에 확정 분류하지 않음 |

유전자마다 `mutated`, 다섯 변이 유형과 `missing` indicator를 만들었다. 여기에
환자별 변이 유전자 수, 전체 변이 수, 복수 변이 유전자 수, 유형별 개수와 결측
개수를 추가했다.

최종 피처는 30,697개다.

```text
샘플 집계 피처 9개 + 4,384개 유전자 × 유전자별 피처 7개 = 30,697개
```

대부분 값이 0이므로 CSR 희소행렬을 사용했다. HGVS/MANE 재표기와 단백질 상대
위치는 원 transcript를 확인할 수 없어 모델 입력에서 제외했다.

## 모델이 학습하는 정보

모델 입력은 유전자별 변이 여부, 변이 유형과 환자 전체의 변이량이다. 타깃은 고정
순서의 26개 `SUBCLASS`다. 피처 생성에는 `SUBCLASS`를 사용하지 않았고 클래스
불균형을 고려해 각 fold의 학습 데이터에서 balanced sample weight를 계산했다.

실제 XGBoost 파라미터 전체는
`reproducibility/exp005_xgb_mutation_features/config.resolved.yaml`에 기록했다.

## 검증 방법

팀 공용 `data/splits/stratified_5fold_seed42.csv`를 사용했다. 각 fold에서 나머지
4개 fold로 학습하고 한 fold를 검증해, 모든 환자의 OOF 예측을 채운 뒤 전체 OOF
Macro F1을 계산했다.

- fold 수: 5
- 기본 seed: 42
- fold seed: 42, 43, 44, 45, 46
- primary metric: 전체 OOF Macro F1
- test 또는 validation의 타깃을 피처 생성에 사용하지 않음

## 실제 결과

### Local OOF

| Fold | Macro F1 |
|---:|---:|
| 0 | 0.3957389475242374 |
| 1 | 0.41264527023707276 |
| 2 | 0.4011635978874454 |
| 3 | 0.39173710435471243 |
| 4 | 0.4130462426049025 |

- 전체 OOF Macro F1: **0.4043796587000222**
- Fold 평균: 0.40286623252167403
- Fold 표준편차: 0.008681207678921672
- Accuracy: 0.39654894371875504
- Log Loss: 1.8632071018218994

클래스별 F1은 ACC 0.7910, SKCM 0.7224, COAD 0.7170, THCA 0.6991로 상대적으로
높았다. KIRC 0.1693, PAAD 0.1849, KIPAN 0.1987, SARC 0.1995는 낮았다.
전체 클래스별 값과 confusion matrix는 `metrics.json`에 있다.

### Public leaderboard

- 제출 파일: `exp005_xgb_mutation_features.csv`
- 제출 ID: 1506233
- 제출 시각: 2026-07-30 18:26:30 KST
- Public score: **0.2987843366**
- 순위: **1위 (제출 화면 확인 시점)**

사용자가 제공한 같은 제출 화면에서 EXP-003 XGBoost baseline의 Public score는
0.228167518이었다. EXP-005는 이 화면상 점수보다 0.0706168186 높다. 이는 Public
leaderboard 비교이며 Local OOF 개선을 뜻하지는 않는다.

## 해석과 한계

- 변이 유형을 추가한 모델은 실제 Public score 0.2987843366을 기록했다.
- Local OOF 0.40438과 Public 0.29878 사이에 차이가 있어 train/test 분포 차이 또는
  leaderboard 표본 차이의 영향을 확인할 필요가 있다.
- 문자열 규칙 기반 분류이므로 `complex`에는 서로 다른 생물학적 변이가 섞여 있다.
- transcript, 단백질 위치와 병원성은 판단하지 않았다.
- 피처 30,697개에 비해 환자는 6,201명이므로 과적합 가능성이 있다.
- 순위는 제출 화면 확인 시점의 값이며 이후 바뀔 수 있다.
- 제출 당시에는 재현 상태가 `NOT_STARTED`였으나, 이후 저장 checkpoint 추론으로
  동일 제출을 재생성해 `INFERENCE_VERIFIED`로 승격했다.
- checkpoint와 재현 번들의 GitHub Release 보관은 아직 완료되지 않았다.

## 다음 실험 후보

1. 동일한 XGBoost 설정과 공용 split에서 4,384개 mutation-presence 피처만 사용해
   Local OOF를 직접 비교한다.
2. `complex` 포함 여부와 샘플 집계 피처 포함 여부를 각각 별도 Experiment Issue로
   비교한다.
3. 비작성자가 clean 환경에서 재학습을 검증하고 checkpoint와 재현 번들을
   GitHub Release에 보관한다.

## 추론 재현 결과

- 검증 시각: 2026-07-30T09:38:54.622845+00:00
- 원본·공용 split·가공 피처 해시: 모두 일치
- 기존 제출 SHA-256: `7bc3e64e1904d9b4007bc141dde771a39e7527172f3cd24c25c408000103183c`
- 재생성 제출 SHA-256: `7bc3e64e1904d9b4007bc141dde771a39e7527172f3cd24c25c408000103183c`
- test 예측 라벨 일치율: 1.0
- test 확률 최대 절대 차이: 2.9788970956623473e-08
- 허용 오차: `atol=1e-6`, `rtol=1e-6`
- 결과: `INFERENCE_VERIFIED`

## 재현과 관련 파일

- Config: `reproducibility/exp005_xgb_mutation_features/config.resolved.yaml`
- Metrics: `reports/exp005_xgb_mutation_features/metrics.json`
- Submission: `submissions/exp005_xgb_mutation_features.csv`
- Reproduction: `reproducibility/exp005_xgb_mutation_features/artifact_manifest.json`
- Source commit: `816d0a5e070c29d2f549e4fb25b81ec5c0ad5f7b`
- Reproduction status: `INFERENCE_VERIFIED`
