# EXP-571: Parser-v4 QC 요약 및 event span 피처 ablation

## 실험 목적

EXP-567을 고정 부모로 사용하여 Parser-v4에서 추출한 데이터 품질 및 변이 범위 요약 피처가 암종 분류 성능에 미치는 영향을 검증했습니다.

부모 특징, LightGBM 모델 파라미터, canonical split, 클래스 순서 및 학습 정책은 유지하고 추가 피처만 변경했습니다.

## 실험 구성

### Base

EXP-567의 특징과 모델 설정을 그대로 재현한 비교 기준입니다.

### Parser QC

샘플별 Parser-v4 처리 결과를 다음과 같이 요약했습니다.

- complete parse 비율
- partial parse 비율
- unresolved 비율
- 기타 parse status 비율
- unresolved token 존재 여부

### Event span

Parser-v4에서 해석된 변이 event의 범위를 다음과 같이 요약했습니다.

- 관측 event 수
- 양수 span event 수
- 양수 span 비율
- span의 log1p 평균
- span의 log1p 표준편차
- span의 log1p 최댓값
- span의 log1p 90백분위수

## 평가 조건

- Parent: EXP-567
- 평가 지표: OOF Macro F1
- Split: 팀 canonical stratified 5-fold
- Seed: 42
- Test 데이터의 정답 또는 분포를 모델 선택에 사용하지 않음
- Base 재현 확인 후 두 ablation을 실행

## 결과

| Arm | OOF Macro F1 | Base 대비 | Accuracy | Log Loss | Fold std |
|---|---:|---:|---:|---:|---:|
| Base | 0.4477416384 | 기준 | 0.4363812288 | 1.8136045028 | 0.0045984625 |
| Parser QC | **0.4514285443** | **+0.0036869059** | **0.4400903080** | 1.8353693600 | 0.0078655955 |
| Event span | 0.4508327972 | +0.0030911588 | 0.4392839865 | 1.8320069203 | 0.0065282764 |

## 해석

Parser QC arm이 가장 높은 OOF Macro F1과 Accuracy를 기록했습니다. Parser-v4의 처리 상태와 unresolved 정도가 암종 분류에 활용할 수 있는 추가 신호를 제공한 것으로 해석합니다.

Event span arm도 Base 대비 Macro F1이 개선됐지만 Parser QC보다 낮았습니다.

두 arm 모두 Base보다 Log Loss와 fold 변동성이 악화됐습니다. 따라서 정답 클래스 선택 성능은 개선됐지만 예측 확률의 안정성과 보정 성능에는 손해가 있었습니다.

## 결론

- 최종 채택 후보: Parser QC arm
- Event span: 단독 개선 확인, 후속 조합 실험 후보
- Parser QC와 event span의 결합은 별도 Issue에서 검증
- 현재 데이콘 미제출
- Public 점수를 이용한 피처 조정은 수행하지 않음

## 산출물

- Base metrics: `reports/exp571_data_centric_features_parser_v4_base/metrics.json`
- Parser QC metrics: `reports/exp571_data_centric_features_parser_v4_parser_qc/metrics.json`
- Event span metrics: `reports/exp571_data_centric_features_parser_v4_event_span/metrics.json`
- Arm summary: `reports/exp571_data_centric_features_parser_v4/arm_summary.json`