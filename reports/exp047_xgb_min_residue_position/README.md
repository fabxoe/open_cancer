# EXP-047 Feature Factory + 유전자별 최소 단백질 잔기 위치

## 한눈에 보기

| 항목 | 실제 값 |
|---|---|
| 실험 ID / Issue | EXP-047 / #47 |
| 부모 실험 | EXP-033 |
| 유일한 모델 입력 변경 | 유전자별 `min_residue_position` 4,384개 추가 |
| 모델 | XGBoost, EXP-033과 동일 설정 |
| 전체 피처 수 | 35,084 |
| Local OOF Macro F1 | 0.4088132438 |
| Public LB | 미제출 |
| 판단 | 위치 family를 후속 확장 후보로 채택 |

## 무엇을 추가했나

EXP-033의 mutation-presence, 변이유형과 세 가지 log-burden 피처는 그대로
유지했다. 각 환자의 각 유전자 셀에서 변이 토큰에 적힌 숫자를 읽고 가장 작은
값 한 개를 추가했다.

예를 들어 한 셀이 다음과 같다고 하자.

```text
R132H 312_313QY>HH
```

토큰에 명시된 단백질 잔기 위치는 `132, 312, 313`이고 이 유전자의
`min_residue_position`은 `132`다. `WT`, 빈 셀 또는 위치를 읽을 수 없는 셀은
희소 행렬에 0으로 남는다. 기존 `mutated`와 `missing` 피처가 별도로 있으므로
이 0은 실제 0번 잔기를 뜻하지 않는다.

이 위치는 **입력 문자열에 적힌 단백질 잔기 위치**다. genomic coordinate,
codon nucleotide 위치, transcript 정규화 좌표 또는 단백질 길이를 추정한 값이
아니다.

## Feature Factory 검증

Factory `1.0.0`은 피처 이름 순서, family 정의, 입력 데이터와 유전자 순서를
Feature Spec으로 묶고 해시 기반 캐시를 만든다.

| 검증 | 결과 |
|---|---|
| 위치 family OFF 시 기존 EXP-005 feature names | SHA-256 동일 |
| 위치 family OFF 시 기존 EXP-005 train/test 행렬 | 원소 단위 동일 |
| EXP-047 train shape | `(6201, 35084)` |
| EXP-047 test shape | `(2546, 35084)` |
| Feature Spec SHA-256 | `562b712a314aebee07cf9d17c18639ec2116a24dbd15a0fe2288c82c6cc7107a` |

파서 QC는 다음과 같다.

| 항목 | train | test |
|---|---:|---:|
| 변이 토큰 수 | 255,164 | 337,512 |
| 위치가 추출된 토큰 | 255,164 | 337,512 |
| 위치 추출 성공률 | 100% | 100% |
| complex token | 341 (0.1336%) | 19,070 (5.6502%) |
| 여러 위치가 적힌 토큰 | 239 | 2,456 |

모든 토큰에서 숫자 위치는 추출됐지만 test의 complex token 비율은 train보다
크게 높다. 이는 위치 숫자를 읽는 데 실패했다는 뜻은 아니며, train에서 드문
표기 형태가 test에 더 많다는 분포 차이다. Public LB를 보고 파서 규칙을 바꾸지
않고 다음 family 설계에서 이 차이를 별도 안정성 대상으로 다룬다.

## 내부 검증 결과

공용 `data/splits/stratified_5fold_seed42.csv`와 EXP-033의 XGBoost 설정을
그대로 사용했다.

| 항목 | EXP-033 | EXP-047 | 차이 |
|---|---:|---:|---:|
| 전체 OOF Macro F1 | 0.4057244634 | 0.4088132438 | +0.0030887804 |
| fold 평균 | 0.4046139109 | 0.4084268650 | +0.0038129541 |
| fold 표준편차 | 0.0109735092 | 0.0085063656 | -0.0024671436 |
| Accuracy | 0.3981615868 | 0.4031607805 | +0.0049991937 |
| Log Loss | 1.8625637293 | 1.8519974947 | -0.0105662346 |

fold별 Macro F1은 다음과 같다.

| fold | Macro F1 | best iteration |
|---:|---:|---:|
| 0 | 0.4113274860 | 200 |
| 1 | 0.4106448428 | 205 |
| 2 | 0.3941926672 | 248 |
| 3 | 0.4057632107 | 220 |
| 4 | 0.4202061182 | 229 |

전체 OOF와 Accuracy가 개선됐고 Log Loss와 fold 변동성은 낮아졌다. 단 한 번의
5-fold 결과이므로 모든 위치 피처가 일반적으로 유효하다고 단정할 수는 없지만,
최소 위치 family를 제거할 이유는 없으며 max/span/bin의 독립 ablation으로
이어갈 근거는 생겼다.

## 재현 상태

clean source commit
`78c52694163c8b3f8e76557a93d271843b1627fa`에서 실행했다. 저장한 5개
checkpoint를 다시 불러와 test 예측을 재생성한 결과:

- 원본과 재생성 submission SHA-256:
  `56c9ecaba23426b159a8bd176ef7860c40d07098a6a9c7f167d1b6c42d7b68fe`
- test 라벨 일치율: 100%
- test 확률 최대 절대 차이: `2.968444823281402e-08`
- 허용 범위: `atol=1e-6`, `rtol=1e-6`
- 결과: `INFERENCE_VERIFIED`

Public leaderboard에는 제출하지 않았다. 따라서 checkpoint Release 보관은
리더보드 제출 후보로 결정될 때 수행한다.

## 관련 파일

- Config: `configs/exp047_xgb_min_residue_position.yaml`
- Resolved config:
  `reproducibility/exp047_xgb_min_residue_position/config.resolved.yaml`
- Metrics: `reports/exp047_xgb_min_residue_position/metrics.json`
- Submission: `submissions/exp047_xgb_min_residue_position.csv` (미제출)
- Reproduction:
  `reproducibility/exp047_xgb_min_residue_position/`
- Factory 운영 안내: `docs/FEATURE_FACTORY.md`
