# EXP-611: Parser-v4 QC + Event Span Combined Ablation

## 실험 정보

- Experiment ID: EXP-611
- Issue: #611
- 담당자: Gomin-art
- 브랜치: `issue-611-exp-parser-v4-qc-event-span-combined`
- Parent: EXP-571 Parser QC arm
- 상태: COMPLETED
- 최종 판단: REJECTED
- 리더보드 제출: 미제출

## 목적

EXP-571에서 각각 Base 대비 개선된 Parser QC 요약 피처와 event span
피처를 함께 사용했을 때 추가적인 OOF Macro F1 개선이 발생하는지
검증했습니다.

부모 모델의 Parser-v4 특징, LightGBM 설정, canonical split, 클래스 순서와
학습 정책은 유지하고 Parser QC와 event span 피처의 결합 여부만 변경했습니다.

## 고정 조건

- canonical stratified 5-fold split
- random seed 42
- Parent: EXP-571 Parser QC arm
- Parser-v4 전처리 및 클래스 순서 유지
- test 데이터는 모델 학습 및 feature 선택에 사용하지 않음
- Public LB 결과를 이용한 설정 변경 없음

## 실험 결과

| 항목 | 결과 |
|---|---:|
| OOF Macro F1 | 0.4510079660 |
| Fold mean Macro F1 | 0.4494159537 |
| Fold std | 0.0065771075 |
| Accuracy | 0.4392839865 |
| Log Loss | 1.8720815334 |

### Fold별 결과

| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |
|---:|---:|---:|---:|---:|
| 0 | 0.4393915164 | 0.4294923449 | 1.8010552910 | 79 |
| 1 | 0.4492104205 | 0.4266129032 | 1.8179800465 | 84 |
| 2 | 0.4455627087 | 0.4379032258 | 1.9375975479 | 44 |
| 3 | 0.4555237109 | 0.4500000000 | 1.8995398124 | 271 |
| 4 | 0.4573914120 | 0.4524193548 | 1.9042922484 | 44 |

## 부모 및 단독 arm 비교

| 실험 | OOF Macro F1 | Log Loss | Fold std |
|---|---:|---:|---:|
| EXP-571 Base | 0.4477416384 | 1.8136045028 | 0.0045984625 |
| EXP-571 Parser QC | **0.4514285443** | 1.8353693600 | 0.0078655955 |
| EXP-571 Event span | 0.4508327972 | 1.8320069203 | 0.0065282764 |
| EXP-611 Combined | 0.4510079660 | 1.8720815334 | 0.0065771075 |

### 성능 차이

- EXP-571 Base 대비 Macro F1: `+0.0032663275`
- EXP-571 Parser QC 대비 Macro F1: `-0.0004205784`
- EXP-571 Event span 대비 Macro F1: `+0.0001751687`
- EXP-571 Parser QC 대비 Log Loss: `+0.0367121734`

## 해석

Parser QC와 event span을 결합하면 Base와 event span 단독 arm보다는 OOF
Macro F1이 높았지만, 기존 최고인 Parser QC 단독 arm을 넘지 못했습니다.

또한 Log Loss가 모든 EXP-571 arm보다 악화됐으며 fold별 best iteration도
44회에서 271회까지 크게 달랐습니다. 두 feature family가 일부 중복된
신호를 제공하거나 특정 fold에서 불안정하게 작용했을 가능성이 있습니다.

## 결론

결합 구성은 Parser QC 단독 대비 추가적인 성능 이득이 없고 확률 품질이
악화되어 `REJECTED`로 기록합니다.

후속 LightGBM 규제 및 multi-seed 안정성 실험은 EXP-611이 아니라
EXP-571 Parser QC arm을 부모로 사용합니다.

## 산출물

- 측정 지표: [metrics.json](metrics.json)
- 실행 설정: `configs/exp611_parser_v4_qc_event_span_combined.yaml`
- 실행 코드: `scripts/run_exp611_parser_v4_qc_event_span_combined.py`